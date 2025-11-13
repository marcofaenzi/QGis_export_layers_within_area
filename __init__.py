"""Plugin entry point for QGIS."""


def classFactory(iface):
    """Instanzia il plugin."""
    from .export_layers_within_area_plugin import ExportLayersWithinAreaPlugin

    return ExportLayersWithinAreaPlugin(iface)

