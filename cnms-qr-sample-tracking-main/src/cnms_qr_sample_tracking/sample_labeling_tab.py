from typing import Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QGridLayout,
    QComboBox,
    QDialogButtonBox,
    QDialog
)
from datetime import datetime
import json
import textwrap
import platform

from .jsonWidget import JsonEditorWidget

try:
    import win32ui
except ImportError:
    print(f"win32ui unavailable on {platform.system()}")
    win32ui = None
try:
    import win32con
except ImportError:
    print(f"win32con unavailable on {platform.system()}")
    win32con = None

from PIL import Image, ImageDraw, ImageFont, ImageWin
import qrcode
from .config import AppConfig
from datafed.CommandLib import API
from pySEA.sea_sand import SEAID, validate_id, ALLOWED_ROLES

SEAID_ROLE_OPTIONS = list(ALLOWED_ROLES)

from .data_update import PerformUpdate
from .data_upload import PerformManualUpload, PerformBatchUpload
# from .upload_data_tab import UploadDataTab

class SampleLabelingTab(QWidget):
    def __init__(self, app_config: AppConfig, df_api: API):
        super().__init__()
        self.app_config = app_config
        self.df_api = df_api
        self.current_df_id = None
        self.current_seaid = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        self.generate_button = QPushButton("Generate new ID")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.clicked.connect(self.generate_code)

        if win32ui is not None:
            print_text = "Print QR label"
        else:
            print_text = f"Label printing is not supported on {platform.system()}"

        self.print_button = QPushButton(print_text)
        self.print_button.setMinimumHeight(40)
        self.print_button.clicked.connect(self.print_label)
        self.print_button.setEnabled(False)

        self.copy_button = QPushButton("Copy ID")
        self.copy_button.setMinimumHeight(40)
        self.copy_button.clicked.connect(self.copy_current_code)
        self.copy_button.setEnabled(False)

        id_link_group = QGroupBox("ID link")
        id_link_layout = QVBoxLayout()

        top_controls_layout = QHBoxLayout()
        manual_entry_label = QLabel("Enter old ID:")
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Type DataFedID or SEAID then press Enter")
        self.code_input.setMinimumHeight(30)
        self.code_input.returnPressed.connect(self.load_manual_code)

        self.view_history_button = QPushButton("View History")
        self.view_history_button.clicked.connect(self.view_history)

        top_controls_layout.addWidget(self.generate_button)
        top_controls_layout.addWidget(manual_entry_label)
        top_controls_layout.addWidget(self.code_input)
        top_controls_layout.addWidget(self.view_history_button)


        row_height = 34
        row_label_style = (
            "QLabel {"
            "border: 1px solid #cccccc;"
            "border-radius: 4px;"
            "padding: 6px 10px;"
            "font-size: 13px;"
            "}"
        )

        self.datafed_id_label = QLabel()
        self.datafed_id_label.setMinimumHeight(row_height)
        self.datafed_id_label.setStyleSheet(row_label_style)
        self.copy_datafed_button = QPushButton("Copy")
        self.copy_datafed_button.setMinimumHeight(row_height)
        self.copy_datafed_button.clicked.connect(self.copy_datafed_id)
        self.copy_datafed_button.setEnabled(False)

        self.seaid_label = QLabel()
        self.seaid_label.setMinimumHeight(row_height)
        self.seaid_label.setStyleSheet(row_label_style)
        self.copy_seaid_button = QPushButton("Copy")
        self.copy_seaid_button.setMinimumHeight(row_height)
        self.copy_seaid_button.clicked.connect(self.copy_seaid_id)
        self.copy_seaid_button.setEnabled(False)

        # ID label displays
        datafed_row_layout = QHBoxLayout()
        datafed_row_layout.addWidget(self.datafed_id_label, stretch=1)
        datafed_row_layout.addWidget(self.copy_datafed_button)

        seaid_row_layout = QHBoxLayout()
        seaid_row_layout.addWidget(self.seaid_label, stretch=1)
        seaid_row_layout.addWidget(self.copy_seaid_button)

        id_link_layout.addLayout(top_controls_layout)
        id_link_layout.addLayout(datafed_row_layout)
        id_link_layout.addLayout(seaid_row_layout)
        id_link_group.setLayout(id_link_layout)

        # QR code saving and printing
        label_printing_group = QGroupBox("Label printing")
        label_printing_layout = QVBoxLayout()
        print_controls_layout = QHBoxLayout()

        self.print_button = QPushButton("Print QR")
        self.print_button.setMinimumHeight(40)
        self.print_button.clicked.connect(self.print_label)
        self.print_button.setEnabled(False)
        print_controls_layout.addWidget(self.print_button)

        self.save_button = QPushButton("Save QR")
        self.save_button.setMinimumHeight(40)
        self.save_button.clicked.connect(self.save_QR_label)
        self.save_button.setEnabled(False)
        print_controls_layout.addWidget(self.save_button)

        self.show_df_id_checkbox = QCheckBox("Show DataFedID")
        self.show_df_id_checkbox.setChecked(False)
        print_controls_layout.addWidget(self.show_df_id_checkbox)

        self.show_seaid_checkbox = QCheckBox("Show SEAID")
        self.show_seaid_checkbox.setChecked(False)
        print_controls_layout.addWidget(self.show_seaid_checkbox)

        self.show_vetical_layout = QCheckBox("Vertical layout")
        self.show_vetical_layout.setChecked(False)
        print_controls_layout.addWidget(self.show_vetical_layout)
        
        label_printing_layout.addLayout(print_controls_layout)
        label_printing_group.setLayout(label_printing_layout)

        layout.addStretch()
        layout.addWidget(id_link_group)
        layout.addWidget(label_printing_group)
        layout.addStretch()
        self._update_id_display(None, None)

        updateOrUploadLayout = QHBoxLayout()
        updateLayout = QVBoxLayout()

        update_header_label = QLabel("Metadata")
        update_header_label.setAlignment(Qt.AlignCenter)
        update_header_label.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
            }
            """
        )
        updateLayout.addWidget(update_header_label)

        self.metadata_viewer = JsonEditorWidget(self, True)
        updateLayout.addWidget(self.metadata_viewer)

        self.update_button = QPushButton("Update")
        self.update_button.setMinimumHeight(20)
        self.update_button.clicked.connect(lambda: PerformUpdate(self, self.current_df_id))
        updateLayout.addWidget(self.update_button, alignment=Qt.AlignCenter)

        # self.update_status_label = QLabel("No updates performed yet")
        # self.update_status_label.setAlignment(Qt.AlignCenter)
        # self.update_status_label.setMinimumHeight(60)
        # self.update_status_label.setStyleSheet(
        #     """
        #     QLabel {
        #         border: 2px dashed #cccccc;
        #         border-radius: 5px;
        #         padding: 20px;
        #         font-style: italic;
        #     }
        #     """
        # )
        # updateLayout.addWidget(self.update_status_label)
        # updateLayout.addStretch()
        updateOrUploadLayout.addLayout(updateLayout)

        uploadLayout = QVBoxLayout()
        upload_header_label = QLabel("Upload Data")
        upload_header_label.setAlignment(Qt.AlignCenter)
        upload_header_label.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
            }
            """
        )
        uploadLayout.addWidget(upload_header_label)

        uploadGLayout = QGridLayout()

        uploadGLayout.addWidget(QPushButton("A"), 0, 0)  # row 0, col 0

        self.upload_button = QPushButton("Upload")
        self.upload_button.setMinimumHeight(40)
        self.upload_button.clicked.connect(lambda: PerformManualUpload(self, self.current_df_id))
        self.upload_batch_button = QPushButton("Batch Upload")
        self.upload_batch_button.setMinimumHeight(40)
        self.upload_batch_button.clicked.connect(lambda: PerformBatchUpload(self))
        self.add_step_button = QPushButton("Add step")
        self.add_step_button.setMinimumHeight(40)
        self.add_step_button.clicked.connect(self.addStep)
        uploadGLayout.addWidget(self.upload_button, 0, 0)
        uploadGLayout.addWidget(self.upload_batch_button, 0, 1)
        uploadGLayout.addWidget(self.add_step_button, 1, 0)
        uploadLayout.addLayout(uploadGLayout)

        self.upload_status_label = QLabel("No data uploaded yet")
        self.upload_status_label.setAlignment(Qt.AlignCenter)
        self.upload_status_label.setMinimumHeight(60)
        self.upload_status_label.setStyleSheet(
            """
            QLabel {
                border: 2px dashed #cccccc;
                border-radius: 5px;
                padding: 20px;
                font-style: italic;
            }
            """
        )
        uploadLayout.addWidget(self.upload_status_label)
        layout.addStretch()
        updateOrUploadLayout.addLayout(uploadLayout)

        layout.addLayout(updateOrUploadLayout)

    def _datafed_context(self) -> str:
        return self.app_config.data["datafed"].get("context", "").strip()

    def _repo_id(self) -> str:
        return self.app_config.data["datafed"].get("repo_id", "").strip()

    def _update_id_display(self, datafed_id: str | None, seaid: str | None):
        self.current_df_id = datafed_id
        self.current_seaid = seaid

        self.datafed_id_label.setText(f"DataFed ID: {datafed_id if datafed_id else '--'}")
        self.seaid_label.setText(f"SEAID: {seaid if seaid else '--'}")

        self.copy_datafed_button.setEnabled(bool(datafed_id))
        self.copy_seaid_button.setEnabled(bool(seaid))
        self.print_button.setEnabled(bool(datafed_id))
        self.save_button.setEnabled(bool(datafed_id))

    def _extract_data_item_seaid(self, metadata: dict) -> str | None:
        if not isinstance(metadata, dict):
            return None

        direct = metadata.get("seaid")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        hierarchy = metadata.get("seaid_hierarchy")
        if isinstance(hierarchy, dict):
            data_item = hierarchy.get("data_item")
            if isinstance(data_item, dict):
                candidate = data_item.get("seaid")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

        return None

    def _metadata_contains_seaid(self, value, target_seaid: str) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() == "seaid" and isinstance(item, str) and item.strip() == target_seaid:
                    return True
                if self._metadata_contains_seaid(item, target_seaid):
                    return True
            return False

        if isinstance(value, list):
            for item in value:
                if self._metadata_contains_seaid(item, target_seaid):
                    return True
            return False

        return False

    def _find_data_record_by_seaid(self, target_seaid: str) -> str | None:
        repo_id = self._repo_id()
        if not repo_id:
            return None

        pending_collections = [repo_id]
        visited_collections = set()
        page_size = 100

        while pending_collections:
            coll_id = pending_collections.pop(0)
            if coll_id in visited_collections:
                continue
            visited_collections.add(coll_id)

            offset = 0
            while True:
                list_resp = self.df_api.collectionItemsList(
                    coll_id,
                    offset=offset,
                    count=page_size,
                    context=repo_id,
                )
                items = list(list_resp[0].item)
                if not items:
                    break

                for item in items:
                    item_id = item.id
                    if item_id.startswith("c/"):
                        if item_id not in visited_collections:
                            pending_collections.append(item_id)
                        continue

                    if not item_id.startswith("d/"):
                        continue

                    try:
                        view_resp = self.df_api.dataView(item_id, context=repo_id)
                        metadata_raw = view_resp[0].data[0].metadata
                        metadata = json.loads(metadata_raw) if metadata_raw else {}
                    except Exception:
                        continue

                    if self._metadata_contains_seaid(metadata, target_seaid):
                        return item_id

                if len(items) < page_size:
                    break
                offset += page_size

        return None
    
    def auto_generate_code(self, title: str, rel, code):
        meta = self.app_config.data.get("user", {})

        repo_id = self._repo_id()

        try:
            if rel is not None and code is not None:
                dc_resp = self.df_api.dataCreate(
                    title,
                    metadata=json.dumps(meta),
                    deps=[[rel, code]],
                    parent_id=repo_id
                )

                id = dc_resp[0].data[0].id
            else:
                dc_resp = self.df_api.dataCreate(
                    title,
                    metadata=json.dumps(meta),
                    parent_id=repo_id,
                )
                id = dc_resp[0].data[0].id

        except Exception as exc:
            id = None
            print(exc)

        #print(dc_resp)

        return id


    def generate_code(self, deps=None):
        user_defaults = dict(self.app_config.data.get("user", {}))
        provenance_defaults = self.app_config.data.get("provenance", {})
        user_defaults["instrument"] = provenance_defaults.get("instrument", "")
        user_defaults["seaid_role"] = provenance_defaults.get("seaid_role", "None")
        result = get_user_info(self, user_defaults)
        if result is None:
            self._update_id_display(None, None)
            return

        repo_id = self._repo_id()
        if not repo_id:
            QMessageBox.warning(self, "Missing Setting", "Set DataFed Repo ID in Settings.")
            return

        context = self._datafed_context()
        if context:
            self.df_api.setContext(context)

        data = {k: v for k, v in result.items() if k != "title"}
        provenance_cfg = self.app_config.data.get("provenance", {})
        orginization = provenance_cfg.get("orginization", "").strip()
        sub_orginization = provenance_cfg.get("sub-orginization", "").strip()
        instrument = result.get("instrument", "").strip()
        seaid_role = result.get("seaid_role", "None").strip()

        if orginization:
            data["orginization"] = orginization
        if sub_orginization:
            data["sub-orginization"] = sub_orginization

        generated_seaid = None
        if seaid_role and seaid_role != "None":
            if not orginization or not sub_orginization:
                QMessageBox.warning(
                    self,
                    "Missing Setting",
                    "Set Orginization and Sub-Orginization in Settings > Provenance.",
                )
                return
            try:
                seaid_obj = SEAID(
                    org=orginization,
                    grp=sub_orginization,
                    instr=instrument,
                    role=seaid_role,
                )
                generated_seaid = seaid_obj.seaid
            except Exception as exc:
                QMessageBox.critical(self, "SEAID Error", f"Could not generate SEAID.\n\n{exc}")
                return
            data["seaid"] = generated_seaid
            data["seaid_hierarchy"] = {
                "organization": {"seaid": seaid_obj.org_seaid, "uuid": str(seaid_obj.org_uuid)},
                "instrument": {"seaid": seaid_obj.instr_seaid, "uuid": str(seaid_obj.instr_uuid)},
                "data_item": {"seaid": seaid_obj.seaid, "uuid": str(seaid_obj.uuid)},
            }

        try:
            dc_resp = self.df_api.dataCreate(
                result["title"],
                metadata=json.dumps(data),
                parent_id=repo_id,
                deps=deps,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "DataFed Error",
                f"Could not create sample record in DataFed.\n\n{exc}",
            )
            self._update_id_display(None, None)
            return

        self.app_config.data["user"].update(
            {
                "name": result["name"],
                "phone": result["phone"],
                "email": result["email"],
                "project_number": result["project_number"],
            }
        )
        self.app_config.data.setdefault("provenance", {})
        self.app_config.data["provenance"]["instrument"] = instrument
        self.app_config.data["provenance"]["seaid_role"] = result["seaid_role"]
        self.app_config.save()

        store_code = dc_resp[0].data[0].id
        self._update_id_display(store_code, generated_seaid)

    def copy_current_code(self):
        if not self.current_df_id:
            return
        QApplication.clipboard().setText(self.current_df_id)

    def make_qr(self, size: int = 100) -> Image.Image:
        qr = qrcode.QRCode(
            version=2, # 25 squares per side for version 2
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=6, #in pixels
            border=0,
        )

        qr.add_data(f"{self.current_df_id}")
        qr.make(fit=False)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size, size), Image.Resampling.NEAREST)
        return img

    def make_text_label(
            self,
            size: int = 50,
            text: Sequence[str] | str | None = None,
            vertical: bool = False,
            scale: int = 8,  # <-- supersampling factor
    ) -> Image.Image | None:

        if isinstance(text, str):
            text_lines = [text]
        elif text is None:
            text_lines = []
        else:
            text_lines = [line for line in text if line]

        if not text_lines:
            return None

        # Scale everything up for high-res rendering
        font = ImageFont.load_default(size=11*scale)
        stroke_width = 0  # must be int, no fractional strokes
        probe = Image.new("RGB", (1, 1), color="white")
        probe_draw = ImageDraw.Draw(probe)

        line_spacing = 4 * scale
        text_top_margin = 1 * scale
        text_bottom_margin = 1 * scale

        line_height = 0
        text_block_width = 0
        for line in text_lines:
            bbox = probe_draw.textbbox((0, 0), line, font=font)
            line_height = max(line_height, bbox[3] - bbox[1])
            text_block_width = max(text_block_width, bbox[2] - bbox[0])

        text_block_height = text_top_margin + (line_height * len(text_lines))
        text_block_height += line_spacing * max(0, len(text_lines) - 1)
        text_block_height += text_bottom_margin

        label_width = size * scale
        label_height = size * scale
        if vertical:
            label_height = text_block_height
        else:
            label_width = text_block_width + 20 * scale

        # Draw at high resolution
        label = Image.new("RGB", (label_width, label_height), color="white")
        draw = ImageDraw.Draw(label)

        x0, y0 = 2 * scale, 2 * scale
        draw.rectangle(
            (x0, y0, label_width - 1, label_height - 1),
            outline="black",
            fill="white",
        )

        text_y = y0 + text_top_margin
        for line in text_lines:
            text_x = max(scale, x0)
            draw.text(
                (text_x, text_y),
                line,
                fill="black",
                font=font,
                stroke_width=stroke_width,
            )
            text_y += line_height + line_spacing

        # Downscale with high-quality resampling — this is what makes it crisp
        final_w = label_width // scale
        final_h = label_height // scale
        label = label.resize((final_w, final_h), resample=Image.BICUBIC)

        return label

    def make_qr_label(
        self,
        size: int = 50,
        text: Sequence[str] | str | None = None,
        vertical: bool = False,
    ) -> Image.Image:
        """
        Create a QR label image with an optional text panel.

        Parameters
        ----------
        size : int, optional
            QR image size in pixels.
        text : Sequence[str] | str | None, optional
            Optional text to render next to or below the QR code.
        vertical : bool, optional
            Whether to place the text panel below the QR code.

        Returns
        -------
        Image.Image
            Final composed label image.
        """
        #create the qr code
        qr_img = self.make_qr(size=size)
        print('qr_size,size',qr_img.size[0],size) #FLAG  

        txt_label = self.make_text_label(text=text, vertical=vertical)
        if txt_label is None:
            return qr_img

        label_width  = size #txt_label.size[0]
        label_height = size #txt_label.size[1]
        x0, y0 = 0, 0
        if vertical:
            label_height += txt_label.size[1]
            y0 += size + 2
        else:
            label_width += txt_label.size[0]
            x0 += size + 2




        # font = ImageFont.load_default(size=11)
        # stroke_width = 0.5
        # probe = Image.new("RGB", (1, 1), color="white")
        # probe_draw = ImageDraw.Draw(probe)


        # line_spacing = 4
        # text_top_margin = 1
        # text_bottom_margin = 1

        # # Get max line sizes then calculate the text box height
        # line_height = 0
        # text_block_width = 0
        # text_block_height = 0
        # if lines_to_print:
        #     for line in lines_to_print:
        #         bbox = probe_draw.textbbox((0, 0), line, font=font)
        #         line_height = max(line_height, bbox[3] - bbox[1])
        #         text_block_width = max(text_block_width, bbox[2] - bbox[0])
        #     text_block_height = text_top_margin + (line_height * len(lines_to_print))
        #     text_block_height += line_spacing * max(0, len(lines_to_print) - 1)
        #     text_block_height += text_bottom_margin
        # print('qr_size, line_height, text_block_height',qr_size, line_height, text_block_height)#FLAG

        # # Calcualte the label size
        # label_width = qr_size
        # label_height = qr_size
        # if vertical: label_height += text_block_height
        # else: label_width += text_block_width + 2
        # print('label_width, label_height',label_width, label_height) #FLAG

        qr_label = Image.new("RGB", (label_width, label_height), color="white") #create a new image
        qr_label.paste(qr_img) #paste the qr image into the main image
        qr_label.paste(txt_label, (x0,y0)) #paste the text label into the main image

        return qr_label


    def make_ID_qr_label(self,
                         size: int = 100,
                         vertical=False
                         ) -> Image.Image:
        print('Vertical flag:', vertical) #FLAG
        # Generate the lines to print
        lines_to_print = []
        if self.show_df_id_checkbox.isChecked() and self.current_df_id:
            lines_to_print.append(self.current_df_id)
        if self.show_seaid_checkbox.isChecked() and self.current_seaid:
            lines_to_print.append(self.current_seaid)
            # fields = self.current_seaid.split("-")
            # if vertical: i = [[0,1,2], [3,4], [5,6]]
            # else: i = [[0,1,2,3], [4,5,6]]
            # for ii in i:
            #     line = "-".join([fields[j] for j in ii if j < len(fields)])
            #     lines_to_print.append(line)
            # for i, line in enumerate(lines_to_print[1:]): lines_to_print[i+1] = "-"+line
        print('lines_to_print', lines_to_print) #FLAG
        qr_label = self.make_qr_label(size=size, text=lines_to_print, vertical=vertical)

        return qr_label

    def save_QR_label(self):
        self.make_ID_qr_label(size=100).save("./qr_label.png")


    def print_label(self):
        """
        Print the active QR label to the configured Windows printer.

        The generated label image is rotated for tape orientation, scaled to fit
        the printable area, and submitted as a one-page print job.

        Raises
        ------
        None
            Errors are reported to the user through a message dialog.
        """
        if win32ui is None or win32con is None:
            QMessageBox.warning(
                self,
                "Unsupported Platform",
                f"Label printing is not supported on {platform.system()}.",
            )
            return

        if not self.current_df_id:
            QMessageBox.warning(self, "Missing ID", "Generate or load a DataFed ID before printing.")
            return

        printer_name = self.app_config.data["printer"].get("name", "").strip()
        if not printer_name:
            QMessageBox.warning(self, "Missing Setting", "Set printer name in Settings.")
            return

        hdc = None
        doc_started = False
        try:
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)

            printer_dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)
            printer_w = hdc.GetDeviceCaps(win32con.HORZRES)
            printer_h = hdc.GetDeviceCaps(win32con.VERTRES)

            tape_height_in = 0.5
            margin_in = 2 / 32
            target_h = int((tape_height_in - margin_in * 2) * printer_dpi_y)
            target_h = max(target_h, 24)

            vertical = self.show_vetical_layout.isChecked()
            img = self.make_ID_qr_label(size=target_h, vertical=vertical)
            rotated = img.rotate(90, expand=True)

            scale = min(printer_w / rotated.width, printer_h / rotated.height)
            dest_w = max(1, int(rotated.width * scale))
            dest_h = max(1, int(rotated.height * scale))
            x = (printer_w - dest_w) // 2
            y = (printer_h - dest_h) // 2

            hdc.StartDoc("Label Print")
            doc_started = True
            hdc.StartPage()
            dib = ImageWin.Dib(rotated)
            dib.draw(hdc.GetHandleOutput(), (x, y, x + dest_w, y + dest_h))
            hdc.EndPage()
            hdc.EndDoc()
        except Exception as exc:
            if hdc is not None and doc_started:
                try:
                    hdc.AbortDoc()
                except Exception:
                    pass
            QMessageBox.critical(self, "Print Error", f"Failed to print label.\n\n{exc}")
        finally:
            if hdc is not None:
                try:
                    hdc.DeleteDC()
                except Exception:
                    pass

    def load_manual_code(self, incode=None):
        if incode is None:
            entered_code = self.code_input.text().strip()
        else:
            entered_code = incode

        print(f"Label {self.current_df_id} printed!")

    def load_manual_code(self):
        entered_code = self.code_input.text().strip()
        if entered_code:
            context_name = self._datafed_context()
            if context_name:
                self.df_api.setContext(context_name)

            repo_id = self._repo_id()
            context = repo_id if repo_id else None
            resolved_datafed_id = None
            resolved_seaid = None

            try:
                view_resp = self.df_api.dataView(entered_code, context=context)
                resolved_datafed_id = view_resp[0].data[0].id
                metadata_raw = view_resp[0].data[0].metadata
                metadata = json.loads(metadata_raw) if metadata_raw else {}
                resolved_seaid = self._extract_data_item_seaid(metadata)
            except Exception:
                if not validate_id(entered_code):
                    QMessageBox.information(self, "Error", "Could not find DataFed record for the entered ID.")
                    return

                try:
                    resolved_datafed_id = self._find_data_record_by_seaid(entered_code)
                except Exception as exc:
                    QMessageBox.information(self, "Error", str(exc))
                    return

                if not resolved_datafed_id:
                    QMessageBox.information(self, "Not Found", f"No DataFed record found for SEAID: {entered_code}")
                    return

                resolved_seaid = entered_code

                try:
                    view_resp = self.df_api.dataView(resolved_datafed_id, context=context)
                    metadata_raw = view_resp[0].data[0].metadata
                    metadata = json.loads(metadata_raw) if metadata_raw else {}
                    metadata_seaid = self._extract_data_item_seaid(metadata)
                    if metadata_seaid:
                        resolved_seaid = metadata_seaid
                except Exception:
                    pass

            self._update_id_display(resolved_datafed_id, resolved_seaid)
            self.code_input.clear()
            self.refresh_metadata_viewer()

    def refresh_metadata_viewer(self):
        dv_resp = self.df_api.dataView(self.current_df_id, context=self.app_config.data["datafed"]["repo_id"])

        meta = json.loads(dv_resp[0].data[0].metadata)

        self.metadata_viewer.load_json(meta)

    def copy_datafed_id(self):
        if self.current_df_id:
            QApplication.clipboard().setText(self.current_df_id)

    def copy_seaid_id(self):
        if self.current_seaid:
            QApplication.clipboard().setText(self.current_seaid)

    def addStep(self):
        dialog = StepDialog(["Sputter",
                             "Evaporation",
                             "Spin coat",
                             "Photolithography",
                             "Develop",
                             "EBL",
                             "RIE",
                             "Wet Etch",
                             "Liftoff",
                             "RTP",
                             "PECVD",
                             "ALD",
                             "Imaging",
                             "Simulation"], parent=self)
        if dialog.exec_() == QDialog.Accepted:
            choice = dialog.selected()

            newCode = self.auto_generate_code(choice, "der", self.current_df_id)

            self.load_manual_code(newCode)

    def view_history(self):
        print("Getting history of ID ...")

def get_user_info(parent=None, defaults=None):
    dialog = UserInfoDialog(defaults=defaults, parent=parent)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.result_data
    return None

class StepDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select step type")
        layout = QVBoxLayout(self)

        self.combo = QComboBox()
        self.combo.addItems(items)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self):
        return self.combo.currentText()

def get_font_path():
    system = platform.system()
    if system == "Windows":
        return "arial.ttf"
    elif system == "Darwin":
        return "/Library/Fonts/Arial.ttf"
    else:  # Linux
        return "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

class UserInfoDialog(QDialog):
    def __init__(self, defaults=None, parent=None):
        super().__init__(parent)
        self.defaults = defaults or {}
        self.setWindowTitle("Enter User Information")
        self.setMinimumWidth(350)
        self.result_data = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Sample")
        self.title_input.setText(self.defaults.get("title", ""))
        layout.addWidget(QLabel("Title:"))
        layout.addWidget(self.title_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("John Doe")
        self.name_input.setText(self.defaults.get("name", ""))
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self.name_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("555-123-4567")
        self.phone_input.setText(self.defaults.get("phone", ""))
        layout.addWidget(QLabel("Phone Number:"))
        layout.addWidget(self.phone_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("user@example.com")
        self.email_input.setText(self.defaults.get("email", ""))
        layout.addWidget(QLabel("Email:"))
        layout.addWidget(self.email_input)

        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("CNMS2026-R-01234")
        self.project_input.setText(self.defaults.get("project_number", ""))
        layout.addWidget(QLabel("Project Number:"))
        layout.addWidget(self.project_input)

        self.instrument_input = QLineEdit()
        self.instrument_input.setPlaceholderText("TEMA1")
        self.instrument_input.setMaxLength(5)
        self.instrument_input.setText(self.defaults.get("instrument", ""))
        layout.addWidget(QLabel("Instrument/sample:"))
        layout.addWidget(self.instrument_input)

        self.role_input = QComboBox()
        self.role_input.addItem("None")
        self.role_input.addItems(SEAID_ROLE_OPTIONS)
        default_role = self.defaults.get("seaid_role", "None")
        role_idx = self.role_input.findText(default_role)
        self.role_input.setCurrentIndex(role_idx if role_idx >= 0 else 0)
        layout.addWidget(QLabel("SEA role:"))
        layout.addWidget(self.role_input)

        button_layout = QHBoxLayout()
        submit_btn = QPushButton("Submit")
        cancel_btn = QPushButton("Cancel")
        submit_btn.setMinimumHeight(35)
        cancel_btn.setMinimumHeight(35)
        submit_btn.clicked.connect(self.submit)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(submit_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def submit(self):
        if not all(
            [
                self.title_input.text().strip(),
                self.name_input.text().strip(),
                self.phone_input.text().strip(),
                self.email_input.text().strip(),
                self.project_input.text().strip(),
                self.instrument_input.text().strip(),
            ]
        ):
            QMessageBox.warning(self, "Missing Fields", "Please fill in all fields.")
            return

        selected_role = self.role_input.currentText().strip()

        now = datetime.now()
        self.result_data = {
            "title": self.title_input.text(),
            "name": self.name_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "project_number": self.project_input.text().strip(),
            "instrument": self.instrument_input.text().strip(),
            "seaid_role": selected_role,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
        }
        self.accept()
