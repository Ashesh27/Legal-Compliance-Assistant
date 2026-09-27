import networkx as nx
import spacy
from collections import defaultdict
from sentence_transformers import util
import os


class HippoRAGLite:
    def __init__(self, nlp_model="it_core_news_sm", embedder=None):
        """
        Lightweight Associative Memory Engine (HippoRAG).
        Clean concept-driven GraphRAG implementation.
        """

        print("🧠 Initializing HippoRAG Lite...")

        try:
            self.nlp = spacy.load(nlp_model)
        except OSError:
            print(f"⚠️ Model {nlp_model} not found. Downloading...")
            os.system(f"python -m spacy download {nlp_model}")
            self.nlp = spacy.load(nlp_model)

        self.embedder = embedder
        self.graph = nx.Graph()
        self.chunk_map = {}
        self.entity_cache = {}
        self.is_indexed = False

    # ============================================================
    # ENTITY EXTRACTION
    # ============================================================

    def extract_entities(self, text):
        """Extract meaningful domain concepts from text."""
        if not text:
            return []

        text_hash = hash(text)
        if text_hash in self.entity_cache:
            return self.entity_cache[text_hash]

        doc = self.nlp(text)
        entities = set()

        DROP_ENTITY_TYPES = {
            "DATE", "CARDINAL", "ORDINAL",
            "PERCENT", "ORG", "PERSON", "GPE"
        }

        # --------------------------------------------------------
        # 1️⃣ Named Entities (Controlled)
        # --------------------------------------------------------
        for ent in doc.ents:
            if ent.label_ in DROP_ENTITY_TYPES:
                continue

            clean = ent.text.lower().strip()
            words = clean.split()

            # Allow multi-word entities (2–4 words)
            if 2 <= len(words) <= 4:
                entities.add(clean)

            # Controlled single-word entities
            elif len(words) == 1:
                token = doc[ent.start]

                if (
                    token.pos_ == "NOUN"
                    and not token.is_stop
                    and len(token.text) > 4
                ):
                    entities.add(token.lemma_.lower())

        # --------------------------------------------------------
        # 2️⃣ Noun Chunks (Lemmatized + POS Filtered)
        # --------------------------------------------------------
        for chunk in doc.noun_chunks:

            # Reject chunks starting with ADP/DET/SCONJ
            if chunk[0].pos_ in {"ADP", "DET", "SCONJ"}:
                continue

            # Lemmatize entire chunk
            lemmas = [t.lemma_.lower() for t in chunk]
            clean_chunk = " ".join(lemmas)
            words = clean_chunk.split()

            if not (2 <= len(words) <= 4):
                continue

            # Must contain at least one NOUN
            if not any(t.pos_ == "NOUN" for t in chunk):
                continue

            # Reject chunks with pronouns
            if any(t.pos_ == "PRON" for t in chunk):
                continue

            entities.add(clean_chunk)

        results = list(entities)
        self.entity_cache[text_hash] = results
        return results

    # ============================================================
    # INDEX BUILDING
    # ============================================================

    def build_index(self, chunks):
        """Build Knowledge Graph."""
        print(f"🧠 Indexing {len(chunks)} chunks...")

        self.graph.clear()
        self.chunk_map.clear()
        self.entity_cache.clear()

        for chunk in chunks:
            c_id = chunk.get("global_id", chunk.get("id"))
            self.chunk_map[c_id] = chunk

            chunk_node = f"chunk_{c_id}"
            self.graph.add_node(chunk_node, type="chunk")

            text = f"{chunk.get('section', '')} {chunk.get('text', '')}"
            entities = self.extract_entities(text)

            for entity in entities:
                safe_entity = entity.replace(" ", "_")
                entity_node = f"ent_{safe_entity}"

                self.graph.add_node(entity_node, type="entity")
                self.graph.add_edge(chunk_node, entity_node, weight=1.0)

        # Clean graph
        self.prune_low_degree_entities(min_degree=2)
        self.prune_high_degree_entities(max_ratio=0.4)

        self.is_indexed = True
        print(f"✅ Graph built: {self.graph.number_of_nodes()} nodes")

    # ============================================================
    # GRAPH CLEANING
    # ============================================================

    def prune_low_degree_entities(self, min_degree=2):
        """Remove rare one-off entities."""
        to_remove = []

        for node in self.graph.nodes:
            if node.startswith("ent_") and self.graph.degree(node) < min_degree:
                to_remove.append(node)

        for n in to_remove:
            self.graph.remove_node(n)

        print(f"🧹 Pruned {len(to_remove)} low-degree entities")

    def prune_high_degree_entities(self, max_ratio=0.4):
        """Remove overly dominant entities (boilerplate)."""
        chunk_nodes = [n for n in self.graph.nodes if n.startswith("chunk_")]
        chunk_count = len(chunk_nodes)

        if chunk_count == 0:
            return

        max_degree = chunk_count * max_ratio
        to_remove = []

        for node in self.graph.nodes:
            if node.startswith("ent_") and self.graph.degree(node) > max_degree:
                to_remove.append(node)

        for n in to_remove:
            self.graph.remove_node(n)

        print(f"🔥 Removed {len(to_remove)} dominant entities")

    # ============================================================
    # SYNONYM LINKING
    # ============================================================

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
