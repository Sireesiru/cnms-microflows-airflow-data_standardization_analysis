#!/home/cloud/microflow_server/bin/python

import sys
sys.path.append('/home/cloud/microflow_server/lib/python3.9/site-packages')

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess
import logging

# -------------------------------------------------------------------------
# Default arguments
# -------------------------------------------------------------------------

default_args = {
    "owner": "Sirisha",
    "depends_on_past": False,
    "start_date": datetime(2026, 3, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=2),}

# -------------------------------------------------------------------------
# Function to execute segmentation pipeline
# -------------------------------------------------------------------------

def run_segmentation_pipeline():
    script = "/home/cloud/cnms-qr-sample-tracking-main/segmentation_pipeline.py"
    python_exec = "/home/cloud/microflow_server/bin/python"
    logging.info("Running segmentation pipeline...")

    result = subprocess.run(
        [python_exec, script],
        capture_output=True,
        text=True
    )

    # Send stdout to Airflow log
    logging.info(result.stdout)

    # Send stderr to Airflow log
    if result.stderr:
        logging.error(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f"Segmentation pipeline failed with exit code {result.returncode}"
        )
    logging.info("Segmentation pipeline completed successfully.")
# -------------------------------------------------------------------------
# DAG
# -------------------------------------------------------------------------

with DAG(
    dag_id="segmentation_pipeline",
    default_args=default_args,
    description="Runs AFM segmentation on standardized HDF5 files",
    schedule_interval=timedelta(minutes=7),
    catchup=False,
    max_active_runs=1,
    tags=["Segmentation", "YOLO", "AFM"],
) as dag:

    segment_h5 = PythonOperator(
        task_id="segment_h5_files",
        python_callable=run_segmentation_pipeline,
    )

    segment_h5