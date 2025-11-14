"""Logica di esportazione dei layer."""

import os
import time
from typing import Iterable, List, Union, Tuple, Callable

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
    Qgis,
    QgsMessageLog,
)


class ExportError(RuntimeError):
    """Errore generico durante l'esportazione."""


def _execute_with_retry(operation: Callable, max_retries: int = 3, delay: float = 1.0) -> any:
    """Esegue un'operazione con retry automatico per gestire timeout di connessione.

    Args:
        operation: Funzione da eseguire
        max_retries: Numero massimo di tentativi
        delay: Ritardo tra tentativi in secondi

    Returns:
        Risultato dell'operazione

    Raises:
        ExportError: Se tutti i tentativi falliscono
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # Controlla se è un errore di connessione che merita un retry
            if any(keyword in error_str for keyword in ['password', 'connection', 'timeout', 'fe_sendauth']):
                if attempt < max_retries - 1:
                    QgsMessageLog.logMessage(
                        f"Tentativo {attempt + 1} fallito, riprovo tra {delay} secondi: {str(e)}",
                        "ExportLayersWithinArea",
                        level=Qgis.Warning,
                    )
                    time.sleep(delay)
                    continue
                else:
                    raise ExportError(f"Connessione al database fallita dopo {max_retries} tentativi: {str(e)}")
            else:
                # Errore non legato alla connessione, non riprovare
                raise ExportError(str(e))

    # Questo non dovrebbe mai essere raggiunto, ma per sicurezza
    raise ExportError(f"Errore imprevisto: {str(last_error)}")


class LayerExporter:
    """Gestisce l'esportazione dei layer selezionati all'interno di uno o più poligoni."""

    def __init__(
        self,
        polygon_layer: QgsVectorLayer,
        polygon_features: Union[QgsFeature, List[QgsFeature]],
        target_layers: Iterable[QgsMapLayer], # Changed from QgsVectorLayer to QgsMapLayer
        output_directory: str,
        export_directory_name: str = "",
        cancellation_check=None,
    ) -> None:
        self._polygon_layer = polygon_layer

        # Normalizza: accetta sia una singola feature che una lista
        if isinstance(polygon_features, QgsFeature):
            self._polygon_features = [polygon_features]
        else:
            self._polygon_features = list(polygon_features)

        self._target_layers = list(target_layers)
        self._output_directory = output_directory
        self._export_directory_name = export_directory_name
        self._cancellation_check = cancellation_check  # Funzione per controllare se l'operazione è stata cancellata

        if not os.path.isdir(self._output_directory):
            raise ExportError("La cartella di destinazione non esiste.")

        # Se non ci sono poligoni selezionati, esportiamo tutti gli elementi (modalità "all_features")
        if self._polygon_features:
            # Verifica che tutte le feature abbiano geometrie valide
            for feature in self._polygon_features:
                if not feature or not feature.geometry() or feature.geometry().isEmpty():
                    raise ExportError("Uno o più poligoni selezionati non contengono geometrie valide.")

        # Crea una sottodirectory per l'esportazione
        from datetime import datetime
        if self._export_directory_name and self._export_directory_name.strip():
            # Usa il nome personalizzato fornito dall'utente
            export_dir_name = self._export_directory_name.strip()
        else:
            # Fallback al timestamp se non è specificato un nome
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir_name = f"export_{timestamp}"

        self._export_subdirectory = os.path.join(self._output_directory, export_dir_name)
        os.makedirs(self._export_subdirectory, exist_ok=True)

    def export(self) -> List[Tuple[str, QgsMapLayer]]:
        exported_data: List[Tuple[str, QgsMapLayer]] = []
        transform_context = QgsProject.instance().transformContext()

        # Determina se dobbiamo applicare ritagli geometrici
        use_clipping = len(self._polygon_features) > 0
        union_geom = None

        if use_clipping:
            # Unisce tutte le geometrie dei poligoni selezionati in un'unica geometria
            union_geom = self._union_polygon_geometries()

        for layer in self._target_layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                if use_clipping:
                    # Logica di esportazione per layer vettoriali (con ritaglio)
                    geom_for_layer = QgsGeometry(union_geom)

                    if not geom_for_layer.isEmpty() and self._polygon_layer.crs() != layer.crs():
                        transform = QgsCoordinateTransform(
                            self._polygon_layer.crs(), layer.crs(), transform_context
                        )
                        geom_for_layer.transform(transform)

                    features = self._features_within(layer, geom_for_layer)
                    if not features:
                        continue
                else:
                    # Esporta tutti gli elementi senza ritaglio
                    features = self._all_features(layer)
                    if not features:
                        continue

                path = self._export_layer(layer, features)
                exported_data.append((path, layer))
            
            elif layer.type() == QgsMapLayer.RasterLayer:
                # Per i layer raster (come XYZ Tiles), li aggiungiamo direttamente al progetto senza esportazione di file
                # Non effettuiamo ritagli di raster qui; semplicemente includiamo il riferimento al layer originale.
                exported_data.append((layer.source(), layer))
            
            else:
                QgsMessageLog.logMessage(
                    f"Tipo di layer non supportato per l'esportazione: {layer.name()} ({layer.type()})",
                    "ExportLayersWithinArea",
                    level=Qgis.Warning,
                )
                continue

        if not exported_data:
            raise ExportError("Nessuna feature è stata esportata. Verifica le selezioni.")

        return exported_data

    def get_export_directory(self) -> str:
        """Restituisce la sottodirectory dove sono stati salvati i file esportati."""
        return self._export_subdirectory

    def _union_polygon_geometries(self) -> QgsGeometry:
        """Unisce tutte le geometrie dei poligoni selezionati in un'unica geometria."""
        if len(self._polygon_features) == 1:
            # Se c'è un solo poligono, restituisci direttamente la sua geometria
            return QgsGeometry(self._polygon_features[0].geometry())
        
        # Combina tutte le geometrie in una geometria multi-poligono
        # combine() crea una geometria che contiene tutte le geometrie
        combined_geom = QgsGeometry(self._polygon_features[0].geometry())
        for feature in self._polygon_features[1:]:
            feature_geom = QgsGeometry(feature.geometry())
            combined_result = combined_geom.combine(feature_geom)
            if combined_result and not combined_result.isEmpty():
                combined_geom = combined_result
        
        # Se possibile, unisci effettivamente le geometrie sovrapposte usando unaryUnion
        # Questo crea una singola geometria unificata invece di una multi-geometria
        try:
            if hasattr(combined_geom, 'unaryUnion'):
                union_geom = combined_geom.unaryUnion()
                if union_geom and not union_geom.isEmpty():
                    return union_geom
        except (AttributeError, Exception):
            # Se unaryUnion non è disponibile o fallisce, usa la geometria combinata
            pass
        
        return combined_geom

    def _features_within(self, layer: QgsVectorLayer, polygon_geom: QgsGeometry) -> List[QgsFeature]:
        result: List[QgsFeature] = []

        # Usa una richiesta spaziale per limitare le features caricate
        # Questo riduce significativamente il carico sul database
        request = QgsFeatureRequest()
        request.setFilterRect(polygon_geom.boundingBox())

        # Aggiungi un piccolo buffer alla bounding box per essere sicuri di non perdere features
        buffered_bbox = polygon_geom.boundingBox()
        buffer_distance = min(buffered_bbox.width(), buffered_bbox.height()) * 0.01  # 1% di buffer
        buffered_bbox.grow(buffer_distance)

        request.setFilterRect(buffered_bbox)

        # Ottimizzazioni per le performance
        request.setFlags(QgsFeatureRequest.NoGeometry | QgsFeatureRequest.SubsetOfAttributes)
        # Rimuovi il flag NoGeometry perché abbiamo bisogno della geometria per il ritaglio
        request.setFlags(request.flags() & ~QgsFeatureRequest.NoGeometry)

        def get_features_operation():
            features_iterator = layer.getFeatures(request)
            for feature in features_iterator:
                # Controlla se l'operazione è stata cancellata
                if self._cancellation_check and self._cancellation_check():
                    raise ExportError("Esportazione cancellata dall'utente")

                geometry = feature.geometry()
                if not geometry or geometry.isEmpty():
                    continue
                if not geometry.intersects(polygon_geom):
                    continue

                new_feature = QgsFeature(feature)
                new_geometry = self._clip_geometry(layer, geometry, polygon_geom)
                if new_geometry is None or new_geometry.isEmpty():
                    continue
                new_feature.setGeometry(new_geometry)
                result.append(new_feature)

        try:
            _execute_with_retry(get_features_operation)
        except ExportError:
            raise  # Re-raise ExportError as-is
        except Exception as e:
            # Gestione errori di connessione database
            error_msg = f"Errore nell'accesso al layer {layer.name()}: {str(e)}"
            if "password" in str(e).lower() or "connection" in str(e).lower():
                error_msg += "\n\nPossibile timeout della connessione al database. Riprova con meno layer o una selezione più piccola."
            raise ExportError(error_msg)

        return result

    def _all_features(self, layer: QgsVectorLayer) -> List[QgsFeature]:
        """Restituisce tutte le features di un layer senza applicare ritagli geometrici."""
        result: List[QgsFeature] = []

        # Usa una richiesta con limiti per evitare di caricare tutto in memoria
        # Questo è particolarmente importante per layer connessi a database
        request = QgsFeatureRequest()

        # Limita il numero di features per evitare timeout (massimo 10000 features)
        # L'utente può sempre fare esportazioni separate se necessario
        request.setLimit(10000)

        # Ottimizzazioni per le performance
        request.setFlags(request.flags() & ~QgsFeatureRequest.NoGeometry)

        def get_all_features_operation():
            features_iterator = layer.getFeatures(request)
            for feature in features_iterator:
                # Controlla se l'operazione è stata cancellata
                if self._cancellation_check and self._cancellation_check():
                    raise ExportError("Esportazione cancellata dall'utente")

                geometry = feature.geometry()
                if not geometry or geometry.isEmpty():
                    continue
                result.append(QgsFeature(feature))

        try:
            _execute_with_retry(get_all_features_operation)
        except ExportError:
            raise  # Re-raise ExportError as-is
        except Exception as e:
            # Gestione errori di connessione database
            error_msg = f"Errore nell'accesso al layer {layer.name()}: {str(e)}"
            if "password" in str(e).lower() or "connection" in str(e).lower():
                error_msg += "\n\nPossibile timeout della connessione al database. Riprova con meno layer o considera di filtrare i dati."
            elif "limit" in str(e).lower():
                error_msg += "\n\nIl layer contiene troppi elementi. Usa la modalità 'Elementi nei poligoni selezionati' per limitare l'esportazione."
            raise ExportError(error_msg)

        return result

    def _clip_geometry(
        self,
        layer: QgsVectorLayer,
        geometry: QgsGeometry,
        polygon_geom: QgsGeometry,
    ) -> QgsGeometry:
        geom_type = layer.geometryType()
        if geom_type == QgsWkbTypes.PointGeometry:
            return geometry if geometry.within(polygon_geom) else None
        if geom_type == QgsWkbTypes.LineGeometry:
            return geometry.intersection(polygon_geom)
        if geom_type == QgsWkbTypes.PolygonGeometry:
            return geometry.intersection(polygon_geom)
        return geometry

    def _export_layer(self, layer: QgsVectorLayer, features: List[QgsFeature]) -> str:
        safe_name = self._sanitize_filename(layer.name())
        
        # Crea un nome file basato sul nome del layer originale
        filename = f"{safe_name}.gpkg"
        
        output_path = os.path.join(self._export_subdirectory, filename)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.fileEncoding = layer.dataProvider().encoding() or "UTF-8"
        options.layerName = safe_name
        options.symbologyExport = QgsVectorFileWriter.SymbologyExport.FeatureSymbology

        transform_context = QgsProject.instance().transformContext()
        writer = QgsVectorFileWriter.create(
            output_path,
            layer.fields(),
            layer.wkbType(),
            layer.crs(),
            transform_context,
            options,
        )

        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise ExportError(f"Errore nella creazione del file: {writer.errorMessage()}")

        writer.addFeatures(features)
        del writer
        return output_path

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name).strip("_") or "layer"

