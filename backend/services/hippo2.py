import networkx as nx
import spacy
import os
import re
import json
from collections import defaultdict
from sentence_transformers import util
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_provider import llm_chat
class HippoRAGLite:
    def __init__(self, nlp_model="it_core_news_sm", embedder=None):
        print("🧠 Initializing HippoRAG Lite (Hybrid LLM Filter)...")
        try:
            self.nlp = spacy.load(nlp_model)
        except OSError:
            os.system(f"python -m spacy download {nlp_model}")
            self.nlp = spacy.load(nlp_model)

        self.embedder = embedder
        self.graph = nx.Graph()
        self.chunk_map = {}
        self.is_indexed = False

    def extract_entities(self, text):
        """Extracts candidate concepts using linguistic rules."""
        if not text: return []
        doc = self.nlp(text)
        entities = set()

        for chunk in doc.noun_chunks:
            # Linguistic Filter: Skip chunks starting with prepositions/conjunctions
            if chunk[0].pos_ in {"ADP", "DET", "SCONJ"}:
                continue
            
            # POS Filter: Ensure the root is a Noun (Kills 'Ove')
            if chunk.root.pos_ not in ["NOUN", "PROPN"]:
                continue

            clean = chunk.text.lower().strip()
            if 2 <= len(clean.split()) <= 4:
                entities.add(clean)
        return list(entities)

    def filter_nodes_with_llm(self, candidates, llm_chat):
        """Uses LLM to identify 'Junk' nodes in a single batch call."""
        if not candidates: return set()
        
        system_prompt = (
            "Sei un esperto di data cleaning. Ti fornirò un elenco di concetti estratti da documenti di compliance. "
            "Identifica i termini che sono 'RUMORE' (nomi di aziende come Lutech, città come Bari, prepositions come 'ove', "
            "o termini generici svuotati di significato). "
            "Restituisci SOLO una lista JSON dei termini da eliminare."
        )
        
        try:
            # Process in one batch to save time/cost
            response = llm_chat(
                model="qwen3:4b-instruct-2507-q4_K_M", # Or your preferred local model
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Lista: {json.dumps(candidates)}"}
                ]
            )
            content = response.get("message", {}).get("content", "")
            match = re.search(r'\[.*\]', content, re.DOTALL)
            return set(json.loads(match.group(0))) if match else set()
        except Exception as e:
            print(f"⚠️ LLM Filter Error: {e}")
            return set()

    def build_index(self, chunks, llm_chat):
        """Builds graph and applies LLM-driven pruning."""
        self.graph.clear()
        self.chunk_map.clear()
        
        print(f"🧠 Step 1: Extracting nodes from {len(chunks)} chunks...")
        raw_entity_map = {}
        global_counts = defaultdict(int)

        for chunk in chunks:
            c_id = chunk.get("global_id", chunk.get("id"))
            self.chunk_map[c_id] = chunk
            ents = self.extract_entities(f"{chunk.get('section', '')} {chunk.get('text', '')}")
            raw_entity_map[c_id] = ents
            for e in set(ents): global_counts[e] += 1

        # Step 2: Semantic Filtering via LLM (Customer-Agnostic)
        candidates = [ent for ent, count in global_counts.items() if count >= 1]
        junk_nodes = self.filter_nodes_with_llm(candidates, llm_chat)
        print(f"✂️ LLM identified {len(junk_nodes)} junk concepts (e.g., Lutech, Bari, Ove).")

        # Step 3: Build the Clean Graph
        for c_id, ents in raw_entity_map.items():
            chunk_node = f"chunk_{c_id}"
            for e in ents:
                if e in junk_nodes: continue
                
                # Statistical Pruning (Safety Net)
                if global_counts[e] > (len(chunks) * 0.4): continue

                entity_node = f"ent_{e.replace(' ', '_')}"
                # TF-IDF style weighting for edges
                weight = 1.0 / (global_counts[e] ** 0.5)
                self.graph.add_edge(chunk_node, entity_node, weight=weight)

        self.is_indexed = True
        print(f"✅ Graph built: {self.graph.number_of_nodes()} nodes.")


    def add_synonym_edges(self, threshold=0.90):
        """Link semantically similar entity nodes."""
        if not self.embedder:
            print("⚠️ No embedder provided.")
            return

        ent_nodes = [n for n in self.graph.nodes if n.startswith("ent_")]
        if len(ent_nodes) < 2:
            return

        labels = [n.replace("ent_", "").replace("_", " ") for n in ent_nodes]
        embeddings = self.embedder.encode(labels, convert_to_tensor=True)
        cosine_scores = util.cos_sim(embeddings, embeddings)

        for i in range(len(ent_nodes)):
            for j in range(i + 1, len(ent_nodes)):
                score = cosine_scores[i][j].item()
                if score >= threshold:
                    self.graph.add_edge(
                        ent_nodes[i],
                        ent_nodes[j],
                        weight=score * 0.5,  # weaker than chunk edges
                        type="synonym"
                    )

        print("🔗 Synonym edges added")

    # ============================================================
    # RETRIEVAL
    # ============================================================

    def retrieve(self, query_text, top_k=15):
        """Retrieve chunks using Personalized PageRank."""
        if not self.is_indexed:
            return []

        query_entities = self.extract_entities(query_text)
        if not query_entities:
            return []

        personalization = {}
        active_seeds = []

        for ent in query_entities:
            safe_ent = ent.replace(" ", "_")
            node_id = f"ent_{safe_ent}"

            if self.graph.has_node(node_id):
                personalization[node_id] = 1.0
                active_seeds.append(ent)

        if not personalization:
            return []

        scores = nx.pagerank(
            self.graph,
            personalization=personalization,
            alpha=0.85,
            weight="weight"
        )

        ranked_chunks = []

        for node, score in scores.items():
            if node.startswith("chunk_"):
                c_id_str = node.split("_", 1)[1]

                try:
                    c_id = int(c_id_str)
                except ValueError:
                    c_id = c_id_str

                original_chunk = self.chunk_map.get(c_id)

                if original_chunk:
                    ranked_chunks.append({
                        "chunk": original_chunk,
                        "score": score,
                        "matched_entities": active_seeds
                    })

        ranked_chunks.sort(key=lambda x: x["score"], reverse=True)

        # Normalize scores
        if ranked_chunks:
            max_score = ranked_chunks[0]["score"]
            for r in ranked_chunks:
                r["score"] /= max_score

        return ranked_chunks[:top_k]
