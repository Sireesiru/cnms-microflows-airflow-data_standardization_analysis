# Globus Endpoint Setup for `cnms-qr-sample-tracking`

This guide explains how to create a Globus endpoint (collection) and configure this app to use it.

## What this app expects

In `Settings -> Endpoints -> Globus`, the app uses:

- `Source Collection`: your local Globus collection UUID (example: `aebc6c06-f21e-4277-a328-95a6a3bbe4e1`)
- `Endpoint Path`: default folder shown by the file picker

During upload, the app builds a Globus source path in this form:

- `<Source Collection>/~/<filename>`

That means the filename is resolved relative to your Globus home (`/~/`).

## 1. Install and configure Globus Connect Personal (Windows)

1. Install Globus Connect Personal for Windows and complete login/setup:
   https://docs.globus.org/globus-connect-personal/install/windows
2. After setup, confirm Globus Connect Personal is running (system tray icon).
3. Right-click the tray icon, open `Options...`, then in `Access` ensure the folders you need are allowed.

Note: By default, `/~/` maps to your Windows home directory (`C:\Users\<you>`).

## 2. Get your local collection UUID

Run:

```powershell
globus endpoint local-id
```

Expected output is a UUID. Put that UUID into `Source Collection` in app Settings.

If you see `No Globus Connect Personal installation found`:

1. Ensure Globus Connect Personal is actually installed for the current Windows user.
2. Launch Globus Connect Personal once and finish the login/collection setup flow.
3. Run `globus endpoint local-id` again.

## 3. Configure this app

Open the app `Settings` tab and set:

1. `Source Collection` to the UUID from `globus endpoint local-id`.
2. `Endpoint Path` to a convenient local folder you browse from.
3. Click `Save Settings`.

The app also tries to auto-detect a local Globus Connect Personal endpoint at startup and may prompt to update `Source Collection`.

## 4. Validate endpoint access (recommended)

List your endpoint home directory:

```powershell
globus ls "$(globus endpoint local-id):/~/"
```

If this works, your endpoint is available.

## 5. Upload workflow notes for this app

Current upload code sends only the selected file's basename, then uses `/~/<filename>`.

Practical guidance:

1. Place files to upload directly in your home directory (`C:\Users\<you>`) so `/~/<filename>` resolves correctly.
2. Avoid duplicate filenames in home when uploading repeatedly.

## Troubleshooting

- `No Globus Personal endpoint found` in app settings:
  Globus Connect Personal is not installed/running for this user, or setup was not completed.
- Upload fails with path/file not found:
  The file is not available at `/~/<filename>` on your local collection.
- Permission/access issues:
  Add needed folders in Globus Connect Personal `Options -> Access`.

## References

- Globus Connect Personal (Windows install/config): https://docs.globus.org/globus-connect-personal/install/windows
- Globus CLI `endpoint local-id`: https://docs.globus.org/cli/reference/endpoint_local-id/
