import json
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QInputDialog, QMessageBox, QDialog)
from PyQt5.QtCore import Qt


class JsonEditorWidget(QWidget):
    """
    A simple JSON editor widget using QTreeWidget.
    Supports nested dicts, lists, and primitive values.
    No external dependencies beyond PyQt5.
    """

    def __init__(self, parent=None, viewOnly=False):
        super().__init__(parent)
        self.view_only = viewOnly
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tree widget — Key and Value only
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Key", "Value"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 250)
        if not self.view_only:
            self.tree.itemDoubleClicked.connect(self.edit_item)
        layout.addWidget(self.tree)

        if not self.view_only:
            # Buttons
            btn_layout = QHBoxLayout()

            self.add_btn = QPushButton("Add Field")
            self.add_btn.clicked.connect(self.add_field)
            btn_layout.addWidget(self.add_btn)

            self.delete_btn = QPushButton("Delete Field")
            self.delete_btn.clicked.connect(self.delete_field)
            btn_layout.addWidget(self.delete_btn)

            layout.addLayout(btn_layout)

    def load_json(self, data: dict):
        """Load a dict into the tree."""
        self.tree.clear()
        self._populate(self.tree.invisibleRootItem(), data)
        self.tree.expandAll()

    def _populate(self, parent_item, data):
        """Recursively populate tree items from data."""
        if isinstance(data, dict):
            for key, value in data.items():
                self._add_node(parent_item, str(key), value)
        elif isinstance(data, list):
            for i, value in enumerate(data):
                self._add_node(parent_item, f"[{i}]", value)

    def _add_node(self, parent_item, key, value):
        """Add a single node to the tree."""
        item = QTreeWidgetItem()
        if not self.view_only:
            item.setFlags(item.flags() | Qt.ItemIsEditable)
        else:
            item.setFlags(item.flags())
        item.setText(0, key)

        if isinstance(value, dict):
            item.setText(1, f"{{{len(value)} items}}")
            item.setData(1, Qt.UserRole, "dict")
            parent_item.addChild(item)
            self._populate(item, value)
        elif isinstance(value, list):
            item.setText(1, f"[{len(value)} items]")
            item.setData(1, Qt.UserRole, "list")
            parent_item.addChild(item)
            self._populate(item, value)
        else:
            if value is None:
                item.setText(1, "null")
            elif isinstance(value, bool):
                item.setText(1, str(value).lower())
            else:
                item.setText(1, str(value))
            item.setData(1, Qt.UserRole, "value")
            parent_item.addChild(item)

    def to_json(self) -> dict:
        """Serialize the tree back to a dict."""
        root = self.tree.invisibleRootItem()
        return self._serialize_children(root)

    def _serialize_children(self, parent_item):
        """Recursively serialize tree items back to a dict or list."""
        child_count = parent_item.childCount()
        if child_count == 0:
            return {}

        is_list = all(
            parent_item.child(i).text(0).startswith("[")
            and parent_item.child(i).text(0).endswith("]")
            for i in range(child_count)
        )

        if is_list:
            result = []
            for i in range(child_count):
                child = parent_item.child(i)
                result.append(self._serialize_item(child))
            return result
        else:
            result = {}
            for i in range(child_count):
                child = parent_item.child(i)
                key = child.text(0)
                result[key] = self._serialize_item(child)
            return result

    def _serialize_item(self, item):
        """Serialize a single tree item to its Python value."""
        node_type = item.data(1, Qt.UserRole)

        if node_type in ("dict", "list"):
            return self._serialize_children(item)
        else:
            return self._infer_value(item.text(1))

    @staticmethod
    def _infer_value(text):
        """Auto-infer the Python type from a string value."""
        if text == "null":
            return None
        if text.lower() == "true":
            return True
        if text.lower() == "false":
            return False
        try:
            return int(text)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            pass
        return text

    def edit_item(self, item, column):
        """Handle double-click to edit value or key, or expand to add children."""
        node_type = item.data(1, Qt.UserRole)
        if column == 1 and node_type in ("dict", "list"):
            # Double-clicking a dict/list value triggers add inside it
            self.tree.setCurrentItem(item)
            self.add_field()
        elif column == 1:
            self.tree.editItem(item, column)

    def add_field(self):
        """Add a new field to the selected item or root."""
        selected = self.tree.currentItem()
        parent = selected if selected and selected.data(1, Qt.UserRole) in ("dict", "list") else self.tree.invisibleRootItem()

        key, ok = QInputDialog.getText(self, "Add Field", "Key name:")
        if not ok or not key.strip():
            return

        type_choice, ok = QInputDialog.getItem(
            self, "Field Type", "Select type:", ["value", "dict", "list"], 0, False
        )
        if not ok:
            return

        if type_choice == "dict":
            self._add_node(parent, key.strip(), {})
        elif type_choice == "list":
            self._add_node(parent, key.strip(), [])
        else:
            value, ok = QInputDialog.getText(self, "Value", "Enter value:")
            if ok:
                self._add_node(parent, key.strip(), self._infer_value(value))

        self.tree.expandAll()
        self._update_container_label(parent)

    def _update_container_label(self, item):
        """Update the display text for dict/list nodes to reflect child count."""
        if item == self.tree.invisibleRootItem():
            return
        node_type = item.data(1, Qt.UserRole)
        count = item.childCount()
        if node_type == "dict":
            item.setText(1, f"{{{count} items}}")
        elif node_type == "list":
            item.setText(1, f"[{count} items]")

    def delete_field(self):
        """Delete the selected field."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a field to delete.")
            return

        parent = selected.parent()
        if parent:
            parent.removeChild(selected)
            self._update_container_label(parent)
        else:
            index = self.tree.indexOfTopLevelItem(selected)
            self.tree.takeTopLevelItem(index)

class JsonEditorDialog(QDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Metadata")
        self.setMinimumSize(500, 400)
        self.result_data = None

        layout = QVBoxLayout(self)

        self.editor = JsonEditorWidget()
        self.editor.load_json(data)
        layout.addWidget(self.editor)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.save)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def save(self):
        self.result_data = self.editor.to_json()
        self.accept()