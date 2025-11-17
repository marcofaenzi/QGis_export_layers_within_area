#!/usr/bin/env python3
"""Script per tradurre automaticamente il file .ts italiano."""

import re
from xml.etree import ElementTree as ET

# Dizionario delle traduzioni
translations = {
    "Export Layers Within Area Configuration": "Configurazione Export Layers Within Area",
    "Select a destination folder": "Seleziona una cartella di destinazione",
    "Browse": "Sfoglia",
    "Enable detailed logging": "Abilita logging dettagliato",
    "Enable/disable detailed log messages during export": "Abilita/disabilita i messaggi di log dettagliati durante l'esportazione",
    "Selection polygon layer:": "Layer poligonale di selezione:",
    "Export folder:": "Cartella di esportazione:",
    "Select destination folder": "Seleziona cartella di destinazione",
    "&Export Layers Within Area": "&Esporta Layer nell'Area Selezionata",
    "Esporta layer nell'area selezionata": "Esporta layer nell'area selezionata",
    "Configura l'area di selezione": "Configura l'area di selezione",
    "Configurazione": "Configurazione",
    "Impostazioni salvate correttamente.": "Impostazioni salvate correttamente.",
    "Export Layers Within Area": "Export Layers Within Area",
    "Configura prima un layer poligonale tramite il pannello impostazioni.": "Configura prima un layer poligonale tramite il pannello impostazioni.",
    "Configura prima una cartella di destinazione tramite il pannello impostazioni.": "Configura prima una cartella di destinazione tramite il pannello impostazioni.",
    "Seleziona almeno un poligono nel layer configurato prima di procedere.": "Seleziona almeno un poligono nel layer configurato prima di procedere.",
    "Impossibile recuperare i poligoni selezionati o le geometrie non sono valide.": "Impossibile recuperare i poligoni selezionati o le geometrie non sono valide.",
    "Nessun layer selezionato per l'esportazione.": "Nessun layer selezionato per l'esportazione.",
    "Problemi di connessione database": "Problemi di connessione database",
    "Alcuni layer potrebbero avere problemi di connessione al database:\n\n{issues}\n\nVerifica le tue credenziali del database.": "Alcuni layer potrebbero avere problemi di connessione al database:\n\n{issues}\n\nVerifica le tue credenziali del database.",
    "Esportazione già in corso": "Esportazione già in corso",
    "È già in corso un'esportazione. Vuoi avviarne un'altra comunque?\n\nNota: L'esportazione precedente continuerà in background.": "È già in corso un'esportazione. Vuoi avviarne un'altra comunque?\n\nNota: L'esportazione precedente continuerà in background.",
    "Errore nel salvataggio temporaneo del progetto.": "Errore nel salvataggio temporaneo del progetto.",
    "Errore nel caricamento della copia del progetto.": "Errore nel caricamento della copia del progetto.",
    "Errore nel salvataggio del progetto QGIS modificato.": "Errore nel salvataggio del progetto QGIS modificato.",
    "Progetto QGIS creato: {project_path}": "Progetto QGIS creato: {project_path}",
    "Annulla": "Annulla",
    "Annulla esportazione": "Annulla esportazione",
    "Sei sicuro di voler annullare l'esportazione in corso?": "Sei sicuro di voler annullare l'esportazione in corso?",
    "Annullamento...": "Annullamento...",
    "Esportazione completata: {count} file creati": "Esportazione completata: {count} file creati",
    "Esportazione cancellata": "Esportazione cancellata",
    "Layer": "Layer",
    "Exported project name": "Nome del progetto esportato",
    "Exported project name:": "Nome del progetto esportato:",
    "Layers to export": "Layer da esportare",
    "Export mode": "Modalità di esportazione",
    "Export all features": "Esporta tutti gli elementi",
    "Export only features within selected polygons": "Esporta solo elementi nei poligoni selezionati",
    "Clipping polygon": "Poligono di ritaglio",
    "Configured layer: {layer_name}": "Layer configurato: {layer_name}",
    "Select at least one polygon in the configured layer before starting the export.": "Seleziona almeno un poligono nel layer configurato prima di avviare l'esportazione.",
    "1 polygon selected": "1 poligono selezionato",
    "{count} polygons selected": "{count} poligoni selezionati",
    "No polygon selected.": "Nessun poligono selezionato.",
    "Select at least one layer to export.": "Seleziona almeno un layer da esportare."
}

def translate_ts_file():
    """Traduce il file .ts italiano."""
    tree = ET.parse('export_layers_within_area_it.ts')
    root = tree.getroot()

    for context in root:
        if context.tag == 'context':
            for message in context:
                if message.tag == 'message':
                    source = message.find('source')
                    translation = message.find('translation')

                    if source is not None and translation is not None:
                        source_text = source.text
                        if source_text in translations:
                            translation.text = translations[source_text]
                            translation.set('type', 'finished')

    # Scrivi il file tradotto
    tree.write('export_layers_within_area_it.ts', encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    translate_ts_file()
    print("Traduzione completata!")
