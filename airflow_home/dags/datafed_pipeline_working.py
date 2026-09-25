#!/home/cloud/microflow_server/bin/python

import sys
sys.path.append('/home/cloud/microflow_server/lib/python3.9/site-packages')

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess

default_args = {
    "owner": "Sirisha",
    "start_date": datetime(2026, 3, 1),
    "retries": 1,
}

with DAG(
    dag_id="datafed_orchestration_pipeline",
    default_args=default_args,
    schedule_interval=timedelta(minutes=5),
    catchup=False,
    description="Automatically detect and process new microscopy files",
) as dag:

    def run_production_pipeline():
        result = subprocess.run(
            [
                "/home/cloud/microflow_server/bin/python",
                "/home/cloud/cnms-qr-sample-tracking-main/production_airflow_upload_pipeline_gwy_airflow.py",
            ],
            capture_output=True,
            text=True,
        )

        print(result.stdout)

        if result.returncode != 0:
            print(result.stderr)
            raise Exception("Production pipeline failed.")

    task_run = PythonOperator(
        task_id="run_production_pipeline",
        python_callable=run_production_pipeline,
    )