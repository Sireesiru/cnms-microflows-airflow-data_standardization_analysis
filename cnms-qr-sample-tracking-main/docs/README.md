# Documentation Index

Project documentation for `cnms-qr-sample-tracking`.

## Installation Order (Required)

Install in this sequence:

1. Package (`uv sync` or `pip install -e .`)
2. DataFed (`pip install datafed` or your site-managed DataFed setup)
3. Globus (`pip install globus-cli` + Globus Connect Personal)

Detailed setup docs:

- [DataFed Setup](./DATAFED_SETUP.md).
- [Globus Setup](./GLOBUS_ENDPOINT_SETUP.md)

### 1) Install the app package

From repo root:

```powershell
uv sync --native-tls
```

Then run:

```powershell
uv run QR.py
```

If you are not using `uv`:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
python QR.py
```

### 2) Install DataFed

Option A (Python package in same environment):

```powershell
pip install datafed
```

Option B (official setup for your site/lab):
- Follow your organization's DataFed onboarding process.

Then continue with: `DATAFED_SETUP.md`.

### 3) Install Globus

Install both:

- Globus CLI:

```powershell
pip install globus-cli
```

- Globus Connect Personal (Windows):
  https://docs.globus.org/globus-connect-personal/install/windows

Then continue with: `GLOBUS_ENDPOINT_SETUP.md`.

## Core guides

- `APP_USER_GUIDE.md`: full app usage flow and settings walkthrough.
- `DATAFED_SETUP.md`: DataFed setup, required IDs, and validation.
- `GLOBUS_ENDPOINT_SETUP.md`: Globus Connect Personal endpoint setup and app mapping.

## Suggested reading order for new users

1. `APP_USER_GUIDE.md`
2. `DATAFED_SETUP.md`
3. `GLOBUS_ENDPOINT_SETUP.md`

## Quick start checklist

1. Install package, DataFed, and Globus (in that order).
2. Configure DataFed context/repo ID. See [DataFed Setup](./DATAFED_SETUP.md).
3. Configure Globus source collection. See [Globus Setup](./GLOBUS_ENDPOINT_SETUP.md).
4. Generate a sample ID.
5. Upload a test file.
