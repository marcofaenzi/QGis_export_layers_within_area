"""Plugin QGIS per esportare layer all'interno di un poligono selezionato."""

import os
from typing import List, Optional, Tuple, Union, Iterable

from qgis.PyQt.QtCore import QCoreApplication, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QProgressBar

from qgis.core import Qgis, QgsFeatureRequest, QgsMessageLog, QgsProject, QgsVectorLayer, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsLayerTree, QgsRasterLayer, QgsMapLayer, QgsMapSettings, QgsReferencedRectangle, QgsBrightnessContrastFilter

from .config_dialog import ConfigDialog
from .exporter import ExportError, LayerExporter
from .export_worker import ExportWorker
from .main_dialog import MainDialog


class ExportLayersWithinAreaPlugin:
    """Classe principale del plugin."""

    def __init__(self, iface) -> None:
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions: List[QAction] = []
        self.menu = self.tr("&Export Layers Within Area")
        self.toolbar = self.iface.addToolBar("Export Layers Within Area")
        self.toolbar.setObjectName("ExportLayersWithinAreaToolbar")

        # Attributi per il progresso
        self.progress_bar = None
        self.progress_message_item = None
        self.export_worker = None

    def tr(self, message: str) -> str:
        return QCoreApplication.translate("ExportLayersWithinArea", message)

    def initGui(self) -> None:
        export_action = QAction(QIcon(), self.tr("Esporta layer nel poligono"), self.iface.mainWindow())
        export_action.triggered.connect(self.run)
        self.actions.append(export_action)

        config_action = QAction(QIcon(), self.tr("Configura layer poligonale"), self.iface.mainWindow())
        config_action.triggered.connect(self.open_configuration)
        self.actions.append(config_action)

        for action in self.actions:
            self.iface.addPluginToMenu(self.menu, action)
            self.toolbar.addAction(action)

    def unload(self) -> None:
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.toolbar.removeAction(action)
        del self.toolbar

    def open_configuration(self) -> None:
        current_layer_id = self._configured_polygon_layer_id()
        current_output_dir = self._output_directory()
        dialog = ConfigDialog(self.iface.mainWindow(), current_layer_id, current_output_dir)
        if dialog.exec_() == dialog.Accepted:
            layer_id = dialog.selected_layer_id()
            output_dir = dialog.output_directory()
            if layer_id:
                settings = self._settings()
                settings.setValue("polygon_layer_id", layer_id)
                settings.setValue("output_directory", output_dir)
                settings.sync()
                QMessageBox.information(
                    self.iface.mainWindow(), self.tr("Configurazione"), self.tr("Layer e directory salvati correttamente."),
                )

    def run(self) -> None:
        polygon_layer = self._configured_polygon_layer()
        if polygon_layer is None:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Configura prima un layer poligonale tramite il pannello impostazioni."),
            )
            return
        
        output_directory = self._output_directory()
        if not output_directory:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Configura prima una cartella di destinazione tramite il pannello impostazioni."),
            )
            return
        
        previously_selected_layer_ids = self._selected_layers_ids_for_export()
        dialog = MainDialog(self.iface.mainWindow(), polygon_layer, previously_selected_layer_ids)
        if dialog.exec_() != dialog.Accepted:
            return

        selected_ids = dialog.selected_feature_ids()
        if not selected_ids:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Seleziona almeno un poligono nel layer configurato prima di procedere."),
            )
            return

        # Recupera tutti i poligoni selezionati
        features = []
        for feature_id in selected_ids:
            feature = self._fetch_feature_by_id(polygon_layer, feature_id)
            if feature is not None and feature.geometry() and not feature.geometry().isEmpty():
                features.append(feature)

        if not features:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Impossibile recuperare i poligoni selezionati o le geometrie non sono valide."),
            )
            return

        layers = dialog.selected_layers()
        if not layers:
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Nessun layer selezionato per l'esportazione."),
            )
            return
        
        self._save_selected_layers_for_export(dialog.layers_to_export())

        exporter = LayerExporter(polygon_layer, features, layers, output_directory)
        try:
            exported_data = exporter.export()
            export_subdirectory = exporter.get_export_directory()
        except ExportError as exc:
            QgsMessageLog.logMessage(str(exc), "ExportLayersWithinArea", level=Qgis.Critical)
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                str(exc),
            )
            return

        self.iface.messageBar().pushSuccess(
            self.tr("Export Layers Within Area"),
            self.tr("Esportazione completata: {count} file creati").format(count=len(exported_data)),
        )

        self._create_qgis_project(exported_data, export_subdirectory)

    def _create_qgis_project(self, exported_data: List[Tuple[str, QgsMapLayer]], output_directory: str) -> None:
        project = QgsProject.instance()
        
        new_project = QgsProject()
        new_project.setFileName(os.path.join(output_directory, "exported_layers_project.qgz"))

        # Imposta il CRS del nuovo progetto uguale a quello del progetto originale
        new_project.setCrs(project.crs())

        # Recupera l'estensione dal mapCanvas corrente
        original_extent = self.iface.mapCanvas().extent()

        # Imposta l'estensione della vista del nuovo progetto
        # Utilizza setDefaultViewExtent() per impostare l'estensione predefinita della vista quando il progetto viene aperto.
        new_project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(original_extent, new_project.crs()))

        # La semplice impostazione dell'extent su viewSettings() sarà presa in considerazione al salvataggio del progetto.
        # Non è necessario impostare il visibile extent sul mapCanvas qui, in quanto è il progetto che deve
        # memorizzare la sua estensione iniziale.

        # Aggiungi un gruppo "Exported Layers" al nuovo progetto
        exported_layers_group = new_project.layerTreeRoot().addGroup(self.tr("Exported Layers"))

        # Mappa gli ID dei layer originali ai nuovi layer esportati (o ai layer raster originali)
        exported_layers_map = {}
        for path, original_layer in exported_data:
            new_qgis_layer = None
            if original_layer.type() == QgsMapLayer.VectorLayer:
                # Layer vettoriale: creato da GeoPackage esportato
                new_qgis_layer = QgsVectorLayer(path, original_layer.name(), "ogr")
                if new_qgis_layer.isValid():
                    if original_layer.renderer() is not None:
                        new_qgis_layer.setRenderer(original_layer.renderer().clone())
                        new_qgis_layer.triggerRepaint()
            elif original_layer.type() == QgsMapLayer.RasterLayer:
                # Layer raster: crea una nuova istanza per il nuovo progetto
                # Per XYZ Tiles, il 'path' è la stringa di connessione URI, usiamo 'wms' come provider key
                new_qgis_layer = QgsRasterLayer(path, original_layer.name(), "wms") # Aggiunto il provider 'wms'
                if new_qgis_layer.isValid():
                    new_qgis_layer.setOpacity(original_layer.opacity()) # Imposta l'opacità
                    
                    # Clona e applica il renderer del layer originale per conservare tutte le proprietà di rendering
                    if original_layer.renderer() is not None:
                        new_qgis_layer.setRenderer(original_layer.renderer().clone())
                    
                    new_qgis_layer.triggerRepaint()
            
            if new_qgis_layer and new_qgis_layer.isValid():
                # Aggiungi il layer al nuovo progetto e mappa l'ID originale al nuovo layer
                new_project.addMapLayer(new_qgis_layer, False) # Non aggiungerlo alla radice per ora
                exported_layers_map[original_layer.id()] = new_qgis_layer
            else:
                QgsMessageLog.logMessage(
                    f"Impossibile caricare il layer {original_layer.name()} dal percorso {path}",
                    "ExportLayersWithinArea",
                    level=Qgis.Warning,
                )

        # Ricostruisci l'albero dei layer nel nuovo progetto
        original_root = project.layerTreeRoot()
        new_root = new_project.layerTreeRoot()
        # Chiamata iniziale a _rebuild_layer_tree
        self._rebuild_layer_tree(original_root, new_root, exported_layers_map)

        if not new_project.write():
            QgsMessageLog.logMessage(
                f"Impossibile salvare il progetto QGIS: {new_project.error().message()}",
                "ExportLayersWithinArea",
                level=Qgis.Critical,
            )
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr(f"Errore nel salvataggio del progetto QGIS."),
            )
            return
        
        # Apre il nuovo progetto
        self.iface.messageBar().pushInfo(
            self.tr("Export Layers Within Area"),
            self.tr("Progetto QGIS creato: {project_path}").format(project_path=new_project.fileName()),
        )

        # Chiede all'utente se vuole aprire il nuovo progetto
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            self.tr("Apri nuovo progetto?"),
            self.tr("Vuoi aprire il progetto appena creato?\n\nAttenzione: il progetto corrente verrà chiuso."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            QgsProject.instance().clear() # Chiude il progetto corrente
            QgsProject.instance().read(new_project.fileName()) # Apre il nuovo progetto

    def _rebuild_layer_tree(self, original_node: QgsLayerTreeGroup, new_parent_group: QgsLayerTreeGroup, exported_layers_map: dict) -> bool:
        # Controlla se il gruppo contiene layer da esportare
        group_contains_exported_layers = False
        for child in original_node.children():
            if child.nodeType() == QgsLayerTree.NodeLayer:
                original_layer = child.layer()
                if original_layer and original_layer.id() in exported_layers_map:
                    new_layer = exported_layers_map[original_layer.id()]
                    tree_layer_node = new_parent_group.addLayer(new_layer) # Cattura il nodo dell'albero del layer
                    # Imposta la visibilità del nodo dell'albero del layer uguale a quella del layer originale
                    tree_layer_node.setItemVisibilityChecked(child.isVisible())
                    
                    # Copia le impostazioni di scale visibility
                    if isinstance(child, QgsLayerTreeLayer):
                        tree_layer_node.setScaleBasedVisibility(child.scaleBasedVisibility())
                        if child.scaleBasedVisibility():
                            tree_layer_node.setMinimumScale(child.minimumScale())
                            tree_layer_node.setMaximumScale(child.maximumScale())
                    
                    group_contains_exported_layers = True
            elif child.nodeType() == QgsLayerTree.NodeGroup:
                # Crea un nuovo gruppo nel progetto esportato
                new_group = new_parent_group.addGroup(child.name())
                # Ricorsione per i sottogruppi e i layer
                if self._rebuild_layer_tree(child, new_group, exported_layers_map):
                    group_contains_exported_layers = True
                else:
                    # Se il sottogruppo è vuoto, rimuovilo tramite indice
                    # Questo è più robusto per versioni di QGIS che non accettano l'oggetto diretto
                    try:
                        idx = -1
                        for i, child_node in enumerate(new_parent_group.children()):
                            if child_node == new_group:
                                idx = i
                                break
                        
                        if idx != -1:
                            new_parent_group.removeChildren(idx, 1)
                        else:
                            QgsMessageLog.logMessage(
                                f"Errore: Il gruppo {new_group.name()} non è stato trovato per la rimozione.",
                                "ExportLayersWithinArea",
                                level=Qgis.Warning,
                            )
                    except ValueError:
                        QgsMessageLog.logMessage(
                            f"Errore: Il gruppo {new_group.name()} non è stato trovato per la rimozione.",
                            "ExportLayersWithinArea",
                            level=Qgis.Warning,
                        )
        return group_contains_exported_layers

    def _fetch_feature_by_id(self, layer: QgsVectorLayer, feature_id: int):
        request = QgsFeatureRequest().setFilterFid(feature_id)
        for feature in layer.getFeatures(request):
            return feature
        return None

    def _configured_polygon_layer_id(self) -> str:
        settings = self._settings()
        return settings.value("polygon_layer_id", "")

    def _configured_polygon_layer(self) -> Optional[QgsVectorLayer]:
        layer_id = self._configured_polygon_layer_id()
        if not layer_id:
            return None
        layer = QgsProject.instance().mapLayer(layer_id)
        if isinstance(layer, QgsVectorLayer):
            return layer
        return None

    def _output_directory(self) -> str:
        settings = self._settings()
        return settings.value("output_directory", os.path.join(os.path.dirname(__file__), "exported_layers"))

    def _selected_layers_ids_for_export(self) -> List[str]:
        settings = self._settings()
        # QSettings restituisce una stringa per le liste, quindi la convertiamo in lista di stringhe
        selected_ids_str = settings.value("selected_layers_for_export", "")
        return selected_ids_str.split(',') if selected_ids_str else []

    def _save_selected_layers_for_export(self, layer_ids: List[str]) -> None:
        settings = self._settings()
        settings.setValue("selected_layers_for_export", ",".join(layer_ids))
        settings.sync()

    def _settings(self) -> QSettings:
        return QSettings("ExportLayersWithinArea", "Plugin")

