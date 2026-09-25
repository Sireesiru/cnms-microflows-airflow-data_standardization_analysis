from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from .config import AppConfig
import globus_sdk

class SettingsTab(QWidget):
    def __init__(self, app_config: AppConfig, on_save=None):
        super().__init__()
        self.app_config = app_config
        self.on_save = on_save
        self.init_ui()
        self.populate()
        self.check_globus_endpoint_ID()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.printer_name = QLineEdit()
        self.datafed_context = QLineEdit()
        self.repo_id = QLineEdit()
        self.endpoint_path = QLineEdit()
        self.src_collection = QLineEdit()

        self.user_name = QLineEdit()
        self.user_phone = QLineEdit()
        self.user_email = QLineEdit()
        self.user_project = QLineEdit()
        self.user_orginization = QLineEdit()
        self.user_sub_orginization = QLineEdit()
        self.user_instrument = QLineEdit()
        self.user_instrument.setMaxLength(5)

        user_group = QGroupBox("User Information")
        user_form = QFormLayout()
        user_form.addRow("Default User Name", self.user_name)
        user_form.addRow("Default User Phone", self.user_phone)
        user_form.addRow("Default User Email", self.user_email)
        user_form.addRow("Default Project #", self.user_project)
        user_group.setLayout(user_form)

        provenance_group = QGroupBox("Provenance")
        provenance_form = QFormLayout()
        provenance_form.addRow("Orginization", self.user_orginization)
        provenance_form.addRow("Sub-Orginization", self.user_sub_orginization)
        provenance_form.addRow("Instrument", self.user_instrument)
        provenance_group.setLayout(provenance_form)

        printer_group = QGroupBox("Printer")
        printer_form = QFormLayout()
        printer_form.addRow("Printer Name", self.printer_name)
        printer_group.setLayout(printer_form)

        endpoint_group = QGroupBox("Endpoints")
        endpoint_layout = QVBoxLayout()

        datafed_group = QGroupBox("DataFed")
        datafed_form = QFormLayout()
        datafed_form.addRow("DataFed Context", self.datafed_context)
        datafed_form.addRow("DataFed Repo ID", self.repo_id)
        datafed_group.setLayout(datafed_form)
        # endpoint_group.setLayout(datafed_group)

        globus_group = QGroupBox("Globus")
        globus_form = QFormLayout()
        globus_form.addRow("Endpoint Path", self.endpoint_path)
        globus_form.addRow("Source Collection", self.src_collection)
        globus_group.setLayout(globus_form)
        # endpoint_group.setLayout(globus_group)

        endpoint_layout.addWidget(datafed_group)
        endpoint_layout.addWidget(globus_group)
        endpoint_group.setLayout(endpoint_layout)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignCenter)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save)

        layout.addWidget(user_group)
        layout.addWidget(provenance_group)
        layout.addWidget(printer_group)
        # layout.addWidget(datafed_group)
        # layout.addWidget(globus_group)
        layout.addWidget(endpoint_group)
        layout.addWidget(save_btn)
        layout.addWidget(self.status)
        layout.addStretch()

    def populate(self):
        cfg = self.app_config.data
        self.printer_name.setText(cfg["printer"].get("name", ""))
        self.datafed_context.setText(cfg["datafed"].get("context", ""))
        self.repo_id.setText(cfg["datafed"].get("repo_id", ""))
        self.endpoint_path.setText(cfg["globus"].get("endpoint_path", ""))
        self.src_collection.setText(cfg["globus"].get("src_collection", ""))
        self.user_name.setText(cfg["user"].get("name", ""))
        self.user_phone.setText(cfg["user"].get("phone", ""))
        self.user_email.setText(cfg["user"].get("email", ""))
        self.user_project.setText(cfg["user"].get("project_number", ""))
        provenance_cfg = cfg.get("provenance", {})
        self.user_orginization.setText(provenance_cfg.get("orginization", ""))
        self.user_sub_orginization.setText(provenance_cfg.get("sub-orginization", ""))
        self.user_instrument.setText(provenance_cfg.get("instrument", ""))

    def save(self):
        self.app_config.data["printer"]["name"] = self.printer_name.text().strip()
        self.app_config.data["datafed"]["context"] = self.datafed_context.text().strip()
        self.app_config.data["datafed"]["repo_id"] = self.repo_id.text().strip()
        self.app_config.data["globus"]["endpoint_path"] = self.endpoint_path.text().strip()
        self.app_config.data["globus"]["src_collection"] = self.src_collection.text().strip()

        self.app_config.data["user"]["name"] = self.user_name.text().strip()
        self.app_config.data["user"]["phone"] = self.user_phone.text().strip()
        self.app_config.data["user"]["email"] = self.user_email.text().strip()
        self.app_config.data["user"]["project_number"] = self.user_project.text().strip()
        self.app_config.data.setdefault("provenance", {})
        self.app_config.data["provenance"]["orginization"] = self.user_orginization.text().strip()
        self.app_config.data["provenance"]["sub-orginization"] = self.user_sub_orginization.text().strip()
        self.app_config.data["provenance"]["instrument"] = self.user_instrument.text().strip()

        self.app_config.save()
        self.status.setText(f"Saved to {self.app_config.config_path}")
        if callable(self.on_save):
            self.on_save()

    def check_globus_endpoint_ID(self):
        endpoint_ID = self.app_config.data["globus"]["src_collection"]

        ###### Detects local computer globus endpoint
        SRC_COLLECTION = globus_sdk.LocalGlobusConnectPersonal().endpoint_id

        if SRC_COLLECTION is None or SRC_COLLECTION == "":
            QMessageBox.warning(self, "Error", "No Globus Personal endpoint found")
            return

        if endpoint_ID != SRC_COLLECTION:
            msg = QMessageBox()
            msg.setWindowTitle("Update Globus Endpoint?")
            msg.setText("Globus endpoint in config does not match locally detected endpoint. Use detected endpoint?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

            if msg.exec_() == QMessageBox.Yes:
                self.src_collection.setText(SRC_COLLECTION)
                self.save()

