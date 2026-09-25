import os
import re
import sys
import traceback

import globus_sdk
import h5py
import numpy as np
import json
import globus_sdk
from datafed.CommandLib import API
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QVBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
    QDialog,
    QSizePolicy, QLineEdit, QPushButton, QInputDialog, QCheckBox, QDialogButtonBox, QHBoxLayout
)

from .config import AppConfig
from .sample_labeling_tab import SampleLabelingTab
from .settings_tab import SettingsTab

def exception_hook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)


class GlobusInterface:
    """Legacy helper retained from QR.py for manual transfer workflows."""

    def __init__(self):
        self.groups_client = None
        self.app = None

    def setup(self, native_client_id: str, token_path: str):
        from globus_sdk.globus_app import UserApp
        from globus_sdk.token_storage import JSONTokenStorage

        auth_client = globus_sdk.NativeAppAuthClient(native_client_id)
        token_storage = JSONTokenStorage(token_path)

        if not token_storage.file_exists():
            auth_client.oauth2_start_flow(
                requested_scopes=globus_sdk.GroupsClient.scopes.view_my_groups_and_memberships,
                refresh_tokens=True,
            )
            authorize_url = auth_client.oauth2_get_authorize_url()
            print(f"Please go to this URL and login:\n\n{authorize_url}\n")
            auth_code = input("Please enter the code here: ").strip()
            token_response = auth_client.oauth2_exchange_code_for_tokens(auth_code)
            token_storage.store_token_response(token_response)

        token_data = token_storage.get_token_data(globus_sdk.GroupsClient.resource_server)
        authorizer = globus_sdk.RefreshTokenAuthorizer(
            token_data.refresh_token,
            auth_client,
            access_token=token_data.access_token,
            expires_at=token_data.expires_at_seconds,
            on_refresh=token_storage.store_token_response,
        )

        self.groups_client = globus_sdk.GroupsClient(authorizer=authorizer)
        self.app = UserApp("my-simple-transfer", client_id=native_client_id)

    def submit_transfer(self, src_collection: str, dst_collection: str, src_path: str):
        if not self.app:
            raise RuntimeError("GlobusInterface is not configured. Call setup() first.")

        client = globus_sdk.TransferClient(app=self.app)
        client.add_app_data_access_scope(dst_collection)

        transfer_request = globus_sdk.TransferData(src_collection, dst_collection)
        dst_name = os.path.basename(src_path)
        dst_path = f"/~/{dst_name}"
        transfer_request.add_item(src_path, dst_path)

        task = client.submit_transfer(transfer_request)
        print(f"Submitted transfer. Task ID: {task['task_id']}.")







class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.app_config = AppConfig()
        self.df_api = API()
        self.apply_datafed_context()
        self.init_ui()
        self.check_collection_exists()

    def apply_datafed_context(self):
        context = self.app_config.data["datafed"].get("context", "").strip()
        if context:
            self.df_api.setContext(context)

    def init_ui(self):
        self.setWindowTitle("CNMS QR Sample Tracking")
        self.setGeometry(100, 100, 700, 520)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        self.sample_labeling_tab = SampleLabelingTab(self.app_config, self.df_api)
        #self.upload_data_tab = UploadDataTab(self.app_config, self.df_api, self.sample_labeling_tab)
        #self.update_sample_tab = UpdateSampleTab(self.sample_labeling_tab, self.df_api, self.app_config)
        self.settings_tab = SettingsTab(self.app_config, on_save=self.apply_datafed_context)

        tabs.addTab(self.sample_labeling_tab, "Data Labeling")
        #tabs.addTab(self.upload_data_tab, "Upload Data")
        #tabs.addTab(self.update_sample_tab, "Update Existing")
        tabs.addTab(self.settings_tab, "Settings")

        self.setup_toolbar()

        # # Menu bar
        # menu_bar = self.menuBar()
        # self.menuBar().setNativeMenuBar(False)
        #
        # # Info display in the menu bar
        # info_widget = QWidget()
        # info_layout = QHBoxLayout(info_widget)
        # info_layout.setContentsMargins(0, 0, 10, 0)
        #
        # menu_bar.setCornerWidget(info_widget)

    def setup_toolbar(self):
        toolbar = self.addToolBar("Collections")
        toolbar.setMovable(False)

        # Add a spacer to push things right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        #self.get_all_collections()

        # Defaults from config
        self.infobar_context_label = QLabel()
        self.infobar_context_label.setText(self.app_config.data["datafed"]["context"])
        self.infobar_collection_label = QLabel()
        self.infobar_collection_label.setText(self.app_config.data["datafed"]["repo_id"])

        toolbar.addWidget(self.infobar_context_label)
        toolbar.addWidget(QLabel("  |  "))
        toolbar.addWidget(self.infobar_collection_label)

        self.new_collection_pb = QPushButton("New Collection")
        self.new_collection_pb.clicked.connect(self.new_collection)
        toolbar.addWidget(self.new_collection_pb)

    def update_collection_toolbar(self):
        self.infobar_collection_label.setText(self.app_config.data["datafed"]["repo_id"])
        self.check_collection_exists()

    def new_collection(self):
        dialog = newCollectionDialog(self.app_config.data["datafed"]["repo_id"], parent=self)
        if dialog.exec_() == QDialog.Accepted:
            title, is_sub, subName = dialog.get_values()
            print(f"Title: {title}, Sub-collection: {is_sub}")

            if is_sub:
                resp = self.df_api.collectionCreate(title, parent_id=subName, context=self.app_config.data["datafed"]["context"])
            else:
                resp = self.df_api.collectionCreate(title, context=self.app_config.data["datafed"]["context"])

            self.settings_tab.repo_id.setText(resp[0].coll[0].id)
            self.settings_tab.save()
            self.update_collection_toolbar()

    def check_collection_exists(self):
        repo_id = self.app_config.data["datafed"]["repo_id"]
        if repo_id:
            try:
                repo = self.app_config.data["datafed"]["repo_id"]
                resp = self.df_api.collectionView(repo)
                text = str(resp[0].coll)

                parents = self.df_api.collectionGetParents(repo)

                text += str(parents[0].path)

                parsed = gcp_response_to_json(text)

                self.infobar_collection_label.setToolTip(json.dumps(parsed, indent=4))

            except Exception as e:
                QMessageBox.warning(self, "Collection Error", str(e))
                self.infobar_collection_label.setToolTip("Unable to get collection info")


def gcp_response_to_json(text):
    result = {}

    # Split on ][  to separate the two blocks
    blocks = text.split('][')

    if len(blocks) >= 1:
        top_block = blocks[0].lstrip('[')
        for match in re.finditer(r'(\w+):\s*"([^"]+)"', top_block):
            result[match.group(1)] = match.group(2)
        for match in re.finditer(r'(\w+):\s*(\d+)', top_block):
            result[match.group(1)] = int(match.group(2))

    # Extract items from second block
    items = []
    if len(blocks) >= 2:
        item_block = blocks[1].rstrip(']')
        for item_match in re.finditer(r'item \{([^}]+)\}', item_block, re.DOTALL):
            item = {}
            for field in re.finditer(r'(\w+):\s*"([^"]+)"', item_match.group(1)):
                item[field.group(1)] = field.group(2)
            items.append(item)

    result["parents"] = items
    return result

class newCollectionDialog(QDialog):
    def __init__(self, collection_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter Title")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Title:"))
        self.title_input = QLineEdit()
        layout.addWidget(self.title_input)

        subLayout = QHBoxLayout()
        self.sub_collection_check = QCheckBox("Sub-collection?")
        self.sub_collection_check.setChecked(True)
        subLayout.addWidget(self.sub_collection_check)
        self.sub_collection_entry = QLineEdit(collection_name)
        subLayout.addWidget(self.sub_collection_entry)
        layout.addLayout(subLayout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return self.title_input.text(), self.sub_collection_check.isChecked(), self.sub_collection_entry.text()

def hdf5_to_original(hdf5_path, parent=None):
    with h5py.File(hdf5_path, "r") as hf:
        data = hf["data"][()]
        ext = hf.attrs["original_extension"]

    save_path, _ = QFileDialog.getSaveFileName(
        parent,
        "Save restored file",
        f"restored{ext}",
        f"Original format (*{ext});;All Files (*)",
    )

    if not save_path:
        return None

    if ext == ".npy":
        np.save(save_path, data)
    elif ext in (".csv", ".txt"):
        delimiter = "," if ext == ".csv" else " "
        np.savetxt(save_path, data, delimiter=delimiter)
    else:
        with open(save_path, "wb") as file_obj:
            file_obj.write(data.tobytes())

    return save_path


def get_dark_palette():
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, Qt.GlobalColor.darkGray)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, Qt.GlobalColor.darkGray)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, Qt.GlobalColor.darkGray)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Light, QColor(53, 53, 53))
    return dark_palette


def main():
    app = QApplication(sys.argv)
    app.setStyle("Windows")
    app.setPalette(get_dark_palette())
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
