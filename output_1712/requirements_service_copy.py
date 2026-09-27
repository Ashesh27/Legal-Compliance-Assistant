import os
import glob
import json
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.prompts_config import EXTRACTION_SYSTEM_PROMPT, get_extraction_user_prompt
from llm_provider import llm_chat

# Load environment variables
load_dotenv()

def extract_json_from_text(text: str):
    """
    Estrae il primo blocco JSON valido da una stringa.
    Args:
        text (str): Testo da cui estrarre JSON.
    Returns:
        dict or list: JSON estratto o [] in caso di errore.
    """
    import json
    import re
    import logging
    logger = logging.getLogger(__name__)
    print(f"DEBUG JSON: Tentativo parsing da testo di {len(text)} caratteri")
    print(f"DEBUG JSON: Prime 200 chars: {text[:200]}...")
    array_match = re.search(r'(\[\s*{[\s\S]*?}\s*\])', text)
    if array_match:
        json_part = array_match.group(1)
        print("DEBUG JSON: Trovato pattern array JSON")
    else:
        obj_match = re.search(r'(\{[\s\S]*?\})', text)
        if obj_match:
            json_part = obj_match.group(1)
            print("DEBUG JSON: Trovato pattern object JSON")
        else:
            start = min([i for i in [text.find('['), text.find('{')] if i != -1], default=-1)
            if start != -1:
                json_part = text[start:]
                print(f"DEBUG JSON: Usando testo da posizione {start}")
            else:
                json_part = text
                print("DEBUG JSON: Usando tutto il testo")
    print(f"DEBUG JSON: JSON estratto ({len(json_part)} chars): {json_part[:200]}...")
    try:
        result = json.loads(json_part)
        print(f"DEBUG JSON: Parsing riuscito - tipo: {type(result)}, elementi: {len(result) if isinstance(result, (list, dict)) else 'N/A'}")
        return result
    except Exception as e:
        logger.error(f"Errore parsing JSON (estratto): {e}")
        print(f"DEBUG JSON: Errore parsing: {e}")
        return []

def parse_ollama_message(message):
    """
    Parsa il messaggio di risposta da Ollama ed estrae il JSON.
    """
    if isinstance(message, dict) and "content" in message:
        text = message["content"]
    elif hasattr(message, "content"):
        text = message.content
    else:
        text = message
    return extract_json_from_text(text)

def extract_requirements_from_text(text: str, chunk_num: int = 0) -> List[Dict[str, str]]:
    """
    Estrae requisiti direttamente dal testo senza passare per macro-temi.
    
    Args:
        text (str): Testo del chunk
        chunk_num (int): Numero del chunk per debug
    
    Returns:
        List[Dict[str, str]]: Lista di requisiti estratti
    """
    # Usa i prompt dal file di configurazione
    system_prompt = EXTRACTION_SYSTEM_PROMPT
    user_prompt = get_extraction_user_prompt(text)
    
    print(f"DEBUG: Estraendo requisiti dal chunk {chunk_num}")
    print(f"DEBUG: Lunghezza testo: {len(text)} caratteri")
    
    # Get model and settings from environment variables
    model_used = os.getenv("LLM_EXTRACTION_MODEL", "deepseek-r1:32b")
    temperature = float(os.getenv("LLM_EXTRACTION_TEMPERATURE", "0.0001"))
    
    try:
        # Use llm_provider instead of direct ollama call
        response = llm_chat(
            model=model_used,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            options={"temperature": temperature}
        )

            
        print (f"DEBUG: Model used: {model_used}")
        message = response.get("message", {})
        print(f"DEBUG: Messaggio completo Ollama: {message}")
        
        requirements = parse_ollama_message(message)
        print(f"DEBUG: Requirements parsed: {requirements}")
        
        if not requirements:
            print(f"WARNING: Nessun requisito estratto dal chunk {chunk_num}")
            return []
        
        # Validazione e pulizia dei requisiti
        validated_requirements = []
        for req in requirements:
            if isinstance(req, dict) and "requirement" in req:
                # Assicurati che ci sia anche audit_question
                if "audit_question" not in req:
                    req["audit_question"] = f"Viene rispettato il requisito: {req['requirement'][:100]}...?"
                
                # Aggiungi citazione e pagine se disponibili
                # Nota: queste verranno arricchite nel chiamante
                req["citation"] = "" 
                req["pages"] = []
                
                validated_requirements.append(req)
        
        print(f"DEBUG: Estratti {len(validated_requirements)} requisiti dal chunk {chunk_num}")
        
        return validated_requirements
        
    except Exception as e:
        print(f"ERROR: Errore nell'estrazione requisiti dal chunk {chunk_num}: {e}")
        return []

def detect_chunk_format(chunks_file_path: str) -> str:
    """
    Rileva il formato del file chunks (classico o dinamico).
    
    Args:
        chunks_file_path: Percorso del file chunks
        
    Returns:
        'dynamic' o 'classic'
    """
    try:
        with open(chunks_file_path, 'r', encoding='utf-8') as f:
            # Leggi le prime righe
            first_lines = ''.join([f.readline() for _ in range(10)])
            
        # Controlla se contiene i marker del formato dinamico
        if 'CHUNKING DINAMICO' in first_lines or 'CHUNK' in first_lines and 'SEZIONE:' in first_lines:
            return 'dynamic'
        else:
            return 'classic'
            
    except Exception as e:
        print(f"WARNING: Errore nel rilevare il formato: {e}, assumo formato classico")
        return 'classic'
def identify_primary_page_from_markers(chunk_text: str,
                                       requirement_index: int,
                                       total_requirements: int,
                                       start_page: int,
                                       end_page: int) -> list:
    """
    Assigns a requirement to a page using page-marker distribution.
    Does NOT rely on requirement text (LLM paraphrasing safe).

    Returns a smart page range [p-1, p, p+1] within section bounds.
    """

    # Extract page markers
    page_numbers = [int(m.group(1)) for m in re.finditer(r'\[PAGE (\d+)\]', chunk_text)]

    # If no markers → fallback to section middle
    if not page_numbers:
        mid = (start_page + end_page) // 2
        return [mid]

    # Deduplicate & sort
    page_numbers = sorted(set(page_numbers))

    # Map requirement index to page index
    page_idx = int(
        (requirement_index / max(total_requirements, 1)) * len(page_numbers)
    )
    page_idx = min(page_idx, len(page_numbers) - 1)

    primary_page = page_numbers[page_idx]

    # Build smart range
    pages = [primary_page - 1, primary_page, primary_page + 1]
    pages = [p for p in pages if start_page <= p <= end_page]

    return sorted(set(pages))



def process_dynamic_chunks_file(chunks_file_path: str) -> List[Dict[str, str]]:
    """
    Processa un file di chunks dinamici (formato nuovo).
    
    Args:
        chunks_file_path: Percorso del file chunks dinamici
        
    Returns:
        Lista di tutti i requisiti estratti
    """
    if not os.path.exists(chunks_file_path):
        print(f"ERROR: File {chunks_file_path} non trovato")
        return []
    
    print(f"Processando file dinamico: {chunks_file_path}")
    
    all_requirements = []
    chunk_num = 0
    
    try:
        with open(chunks_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Dividi in chunk usando il separatore
        chunks = content.split("=" * 80)
        
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or chunk.startswith('CHUNKING DINAMICO'):
                continue
            
            # Parse del chunk dinamico
            lines = chunk.split('\n')
            
            # Estrai metadata
            chunk_id = None
            section_title = None
            pages_range = None
            text_lines = []
            
            in_text = False
            
            for line in lines:
                if line.startswith('CHUNK '):
                    chunk_id = line.replace('CHUNK ', '').strip()
                elif line.startswith('SEZIONE:'):
                    section_title = line.replace('SEZIONE:', '').strip()
                elif line.startswith('PAGINE:'):
                    pages_range = line.replace('PAGINE:', '').strip()
                elif line.startswith('CARATTERI:') or line.startswith('PAROLE:'):
                    # Skip metadata
                    in_text = True  # Il testo inizia dopo questi metadata
                    continue
                elif in_text and line.strip():
                    # Ignora linee separatore
                    if set(line.strip()) <= {'=', '-'}:
                        continue
                    text_lines.append(line)
            
            if not text_lines:
                continue
            
            chunk_num += 1
            chunk_text = '\n'.join(text_lines).strip()
            
            if len(chunk_text) < 10:
                continue
            
            # Parse delle pagine
            current_pages = []
            start_page = None
            end_page = None
            
            if pages_range:
                try:
                    if '-' in pages_range:
                        start, end = pages_range.split('-')
                        start_page = int(start)
                        end_page = int(end)
                        current_pages = list(range(start_page, end_page + 1))
                    else:
                        start_page = end_page = int(pages_range)
                        current_pages = [start_page]
                except:
                    current_pages = []
                    start_page = end_page = 1
            else:
                start_page = end_page = 1
            
            print(f"Processando chunk dinamico {chunk_num} (Sezione: {section_title}): {len(chunk_text)} caratteri")
            
            # Estrai requisiti da questo chunk
            requirements = extract_requirements_from_text(chunk_text, chunk_num)
            
            # ===== NEW: Identify primary page using markers =====
            for req_index, req in enumerate(requirements):
                req['source_chunk'] = chunk_num
                req['requirement_index'] = req_index
                req['total_in_chunk'] = len(requirements)
                req['source_section'] = section_title or 'N/A'
                req['source_file'] = os.path.basename(chunks_file_path)
                req['all_chunk_pages'] = current_pages  # Keep all pages for reference
                
                # NEW: Identify primary page from [PAGE N] markers
                pages_range = identify_primary_page_from_markers(
                    chunk_text=chunk_text,
                    requirement_index=req_index,
                    total_requirements=len(requirements),
                    start_page=start_page or 1,
                    end_page=end_page or 1
                )


                req['pages'] = pages_range

                # Citazione dalla sezione
                clean_text_for_citation = re.sub(r'\[PAGE \d+\]\s*', '', chunk_text)

                first_sentence_match = re.match(r'([^.]{10,}?\.)', clean_text_for_citation)
                if first_sentence_match:
                    citation = first_sentence_match.group(1).strip()
                else:
                    citation = clean_text_for_citation[:100] + "..."
                req['citation'] = citation
            
            all_requirements.extend(requirements)
            
            print(f"Chunk dinamico {chunk_num}: estratti {len(requirements)} requisiti con pagine identificate")
        
    except Exception as e:
        print(f"ERROR: Errore nel processare il file dinamico {chunks_file_path}: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    print(f"TOTALE: estratti {len(all_requirements)} requisiti da {chunk_num} chunk dinamici")
    return all_requirements

def process_chunks_file(chunks_file_path: str) -> List[Dict[str, str]]:
    """
    Processa un file di chunks e estrae tutti i requisiti.
    Rileva automaticamente se è formato classico o dinamico.
    
    Args:
        chunks_file_path (str): Percorso del file chunks
    
    Returns:
        List[Dict[str, str]]: Lista di tutti i requisiti estratti
    """
    if not os.path.exists(chunks_file_path):
        print(f"ERROR: File {chunks_file_path} non trovato")
        return []
    
    # Rileva il formato
    chunk_format = detect_chunk_format(chunks_file_path)
    print(f"📋 Formato rilevato: {chunk_format}")
    
    # Usa il parser appropriato
    if chunk_format == 'dynamic':
        return process_dynamic_chunks_file(chunks_file_path)
    else:
        return process_classic_chunks_file(chunks_file_path)

def process_classic_chunks_file(chunks_file_path: str) -> List[Dict[str, str]]:
    """
    Processa un file di chunks in formato classico.
    
    Args:
        chunks_file_path (str): Percorso del file chunks
    
    Returns:
        List[Dict[str, str]]: Lista di tutti i requisiti estratti
    """
    if not os.path.exists(chunks_file_path):
        print(f"ERROR: File {chunks_file_path} non trovato")
        return []
    
    print(f"Processando file: {chunks_file_path}")
    
    all_requirements = []
    chunk_num = 0
    
    try:
        with open(chunks_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Dividi il contenuto in chunks basandoti sui separatori
        chunks = content.split("=" * 80)
        
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            
            chunk_num += 1
            
            # Estrai il testo del chunk (rimuovi HEADING: e TESTO:)
            lines = chunk.split('\n')
            text_lines = []
            current_pages = []
            
            for line in lines:
                if line.startswith('TESTO:'):
                    # Aggiungi il testo dopo "TESTO:"
                    text_lines.append(line[6:].strip())
                elif line.startswith('PAGINE:'):
                    # Parse pagine
                    try:
                        pages_str = line[7:].strip()
                        if pages_str:
                            current_pages = [int(p) for p in pages_str.split(',') if p.strip()]
                        else:
                            current_pages = []
                    except:
                        current_pages = []
                elif not line.startswith('HEADING:') and line.strip():
                    # Aggiungi altre righe che non sono heading
                    text_lines.append(line.strip())
            
            chunk_text = ' '.join(text_lines).strip()
            
            if len(chunk_text) < 10:  # Salta chunk troppo corti
                continue
            
            print(f"Processando chunk {chunk_num}: {len(chunk_text)} caratteri")
            
            # Estrai requisiti da questo chunk
            requirements = extract_requirements_from_text(chunk_text, chunk_num)
            
            # Aggiungi informazioni aggiuntive ai requisiti
            for req_index, req in enumerate(requirements):
                req['source_chunk'] = chunk_num
                req['requirement_index'] = req_index
                req['total_in_chunk'] = len(requirements)
                req['source_file'] = os.path.basename(chunks_file_path)
                req['pages'] = current_pages
                
                # Estrai citazione (prima frase significativa o primi 100 caratteri)
                # Cerca la prima frase che finisce con un punto
                first_sentence_match = re.match(r'([^.]{10,}?\.)', chunk_text)
                if first_sentence_match:
                    citation = first_sentence_match.group(1).strip()
                else:
                    citation = chunk_text[:100] + "..."
                
                req['citation'] = citation
            
            all_requirements.extend(requirements)
            
            print(f"Chunk {chunk_num}: estratti {len(requirements)} requisiti")
    
    except Exception as e:
        print(f"ERROR: Errore nel processare il file {chunks_file_path}: {e}")
        return []
    
    print(f"TOTALE: estratti {len(all_requirements)} requisiti da {chunk_num} chunks")
    return all_requirements

def save_requirements_to_file(requirements: List[Dict[str, str]], output_file_path: str):
    """
    Salva i requisiti in un file di testo formattato.
    
    Args:
        requirements: Lista di requisiti
        output_file_path: Percorso del file di output
    """
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"REQUISITI ESTRATTI\n")
            f.write(f"Totale requisiti: {len(requirements)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, req in enumerate(requirements, 1):
                f.write(f"REQUISITO {i}\n")
                f.write(f"File sorgente: {req.get('source_file', 'N/A')}\n")
                f.write(f"Chunk sorgente: {req.get('source_chunk', 'N/A')}\n")
                f.write("-" * 40 + "\n")
                f.write(f"REQUISITO: {req.get('requirement', 'N/A')}\n")
                
                # Aggiungi riferimento pagina e citazione
                pages = req.get('pages', [])
                citation = req.get('citation', '')
                if pages or citation:
                    pages_str = ",".join(map(str, pages)) if pages else "N/A"
                    f.write(f"REFERENZE: (pag {pages_str} \"{citation}\")\n")
                f.write(f"DOMANDA AUDIT: {req.get('audit_question', 'N/A')}\n")
                f.write("\n" + "=" * 80 + "\n\n")
        
        print(f"✅ Requisiti salvati in: {output_file_path}")
        
    except Exception as e:
        print(f"❌ Errore nel salvare i requisiti: {e}")

def process_chunks_folder(folder_path: str):
    """
    Processa tutti i file *_chunks.txt in una cartella.
    
    Args:
        folder_path (str): Percorso della cartella contenente i file chunks
    """
    if not os.path.exists(folder_path):
        print(f"❌ La cartella {folder_path} non esiste!")
        return
    
    # Trova tutti i file chunks
    chunks_files = glob.glob(os.path.join(folder_path, "*_chunks.txt"))
    
    if not chunks_files:
        print(f"❌ Nessun file *_chunks.txt trovato nella cartella {folder_path}")
        return
    
    print(f"📁 Trovati {len(chunks_files)} file chunks da processare")
    print("=" * 60)
    
    for i, chunks_file in enumerate(chunks_files, 1):
        print(f"\n🔄 Processando file {i}/{len(chunks_files)}: {os.path.basename(chunks_file)}")
        
        try:
            # Estrai requisiti dal file chunks
            requirements = process_chunks_file(chunks_file)
            
            if not requirements:
                print(f"⚠️  Nessun requisito estratto da {os.path.basename(chunks_file)}")
                continue
            
            # Genera nome file di output
            base_name = os.path.basename(chunks_file).replace("_chunks.txt", "")
            output_file = os.path.join(folder_path, f"{base_name}_requirements.txt")
            
            # Salva i requisiti
            save_requirements_to_file(requirements, output_file)
            
            print(f"✅ Completato: {len(requirements)} requisiti salvati")
            
        except Exception as e:
            print(f"❌ Errore nel processare {chunks_file}: {e}")
            continue
    
    print(f"\n🎉 Processamento completato per tutti i file chunks!")

if __name__ == "__main__":
    # Esempio di utilizzo per un singolo file
    requirements = process_chunks_file(r"C:\Users\ashesh.gupta\checkpoint1512\backend\output\req_UNI_PdR_125-2022_PDR100866103_dynamic_chunks.txt")
    
    if requirements:
        output_file = r"C:\Users\ashesh.gupta\checkpoint1512\backend\output\requirements\req_UNI_PdR_125-2022_PDR100866103_dynamic_req_distributiongpt.txt"
        save_requirements_to_file(requirements, output_file)
        print(f"Processamento completato: {len(requirements)} requisiti estratti")
    else:
        print("Nessun requisito estratto dal file")