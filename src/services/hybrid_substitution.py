"""
Phase 1.5 · Hybrid Ingredient Substitution Mapping
─────────────────────────────────────────────────────────
Analyzes BOM contexts AND USDA Nutritional profiles to find substitutes.
Blends the two similarity matrices for a final score.

Dependencies:
    pip install pandas scikit-learn scipy

Usage:
    python hybrid_substitution.py --target "ING-123" --db path/to/db.sqlite
"""

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler
from sklearn.feature_extraction.text import TfidfTransformer

DEFAULT_DB = "/Users/simon/Universitaet/Makeathon/makeathon-2026-spherecast/db.sqlite"
MIN_SIMILARITY = 0.50

# --- HYBRID WEIGHTING ENGINE ---
# Adjust these to lean heavier on one dataset or the other. Must equal 1.0.
BOM_WEIGHT = 0.40
NUTRITION_WEIGHT = 0.60


def load_bom_data(db_path: str) -> pd.DataFrame:
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


def load_nutrition_data(db_path: str) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    query = """
            SELECT p.SKU, pn.Protein_g, pn.Fat_g, pn.Carbs_g, pn.Water_g
            FROM Product_Nutrition pn
                     JOIN Product p ON pn.ProductId = p.Id \
            """
    df = pd.read_sql(query, con)
    con.close()

    # Set SKU as index for easy alignment later
    if not df.empty:
        df.set_index('SKU', inplace=True)
    return df


def calculate_target_substitutes(components: pd.DataFrame, nutrition_df: pd.DataFrame, target_sku: str) -> dict:
    print("      Building BOM-to-Ingredient matrix...")

    # 1. Group ingredients by BOM
    bom_groups = components.groupby("BOMId")["IngredientSKU"].apply(list)

    # 2. Create Binary Matrix
    mlb = MultiLabelBinarizer()
    binary_bom_matrix = mlb.fit_transform(bom_groups)
    ingredient_names = mlb.classes_

    if target_sku not in ingredient_names:
        raise ValueError(f"Error: Target ingredient '{target_sku}' not found in the BOM database.")

    target_idx = np.where(ingredient_names == target_sku)[0][0]

    # Contextual exact overlaps for the Multivitamin trap
    target_exact_co_occur = np.dot(binary_bom_matrix.T, binary_bom_matrix[:, target_idx])
    ingredient_counts = binary_bom_matrix.sum(axis=0)

    # Apply TF-IDF Weighting
    tfidf = TfidfTransformer(norm=None)
    bom_matrix = tfidf.fit_transform(binary_bom_matrix).toarray()

    print(f"      Analyzed {bom_matrix.shape[0]} BOMs and {bom_matrix.shape[1]} Ingredients.")
    print(f"      Computing Contextual Cosine Similarity for {target_sku}...")

    # 3. Calculate Contextual Similarity
    co_occurrence = np.dot(bom_matrix.T, bom_matrix)
    np.fill_diagonal(co_occurrence, 0)
    target_context = co_occurrence[target_idx].reshape(1, -1)

    # Default to handling the zero-division warnings cleanly
    with np.errstate(divide='ignore', invalid='ignore'):
        context_sim_scores = cosine_similarity(target_context, co_occurrence)[0]

    # Clean up NaNs if any vectors were entirely zero
    context_sim_scores = np.nan_to_num(context_sim_scores)

    # 4. Calculate Nutritional Similarity (HYBRID ADDITION)
    if not nutrition_df.empty:
        print("      Computing Nutritional Similarity and Blending Matrices...")
        # Align nutrition rows to the exact order of `ingredient_names`
        # Any missing SKU gets filled with 0s
        aligned_nutrition = nutrition_df.reindex(ingredient_names).fillna(0)

        scaler = StandardScaler()
        # Shape: (num_ingredients, 4)
        nutrition_matrix = scaler.fit_transform(aligned_nutrition[['Protein_g', 'Fat_g', 'Carbs_g', 'Water_g']])

        # Calculate full nutritional sim matrix
        nutritional_sim_matrix = cosine_similarity(nutrition_matrix)
        target_nutritional_sim = nutritional_sim_matrix[target_idx]

        # BLEND THE SCORES
        sim_scores = (context_sim_scores * BOM_WEIGHT) + (target_nutritional_sim * NUTRITION_WEIGHT)
    else:
        print("      [!] No nutrition data found. Falling back to 100% Contextual scoring.")
        sim_scores = context_sim_scores

    # 5. The Multivitamin Trap Fix
    print("      Filtering out Complements (Multivitamin Trap)...")
    for j in range(len(ingredient_names)):
        if target_idx != j:
            co_occur_count = target_exact_co_occur[j]
            if co_occur_count > 0:
                min_occur = min(ingredient_counts[target_idx], ingredient_counts[j])
                overlap_ratio = co_occur_count / min_occur
                if overlap_ratio > 0.1:  # Overlap > 10%
                    sim_scores[j] *= (1.0 - overlap_ratio)

    # 6. Build the output dictionary
    sim_series = pd.Series(sim_scores, index=ingredient_names)
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
        "weights_used": {"bom": BOM_WEIGHT, "nutrition": NUTRITION_WEIGHT},
        "substitutes": sub_list
    }


def print_summary(result: dict):
    target = result["target_sku"]
    subs = result["substitutes"]

    print("\n" + "═" * 80)
    print(f"  HYBRID SUBSTITUTES FOR: {target}")
    print(
        f"  Weights -> BOM: {result['weights_used']['bom'] * 100}%, Nutrition: {result['weights_used']['nutrition'] * 100}%")
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
    parser = argparse.ArgumentParser(description="Find Hybrid Substitutes for a Specific Ingredient")
    parser.add_argument("--target", required=True, help="The SKU to analyze (e.g. 'ING-123')")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to db.sqlite")
    parser.add_argument("--out-dir", default=".", help="Directory to write output")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/4] Loading ingredient data from {args.db} …")
    components = load_bom_data(args.db)
    nutrition_df = load_nutrition_data(args.db)

    print(f"[2/4] Running hybrid substitution math for {args.target} …")
    try:
        result = calculate_target_substitutes(components, nutrition_df, args.target)
    except ValueError as e:
        print(f"\n[!] {e}")
        return

    print("[3/4] Writing output …")
    safe_target = "".join(c for c in args.target if c.isalnum() or c in ('-', '_'))
    out_path = out_dir / f"substitutes_{safe_target}.json"

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"      Successfully saved to -> {out_path}")

    print("[4/4] Summary …")
    print_summary(result)


if __name__ == "__main__":
    main()