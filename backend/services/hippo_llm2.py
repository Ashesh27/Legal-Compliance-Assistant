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
class HippoRAGFullLLM:
    def __init__(self):
        self.graph = nx.Graph()

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
            
            # 1. Extract
            entities = self.extract_with_llm(full_text)
            
            # 2. Build Graph
            c_id = chunk.get('global_id', i)
            chunk_node = f"chunk_{c_id}"
            # Save text snippet for preview later
            self.graph.add_node(chunk_node, type='chunk', source=chunk.get('source', 'unknown'), text=chunk.get('text', ''))
            
            for ent in entities:
                ent_clean = ent.lower().strip().replace(" ", "_")
                if len(ent_clean) < 2: continue
                ent_node = f"ent_{ent_clean}"
                self.graph.add_node(ent_node, type='entity')
                self.graph.add_edge(chunk_node, ent_node, weight=1.0)
            
            elapsed_chunk = time.time() - chunk_start
            print(f"   [{i+1}/{len(chunks)}] Chunk {c_id} done in {elapsed_chunk:.1f}s | Found {len(entities)} concepts")

        print(f"\n✅ BUILD COMPLETE! Total time: {(time.time() - start_global) / 60:.1f} minutes")
        print(f"📊 Graph Stats: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
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

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # --- CONFIGURATION (LIST OF FILES) ---
    CHUNKS_PATH = [
        r"C:\Users\ashesh.gupta\checkpoint1512\backend\internal\internal_0_POL-960_v00_Politica_per_la_Responsabilita_Sociale_chunks_chunks.json",
        r"C:\Users\ashesh.gupta\checkpoint1512\backend\internal\internal_0_MRS-000_v00_Manuale_Sistema_di_Gestione_Responsabilita_Sociale_chunks_chunks.json"
    ]
    # -------------------------------------

    # 1. Load Data (Supports multiple files now)
    chunks = load_improved_chunks(CHUNKS_PATH)
    if not chunks: exit()

    # 2. Build Graph
    builder_engine = HippoRAGFullLLM()
    G_memory = builder_engine.build_full_index(chunks)

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