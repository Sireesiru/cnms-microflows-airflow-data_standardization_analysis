import json
import os
import igor2
from .jsonWidget import JsonEditorDialog
from .watcher import convert_to_h5

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from datafed.CommandLib import API

def PerformBatchUpload(parent):
    startCode = parent.current_code

    # Get the files needed for upload
    files, _ = QFileDialog.getOpenFileNames(
        parent,
        "Select Files",
        parent.app_config.data["globus"]["endpoint_path"],  # starting directory
        "All Files (*);;Images (*.png *.jpg *.tif)"
    )

    if not files:
        return
    else:
        for file in files:
            bname = os.path.basename(file)
            fID = parent.auto_generate_code(bname, "der", startCode)
            data_path = convert_to_h5(file)
            print(file, data_path, fID)

            uCheck = auto_upload(parent, fID, data_path)
            print(uCheck)

def auto_upload(parent, code, data_path):
    src_collection = parent.app_config.data["globus"].get("src_collection", "").strip()
    local_src_loc = f"{src_collection}{data_path}"

    try:
        du_resp = parent.df_api.dataPut(code, local_src_loc)
        return "Success"
    except Exception as exc:
        print(exc)
        return "Fail"

def PerformManualUpload(parent, current_code):
    if not current_code:
        QMessageBox.warning(parent, "No Sample", "Generate or enter a sample code first.")
        return

    src_collection = parent.app_config.data["globus"].get("src_collection", "").strip()
    if not src_collection:
        QMessageBox.warning(parent, "Missing Setting", "Set Globus source collection in Settings.")
        return

    data_path = get_filepath(parent)
    if not data_path:
        return

    context = parent.app_config.data["datafed"].get("context", "").strip()
    if context:
        parent.df_api.setContext(context)

    ep = parent.app_config.data["globus"].get("endpoint_path", "").strip()
    data_path = convert_to_h5(ep, data_path)

    local_src_loc = f"{src_collection}/~/{os.path.basename(ep)}/{data_path}"

    try:
        du_resp = parent.df_api.dataPut(current_code, local_src_loc)
    except Exception as exc:
        QMessageBox.critical(parent, "Upload Error", f"Data upload failed.\n\n{exc}")
        return

    print(du_resp)
    parent.upload_status_label.setText(f"Uploaded {data_path} to {current_code}")
    parent.upload_status_label.setStyleSheet(
        """
        QLabel {
            border: 2px solid #FF9800;
            border-radius: 5px;
            padding: 20px;
            font-weight: bold;
            font-size: 14px;
        }
        """
    )

def get_filepath(parent):
    start_dir = parent.app_config.data["globus"].get("endpoint_path", "").strip()
    filepath, _ = QFileDialog.getOpenFileName(
        parent,
        "Select a file",
        start_dir,
        "All Files (*);;CSV Files (*.csv);;Text Files (*.txt);;NumPy Files (*.npy)",
    )

    if not filepath:
        return None

    return os.path.basename(filepath)