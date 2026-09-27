import networkx as nx
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os
import json

class HippoRetriever:
    def __init__(self, graph_path, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        print("🧠 Initializing HippoRAG Retriever...")
        
        # 1. Load Graph
        if not os.path.exists(graph_path):
            raise FileNotFoundError(f"Graph file {graph_path} not found!")
        self.graph = nx.read_graphml(graph_path)
        print(f"   📂 Graph loaded: {self.graph.number_of_nodes()} nodes")
        
        # 2. Load Embedding Model (The "Bridge")
        print(f"   🤖 Loading Model: {model_name}...")
        self.encoder = SentenceTransformer(model_name)
        
        # 3. Pre-Compute Entity Embeddings (Cache)
        # We only embed the RED nodes (Concepts), not the chunks.
        print("   ⚡ Caching entity embeddings...")
        self.entity_nodes = [n for n in self.graph.nodes if n.startswith("ent_")]
        self.entity_names = [n.replace("ent_", "").replace("_", " ") for n in self.entity_nodes]
        
        if self.entity_names:
            self.entity_vectors = self.encoder.encode(self.entity_names, convert_to_tensor=False)
        else:
            self.entity_vectors = []
            print("   ⚠️ Warning: No entity nodes found in graph!")

    def get_semantic_anchors(self, query, top_k=5, threshold=0.4):
        """
        Finds graph nodes that mean the same thing as the query.
        """
        if not self.entity_names: return []
        
        # Encode Query
        query_vec = self.encoder.encode([query])
        
        # Calculate Cosine Similarity
        # (Compare 1 Query vs All Entities)
        similarities = cosine_similarity(query_vec, self.entity_vectors)[0]
        
        # Filter and Sort
        anchors = []
        for idx, score in enumerate(similarities):
            if score >= threshold:
                anchors.append((self.entity_nodes[idx], score))
        
        # Sort by score descending and take top K
        anchors.sort(key=lambda x: x[1], reverse=True)
        return anchors[:top_k]

    def retrieve(self, query, top_k_chunks=5):
        print(f"\n🔍 Processing Query: '{query}'")
        
        # Step 1: Find Anchors (The "Ink Drop" spots)
        anchors = self.get_semantic_anchors(query)
        if not anchors:
            print("   ❌ No relevant concepts found in graph.")
            return []
            
        print(f"   ⚓ Anchoring on {len(anchors)} concepts:")
        personalization = {}
        for node, score in anchors:
            print(f"      - {node.replace('ent_','')} (Sim: {score:.3f})")
            # We weight the ink drop by similarity score!
            # A perfect match gets more ink than a weak match.
            personalization[node] = float(score) 

        # Step 2: Run Personalized PageRank (The "Flow")
        print("   🌊 Running PageRank Flow...")
        try:
            # Alpha 0.85 = typical damping factor (85% follow links, 15% restart)
            ppr_scores = nx.pagerank(self.graph, personalization=personalization, alpha=0.85)
        except Exception as e:
            print(f"   ⚠️ PageRank Error: {e}")
            return []

        # Step 3: Extract and Rank Chunks
        chunk_results = []
        for node, score in ppr_scores.items():
            if node.startswith("chunk_"):
                chunk_results.append((node, score))
        
        # Sort by PPR Score
        chunk_results.sort(key=lambda x: x[1], reverse=True)
        
        return chunk_results[:top_k_chunks]

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # CONFIGURATION
    GRAPH_FILE = r"C:\Users\ashesh.gupta\checkpoint1102\backend\services\hippo_full_llm.graphml" 
    TEST_QUERY = "L'organizzazione deve raggiungere la conformità allo Standard SA8000 attraverso l'implementazione e il mantenimento di un sistema di gestione adeguato ed efficace."

    # Initialize
    retriever = HippoRetriever(GRAPH_FILE)
    
    # Run
    results = retriever.retrieve(TEST_QUERY)
    
    print("\n🏆 Final Retrieved Chunks:")
    for rank, (chunk_id, score) in enumerate(results):
        print(f"   #{rank+1} [{chunk_id}] (Score: {score:.4f})")