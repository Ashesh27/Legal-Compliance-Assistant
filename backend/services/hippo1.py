import networkx as nx
import spacy
from sentence_transformers import util
import torch
from collections import defaultdict
import os

class HippoRAGLite:
    def __init__(self, nlp_model="it_core_news_sm", embedder=None):
        """
        Enhanced HippoRAG Lite with Multi-Hop Path Reasoning.
        """
        print("🧠 Initializing Upgraded HippoRAG Lite with Paths...")
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

    def extract_entities(self, text):
        """Extracts Named Entities, Noun Chunks, and Dependency Triples."""
        if not text: return []
        
        text_hash = hash(text)
        if text_hash in self.entity_cache:
            return self.entity_cache[text_hash]

        doc = self.nlp(text.lower())
        entities = set()
        
        # Named Entities
        for ent in doc.ents:
            if ent.label_ not in ['DATE', 'CARDINAL', 'ORDINAL', 'PERCENT']:
                entities.add(ent.text.strip())
        
        # Noun Chunks (tech terms)
        for chunk in doc.noun_chunks:
            clean = chunk.text.strip()
            if 1 < len(clean.split()) <= 4:
                entities.add(clean)
        
        results = list(entities)
        self.entity_cache[text_hash] = results
        return results

    def extract_relations(self, text):
        """Extract simple dependency triples for relation edges."""
        doc = self.nlp(text)
        triples = []
        for token in doc:
            if token.dep_ in ['nsubj', 'dobj', 'nsubjpass'] and token.head.pos_ in ['VERB', 'NOUN']:
                subj = token.text.lower().strip()
                rel = token.head.text.lower().strip()
                obj = [child.text.lower().strip() for child in token.head.children 
                       if child.dep_ in ['dobj', 'attr', 'pobj']]
                if obj:
                    triples.append((subj, rel, obj[0]))
        return triples

    def build_index(self, chunks):
        """Builds enriched bipartite KG with relation edges."""
        print(f"🧠 Indexing {len(chunks)} chunks with relations...")
        self.graph.clear()
        self.chunk_map.clear()
        self.entity_cache.clear()
        
        for chunk in chunks:
            c_id = chunk.get('global_id', chunk.get('id'))
            self.chunk_map[c_id] = chunk
            chunk_node = f"chunk_{c_id}"
            self.graph.add_node(chunk_node, type='chunk')
            
            text_to_analyze = f"{chunk.get('section', '')} {chunk.get('text', '')}"
            
            # Entities → Context edges
            entities = self.extract_entities(text_to_analyze)
            for entity in entities:
                ent_node = f"ent_{entity}"
                self.graph.add_node(ent_node, type='entity')
                self.graph.add_edge(chunk_node, ent_node, weight=1.0, type='context')
            
            # Relations → Multi-hop edges
            relations = self.extract_relations(text_to_analyze)
            for subj, rel, obj in relations:
                subj_node = f"ent_{subj}"
                obj_node = f"ent_{obj}"
                self.graph.add_node(subj_node, type='entity')
                self.graph.add_node(obj_node, type='entity')
                self.graph.add_edge(subj_node, obj_node, weight=0.8, type='relation', relation=rel)
        
        # Synonym edges (if embedder)
        self.add_synonym_edges()
        
        self.is_indexed = True
        print(f"✅ Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")

    def add_synonym_edges(self, threshold=0.90):
        """Dense synonym integration."""
        if not self.embedder: 
            print("⚠️ No embedder, skipping synonyms.")
            return
        
        ent_nodes = [n for n in self.graph.nodes if n.startswith("ent_")]
        if len(ent_nodes) < 2: return
        
        labels = [n.replace("ent_", "") for n in ent_nodes]
        embeddings = self.embedder.encode(labels, convert_to_tensor=True)
        cosine_scores = util.cos_sim(embeddings, embeddings)

        for i in range(len(ent_nodes)):
            for j in range(i + 1, len(ent_nodes)):
                score = cosine_scores[i][j].item()
                if score >= threshold:
                    self.graph.add_edge(ent_nodes[i], ent_nodes[j], weight=score, type='synonym')

    def retrieve(self, query_text, top_k=15):
        """Base PPR retrieval (unchanged, normalized)."""
        if not self.is_indexed: return []

        query_entities = self.extract_entities(query_text)
        if not query_entities: return []

        personalization = {f"ent_{ent}": 1.0 for ent in query_entities 
                          if self.graph.has_node(f"ent_{ent}")}
        if not personalization: return []

        try:
            scores = nx.pagerank(self.graph, personalization=personalization, alpha=0.85)
        except: return []

        ranked_chunks = []
        for node, score in scores.items():
            if node.startswith("chunk_"):
                c_id_str = node.split("_", 1)[1]
                try:
                    c_id = int(c_id_str)
                except ValueError:
                    c_id = c_id_str
                
                chunk = self.chunk_map.get(c_id)
                if chunk:
                    ranked_chunks.append({
                        'chunk': chunk, 'score': score,
                        'matched_entities': list(personalization.keys())
                    })

        ranked_chunks.sort(key=lambda x: x['score'], reverse=True)
        
        if ranked_chunks:
            max_s = ranked_chunks[0]['score']
            for r in ranked_chunks:
                r['score'] /= max_s

        return ranked_chunks[:top_k]

    def retrieve_with_path(self, query_text, top_k=15, max_hops=3, max_paths_per_seed=3):
        """
        Multi-hop PPR + Path Extraction for explainable retrieval.
        Approximates HippoRAG's KG path reasoning.
        """
        # Base retrieval (oversample)
        ranked = self.retrieve(query_text, top_k * 2)
        query_ents = self.extract_entities(query_text)
        seeds = [f"ent_{e}" for e in query_ents if self.graph.has_node(f"ent_{e}")]
        
        for item in ranked:
            chunk_node = f"chunk_{item['chunk'].get('global_id', item['chunk'].get('id'))}"
            all_paths = []
            path_scores = []
            
            for seed in seeds:
                if nx.has_path(self.graph, seed, chunk_node):
                    try:
                        # All shortest paths (efficient for small hops)
                        seed_paths = list(nx.all_shortest_paths(self.graph, seed, chunk_node))
                        for path in seed_paths:
                            if 2 <= len(path) <= max_hops + 1:  # Valid path length
                                clean_path = [(n.replace("ent_", ""), 
                                             self.graph.edges[path[i], path[i+1]].get('type', 'context')) 
                                            for i in range(len(path)-1)]
                                all_paths.append(clean_path[-1][0])  # Entity sequence
                                # Score by edge weights (avg)
                                path_weight = sum(self.graph[u][v]['weight'] for u, v in 
                                                zip(path[:-1], path[1:])) / (len(path)-1)
                                path_scores.append(path_weight)
                    except:
                        continue
            
            item['paths'] = all_paths[:max_paths_per_seed * len(seeds)]  # Clean entity paths
            item['path_count'] = len(all_paths)
            item['path_score'] = sum(path_scores) / max(1, len(path_scores))
            # Boost: original score * (1 + normalized path strength)
            item['score'] *= (1 + min(item['path_score'], 1.0))
        
        ranked.sort(key=lambda x: x['score'], reverse=True)
        return ranked[:top_k]
