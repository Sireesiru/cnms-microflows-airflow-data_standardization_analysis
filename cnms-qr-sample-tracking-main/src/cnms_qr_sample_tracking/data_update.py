import json

from .jsonWidget import JsonEditorDialog

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDialog
)
from datafed.CommandLib import API

def PerformUpdate(parent, current_code):
    code = current_code
    if not code:
        QMessageBox.warning(parent, "Missing Code", "Please enter a sample code.")
        return

    dv_resp = parent.df_api.dataView(code, context=parent.app_config.data["datafed"]["repo_id"])

    metaStart = json.loads(dv_resp[0].data[0].metadata)

    dialog = JsonEditorDialog(metaStart, parent=parent)
    if dialog.exec_() == QDialog.Accepted:
        updated = dialog.result_data
        # print(json.dumps(updated, indent=2))
        du_resp = parent.df_api.dataUpdate(code, metadata=json.dumps(updated), metadata_set=True)
        print(du_resp)

        parent.refresh_metadata_viewer()
        # parent.update_status_label.setText(f"Update called for: {code}")
        # parent.update_status_label.setStyleSheet(
        #     """
        #     QLabel {
        #         border: 2px solid #FF9800;
        #         border-radius: 5px;
        #         padding: 20px;
        #         font-weight: bold;
        #         font-size: 14px;
        #     }
        #     """
        # )
    else:
        print("Cancelled")