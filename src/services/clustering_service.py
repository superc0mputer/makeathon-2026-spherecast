"""
Phase 1 · Hybrid Ingredient Substitution Mapping
─────────────────────────────────────────────────────────
Combines BOM Co-occurrence, FDC Nutritional Features, and PubChem
Chemical Features into a single weighted Cosine Similarity score.
"""

import argparse
import json
import sqlite3
import sys
import os
from pathlib import Path

from sklearn.feature_extraction.text import TfidfTransformer

# Fix local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer, MinMaxScaler

from src.services.supplier_db_service import ingredient_name_from_sku
from src.services.fdc_service import FDCService
from src.services.pubchem_service import enrich_ingredient

DEFAULT_DB = "db/db.sqlite"
MIN_SIMILARITY = 0.40


WEIGHT_BOM = 0.20
WEIGHT_CHEM = 0.25
WEIGHT_FDC = 0.35
WEIGHT_TEXT = 0.20

def load_data(db_path: str) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    query = """
            SELECT bc.BOMId, p.SKU AS IngredientSKU
            FROM BOM_Component bc
                     JOIN Product p ON bc.ConsumedProductId = p.Id
            WHERE p.Type = 'raw-material' \
            """
    components = pd.read_sql(query, con)
    con.close()
    return components


def extract_numerical_value(val_str: str) -> float:
    """Extract numeric value from strings like '64.0 kJ'"""
    try:
        parts = str(val_str).split()
        if len(parts) > 0:
            return float(parts[0])
    except:
        pass
    return 0.0


# ==========================================
# 1. TARGETED SUBSTITUTION (1 x N)
# ==========================================
def calculate_target_substitutes(components: pd.DataFrame, target_sku: str) -> dict:
    fdc_service = FDCService()

    print("      [1/3] Building BOM-to-Ingredient matrix...")
    bom_groups = components.groupby("BOMId")["IngredientSKU"].apply(list)
    mlb = MultiLabelBinarizer()
    binary_bom_matrix = mlb.fit_transform(bom_groups)
    ingredient_skus = mlb.classes_

    if target_sku not in ingredient_skus:
        raise ValueError(f"Error: Target ingredient '{target_sku}' not found in the BOM database.")

    target_idx = np.where(ingredient_skus == target_sku)[0][0]

    # BOM Similarities
    tfidf = TfidfTransformer(norm='l2')
    bom_matrix = tfidf.fit_transform(binary_bom_matrix).toarray()
    co_occurrence = np.dot(bom_matrix.T, bom_matrix)

    np.fill_diagonal(co_occurrence, 0)

    target_context = co_occurrence[target_idx].reshape(1, -1)

    # Safety Check: If the target never appears with any other ingredient
    if not np.any(target_context):
        print(f"        [!] Warning: {target_sku} shares no context. BOM score will be 0.")
        bom_sim_scores = np.zeros(len(ingredient_skus))
    else:
        bom_sim_scores = cosine_similarity(target_context, co_occurrence)[0]

    # Multivitamin Trap Fix (Optimized)
    ingredient_counts = binary_bom_matrix.sum(axis=0)
    for j in range(len(ingredient_skus)):
        if target_idx != j:
            co_occur_count = co_occurrence[target_idx, j]
            if co_occur_count > 0:
                min_occur = min(ingredient_counts[target_idx], ingredient_counts[j])
                overlap_ratio = co_occur_count / min_occur
                if overlap_ratio > 0.1:
                    bom_sim_scores[j] *= (1.0 - overlap_ratio)

    print("      [2/3] Extracting PubChem Chemical Feature Vectors...")
    chem_features = []
    fdc_features = []

    names_mapped = [ingredient_name_from_sku(sku) for sku in ingredient_skus]

    
    for i, name in enumerate(names_mapped):
        if i % 25 == 0 or i == len(names_mapped) - 1:
            print(f"        ...fetching profile {i+1}/{len(names_mapped)}: {name} (can be slow without cache)")
            
        # PubChem
        profile = enrich_ingredient(name)
        chem_vec = [
            profile.molecular_weight or 0.0,
            profile.xlogp or 0.0,
            float(profile.is_salt),
            float(profile.is_organic),
            float(profile.charge or 0.0)
        ]
        chem_features.append(chem_vec)

        # FDC
        fdc_data = fdc_service.get_nutritional_profile(name)
        fdc_vec = [0.0, 0.0, 0.0, 0.0]
        if fdc_data.get("status") == "resolved":
            nutrients = fdc_data["profile"].get("nutrients", {})
            kcal_str = str(nutrients.get("Energy", "0"))
            pro_str = str(nutrients.get("Protein", "0"))
            fat_str = str(nutrients.get("Total lipid (fat)", "0"))
            carb_str = str(nutrients.get("Carbohydrate, by difference", "0"))

            fdc_vec = [
                extract_numerical_value(kcal_str),
                extract_numerical_value(pro_str),
                extract_numerical_value(fat_str),
                extract_numerical_value(carb_str)
            ]
        fdc_features.append(fdc_vec)

    chem_matrix = np.array(chem_features)
    fdc_matrix = np.array(fdc_features)

    scaler = MinMaxScaler()
    chem_norm = np.nan_to_num(scaler.fit_transform(chem_matrix))
    fdc_norm = np.nan_to_num(scaler.fit_transform(fdc_matrix))

    print("      [3/3] Calculating Hybrid Multi-Dimensional Cosine Similarity...")

    target_chem = chem_norm[target_idx].reshape(1, -1)
    if np.any(target_chem) and np.any(chem_norm):
        chem_sim_scores = cosine_similarity(target_chem, chem_norm)[0]
    else:
        chem_sim_scores = np.zeros(len(ingredient_skus))

    target_fdc = fdc_norm[target_idx].reshape(1, -1)
    if np.any(target_fdc) and np.any(fdc_norm):
        fdc_sim_scores = cosine_similarity(target_fdc, fdc_norm)[0]
    else:
        fdc_sim_scores = np.zeros(len(ingredient_skus))
        
    import difflib
    text_sim_scores = np.zeros(len(ingredient_skus))
    
    target_chem_raw_sum = np.sum(np.abs(chem_matrix[target_idx]))
    target_fdc_raw_sum = np.sum(np.abs(fdc_matrix[target_idx]))
    
    target_name_normalized = names_mapped[target_idx].lower()

    # Penalize "similarity by absence" and score text
    for j in range(len(ingredient_skus)):
        # 1. Text Similarity Score
        seq = difflib.SequenceMatcher(None, target_name_normalized, names_mapped[j].lower())
        text_sim_scores[j] = seq.ratio()
        
        # 2. Absence Penalty (if target OR candidate lacks data entirely, zero out the similarity)
        if target_chem_raw_sum == 0.0 or np.sum(np.abs(chem_matrix[j])) == 0.0:
            chem_sim_scores[j] = 0.0
            
        if target_fdc_raw_sum == 0.0 or np.sum(np.abs(fdc_matrix[j])) == 0.0:
            fdc_sim_scores[j] = 0.0

    # Apply Weights
    final_hybrid_scores = (

        (bom_sim_scores * WEIGHT_BOM) + 
        (chem_sim_scores * WEIGHT_CHEM) + 
        (fdc_sim_scores * WEIGHT_FDC) +
        (text_sim_scores * WEIGHT_TEXT)
    )

    print("      Applying Biochemical Ontology Filter (Class vs. Component)...")
    ontology = {
        "b vitamins": ["thiamine", "riboflavin", "niacin", "pantothenic acid", "pyridoxine", "biotin", "folate",
                       "cobalamin", "b1", "b2", "b3", "b5", "b6", "b7", "b9", "b12"],
        "vitamin c complex": ["ascorbic acid", "rutin", "hesperidin", "bioflavonoids"],
        "amino acid blend": ["leucine", "isoleucine", "valine", "glutamine", "arginine"],
        "tocopherols": ["alpha-tocopherol", "beta-tocopherol", "gamma-tocopherol", "delta-tocopherol"]
    }

    target_lower = names_mapped[target_idx].lower()
    for j in range(len(ingredient_skus)):
        sub_sku = names_mapped[j].lower()
        for parent, children in ontology.items():
            parent_key = parent.replace(" ", "-")
            if parent_key in target_lower or parent in target_lower:
                for child in children:
                    child_key = child.replace(" ", "-")
                    if child_key in sub_sku or child in sub_sku:
                        final_hybrid_scores[j] = 0.0
            for child in children:
                child_key = child.replace(" ", "-")
                if child_key in target_lower or child in target_lower:
                    if parent_key in sub_sku or parent in sub_sku:
                        final_hybrid_scores[j] = 0.0

    sim_series = pd.Series(final_hybrid_scores, index=ingredient_skus)
    similarities = sim_series.drop(target_sku).sort_values(ascending=False)

    valid_subs = similarities[similarities >= MIN_SIMILARITY]

    sub_list = []
    for sub_sku, score in valid_subs.items():
        sub_list.append({
            "sku": sub_sku,
            "similarity_score": round(float(score), 4)
        })

    return {
        "target_sku": target_sku,
        "total_viable_substitutes": len(sub_list),
        "substitutes": sub_list[:5]
    }


# ==========================================
# 2. GLOBAL CLUSTERING (N x N)
# ==========================================
def calculate_all_similarities(components: pd.DataFrame) -> list:
    fdc_service = FDCService()

    print("      [1/3] Building global BOM-to-Ingredient matrix...")
    bom_groups = components.groupby("BOMId")["IngredientSKU"].apply(list)
    mlb = MultiLabelBinarizer()
    binary_bom_matrix = mlb.fit_transform(bom_groups)
    ingredient_skus = mlb.classes_
    n_skus = len(ingredient_skus)

    # 1. Global BOM Similarity (N x N Matrix)
    co_occurrence = np.dot(binary_bom_matrix.T, binary_bom_matrix)
    np.fill_diagonal(co_occurrence, 0)

    bom_sim_matrix = cosine_similarity(co_occurrence)

    # Vectorized Multivitamin Trap Fix for N x N
    counts = binary_bom_matrix.sum(axis=0)
    min_occur_matrix = np.minimum.outer(counts, counts)

    with np.errstate(divide='ignore', invalid='ignore'):
        overlap_ratio = co_occurrence / min_occur_matrix
        overlap_ratio = np.nan_to_num(overlap_ratio)

    penalty_mask = overlap_ratio > 0.1
    bom_sim_matrix[penalty_mask] *= (1.0 - overlap_ratio[penalty_mask])

    # 2. Extract Chem and FDC Features globally
    print(f"      [2/3] Extracting Features for {n_skus} ingredients...")
    chem_features = []
    fdc_features = []

    names_mapped = [ingredient_name_from_sku(sku) for sku in ingredient_skus]

    for i, name in enumerate(names_mapped):
        if i % 25 == 0 or i == n_skus - 1:
            print(f"        ...fetching profile {i + 1}/{n_skus}: {name}")

        profile = enrich_ingredient(name)
        chem_vec = [
            profile.molecular_weight or 0.0,
            profile.xlogp or 0.0,
            float(profile.is_salt),
            float(profile.is_organic),
            float(profile.charge or 0.0)
        ]
        chem_features.append(chem_vec)

        fdc_data = fdc_service.get_nutritional_profile(name)
        fdc_vec = [0.0, 0.0, 0.0, 0.0]
        if fdc_data.get("status") == "resolved":
            nutrients = fdc_data["profile"].get("nutrients", {})
            kcal_str = str(nutrients.get("Energy", "0"))
            pro_str = str(nutrients.get("Protein", "0"))
            fat_str = str(nutrients.get("Total lipid (fat)", "0"))
            carb_str = str(nutrients.get("Carbohydrate, by difference", "0"))

            fdc_vec = [
                extract_numerical_value(kcal_str),
                extract_numerical_value(pro_str),
                extract_numerical_value(fat_str),
                extract_numerical_value(carb_str)
            ]
        fdc_features.append(fdc_vec)

    chem_matrix = np.array(chem_features)
    fdc_matrix = np.array(fdc_features)

    scaler = MinMaxScaler()
    chem_norm = np.nan_to_num(scaler.fit_transform(chem_matrix))
    fdc_norm = np.nan_to_num(scaler.fit_transform(fdc_matrix))

    # 3. Calculate Global Similarities (N x N)
    print("      [3/3] Calculating Global Hybrid Similarity Matrix...")
    chem_sim_matrix = cosine_similarity(chem_norm)
    fdc_sim_matrix = cosine_similarity(fdc_norm)

    hybrid_matrix = (
            (bom_sim_matrix * WEIGHT_BOM) +
            (chem_sim_matrix * WEIGHT_CHEM) +
            (fdc_sim_matrix * WEIGHT_FDC)
    )

    # 4. Apply Ontology Filter
    print("      Applying Biochemical Ontology Filter globally...")
    ontology = {
        "b vitamins": ["thiamine", "riboflavin", "niacin", "pantothenic acid", "pyridoxine", "biotin", "folate",
                       "cobalamin", "b1", "b2", "b3", "b5", "b6", "b7", "b9", "b12"],
        "vitamin c complex": ["ascorbic acid", "rutin", "hesperidin", "bioflavonoids"],
        "amino acid blend": ["leucine", "isoleucine", "valine", "glutamine", "arginine"],
        "tocopherols": ["alpha-tocopherol", "beta-tocopherol", "gamma-tocopherol", "delta-tocopherol"]
    }

    names_lower = [name.lower() for name in names_mapped]
    for i in range(n_skus):
        name_i = names_lower[i]
        for j in range(i + 1, n_skus):
            if hybrid_matrix[i, j] < MIN_SIMILARITY:
                continue
            name_j = names_lower[j]

            violation = False
            for parent, children in ontology.items():
                parent_key = parent.replace(" ", "-")
                if (parent_key in name_i or parent in name_i) and any(
                        (c.replace(" ", "-") in name_j or c in name_j) for c in children):
                    violation = True;
                    break
                if (parent_key in name_j or parent in name_j) and any(
                        (c.replace(" ", "-") in name_i or c in name_i) for c in children):
                    violation = True;
                    break

            if violation:
                hybrid_matrix[i, j] = 0.0

    # 5. Extract Final Edges
    print("      Extracting final network edges...")
    edges = []
    for i in range(n_skus):
        for j in range(i + 1, n_skus):
            score = hybrid_matrix[i, j]
            if score >= MIN_SIMILARITY:
                edges.append((ingredient_skus[i], ingredient_skus[j], float(score)))

    return edges


def print_summary(result: dict):
    target = result.get("target_sku", "GLOBAL")
    subs = result.get("substitutes", [])

    print("\n" + "═" * 80)
    print(f"  HYBRID SUBSTITUTES FOR: {target}")
    print("═" * 80)

    if not subs:
        print(f"  No viable substitutes found (Similarity >= {MIN_SIMILARITY}).")
    else:
        print("  Score │ SKU")
        print("  ──────┼────────────────────────────────────────")
        for sub in subs:
            print(f"  {sub['similarity_score']:.3f} │ {sub['sku']}")

    print("═" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Find Hybrid Substitutes")
    parser.add_argument("--target", required=False, help="The SKU of the ingredient to analyze")
    parser.add_argument("--all", action="store_true", help="Generate JSON of all global connections")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to db.sqlite")
    parser.add_argument("--out-dir", default=".", help="Directory to write output")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    components = load_data(args.db)

    if args.all:
        edges = calculate_all_similarities(components)
        out_path = out_dir / "global_substitutes.json"

        # Save the global edges to JSON
        edge_data = [{"source": u, "target": v, "score": round(s, 4)} for u, v, s in edges]
        with open(out_path, "w") as f:
            json.dump(edge_data, f, indent=2)

        print(f"\n✅ Global edges saved to {out_path}")

    elif args.target:
        try:
            result = calculate_target_substitutes(components, args.target)
        except ValueError as e:
            print(f"\n[!] {e}")
            return

        safe_target = "".join(c for c in args.target if c.isalnum() or c in ('-', '_'))
        out_path = out_dir / f"substitutes_{safe_target}.json"

        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)

        print_summary(result)

    else:
        print("❌ Error: Please provide either --target <SKU> or --all")


if __name__ == "__main__":
    main()