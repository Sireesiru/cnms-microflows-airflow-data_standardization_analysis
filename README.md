# cnms-MicroFlows-airflow-data_standardization_analysis.
#Orchestration, pipeline scripts, and environment setups for standardizing and uploading CNMS microflows data (GWY, MRC, CZI) to DataFed.
---
## Overview
This repository provides an **Airflow-orchestrated workflow for automated microscopy data processing and analysis at CNMS**. It connects instrument-generated data with Globus-accessible staging,HDF5 standardization of multimodal datasets,data and metadata upload and management, automated downstream AI/ML image analysis, quantitative feature extraction, and interactive visualization apps. The workflow is designed for continuous operation on the CNMS MicroFlows virtual machine, including integration with network-restricted instrument environments.

**Airflow Persistent Background Execution:** Apache Airflow is deployed as a persistent background service using systemd, on CNMS cloud hosted virtual machine-MicroFlows. This configures Airflow scheduler and webserver to start automatically and remain active independent of user login or terminal sessions. This enables continuous monitoring and orchestration of the data pipeline without requiring manual restart or an active SSH/PuTTY connection.

## Architecture & Data Flow Overview

Airflow continuously monitors and orchestrates an end-to-end data processing and analysis pipeline across three sequential DAGs:

```text

┌─────────────────────────┐
│  DAG 0: Staging Sync    │ ──► Monitors & syncs raw datasets from share drive (/home/cloud/BraVE/AFM/second_run) and 
└───────────┬─────────────┘     Stages files to local staging folder (/Globus-Personal-Docker/data/AFM/second_run)
            │
            ▼
      Every 5 minutes
            │
            ▼
      ┌───────────┐     Detects raw files (.gwy, .czi, .spm, .nid, .ibw) in Globus data/ hub
      │   DAG 1   │ ──► Extracts metadata & converts formats to NeXus HDF5 (.h5.nxs)
      └─────┬─────┘     Generates QR code images & registers entries with metadata to DataFed
            │           Streams files via Globus Personal Docker to designated DataFed Collections
            ▼
            7th minute   
      ┌───────────┐
      │   DAG 2   │ ──► Runs automated AI segmentation (YOLO / U-Net) on converted datasets
      └─────┬─────┘
            ▼
            8th minute
      ┌───────────┐     Calculates quantitative metrics (area, perimeter, thickness, eccentricity, orientation)
      │   DAG 3   │ ──► Generates summary reports & updates interactive Dash visualization workflows
      └───────────┘
```
---

## Repository Structure

```text

cnms-microflows-airflow-data_standardization_analysis/
├── airflow_home/                  # Complete Airflow runtime configuration, webserver setups, & DAGs
│   ├── dags/                      # Active pipeline DAG definitions (DAG 1, DAG 2, DAG 3)
│   ├── airflow.cfg                # Core Airflow configuration
│   └── webserver_config.py        # Webserver access configuration
├── cnms-qr-sample-tracking-main/  # Ingestion pipelines, config.json, project_config.json, src, & utils
├── Globus-Personal-Docker/        # Containerized Globus Personal endpoint setup
│   ├── data/                      # Local transfer hub (raw inputs, QR images, .h5.nxs - ignored by Git)
│   ├── dockerfile                 # Globus container build specification
│   ├── entrypoint.sh              # Container startup & endpoint initialization script
│   └── globus-connect-personal.sh # Globus engine runner script
├── microflow_server/              # Python virtual environment
├── requirements.txt               # Virtual environment dependencies
└── README.md                      # Comprehensive project documentationcnms-microflows-airflow-data_standardization_analysis/
```
---

## Setup & Deployment Guide for New Environments (Outside the MicroFlows virtual machine of  CNMS cloud)

To deploy this system on a new machine or server, execute the following setup sequence:


## 1. Set Up the Globus-Accessible Staging Area
Our pipeline uses a local staging directory that is exposed through a Globus endpoint.Raw microscope files are copied into this location by the Airflow staging DAG. For the current deployment, the staging area is:
`/home/cloud/Globus-Personal-Docker/data/`

For a new deployment, install or copy the Globus Personal Docker configuration and create the staging directory:

```bash
cp -r /home/cloud/Globus-Personal-Docker .
rm -rf Globus-Personal-Docker/.git
mkdir -p Globus-Personal-Docker/data
```

### 2. Configure Virtual Environment and Activate Activate Virtual Environment
```bash
source microflow_server/bin/activate
pip install -r requirements.txt
```

#### 3. Spin Up Globus Personal Docker Container to Setup Globus Endpoint 
```bash
cd Globus-Personal-Docker/
./entrypoint.sh
```
Follow the on-screen browser authorization prompts to log into Globus and register a new endpoint ID for the current host machine.

### 4. Authenticate DataFed CLI
```bash
# Log into DataFed
datafed auth login
```
### 5. Bind the new machine's Globus Endpoint UUID to DataFed
datafed config set globus-endpoint <YOUR_NEW_GLOBUS_ENDPOINT_UUID>

### 6. Initialize & Start Airflow Services
Set the 'AIRFLOW_HOME' environment variable to point directly to the repository configuration:

```bash
export AIRFLOW_HOME=$(pwd)/airflow_home
```
### 7. Configure Persistent Airflow Services (if not already setup for persistent background execution)
For unattended operation on a new VM/server, configure the Airflow scheduler and webserver as persistent background services (e.g., using systemd).
Verify the services using:

```bash
systemctl --user status airflow-scheduler
systemctl --user status airflow-webserver
```

Once running, Airflow will automatically trigger DAG 1, convert files to NeXus HDF5, push them to DataFed, run AI segmentation (DAG 2), and output quantitative analysis to the Dash dashboard (DAG 3).

