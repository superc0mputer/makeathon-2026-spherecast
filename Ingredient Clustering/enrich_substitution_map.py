from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models import ChemicalProfile, ResolutionStatus
from pubchem import enrich_ingredient


RAW_MATERIAL_SKU_RE = re.compile(r"^RM-[^-]+-(?P<name>.+)-[0-9a-f]{8}$")


def ingredient_name_from_sku(sku: str) -> str:
    match = RAW_MATERIAL_SKU_RE.match(sku)
    if not match:
        return sku
    return match.group("name").replace("-", " ")


def warnings_from_profile(profile: ChemicalProfile) -> list[str]:
    if profile.status == ResolutionStatus.RESOLVED:
        return []
    if profile.status == ResolutionStatus.AMBIGUOUS:
        return [
            "Multiple PubChem matches found; using the first returned compound.",
        ]
    if profile.status == ResolutionStatus.NOT_FOUND:
        return [
            "No PubChem compound found for this ingredient name.",
            profile.status_detail,
        ]
    if profile.status == ResolutionStatus.API_ERROR:
        return [
            "PubChem request failed.",
            profile.status_detail,
        ]
    return [profile.status_detail]


def properties_from_profile(profile: ChemicalProfile) -> list[str]:
    properties: list[str] = []
    if profile.title:
        properties.append(f"Title: {profile.title}")
    if profile.iupac_name:
        properties.append(f"IUPAC name: {profile.iupac_name}")
    if profile.description:
        properties.append(f"Description: {profile.description}")
    if profile.molecular_formula:
        properties.append(f"Molecular formula: {profile.molecular_formula}")
    if profile.molecular_weight is not None:
        properties.append(f"Molecular weight: {profile.molecular_weight} g/mol")
    if profile.inchikey:
        properties.append(f"InChIKey: {profile.inchikey}")
    if profile.xlogp is not None:
        properties.append(f"XLogP: {profile.xlogp}")
    if profile.charge is not None:
        properties.append(f"Charge: {profile.charge}")
    if profile.element_set:
        properties.append(f"Elements: {', '.join(profile.element_set)}")
    if profile.is_salt:
        properties.append("Salt form")
    if profile.is_organic:
        properties.append("Organic compound")
    return properties


def component_warnings_from_profile(profile: ChemicalProfile) -> list[str]:
    warnings = warnings_from_profile(profile)
    warnings.extend(profile.safety_hazards)
    unique_warnings: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning not in seen:
            seen.add(warning)
            unique_warnings.append(warning)
    return unique_warnings


def pubchem_components_from_profile(profile: ChemicalProfile) -> list[dict[str, Any]]:
    if profile.status not in {ResolutionStatus.RESOLVED, ResolutionStatus.AMBIGUOUS}:
        return []

    return [
        {
            "component_name": profile.title or profile.query_name,
            "pubchem_cid": str(profile.cid) if profile.cid is not None else None,
            "description": profile.description,
            "synonyms": profile.synonyms,
            "properties": properties_from_profile(profile),
            "warnings": component_warnings_from_profile(profile),
        }
    ]


def ingredient_payload(name: str, profile: ChemicalProfile) -> dict[str, Any]:
    return {
        "ingredient_name": name,
        "pubchem_components": pubchem_components_from_profile(profile),
        "warnings": warnings_from_profile(profile),
    }


def get_profile_with_cache(
    ingredient_name: str,
    cache: dict[str, ChemicalProfile],
) -> ChemicalProfile:
    cache_key = ingredient_name.strip().lower()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    profile = enrich_ingredient(ingredient_name)
    cache[cache_key] = profile
    return profile


def enrich_substitution_map(
    substitution_map: dict[str, Any],
    progress_every: int = 25,
) -> dict[str, Any]:
    enriched_map: dict[str, Any] = {}
    profile_cache: dict[str, ChemicalProfile] = {}
    total_originals = len(substitution_map)

    for index, (original_sku, payload) in enumerate(substitution_map.items(), start=1):
        if index == 1 or index % progress_every == 0 or index == total_originals:
            print(
                f"[{index}/{total_originals}] enriching {original_sku}",
                file=sys.stderr,
                flush=True,
            )

        original_name = ingredient_name_from_sku(original_sku)
        original_profile = get_profile_with_cache(original_name, profile_cache)

        enriched_substitutes: list[dict[str, Any]] = []
        for substitute in payload.get("substitutes", []):
            substitute_sku = substitute["sku"]
            substitute_name = ingredient_name_from_sku(substitute_sku)
            substitute_profile = get_profile_with_cache(substitute_name, profile_cache)

            enriched_substitutes.append(
                {
                    "sku": substitute_sku,
                    "similarity_score": substitute["similarity_score"],
                    "substitute_ingredient_data": ingredient_payload(
                        substitute_name,
                        substitute_profile,
                    ),
                }
            )

        enriched_map[original_sku] = {
            "target_ingredient_data": ingredient_payload(
                original_name,
                original_profile,
            ),
            "total_viable_substitutes": payload.get("total_viable_substitutes", 0),
            "substitutes": enriched_substitutes,
        }

    return enriched_map


def load_substitution_map(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: python enrich_substitution_map.py /path/to/substitution_map.json [output.json]",
            file=sys.stderr,
        )
        return 1

    input_path = Path(sys.argv[1]).expanduser()
    output_path = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else None

    substitution_map = load_substitution_map(input_path)
    enriched_map = enrich_substitution_map(substitution_map)
    rendered = json.dumps(enriched_map, indent=2)

    if output_path is not None:
        output_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
