import networkx as nx
import json
import re
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Union
import sys
import matplotlib.pyplot as plt
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ==========================================
# 1. IMPORT YOUR LLM PROVIDER
# ==========================================
# Make sure llm_provider.py is in the same folder or python path
try:
    from llm_provider import llm_chat 
except ImportError:
    print("⚠️ Error: Could not import 'llm_chat' from llm_provider.")
    print("   Make sure llm_provider.py is in the same directory.")
    exit()

# ==============================================================================
# PART 1: THE BUILDER
# ==============================================================================
class EntityResolver:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2", threshold=0.95):
        print(f"   🧬 Initializing Entity Resolver (Threshold: {threshold})...")
        self.encoder = SentenceTransformer(model_name)
        self.threshold = threshold
        
        # State tracking
        self.canonical_entities = [] # Master list of unique concepts
        self.canonical_vectors = []  # Matrix of embeddings for the master list
        self.alias_map = {}          # Dictionary mapping variations to master concepts

    def resolve(self, raw_entity: str) -> str:
        # Basic string cleaning
        clean_ent = raw_entity.lower().strip().replace(" ", "_")
        if len(clean_ent) < 2: return ""
        
        # 1. Exact Match Cache (Fast path)
        if clean_ent in self.alias_map:
            return self.alias_map[clean_ent]
            
        # 2. Semantic Similarity Check
        ent_vec = self.encoder.encode([clean_ent])
        
        if len(self.canonical_vectors) > 0:
            similarities = cosine_similarity(ent_vec, self.canonical_vectors)[0]
            best_idx = int(np.argmax(similarities))
            best_score = similarities[best_idx]
            
            if best_score >= self.threshold:
                # Merge! Map this new variation to the existing canonical entity
                canonical_name = self.canonical_entities[best_idx]
                self.alias_map[clean_ent] = canonical_name
                return canonical_name
                
        # 3. No match found -> Register as a NEW canonical entity
        self.canonical_entities.append(clean_ent)
        if len(self.canonical_vectors) == 0:
            self.canonical_vectors = ent_vec
        else:
            self.canonical_vectors = np.vstack([self.canonical_vectors, ent_vec])
            
        self.alias_map[clean_ent] = clean_ent
        return clean_ent
    

class HippoRAGFullLLM:
    def __init__(self):
        self.graph = nx.Graph()
        self.resolver = EntityResolver(threshold=0.95)

    def extract_with_llm(self, text):
        system_prompt = (
            "You are a Compliance Expert. Extract a list of key technical concepts, "
            "regulations (e.g., SA8000, ISO), and process requirements from the text.\n"
            "RULES:\n"
            "1. Ignore generic corporate info.\n"
            "2. Ignore functional words (e.g., ove, per, il, del).\n"
            "3. Extract specific phrases (e.g., 'Health and Safety' instead of 'Safety').\n"
            "4. Return ONLY a valid JSON list of strings."
        )
        try:
            response = llm_chat(
                model="qwen3:4b-instruct-2507-q4_K_M", 
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Extract from:\n{text[:2500]}"}
                ]
            )
            content = response.get("message", {}).get("content", "")
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match: return json.loads(match.group(0))
            return []
        except Exception as e:
            print(f"   ⚠️ LLM Error on chunk: {e}")
            return []

    def build_full_index(self, chunks):
        print(f"\n🚀 Starting Graph Build for {len(chunks)} chunks...")
        start_global = time.time()
        
        for i, chunk in enumerate(chunks):
            chunk_start = time.time()
            full_text = f"{chunk.get('section', '')} {chunk.get('text', '')}"
            
            # 1. Extract raw entities via LLM
            raw_entities = self.extract_with_llm(full_text)
            
            # 2. Build Graph Nodes for the Chunk
            c_id = chunk.get('global_id', i)
            chunk_node = f"chunk_{c_id}"
            self.graph.add_node(chunk_node, type='chunk', source=chunk.get('source', 'unknown'), text=chunk.get('text', ''))
            
            # 3. Resolve and Link Entities
            resolved_entities = set() # Use a set to prevent duplicate edges from the same chunk
            for ent in raw_entities:
                canonical_ent = self.resolver.resolve(ent)
                if canonical_ent:
                    resolved_entities.add(canonical_ent)
            
            for canonical_ent in resolved_entities:
                ent_node = f"ent_{canonical_ent}"
                self.graph.add_node(ent_node, type='entity')
                self.graph.add_edge(chunk_node, ent_node, weight=1.0)
            
            elapsed_chunk = time.time() - chunk_start
            print(f"   [{i+1}/{len(chunks)}] Chunk {c_id} | Raw: {len(raw_entities)} -> Clean: {len(resolved_entities)} | {elapsed_chunk:.1f}s")

        print(f"\n✅ BUILD COMPLETE! Total time: {(time.time() - start_global) / 60:.1f} minutes")
        print(f"📊 Graph Stats: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        print(f"🧹 Consolidation Stats: Reduced to {len(self.resolver.canonical_entities)} unique concepts.")
        return self.graph

# ==============================================================================
# PART 2: THE VISUALIZER
# ==============================================================================
def generate_graph_png(G, output_filename="graph_viz.png"):
    print(f"\n🎨 Generating Graph Visualization ({output_filename})...")
    pos = nx.spring_layout(G, k=0.2, iterations=50, seed=42)
    plt.figure(figsize=(20, 20))

    chunk_nodes = [n for n, attr in G.nodes(data=True) if attr.get('type') == 'chunk']
    entity_nodes = [n for n, attr in G.nodes(data=True) if attr.get('type') == 'entity']

    nx.draw_networkx_nodes(G, pos, nodelist=chunk_nodes, node_color='#3498db', node_shape='s', node_size=150, alpha=0.8, label="Chunks")
    nx.draw_networkx_nodes(G, pos, nodelist=entity_nodes, node_color='#e74c3c', node_shape='o', node_size=200, alpha=0.9, label="Concepts")
    nx.draw_networkx_edges(G, pos, width=0.5, alpha=0.3, edge_color='gray')

    degrees = dict(G.degree(entity_nodes))
    top_concepts = sorted(degrees, key=degrees.get, reverse=True)[:30]
    labels = {n: n.replace("ent_", "").replace("_", " ") for n in top_concepts}
    nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight='bold')

    plt.axis('off')
    plt.savefig(output_filename, dpi=120, bbox_inches='tight')
    plt.close()
    print(f"✅ Visualization saved to: {output_filename}")

# ==============================================================================
# PART 3: THE RETRIEVER
# ==============================================================================
class HippoRetrieverInMemory:
    def __init__(self, graph_object, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        print("\n🧠 Initializing Retriever (using in-memory graph)...")
        self.graph = graph_object
        print(f"   🤖 Loading Embedding Model: {model_name}...")
        self.encoder = SentenceTransformer(model_name)
        
        print("   ⚡ Caching entity embeddings...")
        self.entity_nodes = [n for n in self.graph.nodes if n.startswith("ent_")]
        self.entity_names = [n.replace("ent_", "").replace("_", " ") for n in self.entity_nodes]
        
        if self.entity_names:
            self.entity_vectors = self.encoder.encode(self.entity_names, convert_to_tensor=False)
        else:
            self.entity_vectors = []

    def retrieve(self, query, top_k_chunks=10, threshold=0.4):
        print(f"\n🔍 Processing Query: '{query}'")
        
        if not self.entity_names: return []
        query_vec = self.encoder.encode([query])
        similarities = cosine_similarity(query_vec, self.entity_vectors)[0]
        
        personalization = {}
        print(f"   ⚓ Anchors found (Sim > {threshold}):")
        
        count = 0
        for idx, score in enumerate(similarities):
            if score >= threshold:
                node = self.entity_nodes[idx]
                personalization[node] = float(score)
                print(f"      - {node.replace('ent_','')} ({score:.3f})")
                count += 1
        
        if count == 0:
             print("      ❌ No relevant concepts found.")
             return []

        print("   🌊 Running PageRank Flow...")
        try:
            ppr_scores = nx.pagerank(self.graph, personalization=personalization, alpha=0.85)
        except Exception:
            return []

        chunk_results = []
        for node, score in ppr_scores.items():
            if node.startswith("chunk_"):
                chunk_results.append((node, score))
        
        chunk_results.sort(key=lambda x: x[1], reverse=True)
        return chunk_results[:top_k_chunks]

# ==========================================
# HELPER: MULTI-FILE JSON LOADER
# ==========================================
def load_improved_chunks(input_paths: Union[str, List[str]]) -> List[Dict[str, Any]]:
    """
    Loads chunks from one or MORE paths (files or directories).
    """
    # Normalize input to a list
    if isinstance(input_paths, str):
        paths = [input_paths]
    else:
        paths = list(input_paths) # Handle sets/lists

    all_files = []
    
    # 1. Gather all file paths
    for p_str in paths:
        path = Path(p_str)
        if path.is_file():
            all_files.append(path)
        elif path.is_dir():
            found = list(path.glob("*_improved_chunks.json"))
            if not found: found = list(path.glob("*.json"))
            all_files.extend(found)
        else:
            print(f"⚠️ Warning: Path not found: {p_str}")

    print(f"📂 Found {len(all_files)} files to load.")
    
    # 2. Load contents
    all_chunks = []
    for f in all_files:
        try:
            print(f"   - Loading: {f.name}...")
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            chunks = data if isinstance(data, list) else data.get('chunks', [])
            
            for c in chunks:
                # Assign a unique sequential ID across ALL files
                c['global_id'] = len(all_chunks)
                all_chunks.append(c)
        except Exception as e:
            print(f"   ❌ Error loading {f.name}: {e}")

    print(f"📊 Total chunks loaded: {len(all_chunks)}")
    return all_chunks
import networkx as nx
import numpy as np
import json
from datetime import datetime
from pathlib import Path

# -- Graph persistence (uses pickle under the hood) --
def save_graph_gpickle(G: nx.Graph, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"Graph saved -> {path}")

def load_graph_pickle(path):
    path = Path(path)

    with open(path, "rb") as f:
        G = pickle.load(f)

    print(f"Graph loaded <- {path}")
    print(f"Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")
    return G


# -- Embedding cache (entity names + vectors) --
def save_embeddings(entity_names: List[str], entity_vectors: np.ndarray, path: Union[str, Path]):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # store as compressed .npz (names as JSON)
    meta = {'entity_names': entity_names}
    np.savez_compressed(str(path), vectors=entity_vectors.astype(np.float32), meta=json.dumps(meta))
    print(f"Embeddings saved -> {path}")

def load_embeddings(path: Union[str, Path]):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No embeddings file: {path}")
    data = np.load(str(path), allow_pickle=True)
    vectors = data["vectors"]
    meta = json.loads(str(data["meta"].tolist()))
    names = meta['entity_names']
    print(f"Embeddings loaded <- {path} (count={len(names)})")
    return names, vectors

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # --- CONFIGURATION (LIST OF FILES) ---
    CHUNKS_PATH =r"C:\Users\ashesh.gupta\checkpoint1102\internal\internal_0_PO-020_v17_chunks_chunks.json",

    # -------------------------------------

    # 1. Load Data (Supports multiple files now)
    chunks = load_improved_chunks(CHUNKS_PATH)
    if not chunks: exit()

    # 2. Build Graph
    builder_engine = HippoRAGFullLLM()
    G_memory = builder_engine.build_full_index(chunks)

    # ==========================================
    # 🔍 VIEW MERGED ENTITIES
    # ==========================================
    alias_map = builder_engine.resolver.alias_map
    
    # Filter out entities that mapped to themselves (not merged)
    merged_items = {raw: master for raw, master in alias_map.items() if raw != master}
    
    print("\n" + "="*50)
    print(f"🧹 MERGE REPORT: {len(merged_items)} variations consolidated")
    print("="*50)
    
    # Sort them by the master entity so it's easy to read
    sorted_merges = sorted(merged_items.items(), key=lambda x: x[1])
    
    current_master = ""
    for raw, master in sorted_merges:
        if master != current_master:
            print(f"\n👑 {master.upper()}")
            current_master = master
        print(f"   ↳ merged: '{raw}'")
    print("="*50 + "\n")


    # Save graph
    save_graph_gpickle(G_memory, "data/multi_file_graph.gpickle")

    # If you want to cache entity embeddings right after building (so retriever can reuse):
    entity_nodes = [n for n, attr in G_memory.nodes(data=True) if n.startswith("ent_")]
    entity_names = [n.replace("ent_", "").replace("_", " ") for n in entity_nodes]
    if entity_names:
        entity_vectors = builder_engine  # NOTE: builder doesn't compute them; do with your encoder
        # Example: from HippoRetrieverInMemory logic:
        encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        entity_vectors = encoder.encode(entity_names, convert_to_tensor=False)
        save_embeddings(entity_names, np.array(entity_vectors), "data3003/entity_embeddings.npz")

    # 3. Visualize
    generate_graph_png(G_memory, "multi_file_graph.png")

    # 4. Initialize Retriever
    retriever_engine = HippoRetrieverInMemory(G_memory)

    # 5. Interactive Loop
    print("\n" + "="*50)
    print("💬 INTERACTIVE MODE STARTED")
    print(f"   Loaded {len(chunks)} chunks from {len(CHUNKS_PATH)} files.")
    print("   Type a query or 'exit'.")
    print("="*50 + "\n")

    while True:
        user_query = input("🔎 Enter your query: ")
        
        if user_query.lower() in ['exit', 'quit']:
            print("👋 Exiting...")
            break
            
        if not user_query.strip(): continue

        results = retriever_engine.retrieve(user_query, top_k_chunks=10)

        print(f"\n🏆 Top Results for: '{user_query}'")
        print("-" * 60)
        if not results:
            print("   (No results found)")
        else:
            for rank, (chunk_id, score) in enumerate(results):
                node_data = G_memory.nodes[chunk_id]
                # Show text preview
                preview = node_data.get('text', 'No text available')[:80].replace("\n", " ")
                print(f"   #{rank+1:2d} | {chunk_id} | {score:.4f} | \"{preview}...\"")
        print("-" * 60 + "\n")