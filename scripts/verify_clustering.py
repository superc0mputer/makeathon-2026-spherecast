import json
import pandas as pd
from collections import Counter


def verify_substitution_map(map_path):
    with open(map_path, 'r') as f:
        sub_map = json.load(f)

    print("\n" + "═" * 60)
    print("  SUBSTITUTION MAP INTEGRITY REPORT")
    print("═" * 60)

    # --- TEST 1: The "Junk Ingredient" Detector ---
    # If an ingredient is suggested as a substitute for TOO many things,
    # it's likely a generic filler (excipient) and not a true substitute.
    all_suggestions = []
    for ing, data in sub_map.items():
        for sub in data['substitutes']:
            all_suggestions.append(sub['sku'])

    suggestion_counts = Counter(all_suggestions)
    top_junk = [sku for sku, count in suggestion_counts.most_common(5)]

    print(f"\n[!] Top 'Universal' Ingredients (Potential Noise):")
    for sku in top_junk:
        count = suggestion_counts[sku]
        print(f"    - {sku:<40} (Suggested {count} times)")
    print("    Note: If these are generic (Salt, Silica), consider TF-IDF weighting.")

    # --- TEST 2: Semantic Consistency Check ---
    # Do substitutes share similar words in their SKUs?
    print(f"\n[*] Semantic Keyword Match Rate:")
    matches = 0
    total_with_subs = 0

    for ing, data in sub_map.items():
        if not data['substitutes']: continue
        total_with_subs += 1

        # Get keywords from the target (e.g., 'whey', 'vitamin', 'acid')
        target_words = set(ing.lower().split('-'))

        # Check if the #1 substitute shares a keyword
        best_sub = data['substitutes'][0]['sku'].lower()
        if any(word in best_sub for word in target_words if len(word) > 3):
            matches += 1

    match_rate = (matches / total_with_subs) * 100 if total_with_subs > 0 else 0
    print(f"    - {match_rate:.1f}% of Top Substitutes share a SKU keyword.")
    print("    (High % = Very Safe/Conservative | Low % = High Discovery/Potential Noise)")

    # --- TEST 3: The "Smell Test" (Top 10 Strongest Links) ---
    print(f"\n[*] Top 10 Strongest Substitutions (Manual Audit):")
    pairs = []
    for ing, data in sub_map.items():
        for sub in data['substitutes']:
            # Create a sorted tuple to avoid A->B and B->A duplicates
            pair = tuple(sorted([ing, sub['sku']]))
            pairs.append((pair, sub['similarity_score']))

    unique_pairs = sorted(list(set(pairs)), key=lambda x: x[1], reverse=True)

    for (a, b), score in unique_pairs[:10]:
        name_a = "-".join(a.split("-")[2:-1]).upper()
        name_b = "-".join(b.split("-")[2:-1]).upper()
        print(f"    {score:.4f} │ {name_a} <-> {name_b}")

    print("\n" + "═" * 60)


if __name__ == "__main__":
    verify_substitution_map("substitution_map.json")