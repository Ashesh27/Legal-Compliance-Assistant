"""
Script per il chunking gerarchico migliorato dei documenti.
Versione ottimizzata per riconoscere correttamente le sezioni.
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import spacy
from sentence_transformers import SentenceTransformer
import sys
# Aggiungi la directory parent al path per importare i moduli backend
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import numpy as np
from services.smart_content_filter import SmartContentFilter

class ImprovedDocumentChunker:
    def __init__(self, chunk_size=800, overlap=200, min_chunk_size=100):
        """
        Inizializza il chunker con parametri ottimizzati.
        
        Args:
            chunk_size: Dimensione target del chunk (default 800 caratteri)
            overlap: Sovrapposizione tra chunks (default 200 caratteri)
            min_chunk_size: Dimensione minima accettabile per un chunk
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
        
        # Carica modello spaCy per italiano
        try:
            self.nlp = spacy.load("it_core_news_sm")
            print("✅ Modello spaCy caricato")
        except:
            print("⚠️ spaCy non disponibile, uso metodo alternativo")
            self.nlp = None
            
        # Inizializza Smart Content Filter
        try:
            self.smart_filter = SmartContentFilter()
            print("✅ Smart Content Filter inizializzato")
        except Exception as e:
            print(f"⚠️ Impossibile inizializzare Smart Content Filter: {e}")
            self.smart_filter = None
    
    def load_document(self, file_path: str) -> str:
        """
        Carica un documento da file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"📄 Caricato: {os.path.basename(file_path)} ({len(content)} caratteri)")
            return content
        except Exception as e:
            print(f"❌ Errore nel caricare {file_path}: {e}")
            return ""
    
    def extract_sections_from_structured_doc(self, text: str) -> List[Dict[str, Any]]:
        """
        Estrae sezioni da documenti con struttura HEADING/TESTO.
        """
        sections = []
        current_section = None
        
        # Pattern per identificare le sezioni nel formato del documento
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Cerca pattern "HEADING: <titolo>"
            if line.startswith('HEADING:'):
                # Salva sezione precedente se esiste
                if current_section and len(current_section.get('content', '').strip()) > 20:
                    sections.append(current_section)
                
                # Estrai il titolo
                heading = line[8:].strip()  # Rimuove "HEADING:"
                
                # Cerca PAGINE:
                pages_info = "N/A"
                i += 1
                if i < len(lines) and lines[i].strip().startswith('PAGINE:'):
                    pages_info = lines[i][7:].strip()
                    i += 1
                
                # Cerca il contenuto dopo "TESTO:"
                content_lines = []
                
                # Cerca la riga TESTO
                while i < len(lines) and not lines[i].strip().startswith('TESTO:'):
                    i += 1
                
                if i < len(lines) and lines[i].strip().startswith('TESTO:'):
                    # Prima riga di contenuto (dopo TESTO:)
                    first_line = lines[i][6:].strip() if len(lines[i]) > 6 else ""
                    if first_line:
                        content_lines.append(first_line)
                    i += 1
                    
                    # Raccogli tutto il contenuto fino al prossimo separatore o HEADING
                    while i < len(lines):
                        if lines[i].strip() == '=' * 80 or lines[i].strip().startswith('HEADING:'):
                            break
                        content_lines.append(lines[i])
                        i += 1
                
                # Crea nuova sezione
                current_section = {
                    'title': heading if heading != 'NO_HEADING' else 'Sezione',
                    'content': '\n'.join(content_lines).strip(),
                    'level': self.determine_section_level(heading),
                    'start_line': i,
                    'pages': pages_info
                }
            else:
                i += 1
        
        # Aggiungi ultima sezione
        if current_section and len(current_section.get('content', '').strip()) > 20:
            sections.append(current_section)
        
        return sections
    
    def determine_section_level(self, title: str) -> int:
        """
        Determina il livello gerarchico basato sul pattern del titolo.
        """
        if not title or title == 'NO_HEADING':
            return 3
        
        # Pattern per numerazione gerarchica (es. "4.9.1.2.3")
        if re.match(r'^[\d.]+\s', title):
            dots = title.split(' ')[0].count('.')
            return min(dots + 1, 5)
        
        # Titoli principali (tutto maiuscolo, breve)
        if title.isupper() and len(title) < 30:
            return 1
        
        # Altri titoli
        return 2
    
    def identify_document_structure_smart(self, text: str) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
        """
        Identifica la struttura del documento in modo intelligente.
        Prima verifica se è un documento strutturato con HEADING/TESTO,
        altrimenti usa pattern classici.
        """
        # Verifica se il documento ha la struttura HEADING/TESTO
        if 'HEADING:' in text and 'TESTO:' in text:
            print("📋 Documento strutturato rilevato (formato HEADING/TESTO)")
            sections = self.extract_sections_from_structured_doc(text)
            page_markers = self.extract_page_markers(text)
            return sections, page_markers
        
        # Altrimenti usa il metodo originale migliorato
        print("📋 Documento non strutturato - uso pattern classici")
        return self.identify_document_structure_classic(text)
    
    def identify_document_structure_classic(self, text: str) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
        """
        Metodo classico per documenti senza struttura HEADING/TESTO.
        """
        page_markers = self.extract_page_markers(text)
        text = self.clean_index_patterns(text)
        
        sections = []
        
        # Pattern più specifici per titoli reali
        patterns = [
            # Numerazione gerarchica (es. "4.1 Titolo", "4.9.1.2 Titolo")
            (r'^([\d.]+)\s+([A-Z][^\n]{2,80})$', 'numbered'),
            # Titoli in maiuscolo (non troppo lunghi)
            (r'^([A-Z][A-Z\s]{3,40})$', 'caps'),
            # Titoli con due punti
            (r'^([A-Z][a-z]+(?:\s+[A-Za-z]+){0,5}):$', 'colon'),
        ]
        
        lines = text.split('\n')
        current_section = {
            'title': 'Introduzione',
            'level': 0,
            'content': [],
            'start_line': 0
        }
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Salta righe vuote o troppo lunghe
            if not line_stripped or len(line_stripped) > 100:
                if line_stripped:
                    current_section['content'].append(line)
                continue
            
            is_header = False
            
            for pattern, pattern_type in patterns:
                match = re.match(pattern, line_stripped)
                if match:
                    # Valida il titolo
                    if pattern_type == 'numbered' and len(match.groups()) > 1:
                        title_candidate = match.group(2).strip()
                        number = match.group(1)
                    else:
                        title_candidate = line_stripped.strip()
                        number = ""
                    
                    # Verifica validità del titolo
                    if self.is_valid_section_title(title_candidate):
                        # Salva sezione precedente
                        if current_section['content']:
                            current_section['content'] = '\n'.join(current_section['content'])
                            current_section['end_line'] = i - 1
                            if len(current_section['content']) > self.min_chunk_size:
                                sections.append(current_section)
                        
                        # Crea nuova sezione
                        full_title = f"{number} {title_candidate}".strip() if number else title_candidate
                        current_section = {
                            'title': full_title[:80],
                            'level': self.determine_hierarchy_level(line_stripped, pattern_type),
                            'type': pattern_type,
                            'content': [],
                            'start_line': i
                        }
                        is_header = True
                        break
            
            if not is_header and line_stripped:
                current_section['content'].append(line)
        
        # Aggiungi ultima sezione
        if current_section['content']:
            current_section['content'] = '\n'.join(current_section['content'])
            current_section['end_line'] = len(lines) - 1
            if len(current_section['content']) > self.min_chunk_size:
                sections.append(current_section)
        
        return sections, page_markers
    
    def extract_page_markers(self, text: str) -> Dict[int, int]:
        """
        Estrae i marcatori di pagina dal testo.
        """
        page_markers = {}
        lines = text.split('\n')
        current_page = 1
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Pattern per numeri di pagina isolati
            if re.match(r'^\s*\d{1,3}\s*$', line_stripped):
                try:
                    page_num = int(line_stripped)
                    if 1 <= page_num <= 500 and page_num >= current_page:
                        current_page = page_num
                        page_markers[i] = current_page
                except ValueError:
                    pass
            
            # Pattern per footer con pagina
            page_match = re.search(r'(?:pagina|pag\.?)\s*(\d+)', line_stripped, re.IGNORECASE)
            if page_match:
                try:
                    page_num = int(page_match.group(1))
                    if page_num >= current_page:
                        current_page = page_num
                        page_markers[i] = current_page
                except ValueError:
                    pass
        
        return page_markers
    
    def clean_index_patterns(self, text: str) -> str:
        """
        Rimuove pattern di indici e artefatti dal testo.
        """
        # Rimuove indici con molti punti
        text = re.sub(r'^[^.]+\.{3,}\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\.{5,}', '', text)
        
        # Rimuove numeri di pagina isolati
        text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)
        
        # Rimuove header/footer ricorrenti
        headers_to_remove = [
            'LUTECHSERVICES', 'Del:', 'Manuale', 'Codice documento',
            'Versione \d+', 'MRS-\d+', 'POL-\d+', 'PSQ-\d+'
        ]
        
        for header in headers_to_remove:
            text = re.sub(f'^\\s*{header}\\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        
        return text
    
    def is_valid_section_title(self, title: str) -> bool:
        """
        Valida se un titolo di sezione è significativo.
        """
        if not title or len(title.strip()) < 3:
            return False
        
        title_upper = title.strip().upper()
        
        # Blacklist di pattern non validi
        invalid_patterns = [
            r'^[A-Z]+SERVICES$',
            r'^DEL:?$',
            r'^[A-Z]{2,5}-?\d*$',
            r'^MANUALE$',
            r'^DOCUMENTO$',
            r'^CODICE$',
            r'^VERSIONE',
            r'^PAGINA',
            r'^\d+$',
            r'^[=\-_]{2,}$',
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, title_upper):
                return False
        
        # Deve contenere almeno qualche parola significativa
        words = re.findall(r'\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}\b', title)
        return len(words) >= 1
    
    def determine_hierarchy_level(self, title: str, pattern_type: str) -> int:
        """
        Determina il livello gerarchico di una sezione.
        """
        if pattern_type == 'numbered':
            # Conta i punti nella numerazione
            match = re.match(r'^([\d.]+)', title)
            if match:
                dots = match.group(1).count('.')
                return min(dots + 1, 5)
        elif pattern_type == 'caps':
            return 1
        elif pattern_type == 'colon':
            return 2
        else:
            return 3
    
    def create_hierarchical_chunks(self, text: str, preserve_structure: bool = True) -> List[Dict[str, Any]]:
        """
        Crea chunks gerarchici con contesto preservato.
        """
        chunks = []
        
        if preserve_structure:
            # Applica filtro intelligente se disponibile
            if self.smart_filter:
                print("🔍 Esecuzione Smart Content Filter...")
                original_len = len(text)
                text = self.smart_filter.analyze_and_trim(text)
                if len(text) < original_len:
                    print(f"✂️  Testo ridotto da {original_len} a {len(text)} caratteri")
            
            # Usa il metodo smart per identificare la struttura
            sections, page_markers = self.identify_document_structure_smart(text)
            
            print(f"📊 Identificate {len(sections)} sezioni nel documento")
            
            # Mostra le sezioni trovate per debug
            for idx, section in enumerate(sections[:10]):  # Mostra prime 10
                print(f"   Sezione {idx+1}: {section['title'][:50]} (livello {section['level']})")
            
            for section in sections:
                section_chunks = self.chunk_section_with_context(
                    section['content'],
                    section['title'],
                    section['level'],
                    section.get('start_line', 0),
                    page_markers,
                    section.get('pages', None)
                )
                chunks.extend(section_chunks)
        else:
            # Chunking semplice senza struttura
            page_markers = self.extract_page_markers(text)
            text = self.clean_index_patterns(text)
            chunks = self.simple_chunk_with_overlap(text, page_markers)
        
        # Filtra chunks non validi
        valid_chunks = [c for c in chunks if self.validate_chunk(c)]
        
        if len(chunks) != len(valid_chunks):
            print(f"⚠️  Filtrati {len(chunks) - len(valid_chunks)} chunks non validi")
        
        print(f"✂️  Creati {len(valid_chunks)} chunks validi")
        return valid_chunks
    
    def validate_chunk(self, chunk: Dict[str, Any]) -> bool:
        """
        Valida se un chunk è valido.
        """
        text = chunk.get('text', '')
        
        if not text or len(text.strip()) < self.min_chunk_size:
            return False
        
        # Verifica che non sia principalmente numeri e punti
        dots_and_nums = len(re.findall(r'[.\d]', text))
        total_chars = len(text)
        
        if total_chars > 0 and dots_and_nums / total_chars > 0.6:
            return False
        
        # Verifica che ci siano abbastanza parole reali
        words = re.findall(r'\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]{4,}\b', text)
        if len(words) < 10:
            return False
        
        return True
    
    def chunk_section_with_context(self, text: str, section_title: str, level: int,
                                  start_line: int = 0, page_markers: Dict[int, int] = None,
                                  pre_extracted_pages: str = None) -> List[Dict[str, Any]]:
        """
        Divide una sezione in chunks mantenendo il contesto.
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return []
        
        if page_markers is None:
            page_markers = {}
        
        chunks = []
        
        # Usa spaCy se disponibile per dividere in frasi
        if self.nlp:
            doc = self.nlp(text)
            sentences = [sent.text for sent in doc.sents]
        else:
            # Fallback: divisione semplice per punti
            sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = []
        current_size = 0
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            current_chunk.append(sentence)
            current_size += len(sentence) + 1
            
            # Crea chunk quando raggiunge la dimensione target
            if current_size >= self.chunk_size:
                chunk_text = ' '.join(current_chunk)
                
                # Contesto precedente (ultime 2 frasi del chunk precedente)
                prev_context = ""
                if i > 0:
                    prev_sentences = sentences[max(0, i - 2):i]
                    prev_context = ' '.join(prev_sentences)[-self.overlap:] if prev_sentences else ""
                
                # Contesto successivo (prossime 2 frasi)
                next_context = ""
                if i + 1 < len(sentences):
                    next_sentences = sentences[i + 1:min(i + 3, len(sentences))]
                    next_context = ' '.join(next_sentences)[:self.overlap] if next_sentences else ""
                
                chunks.append({
                    'id': f"{section_title[:30].replace(' ', '_')}_{len(chunks) + 1}",
                    'text': chunk_text,
                    'section': section_title,
                    'hierarchy_level': level,
                    'context_before': prev_context,
                    'context_after': next_context,
                    'full_text_with_context': f"{prev_context} {chunk_text} {next_context}".strip(),
                    'chunk_size': len(chunk_text),
                    'page_number': pre_extracted_pages if pre_extracted_pages else self.get_page_for_line(start_line + i, page_markers)
                })
                
                # Mantieni overlap
                overlap_sentences = max(1, int(len(current_chunk) * 0.2))
                current_chunk = current_chunk[-overlap_sentences:]
                current_size = sum(len(s) + 1 for s in current_chunk)
        
        # Aggiungi chunk rimanente
        if current_chunk and current_size >= self.min_chunk_size:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'id': f"{section_title[:30].replace(' ', '_')}_{len(chunks) + 1}",
                'text': chunk_text,
                'section': section_title,
                'hierarchy_level': level,
                'context_before': "",
                'context_after': "",
                'full_text_with_context': chunk_text,
                'chunk_size': len(chunk_text),
                'page_number': pre_extracted_pages if pre_extracted_pages else self.get_page_for_line(start_line + len(sentences), page_markers)
            })
        
        return chunks
    
    def simple_chunk_with_overlap(self, text: str, page_markers: Dict[int, int] = None) -> List[Dict[str, Any]]:
        """
        Chunking semplice con overlap per testi senza struttura chiara.
        """
        if page_markers is None:
            page_markers = {}
        
        chunks = []
        
        # Dividi in paragrafi o frasi
        if self.nlp:
            doc = self.nlp(text)
            sentences = [sent.text for sent in doc.sents]
        else:
            sentences = text.split('. ')
        
        current_chunk = []
        current_size = 0
        
        for i, sentence in enumerate(sentences):
            current_chunk.append(sentence)
            current_size += len(sentence)
            
            if current_size >= self.chunk_size:
                chunk_text = ' '.join(current_chunk)
                
                chunks.append({
                    'id': f"chunk_{len(chunks) + 1}",
                    'text': chunk_text[:self.chunk_size],
                    'section': 'Documento',
                    'hierarchy_level': 0,
                    'full_text_with_context': chunk_text,
                    'chunk_size': len(chunk_text[:self.chunk_size]),
                    'page_number': self.get_page_for_line(i * 2, page_markers) # Approssimazione per chunking semplice
                })
                
                # Sliding window
                while current_size > self.chunk_size - self.overlap and len(current_chunk) > 1:
                    removed = current_chunk.pop(0)
                    current_size -= len(removed)
        
        # Ultimo chunk
        if current_chunk and current_size >= self.min_chunk_size:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'id': f"chunk_{len(chunks) + 1}",
                'text': chunk_text,
                'section': 'Documento',
                'hierarchy_level': 0,
                'full_text_with_context': chunk_text,
                'chunk_size': len(chunk_text),
                'page_number': self.get_page_for_line(len(sentences) * 2, page_markers) # Approssimazione
            })
        
        return chunks
    
    def get_page_for_line(self, line_number: int, page_markers: Dict[int, int]) -> int:
        """
        Determina il numero di pagina per una data riga.
        """
        if not page_markers:
            return max(1, line_number // 50 + 1)
        
        current_page = 1
        for marker_line, page_num in sorted(page_markers.items()):
            if marker_line <= line_number:
                current_page = page_num
            else:
                break
        
        return current_page
    
    def process_multiple_documents(self, file_paths: List[str], output_dir: str = "chunks_output"):
        """
        Processa multipli documenti e salva i chunks.
        """
        Path(output_dir).mkdir(exist_ok=True)
        
        all_chunks = {}
        
        for file_path in file_paths:
            print(f"\n{'='*60}")
            print(f"📄 Processing: {os.path.basename(file_path)}")
            print('='*60)
            
            # Carica documento
            text = self.load_document(file_path)
            if not text:
                continue
            
            # Crea chunks
            chunks = self.create_hierarchical_chunks(text, preserve_structure=True)
            
            # Aggiungi metadati del file
            for chunk in chunks:
                chunk['source_file'] = os.path.basename(file_path)
                chunk['source_path'] = file_path
            
            all_chunks[os.path.basename(file_path)] = chunks
            
            # Salva chunks in JSON
            output_file = Path(output_dir) / f"{Path(file_path).stem}_chunks.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            
            # Salva versione testuale leggibile
            output_txt = Path(output_dir) / f"{Path(file_path).stem}_chunks.txt"
            with open(output_txt, 'w', encoding='utf-8') as f:
                f.write(f"CHUNKS - {os.path.basename(file_path)}\n")
                f.write("="*80 + "\n\n")
                
                for i, chunk in enumerate(chunks, 1):
                    f.write(f"CHUNK {i}\n")
                    f.write("-"*40 + "\n")
                    f.write(f"Sezione: {chunk['section']}\n")
                    f.write(f"Livello: {chunk['hierarchy_level']}\n")
                    f.write(f"Pagina: {chunk.get('page_number', 'N/A')}\n")
                    f.write(f"Dimensione: {chunk['chunk_size']} caratteri\n\n")
                    f.write(f"TESTO:\n{chunk['text']}\n")
                    
                    if chunk.get('context_before'):
                        f.write(f"\nCONTESTO PRECEDENTE:\n{chunk['context_before']}\n")
                    
                    if chunk.get('context_after'):
                        f.write(f"\nCONTESTO SUCCESSIVO:\n{chunk['context_after']}\n")
                    
                    f.write("\n" + "="*80 + "\n\n")
            
            print(f"✅ Salvati {len(chunks)} chunks in {output_file}")
        
        # Salva riepilogo
        summary_file = Path(output_dir) / "chunking_summary.json"
        summary = {
            'total_files': len(file_paths),
            'total_chunks': sum(len(chunks) for chunks in all_chunks.values()),
            'parameters': {
                'chunk_size': self.chunk_size,
                'overlap': self.overlap,
                'min_chunk_size': self.min_chunk_size
            },
            'files_processed': list(all_chunks.keys())
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n📊 RIEPILOGO:")
        print(f"   - File processati: {summary['total_files']}")
        print(f"   - Chunks totali creati: {summary['total_chunks']}")
        print(f"   - Output salvato in: {output_dir}/")
        
        return all_chunks

def main():
    """
    Esempio di utilizzo del chunker migliorato.
    """
    # Configurazione
    chunker = ImprovedDocumentChunker(
        chunk_size=800,
        overlap=200,
        min_chunk_size=100
    )
    
    # File da processare
    files_to_process = [
        "/home/srv_user/ai_doc/AI_compliance/BertTopic/Caso_1/MRS-000 v00 Manuale Sistema di Gestione Responsabilità Sociale_chunks.txt",
        "/home/srv_user/ai_doc/AI_compliance/BertTopic/Caso_1/PO-020 v17_chunks.txt",
        "/home/srv_user/ai_doc/AI_compliance/BertTopic/Caso_1/PSQ-025 v23_chunks.txt",
        "/home/srv_user/ai_doc/AI_compliance/BertTopic/Caso_1/PSQ-501-IT v03 - Politica Whistleblowing_chunks.txt",
        "/home/srv_user/ai_doc/AI_compliance/BertTopic/Caso_1/POL-960 v00 Politica per la Responsabilità Sociale_chunks.txt"
        
    ]
    
    # Directory di output
    output_dir = "/home/srv_user/ai_doc/AI_compliance/BertTopic/Caso_1/improved_chunks_output"
    
    # Processa tutti i documenti
    all_chunks = chunker.process_multiple_documents(files_to_process, output_dir)
    
    print("\n✅ Chunking completato con successo!")

if __name__ == "__main__":
    main()