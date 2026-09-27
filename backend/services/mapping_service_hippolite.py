"""
Modulo di mappatura dei chunks con HippoRAG.
Include visualizzazione del grafo e analisi dell'impatto.
"""

import os
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import sys
import networkx as nx

# Try importing matplotlib for visualization
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("⚠️ Matplotlib non trovato. La visualizzazione del grafo sarà disabilitata.")
    MATPLOTLIB_AVAILABLE = False

# Try importing from the file we just created
try:
    from hippo2 import HippoRAGLite
    print("✅ hippo2.py importato con successo.")
except ImportError:
    print("⚠️ Please create hippo2.py in the same directory!")

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.prompts_config import MAPPING_SYSTEM_PROMPT, get_mapping_user_prompt
from llm_provider import llm_chat

# Load environment variables
load_dotenv()
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from pathlib import Path
from datetime import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

class ImprovedRequirementsMapper:
    def __init__(self, embedding_model_name: str = None, use_hipporag: bool = False):
        """
        Inizializza il mapper migliorato.
        
        Args:
            embedding_model_name: Nome del modello per embeddings
            use_hipporag: Abilita il motore associativo (Graph)
        """
        # Load model names from environment variables
        if embedding_model_name is None:
            embedding_model_name = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
        print(f"🔄 Inizializzazione sistema di mapping migliorato...")
        
        # Modello di embedding
        self.embedding_model = SentenceTransformer(embedding_model_name)
        print(f"✅ Modello embedding caricato: {embedding_model_name}")
        
        # TF-IDF per keyword matching
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        
        # Cache per ottimizzazione
        self.embedding_cache = {}
        
        # Stopwords italiane
        self.stopwords = set([
            'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una', 'di', 'da', 'in', 'su',
            'per', 'con', 'tra', 'fra', 'a', 'e', 'è', 'o', 'ma', 'se', 'che', 'chi', 'cui'
        ])

        # --- HippoRAG Setup ---
        self.use_hipporag = use_hipporag
        self.hippo_engine = None 

        if self.use_hipporag:
            print("🧠 Abilitazione HippoRAG Lite (Associative Memory)...")
            try:
                # Initialize the Lite engine
                self.hippo_engine = HippoRAGLite()
                print("✅ HippoRAG Lite inizializzato.")
            except Exception as e:
                print(f"⚠️ Errore inizializzazione HippoRAG Lite: {e}")
                self.use_hipporag = False

    def build_hipporag_index(self, chunks: List[Dict[str, Any]], llm_chat):
        """
        Costruisce il grafo associativo usando il motore Lite.
        """
        if not self.use_hipporag or not self.hippo_engine:
            return
            
        print("\n🧠 Costruzione Indice HippoRAG Lite...")
        try:
            # 1. Build the base Graph (Context Edges: Entities to Chunks)
            self.hippo_engine.build_index(chunks, llm_chat)
            
            # 2. Add Synonym Edges (Dense Integration)
            # Using the same model already in self.embedding_model
            self.hippo_engine.embedder = self.embedding_model 
            self.hippo_engine.add_synonym_edges(threshold=0.90)
        except Exception as e:
            print(f"❌ Errore durante l'indexing HippoRAG: {e}")
            self.use_hipporag = False

    def visualize_graph(self, output_dir: str):
        """
        Genera un'immagine del Knowledge Graph (Hub principali).
        """
        if not self.use_hipporag or not self.hippo_engine or not MATPLOTLIB_AVAILABLE:
            return

        print("🎨 Generazione visualizzazione grafo...")
        try:
            G = self.hippo_engine.graph
            if G.number_of_nodes() == 0:
                print("⚠️ Grafo vuoto, niente da visualizzare.")
                return

            # Calcola i "Knowledge Hubs" (entità più connesse)
            entity_degrees = []
            for node in G.nodes():
                if node.startswith("ent_"):
                    entity_degrees.append((node, G.degree(node)))
            
            # Ordina per connessioni
            entity_degrees.sort(key=lambda x: x[1], reverse=True)
            top_hubs = [n[0] for n in entity_degrees[:20]] # Top 5 concetti
            
            # Crea un sottografo per la visualizzazione (Hubs + Vicini)
            nodes_to_draw = set(top_hubs)
            for hub in top_hubs:
                neighbors = list(G.neighbors(hub))[:8] # Limita a 8 documenti per hub
                nodes_to_draw.update(neighbors)
                
            subgraph = G.subgraph(list(nodes_to_draw))
            
            plt.figure(figsize=(12, 10))
            pos = nx.spring_layout(subgraph, k=0.6, seed=42)
            
            # Disegna Documenti (Chunks)
            chunk_nodes = [n for n in subgraph.nodes if n.startswith('chunk_')]
            nx.draw_networkx_nodes(subgraph, pos, nodelist=chunk_nodes, node_color='#aec7e8', 
                                   node_size=300, node_shape='s', label='Documents')
            
            # Disegna Concetti (Entità)
            ent_nodes = [n for n in subgraph.nodes if n.startswith('ent_')]
            nx.draw_networkx_nodes(subgraph, pos, nodelist=ent_nodes, node_color='#ff9896', 
                                   node_size=600, node_shape='o', label='Concepts')
            
            # Etichette
            labels = {n: n.replace('ent_', '').upper() if n.startswith('ent_') else '' for n in subgraph.nodes}
            nx.draw_networkx_labels(subgraph, pos, labels, font_size=8, font_weight='bold')
            
            # Archi
            nx.draw_networkx_edges(subgraph, pos, alpha=0.4, edge_color='gray')
            
            plt.title("HippoRAG Knowledge Graph (Top Connected Concepts)")
            plt.axis('off')
            plt.legend()
            
            out_file = os.path.join(output_dir, "hipporag_graph.png")
            plt.savefig(out_file, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"✅ Grafo visualizzato salvato in: {out_file}")
            
        except Exception as e:
            print(f"⚠️ Errore visualizzazione grafo: {e}")

    def load_requirements_enhanced(self, requirements_file: str, max_requirements: int = 50, 
                                  start_from: int = 0) -> List[Dict[str, Any]]:
        """Carica requisiti con parsing migliorato e limitazione opzionale."""
        requirements = []
        if not os.path.exists(requirements_file):
            print(f"❌ File requisiti non trovato: {requirements_file}")
            return requirements
        
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            req_blocks = re.split(r'REQUISITO \d+', content)[1:]
            
            if max_requirements or start_from > 0:
                end_idx = start_from + max_requirements if max_requirements else len(req_blocks)
                req_blocks = req_blocks[start_from:end_idx]
                print(f"⚠️  Caricamento limitato: requisiti {start_from+1} a {min(end_idx, len(req_blocks)+start_from)}")
            
            for i, block in enumerate(req_blocks, start_from + 1):
                lines = block.strip().split('\n')
                requirement_data = {
                    'id': i, 'requirement_original': "", 'requirement_paraphrased': "",
                    'audit_question': "", 'source_file': "", 'source_chunk': "",
                    'keywords': [], 'requirement_type': "", 'references': ""
                }
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('File sorgente:'): requirement_data['source_file'] = line.replace('File sorgente:', '').strip()
                    elif line.startswith('Chunk sorgente:'): requirement_data['source_chunk'] = line.replace('Chunk sorgente:', '').strip()
                    elif line.startswith('REQUISITO ORIGINALE:'): requirement_data['requirement_original'] = line.replace('REQUISITO ORIGINALE:', '').strip()
                    elif line.startswith('REQUISITO PARAFRASATO:'): requirement_data['requirement_paraphrased'] = line.replace('REQUISITO PARAFRASATO:', '').strip()
                    elif line.startswith('REQUISITO:'): requirement_data['requirement_paraphrased'] = line.replace('REQUISITO:', '').strip()
                    elif line.startswith('DOMANDA AUDIT:'): requirement_data['audit_question'] = line.replace('DOMANDA AUDIT:', '').strip()
                    elif line.startswith('REFERENZE:'): requirement_data['references'] = line.replace('REFERENZE:', '').strip()
                
                if not requirement_data['requirement_original'] and requirement_data['requirement_paraphrased']:
                    requirement_data['requirement_original'] = requirement_data['requirement_paraphrased']
                
                if requirement_data['requirement_original']:
                    requirement_data['keywords'] = self.extract_keywords(requirement_data['requirement_original'])
                    requirement_data['requirement_type'] = self.classify_requirement_type(requirement_data['requirement_original'])
                    requirement_data['requirement_combined'] = f"{requirement_data['requirement_original']} {requirement_data['requirement_paraphrased']}".strip()
                    requirements.append(requirement_data)
            
            print(f"📋 Caricati {len(requirements)} requisiti con metadati arricchiti")
            return requirements
        except Exception as e:
            print(f"❌ Errore nel caricare i requisiti: {e}")
            return []
    
    def load_improved_chunks(self, chunks_dir: str) -> List[Dict[str, Any]]:
        """Carica chunks dal formato migliorato (JSON)."""
        all_chunks = []
        chunk_files = list(Path(chunks_dir).glob("*_improved_chunks.json"))
        if not chunk_files: chunk_files = list(Path(chunks_dir).glob("*.json"))
        
        for chunk_file in chunk_files:
            print(f"📁 Caricamento chunks da: {chunk_file.name}")
            try:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunks = json.load(f)
                for chunk in chunks:
                    chunk['global_id'] = len(all_chunks)
                    chunk['section_number'] = self.extract_section_number(chunk.get('section', ''))
                    all_chunks.append(chunk)
                print(f"   ✅ Caricati {len(chunks)} chunks")
            except Exception as e:
                print(f"   ❌ Errore: {e}")
                continue
        print(f"📊 Totale chunks caricati: {len(all_chunks)}")
        return all_chunks
    
    def extract_section_number(self, section_title: str) -> str:
        patterns = [r'^(\d+\.?\d*\.?\d*)', r'^([IVXLCDM]+)', r'^([A-Z])\.']
        for pattern in patterns:
            match = re.match(pattern, section_title)
            if match: return match.group(1)
        return ""
    
    def extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r'\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}\b', text.lower())
        keywords = [w for w in words if w not in self.stopwords]
        important_patterns = [r'deve\s+(\w+)', r'necessario\s+(\w+)', r'richiesto\s+(\w+)', r'obbligo\s+di\s+(\w+)', r'divieto\s+di\s+(\w+)']
        for pattern in important_patterns:
            matches = re.findall(pattern, text.lower())
            keywords.extend(matches)
        return list(set(keywords))[:20]
    
    def classify_requirement_type(self, text: str) -> str:
        text_lower = text.lower()
        if any(word in text_lower for word in ['documentare', 'registrare', 'policy', 'procedura']): return 'documentazione'
        elif any(word in text_lower for word in ['formare', 'formazione', 'training', 'addestramento']): return 'formazione'
        elif any(word in text_lower for word in ['monitorare', 'verificare', 'audit', 'controllo']): return 'monitoraggio'
        elif any(word in text_lower for word in ['comunicare', 'informare', 'notificare']): return 'comunicazione'
        elif any(word in text_lower for word in ['non deve', 'vietato', 'proibito']): return 'divieto'
        else: return 'generale'
    
    def compute_tfidf_scores(self, query: str, documents: List[str]) -> np.ndarray:
        if not self.tfidf_vectorizer:
            self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), stop_words=list(self.stopwords))
            all_texts = [query] + documents
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
        else:
            query_vec = self.tfidf_vectorizer.transform([query])
            docs_vecs = self.tfidf_vectorizer.transform(documents)
            scores = cosine_similarity(query_vec, docs_vecs)[0]
            return scores
        query_vec = self.tfidf_matrix[0]
        docs_vecs = self.tfidf_matrix[1:]
        return cosine_similarity(query_vec, docs_vecs)[0]
    
    def keyword_overlap_score(self, req_keywords: List[str], chunk_text: str) -> float:
        if not req_keywords: return 0.0
        chunk_words = set(re.findall(r'\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}\b', chunk_text.lower()))
        req_keywords_set = set(req_keywords)
        overlap = len(req_keywords_set.intersection(chunk_words))
        return overlap / len(req_keywords_set)

    def hipporag_retrieval(self, requirement: Dict[str, Any], top_k: int = 15) -> List[Dict[str, Any]]:
        """Esegue il retrieval associativo usando HippoRAG Lite."""
        if not self.use_hipporag or not self.hippo_engine:
            return []
        query = f"{requirement['requirement_original']} {requirement['requirement_paraphrased']}"
        try:
            results = self.hippo_engine.retrieve(query, top_k=top_k)
            matches = []
            for i, res in enumerate(results):
                chunk = res['chunk']
                score = res['score']
                entities = res.get('matched_entities', [])
                matches.append({
                    'chunk': chunk,
                    'similarity_score': float(score),
                    'tfidf_score': 0.0,
                    'keyword_score': 0.0,
                    'final_score': float(score),
                    'rank': i + 1,
                    'source': f"hipporag (via {', '.join(entities[:3])})"
                })
            if matches:
                print(f"      🧠 HippoRAG attivato: {len(matches)} chunks collegati.")
            return matches
        except Exception as e:
            print(f"      ⚠️ Errore durante HippoRAG retrieval: {e}")
            return []
    
    def hybrid_retrieval(self, requirement: Dict[str, Any], chunks: List[Dict[str, Any]], 
                        req_embedding: np.ndarray, chunk_embeddings: np.ndarray, top_k: int = 30) -> List[Dict[str, Any]]:
        print(f"   🔍 Hybrid retrieval per requisito {requirement['id']}...")
        semantic_scores = cosine_similarity([req_embedding], chunk_embeddings)[0]
        chunk_texts = [c.get('full_text_with_context', c['text']) for c in chunks]
        tfidf_scores = self.compute_tfidf_scores(requirement['requirement_combined'], chunk_texts)
        keyword_scores = np.array([self.keyword_overlap_score(requirement['keywords'], c.get('full_text_with_context', c['text'])) for c in chunks])
        section_boost = np.array([1.2 if self.is_relevant_section(requirement['requirement_type'], c.get('section', '')) else 1.0 for c in chunks])

        hippo_score_vector = np.zeros(len(chunks))
        if self.use_hipporag and self.hippo_engine:
            hippo_matches = self.hipporag_retrieval(requirement)
            for res in hippo_matches:
                c_id = res['chunk']['global_id']
                if c_id < len(chunks):
                    hippo_score_vector[c_id] = res['final_score']

        # Aggressive graph weight for demonstration (50% Hippo)
        final_scores = (
            0.40 * semantic_scores + 
            0.20 * tfidf_scores + 
            0.15 * keyword_scores + 
            0.25 * hippo_score_vector
        ) * section_boost
        
        if final_scores.max() > 0: final_scores = final_scores / final_scores.max()
        top_indices = np.argsort(final_scores)[::-1][:top_k]
        
        matches = []
        for idx in top_indices:
            if final_scores[idx] > 0.25:
                src = "hybrid"
                if hippo_score_vector[idx] > 0: src += "+hipporag"
                matches.append({
                    'chunk': chunks[idx],
                    'similarity_score': float(semantic_scores[idx]),
                    'tfidf_score': float(tfidf_scores[idx]),
                    'keyword_score': float(keyword_scores[idx]),
                    'final_score': float(final_scores[idx]),
                    'rank': len(matches) + 1,
                    'source': src
                })
        print(f"      ✅ Trovati {len(matches)} matches con score > 0.25")
        return sorted(matches, key=lambda x: x['final_score'], reverse=True)[:15]
    
    def is_relevant_section(self, req_type: str, section_title: str) -> bool:
        section_lower = section_title.lower()
        relevance_map = {
            'documentazione': ['documento', 'procedura', 'policy', 'registro'],
            'formazione': ['formazione', 'training', 'addestramento', 'competenze'],
            'monitoraggio': ['monitoraggio', 'audit', 'verifica', 'controllo'],
            'comunicazione': ['comunicazione', 'informazione', 'notifica'],
            'divieto': ['divieto', 'restrizione', 'limitazione']
        }
        return any(term in section_lower for term in relevance_map.get(req_type, []))
    
    def enhanced_llm_analysis(self, requirement: Dict[str, Any], matches: List[Dict[str, Any]], model_name: str = None) -> Dict[str, Any]:
        if model_name is None: model_name = os.getenv("LLM_MAPPING_MODEL", "deepseek-r1:14b")
        if not matches: return self.get_default_analysis()
        
        chunks_context = self.prepare_enriched_context(matches)
        system_prompt = MAPPING_SYSTEM_PROMPT
        user_prompt = get_mapping_user_prompt(
            requirement_original=requirement['requirement_original'],
            requirement_type=requirement.get('requirement_type', 'generale'),
            keywords=requirement.get('keywords', []),
            chunks_context=chunks_context
        )
        
        try:
            print(f"DEBUG LLM CALL → provider={os.getenv('LLM_PROVIDER')} model={model_name}")
            response = llm_chat(
                model=model_name,
                messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
                options={"num_predict": int(os.getenv("LLM_NUM_PREDICT", "512")), "temperature": float(os.getenv("LLM_MAPPING_TEMPERATURE", "0.1")), "num_ctx": int(os.getenv("LLM_NUM_CTX", "8192")), "top_p": float(os.getenv("LLM_TOP_P", "0.95"))}
            )
            response_text = response.get("message", {}).get("content", "").strip()
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match: return self.validate_llm_response(json.loads(json_match.group(0)))
            else: raise ValueError("No valid JSON in response")
        except Exception as e:
            print(f"      ❌ Errore analisi LLM: {e}")
            return self.get_default_analysis()
    
    def prepare_enriched_context(self, matches: List[Dict[str, Any]]) -> str:
        context_parts = []
        for i, match in enumerate(matches[:10], 1):
            chunk = match['chunk']
            section_info = chunk.get('section', 'N/A')
            source_label = match.get('source', 'hybrid')
            context_parts.append(f"""
DOCUMENTO {i} (Source: {source_label} - Score: {match['final_score']:.2f})
File: {chunk.get('source_file', 'N/A')}
Sezione: {section_info}
CONTENUTO:
{chunk.get('full_text_with_context', chunk['text'])}
---""")
        return '\n'.join(context_parts)
    
    def validate_llm_response(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        required = ["allineamento", "gap", "livello_copertura", "descrizione_livello"]
        for field in required:
            if field not in analysis: analysis[field] = self.get_default_value(field)
        if not isinstance(analysis.get("livello_copertura"), int): analysis["livello_copertura"] = 1
        analysis["livello_copertura"] = max(1, min(5, analysis["livello_copertura"]))
        level_map = {5: "COMPLETA", 4: "ELEVATA", 3: "MEDIA", 2: "BASSA", 1: "ASSENTE"}
        analysis["descrizione_livello"] = level_map.get(analysis["livello_copertura"], "ASSENTE")
        return analysis
    
    def get_default_value(self, field: str) -> Any:
        defaults = {"allineamento": "Analisi non disponibile", "gap": "Gap non identificati", "livello_copertura": 1, "descrizione_livello": "ASSENTE", "confidence": 0.5}
        return defaults.get(field, "")
    
    def get_default_analysis(self) -> Dict[str, Any]:
        return {"allineamento": "Errore nell'analisi automatica", "gap": "Impossibile determinare gap", "livello_copertura": 1, "descrizione_livello": "ASSENTE", "confidence": 0.0, "aspetti_coperti": [], "aspetti_mancanti": ["Analisi non disponibile"], "azioni_richieste": ["Verificare manualmente"]}
    
    def clean_text_artifacts(self, text: str) -> str:
        if not text or len(text) < 3: return text
        tokens = text.split()
        if not tokens: return ""
        output = [tokens[0]]
        current_word = tokens[0]
        for i in range(1, len(tokens)):
            token = tokens[i]
            if current_word and token and current_word[-1] == token[0]: current_word += token[1:]
            else:
                output.append(current_word)
                current_word = token
        output.append(current_word)
        return " ".join(output)

    def format_top_matches_for_excel(self, matches: List[Dict[str, Any]]) -> str:
        if not matches: return "Nessun match trovato"
        formatted_matches = []
        for i, match in enumerate(matches[:10], 1):
            chunk = match['chunk']
            section_info = self.clean_text_artifacts(chunk.get('section', 'N/A')[:50])
            source_label = match.get('source', 'hybrid')
            formatted_matches.append(f"{i}. [{source_label}] File: {chunk.get('source_file', 'N/A')}\n   Sezione: {section_info}\n   Score: {match['final_score']:.3f}")
        return "\n\n".join(formatted_matches)
    
    def create_excel_output(self, results: List[Dict[str, Any]], output_path: str):
        excel_data = []
        for result in results:
            analysis = result['analysis']
            row = {
                'REQUISITO ESTERNO': result['requirement_original'],
                'REFERENZE': result.get('references', ''),
                'DOMANDA AUDIT': result.get('audit_question', ''),
                'MAPPING DOCUMENTI INTERNI': self.format_top_matches_for_excel(result['matches']),
                'LIVELLO': f"{analysis['livello_copertura']} - {analysis['descrizione_livello']}",
                'ALLINEAMENTO': analysis['allineamento'],
                'GAP': analysis['gap'],
                'ASPETTI COPERTI': ', '.join(analysis.get('aspetti_coperti', [])),
                'ASPETTI MANCANTI': ', '.join(analysis.get('aspetti_mancanti', [])),
                'AZIONI RICHIESTE': ', '.join(analysis.get('azioni_richieste', []))
            }
            excel_data.append(row)
        df = pd.DataFrame(excel_data)
        excel_file = Path(output_path) / "mapping_results.xlsx"
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Risultati Mapping', index=False)
            worksheet = writer.sheets['Risultati Mapping']
            for column in worksheet.columns: worksheet.column_dimensions[column[0].column_letter].width = 40
        print(f"✅ File Excel salvato: {excel_file}")
    def visualize_interactive_graph(self, output_dir: str):
        """
        Generates an interactive HTML Knowledge Graph using Pyvis.
        Useful for debugging HippoRAG's associative paths.
        """
        from pyvis.network import Network
        if not self.use_hipporag or not self.hippo_engine:
            print("⚠️ HippoRAG engine not initialized. Skipping visualization.")
            return

        print("🌐 Generating interactive Pyvis graph...")
        
        # 1. Initialize Pyvis Network
        # We use a white background and enable the filter menu
        net = Network(
            height="850px", 
            width="100%", 
            bgcolor="#ffffff", 
            font_color="black", 
            notebook=False,
            directed=False
        )

        G = self.hippo_engine.graph

        # 2. Advanced Physics Configuration
        # This keeps the nodes from overlapping and makes them "bouncy"
        net.force_atlas_2based(
            gravity=-60,
            central_gravity=0.01,
            spring_length=120,
            spring_strength=0.08,
            damping=0.4
        )

        # 3. Add Nodes with Metadata
        for node in G.nodes():
            # ENTITY NODES (Concepts)
            if node.startswith("ent_"):
                label = node.replace("ent_", "").upper()
                # Degree tells us how many chunks this entity connects
                degree = G.degree(node)
                
                net.add_node(
                    node, 
                    label=label, 
                    color="#ff7675",      # Coral Red
                    size=20 + (degree * 3), # Hubs appear larger
                    title=f"CONCEPT: {label}<br>Connected to {degree} documents",
                    group="concept",
                    shape="dot"
                )
            
            # CHUNK NODES (Documents)
            else:
                c_id_str = node.replace("chunk_", "")
                # Try to get the original data from the map
                try:
                    c_id = int(c_id_str) if c_id_str.isdigit() else c_id_str
                    chunk_data = self.hippo_engine.chunk_map.get(c_id, {})
                except:
                    chunk_data = {}

                text_snippet = chunk_data.get('text', 'No text available')[:300]
                source_file = chunk_data.get('source_file', 'Unknown')

                net.add_node(
                    node, 
                    label=f"Doc {c_id_str}", 
                    color="#74b9ff",      # Sky Blue
                    size=15, 
                    title=f"<b>FILE:</b> {source_file}<br><br><b>CONTENT:</b><br>{text_snippet}...", 
                    group="document",
                    shape="square"        # Squares distinguish docs from concepts
                )

        # 4. Add Edges
        for source, target, data in G.edges(data=True):
            is_synonym = data.get('type') == 'synonym'
            net.add_edge(
                source, 
                target, 
                value=data.get('weight', 1.0), 
                color="#dfe6e9" if not is_synonym else "#fdcb6e", # Yellow for synonyms
                width=1 if not is_synonym else 3,
                dashed=is_synonym # Dashed lines for semantic links
            )

        # 5. Save and Export
        output_file = os.path.join(output_dir, "hipporag_explorer.html")
        
        # Optional: Add a UI to the HTML to let you tweak physics live
        # net.show_buttons(filter_=['physics']) 
        
        net.save_graph(output_file)
        print(f"✅ Interactive graph saved to: {output_file}")
    def calculate_enhanced_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(results)
        if total == 0: return {}
        
        # Calculate levels
        level_counts = {f'level_{i}': sum(1 for r in results if r['analysis']['livello_copertura'] == i) for i in range(1, 6)}
        
        # HippoRAG Specific Impact
        hippo_impact = 0
        hippo_wins = 0 # Cases where Hippo was the TOP 1 match
        
        if self.use_hipporag:
            for r in results:
                matches = r.get('matches', [])
                if any('hipporag' in m.get('source', '') for m in matches):
                    hippo_impact += 1
                if matches and 'hipporag' in matches[0].get('source', ''):
                    hippo_wins += 1
                    
        return {
            "total_requirements": total,
            "coverage_levels": level_counts,
            "hippo_impact_count": hippo_impact,
            "hippo_impact_percent": (hippo_impact/total*100) if total else 0,
            "hippo_top1_wins": hippo_wins
        }
    def save_enhanced_results(self, results: List[Dict[str, Any]], output_dir: str):
        """
        Salva risultati in formato JSON e testo (Report).
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 1. Save JSON
        json_file = output_path / "mapping_results.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 2. Save Text Report
        txt_file = output_path / "mapping_report.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("REPORT MAPPING COMPLIANCE - ANALISI HIPPORAG\n")
            f.write("="*80 + "\n\n")
            
            for result in results:
                f.write(f"REQUISITO {result['requirement_id']}\n")
                f.write("-"*60 + "\n")
                f.write(f"TESTO: {result['requirement_original']}\n")
                if result.get('audit_question'):
                    f.write(f"DOMANDA: {result['audit_question']}\n")
                f.write("\n")
                
                f.write("TOP MATCHES:\n")
                for match in result['matches'][:5]:
                    chunk = match['chunk']
                    # Handle section info safely
                    sec = chunk.get('section', 'N/A')
                    if isinstance(sec, str):
                        sec = sec[:50].replace('\n', ' ')
                    
                    source = match.get('source', 'hybrid')
                    f.write(f"   {match['rank']}. [{source}] Score: {match['final_score']:.3f}\n")
                    f.write(f"      File: {chunk.get('source_file', 'N/A')}\n")
                    f.write(f"      Sez:  {sec}\n")
                
                f.write("\nANALISI:\n")
                analysis = result['analysis']
                f.write(f"   Livello: {analysis['livello_copertura']} - {analysis['descrizione_livello']}\n")
                if analysis.get('gap'):
                    f.write(f"   Gap: {analysis['gap'][:200]}...\n")
                
                f.write("\n" + "="*80 + "\n\n")
        
        print(f"✅ Risultati salvati in {output_dir}/")

        
    def process_enhanced_mapping(self, requirements_file: str, chunks_dir: str, output_dir: str, use_combined_embeddings: bool = True, max_requirements: int = None, start_from: int = 0):
        print("\n" + "="*80)
        print("🚀 AVVIO MAPPING COMPLIANCE MIGLIORATO")
        print("="*80)
        Path(output_dir).mkdir(exist_ok=True)
        
        requirements = self.load_requirements_enhanced(requirements_file, max_requirements, start_from)
        if not requirements: return {"status": "error"}
        
        chunks = self.load_improved_chunks(chunks_dir)
        if not chunks: return {"status": "error"}
        
        # TF-IDF
        all_texts = [r['requirement_combined'] for r in requirements] + [c.get('full_text_with_context', c['text']) for c in chunks]
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2), stop_words=list(self.stopwords))
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
        
        # Build & Visualize Graph
        if self.use_hipporag:
            self.build_hipporag_index(chunks, llm_chat)
            self.visualize_interactive_graph(output_dir)
            self.visualize_graph(output_dir)

        # Embeddings
        print("\n🧮 Calcolo embeddings...")
        req_texts = [r['requirement_combined'] for r in requirements]
        req_embeddings = self.embedding_model.encode(req_texts, show_progress_bar=True)
        chunk_texts = [c.get('full_text_with_context', c['text']) for c in chunks]
        chunk_embeddings = self.embedding_model.encode(chunk_texts, show_progress_bar=True)
        
        # Processing
        print(f"\n🔄 Processamento {len(requirements)} requisiti...")
        results = []
        for i, requirement in enumerate(requirements):
            print(f"\n📍 Requisito {i+1}/{len(requirements)} (ID: {requirement['id']})")
            matches = self.hybrid_retrieval(requirement, chunks, req_embeddings[i], chunk_embeddings, top_k=30)
            if matches:
                print("   🤖 Analisi LLM...")
                analysis = self.enhanced_llm_analysis(requirement, matches)
            else:
                analysis = self.get_default_analysis()
            
            results.append({
                "requirement_id": requirement['id'],
                "requirement_original": requirement['requirement_original'],
                "matches": matches,
                "analysis": analysis
            })
        
        # Save & Stats
        self.save_enhanced_results(results, output_dir)
        self.create_excel_output(results, output_dir)
        self.visualize_interactive_graph(output_dir)
        stats = self.calculate_enhanced_statistics(results)

        
        print("\n" + "="*80)
        print("📊 STATISTICHE FINALI & IMPATTO HIPPORAG")
        print("="*80)
        print(f"Requisiti processati: {stats['total_requirements']}")
        if self.use_hipporag:
            print(f"🧠 Requisiti arricchiti da HippoRAG: {stats['hippo_impact_count']} ({stats['hippo_impact_percent']:.1f}%)")
            print(f"🏆 HippoRAG ha trovato il Miglior Match (Top 1): {stats['hippo_top1_wins']} volte")
        else:
            print("⚪ HippoRAG disabilitato.")
            
        return {"status": "success", "stats": stats, "output_dir": output_dir}

def main():
    mapper = ImprovedRequirementsMapper(embedding_model_name="paraphrase-multilingual-MiniLM-L12-v2", use_hipporag=True)
    # Update paths as needed
    requirements_file = r"C:\Users\ashesh.gupta\checkpoint1512\backend\output_1712\final_requirements\req_SA8000_Standard2014_ITA_final.txt"
    chunks_dir = "C:\\Users\\ashesh.gupta\\checkpoint1512\\backend\\internal"
    output_dir = "C:\\Users\\ashesh.gupta\\checkpoint1512\\backend\\output\\mappingSA8000_hippo"
    
    mapper.process_enhanced_mapping(requirements_file, chunks_dir, output_dir, max_requirements=1, start_from=0)

if __name__ == "__main__":
    main()