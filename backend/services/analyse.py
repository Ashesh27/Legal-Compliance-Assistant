import json
import glob
import numpy as np

def analyze_hipporag_impact(output_dir):
    json_files = glob.glob(f"{output_dir}/*.json")
    if not json_files:
        print("No results found.")
        return

    print(f"📊 Analyzing Impact in: {json_files[0]}")
    with open(json_files[0], 'r', encoding='utf-8') as f:
        results = json.load(f)

    total_reqs = len(results)
    hippo_wins = 0
    hippo_boosts = 0
    
    for req in results:
        # Check the top 3 matches
        top_matches = req['matches'][:3]
        
        found_by_hippo = False
        for m in top_matches:
            if 'hipporag' in m.get('source', '').lower():
                found_by_hippo = True
                
        if found_by_hippo:
            hippo_wins += 1
            
    print("\n📈 HippoRAG Impact Report")
    print("="*40)
    print(f"Total Requirements: {total_reqs}")
    print(f"Reqs with HippoRAG in Top 3: {hippo_wins} ({hippo_wins/total_reqs*100:.1f}%)")
    print("="*40)
    
    if hippo_wins > 0:
        print("✅ SUCCESS: The graph is actively retrieving relevant context.")
    else:
        print("⚠️ NOTE: HippoRAG didn't change the top results. Check if entity extraction is working.")

if __name__ == "__main__":
    # Point to your output directory
    OUTPUT_DIR = "/home/ashesh_kumar_gupta/output/mappingFAQ_Accredia_PdR125_improved_hippo"
    analyze_hipporag_impact(OUTPUT_DIR)