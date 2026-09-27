import pandas as pd
import numpy as np

def compare_results(normal_file, hippo_file):
    print(f"⚖️ COMPARING:\n  A: {normal_file}\n  B: {hippo_file}\n")
    
    try:
        df_norm = pd.read_excel(normal_file)
        df_hippo = pd.read_excel(hippo_file)
    except Exception as e:
        print(f"❌ Error loading files: {e}")
        return

    # 1. Check Retrieval Differences (Did we find NEW documents?)
    changed_reqs = 0
    total_new_docs = 0
    
    for i in range(len(df_norm)):
        # Extract the list of retrieved files from the cell text
        norm_docs = set(df_norm.iloc[i]['MAPPING DOCUMENTI INTERNI'].split('\n'))
        hippo_docs = set(df_hippo.iloc[i]['MAPPING DOCUMENTI INTERNI'].split('\n'))
        
        # Calculate difference
        new_in_hippo = hippo_docs - norm_docs
        
        if new_in_hippo:
            changed_reqs += 1
            total_new_docs += len(new_in_hippo)
            print(f"📍 Req {i+1} Change:")
            for doc in new_in_hippo:
                if "File:" in doc: # Filter for file lines only
                    print(f"   ➕ Hippo Found: {doc.strip()}")

    # 2. Check Analysis Differences (Did the LLM change its mind?)
    verdict_changes = 0
    for i in range(len(df_norm)):
        score_norm = str(df_norm.iloc[i]['LIVELLO'])
        score_hippo = str(df_hippo.iloc[i]['LIVELLO'])
        
        if score_norm != score_hippo:
            verdict_changes += 1
            print(f"🧠 LLM Verdict Change on Req {i+1}: {score_norm} -> {score_hippo}")

    print("\n" + "="*40)
    print("📊 IMPACT SUMMARY")
    print("="*40)
    print(f"Total Requirements: {len(df_norm)}")
    print(f"Requirements with NEW Docs: {changed_reqs} ({(changed_reqs/len(df_norm))*100:.1f}%)")
    print(f"LLM Verdicts Changed:       {verdict_changes}")
    print("="*40)

if __name__ == "__main__":
    # Update these paths to your actual files
    NORMAL = "/home/ashesh_kumar_gupta/output/mappingFAQ_Accredia_PdR125_improved/mapping_results.xlsx"
    HIPPO = "/home/ashesh_kumar_gupta/output/mappingFAQ_Accredia_PdR125_improved_hippo/mapping_results.xlsx"
    compare_results(NORMAL, HIPPO)