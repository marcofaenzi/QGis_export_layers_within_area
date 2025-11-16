"""Finestra di configurazione del plugin."""

import os
from typing import List, Optional, Tuple

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from qgis.core import QgsMapLayer, QgsProject, QgsWkbTypes


class ConfigDialog(QDialog):
    """Dialog per selezionare il layer poligonale di riferimento."""

    def __init__(self, parent=None, current_layer_id: Optional[str] = None, current_output_dir: Optional[str] = None, logging_enabled: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurazione Export Layers Within Area")

        self._layers: List[Tuple[str, str]] = []
        self._combo = QComboBox(self)
        self._combo.setEditable(False)

        self._build_layer_list(current_layer_id)

        self._output_dir_edit = QLineEdit(self)
        self._output_dir_edit.setPlaceholderText("Seleziona una cartella di destinazione")
        default_path = QgsProject.instance().homePath() or os.path.expanduser("~")
        self._output_dir_edit.setText(current_output_dir or default_path)

        browse_button = QPushButton("Sfoglia", self)
        browse_button.clicked.connect(self._choose_output_dir)

        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self._output_dir_edit)
        output_dir_layout.addWidget(browse_button)

        # Checkbox per abilitare/disabilitare i log
        self._logging_checkbox = QCheckBox("Abilita logging dettagliato", self)
        self._logging_checkbox.setChecked(logging_enabled)
        self._logging_checkbox.setToolTip("Abilita/disabilita i messaggi di log dettagliati durante l'esportazione")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Layer poligonale di selezione:"))
        layout.addWidget(self._combo)
        layout.addWidget(QLabel("Cartella di esportazione:"))
        layout.addLayout(output_dir_layout)
        layout.addWidget(self._logging_checkbox)
        layout.addWidget(buttons)

    def _build_layer_list(self, current_layer_id: Optional[str]) -> None:
        project = QgsProject.instance()
        polygon_layers: List[Tuple[str, str]] = []

        for layer in project.mapLayers().values():
            if layer.type() != QgsMapLayer.VectorLayer:
                continue
            if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
                continue
            polygon_layers.append((layer.id(), layer.name()))

        polygon_layers.sort(key=lambda item: item[1].lower())
        self._layers = polygon_layers

        self._combo.clear()
        for layer_id, layer_name in polygon_layers:
            self._combo.addItem(layer_name, layer_id)
            if current_layer_id and layer_id == current_layer_id:
                self._combo.setCurrentIndex(self._combo.count() - 1)

    def selected_layer_id(self) -> Optional[str]:
        index = self._combo.currentIndex()
        if index < 0:
            return None
        return self._combo.itemData(index)

    def output_directory(self) -> str:
        directory = self._output_dir_edit.text().strip()
        return directory if directory else ""

    def logging_enabled(self) -> bool:
        return self._logging_checkbox.isChecked()

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Seleziona cartella di destinazione", self._output_dir_edit.text()
        )
        if directory:
            self._output_dir_edit.setText(directory)

