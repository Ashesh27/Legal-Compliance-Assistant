import os
import glob
import json
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts_config import EXTRACTION_SYSTEM_PROMPT, get_extraction_user_prompt
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
                
                validated_requirements.append(req)
        
        print(f"DEBUG: Estratti {len(validated_requirements)} requisiti dal chunk {chunk_num}")
        
        return validated_requirements
        
    except Exception as e:
        print(f"ERROR: Errore nell'estrazione requisiti dal chunk {chunk_num}: {e}")
        return []

def process_chunks_file(chunks_file_path: str) -> List[Dict[str, str]]:
    """
    Processa un file di chunks e estrae tutti i requisiti.
    
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
            
            for line in lines:
                if line.startswith('TESTO:'):
                    # Aggiungi il testo dopo "TESTO:"
                    text_lines.append(line[6:].strip())
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
            for req in requirements:
                req['source_chunk'] = chunk_num
                req['source_file'] = os.path.basename(chunks_file_path)
            
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
    requirements = process_chunks_file("/home/srv_user/ai_doc/AI_compliance/BertTopic/Analisi-Funzionale-Energy-01_chunks.txt")
    
    if requirements:
        output_file = "/home/srv_user/ai_doc/AI_compliance/BertTopic/Analisi-Funzionale-Energy-01_requirements.txt"
        save_requirements_to_file(requirements, output_file)
        print(f"Processamento completato: {len(requirements)} requisiti estratti")
    else:
        print("Nessun requisito estratto dal file")
