# Guida al Test delle Relazioni

Questa guida spiega come verificare che le relazioni vengano correttamente copiate nel progetto esportato.

## Modifiche Implementate (v1.5.1)

Il metodo `_copy_project_relations()` è stato migliorato con:

1. ✅ **Validazione completa**: Ogni relazione viene validata con `isValid()` prima dell'aggiunta
2. ✅ **Controllo campi**: Verifica che tutti i campi della relazione esistano nei layer esportati
3. ✅ **Impostazione contesto**: Il contesto del progetto viene impostato sulla relazione per una validazione corretta
4. ✅ **Log dettagliati**: Messaggi informativi su ogni operazione di copia delle relazioni
5. ✅ **Gestione errori robusta**: Try-catch con messaggi di errore specifici

## Come Testare

### Passo 1: Prepara un progetto di test

1. Apri un progetto QGIS che contiene relazioni tra layer
2. Verifica che le relazioni siano configurate correttamente:
   - Vai su **Progetto → Proprietà → Relazioni**
   - Controlla che ci siano relazioni definite
   - Verifica che le relazioni siano valide

### Passo 2: Configura ed esegui l'esportazione

1. Apri QGIS e carica il plugin
2. Configura il layer poligonale e la directory di output
3. Seleziona almeno i layer che fanno parte delle relazioni
4. **IMPORTANTE**: Assicurati di esportare ENTRAMBI i layer di ogni relazione
   - Layer referencing (child/figlio)
   - Layer referenced (parent/genitore)
5. Esegui l'esportazione

### Passo 3: Controlla i log durante l'esportazione

1. Apri il pannello **Vista → Pannelli → Log messaggi**
2. Seleziona la scheda **ExportLayersWithinArea**
3. Cerca messaggi come:
   ```
   Relazione 'nome_relazione' copiata con successo nel progetto esportato
   (referencing: layer_child, referenced: layer_parent)
   ```
4. Se vedi warning, leggi attentamente il messaggio per capire il problema:
   - `Campi mancanti nei layer esportati`: un campo della relazione non esiste nel GeoPackage
   - `Layer non esportato(i)`: uno dei layer della relazione non è stato selezionato per l'esportazione
   - `Relazione non valida`: la relazione non supera la validazione di QGIS

### Passo 4: Verifica le relazioni nel progetto esportato

1. Apri il progetto esportato (file `.qgz`)
2. Vai su **Progetto → Proprietà → Relazioni**
3. Verifica che le relazioni siano presenti
4. Prova ad usare le relazioni:
   - Apri la tabella degli attributi del layer parent
   - Dovrebbe apparire una colonna con l'icona di relazione
   - Cliccando sull'icona dovresti vedere i record child correlati

### Passo 5: Usa lo script di test (opzionale ma consigliato)

1. Nel progetto esportato, apri la **Console Python** (Plugins → Console Python)
2. Esegui lo script di test:
   ```python
   import sys
   sys.path.append('/home/marco/NextCloud/sviluppo/plugin_QGIS/QGis_export_layers_within_area')
   from test_relations import test_relations
   test_relations()
   ```
3. Lo script mostrerà:
   - Numero di relazioni trovate
   - Dettagli di ogni relazione (nome, layer, campi)
   - Se le relazioni sono valide o meno
   - Eventuali problemi (campi mancanti, layer non trovati, ecc.)

### Esempio di output dello script di test

```
✅ Trovate 2 relazioni nel progetto:
================================================================================

🔗 Relazione: comuni_province (ID: comuni_province_1)
   Tipo: Association
   📄 Layer referencing (child): comuni
      Campi: provincia_id
   📄 Layer referenced (parent): province
      Campi: id
   ✅ Relazione VALIDA

🔗 Relazione: edifici_comuni (ID: edifici_comuni_1)
   Tipo: Association
   📄 Layer referencing (child): edifici
      Campi: comune_id
   📄 Layer referenced (parent): comuni
      Campi: id
   ✅ Relazione VALIDA

================================================================================
Riepilogo: 2 valide, 0 non valide
✅ Tutte le relazioni sono valide!
```

## Problemi Comuni e Soluzioni

### ⚠️ "Campi mancanti nei layer esportati"

**Causa**: Uno o più campi della relazione non esistono nei layer GeoPackage esportati.

**Soluzione**:
- Verifica che i campi esistano nel layer originale
- Controlla che i campi siano stati effettivamente esportati nel GeoPackage
- I campi devono avere lo stesso nome nel layer originale e in quello esportato

### ⚠️ "Layer non esportato(i)"

**Causa**: Uno dei layer della relazione non è stato selezionato per l'esportazione.

**Soluzione**:
- Assicurati di selezionare ENTRAMBI i layer della relazione durante l'esportazione
- Le relazioni vengono copiate solo se entrambi i layer sono presenti nell'esportazione

### ⚠️ "Relazione non valida"

**Causa**: La relazione non supera la validazione di QGIS.

**Soluzione**:
- Verifica che la relazione sia valida nel progetto originale
- Controlla che i layer esportati contengano i campi corretti
- Verifica che i tipi di dati dei campi siano compatibili

### ⚠️ "Impossibile trovare i layer per la relazione nel nuovo progetto"

**Causa**: I layer esistono ma non sono stati trovati nel progetto esportato.

**Soluzione**:
- Questo è un errore interno, controlla i log di QGIS per maggiori dettagli
- Assicurati che i layer siano stati effettivamente aggiunti al progetto
- Riporta il problema con i dettagli dai log

## Confronto con Progetto Originale

Per confrontare le relazioni tra progetto originale e esportato:

```python
from test_relations import compare_relations
compare_relations('/percorso/al/progetto/originale.qgz')
```

Questo mostrerà:
- Relazioni presenti in entrambi i progetti
- Relazioni mancanti nel progetto esportato
- Relazioni extra nel progetto esportato (non dovrebbe succedere)

## Ulteriori Informazioni

- Consulta il [CHANGELOG.md](CHANGELOG.md) per la cronologia delle modifiche
- Consulta il [README.md](README.md) per la documentazione completa del plugin
- I log di QGIS (pannello "Log messaggi") forniscono informazioni dettagliate durante l'esportazione

