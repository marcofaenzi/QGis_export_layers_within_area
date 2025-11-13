# Export Layers Within Area

Plugin QGIS per esportare layer vettoriali e raster limitando i contenuti agli elementi contenuti in uno o più poligoni selezionati.

## Scopo

Il plugin permette di esportare layer selezionati dal progetto QGIS corrente, limitandone i contenuti spaziali agli elementi che ricadono all'interno di poligoni precedentemente selezionati in un layer poligonale di riferimento.

È particolarmente utile per:
- Creare sottoinsiemi spaziali di dati geografici
- Esportare dati per specifiche aree di interesse
- Preparare dataset per analisi territoriali mirate

## Installazione

1. Scaricare il plugin come archivio ZIP
2. In QGIS, andare su `Plugins → Gestisci e installa plugin → Installa da ZIP`
3. Selezionare il file ZIP scaricato e cliccare "Installa plugin"
4. Attivare il plugin nella sezione "Installati"

## Configurazione

### 1. Configurazione layer poligonale

Prima di utilizzare il plugin, è necessario configurare un layer poligonale che fungerà da riferimento spaziale:

1. Cliccare sull'icona delle impostazioni (⚙️) nella barra degli strumenti del plugin
2. Selezionare il layer poligonale desiderato dal menu a tendina
3. Scegliere la cartella di destinazione per le esportazioni
4. Cliccare "OK" per salvare la configurazione

### 2. Configurazione cartella di output

Nella stessa finestra di configurazione, è possibile impostare:
- La cartella di destinazione predefinita per le esportazioni
- Se non specificata, verrà utilizzata una sottocartella `exported_layers` nella directory del plugin

## Utilizzo

### Avvio esportazione

1. Cliccare sull'icona di esportazione (📤) nella barra degli strumenti del plugin
2. Selezionare i layer da esportare dall'elenco disponibile
3. Scegliere la modalità di esportazione:
   - **Elementi nei poligoni selezionati**: esporta solo gli elementi che ricadono entro i poligoni selezionati
   - **Tutti gli elementi**: esporta tutti gli elementi dei layer selezionati (senza filtro spaziale)

### Selezione poligoni

Per la modalità "Elementi nei poligoni selezionati":
- Selezionare uno o più poligoni nel layer configurato prima di avviare l'esportazione
- Il plugin utilizzerà questi poligoni come maschera spaziale per filtrare i dati

### Nome directory di esportazione

- È possibile specificare un nome personalizzato per la cartella che conterrà i file esportati
- Se non specificato, verrà utilizzato un timestamp come nome della cartella

## Output

Il plugin genera:

### File esportati
- **Layer vettoriali**: esportati in formato GeoPackage (.gpkg)
- **Layer raster**: conservati con le loro impostazioni originali
- **Progetto QGIS**: file .qgz contenente tutti i layer esportati con la stessa struttura ad albero del progetto originale, incluse le relazioni tra tabelle

### Struttura cartella di output
```
cartella_esportazione/
├── layer1.gpkg
├── layer2.gpkg
├── raster1.tif
├── exported_layers_project.qgz
└── [altri file esportati]
```

## Funzionalità avanzate

### Gestione esportazioni concorrenti
- Il plugin impedisce l'avvio di esportazioni multiple simultanee
- Se si tenta di avviare una nuova esportazione mentre un'altra è in corso, viene mostrato un avviso di conferma
- È possibile scegliere di procedere comunque o annullare la nuova esportazione

### Conservazione delle proprietà dei layer
- **Stili e renderer**: mantenuti nel progetto esportato
- **Etichette (labels)**: impostazioni di etichettatura copiate solo se effettivamente abilitate e configurate (validazione semplificata per compatibilità versioni QGIS)
- **Visibilità**: rispettata la configurazione di visibilità dei layer
- **Scala di visibilità**: conservate le impostazioni di scala minima/massima
- **Opacità**: mantenuta per i layer raster

### Gestione delle relazioni
- **Relazioni tra tabelle**: vengono copiate automaticamente nel progetto esportato
- **Solo relazioni complete**: vengono incluse solo le relazioni dove entrambi i layer correlati sono stati esportati
- **Validazione completa**: ogni relazione viene validata prima dell'aggiunta al progetto esportato
- **Controllo dei campi**: verifica automatica che tutti i campi della relazione esistano nei layer esportati
- **Log delle operazioni**: vengono registrati nel log di QGIS i dettagli su quali relazioni sono state copiate o saltate, con informazioni dettagliate su eventuali problemi
- **Test delle relazioni**: disponibile uno script (`test_relations.py`) per verificare che le relazioni siano state copiate correttamente

### Barra di progresso
- Monitoraggio in tempo reale dell'avanzamento dell'esportazione
- Possibilità di cancellare l'operazione in corso

### Ottimizzazioni per database e performance
- **Gestione timeout connessioni**: retry automatico per connessioni database scadute
- **Query ottimizzate**: utilizzo di bounding box spaziali per ridurre il carico sui database
- **Nessun limite**: esportazione di tutti gli elementi disponibili nei layer selezionati
- **Controlli cancellazione**: possibilità di interrompere operazioni lunghe in qualsiasi momento
- **Buffer spaziale**: piccolo buffer aggiunto alle bounding box per evitare perdita di features ai bordi

## Requisiti di sistema

- QGIS 3.22 o superiore
- Python 3.7+
- Moduli QGIS standard (nessuna dipendenza esterna)

## Note tecniche

- L'esportazione avviene in background tramite thread separato per non bloccare l'interfaccia utente
- I layer vettoriali vengono ritagliati geometricamente utilizzando gli algoritmi di QGIS
- Il progetto QGIS esportato mantiene la struttura ad albero dei layer del progetto originale
- I layer raster vengono referenziati nel nuovo progetto mantenendo le impostazioni originali

## Risoluzione problemi

### Timeout e freeze durante esportazioni
Se QGIS va in freeze durante esportazioni complesse con molti dati:

1. **Usa selezione poligonale**: invece di "Tutti gli elementi", seleziona specifici poligoni per limitare i dati
2. **Riduci numero layer**: esporta meno layer contemporaneamente
3. **Cancella operazione**: usa il pulsante "Annulla" nella barra di progresso per interrompere esportazioni lunghe
4. **Controlla connessione database**: assicurati che la connessione PostgreSQL/PostGIS sia stabile

### Errori di connessione database
- **"fe_sendauth: no password supplied"**: il plugin ritenta automaticamente la connessione
- **Timeout connessione**: il sistema attende qualche secondo e riprova automaticamente
- Se i problemi persistono, verifica le impostazioni di connessione al database in QGIS

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 53f3979 (Revert "versione 1.4")
#### Come salvare le credenziali del database nel progetto QGIS:
1. **Per ciascun layer PostGIS nel progetto**:
   - Fai clic destro sul layer → Proprietà
   - Vai alla scheda "Origine"
   - Nella sezione "Connessione", clicca su "Memorizza nella configurazione del progetto"
   - Inserisci username e password quando richiesti
   - Clicca "OK" per salvare

2. **Verifica che le credenziali siano salvate**:
   - Riapri il progetto QGIS
   - I layer dovrebbero caricarsi senza richiedere nuovamente la password

3. **Se usi l'autenticazione master di QGIS**:
   - Vai su Impostazioni → Opzioni → Autenticazione
   - Assicurati che l'autenticazione sia configurata correttamente
   - Verifica che i layer utilizzino l'autenticazione master

### Problemi con le relazioni nel progetto esportato
Se le relazioni tra tabelle non vengono visualizzate correttamente nel progetto esportato:

1. **Verifica che entrambi i layer siano stati esportati**:
   - Le relazioni vengono copiate solo se entrambi i layer (referencing e referenced) sono presenti nell'esportazione
   - Controlla il log di QGIS (Vista → Pannelli → Log messaggi) per vedere quali relazioni sono state saltate

2. **Controlla il log di QGIS**:
   - Apri il pannello "Log messaggi" in QGIS
   - Cerca messaggi con tag "ExportLayersWithinArea"
   - Verifica se ci sono messaggi di warning o errori relativi alle relazioni
   - I messaggi ti diranno se una relazione non è stata copiata e perché (campi mancanti, layer non validi, ecc.)

3. **Usa lo script di test**:
   - Apri il progetto esportato in QGIS
   - Vai su Plugins → Console Python
   - Carica ed esegui lo script `test_relations.py` dalla directory del plugin:
     ```python
     exec(open('/path/to/plugin/test_relations.py').read())
     ```
   - Lo script mostrerà tutte le relazioni presenti e se sono valide

4. **Verifica manualmente le relazioni**:
   - Nel progetto esportato, vai su Progetto → Proprietà → Relazioni
   - Controlla se le relazioni sono presenti nell'elenco
   - Se una relazione appare ma non funziona, verifica che i campi della relazione esistano in entrambi i layer

5. **Problemi comuni**:
   - **Campi mancanti**: Se i campi della relazione non esistono nei layer esportati (GeoPackage), la relazione viene saltata
   - **Layer non esportati**: Se uno dei layer della relazione non è stato selezionato per l'esportazione, la relazione viene saltata
   - **Relazioni non valide nel progetto originale**: Le relazioni devono essere valide nel progetto originale per essere copiate

### Esportazioni di grandi dimensioni
Per esportazioni molto grandi, considera:
- Usa la modalità "Elementi nei poligoni selezionati" per limitare l'esportazione a specifiche aree
=======
<<<<<<< HEAD
=======
>>>>>>> parent of c3aef7c (versione 1.4)
=======
>>>>>>> 53f3979 (Revert "versione 1.4")
### Limite features raggiunto
Quando viene visualizzato l'errore "Il layer contiene troppi elementi":
- Usa la modalità "Elementi nei poligoni selezionati" per limitare l'esportazione
>>>>>>> parent of c3aef7c (versione 1.4)
- Effettua esportazioni separate per porzioni più piccole dell'area di interesse
- Usa il pulsante "Annulla" se l'esportazione sta impiegando troppo tempo

## Cronologia delle modifiche

Vedi [CHANGELOG.md](CHANGELOG.md) per la cronologia completa delle modifiche e delle nuove funzionalità.

## Supporto

Per segnalare bug o richiedere funzionalità, utilizzare il repository del progetto.

## Licenza

Questo plugin può essere distribuito solo sotto licenza GNU GPL v.2 o successiva.
