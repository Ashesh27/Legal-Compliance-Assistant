import os
import sys
import json
import time
import hashlib
import logging
import shelve
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import markdown
from tqdm import tqdm
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Conditional imports with fallbacks
try:
    from weasyprint import HTML, CSS
    PDF_ENGINE = "weasyprint"
except (ImportError, OSError):
    from xhtml2pdf import pisa
    PDF_ENGINE = "xhtml2pdf"
    logging.warning("WeasyPrint not found, falling back to xhtml2pdf")

# Setup path for local imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from scripts.chunking_dynamic import DynamicMacroSectionChunker
from llm_provider import llm_chat
from config import LLM_EXTRACTION_MODEL, LLM_PROVIDER

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

def setup_logging(log_level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """Configure structured logging with optional file output."""
    logger = logging.getLogger("AnnexMerger")
    logger.setLevel(log_level)
    logger.handlers.clear()
    
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ChunkMatch:
    """Represents a matched annex chunk with similarity score."""
    chunk: Dict[str, Any]
    similarity: float
    
    def __repr__(self) -> str:
        return f"ChunkMatch(title='{self.chunk.get('section_title', 'N/A')}', sim={self.similarity:.3f})"

@dataclass
class MergeResult:
    """Result of a single chunk merge operation."""
    section_title: str
    original_text: str
    merged_text: str
    annex_matches: List[ChunkMatch]
    was_modified: bool
    cache_hit: bool = False
    processing_time: float = 0.0

@dataclass
class MergeJobStats:
    """Statistics for the entire merge job."""
    total_chunks: int = 0
    modified_chunks: int = 0
    cache_hits: int = 0
    total_annex_matches: int = 0
    total_processing_time: float = 0.0
    llm_calls: int = 0

# =============================================================================
# ITALIAN STOPWORDS
# =============================================================================

ITALIAN_STOPWORDS = frozenset([
    'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una', 'di', 'a', 'da', 
    'in', 'con', 'su', 'per', 'tra', 'fra', 'e', 'o', 'ma', 'che', 'non', 
    'è', 'sono', 'sia', 'essere', 'avere', 'ha', 'hanno', 'questo', 'questa',
    'questi', 'queste', 'quello', 'quella', 'quelli', 'quelle', 'come', 'dove',
    'quando', 'perché', 'se', 'più', 'anche', 'solo', 'proprio', 'tutto',
    'tutti', 'ogni', 'altro', 'altri', 'altra', 'altre', 'stesso', 'stessa',
    'nel', 'nella', 'nei', 'nelle', 'del', 'della', 'dei', 'delle', 'dal',
    'dalla', 'dai', 'dalle', 'sul', 'sulla', 'sui', 'sulle', 'al', 'alla',
    'ai', 'alle', 'cui', 'chi', 'cosa', 'quale', 'quali', 'quanto', 'quanta',
    'quanti', 'quante', 'molto', 'poco', 'tanto', 'troppo', 'già', 'ancora',
    'sempre', 'mai', 'ora', 'poi', 'prima', 'dopo', 'sopra', 'sotto', 'dentro',
    'fuori', 'così', 'quindi', 'però', 'infatti', 'inoltre', 'oppure', 'ovvero',
    'dunque', 'perciò', 'pertanto', 'tuttavia', 'comunque', 'anzi', 'cioè'
])

# =============================================================================
# LLM CACHE
# =============================================================================

class LLMCache:
    """
    Persistent cache for LLM responses using shelve.
    Avoids redundant API calls for identical content.
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_path = str(self.cache_dir / "llm_cache")
        self._hits = 0
        self._misses = 0
    
    def _compute_key(self, main_text: str, annex_text: str) -> str:
        """Generate deterministic hash key for content pair."""
        combined = f"{main_text}||SEPARATOR||{annex_text}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()[:32]
    
    def get(self, main_text: str, annex_text: str) -> Optional[str]:
        """Retrieve cached response if available."""
        key = self._compute_key(main_text, annex_text)
        try:
            with shelve.open(self.cache_path) as cache:
                if key in cache:
                    self._hits += 1
                    return cache[key]
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        self._misses += 1
        return None
    
    def set(self, main_text: str, annex_text: str, response: str) -> None:
        """Store response in cache."""
        key = self._compute_key(main_text, annex_text)
        try:
            with shelve.open(self.cache_path) as cache:
                cache[key] = response
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    @property
    def stats(self) -> Dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}
    
    def clear(self) -> None:
        """Clear all cached entries."""
        try:
            with shelve.open(self.cache_path) as cache:
                cache.clear()
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")

# =============================================================================
# SEMANTIC RETRIEVER
# =============================================================================

class SemanticRetriever:
    """
    TF-IDF based semantic retrieval for finding relevant annex chunks.
    More robust than simple keyword matching.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.10,
        max_results: int = 5,
        ngram_range: Tuple[int, int] = (1, 2)
    ):
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results
        self.ngram_range = ngram_range
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._annex_vectors = None
        self._annex_chunks: List[Dict] = []
    
    def index_annexes(self, annex_chunks: List[Dict]) -> None:
        """
        Pre-compute TF-IDF vectors for all annex chunks.
        Call once before querying.
        """
        if not annex_chunks:
            logger.warning("No annex chunks to index")
            return
        
        self._annex_chunks = annex_chunks
        texts = [self._preprocess(chunk['text']) for chunk in annex_chunks]
        
        self._vectorizer = TfidfVectorizer(
            stop_words=list(ITALIAN_STOPWORDS),
            ngram_range=self.ngram_range,
            max_df=0.95,  # Ignore terms in >95% of docs
            min_df=1,
            sublinear_tf=True  # Apply log scaling to TF
        )
        
        self._annex_vectors = self._vectorizer.fit_transform(texts)
        logger.info(f"Indexed {len(annex_chunks)} annex chunks with {self._annex_vectors.shape[1]} features")
    
    def _preprocess(self, text: str) -> str:
        """Basic text preprocessing."""
        # Lowercase and normalize whitespace
        text = ' '.join(text.lower().split())
        return text
    
    def find_relevant(self, main_chunk: Dict) -> List[ChunkMatch]:
        """
        Find annex chunks semantically similar to the main chunk.
        Returns sorted list of ChunkMatch objects.
        """
        if self._vectorizer is None or self._annex_vectors is None:
            return []
        
        # Transform query
        query_text = self._preprocess(main_chunk['text'])
        query_vector = self._vectorizer.transform([query_text])
        
        # Compute similarities
        similarities = cosine_similarity(query_vector, self._annex_vectors).flatten()
        
        # Filter and sort
        matches = []
        for idx, sim in enumerate(similarities):
            if sim >= self.similarity_threshold:
                matches.append(ChunkMatch(
                    chunk=self._annex_chunks[idx],
                    similarity=float(sim)
                ))
        
        # Sort by similarity descending, limit results
        matches.sort(key=lambda x: x.similarity, reverse=True)
        return matches[:self.max_results]

# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

SYSTEM_PROMPT = """Sei un esperto redattore tecnico legislativo italiano.
Il tuo compito è integrare precisazioni, allegati (annex) o FAQ all'interno di un testo normativo principale.

═══════════════════════════════════════════════════════════════════════════════
REGOLE INDEROGABILI:
═══════════════════════════════════════════════════════════════════════════════

1. **STRUTTURA**: Mantieni ESATTAMENTE la struttura, l'ordine e lo stile del testo principale.

2. **INTEGRAZIONE SELETTIVA**: Aggiungi SOLO informazioni dall'annex che sono:
   - NUOVE (non già presenti nel testo principale)
   - RILEVANTI (pertinenti alla sezione specifica)
   - UTILI (chiariscono, precisano o completano il contenuto)

3. **FLUIDITÀ**: Le integrazioni devono sembrare scritte originariamente nel documento.
   NON usare frasi come "come specificato nell'allegato" o "secondo le FAQ".

4. **NESSUN META-CONTENUTO**: 
   - NO introduzioni ("Certamente, ecco...")
   - NO conclusioni ("Spero che questo...")
   - NO riferimenti all'allegato come fonte esterna

5. **PRESERVAZIONE**: Se l'annex non contiene nulla di rilevante per questa sezione,
   restituisci il testo principale IDENTICO, senza modifiche.

6. **OUTPUT**: Restituisci SOLO il testo risultante in formato Markdown pulito.

7. **INDIVIDUAZIONE TITOLI** : 
   - Deve essere un capitolo principale di ALTO LIVELLO (es. "I. INTRODUZIONE", "IV. REQUISITI").
   - Di solito sono indicati con NUMERI ROMANI (I, II, III, IV) o titoli in MAIUSCOLO molto evidenti.
   - Se è presente un numero più titolo (es 1. Introduzione), ed è seguito da altri numeri come (1.1, 1.2), allora è un titolo.
   - Se è presente un numero più titolo (es 1. Introduzione), seguito da del testo, diviso magari in simboli (es. ▶), ed il numero successivo seguito da un altro titolo è maggiore con una differenza di +1, allora è un titolo.
 """

FEW_SHOT_EXAMPLES = """
═══════════════════════════════════════════════════════════════════════════════
ESEMPI:
═══════════════════════════════════════════════════════════════════════════════

### ESEMPIO 1: Integrazione necessaria

TESTO PRINCIPALE:
"I soggetti obbligati devono presentare la documentazione entro 30 giorni."

ANNEX:
"FAQ 12: La documentazione deve essere presentata in formato PDF/A firmato digitalmente. 
Sono accettate anche PEC con firma qualificata."

OUTPUT CORRETTO:
"I soggetti obbligati devono presentare la documentazione entro 30 giorni in formato PDF/A 
firmato digitalmente. Sono accettate anche trasmissioni via PEC con firma qualificata."

---

### ESEMPIO 2: Annex non rilevante

TESTO PRINCIPALE:
"Le sanzioni per inadempimento sono determinate ai sensi dell'art. 45."

ANNEX:
"FAQ 8: Per le modalità di accreditamento, consultare la sezione dedicata del portale."

OUTPUT CORRETTO:
"Le sanzioni per inadempimento sono determinate ai sensi dell'art. 45."

(L'annex parla di accreditamento, non pertinente alle sanzioni → testo invariato)
"""

USER_PROMPT_TEMPLATE = """
═══════════════════════════════════════════════════════════════════════════════
TESTO PRINCIPALE
Sezione: {section_title}
═══════════════════════════════════════════════════════════════════════════════

{main_text}

═══════════════════════════════════════════════════════════════════════════════
CONTENUTI ANNEX/FAQ POTENZIALMENTE RILEVANTI
(Similarità semantica rilevata)
═══════════════════════════════════════════════════════════════════════════════

{annex_content}

═══════════════════════════════════════════════════════════════════════════════
COMPITO
═══════════════════════════════════════════════════════════════════════════════

Riscrivi il Testo Principale integrando le informazioni dall'Annex SOLO SE:
- Aggiungono dettagli nuovi e pertinenti a QUESTA specifica sezione
- Non sono già implicite o presenti nel testo

Se nessuna informazione dell'annex è rilevante per questa sezione, restituisci 
il Testo Principale ESATTAMENTE com'è, senza alcuna modifica.

OUTPUT (solo il testo, nient'altro):"""

# =============================================================================
# PDF GENERATOR
# =============================================================================

class PDFGenerator:
    """Handles Markdown to PDF conversion with professional styling."""
    
    CSS_STYLES = """
    @page {
        size: A4;
        margin: 2.5cm 2cm;
        @top-center { content: "Documento Rielaborato"; font-size: 9pt; color: #666; }
        @bottom-center { content: "Pagina " counter(page) " di " counter(pages); font-size: 9pt; color: #666; }
    }
    
    body {
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #1a1a1a;
        text-align: justify;
        hyphens: auto;
    }
    
    h1 {
        color: #1a365d;
        font-size: 22pt;
        font-weight: 700;
        border-bottom: 3px solid #2c5282;
        padding-bottom: 12px;
        margin-top: 0;
        margin-bottom: 24px;
        page-break-after: avoid;
    }
    
    h2 {
        color: #2c5282;
        font-size: 16pt;
        font-weight: 600;
        margin-top: 28px;
        margin-bottom: 14px;
        padding-left: 12px;
        border-left: 4px solid #4299e1;
        page-break-after: avoid;
    }
    
    h3 {
        color: #2d3748;
        font-size: 13pt;
        font-weight: 600;
        margin-top: 20px;
        margin-bottom: 10px;
        page-break-after: avoid;
    }
    
    p {
        margin-bottom: 12px;
        orphans: 3;
        widows: 3;
    }
    
    ul, ol {
        margin-left: 20px;
        margin-bottom: 12px;
    }
    
    li {
        margin-bottom: 6px;
    }
    
    code {
        background-color: #f7fafc;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 10pt;
        color: #c53030;
    }
    
    pre {
        background-color: #f7fafc;
        padding: 16px;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
        overflow-x: auto;
        font-size: 9pt;
    }
    
    blockquote {
        border-left: 4px solid #cbd5e0;
        margin: 16px 0;
        padding: 12px 20px;
        background-color: #f7fafc;
        font-style: italic;
        color: #4a5568;
    }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;
        font-size: 10pt;
    }
    
    th, td {
        border: 1px solid #e2e8f0;
        padding: 10px 12px;
        text-align: left;
    }
    
    th {
        background-color: #edf2f7;
        font-weight: 600;
        color: #2d3748;
    }
    
    tr:nth-child(even) {
        background-color: #f7fafc;
    }
    
    a {
        color: #2b6cb0;
        text-decoration: none;
    }
    
    a:hover {
        text-decoration: underline;
    }
    
    .section-break {
        page-break-before: always;
    }
    """
    
    def __init__(self):
        self.engine = PDF_ENGINE
        logger.info(f"PDF Engine: {self.engine}")
    
    def convert(self, md_content: str, output_path: str) -> bool:
        """Convert Markdown to PDF."""
        # Convert MD to HTML with extensions
        html_content = markdown.markdown(
            md_content,
            extensions=[
                'tables',
                'fenced_code',
                'toc',
                'nl2br',
                'sane_lists'
            ]
        )
        
        full_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Documento Rielaborato</title>
</head>
<body>
{html_content}
</body>
</html>"""
        
        try:
            if self.engine == "weasyprint":
                return self._convert_weasyprint(full_html, output_path)
            else:
                return self._convert_xhtml2pdf(full_html, output_path)
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            return False
    
    def _convert_weasyprint(self, html: str, output_path: str) -> bool:
        """Convert using WeasyPrint."""
        css = CSS(string=self.CSS_STYLES)
        HTML(string=html).write_pdf(output_path, stylesheets=[css])
        logger.info(f"PDF generated (WeasyPrint): {output_path}")
        return True
    
    def _convert_xhtml2pdf(self, html: str, output_path: str) -> bool:
        """Fallback conversion using xhtml2pdf."""
        # Inject CSS inline for xhtml2pdf
        styled_html = html.replace(
            '<head>',
            f'<head><style>{self.CSS_STYLES}</style>'
        )
        
        with open(output_path, "wb") as pdf_file:
            status = pisa.CreatePDF(styled_html, dest=pdf_file)
        
        if status.err:
            logger.error(f"xhtml2pdf errors: {status.err}")
            return False
        
        logger.info(f"PDF generated (xhtml2pdf): {output_path}")
        return True

# =============================================================================
# MAIN MERGER CLASS
# =============================================================================

class AnnexMergerEnhanced:
    """
    Advanced document merger with semantic retrieval and parallel processing.
    
    Features:
    - Semantic similarity-based chunk matching (TF-IDF)
    - Parallel LLM calls for faster processing
    - Response caching to avoid duplicate API calls
    - Professional PDF output with WeasyPrint
    - Comprehensive logging and statistics
    """
    
    def __init__(
        self,
        pages_per_batch: int = 3,
        similarity_threshold: float = 0.10,
        max_annex_matches: int = 5,
        max_workers: int = 4,
        max_context_tokens: int = 6000,
        enable_cache: bool = True,
        cache_dir: str = ".cache",
        llm_temperature: float = 0.0
    ):
        """
        Initialize the merger.
        
        Args:
            pages_per_batch: Pages per chunk in document splitting
            similarity_threshold: Minimum TF-IDF similarity to consider a match
            max_annex_matches: Maximum annex chunks to include per main chunk
            max_workers: Thread pool size for parallel processing
            max_context_tokens: Approx token limit for annex context
            enable_cache: Whether to cache LLM responses
            cache_dir: Directory for cache storage
            llm_temperature: LLM temperature (0 for deterministic)
        """
        self.chunker = DynamicMacroSectionChunker(pages_per_batch=pages_per_batch)
        self.retriever = SemanticRetriever(
            similarity_threshold=similarity_threshold,
            max_results=max_annex_matches
        )
        self.pdf_generator = PDFGenerator()
        self.cache = LLMCache(cache_dir) if enable_cache else None
        
        self.max_workers = max_workers
        self.max_context_tokens = max_context_tokens
        self.llm_temperature = llm_temperature
        
        self.stats = MergeJobStats()
    
    def process_files(
        self,
        main_doc_path: str,
        annex_paths: List[str],
        output_dir: str,
        job_name: str,
        generate_pdf: bool = True
    ) -> Dict[str, Any]:
        """
        Main entry point for document processing.
        
        Args:
            main_doc_path: Path to main document
            annex_paths: List of paths to annex documents
            output_dir: Output directory for results
            job_name: Name for output files
            generate_pdf: Whether to generate PDF (in addition to MD)
            
        Returns:
            Dict with output paths and statistics
        """
        start_time = time.time()
        logger.info(f"{'='*60}")
        logger.info(f"STARTING MERGE JOB: {job_name}")
        logger.info(f"{'='*60}")
        
        # Reset stats
        self.stats = MergeJobStats()
        
        # 1. Chunk Main Document
        logger.info(f"📄 Chunking main document: {os.path.basename(main_doc_path)}")
        main_chunks_data = self.chunker.process_document(main_doc_path)
        main_chunks = main_chunks_data['chunks']
        self.stats.total_chunks = len(main_chunks)
        logger.info(f"   → {len(main_chunks)} chunks extracted")
        
        # 2. Chunk Annex Documents
        all_annex_chunks = []
        for ann_path in annex_paths:
            logger.info(f"📎 Chunking annex: {os.path.basename(ann_path)}")
            ann_data = self.chunker.process_document(ann_path)
            ann_chunks = ann_data['chunks']
            # Tag chunks with source
            for chunk in ann_chunks:
                chunk['source_file'] = os.path.basename(ann_path)
            all_annex_chunks.extend(ann_chunks)
            logger.info(f"   → {len(ann_chunks)} chunks extracted")
        
        logger.info(f"✅ Total: {len(main_chunks)} main + {len(all_annex_chunks)} annex chunks")
        
        # 3. Index annexes for semantic search
        logger.info("🔍 Building semantic index...")
        self.retriever.index_annexes(all_annex_chunks)
        
        # 4. Parallel merge processing
        logger.info(f"🔄 Processing chunks (workers={self.max_workers})...")
        merge_results = self._parallel_merge(main_chunks)
        
        # 5. Compile final document
        merged_md = self._compile_markdown(merge_results)
        
        # 6. Save outputs
        os.makedirs(output_dir, exist_ok=True)
        
        md_path = os.path.join(output_dir, f"{job_name}.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(merged_md)
        logger.info(f"📝 Markdown saved: {md_path}")
        
        pdf_path = None
        if generate_pdf:
            pdf_path = os.path.join(output_dir, f"{job_name}.pdf")
            self.pdf_generator.convert(merged_md, pdf_path)
        
        # 7. Compile statistics
        self.stats.total_processing_time = time.time() - start_time
        
        logger.info(f"{'='*60}")
        logger.info("JOB COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"  Total chunks:      {self.stats.total_chunks}")
        logger.info(f"  Modified chunks:   {self.stats.modified_chunks}")
        logger.info(f"  Cache hits:        {self.stats.cache_hits}")
        logger.info(f"  LLM calls:         {self.stats.llm_calls}")
        logger.info(f"  Processing time:   {self.stats.total_processing_time:.2f}s")
        logger.info(f"{'='*60}")
        
        return {
            "markdown_path": md_path,
            "pdf_path": pdf_path,
            "stats": {
                "total_chunks": self.stats.total_chunks,
                "modified_chunks": self.stats.modified_chunks,
                "cache_hits": self.stats.cache_hits,
                "llm_calls": self.stats.llm_calls,
                "processing_time_seconds": self.stats.total_processing_time
            }
        }
    
    def _parallel_merge(self, main_chunks: List[Dict]) -> List[MergeResult]:
        """
        Process chunks in parallel using ThreadPoolExecutor.
        Maintains original order of chunks.
        """
        results: List[Optional[MergeResult]] = [None] * len(main_chunks)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_idx = {
                executor.submit(self._process_chunk, chunk): idx
                for idx, chunk in enumerate(main_chunks)
            }
            
            # Collect results with progress bar
            with tqdm(total=len(main_chunks), desc="Merging", unit="chunk") as pbar:
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        results[idx] = future.result()
                    except Exception as e:
                        logger.error(f"Chunk {idx} failed: {e}")
                        # Fallback: keep original
                        results[idx] = MergeResult(
                            section_title=main_chunks[idx]['section_title'],
                            original_text=main_chunks[idx]['text'],
                            merged_text=main_chunks[idx]['text'],
                            annex_matches=[],
                            was_modified=False
                        )
                    pbar.update(1)
        
        return results
    
    def _process_chunk(self, main_chunk: Dict) -> MergeResult:
        """
        Process a single main chunk: find relevant annexes and merge.
        """
        start_time = time.time()
        section_title = main_chunk['section_title']
        original_text = main_chunk['text']
        
        # Find relevant annex chunks
        matches = self.retriever.find_relevant(main_chunk)
        self.stats.total_annex_matches += len(matches)
        
        if not matches:
            # No relevant annexes found
            return MergeResult(
                section_title=section_title,
                original_text=original_text,
                merged_text=original_text,
                annex_matches=[],
                was_modified=False,
                processing_time=time.time() - start_time
            )
        
        # Build annex context
        annex_context = self._build_annex_context(matches)
        
        # Check cache
        cache_hit = False
        if self.cache:
            cached = self.cache.get(original_text, annex_context)
            if cached:
                cache_hit = True
                self.stats.cache_hits += 1
                merged_text = cached
            else:
                merged_text = self._call_llm(main_chunk, annex_context)
                self.cache.set(original_text, annex_context, merged_text)
        else:
            merged_text = self._call_llm(main_chunk, annex_context)
        
        # Determine if modified
        was_modified = merged_text.strip() != original_text.strip()
        if was_modified:
            self.stats.modified_chunks += 1
        
        return MergeResult(
            section_title=section_title,
            original_text=original_text,
            merged_text=merged_text,
            annex_matches=matches,
            was_modified=was_modified,
            cache_hit=cache_hit,
            processing_time=time.time() - start_time
        )
    
    def _build_annex_context(self, matches: List[ChunkMatch]) -> str:
        """
        Build the annex context string, respecting token limits.
        """
        context_parts = []
        total_chars = 0
        max_chars = self.max_context_tokens * 4  # ~4 chars per token
        
        for match in matches:
            chunk = match.chunk
            source = chunk.get('source_file', 'Unknown')
            title = chunk.get('section_title', 'N/A')
            text = chunk['text']
            
            header = f"[Fonte: {source} | Sezione: {title} | Similarità: {match.similarity:.2f}]"
            part = f"{header}\n{text}"
            
            if total_chars + len(part) > max_chars:
                # Truncate this part
                remaining = max_chars - total_chars - len(header) - 50
                if remaining > 200:
                    part = f"{header}\n{text[:remaining]}...[TRONCATO]"
                    context_parts.append(part)
                break
            
            context_parts.append(part)
            total_chars += len(part)
        
        return "\n\n---\n\n".join(context_parts)
    
    def _call_llm(self, main_chunk: Dict, annex_context: str) -> str:
        """
        Call LLM to merge main chunk with annex content.
        """
        self.stats.llm_calls += 1
        
        user_prompt = USER_PROMPT_TEMPLATE.format(
            section_title=main_chunk['section_title'],
            main_text=main_chunk['text'],
            annex_content=annex_context
        )
        
        full_system = SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES
        
        try:
            response = llm_chat(
                model=LLM_EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": user_prompt}
                ],
                options={"temperature": self.llm_temperature},
                provider=LLM_PROVIDER
            )
            return response['message']['content'].strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return main_chunk['text']
    
    def _compile_markdown(self, results: List[MergeResult]) -> str:
        """
        Compile all merge results into final Markdown document.
        """
        lines = [
            "# Documento Rielaborato",
            "",
            f"> *Generato automaticamente il {time.strftime('%d/%m/%Y alle %H:%M')}*",
            f"> *Sezioni elaborate: {len(results)} | Sezioni modificate: {self.stats.modified_chunks}*",
            "",
            "---",
            ""
        ]
        
        for result in results:
            lines.append(f"## {result.section_title}")
            lines.append("")
            lines.append(result.merged_text)
            lines.append("")
        
        return "\n".join(lines)
    
    def clear_cache(self) -> None:
        """Clear the LLM response cache."""
        if self.cache:
            self.cache.clear()

# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Command-line interface for AnnexMerger."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Merge annex documents into a main document intelligently.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python annex_merger_enhanced.py main.pdf annex1.pdf annex2.pdf -o output -n merged_doc
  python annex_merger_enhanced.py main.pdf annexes/*.pdf --workers 8 --threshold 0.15
        """
    )
    
    parser.add_argument("main_doc", help="Path to main document (PDF)")
    parser.add_argument("annexes", nargs="+", help="Paths to annex documents")
    parser.add_argument("-o", "--output", default="./output", help="Output directory")
    parser.add_argument("-n", "--name", default="merged_document", help="Output file name")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--threshold", type=float, default=0.10, help="Similarity threshold")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM caching")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cache before run")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Initialize merger
    merger = AnnexMergerEnhanced(
        similarity_threshold=args.threshold,
        max_workers=args.workers,
        enable_cache=not args.no_cache
    )
    
    # Clear cache if requested
    if args.clear_cache:
        merger.clear_cache()
    
    # Run merge
    result = merger.process_files(
        main_doc_path=args.main_doc,
        annex_paths=args.annexes,
        output_dir=args.output,
        job_name=args.name,
        generate_pdf=not args.no_pdf
    )
    
    print(f"\n✅ Output files:")
    print(f"   Markdown: {result['markdown_path']}")
    if result['pdf_path']:
        print(f"   PDF:      {result['pdf_path']}")

if __name__ == "__main__":
    main()