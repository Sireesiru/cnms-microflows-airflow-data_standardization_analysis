# DataFed Setup for `cnms-qr-sample-tracking`

This guide covers the DataFed pieces required by this app.

## How this app uses DataFed

The app initializes a DataFed API client (`datafed.CommandLib.API`) at startup and uses:

- `setContext(<context>)`
- `dataCreate(title, metadata=..., parent_id=<repo_id>)`
- `dataPut(<record_id>, <globus_source_path>)`

Configured values are read from app Settings:

- `DataFed Context`
- `DataFed Repo ID`

## Prerequisites

- You have a DataFed account. [DataFed](https://datafed.ornl.gov/)
- DataFed Python client/CLI is installed and usable from this environment. [DataFed install](https://ornl.github.io/DataFed/user/client/install.html)
- You can authenticate successfully as your DataFed user.
- You have write permission to the target DataFed collection (`repo_id`).

## 1. Verify DataFed login outside the app

In the same environment where you run this app, test DataFed authentication.

Example checks (adjust to your local DataFed setup):

```powershell
python -c "from datafed.CommandLib import API; API(); print('DataFed client init OK')"
```

If your DataFed install requires an explicit login/init command, run that first, then repeat the check.

## 2. Identify context and repo ID

You need two values for app Settings:

1. `DataFed Context`: project/work context (example: `p/cnms`).
2. `DataFed Repo ID`: target collection/container ID where sample records are created (example format: `c/525611316`).

Use your DataFed CLI or existing workflow to confirm the exact IDs you should use.

## 3. Configure app Settings

In the app `Settings` tab:

1. Set `DataFed Context`.
2. Set `DataFed Repo ID`.
3. Click `Save Settings`.

The app applies context immediately after save and on app startup.

## 4. Validate from app flow

### Generate ID validation

1. Open `Sample Labeling`.
2. Click `Generate id` and submit required fields.
3. Expect a created record ID and enabled print/copy actions.

### Upload validation

1. Ensure a sample ID is active.
2. Open `Upload Data` and choose a file.
3. Expect success status after `dataPut`.

## Common errors and fixes

- `Missing Setting: Set DataFed Repo ID in Settings.`
  Add `DataFed Repo ID` in Settings.
- `DataFed Error: Could not create sample record...`
  Check login/session, context, and write permission to repo.
- Upload failure during `dataPut`
  Validate both DataFed permissions and Globus source path configuration.

## Recommended team practice

- Keep an agreed `DataFed Context` and `Repo ID` documented for your lab/team.
- Test record creation with a non-production collection before onboarding new users.
- Pair this doc with `docs/GLOBUS_ENDPOINT_SETUP.md` for complete upload setup.
