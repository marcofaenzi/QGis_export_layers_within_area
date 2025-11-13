"""Worker thread per l'esportazione in background."""

from typing import List, Tuple, Optional
from qgis.PyQt.QtCore import QThread, pyqtSignal
from qgis.core import QgsMapLayer, QgsVectorLayer, QgsFeature, QgsMessageLog, Qgis

from .exporter import LayerExporter, ExportError


class ExportWorker(QThread):
    """Thread worker per eseguire l'esportazione in background."""

    # Segnali per comunicare con il thread principale
    progress_updated = pyqtSignal(int, str)  # progresso (0-100), messaggio
    export_finished = pyqtSignal(list, str)  # exported_data, export_directory
    export_error = pyqtSignal(str)  # messaggio di errore
    export_cancelled = pyqtSignal()  # esportazione cancellata

    def __init__(
        self,
        polygon_layer: QgsVectorLayer,
        polygon_features: List[QgsFeature],
        layers: List[QgsMapLayer],
        output_directory: str,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.polygon_layer = polygon_layer
        self.polygon_features = polygon_features
        self.layers = layers
        self.output_directory = output_directory
        self.is_cancelled = False

    def run(self) -> None:
        """Esegue l'esportazione nel thread separato."""
        try:
            # Inizializza il progresso
            self.progress_updated.emit(0, "Inizializzazione esportazione...")

            # Crea l'exporter con callback di progresso
            exporter = LayerExporter(
                self.polygon_layer,
                self.polygon_features,
                self.layers,
                self.output_directory
            )

            # Patch del metodo export per aggiungere il progresso
            original_export = exporter.export
            def export_with_progress():
                return self._export_with_progress(exporter, original_export)

            exporter.export = export_with_progress

            # Esegue l'esportazione
            exported_data = exporter.export()
            export_directory = exporter.get_export_directory()

            if not self.is_cancelled:
                self.progress_updated.emit(100, "Esportazione completata")
                self.export_finished.emit(exported_data, export_directory)
            else:
                self.export_cancelled.emit()

        except ExportError as e:
            if not self.is_cancelled:
                self.export_error.emit(str(e))
        except Exception as e:
            if not self.is_cancelled:
                self.export_error.emit(f"Errore imprevisto: {str(e)}")

    def _export_with_progress(self, exporter: LayerExporter, original_export) -> List[Tuple[str, QgsMapLayer]]:
        """Versione dell'export con monitoraggio del progresso."""
        total_layers = len(exporter._target_layers)
        completed_layers = 0

        # Sovrascrivi temporaneamente il metodo per intercettare i progressi
        original_export_layer = exporter._export_layer

        def export_layer_with_progress(layer, features):
            result = original_export_layer(layer, features)
            nonlocal completed_layers
            completed_layers += 1
            progress = int((completed_layers / total_layers) * 90)  # 90% per l'esportazione, 10% per il setup
            self.progress_updated.emit(progress, f"Esportazione layer: {layer.name()}")
            return result

        exporter._export_layer = export_layer_with_progress

        # Esegue l'esportazione originale
        self.progress_updated.emit(10, "Preparazione layer...")
        result = original_export()
        return result

    def cancel(self) -> None:
        """Cancella l'esportazione."""
        self.is_cancelled = True