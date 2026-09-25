#!/home/cloud/microflow_server/bin/python

import sys
sys.path.append('/home/cloud/microflow_server/lib/python3.9/site-packages')

import json
import os
import shutil
import time
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
from airflow.utils.dates import days_ago

default_args = {
    "owner": "Sirisha",
    "depends_on_past": False,
    "start_date": datetime(2026, 3, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

# ============================================================
# Paths
# ============================================================
PROJECT_CONFIG = Path("/home/cloud/cnms-qr-sample-tracking-main/project_config.json")
BRAVE_ROOT = Path("/home/cloud/BraVE")
STAGING_ROOT = Path("/home/cloud/Globus-Personal-Docker/data")
# File must not have been modified for at least 2 minutes
MIN_FILE_AGE_SECONDS = 120

# ============================================================
# Read transfer configuration
# ============================================================
def load_transfer_config():
    if not PROJECT_CONFIG.exists():
        raise FileNotFoundError(
            f"Project config not found: {PROJECT_CONFIG}"
        )
    with open(PROJECT_CONFIG, "r") as f:
        project_data = json.load(f)
    transfer = project_data.get("transfer")
    if not transfer:
        raise RuntimeError("'transfer' section missing from project_config.json")
    source = Path(transfer["source_folder"])
    destination_relative = Path(transfer["destination_folder"])
    destination = STAGING_ROOT / destination_relative
    return source, destination

# ============================================================
# Check whether file is old enough to copy
# ============================================================
def file_is_stable(file_path):
    try:
        age = time.time() - file_path.stat().st_mtime
        return age >= MIN_FILE_AGE_SECONDS
    except OSError:
        return False
# ============================================================
# Check whether staging already has this file
# ============================================================
def needs_copy(source, destination):
    if not destination.exists():
        return True
    try:
        src = source.stat()
        dst = destination.stat()
        if (
            src.st_size == dst.st_size
            and dst.st_mtime >= src.st_mtime
        ):
            return False
    except OSError:
        return True
    return True
# ============================================================
# Synchronize configured BRaVE folder
# ============================================================
def sync_brave_to_staging(**context):
    source_folder, destination_folder = load_transfer_config()
    print("=" * 70)
    print(" BRaVE -> GLOBUS STAGING")
    print("=" * 70)
    print(f"Source      : {source_folder}")
    print(f"Destination : {destination_folder}")
    # --------------------------------------------------------
    # Safety checks
    # --------------------------------------------------------
    if not source_folder.exists():
        raise RuntimeError(
            f"Source folder does not exist: {source_folder}")
    if not source_folder.is_dir():
        raise RuntimeError(f"Source is not a directory: {source_folder}")
    try:
        source_folder.resolve().relative_to(
            BRAVE_ROOT.resolve()
        )
    except ValueError:
        raise RuntimeError(
            f"Source must be inside {BRAVE_ROOT}"
        )
    destination_folder.mkdir(
        parents=True,
        exist_ok=True
    )
    copied_count = 0
    skipped_count = 0
    waiting_count = 0
    # --------------------------------------------------------
    # Recursively scan ONLY the configured source folder
    # --------------------------------------------------------

    for source_file in source_folder.rglob("*"):

        if not source_file.is_file():
            continue
        # Ignore hidden/temp files
        if source_file.name.startswith("."):
            continue
        if source_file.name.endswith(
            (".tmp", ".part", ".copying")
        ):
            continue
        # Preserve hierarchy INSIDE selected source directory
        relative_path = source_file.relative_to(
            source_folder
        )
        destination_file = (
            destination_folder / relative_path
        )
        # ----------------------------------------------------
        # Already synchronized
        # ----------------------------------------------------
        if not needs_copy(
            source_file,
            destination_file
        ):
            skipped_count += 1
            continue
        # ----------------------------------------------------
        # File may still be acquiring
        # ----------------------------------------------------

        if not file_is_stable(source_file):
            print(
                f"[WAIT] {source_file} may still be acquiring"
            )
            waiting_count += 1
            continue
        # ---------------------------------------------------
        # Create corresponding destination subfolder
        # ----------------------------------------------------
        destination_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        temp_file = destination_file.with_name(
            destination_file.name + ".copying"
        )
        print(f"[COPY] {source_file}")
        print(f"    -> {destination_file}")
        try:
            shutil.copy2(
                source_file,
                temp_file
            )
            # Make sure complete file was copied
            if (
                source_file.stat().st_size
                != temp_file.stat().st_size
            ):
                raise RuntimeError(
                    "Source and destination file sizes differ"
                )
            # Atomic rename
            os.replace(
                temp_file,
                destination_file
            )
            copied_count += 1
            print(
                f"[SUCCESS] {relative_path}"
            )
        except Exception:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise
    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    print()
    print("=" * 70)
    print(f"Copied  : {copied_count}")
    print(f"Existing: {skipped_count}")
    print(f"Waiting : {waiting_count}")
    print("=" * 70)
    context["ti"].xcom_push(
        key="files_copied",
        value=copied_count
    )
    return copied_count

# ============================================================
# Trigger DataFed only when something was copied
# ============================================================

def new_files_available(**context):
    copied_count = context["ti"].xcom_pull(
        task_ids="sync_brave_to_staging",
        key="files_copied"
    )
    copied_count = copied_count or 0
    if copied_count > 0:
        print(
            f"[INFO] {copied_count} new file(s) staged."
        )
        print("[INFO] Triggering DataFed pipeline.")
        return True
    print("[INFO] Nothing new. DataFed pipeline not triggered.")
    return False
# ============================================================
# DAG
# ============================================================
with DAG(
    dag_id="brave_staging_sync",
    default_args=default_args,
    description="Copies new files from BRaVE mounted storage into Globus staging",
    schedule_interval=timedelta(minutes=5),
    catchup=False,
    max_active_runs=1,
    tags=["BRaVE", "Globus", "DataFed"],
) as dag:
    sync_files = PythonOperator(
        task_id="sync_brave_to_staging",
        python_callable=sync_brave_to_staging,
    )

    check_files = ShortCircuitOperator(
        task_id="new_files_available",
        python_callable=new_files_available,
    )

    trigger_datafed = TriggerDagRunOperator(
        task_id="trigger_datafed_orchestration",
        trigger_dag_id="datafed_orchestration_pipeline",
        wait_for_completion=False,
    )

    sync_files >> check_files >> trigger_datafed