#!/usr/bin/env python3

from pathlib import Path
import json
import base64
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.express as px


##################################################
# Configuration
##################################################

CONFIG_FILE = Path("/home/cloud/cnms-qr-sample-tracking-main/config.json")
PROJECT_CONFIG_FILE = Path("/home/cloud/cnms-qr-sample-tracking-main/project_config.json")

with open(CONFIG_FILE, "r") as f:
    config_data = json.load(f)
with open(PROJECT_CONFIG_FILE, "r") as f:
    project_data = json.load(f)

STAGING_ROOT = Path(config_data["pipeline"]["watch_directory"])
DESTINATION_FOLDER = (project_data["transfer"]["destination_folder"])

DATA_DIR = STAGING_ROOT / DESTINATION_FOLDER
OVERLAY_DIR = DATA_DIR / "overlays"
MEASURE_DIR = DATA_DIR / "measurements"

print(f"[+] Dash project directory: {DATA_DIR}")
print(f"[+] Overlay directory: {OVERLAY_DIR}")
print(f"[+] Measurement directory: {MEASURE_DIR}")

######################################################
# Find processed samples
######################################################
def samples():
    """
    Return samples that have BOTH:
        - measurement CSV
        - overlay image

    Only fully processed segmentation results are displayed.
    """
    out = []
    if not MEASURE_DIR.exists():
        return out
    if not OVERLAY_DIR.exists():
        return out
    measurement_files = sorted(
        MEASURE_DIR.glob("*_measurements.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    for f in measurement_files:
        sample = f.name.replace(
            "_measurements.csv",
            ""
        )
        overlay = (
            OVERLAY_DIR /
            f"{sample}_overlay.png"
        )
        if overlay.exists():
            out.append(sample)
    return out
####################################################
# Dash application
####################################################
app = Dash(__name__)
initial_samples = samples()
app.layout = html.Div([
    html.H2("BRaVE AI Analysis Dashboard"),
    # Automatically check for new segmentation outputs
    dcc.Interval(
        id="refresh-interval",
        interval=30 * 1000,       # 30 seconds
        n_intervals=0
    ),
    dcc.Dropdown(
        id="sample",
        options=[
            {
                "label": x + ".h5.nxs",
                "value": x
            }
            for x in initial_samples
        ],
        value=initial_samples[0]
        if initial_samples else None,
        clearable=False
    ),
    html.Br(),
    html.Img(
        id="overlay",
        style={"width": "600px"}
    ),
    dcc.Graph(id="hist"),
    html.Div(id="table")
])
########################################################
# Refresh sample dropdown
########################################################
@app.callback(
    Output("sample", "options"),
    Output("sample", "value"),
    Input("refresh-interval", "n_intervals"),
    Input("sample", "value")
)
def refresh_samples(n_intervals, current_sample):
    current_samples = samples()
    options = [
        {
            "label": x + ".h5.nxs",
            "value": x
        }
        for x in current_samples
    ]
    if not current_samples:
        return options, None
    # Keep currently selected sample if it still exists
    if current_sample in current_samples:
        return options, current_sample
    # Otherwise select newest processed sample
    return options, current_samples[0]
###############################################################
# Display selected sample
###############################################################

@app.callback(
    Output("overlay", "src"),
    Output("hist", "figure"),
    Output("table", "children"),
    Input("sample", "value")
)
def update(sample):
    if not sample:
        return None, {}, "No processed samples."
    overlay_file = (
        OVERLAY_DIR /
        f"{sample}_overlay.png")
    measurement_file = (
        MEASURE_DIR /
        f"{sample}_measurements.csv"
    )
    # ---------------------------------------------------------
    # Guardrail: make sure both outputs exist
    # ---------------------------------------------------------
    if not overlay_file.exists():
        return (
            None,
            {},
            f"Overlay not available for {sample}."
        )
    if not measurement_file.exists():
        return (
            None,
            {},
            f"Measurements not available for {sample}."
        )
    # ---------------------------------------------------------
    # Read measurements
    # ---------------------------------------------------------
    try:
        df = pd.read_csv(measurement_file)

    except Exception as e:
        return (
            None,
            {},
            f"Unable to read measurements for {sample}: {e}"
        )
    # ---------------------------------------------------------
    # Read overlay
    # ---------------------------------------------------------
    try:
        with open(overlay_file, "rb") as f:

            img = (
                "data:image/png;base64,"
                + base64.b64encode(
                    f.read()
                ).decode()
            )
    except Exception as e:
        return (
            None,
            {},
            f"Unable to read overlay for {sample}: {e}"
        )
    # ---------------------------------------------------------
    # Handle empty segmentation results
    # ---------------------------------------------------------
    if df.empty:
        return (
            img,
            {},
            "No segmented objects detected."
        )
    # ---------------------------------------------------------
    # Histogram
    # ---------------------------------------------------------

    if "Area_um2" in df.columns:
        col = "Area_um2"
    elif len(df.columns) > 1:
        col = df.columns[1]
    else:
        return (
            img,
            {},
            "No suitable measurement column available."
        )
    fig = px.histogram(
        df,
        x=col,
        title="Area Distribution"
    )

    # ---------------------------------------------------------
    # Measurement table
    # ---------------------------------------------------------
    table = html.Table([
        html.Thead(
            html.Tr([
                html.Th(c)
                for c in df.columns
            ])
        ),
        html.Tbody([
            html.Tr([
                html.Td(df.iloc[i][c])
                for c in df.columns
            ])
            for i in range(
                min(20, len(df))
            )
        ])

    ])
    return img, fig, table

###############################################################################
# Run server
###############################################################################

if __name__ == "__main__":
    print("[+] Starting BRaVE Dash server on port 8051")
    app.run(debug=False,host="0.0.0.0",port=8051)