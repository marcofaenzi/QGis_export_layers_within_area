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

    def _create_qgis_project_v2(self, exported_data: List[Tuple[str, QgsMapLayer]], output_directory: str) -> None:
        """Crea una copia del progetto QGIS corrente e la modifica per contenere solo i layer esportati.

        APPROCCIO v2.0.0:
        1. Salva il progetto corrente in una nuova posizione
        2. Carica il progetto appena salvato
        3. Rimuove tutti i layer non esportati
        4. Rimuove i gruppi vuoti
        5. Salva il progetto modificato

        Args:
            exported_data: Lista di tuple (percorso_file, layer_originale)
            output_directory: Directory dove salvare il progetto
        """
        project = QgsProject.instance()

        # Crea il nome del file di destinazione
        current_project_name = project.baseName() or "exported_project"
        qgz_filename = f"{current_project_name}_exported.qgz"
        final_project_path = os.path.join(output_directory, qgz_filename)

        # PASSO 1: Salva il progetto corrente nella posizione desiderata
        project.setFileName(final_project_path)

        if not project.write():
            QgsMessageLog.logMessage(
                f"Impossibile salvare il progetto QGIS: {project.error().message()}",
                "ExportLayersWithinArea",
                level=Qgis.Critical,
            )
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Errore nel salvataggio del progetto QGIS."),
            )
            return

        # PASSO 2: Carica il progetto appena salvato per modificarlo
        new_project = QgsProject()
        if not new_project.read(final_project_path):
            QgsMessageLog.logMessage(
                "Impossibile ricaricare il progetto appena salvato",
                "ExportLayersWithinArea",
                level=Qgis.Critical,
            )
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Errore nel caricamento del progetto appena salvato."),
            )
            return

        # PASSO 3: Identifica quali layer sono stati esportati
        exported_layer_ids = {original_layer.id() for _, original_layer in exported_data}

        # PASSO 4: Rimuovi tutti i layer che non sono stati esportati
        layers_to_remove = []
        for layer_id, layer in new_project.mapLayers().items():
            if layer_id not in exported_layer_ids:
                layers_to_remove.append(layer_id)

        for layer_id in layers_to_remove:
            new_project.removeMapLayer(layer_id)
            QgsMessageLog.logMessage(
                f"Layer rimosso dal progetto esportato: {new_project.mapLayer(layer_id).name() if new_project.mapLayer(layer_id) else layer_id}",
                "ExportLayersWithinArea",
                level=Qgis.Info,
            )

        # PASSO 5: Rimuovi i gruppi vuoti dall'albero dei layer
        self._remove_empty_groups(new_project.layerTreeRoot())

        # PASSO 6: Salva il progetto modificato
        if not new_project.write():
            QgsMessageLog.logMessage(
                f"Impossibile salvare il progetto QGIS modificato: {new_project.error().message()}",
                "ExportLayersWithinArea",
                level=Qgis.Critical,
            )
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Export Layers Within Area"),
                self.tr("Errore nel salvataggio del progetto QGIS modificato."),
            )
            return

        # Log di completamento
        num_layers = len(new_project.mapLayers())
        num_relations = len(new_project.relationManager().relations())
        QgsMessageLog.logMessage(
            f"Progetto v2.0.0 completato - Layer esportati: {len(exported_layer_ids)}, Layer totali: {num_layers}, Relazioni: {num_relations}, File: {qgz_filename}",
            "ExportLayersWithinArea",
            level=Qgis.Info,
        )

        # Mostra messaggio di successo
        self.iface.messageBar().pushSuccess(
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
            # Ricarica il progetto dalla nuova posizione
            success = QgsProject.instance().read(final_project_path)
            if not success:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("Errore apertura progetto"),
                    self.tr("Impossibile aprire il progetto esportato."),
                )

    def _remove_empty_groups(self, root_group: QgsLayerTreeGroup) -> None:
        """Rimuove ricorsivamente i gruppi vuoti dall'albero dei layer.

        Args:
            root_group: Il gruppo radice da cui iniziare la pulizia
        """
        # Lista per tenere traccia dei gruppi da rimuovere
        groups_to_remove = []

        def collect_empty_groups(group):
            """Raccoglie ricorsivamente i gruppi vuoti."""
            for child in group.children():
                if child.nodeType() == QgsLayerTree.NodeGroup:
                    # Ricorsione sui sottogruppi
                    collect_empty_groups(child)

                    # Controlla se questo gruppo è vuoto
                    if not child.children():
                        groups_to_remove.append(child)
                        QgsMessageLog.logMessage(
                            f"Gruppo vuoto trovato e contrassegnato per rimozione: {child.name()}",
                            "ExportLayersWithinArea",
                            level=Qgis.Info,
                        )

        # Raccogli tutti i gruppi vuoti
        collect_empty_groups(root_group)

        # Rimuovi i gruppi vuoti (dal più profondo al più superficiale)
        # Invertiamo l'ordine per rimuovere prima i gruppi più profondi
        groups_to_remove.reverse()

        for empty_group in groups_to_remove:
            group_name = empty_group.name()  # Salva il nome prima della rimozione
            try:
                # Trova il gruppo padre
                parent = empty_group.parent()
                if parent:
                    # Rimuovi il gruppo dal padre
                    parent.removeChildNode(empty_group)
                    QgsMessageLog.logMessage(
                        f"Gruppo vuoto rimosso: {group_name}",
                        "ExportLayersWithinArea",
                        level=Qgis.Info,
                    )
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Errore nella rimozione del gruppo vuoto {group_name}: {str(e)}",
                    "ExportLayersWithinArea",
                    level=Qgis.Warning,
                )

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

        # Crea il progetto QGIS usando il nuovo approccio v2.0.0
        self._create_qgis_project_v2(exported_data, export_directory)

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

