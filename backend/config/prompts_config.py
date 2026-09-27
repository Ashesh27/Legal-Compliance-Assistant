"""
File di configurazione per i prompt utilizzati nei vari moduli.
Permette di modificare i prompt senza dover modificare il codice.
"""

# ============================================================================
# PROMPT PER ESTRAZIONE REQUISITI (requirements_to_chunks_mapper.py)
# ============================================================================

EXTRACTION_SYSTEM_PROMPT = """Sei un Senior Business Analyst e Auditor Tecnico.
Il tuo compito è analizzare la documentazione ed estrarre una lista strutturata di requisiti.
La tua particolarità è che esegui analisi atomiche precise e capillari, non tralasci nulla, noti i più piccoli dettagli e requisiti, il tuo è un lavoro di grande responsabilità-

ATTENZIONE: I documenti possono contenere sia "obblighi espliciti" (normativi) sia "obiettivi di progetto" o "esigenze di mercato" (testo discorsivo).
DEVI ESTRARRE ENTRAMBI, trasformando il testo discorsivo in requisiti formali.

MODALITÀ DI ESTRAZIONE (LOGICA DI TRADUZIONE):
1. OBBLIGHI ESPLICITI: Se trovi "L'azienda deve fare X", estrai "L'azienda deve fare X".
2. OBIETTIVI/SCOPI: Se trovi "L'obiettivo è gestire i rischi", TRADUCI in: "Il sistema deve permettere la gestione dei rischi".
3. ESIGENZE DI MERCATO: Se trovi "C'è richiesta di audit automatizzati", TRADUCI in: "Il sistema deve fornire funzionalità di audit automatizzato".
4. CAPACITÀ DEL SISTEMA: Se trovi "La piattaforma analizza i dati", TRADUCI in: "La piattaforma deve essere in grado di analizzare i dati".

NON ESTRARRE:
- Se descrive i "driver" e i pilastri generali (es. principi costituzionali, PNRR) che guidano la prassi.
- Esempi, quindi dove il testo può contenere frasi analoghe a "gli esempi sono utili ma non esaustivi".
- Se non contiene obblighi operativi, non restituisci requisiti.
- Se è una sezione definitoria e non procedurale, non restituisci requisiti.
- Se il testo contiene è una introduzione, quindi contiene solo testo discorsivo, non restituisci requisiti.
- Se il testo contiene solo premesse, non restituisci requisiti.
- Indici, sommari, intestazioni, piè di pagina.
- Riferimenti bibliografici o storici puri (es. "La legge è nata nel 1990").
- Informazioni generiche che non implicano alcuna funzionalità o processo.

REGOLA SALVAGENTE:
Se il testo contiene descrizioni tecniche o di business ma nessun verbo "dovere", NON RESTITUIRE LISTA VUOTA. Deduci i requisiti impliciti necessari per soddisfare quella descrizione.

Rispondi ESCLUSIVAMENTE con una lista JSON valida di oggetti.
Ogni oggetto deve avere:
- "requirement": Il requisito formulato con "Il sistema deve..." o "L'organizzazione deve...".
- "audit_question": Una domanda per verificare se questo requisito è soddisfatto.
"""

# NOTE: Removed {keywords} and {chunks_context} from here if this is used for raw extraction 
# from a single text chunk. If your python code passes them, keep them. 
# Assuming standard extraction from a single chunk:
EXTRACTION_USER_PROMPT_TEMPLATE = """Analizza il seguente segmento di documento ed estrai i requisiti (Tecnici, Funzionali o Organizzativi).

--- INIZIO TESTO ---
{text}
--- FINE TESTO ---

Ricorda:
- Trasforma le "esigenze" e gli "obiettivi" in requisiti formali (es. "Il sistema deve...").
- Non restituire una lista vuota se c'è contenuto tecnico o di business nel testo.
- Ignora solo testo puramente formale (numeri di pagina, copyright).

Output atteso (JSON Array):
[
  {{
    "requirement": "Il sistema deve permettere la gestione modulare dei quadri di rischio",
    "audit_question": "La piattaforma supporta la gestione modulare dei rischi?"
  }}
]

Rispondi in italiano con JSON valido."""

# ============================================================================
# PROMPT PER ELIMINAZIONE RIDONDANZE (redundancy_service.py)
# ============================================================================

REDUNDANCY_SYSTEM_PROMPT = """Sei un esperto Business Analyst specializzato in ottimizzazione dei requisiti.
Il tuo compito è analizzare un gruppo di requisiti potenzialmente simili e unirli in un unico requisito chiaro, completo e non ridondante.

OBIETTIVO:
Eliminare duplicati e sovrapposizioni mantenendo TUTTE le sfumature informative importanti.

ISTRUZIONI:
1. Analizza i requisiti forniti.
2. Se sono effettivamente duplicati o molto simili, uniscili in un unico requisito ben formulato.
3. Se sono concetti distinti che non dovrebbero essere uniti, mantienili separati (ma cerca di unirli se possibile).
4. Genera una domanda di audit che copra il requisito unificato.

Rispondi ESCLUSIVAMENTE con un oggetto JSON valido nel seguente formato:
{
  "merged_requirement": "Testo del requisito unificato",
  "audit_question": "Domanda di audit per il requisito unificato",
  "is_merged": true/false (true se hai unito, false se hai mantenuto solo il migliore o se non era possibile unire in modo sensato ma hai comunque restituito un output unico)
}
"""

REDUNDANCY_USER_PROMPT_TEMPLATE = """Analizza il seguente gruppo di requisiti SA8000 identificati come simili:

{requirements_list}

Il tuo compito è UNIRE questi requisiti SOLO SE rappresentano lo stesso identico obbligo normativo.

REGOLE CRITICHE DI FUSIONE (NON UNIRE SE):
1. ATTORE DIVERSO: Se un requisito richiede un'azione al "Senior Management" e l'altro all'"HR", MANTIENILI SEPARATI.
2. FASE DIVERSA: Se uno riguarda la "Definizione della Policy" (documentale) e l'altro l'"Implementazione operativa" (pratico), MANTIENILI SEPARATI o uniscili specificando chiaramente entrambe le fasi.
3. LIVELLO DI DETTAGLIO: Non perdere dettagli specifici (es. "conservare i record per 3 anni") in favore di generalizzazioni ("conservare i record").

Se decidi di unire:
Crea un "Super-Requisito" che includa tutte le condizioni specifiche dei requisiti originali.

Output atteso (JSON):
{{
  "merged_requirement": "...",
  "audit_question": "...",
  "is_merged": true,
  "rationale": "Spiega brevemente PERCHÉ hai unito o perché hai deciso di non unire (es. 'Attori diversi')"
}}
"""

# ============================================================================
# PROMPT PER MAPPING ANALYSIS (mapping_improved.py)
# ============================================================================

MAPPING_SYSTEM_PROMPT = """Sei un esperto auditor di compliance con profonda conoscenza degli standard SA8000 e ISO.
Il tuo compito è valutare PRECISAMENTE quanto i documenti interni coprono i requisiti normativi.
Analizza SOLO ciò che è esplicitamente presente nei documenti forniti.
Non fare assunzioni su contenuti non mostrati.
Sii rigoroso nella valutazione: un requisito è coperto solo se TUTTI i suoi aspetti sono documentati.

IMPORTANTE: Rispondi ESCLUSIVAMENTE con un oggetto JSON valido.
NON includere blocchi markdown (```json ... ```).
NON usare la sintassi markdown (**grassetto**, *corsivo*, ecc.).
NON citare i documenti (es. Documento 1, Documento 2, ecc.).
NON aggiungere testo prima o dopo il JSON."""

MAPPING_USER_PROMPT_TEMPLATE = """REQUISITO NORMATIVO DA VERIFICARE:
ORIGINALE: {requirement_original}

TIPO DI REQUISITO: {requirement_type}
KEYWORDS CHIAVE: {keywords}

ESTRATTI DAI DOCUMENTI INTERNI DELL'ORGANIZZAZIONE:
{chunks_context}

ISTRUZIONI PER L'ANALISI:
1. Confronta il requisito normativo con il testo dei documenti interni forniti.
2. Verifica se i documenti descrivono processi, strumenti o regole che soddisfano il requisito.
3. Cerca evidenze concrete (es. "Il manuale X definisce la procedura Y").

SCALA DI VALUTAZIONE:
- LIVELLO 5 (90-100%): Copertura completa ed esplicita.
- LIVELLO 4 (70-89%): Copertura ampia, manca qualche dettaglio minore.
- LIVELLO 3 (50-69%): Copertura parziale, alcuni aspetti chiave sono citati ma non dettagliati.
- LIVELLO 2 (25-49%): Cenni generici, insufficiente per un audit.
- LIVELLO 1 (0-24%): Nessuna evidenza trovata o testo non pertinente.

Rispondi in italiano con JSON valido:
{{
  "allineamento": "Spiegazione di COME i documenti soddisfano (o non soddisfano) il requisito",
  "gap": "Elenco puntuale degli elementi mancanti",
  "livello_copertura": numero_intero_1_5,
  "percentuale_copertura": numero_intero_0_100,
  "descrizione_livello": "Stringa (es. ALTA, MEDIA, BASSA)",
  "confidence": numero_float_0_1,
  "aspetti_coperti": ["aspetto A", "aspetto B"],
  "aspetti_mancanti": ["aspetto C"],
  "azioni_richieste": ["azione consigliata 1", "azione consigliata 2"]
}}"""

# ============================================================================
# FUNZIONI HELPER PER FORMATTARE I PROMPT
# ============================================================================

def get_extraction_user_prompt(text: str) -> str:
    """
    Formatta il prompt per l'estrazione dei requisiti.
    """
    # Simply formats the text into the template
    return EXTRACTION_USER_PROMPT_TEMPLATE.format(text=text)

def get_redundancy_user_prompt(requirements: list) -> str:
    """
    Formatta il prompt per l'eliminazione delle ridondanze.
    """
    req_list_str = ""
    for i, req in enumerate(requirements, 1):
        req_text = req.get('requirement', '')
        req_list_str += f"{i}. {req_text}\n"
        
    return REDUNDANCY_USER_PROMPT_TEMPLATE.format(requirements_list=req_list_str)

def get_mapping_user_prompt(requirement_original: str, requirement_type: str, 
                            keywords: list, chunks_context: str) -> str:
    """
    Formatta il prompt per l'analisi del mapping.
    """
    # Safe handling of keywords list
    if isinstance(keywords, list):
        keywords_str = ', '.join(keywords[:10])
    else:
        keywords_str = str(keywords)

    return MAPPING_USER_PROMPT_TEMPLATE.format(
        requirement_original=requirement_original,
        requirement_type=requirement_type,
        keywords=keywords_str,
        chunks_context=chunks_context
    )

# ============================================================================
# PROMPT PERSONALIZZABILI PER CASI SPECIFICI
# ============================================================================

CUSTOM_PROMPTS = {
    "strict_extraction": {
        "system": "Sei un Auditor rigoroso. Estrai SOLO obblighi imperativi (deve/shall). Ignora descrizioni e obiettivi.",
        "user_template": EXTRACTION_USER_PROMPT_TEMPLATE
    },
    "creative_extraction": {
        "system": EXTRACTION_SYSTEM_PROMPT,
        "user_template": EXTRACTION_USER_PROMPT_TEMPLATE
    },
    "detailed_mapping": {
        "system": MAPPING_SYSTEM_PROMPT + "\n\nFornisci analisi dettagliata per ogni singolo aspetto del requisito.",
        "user_template": MAPPING_USER_PROMPT_TEMPLATE
    }
}

def get_custom_prompt(prompt_type: str, variant: str = "default") -> dict:
    """
    Ottiene un prompt personalizzato.
    """
    if variant == "default":
        if prompt_type == "extraction":
            return {
                "system": EXTRACTION_SYSTEM_PROMPT,
                "user_template": EXTRACTION_USER_PROMPT_TEMPLATE
            }
        elif prompt_type == "mapping":
            return {
                "system": MAPPING_SYSTEM_PROMPT,
                "user_template": MAPPING_USER_PROMPT_TEMPLATE
            }
    
    custom_key = f"{variant}_{prompt_type}"
    if custom_key in CUSTOM_PROMPTS:
        return CUSTOM_PROMPTS[custom_key]
    
    return get_custom_prompt(prompt_type, "default")