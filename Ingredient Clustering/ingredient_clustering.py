"""
Phase 1 · Ingredient Substitution Mapping
─────────────────────────────────────────
Analyzes BOMs to determine the "context" of every raw material (what other
ingredients it frequently co-occurs with). Uses Cosine Similarity to find
ingredients that share identical contexts, flagging them as potential substitutes.

Outputs:
  - substitution_map.json   Maps every RM to its closest statistical substitutes.

Dependencies:
    pip install pandas scikit-learn scipy

Usage:
    python ingredient_substitution.py --db path/to/db.sqlite
"""

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.feature_extraction.text import TfidfTransformer, TfidfVectorizer

DEFAULT_DB = "../db.sqlite"

# Minimum similarity score (0.0 to 1.0) to be considered a viable substitute
MIN_SIMILARITY = 0.50

def load_data(db_path: str) -> pd.DataFrame:
    con = sqlite3.connect(db_path)

    # We only care about BOMs and Raw Materials for substitution logic.
    # Exclude packaging, scoops, labels, etc.
    query = """
        SELECT bc.BOMId, p.SKU AS IngredientSKU 
        FROM BOM_Component bc 
        JOIN Product p ON bc.ConsumedProductId = p.Id
        WHERE p.Type = 'raw-material'
    """
    components = pd.read_sql(query, con)
    con.close()

    return components


def calculate_substitutes(components: pd.DataFrame) -> dict:
    print("      Building BOM-to-Ingredient matrix...")

    # 1. Group ingredients by BOM
    bom_groups = components.groupby("BOMId")["IngredientSKU"].apply(list)

    # 2. Create Binary Matrix (Rows = BOMs, Columns = Ingredients)
    mlb = MultiLabelBinarizer()
    binary_bom_matrix = mlb.fit_transform(bom_groups)
    ingredient_names = mlb.classes_

    # Get exact co-occurrence counts to penalize complements (ingredients in the SAME BOM)
    exact_co_occurrence = np.dot(binary_bom_matrix.T, binary_bom_matrix)
    ingredient_counts = np.diag(exact_co_occurrence)

    # Apply TF-IDF Weighting to reduce noise from generic ingredients (Salt, Silica)
    # Using norm=None preserves raw overlap magnitudes but scales by global rarity
    tfidf = TfidfTransformer(norm=None)
    bom_matrix = tfidf.fit_transform(binary_bom_matrix).toarray()

    print(f"      Analyzed {bom_matrix.shape[0]} BOMs and {bom_matrix.shape[1]} Ingredients.")
    print("      Calculating contextual co-occurrence...")

    # 3. Create Context Matrix (Rows = Ingredients, Cols = Ingredients)
    # This matrix tells us how much the contextual environments overlap
    co_occurrence = np.dot(bom_matrix.T, bom_matrix)
    np.fill_diagonal(co_occurrence, 0)

    print("      Computing Cosine Similarity to find substitutes...")

    # 4. Calculate Contextual Similarity
    sim_matrix = cosine_similarity(co_occurrence)

    # 4.5. The Multivitamin Trap Fix
    # True substitutes share the same context but rarely appear IN THE SAME BOM.
    # If they appear together often, they are Complements (e.g. Lycopene + Sodium Benzoate in a premix).
    print("      Filtering out Complements (Multivitamin Trap)...")
    for i in range(len(ingredient_names)):
        for j in range(len(ingredient_names)):
            if i != j:
                # If they appear together in more than a tiny fraction of their usages, penalize heavily
                # (A true substitute replaces the other, so direct co-occurrence should be near 0)
                co_occur_count = exact_co_occurrence[i, j]
                if co_occur_count > 0:
                    min_occur = min(ingredient_counts[i], ingredient_counts[j])
                    overlap_ratio = co_occur_count / min_occur
                    if overlap_ratio > 0.1: # If they overlap > 10% of the time, they are complements
                        sim_matrix[i, j] *= (1.0 - overlap_ratio) # Penalize proportional to overlap

    # Convert back to a DataFrame for easy lookup
    sim_df = pd.DataFrame(sim_matrix, index=ingredient_names, columns=ingredient_names)

    # 5. Build the output dictionary
    sub_map = {}
    for ingredient in ingredient_names:
        # Get similarities for this ingredient, drop itself, and sort descending
        similarities = sim_df.loc[ingredient].drop(ingredient).sort_values(ascending=False)

        # Filter by threshold
        valid_subs = similarities[similarities >= MIN_SIMILARITY]

        sub_list = []
        for sub_sku, score in valid_subs.items():
            sub_list.append({
                "sku": sub_sku,
                "similarity_score": round(float(score), 4)
            })

        sub_map[ingredient] = {
            "total_viable_substitutes": len(sub_list),
            "substitutes": sub_list
        }

    return sub_map


def print_summary(sub_map: dict):
    print("\n" + "═" * 80)
    print("  TOP SUBSTITUTION OPPORTUNITIES (Similarity > 0.85)")
    print("═" * 80)

    # Find the strongest relationships to print to console
    strong_pairs = set()
    for ing, data in sub_map.items():
        for sub in data["substitutes"]:
            if sub["similarity_score"] > 0.85:
                # Sort to avoid printing A->B and B->A twice
                pair = tuple(sorted([ing, sub['sku']]))
                strong_pairs.add((pair, sub['similarity_score']))

    # Sort by score descending
    sorted_pairs = sorted(list(strong_pairs), key=lambda x: x[1], reverse=True)

    for pair, score in sorted_pairs[:15]:  # Print top 15
        print(f"  {score:.3f} │ {pair[0]}")
        print(f"          │ {pair[1]}\n")
    print("═" * 80)


def main():
    parser = argparse.ArgumentParser(description="Find Ingredient Substitutes")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to db.sqlite")
    parser.add_argument("--out-dir", default=".", help="Directory to write output")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/4] Loading ingredient data from {args.db} …")
    components = load_data(args.db)

    print("[2/4] Running substitution math …")
    substitution_map = calculate_substitutes(components)

    print("[3/4] Writing output …")
    out_path = out_dir / "substitution_map.json"
    with open(out_path, "w") as f:
        json.dump(substitution_map, f, indent=2)

    print(f"      Successfully saved to -> {out_path}")

    print("[4/4] Summary …")
    print_summary(substitution_map)


if __name__ == "__main__":
    main()