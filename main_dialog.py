"""Dialog principale del plugin."""

import os
from datetime import datetime
from typing import List, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from qgis.core import QgsMapLayer, QgsProject, QgsVectorLayer, QgsWkbTypes, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsLayerTree
from qgis.core import Qgis


class MainDialog(QDialog):
    """Dialog che permette di selezionare i layer da esportare e il poligono."""

    def __init__(self, parent: QWidget, polygon_layer: QgsVectorLayer, previously_selected_layer_ids: Optional[List[str]] = None, logging_enabled: bool = True, last_export_mode: str = "all_features") -> None:
        super().__init__(parent)
        self._polygon_layer = polygon_layer
        self._selected_feature_ids = [feature.id() for feature in polygon_layer.selectedFeatures()]
        self._layers_to_export: List[str] = []
        self._previously_selected_layer_ids = previously_selected_layer_ids or []
        self._export_mode = last_export_mode  # Usa la modalità precedente invece di default
        self._logging_enabled = logging_enabled

        self.setWindowTitle("Export Layers Within Area")
        self.resize(540, 480)

        self._feature_label = QLabel(self)
        self._feature_label.setWordWrap(True)
        self._refresh_feature_label()

        self._layer_tree = QTreeWidget(self)
        self._layer_tree.setHeaderLabel("Layer")
        self._layer_tree.setColumnCount(1)
        self._populate_layer_list(self._previously_selected_layer_ids)

        # Campo per il nome della directory
        self._directory_name_edit = QLineEdit(self)
        self._directory_name_edit.setPlaceholderText("Nome del progetto esportato")
        self._set_default_directory_name()
        
        directory_name_label = QLabel("Nome del progetto esportato:", self)
        directory_name_layout = QVBoxLayout()
        directory_name_layout.addWidget(directory_name_label)
        directory_name_layout.addWidget(self._directory_name_edit)

        selection_box = QGroupBox("Layer da esportare", self)
        selection_layout = QVBoxLayout(selection_box)
        selection_layout.addWidget(self._layer_tree)

        # Sezione modalità di esportazione
        export_mode_box = QGroupBox("Modalità di esportazione", self)
        export_mode_layout = QVBoxLayout(export_mode_box)

        self._export_all_radio = QRadioButton("Esporta tutti gli elementi", self)
        self._export_all_radio.toggled.connect(self._on_export_mode_changed)

        self._export_within_area_radio = QRadioButton("Esporta solo elementi nei poligoni selezionati", self)
        self._export_within_area_radio.toggled.connect(self._on_export_mode_changed)

        # Imposta il radiobutton corretto basato sulla modalità precedente
        if self._export_mode == "all_features":
            self._export_all_radio.setChecked(True)
        else:
            self._export_within_area_radio.setChecked(True)

        export_mode_layout.addWidget(self._export_all_radio)
        export_mode_layout.addWidget(self._export_within_area_radio)

        # Sezione informazioni poligono (visibile solo se si sceglie "within_area")
        self._polygon_info_box = QGroupBox("Poligono di ritaglio", self)
        polygon_info_layout = QVBoxLayout(self._polygon_info_box)
        polygon_info_layout.addWidget(QLabel(f"Layer configurato: {polygon_layer.name()}"))
        polygon_info_layout.addWidget(self._feature_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(export_mode_box)
        layout.addWidget(self._polygon_info_box)
        layout.addWidget(selection_box)
        layout.addLayout(directory_name_layout)
        layout.addWidget(buttons)

        # Inizializza lo stato della sezione poligoni (disabilitata per default)
        self._polygon_info_box.setEnabled(False)

    def _set_default_directory_name(self) -> None:
        """Imposta il nome predefinito della directory nel formato YYYY-MM-DD_nome_progetto."""
        project = QgsProject.instance()
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Prova a ottenere il titolo del progetto, altrimenti usa il nome del file
        project_name = project.title()
        if not project_name or project_name.strip() == "":
            # Se non c'è un titolo, usa il nome del file senza estensione
            project_file = project.fileName()
            if project_file:
                project_name = os.path.splitext(os.path.basename(project_file))[0]
            else:
                project_name = "progetto"
        
        # Sanitizza il nome del progetto per usarlo come nome directory
        safe_project_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in project_name).strip("_") or "progetto"
        
        default_name = f"{date_str}_{safe_project_name}"
        self._directory_name_edit.setText(default_name)

    def _populate_layer_list(self, previously_selected_layer_ids: List[str]) -> None:
        self._layer_tree.clear()
        root_node = QgsProject.instance().layerTreeRoot()
        self._add_children_to_tree(root_node, self._layer_tree.invisibleRootItem(), previously_selected_layer_ids)
        self._layer_tree.expandAll()

    def _add_children_to_tree(self, node: QgsLayerTreeGroup, parent_item: QTreeWidgetItem, previously_selected_layer_ids: List[str]) -> None:
        for child in node.children():
            if child.nodeType() == QgsLayerTree.NodeLayer:
                layer = child.layer()
                
                # Log dettagliato per ogni layer trovato
                if layer is not None:
                    if layer.type() == QgsMapLayer.VectorLayer:
                        geom_type = layer.geometryType()
                        if geom_type == QgsWkbTypes.NoGeometry or geom_type == QgsWkbTypes.NullGeometry:
                            geom_type_str = "Tabella (senza geometria)"
                        else:
                            geom_type_str = f"GeomType:{geom_type}"
                    else:
                        geom_type_str = "N/A"
                    self._log_message(
                        f"[DEBUG] Layer trovato: {layer.name()} | Tipo: {layer.type()} | {geom_type_str}",
                        Qgis.Info
                    )
                
                # Modificato per includere layer Raster (come XYZ Tiles) e layer senza geometria (tabelle)
                if layer is None or (layer.type() != QgsMapLayer.VectorLayer and layer.type() != QgsMapLayer.RasterLayer):
                    if layer is not None:
                        self._log_message(f"[DEBUG] Layer escluso (tipo non supportato): {layer.name()}", Qgis.Info)
                    continue
                
                if layer == self._polygon_layer: # Escludi il layer poligonale di riferimento
                    self._log_message(f"[DEBUG] Layer escluso (poligono di riferimento): {layer.name()}", Qgis.Info)
                    continue

                # Log per layer che vengono aggiunti alla lista
                self._log_message(f"[DEBUG] Layer aggiunto alla lista: {layer.name()} (ID: {layer.id()})", Qgis.Info)

                item = QTreeWidgetItem(parent_item)
                item.setText(0, layer.name())
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setData(0, Qt.ItemDataRole.UserRole, layer.id())

                if layer.id() in previously_selected_layer_ids:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    self._log_message(f"[DEBUG] _add_children_to_tree: Layer pre-selezionato: {layer.name()}", Qgis.Info)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)

            elif child.nodeType() == QgsLayerTree.NodeGroup:
                group_item = QTreeWidgetItem(parent_item)
                group_item.setText(0, child.name())
                # I gruppi non sono direttamente selezionabili, ma i loro figli sì
                # group_item.setFlags(group_item.flags() | Qt.ItemFlag.ItemIsTristate)
                self._add_children_to_tree(child, group_item, previously_selected_layer_ids)

    def _refresh_feature_label(self) -> None:
        if not self._selected_feature_ids:
            self._feature_label.setText(
                "Seleziona almeno un poligono nel layer configurato prima di avviare l'esportazione."
            )
        elif len(self._selected_feature_ids) == 1:
            self._feature_label.setText("1 poligono selezionato")
        else:
            self._feature_label.setText(f"{len(self._selected_feature_ids)} poligoni selezionati")

    def _on_export_mode_changed(self) -> None:
        """Gestisce il cambio di modalità di esportazione."""
        if self._export_within_area_radio.isChecked():
            self._export_mode = "within_area"
            self._polygon_info_box.setEnabled(True)
        else:
            self._export_mode = "all_features"
            self._polygon_info_box.setEnabled(False)

    def _on_accept(self) -> None:
        self._layers_to_export = []
        self._get_checked_layers_from_tree(self._layer_tree.invisibleRootItem())

        # Validazione basata sulla modalità selezionata
        if self._export_mode == "within_area":
            if not self._selected_feature_ids:
                QMessageBox.warning(self, "Export Layers Within Area", "Nessun poligono selezionato.")
                return
        # Per "all_features" non è necessaria la selezione di poligoni

        if not self._layers_to_export:
            QMessageBox.warning(self, "Export Layers Within Area", "Seleziona almeno un layer da esportare.")
            return

        self.accept()

    def _get_checked_layers_from_tree(self, item: QTreeWidgetItem) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            if child.checkState(0) == Qt.CheckState.Checked:
                layer_id = child.data(0, Qt.ItemDataRole.UserRole)
                if layer_id: # Assicurati che sia un ID valido di layer e non un gruppo
                    self._layers_to_export.append(layer_id)
            self._get_checked_layers_from_tree(child) # Ricorsione per i figli

    def selected_feature_ids(self) -> List[int]:
        return list(self._selected_feature_ids)

    def selected_layers(self) -> List[QgsMapLayer]: # Corretta la firma del metodo per essere più generica
        project = QgsProject.instance()
        layers: List[QgsMapLayer] = [] # Corretto il tipo della lista per essere più generica
        for layer_id in self._layers_to_export:
            layer = project.mapLayer(layer_id)
            if layer is not None: # Aggiungi controllo per None
                layers.append(layer)
        return layers

    def layers_to_export(self) -> List[str]:
        return list(self._layers_to_export)

    def selected_polygon_layer(self) -> QgsVectorLayer:
        return self._polygon_layer

    def export_directory_name(self) -> str:
        """Restituisce il nome della directory di esportazione."""
        name = self._directory_name_edit.text().strip()
        if not name:
            # Se è vuoto, usa il nome predefinito
            self._set_default_directory_name()
            name = self._directory_name_edit.text().strip()
        return name

    def export_mode(self) -> str:
        """Restituisce la modalità di esportazione selezionata."""
        return self._export_mode

    def _log_message(self, message: str, level: Qgis.MessageLevel = Qgis.Info) -> None:
        """Logga un messaggio solo se il logging è abilitato."""
        if self._logging_enabled:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(message, "ExportLayersWithinArea", level)

