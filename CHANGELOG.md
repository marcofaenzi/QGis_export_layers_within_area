# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-11-14

### Added
- **Project copying approach**: Instead of creating a new empty project, the plugin now copies the existing QGIS project and updates only the datasource paths of exported layers
- **Complete configuration preservation**: All project settings, groups, relations, styles, and configurations are automatically preserved in the exported project
- **Simplified export workflow**: Eliminates the need to manually recreate layer groups, styles, and project settings after export
- **Layer cleanup**: Automatically removes non-exported layers from the copied project
- **Group cleanup**: Automatically removes empty groups from the layer tree after layer removal
- **Empty table export**: Tables without geometry are now exported even when empty, preserving their structure for future use

### Changed
- **Export method**: Completely redesigned the project creation logic to use project copying instead of building from scratch
- **Layer management**: Exported layers now maintain their position in the layer tree and all associated properties
- **Project opening**: Exported projects are no longer opened automatically; only success message with file path is shown

### Removed
- **Manual project reconstruction**: Removed the complex logic for rebuilding layer trees, groups, and relations from scratch

## [1.5.3] - 2025-11-14

### Added
- **Supporto layer senza geometria**: I layer vettoriali senza geometria (tabelle) possono ora essere selezionati ed esportati
- **Esportazione completa tabelle**: Le tabelle vengono sempre esportate con tutti i record, indipendentemente dal poligono di selezione

### Fixed
- **Riconoscimento tabelle**: Corretta la logica per riconoscere correttamente i layer con `NullGeometry` (valore 4) come tabelle senza geometria

### Changed
- **Dialog di selezione**: Rimosso il filtro che escludeva i layer senza geometria dalla lista di selezione
- **Gestione esportazione tabelle**: Ottimizzata la gestione dei layer senza geometria per migliorare le performance
- **Logging migliorato**: Aggiunto logging dettagliato per identificare correttamente i layer senza geometria

## [1.5.2] - 2025-11-14

### Changed
- **Geometrie non tagliate**: Le geometrie parzialmente incluse nel poligono di selezione ora vengono incluse intere senza modificare la geometria originale
- **Performance migliorate**: Rimossa l'operazione di clipping delle geometrie, migliorando significativamente la velocità di esportazione

### Removed
- **Clipping delle geometrie**: Rimossa la logica di ritaglio (clip/intersection) delle geometrie che intersecano il poligono di selezione
- **Metodo `_clip_geometry`**: Rimosso il metodo non più necessario per il ritaglio geometrico

## [1.5.0] - 2025-11-13

### Added
- **Automatic labeling mode activation**: Layers exported with rule-based labeling now automatically appear with the correct labeling type ("Rule-based labeling") instead of "No labels"
- **Deferred labeling application**: Labels are now applied after all layers are added to the project, ensuring proper dependencies and activation
- **Comprehensive labeling support**: Plugin now copies label configurations (simple labels, rule-based labels) and activates the appropriate labeling mode
- **Enhanced labeling validation**: Added validation to ensure labels are properly applied and functional in exported projects

### Fixed
- **Label copying timing issue**: Fixed issue where labels were copied but not activated due to incorrect timing in the export process
- **Rule-based labeling export**: Rule-based labeling configurations are now properly exported and activated
- **Label type inheritance**: Exported layers now inherit the correct labeling mode from the original layers

### Changed
- **Labeling workflow**: Improved the labeling export process to apply configurations after project setup for better reliability

## [1.4.1] - 2025-11-13

### Added
- **Intelligent label copying**: Plugin now only copies labels that are actually enabled and configured, avoiding empty/disabled label configurations
- **Label validation system**: Added comprehensive validation for label configurations before copying
- **Smart label detection**: Automatically detects and copies simple labels, rule-based labels, and other labeling types

### Fixed
- **Empty label export**: Fixed issue where disabled or empty label configurations were being copied unnecessarily
- **Label validation errors**: Resolved errors in label validation logic for different QGIS versions

### Changed
- **Label export logic**: Improved label copying to be more intelligent and avoid copying irrelevant configurations

## [1.4.0] - 2025-11-13

### Added
- **Relation copying**: Project relations between tables are now automatically copied to exported projects
- **Relation validation**: Only relations where both referenced layers are exported are included
- **Relation logging**: Added logging for relation copying operations

### Fixed
- **Relation mapping bug**: Fixed AttributeError in relation copying due to incorrect dictionary key access
- **Project relations export**: Relations are now properly maintained in exported QGIS projects

## [1.3.0] - 2025-11-13

### Added
- **Dynamic QGZ naming**: Exported QGZ project files now use the original project name (e.g., `my_project_exported.qgz`)
- **Project name inheritance**: Export directory and files are named based on the source project

### Changed
- **File naming convention**: QGZ files no longer use generic names, now reflect the source project

## [1.2.0] - 2025-11-13

### Added
- **Automatic database reconnection**: Plugin automatically retries failed database connections with exponential backoff
- **Timeout handling**: Improved handling of database timeouts and connection issues
- **Connection validation**: Pre-export validation of database layer accessibility
- **Error recovery**: Smart error handling for database connection problems

### Fixed
- **Database connection failures**: Resolved "fe_sendauth: no password supplied" and timeout errors
- **Export interruptions**: Better handling of database connectivity issues during long exports

### Changed
- **Database error messages**: More informative error messages with recovery suggestions
- **Connection retry logic**: Improved retry mechanism for database operations

## [1.1.0] - 2025-11-13

### Added
- **Spatial query optimization**: Uses bounding boxes with buffers to limit database queries
- **Cancellation support**: Users can cancel long-running exports with a dedicated button
- **Progress feedback**: Enhanced progress reporting during export operations
- **Memory optimization**: Reduced memory usage for large dataset exports

### Fixed
- **Performance issues**: Resolved slow exports for large datasets
- **Memory consumption**: Optimized query patterns to reduce memory usage
- **Export cancellation**: Added proper cancellation handling for database operations

### Removed
- **Arbitrary export limits**: Removed the 10,000 feature limit that was restricting functionality

## [1.0.0] - 2025-11-13

### Added
- **Core export functionality**: Export vector layers within selected polygon areas
- **Geographic filtering**: Clip vector features to polygon boundaries
- **GeoPackage export**: Export to GeoPackage format with proper CRS handling
- **QGIS project generation**: Automatic creation of QGIS project files with exported layers
- **Symbology preservation**: Maintains original layer styling and rendering
- **Layer organization**: Proper layer grouping in exported projects
- **Configuration dialog**: User-friendly interface for setting up export parameters
- **Output directory management**: Flexible output directory selection

### Features
- Export all features or only those within selected polygons
- Support for multiple polygon selections
- Automatic coordinate transformation
- Progress monitoring
- Error handling and user feedback

---

## Development Notes

This changelog documents the evolution of the Export Layers Within Area QGIS plugin during an intensive development session. The plugin was enhanced from a basic export tool to a comprehensive solution with advanced features like:

- Robust database connectivity handling
- Intelligent label and symbology preservation
- Relation management
- Performance optimizations
- User experience improvements

All changes maintain backward compatibility and follow QGIS plugin development best practices.
