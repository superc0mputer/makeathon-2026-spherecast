"""
Phase 1 · Ingredient Substitution Mapping (Single Target)
─────────────────────────────────────────────────────────
Analyzes BOMs to determine the "context" of a target raw material.
Uses Cosine Similarity to find ingredients that share identical contexts,
flagging them as potential substitutes.

Outputs:
  - substitutes_[TARGET_SKU].json   Maps the target RM to its substitutes.

Dependencies:
    pip install pandas scikit-learn scipy

Usage:
    python ingredient_substitution.py --target "ING-123" --db path/to/db.sqlite
"""

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.feature_extraction.text import TfidfTransformer

DEFAULT_DB = "../db.sqlite"

# Minimum similarity score (0.0 to 1.0) to be considered a viable substitute
MIN_SIMILARITY = 0.50

def load_data(db_path: str) -> pd.DataFrame:
    con = sqlite3.connect(db_path)

    # We only care about BOMs and Raw Materials for substitution logic.
    query = """
        SELECT bc.BOMId, p.SKU AS IngredientSKU 
        FROM BOM_Component bc 
        JOIN Product p ON bc.ConsumedProductId = p.Id
        WHERE p.Type = 'raw-material'
    """
    components = pd.read_sql(query, con)
    con.close()

    return components


def calculate_target_substitutes(components: pd.DataFrame, target_sku: str) -> dict:
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

    # Get exact co-occurrence counts for the target against all others
    # and total usage counts for the Multivitamin Trap fix
    target_exact_co_occur = np.dot(binary_bom_matrix.T, binary_bom_matrix[:, target_idx])
    ingredient_counts = binary_bom_matrix.sum(axis=0)

    # Apply TF-IDF Weighting
    tfidf = TfidfTransformer(norm=None)
    bom_matrix = tfidf.fit_transform(binary_bom_matrix).toarray()

    print(f"      Analyzed {bom_matrix.shape[0]} BOMs and {bom_matrix.shape[1]} Ingredients.")
    print(f"      Calculating contextual co-occurrence for {target_sku}...")

    # 3. Create Context Matrix (Rows = Ingredients, Cols = Ingredients)
    co_occurrence = np.dot(bom_matrix.T, bom_matrix)
    np.fill_diagonal(co_occurrence, 0)

    print(f"      Computing Cosine Similarity for {target_sku}...")

    # 4. Calculate Contextual Similarity (Target vs All)
    target_context = co_occurrence[target_idx].reshape(1, -1)
    sim_scores = cosine_similarity(target_context, co_occurrence)[0]

    # 4.5. The Multivitamin Trap Fix (Only loop over the target's relationships)
    print("      Filtering out Complements (Multivitamin Trap)...")
    for j in range(len(ingredient_names)):
        if target_idx != j:
            co_occur_count = target_exact_co_occur[j]
            if co_occur_count > 0:
                min_occur = min(ingredient_counts[target_idx], ingredient_counts[j])
                overlap_ratio = co_occur_count / min_occur
                if overlap_ratio > 0.1: # If they overlap > 10% of the time, they are complements
                    sim_scores[j] *= (1.0 - overlap_ratio)

    # 5. Build the output dictionary
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
        "substitutes": sub_list
    }


def print_summary(result: dict):
    target = result["target_sku"]
    subs = result["substitutes"]

    print("\n" + "═" * 80)
    print(f"  SUBSTITUTES FOR: {target}")
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
    parser = argparse.ArgumentParser(description="Find Substitutes for a Specific Ingredient")
    parser.add_argument("--target", required=True, help="The SKU of the ingredient to analyze (e.g. 'ING-123')")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to db.sqlite")
    parser.add_argument("--out-dir", default=".", help="Directory to write output")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/4] Loading ingredient data from {args.db} …")
    components = load_data(args.db)

    print(f"[2/4] Running substitution math for {args.target} …")
    try:
        result = calculate_target_substitutes(components, args.target)
    except ValueError as e:
        print(f"\n[!] {e}")
        return

    print("[3/4] Writing output …")
    # Clean the filename in case the SKU has weird characters
    safe_target = "".join(c for c in args.target if c.isalnum() or c in ('-', '_'))
    out_path = out_dir / f"substitutes_{safe_target}.json"

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"      Successfully saved to -> {out_path}")

    print("[4/4] Summary …")
    print_summary(result)


if __name__ == "__main__":
    main()