import networkx as nx
import json
import re
import time
import os
from pathlib import Path
from typing import List, Dict, Any
import sys
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

# ==========================================
# 2. THE HIPPORAG ENGINE (LLM VERSION)
# ==========================================
class HippoRAGFullLLM:
    def __init__(self):
        self.graph = nx.Graph()

    def extract_with_llm(self, text):
        """
        Uses the LLM to extract clean, technical concepts.
        """
        system_prompt = (
            "You are a Compliance Expert. Extract a list of key technical concepts, "
            "regulations (e.g., SA8000, ISO), and process requirements from the text.\n"
            "RULES:\n"
            "1. Ignore generic corporate info (e.g., Lutech, Bari, S.p.A.).\n"
            "2. Ignore functional words (e.g., ove, per, il, del).\n"
            "3. Extract specific phrases (e.g., 'Health and Safety' instead of 'Safety').\n"
            "4. Return ONLY a valid JSON list of strings."
        )

        try:
            # Call your local LLM (Ollama / DeepSeek)
            response = llm_chat(
                model="qwen3:4b-instruct-2507-q4_K_M",  # Checking your model name
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Extract from:\n{text[:2500]}"} # Limit context
                ]
            )
            content = response.get("message", {}).get("content", "")
            
            # Extract JSON list from response
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return []
        except Exception as e:
            print(f"   ⚠️ LLM Error on chunk: {e}")
            return []

    def build_full_index(self, chunks):
        print(f"\n🚀 Starting Full Graph Build for {len(chunks)} chunks...")
        print("   Mode: Full LLM Extraction ")
        print("  Do not close this window.\n")
        
        start_global = time.time()
        
        for i, chunk in enumerate(chunks):
            # Combine section and text for context
            chunk_start = time.time()
            full_text = f"{chunk.get('section', '')} {chunk.get('text', '')}"
            
            # 1. Extract Entities via LLM
            entities = self.extract_with_llm(full_text)
            
            # 2. Build Graph Nodes & Edges
            c_id = chunk.get('global_id', i)
            chunk_node = f"chunk_{c_id}"
            
            # Add chunk node
            self.graph.add_node(chunk_node, type='chunk', source=chunk.get('source', 'unknown'))
            
            for ent in entities:
                # normalize: lowercase and underscores
                ent_clean = ent.lower().strip().replace(" ", "_")
                if len(ent_clean) < 2: continue # skip empty
                
                ent_node = f"ent_{ent_clean}"
                
                # Add entity node and edge
                self.graph.add_node(ent_node, type='entity')
                self.graph.add_edge(chunk_node, ent_node, weight=1.0)
            
                # 3. VERBOSE PRINT (Every Single Chunk)
            elapsed_total = (time.time() - start_global) / 60
            elapsed_chunk = time.time() - chunk_start
            
            print(f"   [{i+1}/{len(chunks)}] Chunk {c_id} done in {elapsed_chunk:.1f}s | Found {len(entities)} concepts")

        print(f"\n✅ BUILD COMPLETE! Total time: {elapsed_total:.1f} minutes")
        return self.graph

# ==========================================
# 3. JSON LOADER (Your Logic)
# ==========================================
def load_improved_chunks(input_path: str) -> List[Dict[str, Any]]:
    """Loads chunks from a SINGLE JSON file OR a directory."""
    all_chunks = []
    path = Path(input_path)
    
    # LOGIC CHANGE: Check if it's a File or Directory
    if path.is_file():
        print(f"📄 Detected single file input: {path.name}")
        files_to_process = [path]
    elif path.is_dir():
        print(f"📂 Detected directory input: {path}")
        files_to_process = list(path.glob("*_improved_chunks.json"))
        if not files_to_process:
            files_to_process = list(path.glob("*.json"))
    else:
        print(f"❌ Error: Path not found -> {input_path}")
        return []

    for chunk_file in files_to_process:
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Handle list vs dict wrapper
            chunks = data if isinstance(data, list) else data.get('chunks', [])
            
            for chunk in chunks:
                chunk['global_id'] = len(all_chunks)
                all_chunks.append(chunk)
                
            print(f"   - Loaded {len(chunks)} chunks from {chunk_file.name}")
        except Exception as e:
            print(f"   ❌ Error loading {chunk_file.name}: {e}")

    print(f"📊 Total chunks loaded: {len(all_chunks)}")
    return all_chunks

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # CONFIGURATION
    CHUNKS_DIR = r"C:\Users\ashesh.gupta\checkpoint1512\backend\internal\internal_0_POL-960_v00_Politica_per_la_Responsabilita_Sociale_chunks_chunks.json"
    OUTPUT_FILE = "hippo_full_llm.graphml"

    # 1. Load Data
    chunks = load_improved_chunks(CHUNKS_DIR)
    
    if chunks:
        # 2. Build Graph
        engine = HippoRAGFullLLM()
        graph = engine.build_full_index(chunks)
        
        # 3. Save Graph
        print(f"💾 Saving graph to '{OUTPUT_FILE}'...")
        nx.write_graphml(graph, OUTPUT_FILE)
        
        # 4. Verification: Print Top 15 Concepts
        print("\n🏆 Top 15 Most Connected Concepts:")
        # Filter for entity nodes (starting with ent_)
        entity_nodes = [n for n in graph.nodes if n.startswith("ent_")]
        # Sort by degree (connection count)
        top_nodes = sorted(entity_nodes, key=lambda n: graph.degree(n), reverse=True)[:15]
        
        for n in top_nodes:
            clean_name = n.replace("ent_", "").replace("_", " ")
            print(f"   - {clean_name} ({graph.degree(n)} links)")