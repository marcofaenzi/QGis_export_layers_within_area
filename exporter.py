"""Logica di esportazione dei layer."""

import os
from typing import Iterable, List, Union, Tuple

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
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


class LayerExporter:
    """Gestisce l'esportazione dei layer selezionati all'interno di uno o più poligoni."""

    def __init__(
        self,
        polygon_layer: QgsVectorLayer,
        polygon_features: Union[QgsFeature, List[QgsFeature]],
        target_layers: Iterable[QgsMapLayer], # Changed from QgsVectorLayer to QgsMapLayer
        output_directory: str,
    ) -> None:
        self._polygon_layer = polygon_layer
        
        # Normalizza: accetta sia una singola feature che una lista
        if isinstance(polygon_features, QgsFeature):
            self._polygon_features = [polygon_features]
        else:
            self._polygon_features = list(polygon_features)
        
        self._target_layers = list(target_layers)
        self._output_directory = output_directory

        if not os.path.isdir(self._output_directory):
            raise ExportError("La cartella di destinazione non esiste.")

        if not self._polygon_features:
            raise ExportError("Nessun poligono selezionato.")

        # Verifica che tutte le feature abbiano geometrie valide
        for feature in self._polygon_features:
            if not feature or not feature.geometry() or feature.geometry().isEmpty():
                raise ExportError("Uno o più poligoni selezionati non contengono geometrie valide.")

    def export(self) -> List[Tuple[str, QgsMapLayer]]:
        exported_data: List[Tuple[str, QgsMapLayer]] = []
        transform_context = QgsProject.instance().transformContext()

        # Unisce tutte le geometrie dei poligoni selezionati in un'unica geometria
        union_geom = self._union_polygon_geometries()

        for layer in self._target_layers:
            if layer.type() == QgsMapLayer.VectorLayer:
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
        request = layer.getFeatures()
        for feature in request:
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
        
        output_path = os.path.join(self._output_directory, filename)

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

