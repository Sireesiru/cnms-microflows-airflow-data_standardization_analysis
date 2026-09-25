# CNMS QR Sample Tracking

Desktop application for generating and printing QR labels, then uploading sample data to DataFed using Globus paths.

## Overview

This project provides a simple PyQt5 interface with three tabs:

- `Sample Labeling`: Generate a new sample record in DataFed, and optionally generate a SEAID (`sea-sand`) for provenance metadata.
- `Upload Data`: Select a local file and upload it to the active sample record via DataFed.
- `Settings`: Configure printer, DataFed context/repo ID, Globus source collection, default user info, and provenance defaults.

The package uses a `src/` layout, with the main app code in `src/cnms_qr_sample_tracking/app.py`.

## Requirements

- Windows (label printing uses `pywin32` printer APIs). #TODO make this independent of Windows
- Python 3.9+ (3.10 or 3.11 recommended).
- Epson label printer and driver installed (default printer name in code: `EPSON LW-PX750`).
- DataFed account and client configuration.
- Globus endpoint available on the machine where this runs.

## Installation
Install in this sequence:
1. Package (`uv sync` or `pip install -e .`)
2. DataFed (`pip install datafed` or your site-managed DataFed setup)
3. Globus (`pip install globus-cli` + Globus Connect Personal)
See below for more details.
### Installing the package
From the repository root follow one of the following installations.

With uv:
```powershell
uv sync
.\.venv\Scripts\activate
```

With pip (editable):
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

With pip (non-editable):
```powershell
pip install .
```

## Installation Order (Required)

Install in this sequence:

1. Package (`uv sync` or `pip install -e .`)
2. DataFed (`pip install datafed` or your site-managed DataFed setup)
3. Globus (`pip install globus-cli` + Globus Connect Personal)

Detailed setup docs:

- [DataFed Setup](./DATAFED_SETUP.md).
- [Globus Setup](./GLOBUS_ENDPOINT_SETUP.md)

## Configuration

Settings are stored in:

- `~/.cnms-qr-sample-tracking/config.json`

On first run, defaults are created automatically. Update values from the `Settings` tab.

SEA provenance settings:
- `Settings > User Information > Provenance > Institution`
- `Settings > User Information > Provenance > Instrument`

During ID generation you can select:
- `Instrument/sample:` (max 5 characters)
- `SEA role:` (`00`, `E0`, `S0`, `T0`, `TE`, `TS`, `A0`, `N0`, `X0`, or `None`)

If a role other than `None` is selected, a SEAID is generated and included in the DataFed metadata as `seaid`.

Documentation index: `docs/README.md`.
- App user guide: `docs/APP_USER_GUIDE.md`
- DataFed setup: `docs/DATAFED_SETUP.md`
- Globus endpoint setup: `docs/GLOBUS_ENDPOINT_SETUP.md`

## Run

After install:

```powershell
uv run QR.py
```

Or directly:

```powershell
python QR.py
```

## Notes

- `Upload Data` currently returns the selected file name from the file picker and uploads that reference through DataFed. The HDF5 conversion helper exists in code but is not active due to the early return in `file_to_hdf5_json()`.
- Optional Globus transfer helper code is present but disabled/commented in the current UI flow.

## Development

Common commands:

```powershell
pip install -e .
python QR.py
```

## License

No license file is currently included in this repository.


