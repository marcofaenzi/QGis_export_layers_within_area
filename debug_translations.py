#!/usr/bin/env python3
"""Script di debug per verificare il caricamento delle traduzioni in QGIS."""

import os
import sys

# Aggiungi il percorso del plugin
plugin_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, plugin_dir)

def debug_qgis_locale():
    """Debug del rilevamento lingua QGIS e caricamento traduzioni."""
    try:
        from qgis.core import Qgis, QgsApplication
        from qgis.PyQt.QtCore import QCoreApplication, QTranslator

        print("=== Debug caricamento traduzioni ===")

        # Verifica che QGIS sia inizializzato
        if not QgsApplication.instance():
            print("❌ QGIS non è inizializzato")
            return

        # Ottieni la lingua di QGIS
        locale = QgsApplication.locale()
        print(f"🌍 Lingua QGIS rilevata: '{locale}'")

        # Directory delle traduzioni
        translations_dir = os.path.join(plugin_dir, "i18n")
        print(f"📁 Directory traduzioni: {translations_dir}")
        print(f"📁 Esiste directory: {os.path.exists(translations_dir)}")

        # Lista dei file .qm disponibili
        if os.path.exists(translations_dir):
            qm_files = [f for f in os.listdir(translations_dir) if f.endswith('.qm')]
            print(f"📄 File .qm disponibili: {qm_files}")
        else:
            print("❌ Directory traduzioni non trovata!")
            return

        # Prova a caricare le traduzioni
        translator = QTranslator()

        # Lista delle varianti da provare
        locale_variants = [locale]
        if '_' in locale:
            language_only = locale.split('_')[0]
            if language_only != locale:
                locale_variants.append(language_only)

        print(f"🔍 Varianti da provare: {locale_variants}")

        for locale_variant in locale_variants:
            qm_file = f"export_layers_within_area_{locale_variant}.qm"
            qm_path = os.path.join(translations_dir, qm_file)
            print(f"🔍 Cercando: {qm_path}")
            print(f"   Esiste: {os.path.exists(qm_path)}")

            if os.path.exists(qm_path):
                success = translator.load(qm_path)
                print(f"   Caricato: {success}")
                if success:
                    installed = QCoreApplication.installTranslator(translator)
                    print(f"   Installato: {installed}")

                    # Test una traduzione
                    test_translation = QCoreApplication.translate("MainDialog", "Layers to export")
                    print(f"   Test traduzione 'Layers to export': '{test_translation}'")
                    break
            else:
                print("   File non trovato")

        print("\n=== Test traduzioni specifiche ===")
        test_strings = [
            ("MainDialog", "Layers to export"),
            ("ConfigDialog", "Browse"),
            ("ExportLayersWithinAreaPlugin", "Export layers within selected area")
        ]

        for context, text in test_strings:
            translated = QCoreApplication.translate(context, text)
            status = "✅ Tradotto" if translated != text else "❌ Non tradotto"
            print(f"{status} {context}:'{text}' → '{translated}'")

    except ImportError as e:
        print(f"❌ Errore importazione: {e}")
        print("Assicurati che QGIS sia installato e accessibile")

if __name__ == "__main__":
    debug_qgis_locale()
