# Export Layers Within Area

QGIS plugin for exporting vector and raster layers, limiting content to features contained within one or more selected polygons.

## Purpose

The plugin allows exporting selected layers from the current QGIS project, spatially limiting their content to features that fall within previously selected polygons in a reference polygon layer.

It is particularly useful for:
- Creating spatial subsets of geographic data
- Exporting data for specific areas of interest
- Preparing datasets for targeted territorial analyses

## Installation

1. Download the plugin as a ZIP archive
2. In QGIS, go to `Plugins → Manage and Install Plugins → Install from ZIP`
3. Select the downloaded ZIP file and click "Install Plugin"
4. Activate the plugin in the "Installed" section

## Configuration

### 1. Polygon Layer Configuration

Before using the plugin, you need to configure a polygon layer that will serve as spatial reference:

1. Click the settings icon (⚙️) in the plugin toolbar
2. Select the desired polygon layer from the dropdown menu
3. Choose the destination folder for exports
4. Click "OK" to save the configuration

### 2. Output Folder Configuration

In the same configuration window, you can set:
- The default destination folder for exports
- If not specified, a subfolder `exported_layers` in the plugin directory will be used

## Usage

### Starting Export

1. Click the export icon (📤) in the plugin toolbar
2. Select the layers to export from the available list
3. Choose the export mode:
   - **Features within selected polygons**: exports only features that fall within the selected polygons
   - **All features**: exports all features from the selected layers (without spatial filtering)

### Polygon Selection

For the "Features within selected polygons" mode:
- Select one or more polygons in the configured layer before starting the export
- The plugin will use these polygons as a spatial mask to filter the data

### Export Directory Name

- You can specify a custom name for the folder that will contain the exported files
- If not specified, a timestamp will be used as the folder name

## Output

The plugin generates:

### Exported Files
- **Vector layers**: exported in GeoPackage format (.gpkg)
- **Raster layers**: preserved with their original settings
- **QGIS Project**: .qgz file containing all exported layers with the same tree structure as the original project, including table relationships

### Output Folder Structure
```
export_folder/
├── layer1.gpkg
├── layer2.gpkg
├── raster1.tif
├── [project_name]_exported.qgz
└── [other exported files]
```

**Note**: The name of the exported QGIS project file corresponds to the current project name (e.g.: `my_project_exported.qgz`).

## Advanced Features

### Concurrent Export Management
- The plugin prevents starting multiple simultaneous exports
- If you try to start a new export while another is in progress, a confirmation warning is shown
- You can choose to proceed anyway or cancel the new export

### Layer Properties Preservation
- **Styles and renderers**: maintained in the exported project
- **Labels**: labeling settings copied only if actually enabled and configured (simplified validation for QGIS version compatibility)
- **Visibility**: layer visibility configuration is respected
- **Scale visibility**: minimum/maximum scale settings are preserved
- **Opacity**: maintained for raster layers

### Relationship Management
- **Table relationships**: automatically copied to the exported project
- **Complete relationships only**: only relationships where both related layers have been exported are included
- **Operation logs**: details about which relationships were copied or skipped are logged in QGIS logs

### Progress Bar
- Real-time monitoring of export progress
- Ability to cancel the ongoing operation

### Database and Performance Optimizations
- **Connection timeout management**: automatic retry for expired database connections
- **Optimized queries**: use of spatial bounding boxes to reduce database load
- **No limits**: export of all available features in the selected layers
- **Cancellation controls**: ability to interrupt long operations at any time
- **Spatial buffer**: small buffer added to bounding boxes to avoid losing features at edges

## System Requirements

- QGIS 3.22 or higher
- Python 3.7+
- Standard QGIS modules (no external dependencies)

## Technical Notes

- Export occurs in background via separate thread to not block the user interface
- Vector layers are geometrically clipped using QGIS algorithms
- The exported QGIS project maintains the layer tree structure of the original project
- Raster layers are referenced in the new project maintaining their original settings

## Troubleshooting

### Timeouts and Freezes During Exports
If QGIS freezes during complex exports with lots of data:

1. **Use polygon selection**: instead of "All features", select specific polygons to limit the data
2. **Reduce layer count**: export fewer layers simultaneously
3. **Cancel operation**: use the "Cancel" button in the progress bar to interrupt long exports
4. **Check database connection**: ensure PostgreSQL/PostGIS connection is stable

### Database Connection Errors
- **"fe_sendauth: no password supplied"**: the plugin automatically retries the connection, but credentials need to be saved
- **Connection timeout**: the system waits a few seconds and automatically retries
- If problems persist, check database connection settings in QGIS

#### How to save database credentials in QGIS project:
1. **For each PostGIS layer in the project**:
   - Right-click on the layer → Properties
   - Go to the "Source" tab
   - In the "Connection" section, click "Store in project configuration"
   - Enter username and password when prompted
   - Click "OK" to save

2. **Verify that credentials are saved**:
   - Reopen the QGIS project
   - Layers should load without requiring password again

3. **If using QGIS master authentication**:
   - Go to Settings → Options → Authentication
   - Ensure authentication is configured correctly
   - Verify that layers use master authentication

### Large Exports
For very large exports, consider:
- Use "Features within selected polygons" mode to limit export to specific areas
- Perform separate exports for smaller portions of the area of interest
- Use the "Cancel" button if the export is taking too long

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete changelog and new features.

## Support

To report bugs or request features, use the project repository.

## License

This plugin can only be distributed under GNU GPL v.2 or later license.
