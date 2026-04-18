"""
Phase 1 enrichment: query PubChem REST API for a given ingredient name
and normalise the response into a ChemicalProfile ready for the LLM.
"""

import re
from typing import Any, Optional
import dataclasses

from models.substitution.chemical_profile import ChemicalProfile, ResolutionStatus
from src.services.cache_service import get_pubchem, set_pubchem
from src.api_clients.pubchem_client import PubChemClient

MAX_SYNONYMS = 10
MAX_SAFETY_HAZARDS = 12

def _parse_elements(formula: Optional[str]) -> list[str]:
    """Extract unique element symbols from a molecular formula string."""
    if not formula:
        return []
    return sorted(set(re.findall(r"[A-Z][a-z]?", formula)))

METAL_IONS = {
    "Mg", "Ca", "Na", "K", "Zn", "Fe", "Cu", "Mn",
    "Se", "Cr", "Mo", "Li", "Al",
}

def _is_salt(elements: list[str]) -> bool:
    return any(e in METAL_IONS for e in elements)

def _is_organic(elements: list[str]) -> bool:
    return "C" in elements

def _collect_text_values(node: Any) -> list[str]:
    values: list[str] = []
    if isinstance(node, str):
        text = node.strip()
        if text:
            values.append(text)
        return values
    if isinstance(node, list):
        for item in node:
            values.extend(_collect_text_values(item))
        return values
    if isinstance(node, dict):
        preferred_keys = (
            "TOCHeading",
            "Name",
            "String",
            "DisplayString",
            "Number",
            "DateISO8601",
        )
        for key in preferred_keys:
            if key in node:
                values.extend(_collect_text_values(node[key]))
        for key, value in node.items():
            if key not in preferred_keys:
                values.extend(_collect_text_values(value))
    return values

def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique

def _fetch_description(cid: int, rate_limit: bool) -> Optional[str]:
    data, status_code, error = PubChemClient.get_description_by_cid(cid, rate_limit=rate_limit)
    if error or status_code != 200 or not data:
        return None

    information = data.get("InformationList", {}).get("Information", [])
    if not information:
        return None

    description = information[0].get("Description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    return None

def _fetch_synonyms(cid: int, rate_limit: bool) -> list[str]:
    data, status_code, error = PubChemClient.get_synonyms_by_cid(cid, rate_limit=rate_limit)
    if error or status_code != 200 or not data:
        return []

    information = data.get("InformationList", {}).get("Information", [])
    if not information:
        return []

    synonyms = information[0].get("Synonym", [])
    if not isinstance(synonyms, list):
        return []

    clean_synonyms = [
        value.strip()
        for value in synonyms
        if isinstance(value, str) and value.strip()
    ]
    return _dedupe_preserve_order(clean_synonyms)[:MAX_SYNONYMS]

def _fetch_safety_hazards(cid: int, rate_limit: bool) -> list[str]:
    data, status_code, error = PubChemClient.get_safety_hazards_by_cid(cid, rate_limit=rate_limit)
    if error or status_code != 200 or not data:
        return []

    record = data.get("Record", {})
    sections = record.get("Section", [])
    if not sections:
        return []

    extracted = _collect_text_values(sections)
    filtered = [
        value
        for value in extracted
        if value.lower() != "safety and hazards"
    ]
    return _dedupe_preserve_order(filtered)[:MAX_SAFETY_HAZARDS]

def _enrich_with_annotations(profile: ChemicalProfile, rate_limit: bool) -> ChemicalProfile:
    if profile.cid is None:
        return profile

    profile.description = _fetch_description(profile.cid, rate_limit=rate_limit)
    profile.synonyms = _fetch_synonyms(profile.cid, rate_limit=rate_limit)
    profile.safety_hazards = _fetch_safety_hazards(profile.cid, rate_limit=rate_limit)
    if not profile.title:
        profile.title = profile.iupac_name or profile.query_name
    return profile

def _build_resolved_profile(query_name: str, props: dict, ambiguous: bool) -> ChemicalProfile:
    """Build a ChemicalProfile from a raw PubChem properties dict."""
    formula = props.get("MolecularFormula")
    elements = _parse_elements(formula)

    status = ResolutionStatus.AMBIGUOUS if ambiguous else ResolutionStatus.RESOLVED
    detail = (
        "Resolved — multiple CIDs matched, using the first result."
        if ambiguous
        else "Resolved from PubChem."
    )

    return ChemicalProfile(
        query_name=query_name,
        status=status,
        status_detail=detail,
        cid=props.get("CID"),
        title=props.get("Title"),
        iupac_name=props.get("IUPACName"),
        molecular_formula=formula,
        molecular_weight=props.get("MolecularWeight"),
        inchikey=props.get("InChIKey"),
        xlogp=props.get("XLogP"),
        charge=props.get("Charge"),
        is_salt=_is_salt(elements),
        is_organic=_is_organic(elements),
        element_set=elements,
    )

def _not_found_profile(query_name: str, detail: str) -> ChemicalProfile:
    return ChemicalProfile(
        query_name=query_name,
        status=ResolutionStatus.NOT_FOUND,
        status_detail=detail,
    )

def _error_profile(query_name: str, detail: str) -> ChemicalProfile:
    return ChemicalProfile(
        query_name=query_name,
        status=ResolutionStatus.API_ERROR,
        status_detail=detail,
    )

def enrich_ingredient(
        ingredient_name: str,
        rate_limit: bool = True,
        max_age_days: int = None,
) -> ChemicalProfile:
    # Check cache first
    cached_data = get_pubchem(ingredient_name, max_age_days=max_age_days)
    if cached_data:
        if "status" in cached_data and isinstance(cached_data["status"], str):
            try:
                cached_data["status"] = ResolutionStatus(cached_data["status"])
            except ValueError:
                pass
        return ChemicalProfile(**cached_data)

    data, status_code, error = PubChemClient.get_properties_by_name(ingredient_name, rate_limit=rate_limit)

    # Attempt to sanitize
    if status_code == 404:
        clean_name = re.sub(r'(?i)\b(powder|extract|leaf|root|organic|natural|flavor|concentrate|gel|juice|lake|membrane|peptides|syrup|blend)\b', '', ingredient_name)
        clean_name = re.sub(r'[-\s][a-zA-Z0-9]+$', '', clean_name.strip())
        clean_name = " ".join(clean_name.split())
        
        if clean_name and clean_name != ingredient_name.strip():
            data2, status_code2, error2 = PubChemClient.get_properties_by_name(clean_name, rate_limit=rate_limit)
            if status_code2 == 200:
                data = data2
                status_code = status_code2
                error = error2
    
    final_profile = None

    if error:
        final_profile = _error_profile(ingredient_name, error)
    elif status_code == 404:
        detail = "Compound not found in PubChem."
        if data:
            fault = data.get("Fault", {})
            detail = fault.get("Message", detail)
        final_profile = _not_found_profile(
            ingredient_name,
            f"{detail} This ingredient may be a mixture, extract, or proprietary blend.",
        )
    elif status_code != 200:
        final_profile = _error_profile(
            ingredient_name,
            f"PubChem returned HTTP {status_code}.",
        )
    elif not data:
        final_profile = _error_profile(ingredient_name, "Could not parse PubChem response as JSON.")
    elif "Fault" in data:
        fault = data["Fault"]
        final_profile = _not_found_profile(
            ingredient_name,
            f"PubChem fault: {fault.get('Message', 'Unknown error')}",
        )
    else:
        props_list = data.get("PropertyTable", {}).get("Properties", [])
        if not props_list:
            final_profile = _not_found_profile(ingredient_name, "PubChem returned an empty property table.")
        else:
            ambiguous = len(props_list) > 1
            profile = _build_resolved_profile(ingredient_name, props_list[0], ambiguous)
            final_profile = _enrich_with_annotations(profile, rate_limit=rate_limit)

    dict_profile = dataclasses.asdict(final_profile)
    if isinstance(dict_profile["status"], ResolutionStatus):
        dict_profile["status"] = dict_profile["status"].value
    set_pubchem(ingredient_name, dict_profile)

    return final_profile

