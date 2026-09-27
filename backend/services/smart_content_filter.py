import os
import re
from typing import Dict, Any, Tuple, Optional
from llm_provider import get_llm_provider

class SmartContentFilter:
    """
    Filtra intelligentemente l'inizio e la fine dei documenti per rimuovere
    header, footer, indici e copertine non rilevanti usando un LLM.
    """
    
    def __init__(self, model_name: str = None):
        """
        Inizializza il filtro intelligente.
        
        Args:
            model_name: Nome del modello LLM da utilizzare. Se None, usa LLM_EXTRACTION_MODEL da .env
        """
        self.llm = get_llm_provider()
        self.model_name = model_name or os.getenv("LLM_EXTRACTION_MODEL", "gemini-1.5-flash")
        # Rimuove eventuali commenti dal nome del modello (es. "gemini-2.5-pro # commento")
        if "#" in self.model_name:
            self.model_name = self.model_name.split("#")[0].strip()
            
        print(f"🔹 SmartContentFilter using model: {self.model_name}")
        self.context_window = 4000  # Caratteri da analizzare all'inizio/fine
        
    def analyze_and_trim(self, text: str) -> str:
        """
        Analizza e taglia il testo rimuovendo pagine non rilevanti all'inizio e alla fine.
        Identifica "pagine" logicamente e chiede all'LLM se mantenerle.
        """
        if not text or len(text) < 1000:
            return text
            
        # 1. Suddividi in "pagine" logiche (circa 3000 caratteri o marcatori se presenti)
        # Cerchiamo marcatori di pagina comuni o usiamo lunghezza fissa
        pages = self._split_into_logical_pages(text)
        print(f"📄 Documento suddiviso in {len(pages)} segmenti/pagine logiche per analisi.")
        
        # 2. Analizza prime 3 pagine
        start_index = 0
        pages_to_check_start = min(len(pages), 3)
        
        print("🔍 Analisi INIZIO documento...")
        for i in range(pages_to_check_start):
            page_content = pages[i]
            is_content = self._classify_page_content(page_content, is_start=True)
            
            if is_content:
                print(f"   ✅ Pagina {i+1} identificata come CONTENUTO. Stop taglio iniziale.")
                break
            else:
                print(f"   ❌ Pagina {i+1} identificata come NO-REQ (Cover/Indice/Intro). Sarà rimossa.")
                start_index += len(page_content)

        # 3. Analizza ultime 3 pagine (solo se rimangono abbastanza pagine)
        end_index = len(text)
        if len(pages) - pages_to_check_start > 2:
            print("🔍 Analisi FINE documento...")
            pages_to_check_end = min(len(pages) - pages_to_check_start, 3)
            
            for i in range(pages_to_check_end):
                # Indice inverso: -1, -2, -3
                idx = -1 - i
                page_content = pages[idx]
                is_content = self._classify_page_content(page_content, is_start=False)
                
                if is_content:
                    print(f"   ✅ Pagina finale {abs(idx)} identificata come CONTENUTO. Stop taglio finale.")
                    break
                else:
                    print(f"   ❌ Pagina finale {abs(idx)} identificata come NO-REQ (Admin/Footer). Sarà rimossa.")
                    end_index -= len(page_content)
        
        # 4. Applica taglio
        if start_index > 0 or end_index < len(text):
            return text[start_index:end_index]
            
        return text

    def _split_into_logical_pages(self, text: str) -> list[str]:
        """
        Divide il testo in segmenti che approssimano le pagine.
        """
        # Se ci sono caratteri Form Feed, usali
        if '\f' in text:
            return text.split('\f')
            
        # Altrimenti usa chunk di lunghezza fissa cercando newline vicini
        page_size = 3000
        pages = []
        current_pos = 0
        
        while current_pos < len(text):
            end_pos = min(current_pos + page_size, len(text))
            
            # Cerca un fine riga vicino al limite per non troncare frasi a metà
            if end_pos < len(text):
                next_newline = text.find('\n', end_pos)
                if next_newline != -1 and next_newline - end_pos < 500:
                    end_pos = next_newline + 1
            
            pages.append(text[current_pos:end_pos])
            current_pos = end_pos
            
        return pages

    def _classify_page_content(self, text_chunk: str, is_start: bool) -> bool:
        """
        Chiede all'LLM se il chunk è contenuto rilevante o metadati/indice.
        Returns: True se è contenuto, False se va scartato.
        """
        # Prendi solo i primi/ultimi caratteri del chunk per risparmiare token se molto lungo
        preview_text = text_chunk
        if len(preview_text) > 1500:
             preview_text = preview_text[:750] + "\n...\n" + preview_text[-750:]
             
        context_type = "PRIMA PAGINA/INIZIO" if is_start else "ULTIMA PAGINA/FINE"
        
        prompt = f"""
Sei un analista di conformità. Stai esaminando la {context_type} di un documento tecnico.
Devi decidere se questa pagina contiene REQUISITI DI CONFORMITÀ/CONTENUTO TECNICO oppure solo METADATI/INDICI/COPERTINE da ignorare.

TESTO PAGINA:
```
{preview_text}
```

Regole di decisione:
1. SCARTA (Ignora) se contiene solo: Titolo Documento, Autori, Loghi, Indice (Sommario), Tabelle Revisioni, Definizioni generiche, Pagine bianche, Note legali finali.
2. TIENI (Contenuto) se contiene: Introduzione al sistema, Scopo specifico, Normative di riferimento, Descrizione processi, Requisiti, Responsabilità attive.

Rispondi SOLO con una parola: "TIENI" o "SCARTA".
"""
        try:
            response = self.llm.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0, "num_predict": 100}
            )
            
            answer = response["message"]["content"].strip().upper()
            
            # Se la risposta contiene TIENI, salvalo
            if "TIENI" in answer:
                return True
            return False
            
        except Exception as e:
            print(f"❌ Errore classificazione pagina: {e}")
            # In caso di errore, per sicurezza manteniamo il contenuto (better safe than sorry)
            return True

