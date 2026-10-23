"""JSON Schemas management page for Peke GUI."""

import importlib.util
import inspect
from pathlib import Path

from pydantic import BaseModel
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from peke.schemas import SCHEMA_REGISTRY


class SchemasPage(QWidget):
    """JSON Schemas page supporting schema preview and safe .py Pydantic model loading."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = QSettings("Peke", "Workbench")
        self.user_schemas: dict[str, type[BaseModel]] = {}
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("JSON Schemas Management")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2D5A4C;")
        layout.addWidget(title)

        splitter = QSplitter()
        layout.addWidget(splitter)

        # Left list panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Registered Schemas:"))
        self.schema_list = QListWidget()
        left_layout.addWidget(self.schema_list)

        self.load_file_btn = QPushButton("Load schema from file (.py)")
        self.load_file_btn.clicked.connect(self.load_schema_from_file)
        left_layout.addWidget(self.load_file_btn)

        splitter.addWidget(left_panel)

        # Right preview panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_title = QLabel("Schema JSON Schema Preview:")
        self.preview_title.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(self.preview_title)

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setStyleSheet("font-family: monospace; background-color: #1E1E1E;")
        right_layout.addWidget(self.preview_edit)

        self.activate_btn = QPushButton("Set as Active Schema")
        self.activate_btn.clicked.connect(self.set_active_schema)
        right_layout.addWidget(self.activate_btn)

        splitter.addWidget(right_panel)
        splitter.setSizes([200, 500])

        self.schema_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.populate_schemas()

    def populate_schemas(self) -> None:
        self.schema_list.clear()
        for name in SCHEMA_REGISTRY:
            item = QListWidgetItem(f"⭐ {name} (Built-in)")
            item.setData(100, name)
            self.schema_list.addItem(item)

        for name in self.user_schemas:
            item = QListWidgetItem(f"📄 {name} (User)")
            item.setData(100, name)
            self.schema_list.addItem(item)

        active_schema = self.settings.value("active_schema", "Article")
        for i in range(self.schema_list.count()):
            item = self.schema_list.item(i)
            if item.data(100) == active_schema:
                self.schema_list.setCurrentItem(item)
                break

    def on_selection_changed(self) -> None:
        selected = self.schema_list.selectedItems()
        if not selected:
            self.preview_edit.clear()
            return

        name = selected[0].data(100)
        model_cls = SCHEMA_REGISTRY.get(name) or self.user_schemas.get(name)
        if model_cls:
            import json
            schema_dict = model_cls.model_json_schema()
            self.preview_edit.setPlainText(json.dumps(schema_dict, indent=2))

    def load_schema_from_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Schema Python File", "", "Python Files (*.py);;All Files (*)"
        )
        if not file_path:
            return

        p = Path(file_path)
        try:
            spec = importlib.util.spec_from_file_location(p.stem, p)
            if spec is None or spec.loader is None:
                raise ValueError("Could not load spec for python file.")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            loaded_count = 0
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseModel) and obj is not BaseModel:
                    self.user_schemas[name] = obj
                    SCHEMA_REGISTRY[name] = obj
                    loaded_count += 1

            if loaded_count == 0:
                QMessageBox.warning(self, "No Models Found", "No Pydantic BaseModel subclasses found in file.")
            else:
                QMessageBox.information(
                    self, "Schema Loaded", f"Successfully loaded {loaded_count} model(s) from '{p.name}'."
                )
                self.populate_schemas()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Schema Load Error",
                f"Failed to safely import schema file:\n{e}\n\nEnsure the file contains valid Pydantic models.",
            )

    def set_active_schema(self) -> None:
        selected = self.schema_list.selectedItems()
        if selected:
            name = selected[0].data(100)
            self.settings.setValue("active_schema", name)
            QMessageBox.information(self, "Active Schema Set", f"'{name}' set as active extraction schema.")
