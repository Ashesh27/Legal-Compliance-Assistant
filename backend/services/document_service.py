from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker, HierarchicalChunker
import re
import os
import glob
from docling_core.transforms.chunker.base import BaseChunk, BaseChunker, BaseMeta
from collections import defaultdict

def estimate_tokens(text):
    """Stima approssimativa del numero di token (1 token ≈ 4 caratteri)"""
    return len(text) // 4

def clean_text_artifacts(text):
    """
    Pulisce artefatti di estrazione PDF tipo 'sliding window' 
    (es. "S SC CO OP PO O" -> "SCOPO").
    """
    if not text or len(text) < 3:
        return text
        
    tokens = text.split()
    if not tokens:
        return ""
        
    output = []
    current_word = tokens[0]
    
    for i in range(1, len(tokens)):
        token = tokens[i]
        
        # Controlla overlap: se l'ultimo char della parola corrente 
        # coincide col primo del token successivo
        if current_word and token and current_word[-1] == token[0]:
            current_word += token[1:]
        else:
            output.append(current_word)
            current_word = token
            
    output.append(current_word)
    return " ".join(output)

def split_large_chunks(text, max_tokens=500, overlap_tokens=50):
    """
    Divide un testo lungo in chunk più piccoli rispettando il limite di token
    
    Args:
        text: testo da dividere
        max_tokens: numero massimo di token per chunk
        overlap_tokens: sovrapposizione tra chunk consecutivi
    
    Returns:
        lista di chunk di testo
    """
    # Converti token in caratteri approssimativi (1 token ≈ 4 caratteri)
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_chars
        
        if end >= len(text):
            # Ultimo chunk
            chunks.append(text[start:])
            break
        
        # Cerca un punto di interruzione naturale (frase, paragrafo)
        chunk_text = text[start:end]
        
        # Cerca la fine dell'ultima frase completa
        last_period = chunk_text.rfind('. ')
        last_newline = chunk_text.rfind('\n')
        
        # Usa il punto di interruzione più vicino alla fine
        break_point = max(last_period, last_newline)
        
        if break_point > start + max_chars // 2:  # Se il break point è ragionevole
            end = start + break_point + 1
        
        chunks.append(text[start:end])
        
        # Calcola il prossimo punto di inizio con sovrapposizione
        start = end - overlap_chars
        if start < 0:
            start = end
    
    return chunks

def load_chunks_from_file(file_path, min_chars=10, max_tokens=500, save_to_file=True, output_file=None):
    """Carica un documento e segmenta in chunk semantici con Docling"""
    doc = DocumentConverter().convert(file_path).document
    print(f"Documento caricato: {doc.origin.filename}")
    print(f"Numero totale di pagine: {len(doc.pages)}")
    print("-" * 50)

    chunker = HybridChunker()
    chunks = list(chunker.chunk(doc))
    
    print(f"Numero di chunk iniziali: {len(chunks)}")
    
    # Raggruppa i chunk per heading
    grouped_chunks = defaultdict(list)
    
    for chunk in chunks:
        # Filtra chunk troppo corti
        if len(chunk.text.strip()) < min_chars:
            continue
            
        # Usa il primo heading come chiave, o "NO_HEADING" se non presente
        heading_key = chunk.meta.headings[0] if chunk.meta.headings else "NO_HEADING"
        
        # Pulisce artefatti nel testo e nell'heading
        cleaned_text = clean_text_artifacts(chunk.text.strip())
        cleaned_heading = clean_text_artifacts(heading_key)
        
        # Estrai numeri di pagina dai doc_items
        page_numbers = set()
        if hasattr(chunk.meta, 'doc_items'):
            for item in chunk.meta.doc_items:
                if hasattr(item, 'prov') and item.prov:
                    for prov_item in item.prov:
                        if hasattr(prov_item, 'page_no'):
                            page_numbers.add(prov_item.page_no)
        
        grouped_chunks[cleaned_heading].append({
            'text': cleaned_text,
            'pages': list(page_numbers)
        })
    
    # Unisci i testi per ogni heading e gestisci il limite di token
    final_segments = []
    
    for heading, items in grouped_chunks.items():
        # Unisci TUTTI i testi con lo stesso heading in un unico chunk
        texts = [item['text'] for item in items]
        combined_text = " ".join(texts)
        
        # Raccogli tutte le pagine uniche
        all_pages = set()
        for item in items:
            all_pages.update(item['pages'])
        sorted_pages = sorted(list(all_pages))
        
        # Controlla se il chunk è troppo lungo
        if estimate_tokens(combined_text) > max_tokens:
            # Dividi il chunk lungo in parti più piccole
            sub_chunks = split_large_chunks(combined_text, max_tokens)
            
            # Unisci tutti i sub-chunk in un unico testo con separatori
            final_text = "\n\n".join(sub_chunks)
            
            final_segments.append({
                'heading': heading,  # Mantieni lo stesso heading originale
                'text': final_text,
                'chars': len(final_text),
                'tokens_estimate': estimate_tokens(final_text),
                'sub_chunks_count': len(sub_chunks),  # Info aggiuntiva
                'pages': sorted_pages
            })
        else:
            # Il chunk rientra nel limite
            final_segments.append({
                'heading': heading,
                'text': combined_text,
                'chars': len(combined_text),
                'tokens_estimate': estimate_tokens(combined_text),
                'sub_chunks_count': 1,
                'pages': sorted_pages
            })
    
    print(f"Segmenti finali raggruppati: {len(final_segments)}")
    print("=" * 50)
    
    # Visualizza i segmenti finali
    for i, segment in enumerate(final_segments, 1):
        print(f"\n--- SEGMENTO {i} ---")
        print(f"Heading: {segment['heading']}")
        print(f"Caratteri: {segment['chars']}")
        print(f"Token stimati: {segment['tokens_estimate']}")
        print(f"Sub-chunks: {segment['sub_chunks_count']}")
        print(f"Pagine: {segment['pages']}")
        print(f"Testo: {segment['text'][:200]}{'...' if len(segment['text']) > 200 else ''}")
        print("-" * 30)
    
    # Salva i risultati in un file TXT
    if save_to_file:
        if output_file is None:
            # Genera nome file automatico
            import os
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_file = f"{base_name}_segmenti_docling.txt"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(final_segments, 1):
                    f.write(f"HEADING: {segment['heading']}\n")
                    f.write(f"PAGINE: {','.join(map(str, segment['pages']))}\n")
                    f.write(f"TESTO: {segment['text']}\n")
                    f.write("\n" + "=" * 80 + "\n\n")
            
            print(f"\n✅ Risultati salvati in: {output_file}")
            
        except Exception as e:
            print(f"\n❌ Errore nel salvare il file: {e}")
    
    return final_segments

def process_folder(folder_path, min_chars=10, max_tokens=500, file_extensions=None):
    """
    Processa tutti i documenti PDF in una cartella
    
    Args:
        folder_path: percorso della cartella contenente i PDF
        min_chars: lunghezza minima caratteri per segmento
        max_tokens: limite massimo token per segmento (per evitare errori del modello)
        file_extensions: lista di estensioni da processare (default: ['pdf'])
    """
    if file_extensions is None:
        file_extensions = ['pdf']
    
    if not os.path.exists(folder_path):
        print(f"❌ La cartella {folder_path} non esiste!")
        return
    
    # Trova tutti i file con le estensioni specificate
    all_files = []
    for ext in file_extensions:
        pattern = os.path.join(folder_path, f"*.{ext}")
        all_files.extend(glob.glob(pattern))
    
    if not all_files:
        print(f"❌ Nessun file trovato nella cartella {folder_path} con estensioni {file_extensions}")
        return
    
    print(f"📁 Trovati {len(all_files)} file da processare")
    print("=" * 60)
    
    for i, file_path in enumerate(all_files, 1):
        print(f"\n🔄 Processando file {i}/{len(all_files)}: {os.path.basename(file_path)}")
        
        try:
            # Genera nome file di output
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_file = os.path.join(folder_path, f"{base_name}_chunks.txt")
            
            # Processa il documento
            segments = load_chunks_from_file(
                file_path=file_path,
                min_chars=min_chars,
                max_tokens=max_tokens,
                save_to_file=True,
                output_file=output_file
            )
            
            print(f"✅ Completato: {len(segments)} segmenti salvati")
            
        except Exception as e:
            print(f"❌ Errore nel processare {file_path}: {e}")
            continue
    
    print(f"\n🎉 Processamento completato per tutti i file nella cartella!")

def process_path(path, min_chars=10, max_tokens=500, file_extensions=None):
    """
    Funzione principale che processa un file singolo o una cartella
    
    Args:
        path: percorso di un file PDF o di una cartella contenente PDF
        min_chars: lunghezza minima caratteri per segmento
        max_tokens: limite massimo token per segmento
        file_extensions: lista di estensioni da processare (solo per cartelle)
    """
    if not os.path.exists(path):
        print(f"❌ Il percorso {path} non esiste!")
        return
    
    # Controlla se è un file o una cartella
    if os.path.isfile(path):
        # È un file singolo
        print(f"📄 Processando file singolo: {os.path.basename(path)}")
        print("=" * 60)
        
        try:
            # Genera nome file di output nella stessa cartella del file originale
            dir_path = os.path.dirname(path)
            base_name = os.path.splitext(os.path.basename(path))[0]
            output_file = os.path.join(dir_path, f"{base_name}_chunks.txt")
            
            # Processa il documento
            segments = load_chunks_from_file(
                file_path=path,
                min_chars=min_chars,
                max_tokens=max_tokens,
                save_to_file=True,
                output_file=output_file
            )
            
            print(f"\n✅ Processamento completato: {len(segments)} segmenti salvati")
            
        except Exception as e:
            print(f"❌ Errore nel processare il file: {e}")
    
    elif os.path.isdir(path):
        # È una cartella
        print(f"📁 Processando cartella: {path}")
        process_folder(path, min_chars, max_tokens, file_extensions)
    
    else:
        print(f"❌ Il percorso {path} non è né un file né una cartella valida!")

# ============================================
# ESEMPI DI UTILIZZO
# ============================================

# Esempio 1: Processa un SINGOLO FILE PDF
# process_path(
#     path="/home/user/documento.pdf",
#     min_chars=10,
#     max_tokens=400
# )

# Esempio 2: Processa TUTTI i PDF in una CARTELLA
# process_path(
#     path="/home/user/documenti/",
#     min_chars=10,
#     max_tokens=400,
#     file_extensions=['pdf', 'docx']  # Opzionale: specifica le estensioni
# )

# Esempio 3: Utilizzo diretto nel codice
if __name__ == "__main__":
    # Modifica questo percorso con il tuo file o cartella
    PATH = "/home/srv_user/ai_doc/AI_compliance/BertTopic/Analisi-Funzionale-Energy-01.pdf"  # Può essere file o cartella
    
    process_path(
        path=PATH,
        min_chars=10,
        max_tokens=400
    )