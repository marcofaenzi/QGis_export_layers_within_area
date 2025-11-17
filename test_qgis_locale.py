#!/usr/bin/env python3
"""Script di test per verificare il caricamento delle traduzioni basato sulla lingua QGIS."""

import os
import sys
from qgis.PyQt.QtCore import QCoreApplication, QTranslator, QLocale
from qgis.PyQt.QtWidgets import QApplication

# Aggiungi il percorso del plugin
plugin_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, plugin_dir)

# Mock di QgsApplication per test
class MockQgsApplication:
    @staticmethod
    def locale():
        return "it_IT"  # Simula lingua italiana in QGIS

# Sostituisci temporaneamente per test
import qgis.core
original_qgs_app = getattr(qgis.core, 'QgsApplication', None)
qgis.core.QgsApplication = MockQgsApplication

def test_qgis_locale_loading():
    """Test del caricamento traduzioni basato su lingua QGIS."""
    app = QApplication([])

    print("=== Test caricamento traduzioni basato su lingua QGIS ===")

    # Simula il metodo _load_translations del plugin
    def _load_translations():
        """Carica le traduzioni basate sulla lingua di QGIS."""
        # Ottieni la lingua di QGIS
        locale = qgis.core.QgsApplication.locale()
        print(f"Lingua QGIS rilevata: {locale}")

        # Lista delle varianti da provare in ordine di priorità
        translations_dir = os.path.join(plugin_dir, "i18n")
        translator = QTranslator()

        locale_variants = [locale]  # Locale completo (es. it_IT)

        # Aggiungi variante con solo la lingua se diversa
        if '_' in locale:
            language_only = locale.split('_')[0]
            if language_only != locale:
                locale_variants.append(language_only)  # Solo lingua (es. it)

        # Prova ogni variante
        for locale_variant in locale_variants:
            qm_file = f"export_layers_within_area_{locale_variant}.qm"
            qm_path = os.path.join(translations_dir, qm_file)
            print(f"Cercando traduzioni: {qm_path}")
            if os.path.exists(qm_path) and translator.load(qm_path):
                QCoreApplication.installTranslator(translator)
                print(f"✓ Traduzioni caricate: {locale_variant}")
                return True

        print("✗ Nessun file di traduzione trovato, uso lingua inglese di default")
        return False

    # Test caricamento
    success = _load_translations()

    if success:
        # Test alcune traduzioni
        test_strings = [
            ("ConfigDialog", "Browse", "Sfoglia"),
            ("MainDialog", "Layers to export", "Layer da esportare"),
            ("MainDialog", "Export all features", "Esporta tutti gli elementi")
        ]

        print("\n=== Test traduzioni ===")
        for context, english, expected_italian in test_strings:
            translated = QCoreApplication.translate(context, english)
            if translated == expected_italian:
                print(f"✓ '{english}' -> '{translated}'")
            else:
                print(f"✗ '{english}' -> '{translated}' (atteso: '{expected_italian}')")
    else:
        print("Test fallito: traduzioni non caricate")

    print("\nTest completato!")

if __name__ == "__main__":
    test_qgis_locale_loading()
