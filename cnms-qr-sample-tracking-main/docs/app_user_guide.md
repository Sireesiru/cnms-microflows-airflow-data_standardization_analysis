# App User Guide

This guide explains day-to-day use of `cnms-qr-sample-tracking`.

## What the app does

The app supports three core tasks:

1. Create a sample record in DataFed and print a QR label.
2. Load an existing sample ID (manual entry or QR scan).
3. Upload a selected file reference to that sample record via DataFed + Globus path.

## Prerequisites

- Python environment installed from this repo (`uv sync` or `pip install -e .`).
- DataFed client is installed and you can authenticate as your user.
- Globus Connect Personal is installed and your local collection is configured.
- Printer is installed if you will print labels.

If your network uses enterprise certificates and `uv sync` fails with certificate errors, use:

```powershell
uv sync --native-tls
```

## Start the app

From repo root:

```powershell
uv run QR.py
```

Or:

```powershell
python QR.py
```

## First-time setup in Settings

Open `Settings` and set the following fields.

### User Information

- `Default User Name`
- `Default User Phone`
- `Default User Email`
- `Default Project #`

These values prefill the Generate ID dialog.

### Printer

- `Printer Name`: exact Windows printer name used for label printing.

### Endpoints -> DataFed

- `DataFed Context` (example from defaults: `p/cnms`)
- `DataFed Repo ID` (example format: `c/<id>`)

### Endpoints -> Globus

- `Endpoint Path`: default folder opened by file picker.
- `Source Collection`: your local Globus collection UUID.

Click `Save Settings`.

## Sample Labeling tab

### Generate id

1. Click `Generate id`.
2. Fill in title/name/phone/email/project in the dialog.
3. App creates a DataFed record and returns its ID.
4. ID is shown, and `Print QR` / `Copy ID` are enabled.

### Read QR

1. Click `Read QR`.
2. Camera window opens.
3. Show a QR code to the camera.
4. Decoded text is set as the active sample ID.

Controls:

- `Q` or `Esc`: cancel scanning.

### Enter old id

- Type an existing DataFed ID in the input field and press `Enter`.

### Print QR

- Prints a QR label for the active ID.
- Optional checkbox: `Print ID text under QR`.

## Upload Data tab

1. Ensure an active sample ID is loaded.
2. Click `Upload` and choose a file.
3. App submits `dataPut` to DataFed using Globus source location format:
   `<Source Collection>/~/<filename>`

Important current behavior:

- Upload path currently uses only the selected file name (basename), not full local path.
- Place files in your home directory if needed so `/~/filename` resolves correctly.

## Update Existing tab

- Placeholder tab currently showing selected ID status.

## Troubleshooting

- `Missing Setting` warnings:
  Required values in Settings are blank.
- `DataFed Error` when generating ID:
  Verify DataFed login/context/repo permissions.
- `Camera Error` or missing dependency when using `Read QR`:
  Ensure webcam is available and `opencv-python` is installed.
- `Print Error`:
  Confirm printer name and Windows printer availability.


