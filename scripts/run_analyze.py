import json
import math
import os
import sqlite3
import sys

repo_root = sys.argv[1]
db_path = sys.argv[2]
product_id = int(sys.argv[3])
target_sku = sys.argv[4]
priority = sys.argv[5]

sys.path.insert(0, repo_root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(repo_root, ".env"))
except Exception:
    pass

from src.models.biochemical_context import BiochemicalContext
from src.models.logistics_context import LogisticsContext, SourcedMaterial, SupplierDetails
from src.models.substitution.full_ingredient_profile import FullIngredientProfile
from src.models.substitution.nutritional_profile import NutritionalProfile
from src.services.clustering_service import calculate_target_substitutes, load_data
from src.services.fdc_service import fetch_fdc_profiles
from src.services.llm_service import IngredientLLMClient
from src.services.mintec_service import SupplyChainEnricher
from src.services.pubchem_service import enrich_ingredient
from src.services.supplier_db_service import ingredient_name_from_sku

COMPANY_COORDS = (48.1351, 11.5820)

priority_map = {
    "cost": "Reduce Cost",
    "suppliers": "Reduce Supplier Count",
    "risk": "Reduce Risk / Improve Reliability",
    "sustainability": "Improve Sustainability",
}

priority_label = priority_map.get(priority, priority)

def get_full_profile(name: str, fdc_api_key: str | None):
    pubchem = enrich_ingredient(name)
    fdc_data = fetch_fdc_profiles(target=name, candidates=[], api_key=fdc_api_key)
    nutritional_data = fdc_data.get("target", {}).get(name, {})
    return FullIngredientProfile(
        chemical_properties=pubchem.to_llm_dict(),
        nutritional_properties=NutritionalProfile(**nutritional_data) if nutritional_data else None
    )

def normalize_name(value: str) -> str:
    return " ".join(value.lower().split())

def safe_float(value, default):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default

def score_candidate(substitute, priority_key):
    confidence = safe_float(substitute.get("confidence_score"), 0.0)
    price = safe_float(substitute.get("price_per_kg"), 999999.0)
    suppliers = substitute.get("suppliers", []) or []
    supplier_count = len(suppliers)
    distances = [safe_float(s.get("distance_km"), 999999.0) for s in suppliers if s.get("distance_km") is not None]
    best_distance = min(distances) if distances else 999999.0

    if priority_key == "cost":
        return (
            -price,
            confidence,
            -supplier_count,
            -best_distance,
        )
    if priority_key == "suppliers":
        return (
            supplier_count,
            confidence,
            -best_distance,
            -price,
        )
    if priority_key == "risk":
        return (
            confidence,
            -best_distance,
            supplier_count,
            -price,
        )
    if priority_key == "sustainability":
        return (
            -best_distance,
            confidence,
            -price,
            supplier_count,
        )
    return (
        confidence,
        -price,
        -best_distance,
        supplier_count,
    )

def choose_supplier(substitute):
    suppliers = substitute.get("suppliers", []) or []
    if not suppliers:
        return {
            "supplier_id": -1,
            "name": "No supplier found",
            "price_per_kg": safe_float(substitute.get("price_per_kg"), 0.0),
            "distance_km": 0.0,
        }

    best_supplier = min(
        suppliers,
        key=lambda supplier: (
            safe_float(supplier.get("distance_km"), 999999.0),
            supplier.get("name", ""),
        ),
    )

    return {
        "supplier_id": int(best_supplier.get("supplier_id", -1)),
        "name": best_supplier.get("name", "Unknown Supplier"),
        "price_per_kg": safe_float(substitute.get("price_per_kg"), 0.0),
        "distance_km": round(safe_float(best_supplier.get("distance_km"), 0.0), 1),
    }

def heuristic_reason(substitute, supplier, priority_key):
    confidence = int(safe_float(substitute.get("confidence_score"), 0.0))
    price = substitute.get("price_per_kg")
    supplier_count = len(substitute.get("suppliers", []) or [])
    distance = supplier.get("distance_km", 0.0)

    if priority_key == "cost":
        return f"Ranked highly for cost because it remains substitutable ({confidence}/100 confidence) and is paired with a lower-cost sourcing option at {price} per kg."
    if priority_key == "suppliers":
        return f"Ranked highly for supplier flexibility because it remains substitutable ({confidence}/100 confidence) and currently has {supplier_count} supplier option(s) available."
    if priority_key == "risk":
        return f"Ranked highly for reliability because it keeps a strong substitutability score ({confidence}/100) and can be sourced from a comparatively closer supplier at about {distance} km."
    if priority_key == "sustainability":
        return f"Ranked highly for sustainability because it remains substitutable ({confidence}/100 confidence) and the selected supplier is relatively close at about {distance} km."
    return f"Ranked as a strong overall option with {confidence}/100 substitutability confidence and available supplier support."

def build_fallback_recommendations(substitutes, priority_key, current_supplier_names_str):
    valid_substitutes = []
    forbidden_suppliers = [s.strip().lower() for s in (current_supplier_names_str or "").split(",") if s.strip()]

    for item in substitutes:
        suppliers = item.get("suppliers", []) or []
        valid_suppliers = [sup for sup in suppliers if sup.get("name", "").lower() not in forbidden_suppliers]
        if valid_suppliers:
            item_copy = dict(item)
            item_copy["suppliers"] = valid_suppliers
            valid_substitutes.append(item_copy)

    ranked = sorted(
        valid_substitutes,
        key=lambda item: score_candidate(item, priority_key),
        reverse=True,
    )[:3]
    return {
        "top_3_recommendations": [
            {
                "rank": index + 1,
                "substitute_name": item.get("substitute_name"),
                "confidence_score": int(safe_float(item.get("confidence_score"), 0)),
                "recommended_supplier": choose_supplier(item),
                "reasoning_summary": heuristic_reason(item, choose_supplier(item), priority_key),
            }
            for index, item in enumerate(ranked)
        ]
    }

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

product = conn.execute(
    """
    SELECT p.Id, p.SKU, c.Name AS company_name
    FROM Product p
    JOIN Company c ON c.Id = p.CompanyId
    WHERE p.Id = ?
    """,
    (product_id,),
).fetchone()

if product is None:
    print(json.dumps({"error": "Selected product not found."}))
    raise SystemExit(0)

ingredient_rows = conn.execute(
    """
    SELECT rp.Id, rp.SKU
    FROM BOM b
    JOIN BOM_Component bc ON bc.BOMId = b.Id
    JOIN Product rp ON rp.Id = bc.ConsumedProductId
    WHERE b.ProducedProductId = ?
    ORDER BY rp.SKU
    """,
    (product_id,),
).fetchall()

current_suppliers_rows = conn.execute(
    """
    SELECT s.Name
    FROM Product p
    JOIN Supplier_Product sp ON p.Id = sp.ProductId
    JOIN Supplier s ON sp.SupplierId = s.Id
    WHERE p.SKU = ?
    """,
    (target_sku,)
).fetchall()
current_supplier_names = ", ".join([r["Name"] for r in current_suppliers_rows]) if current_suppliers_rows else None

conn.close()

target_name = ingredient_name_from_sku(target_sku)
bom_ingredient_names = [
    ingredient_name_from_sku(row["SKU"]).title()
    for row in ingredient_rows
    if row["SKU"] != target_sku
]

components = load_data(db_path)
cluster_result = calculate_target_substitutes(components, target_sku)
cluster_substitutes = cluster_result.get("substitutes", [])
candidate_skus = [sub["sku"] for sub in cluster_substitutes]
candidate_names = [ingredient_name_from_sku(sku) for sku in candidate_skus]

fdc_api_key = os.environ.get("FDC_API_KEY")
target_profile = get_full_profile(target_name, fdc_api_key)
bom_profiles = {name: get_full_profile(name, fdc_api_key) for name in bom_ingredient_names[:12]}
candidate_profiles = {name: get_full_profile(name, fdc_api_key) for name in candidate_names}

context = BiochemicalContext(
    target_ingredient=target_name,
    product_cluster=product["SKU"].replace("FG-", "").replace("-", " "),
    target_profile=target_profile,
    bom_profiles=bom_profiles,
    candidate_profiles=candidate_profiles,
)

api_key = os.environ.get("GEMINI_API_KEY")
vertex_project = os.environ.get("VERTEX_PROJECT_ID")
vertex_location = os.environ.get("VERTEX_LOCATION", "us-central1")

llm_client = None
if api_key or vertex_project:
    llm_client = IngredientLLMClient(api_key=api_key, project_id=vertex_project, location=vertex_location)

substitution_result = None
substitution_error = None
recommendation_result = None
recommendation_error = None

if llm_client is not None:
    try:
        substitution_result = llm_client.get_substitutes(context)
    except Exception as exc:
        substitution_error = str(exc)
else:
    substitution_error = "No GEMINI_API_KEY or VERTEX_PROJECT_ID configured."

if not substitution_result or "error" in substitution_result:
    if isinstance(substitution_result, dict) and substitution_result.get("error"):
        substitution_error = substitution_result["error"]
    substitution_result = {
        "substitutes": [
            {
                "substitute_name": name.title(),
                "candidate_sku": candidate_skus[index],
                "confidence_score": max(60, 90 - (index * 6)),
                "reasoning": "Fallback shortlist generated from hybrid similarity because the live substitution LLM call was unavailable.",
                "hybrid_similarity": cluster_substitutes[index]["similarity_score"],
            }
            for index, name in enumerate(candidate_names[:5])
        ]
    }

cluster_lookup = {
    normalize_name(ingredient_name_from_sku(sub["sku"])): sub
    for sub in cluster_substitutes
}

resolved_substitutes = []
for item in substitution_result.get("substitutes", []):
    explicit_sku = item.get("candidate_sku")
    if explicit_sku:
        cluster_match = next((sub for sub in cluster_substitutes if sub["sku"] == explicit_sku), None)
    else:
        normalized = normalize_name(item.get("substitute_name", ""))
        cluster_match = cluster_lookup.get(normalized)
    resolved_substitutes.append({
        "substitute_name": item.get("substitute_name"),
        "candidate_sku": cluster_match["sku"] if cluster_match else None,
        "confidence_score": int(safe_float(item.get("confidence_score"), 0)),
        "reasoning": item.get("reasoning"),
        "hybrid_similarity": item.get("hybrid_similarity", cluster_match["similarity_score"] if cluster_match else None),
    })

enricher = SupplyChainEnricher(db_path=db_path)
enriched = enricher.enrich_substitutes({"substitutes": resolved_substitutes}, company_coords=COMPANY_COORDS)
enriched_substitutes = enriched.get("substitutes", [])

if not enriched_substitutes:
    recommendation_result = {"top_3_recommendations": []}
else:
    logistics_context = LogisticsContext(
        target_ingredient=target_name.title(),
        company_coords=[COMPANY_COORDS[0], COMPANY_COORDS[1]],
        bom_ingredients=bom_ingredient_names,
        preference_weights={
            "selected_priority": priority_label,
            "priority_key": priority,
        },
        current_supplier=current_supplier_names,
        candidates=[
            SourcedMaterial(
                substitute_name=item.get("substitute_name", ""),
                confidence_score=int(safe_float(item.get("confidence_score"), 0)),
                reasoning=item.get("reasoning", ""),
                price_per_kg=safe_float(item.get("price_per_kg"), None),
                suppliers=[
                    SupplierDetails(
                        supplier_id=int(supplier.get("supplier_id", -1)),
                        name=supplier.get("name", "Unknown Supplier"),
                        match_confidence=supplier.get("match_confidence"),
                        lat=safe_float(supplier.get("lat"), None),
                        lng=safe_float(supplier.get("lng"), None),
                        distance_km=safe_float(supplier.get("distance_km"), None),
                        stocked_ingredients=supplier.get("stocked_ingredients", []) or [],
                    )
                    for supplier in item.get("suppliers", []) or []
                ],
            )
            for item in enriched_substitutes
        ],
    )

    if llm_client is not None:
        try:
            recommendation_result = llm_client.get_top_3_recommendations(logistics_context)
        except Exception as exc:
            recommendation_error = str(exc)
    else:
        recommendation_error = "No GEMINI_API_KEY or VERTEX_PROJECT_ID configured."

    if not recommendation_result or "error" in recommendation_result:
        if isinstance(recommendation_result, dict) and recommendation_result.get("error"):
            recommendation_error = recommendation_result["error"]
        recommendation_result = build_fallback_recommendations(enriched_substitutes, priority, current_supplier_names)

available_substitutes = {
    normalize_name(item.get("substitute_name", "")): item
    for item in enriched_substitutes
}
sanitized_recommendations = []
seen_recommendations = set()
for recommendation in recommendation_result.get("top_3_recommendations", []):
    normalized_name = normalize_name(recommendation.get("substitute_name", ""))
    if normalized_name not in available_substitutes or normalized_name in seen_recommendations:
        continue
    sanitized_recommendations.append(recommendation)
    seen_recommendations.add(normalized_name)

# If LLM didn't return correctly or we had to filter things out entirely:
if not sanitized_recommendations and enriched_substitutes:
    fallback_res = build_fallback_recommendations(enriched_substitutes, priority, current_supplier_names)
    recommendation_result = fallback_res
    sanitized_recommendations = fallback_res.get("top_3_recommendations", [])
else:
    recommendation_result = {"top_3_recommendations": sanitized_recommendations}

resolved_substitute_cards = []
top_recommendations = []
for recommendation in recommendation_result.get("top_3_recommendations", []):
    supplier = recommendation.get("recommended_supplier", {}) or {}
    top_recommendations.append({
        "rank": recommendation.get("rank"),
        "substituteName": recommendation.get("substitute_name"),
        "confidenceScore": recommendation.get("confidence_score"),
        "supplier": {
            "id": supplier.get("supplier_id"),
            "name": supplier.get("name"),
            "pricePerKg": supplier.get("price_per_kg"),
            "distanceKm": supplier.get("distance_km"),
        },
        "reasoningSummary": recommendation.get("reasoning_summary"),
    })

recommendation_lookup = {
    normalize_name(item["substituteName"]): item
    for item in top_recommendations
}

forbidden_suppliers = [s.strip().lower() for s in (current_supplier_names or "").split(",") if s.strip()]

for item in enriched_substitutes:
    normalized_name = normalize_name(item.get("substitute_name", ""))
    recommendation = recommendation_lookup.get(normalized_name)
    
    # Exclude substitute entirely if its ONLY suppliers are the ones we already use
    item_suppliers = [s.get("name", "").lower() for s in (item.get("suppliers", []) or [])]
    if item_suppliers and all(s in forbidden_suppliers for s in item_suppliers):
        continue

    resolved_substitute_cards.append({
        "name": item.get("substitute_name"),
        "sku": item.get("candidate_sku"),
        "confidenceScore": item.get("confidence_score"),
        "reasoning": item.get("reasoning"),
        "hybridSimilarity": item.get("hybrid_similarity"),
        "pricePerKg": item.get("price_per_kg"),
        "supplierCount": len(item.get("suppliers", []) or []),
        "rank": recommendation.get("rank") if recommendation else None,
        "rankingReasoning": recommendation.get("reasoningSummary") if recommendation else None,
        "recommendedSupplier": recommendation.get("supplier") if recommendation else None,
    })

resolved_substitute_cards.sort(
    key=lambda item: (
        item["rank"] is None,
        item["rank"] if item["rank"] is not None else 999,
        -safe_float(item.get("confidenceScore"), 0),
    )
)

result = {
    "product": {
        "id": product["Id"],
        "sku": product["SKU"],
        "label": product["SKU"].replace("FG-", "").replace("-", " "),
        "companyName": product["company_name"],
    },
    "targetIngredient": {
        "sku": target_sku,
        "name": target_name.title(),
    },
    "priority": priority,
    "priorityLabel": priority_label,
    "bomIngredientNames": bom_ingredient_names,
    "substitutes": resolved_substitute_cards,
    "usedFallback": substitution_error is not None or recommendation_error is not None,
    "substitutionLlmError": substitution_error,
    "recommendationLlmError": recommendation_error,
}

print(json.dumps(result))