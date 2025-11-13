"""Plugin QGIS per esportare layer all'interno di un poligono selezionato."""

import os
from typing import List, Optional, Tuple, Union, Iterable

from qgis.PyQt.QtCore import QCoreApplication, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QProgressBar, QPushButton

from qgis.core import Qgis, QgsFeatureRequest, QgsMessageLog, QgsProject, QgsVectorLayer, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsLayerTree, QgsRasterLayer, QgsMapLayer, QgsMapSettings, QgsReferencedRectangle, QgsBrightnessContrastFilter, QgsApplication, QgsRelation, QgsRelationManager

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
        self.cancel_button = None
        self.export_worker = None

    def tr(self, message: str) -> str:
        return QCoreApplication.translate("ExportLayersWithinArea", message)

    def initGui(self) -> None:
        # Icona esportazione personalizzata
        export_icon_path = os.path.join(self.plugin_dir, "icons", "export_map.svg")
        export_action = QAction(QIcon(export_icon_path), self.tr("Esporta layer nel poligono"), self.iface.mainWindow())
        export_action.triggered.connect(self.run)
        self.actions.append(export_action)

        # Icona configurazione personalizzata  
        settings_icon_path = os.path.join(self.plugin_dir, "icons", "setting_map.svg")
        config_action = QAction(QIcon(settings_icon_path), self.tr("Configura layer poligonale"), self.iface.mainWindow())
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

        # Ottieni la modalità di esportazione
        export_mode = dialog.export_mode()

        features = []
        if export_mode == "within_area":
            # Modalità tradizionale: esporta solo gli elementi nei poligoni selezionati
            selected_ids = dialog.selected_feature_ids()
            if not selected_ids:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("Export Layers Within Area"),
                    self.tr("Seleziona almeno un poligono nel layer configurato prima di procedere."),
                )
                return

            # Recupera tutti i poligoni selezionati
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
        # Per "all_features", features rimane una lista vuota

        layers = dialog.selected_layers()
        if not layers:
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Nessun layer selezionato per l'esportazione."),
            )
            return

        self._save_selected_layers_for_export(dialog.layers_to_export())

        # Verifica l'accessibilità dei layer connessi a database prima di iniziare l'esportazione
        db_layers_issues = self._check_database_layers_accessibility(layers)
        if db_layers_issues:
            reply = QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Problemi di connessione database"),
                self.tr("Alcuni layer potrebbero avere problemi di connessione al database:\n\n{issues}\n\n"
                       "Assicurati che le credenziali del database siano salvate nel progetto QGIS "
                       "(Layer → Proprietà → Origine → Memorizza nella configurazione del progetto).\n\n"
                       "Vuoi continuare comunque?").format(issues="\n".join(db_layers_issues)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Controlla se c'è già un'esportazione in corso
        if self.export_worker is not None and self.export_worker.isRunning():
            reply = QMessageBox.question(
                self.iface.mainWindow(),
                self.tr("Esportazione già in corso"),
                self.tr("È già in corso un'esportazione. Vuoi avviarne un'altra comunque?\n\nNota: L'esportazione precedente continuerà in background."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Mostra la barra di progresso
        mode_text = "tutti gli elementi" if export_mode == "all_features" else "elementi nei poligoni selezionati"
        self._show_progress(f"Esportazione {mode_text}...")

        # Crea il worker thread
        export_directory_name = dialog.export_directory_name()
        self.export_worker = ExportWorker(polygon_layer, features, layers, output_directory, export_directory_name)

        # Connette i segnali del worker
        self.export_worker.progress_updated.connect(self._on_export_progress)
        self.export_worker.export_finished.connect(self._on_export_finished)
        self.export_worker.export_error.connect(self._on_export_error)
        self.export_worker.export_cancelled.connect(self._on_export_cancelled)

        # Avvia l'esportazione in background
        self.export_worker.start()

    def _create_qgis_project(self, exported_data: List[Tuple[str, QgsMapLayer]], output_directory: str) -> None:
        project = QgsProject.instance()
        
        new_project = QgsProject()

        # Usa il nome del progetto corrente per il file esportato
        current_project_name = project.baseName() or "exported_project"
        qgz_filename = f"{current_project_name}_exported.qgz"
        new_project.setFileName(os.path.join(output_directory, qgz_filename))

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

        # Copia le relazioni dal progetto originale al nuovo progetto
        self._copy_project_relations(project, new_project, exported_layers_map)

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
            self.tr("Progetto QGIS creato: {project_path}").format(project_path=qgz_filename),
        )

        # Chiede all'utente se vuole aprire il nuovo progetto
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            self.tr("Apri nuovo progetto?"),
            self.tr("Vuoi aprire il progetto appena creato ({project_name})?\n\nAttenzione: il progetto corrente verrà chiuso.").format(project_name=qgz_filename),
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
                    
                    # Copia le impostazioni di scale visibility dal layer originale al nuovo layer
                    if isinstance(child, QgsLayerTreeLayer) and new_layer is not None:
                        try:
                            # Le impostazioni di scale visibility sono sul layer, non sul node dell'albero
                            original_layer = child.layer()
                            if original_layer and hasattr(original_layer, 'hasScaleBasedVisibility') and hasattr(new_layer, 'setScaleBasedVisibility'):
                                if original_layer.hasScaleBasedVisibility():
                                    new_layer.setScaleBasedVisibility(True)
                                    if hasattr(original_layer, 'minimumScale') and hasattr(original_layer, 'maximumScale'):
                                        if hasattr(new_layer, 'setMinimumScale') and hasattr(new_layer, 'setMaximumScale'):
                                            new_layer.setMinimumScale(original_layer.minimumScale())
                                            new_layer.setMaximumScale(original_layer.maximumScale())
                        except Exception as e:
                            # In caso di errore con le impostazioni di scale visibility, continua senza errori
                            QgsMessageLog.logMessage(
                                f"Impossibile copiare le impostazioni di scale visibility per il layer {new_layer.name()}: {str(e)}",
                                "ExportLayersWithinArea",
                                level=Qgis.Warning,
                            )
                    
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

    def _show_progress(self, message: str = "Esportazione in corso...") -> None:
        """Mostra la barra di progresso nella barra di stato."""
        if self.progress_message_item is None:
            self.progress_message_item = self.iface.messageBar().createMessage(message)
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_message_item.layout().addWidget(self.progress_bar)

            # Aggiungi pulsante di cancellazione
            self.cancel_button = QPushButton(self.tr("Annulla"))
            self.cancel_button.clicked.connect(self._cancel_export)
            self.progress_message_item.layout().addWidget(self.cancel_button)

            self.iface.messageBar().pushWidget(self.progress_message_item, Qgis.Info)

    def _update_progress(self, value: int, message: str) -> None:
        """Aggiorna il progresso nella barra di stato."""
        if self.progress_bar is not None:
            self.progress_bar.setValue(value)
        if self.progress_message_item is not None:
            self.progress_message_item.setText(message)

    def _hide_progress(self) -> None:
        """Nasconde la barra di progresso."""
        if self.progress_message_item is not None:
            self.iface.messageBar().clearWidgets()
            self.progress_message_item = None
            self.progress_bar = None
            self.cancel_button = None

    def _cancel_export(self) -> None:
        """Cancella l'esportazione in corso."""
        if self.export_worker is not None and self.export_worker.isRunning():
            reply = QMessageBox.question(
                self.iface.mainWindow(),
                self.tr("Annulla esportazione"),
                self.tr("Sei sicuro di voler annullare l'esportazione in corso?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.export_worker.cancel()
                # Disabilita il pulsante di cancellazione
                if self.cancel_button is not None:
                    self.cancel_button.setEnabled(False)
                    self.cancel_button.setText(self.tr("Annullamento..."))

    def _on_export_progress(self, value: int, message: str) -> None:
        """Gestisce gli aggiornamenti del progresso dal worker thread."""
        self._update_progress(value, message)

    def _on_export_finished(self, exported_data: List[Tuple[str, QgsMapLayer]], export_directory: str) -> None:
        """Gestisce il completamento dell'esportazione."""
        self._hide_progress()

        # Pulisce il worker
        if self.export_worker is not None:
            self.export_worker = None

        # Mostra messaggio di successo
        self.iface.messageBar().pushSuccess(
            self.tr("Export Layers Within Area"),
            self.tr("Esportazione completata: {count} file creati").format(count=len(exported_data)),
        )

        # Crea il progetto QGIS
        self._create_qgis_project(exported_data, export_directory)

    def _on_export_error(self, error_message: str) -> None:
        """Gestisce gli errori durante l'esportazione."""
        self._hide_progress()

        # Pulisce il worker
        if self.export_worker is not None:
            self.export_worker = None

        # Mostra messaggio di errore
        QMessageBox.critical(
            self.iface.mainWindow(),
            self.tr("Export Layers Within Area"),
            error_message,
        )

    def _on_export_cancelled(self) -> None:
        """Gestisce la cancellazione dell'esportazione."""
        self._hide_progress()

        # Pulisce il worker
        if self.export_worker is not None:
            self.export_worker = None

        # Mostra messaggio informativo
        self.iface.messageBar().pushInfo(
            self.tr("Export Layers Within Area"),
            self.tr("Esportazione cancellata"),
        )

    def _copy_project_relations(self, original_project: QgsProject, new_project: QgsProject, exported_layers_map: dict) -> None:
        """Copia le relazioni dal progetto originale al nuovo progetto esportato.

        Args:
            original_project: Il progetto originale
            new_project: Il nuovo progetto esportato
            exported_layers_map: Mappatura dagli ID originali ai nuovi layer esportati
        """
        original_relation_manager = original_project.relationManager()
        new_relation_manager = new_project.relationManager()

        # Inverti il mapping per ottenere gli ID dei nuovi layer
        reverse_layer_map = {original_layer.id(): new_layer.id()
                           for original_layer, new_layer in exported_layers_map.items()}

        # Copia ogni relazione esistente
        for relation in original_relation_manager.relations().values():
            referencing_layer_id = relation.referencingLayerId()
            referenced_layer_id = relation.referencedLayerId()

            # Verifica se entrambi i layer della relazione sono stati esportati
            if (referencing_layer_id in reverse_layer_map and
                referenced_layer_id in reverse_layer_map):

                try:
                    # Crea una nuova relazione con i riferimenti ai nuovi layer
                    new_relation = QgsRelation()
                    new_relation.setId(relation.id())
                    new_relation.setName(relation.name())
                    new_relation.setReferencingLayer(reverse_layer_map[referencing_layer_id])
                    new_relation.setReferencedLayer(reverse_layer_map[referenced_layer_id])
                    new_relation.setReferencingLayerFields(relation.referencingFields())
                    new_relation.setReferencedLayerFields(relation.referencedFields())
                    new_relation.setStrength(relation.strength())

                    # Aggiungi la relazione al nuovo progetto
                    if new_relation_manager.addRelation(new_relation):
                        QgsMessageLog.logMessage(
                            f"Relazione '{relation.name()}' copiata nel progetto esportato",
                            "ExportLayersWithinArea",
                            level=Qgis.Info,
                        )
                    else:
                        QgsMessageLog.logMessage(
                            f"Impossibile copiare la relazione '{relation.name()}'",
                            "ExportLayersWithinArea",
                            level=Qgis.Warning,
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Errore nella copia della relazione '{relation.name()}': {str(e)}",
                        "ExportLayersWithinArea",
                        level=Qgis.Warning,
                    )
            else:
                # Salta le relazioni che coinvolgono layer non esportati
                missing_layers = []
                if referencing_layer_id not in reverse_layer_map:
                    missing_layers.append("referencing")
                if referenced_layer_id not in reverse_layer_map:
                    missing_layers.append("referenced")

                QgsMessageLog.logMessage(
                    f"Relazione '{relation.name()}' saltata: layer {', '.join(missing_layers)} non esportato(i)",
                    "ExportLayersWithinArea",
                    level=Qgis.Info,
                )

    def _check_database_layers_accessibility(self, layers: List[QgsMapLayer]) -> List[str]:
        """Verifica l'accessibilità dei layer connessi a database prima dell'esportazione.

        Returns:
            Lista di stringhe con i problemi riscontrati per ciascun layer
        """
        issues = []

        for layer in layers:
            if not isinstance(layer, QgsVectorLayer):
                continue

            # Verifica se il layer è connesso a un database PostgreSQL/PostGIS
            provider = layer.dataProvider()
            if provider.name().lower() in ['postgres', 'postgis']:
                try:
                    # Prova a contare le features per verificare la connessione
                    # Questo è un'operazione leggera che verifica l'accesso al database
                    feature_count = layer.featureCount()
                    if feature_count < 0:  # -1 indica errore
                        issues.append(f"• {layer.name()}: Impossibile accedere al database (conteggio features fallito)")
                except Exception as e:
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ['password', 'authentication', 'fe_sendauth', 'connection']):
                        issues.append(f"• {layer.name()}: Problema di autenticazione al database ({str(e)[:50]}...)")
                    else:
                        issues.append(f"• {layer.name()}: Errore di connessione al database ({str(e)[:50]}...)")

        return issues

