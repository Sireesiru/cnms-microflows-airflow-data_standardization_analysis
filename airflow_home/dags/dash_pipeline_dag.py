#!/home/cloud/microflow_server/bin/python

import sys
sys.path.append('/home/cloud/microflow_server/lib/python3.9/site-packages')

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess
import logging

###############################################################################
# Default Arguments
###############################################################################

default_args = {
    "owner": "Sirisha",
    "depends_on_past": False,
    "start_date": datetime(2026, 3, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

###############################################################################
# Dash Launcher
###############################################################################

def launch_dash():

    DASH_SCRIPT = "/home/cloud/cnms-qr-sample-tracking-main/dash_app.py"
    PYTHON = "/home/cloud/microflow_server/bin/python"

    logging.info("Checking Dash server...")

    # Is Dash already running?
    result = subprocess.run(
        ["pgrep", "-f", DASH_SCRIPT],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        logging.info("Dash server already running.")
        return

    logging.info("Starting Dash server...")

    logfile = open("/home/cloud/dash.log", "a", buffering=1)

    subprocess.Popen(
        [PYTHON, DASH_SCRIPT],
        stdout=logfile,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )

    logging.info("Dash server started.")

###############################################################################
# DAG
###############################################################################

with DAG(
    dag_id="dash_pipeline",
    default_args=default_args,
    description="Launch Dash visualization server",
    schedule_interval=timedelta(minutes=8),
    catchup=False,
    max_active_runs=1,
    tags=["Dash", "Visualization"],
) as dag:

    launch_dashboard = PythonOperator(
        task_id="launch_dash_dashboard",
        python_callable=launch_dash,
    )

    launch_dashboard