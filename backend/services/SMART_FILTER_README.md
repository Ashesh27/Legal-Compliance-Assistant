# Smart Content Filter - Guida Rapida

## Scopo

Smart Content Filter serve a **ripulire intelligentemente** i documenti prima della fase di chunking, rimuovendo le parti che non costituiscono "requisiti" o "contenuto tecnico" utile, ma che potrebbero inquinare la ricerca (es. Copertine, Indici, Log delle revisioni, Footer legali).

## Come Funziona

Il sistema non usa regole fisse (regex o keyword) ma sfrutta l'LLM per una classificazione semantica delle pagine.

1. **Suddivisione in Pagine Logiche**:
   Il testo grezzo viene diviso in segmenti di circa **3000 caratteri** (o usando i marcatori di pagina se presenti), simulando le pagine fisiche del documento.
2. **Analisi Iniziale (Head)**:

   - Esamina sequenzialmente le prime **3 pagine**.
   - Per ogni pagina, chiede all'LLM: *"Questa pagina contiene requisiti tecnici/normativi o solo metadati/indici?"*.
   - Se l'LLM risponde **"SCARTA"**, la pagina viene rimossa.
   - Se l'LLM risponde **"TIENI"**, l'analisi si ferma e il resto viene preservato.
3. **Analisi Finale (Tail)**:

   - Esamina le ultime **3 pagine** (partendo dall'ultima a ritroso).
   - Applica la stessa logica "TIENI/SCARTA".
   - Rimuove le pagine finali identificate come non rilevanti (es. disclaimer finali, pagine bianche).

## Configurazione

Il servizio usa il modello definito in `.env`:

```bash
LLM_EXTRACTION_MODEL=gemini-2.5-pro
```

È possibile configurare il numero di pagine da analizzare modificando `pages_to_check_start` in `smart_content_filter.py`.

## Integrazione

È integrato automaticamente in `ImprovedDocumentChunker`. Ogni documento passa attraverso `analyze_and_trim(text)` prima di essere processato.
