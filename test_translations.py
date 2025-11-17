#!/usr/bin/env python3
"""Script di test per verificare il funzionamento delle traduzioni."""

import os
import sys
from qgis.PyQt.QtCore import QCoreApplication, QTranslator, QLocale
from qgis.PyQt.QtWidgets import QApplication

# Aggiungi il percorso del plugin
plugin_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, plugin_dir)

def test_translations():
    """Test delle traduzioni."""
    app = QApplication([])

    # Test italiano
    print("=== Test Italiano ===")
    translator_it = QTranslator()
    qm_path_it = os.path.join(plugin_dir, "i18n", "export_layers_within_area_it.qm")
    if translator_it.load(qm_path_it):
        QCoreApplication.installTranslator(translator_it)
        print("✓ Traduzioni italiane caricate")
    else:
        print("✗ Errore caricamento traduzioni italiane")

    # Test traduzioni con contesti corretti
    test_strings = [
        ("MainDialog", "Export Layers Within Area", "Export Layers Within Area"),
        ("ConfigDialog", "Browse", "Sfoglia"),
        ("ConfigDialog", "Enable detailed logging", "Abilita logging dettagliato"),
        ("MainDialog", "Layers to export", "Layer da esportare"),
        ("MainDialog", "Export all features", "Esporta tutti gli elementi"),
        ("MainDialog", "No polygon selected.", "Nessun poligono selezionato.")
    ]

    for context, english, expected_italian in test_strings:
        # Simula la traduzione italiana
        translated = QCoreApplication.translate(context, english)
        if translated == expected_italian:
            print(f"✓ '{english}' -> '{translated}'")
        else:
            print(f"✗ '{english}' -> '{translated}' (atteso: '{expected_italian}')")

    # Rimuovi traduttore italiano
    QCoreApplication.removeTranslator(translator_it)

    print("\n=== Test Inglese (default) ===")
    # Test inglese (dovrebbe essere la lingua di default)
    for context, english, _ in test_strings:
        translated = QCoreApplication.translate(context, english)
        if translated == english:
            print(f"✓ '{english}' -> '{translated}' (default)")
        else:
            print(f"? '{english}' -> '{translated}' (diverso dal default)")

    print("\nTest completato!")

if __name__ == "__main__":
    test_translations()
