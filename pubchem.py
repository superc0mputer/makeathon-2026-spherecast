"""
Phase 1 enrichment: query PubChem REST API for a given ingredient name
and normalise the response into a ChemicalProfile ready for the LLM.

API base: https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/...

Usage:
    from pubchem_enrichment import enrich_ingredient

    profile = enrich_ingredient("ascorbic acid")
    print(profile)
"""

import time
import urllib.parse
import re
from typing import Any, Optional

import requests

from models import ChemicalProfile, ResolutionStatus

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name"
PUBCHEM_CID_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid"
PUBCHEM_VIEW_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"

# Properties we fetch — chosen because they are useful for the LLM to
# reason about functional equivalence between two ingredients:
#   MolecularFormula  — same formula = almost certainly same compound
#   MolecularWeight   — useful for dosage/ratio reasoning
#   IUPACName         — canonical chemical name, disambiguates common names
#   InChIKey          — deterministic hash; identical = same compound
#   XLogP             — lipophilicity; affects bioavailability / formulation role
#   Charge            — ionic state; relevant for salt vs free-acid forms

PROPERTIES = "MolecularFormula,MolecularWeight,IUPACName,InChIKey,XLogP,Charge"

REQUEST_TIMEOUT = 10  # seconds
RATE_LIMIT_DELAY = 0.3  # seconds between calls — PubChem asks for max 5 req/s
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


def _request_json(
    url: str,
    rate_limit: bool = True,
) -> tuple[Optional[dict[str, Any]], Optional[int], Optional[str]]:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        return None, None, "PubChem request timed out."
    except requests.exceptions.ConnectionError as exc:
        return None, None, f"Network error: {exc}"
    except requests.exceptions.RequestException as exc:
        return None, None, f"Request error: {exc}"
    finally:
        if rate_limit:
            time.sleep(RATE_LIMIT_DELAY)

    try:
        data = response.json()
    except ValueError:
        data = None

    return data, response.status_code, None


def _fetch_description(cid: int, rate_limit: bool) -> Optional[str]:
    url = f"{PUBCHEM_CID_BASE}/{cid}/description/JSON"
    data, status_code, error = _request_json(url, rate_limit=rate_limit)
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
    url = f"{PUBCHEM_CID_BASE}/{cid}/synonyms/JSON"
    data, status_code, error = _request_json(url, rate_limit=rate_limit)
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
    heading = urllib.parse.quote("Safety and Hazards")
    url = f"{PUBCHEM_VIEW_BASE}/{cid}/JSON?heading={heading}"
    data, status_code, error = _request_json(url, rate_limit=rate_limit)
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
) -> ChemicalProfile:
    """
    Query PubChem for a single ingredient name and return a ChemicalProfile.

    Args:
        ingredient_name: plain-text ingredient name, e.g. "ascorbic acid"
        rate_limit: if True, sleep 0.3s after the call to respect PubChem limits

    Returns:
        ChemicalProfile with status set to RESOLVED, NOT_FOUND, or API_ERROR
    """
    encoded = urllib.parse.quote(ingredient_name.strip())
    url = f"{PUBCHEM_BASE}/{encoded}/property/{PROPERTIES}/JSON"

    data, status_code, error = _request_json(url, rate_limit=rate_limit)
    if error:
        return _error_profile(ingredient_name, error)

    # PubChem returns 404 for unknown compounds
    if status_code == 404:
        detail = "Compound not found in PubChem."
        if data:
            fault = data.get("Fault", {})
            detail = fault.get("Message", detail)
        return _not_found_profile(
            ingredient_name,
            f"{detail} This ingredient may be a mixture, extract, or proprietary blend.",
        )

    if status_code != 200:
        return _error_profile(
            ingredient_name,
            f"PubChem returned HTTP {status_code}.",
        )

    if not data:
        return _error_profile(ingredient_name, "Could not parse PubChem response as JSON.")

    # Fault block inside a 200 response (PubChem does this sometimes)
    if "Fault" in data:
        fault = data["Fault"]
        return _not_found_profile(
            ingredient_name,
            f"PubChem fault: {fault.get('Message', 'Unknown error')}",
        )

    props_list = data.get("PropertyTable", {}).get("Properties", [])
    if not props_list:
        return _not_found_profile(ingredient_name, "PubChem returned an empty property table.")

    ambiguous = len(props_list) > 1
    profile = _build_resolved_profile(ingredient_name, props_list[0], ambiguous)
    return _enrich_with_annotations(profile, rate_limit=rate_limit)


def enrich_pair(
        name_a: str,
        name_b: str,
) -> tuple[ChemicalProfile, ChemicalProfile]:
    """
    Enrich both ingredients in a substitution pair.
    Returns (profile_a, profile_b) ready to pass to the LLM.
    """
    profile_a = enrich_ingredient(name_a)
    profile_b = enrich_ingredient(name_b)
    return profile_a, profile_b


def pair_to_llm_context(
        profile_a: ChemicalProfile,
        profile_b: ChemicalProfile,
) -> dict[str, Any]:
    """
    Build the chemical context dict that gets embedded in the LLM prompt.
    Includes a pre-computed same_compound flag so the LLM doesn't have to
    compare InChIKeys itself.
    """
    same = profile_a.same_compound_as(profile_b)
    return {
        "ingredient_a": profile_a.to_llm_dict(),
        "ingredient_b": profile_b.to_llm_dict(),
        "same_compound": same,  # True / False / None (unknown)
        "both_resolved": (
                profile_a.status in {ResolutionStatus.RESOLVED, ResolutionStatus.AMBIGUOUS} and
                profile_b.status in {ResolutionStatus.RESOLVED, ResolutionStatus.AMBIGUOUS}
        ),
        "chemical_context_note": (
            "Both ingredients resolved to PubChem records."
            if same is not None
            else "One or both ingredients could not be resolved in PubChem — "
                 "reason from ingredient names and BOM context alone."
        ),
    }
