import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument

# Setup path per importare moduli locali
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from llm_provider import llm_chat
from config import LLM_EXTRACTION_MODEL, LLM_PROVIDER


class DynamicMacroSectionChunker:
    """
    Chunker dinamico che usa LLM per identificare le macrosezioni del documento
    e crea chunk completi per ogni sezione.
    """
    
    def __init__(self, pages_per_batch: int = 5):
        """
        Inizializza il chunker dinamico.
        
        Args:
            pages_per_batch: Numero di pagine da processare per volta con LLM
        """
        self.pages_per_batch = pages_per_batch
        self.converter = DocumentConverter()
        
    def extract_text_by_pages(self, file_path: str) -> Dict[int, str]:
        """
        Estrae il testo dal PDF organizzato per pagina.
        Tenta diversi metodi per ottenere una divisione in pagine affidabile.
        Include anche tabelle convertite in formato Markdown.
        
        Args:
            file_path: Percorso del file PDF
            
        Returns:
            Dizionario {numero_pagina: testo}
        """
        print(f"📄 Estraendo testo da: {file_path}")
        
        pages_text = {}
        tables_by_page = {}  # Store tables separately by page
        
        try:
            # Converti il documento
            result = self.converter.convert(file_path)
            doc: DoclingDocument = result.document
            
            # Extract tables first
            tables_by_page = self._extract_tables(doc)
            if tables_by_page:
                print(f"  📊 Trovate tabelle in {len(tables_by_page)} pagine")
            
            # 1. Tentativo: Export to dict (più strutturato e affidabile per Docling v2)
            try:
                doc_dict = doc.export_to_dict()
                
                # Docling v2 mette il testo in 'texts' o 'body'
                text_items = []
                if 'texts' in doc_dict:
                    text_items = doc_dict['texts']
                elif 'body' in doc_dict and 'children' in doc_dict['body']:
                     # Struttura alternativa
                     pass 
                
                if text_items:
                    print(f"  ℹ️ Trovati {len(text_items)} elementi di testo nel dizionario Docling")
                    for item in text_items:
                        text = item.get('text', '')
                        if not text:
                            continue
                        
                        # Cerca il numero di pagina nella provenance
                        page_no = 1
                        if 'prov' in item and item['prov']:
                             # prov è una lista di location, prendiamo la prima
                             page_no = item['prov'][0].get('page_no', 1)
                        elif 'orig' in item:
                             # struttura legacy
                             pass
                        
                        if page_no not in pages_text:
                            pages_text[page_no] = []
                        pages_text[page_no].append(text)
                    
                    # Unisci le liste di testo per ogni pagina
                    final_pages = {}
                    for p, lines in pages_text.items():
                        final_pages[p] = "\n".join(lines)
                    pages_text = final_pages
            except Exception as e:
                print(f"  ⚠️ Metodo dict fallito: {e}, passo al fallback Markdown")
                pages_text = {} # Reset

            # 2. Tentativo: Markdown con split su marker (Fallback)
            if not pages_text:
                print("  ℹ️ Uso fallback visuale (Markdown markers)")
                full_text = doc.export_to_markdown()
                
                lines = full_text.split('\n')
                current_page = 1
                current_text = []
                
                # Regex per intercettare i cambi pagina
                # Docling spesso usa <!-- image --> come separatore tra pagine se ci sono header/footer grafici
                page_marker_regex = re.compile(r'(^##\s+Page\s+(\d+))|(<!--\s*image\s*-->)')
                
                for line in lines:
                    match = page_marker_regex.search(line)
                    if match:
                        if current_text:
                            if current_page not in pages_text: pages_text[current_page] = ""
                            pages_text[current_page] += '\n'.join(current_text)
                            current_text = []
                        
                        if match.group(2):
                            current_page = int(match.group(2))
                        else:
                            # Se troviamo un marker grafico, assumiamo cambio pagina
                            # Ma attenzione a non incrementare troppo se ce ne sono tanti
                            current_page += 1
                    else:
                        current_text.append(line)
                
                if current_text:
                    if current_page not in pages_text: pages_text[current_page] = ""
                    pages_text[current_page] += '\n'.join(current_text)

            # 3. Fallback finale: Splitting sintetico se abbiamo 1 sola pagina gigante
            # (Spesso accade se il PDF non ha layer testo o Docling non trova split)
            if (len(pages_text) <= 1) and (sum(len(t) for t in pages_text.values()) > 5000):
                print("  ⚠️ Paginazione fallita, uso splitting sintetico (3000 chars/pag)")
                
                # Recupera tutto il testo
                all_text = ""
                for p in sorted(pages_text.keys()):
                    all_text += pages_text[p] + "\n"
                if not all_text: 
                    all_text = doc.export_to_markdown()
                
                pages_text = {}
                chars_per_page = 3000
                total_len = len(all_text)
                
                for i in range(0, total_len, chars_per_page):
                    page_num = (i // chars_per_page) + 1
                    pages_text[page_num] = all_text[i : i + chars_per_page]
            
            # 4. Append tables to each page's text
            for page_no, table_md in tables_by_page.items():
                if page_no in pages_text:
                    pages_text[page_no] += f"\n\n{table_md}"
                else:
                    pages_text[page_no] = table_md
            
            print(f"✅ Estratte {len(pages_text)} pagine (reali o stimate)")
            return pages_text
            
        except Exception as e:
            print(f"❌ Errore critico estrazione pagine: {e}")
            import traceback
            traceback.print_exc()
            return {1: "ERRORE ESTRAZIONE TESTO"}
    
    def _extract_tables(self, doc: DoclingDocument) -> Dict[int, str]:
        """
        Estrae le tabelle dal documento Docling e le converte in Markdown.
        
        Args:
            doc: DoclingDocument processato
            
        Returns:
            Dizionario {numero_pagina: tabella_markdown}
        """
        tables_by_page = {}
        
        try:
            doc_dict = doc.export_to_dict()
            
            # Docling stores tables in 'tables' key
            tables = doc_dict.get('tables', [])
            
            for table in tables:
                # Get page number from provenance
                page_no = 1
                if 'prov' in table and table['prov']:
                    page_no = table['prov'][0].get('page_no', 1)
                
                # Convert table to Markdown
                table_md = self._table_to_markdown(table)
                
                if table_md:
                    if page_no not in tables_by_page:
                        tables_by_page[page_no] = ""
                    tables_by_page[page_no] += f"\n\n**[TABELLA]**\n{table_md}\n"
                    
        except Exception as e:
            print(f"  ⚠️ Errore estrazione tabelle: {e}")
            
        return tables_by_page
    
    def _table_to_markdown(self, table: Dict[str, Any]) -> str:
        """
        Converte una tabella Docling in formato Markdown.
        
        Args:
            table: Dizionario tabella da Docling
            
        Returns:
            Stringa Markdown della tabella
        """
        try:
            # Docling table structure varies
            # Try to get the grid data
            data = table.get('data', {})
            
            # Check for 'grid' format (common in Docling v2)
            if 'grid' in data:
                grid = data['grid']
                if not grid:
                    return ""
                    
                md_lines = []
                
                # First row as header
                if grid:
                    header_row = grid[0]
                    header_cells = [str(cell.get('text', cell) if isinstance(cell, dict) else cell) for cell in header_row]
                    md_lines.append("| " + " | ".join(header_cells) + " |")
                    md_lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")
                    
                    # Data rows
                    for row in grid[1:]:
                        cells = [str(cell.get('text', cell) if isinstance(cell, dict) else cell) for cell in row]
                        # Ensure same number of columns
                        while len(cells) < len(header_cells):
                            cells.append("")
                        md_lines.append("| " + " | ".join(cells) + " |")
                
                return "\n".join(md_lines)
            
            # Try 'cells' format (alternative structure)
            elif 'cells' in data:
                cells = data['cells']
                if not cells:
                    return ""
                    
                # Build grid from cells
                max_row = max(c.get('row', 0) for c in cells) + 1
                max_col = max(c.get('col', 0) for c in cells) + 1
                
                grid = [["" for _ in range(max_col)] for _ in range(max_row)]
                
                for cell in cells:
                    r = cell.get('row', 0)
                    c = cell.get('col', 0)
                    text = cell.get('text', '')
                    if r < max_row and c < max_col:
                        grid[r][c] = str(text)
                
                md_lines = []
                if grid:
                    # Header
                    md_lines.append("| " + " | ".join(grid[0]) + " |")
                    md_lines.append("| " + " | ".join(["---"] * len(grid[0])) + " |")
                    # Data
                    for row in grid[1:]:
                        md_lines.append("| " + " | ".join(row) + " |")
                
                return "\n".join(md_lines)
            
            # Fallback: try to get raw text representation
            elif 'text' in table:
                return f"```\n{table['text']}\n```"
                
        except Exception as e:
            print(f"    ⚠️ Errore conversione tabella: {e}")
            
        return ""
    
    def identify_macro_sections_llm(self, pages_text: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Identifica le macrosezioni del documento usando LLM.
        """
        print(f"\n🔍 Identificando macrosezioni con LLM...")
        
        all_sections = []
        page_numbers = sorted(pages_text.keys())
        
        # 1. Identificazione grezza per batch
        for i in range(0, len(page_numbers), self.pages_per_batch):
            batch_pages = page_numbers[i:i + self.pages_per_batch]
            
            # Prepara contesto per LLM
            batch_text = ""
            for page_num in batch_pages:
                batch_text += f"\n\n--- PAGINA {page_num} ---\n"
                # Usa solo i primi 1000 caratteri per pagina per non confondere il modello con dettagli
                page_content = pages_text[page_num]
                if len(page_content) > 1500:
                    page_content = page_content[:1500] + "... [continua]"
                batch_text += page_content
            
            print(f"  📑 Analisi batch pagine {batch_pages[0]}-{batch_pages[-1]}")
            
            sections = self._call_llm_for_sections(batch_text, batch_pages[0], batch_pages[-1])
            all_sections.extend(sections)
        
        # 2. Refinement e Deduplica
        if not all_sections:
            return [{'title': 'DOCUMENTO COMPLETO', 'start_page': page_numbers[0], 'end_page': page_numbers[-1]}]

        # Ordina per pagina di inizio
        all_sections.sort(key=lambda x: x['start_page'])
        
        # Filtra duplicati e "sottosezioni" che potrebbero essere sfuggite
        final_sections = []
        seen_pages = set()
        
        for section in all_sections:
            # Se abbiamo già una sezione che inizia in questa pagina, teniamo la prima (di solito la più "macro")
            # Oppure se il titolo sembra molto simile a uno già visto
            if section['start_page'] in seen_pages:
                continue
            
            final_sections.append(section)
            seen_pages.add(section['start_page'])
            
        # 3. Calcolo end_page
        for i in range(len(final_sections) - 1):
            final_sections[i]['end_page'] = final_sections[i+1]['start_page'] - 1
            # Safety check
            if final_sections[i]['end_page'] < final_sections[i]['start_page']:
                 final_sections[i]['end_page'] = final_sections[i]['start_page']
                 
        # L'ultima sezione va fino alla fine
        final_sections[-1]['end_page'] = page_numbers[-1]
        
        print(f"\n✅ Identificate {len(final_sections)} macrosezioni definitive:")
        for s in final_sections:
            print(f"  🔹 {s['title']} (pagine {s['start_page']}-{s['end_page']})")
            
        return final_sections
    
    def _call_llm_for_sections(self, text: str, start_page: int, end_page: int) -> List[Dict[str, Any]]:
        """
        Invoca LLM per trovare le sezioni nel batch.
        """
        system_prompt = """Sei un esperto analisi documenti normativi (come SA8000, ISO).
Il tuo compito è identificare SOLO le MACROSEZIONI di PRIMO LIVELLO che INIZIANO in queste pagine.

DEFINIZIONE DI MACROSEZIONE:
1. Deve essere un capitolo principale di ALTO LIVELLO (es. "I. INTRODUZIONE", "IV. REQUISITI").
2. Di solito sono indicati con NUMERI ROMANI (I, II, III, IV) o titoli in MAIUSCOLO molto evidenti.
3. Se è presente un numero più titolo (es 1. Introduzione), ed è seguito da altri numeri come (1.1, 1.2), allora è una macrosezione.
4. Se è presente un numero più titolo (es 1. Introduzione), seguito da del testo, diviso magari in simboli (es. ▶), ed il numero successivo seguito da un altro titolo è maggiore con una differenza di +1, allora è una macrosezione.
5. NON deve essere una sottosezione.
6. Se il documento è un markdown, allora puoi affidarti anche ad i titoli per distinguere le macrosezioni, come gli h2 (##).

❌ DA IGNORARE ASSOLUTAMENTE:
- Qualsiasi sezione che inizia con NUMERI ARABI (1., 2., 9.) se fa parte di un capitolo Romano principale. Esempio: "9. SISTEMA DI GESTIONE" è una sottosezione di "IV. REQUISITI" -> DEVI IGNORARLA.
- Sottosezioni numerate (es. "4.1", "9.4").
- Punti elenco.

Rispondi SOLO se inizia un NUOVO MACRO-CAPITOLO (I, II, III...)."""

        user_prompt = f"""Analizza il testo (pag {start_page}-{end_page}).
Elenca SOLO le MACROSEZIONI che INIZIANO in questo batch.
Se il testo è la continuazione del capitolo precedente, restituisci una lista vuota.

TESTO:
{text}

Rispondi SOLO con JSON:
{{
  "sections": [
    {{ "title": "TITOLO ESATTO MACROSEZIONE", "start_page": {start_page} }}
  ]
}}
Se nessuna NUOVA macrosezione inizia qui: {{ "sections": [] }}
"""

        try:
            response = llm_chat(
                model=LLM_EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={
                    "temperature": 0.0,
                    "num_predict": 168384
                },
                provider=LLM_PROVIDER
            )
            
            content = response['message']['content'].strip()
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'^```\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            
            result = json.loads(content)
            sections = []
            
            for s in result.get('sections', []):
                if 'title' in s:
                    # Validazione extra: il titolo deve sembrare una macrosezione
                    # Se inizia con numeri tipo "1.2" o "9.4", probabilmente è una sottosezione, la scartiamo
                    title = s['title'].strip()
                    if re.match(r'^\d+\.\d+', title):
                         print(f"  ⚠️ Scartata sottosezione: {title}")
                         continue
                         
                    page = s.get('start_page', start_page)
                    if page < start_page: page = start_page
                    if page > end_page: page = end_page
                    
                    sections.append({
                        'title': title,
                        'start_page': page
                    })
            return sections
            
        except Exception as e:
            print(f"  ⚠️ Errore LLM batch {start_page}-{end_page}: {e}")
            return []



    def extract_section_chunks(self, file_path: str, sections: List[Dict[str, Any]], 
                               pages_text: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Crea i chunk fisici unendo il testo delle pagine.
        """
        print(f"\n📦 Creando chunk per macrosezioni...")
        chunks = []
        
        for i, section in enumerate(sections):
            start = section['start_page']
            end = section['end_page']
            
        # Colleziona testo CON MARKER DI PAGINA
            chunk_text = []
            for p in range(start, end + 1):
                if p in pages_text:
                    # Inserisce marker di pagina prima del testo per tracciabilità
                    chunk_text.append(f"[PAGE:{p}]")
                    chunk_text.append(pages_text[p])
            
            full_text = "\n\n".join(chunk_text).strip()
            
            # Se vuoto, skip
            if not full_text:
                print(f"  ⚠️ Sezione vuota: {section['title']}")
                continue
                
            chunk = {
                'chunk_id': i,
                'section_title': section['title'],
                'start_page': start,
                'end_page': end,
                'text': full_text,
                'char_count': len(full_text),
                'word_count': len(full_text.split())
            }
            chunks.append(chunk)
            print(f"  ✅ Chunk {i}: '{section['title']}' ({chunk['char_count']} chars)")
            
        return chunks

    def process_document(self, file_path: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Main entry point.
        """
        print(f"\n{'='*80}")
        print(f"🚀 CHUNKING DINAMICO V2 - {os.path.basename(file_path)}")
        print(f"{'='*80}\n")
        
        # Check if it's a Markdown file - use dedicated parser
        if file_path.lower().endswith('.md'):
            print("📝 Rilevato file Markdown - uso parser dedicato per headings")
            return self._process_markdown_file(file_path, output_dir)
        
        # 1. Pagine (for PDFs)
        pages_text = self.extract_text_by_pages(file_path)
        if not pages_text:
            raise ValueError("Impossibile estrarre testo")
            
        # 2. Sezioni
        sections = self.identify_macro_sections_llm(pages_text)
        
        # 3. Chunks
        chunks = self.extract_section_chunks(file_path, sections, pages_text)
        
        # 4. Salva
        if output_dir:
            self._save_results(file_path, chunks, sections, output_dir)
            
        return {
            'file': os.path.basename(file_path),
            'total_pages': len(pages_text),
            'total_sections': len(sections),
            'total_chunks': len(chunks),
            'chunks': chunks
        }
    
    def _process_markdown_file(self, file_path: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Process Markdown files by parsing ## headings directly.
        Much more reliable than using Docling/LLM for MD files.
        
        Args:
            file_path: Path to .md file
            output_dir: Optional output directory
            
        Returns:
            Dict with chunks
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Find all ## headings (H2 sections)
        sections = []
        current_section = None
        current_text = []
        
        for i, line in enumerate(lines):
            # Match ## headings (H2)
            if line.startswith('## '):
                # Save previous section
                if current_section is not None:
                    sections.append({
                        'title': current_section,
                        'text': '\n'.join(current_text).strip(),
                        'line_start': sections[-1]['line_end'] + 1 if sections else 0
                    })
                    if sections:
                        sections[-1]['line_end'] = i - 1
                
                current_section = line[3:].strip()
                current_text = []
            else:
                current_text.append(line)
        
        # Don't forget the last section
        if current_section is not None:
            sections.append({
                'title': current_section,
                'text': '\n'.join(current_text).strip(),
                'line_start': sections[-1]['line_end'] + 1 if len(sections) > 0 else 0,
                'line_end': len(lines) - 1
            })
        
        # If no ## headings found, try # headings (H1)
        if not sections:
            print("  ⚠️ Nessun ## trovato, provo con # headings")
            current_section = None
            current_text = []
            
            for i, line in enumerate(lines):
                if line.startswith('# ') and not line.startswith('##'):
                    if current_section is not None:
                        sections.append({
                            'title': current_section,
                            'text': '\n'.join(current_text).strip()
                        })
                    current_section = line[2:].strip()
                    current_text = []
                else:
                    current_text.append(line)
            
            if current_section is not None:
                sections.append({
                    'title': current_section,
                    'text': '\n'.join(current_text).strip()
                })
        
        # If still nothing found, create single chunk
        if not sections:
            print("  ⚠️ Nessun heading trovato, creo chunk unico")
            sections = [{
                'title': 'DOCUMENTO COMPLETO',
                'text': content
            }]
        
        # Build chunks with SECTION markers for traceability
        chunks = []
        for i, section in enumerate(sections):
            if not section['text']:
                continue
            
            # Inserisce marker di sezione prima del testo per tracciabilità
            section_title = section['title']
            text_with_marker = f"[SECTION:{section_title}]\n{section['text']}"
                
            chunk = {
                'chunk_id': i,
                'section_title': section_title,
                'start_page': 1,  # MD files don't have pages
                'end_page': 1,
                'text': text_with_marker,
                'char_count': len(section['text']),  # Original text length
                'word_count': len(section['text'].split())
            }
            chunks.append(chunk)
            print(f"  ✅ Chunk {i}: '{section_title}' ({chunk['char_count']} chars)")
        
        print(f"\n✅ Markdown: trovate {len(chunks)} sezioni")
        
        # Save if needed
        if output_dir:
            self._save_results(file_path, chunks, sections, output_dir)
        
        return {
            'file': os.path.basename(file_path),
            'total_pages': 1,
            'total_sections': len(sections),
            'total_chunks': len(chunks),
            'chunks': chunks
        }

    def _save_results(self, file_path: str, chunks: List[Dict[str, Any]], 
                      sections: List[Dict[str, Any]], output_dir: str):
        """
        Salvataggio su file JSON e TXT compatibile.
        """
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # JSON Chunk
        json_path = os.path.join(output_dir, f"{base_name}_dynamic_chunks.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
            
        # TXT Chunk (Formato per requirements_service)
        txt_path = os.path.join(output_dir, f"{base_name}_dynamic_chunks.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"CHUNKING DINAMICO - {os.path.basename(file_path)}\n")
            f.write(f"{'='*80}\n\n")
            for c in chunks:
                f.write(f"{'='*80}\n")
                f.write(f"CHUNK {c['chunk_id']}\n")
                f.write(f"SEZIONE: {c['section_title']}\n")
                f.write(f"PAGINE: {c['start_page']}-{c['end_page']}\n")
                f.write(f"CARATTERI: {c['char_count']}\n")
                f.write(f"PAROLE: {c['word_count']}\n")
                f.write(f"{'-'*80}\n\n")
                f.write(c['text'])
                f.write("\n\n")
                
        # Metadata
        meta_path = os.path.join(output_dir, f"{base_name}_dynamic_metadata.json")
        meta = {
            'file': os.path.basename(file_path),
            'method': 'dynamic_v2',
            'sections': sections
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
            
        print(f"  💾 Risultati salvati in {output_dir}")

