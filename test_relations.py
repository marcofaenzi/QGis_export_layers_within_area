"""Script di test per verificare la copia delle relazioni nei progetti esportati.

Questo script può essere eseguito dalla console Python di QGIS per verificare
che le relazioni siano state copiate correttamente nel progetto esportato.

Uso:
1. Apri il progetto esportato in QGIS
2. Apri la console Python (Plugins → Console Python)
3. Esegui questo script modificando il percorso se necessario
"""

from qgis.core import QgsProject, QgsMessageLog, Qgis


def test_relations():
    """Testa e mostra tutte le relazioni presenti nel progetto corrente."""
    project = QgsProject.instance()
    relation_manager = project.relationManager()
    
    relations = relation_manager.relations()
    
    if not relations:
        print("❌ Nessuna relazione trovata nel progetto corrente")
        QgsMessageLog.logMessage(
            "Nessuna relazione trovata nel progetto corrente",
            "TestRelations",
            level=Qgis.Warning,
        )
        return False
    
    print(f"✅ Trovate {len(relations)} relazioni nel progetto:")
    print("=" * 80)
    
    valid_count = 0
    invalid_count = 0
    
    for relation_id, relation in relations.items():
        print(f"\n🔗 Relazione: {relation.name()} (ID: {relation_id})")
        print(f"   Tipo: {relation.strength()}")
        
        # Layer referencing (child)
        ref_layer = relation.referencingLayer()
        if ref_layer:
            print(f"   📄 Layer referencing (child): {ref_layer.name()}")
            print(f"      Campi: {', '.join(relation.referencingFields())}")
        else:
            print(f"   ❌ Layer referencing non trovato: {relation.referencingLayerId()}")
        
        # Layer referenced (parent)
        refd_layer = relation.referencedLayer()
        if refd_layer:
            print(f"   📄 Layer referenced (parent): {refd_layer.name()}")
            print(f"      Campi: {', '.join(relation.referencedFields())}")
        else:
            print(f"   ❌ Layer referenced non trovato: {relation.referencedLayerId()}")
        
        # Validazione
        if relation.isValid():
            print("   ✅ Relazione VALIDA")
            valid_count += 1
        else:
            print(f"   ❌ Relazione NON VALIDA: {relation.validationError()}")
            invalid_count += 1
        
        # Verifica che i campi esistano nei layer
        if ref_layer and refd_layer:
            ref_fields = [field.name() for field in ref_layer.fields()]
            refd_fields = [field.name() for field in refd_layer.fields()]
            
            missing_ref_fields = [f for f in relation.referencingFields() if f not in ref_fields]
            missing_refd_fields = [f for f in relation.referencedFields() if f not in refd_fields]
            
            if missing_ref_fields:
                print(f"   ⚠️  Campi mancanti nel layer referencing: {', '.join(missing_ref_fields)}")
            if missing_refd_fields:
                print(f"   ⚠️  Campi mancanti nel layer referenced: {', '.join(missing_refd_fields)}")
    
    print("\n" + "=" * 80)
    print(f"Riepilogo: {valid_count} valide, {invalid_count} non valide")
    
    if invalid_count > 0:
        print("⚠️  Attenzione: alcune relazioni non sono valide!")
        QgsMessageLog.logMessage(
            f"Test completato: {valid_count} relazioni valide, {invalid_count} non valide",
            "TestRelations",
            level=Qgis.Warning,
        )
        return False
    else:
        print("✅ Tutte le relazioni sono valide!")
        QgsMessageLog.logMessage(
            f"Test completato con successo: {valid_count} relazioni valide",
            "TestRelations",
            level=Qgis.Info,
        )
        return True


def compare_relations(original_project_path=None):
    """Confronta le relazioni tra il progetto originale e quello esportato.
    
    Args:
        original_project_path: Percorso al progetto originale (opzionale)
    """
    current_project = QgsProject.instance()
    
    if not original_project_path:
        print("⚠️  Per confrontare le relazioni, specifica il percorso al progetto originale:")
        print("   compare_relations('/path/to/original_project.qgz')")
        return
    
    # Carica il progetto originale temporaneamente
    original_project = QgsProject()
    if not original_project.read(original_project_path):
        print(f"❌ Impossibile leggere il progetto originale: {original_project_path}")
        return
    
    orig_relations = original_project.relationManager().relations()
    curr_relations = current_project.relationManager().relations()
    
    print(f"Progetto originale: {len(orig_relations)} relazioni")
    print(f"Progetto corrente: {len(curr_relations)} relazioni")
    
    # Relazioni mancanti
    missing = set(orig_relations.keys()) - set(curr_relations.keys())
    if missing:
        print(f"\n⚠️  Relazioni mancanti nel progetto esportato: {len(missing)}")
        for rel_id in missing:
            rel = orig_relations[rel_id]
            print(f"   - {rel.name()} (ID: {rel_id})")
    
    # Relazioni aggiunte (non dovrebbe succedere)
    added = set(curr_relations.keys()) - set(orig_relations.keys())
    if added:
        print(f"\n⚠️  Relazioni extra nel progetto esportato: {len(added)}")
        for rel_id in added:
            rel = curr_relations[rel_id]
            print(f"   - {rel.name()} (ID: {rel_id})")
    
    # Relazioni in comune
    common = set(orig_relations.keys()) & set(curr_relations.keys())
    if common:
        print(f"\n✅ Relazioni copiate correttamente: {len(common)}")
        for rel_id in common:
            rel = curr_relations[rel_id]
            print(f"   - {rel.name()} (ID: {rel_id})")


if __name__ == "__main__":
    # Esegui il test di base
    test_relations()
    
    # Per confrontare con il progetto originale, decommentare e modificare il percorso:
    # compare_relations('/path/to/original_project.qgz')

