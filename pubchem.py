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

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        return _error_profile(ingredient_name, "PubChem request timed out.")
    except requests.exceptions.ConnectionError as e:
        return _error_profile(ingredient_name, f"Network error: {e}")
    finally:
        if rate_limit:
            time.sleep(RATE_LIMIT_DELAY)

    # PubChem returns 404 for unknown compounds
    if response.status_code == 404:
        try:
            fault = response.json().get("Fault", {})
            detail = fault.get("Message", "Compound not found in PubChem.")
        except ValueError:
            detail = "Compound not found in PubChem."
        return _not_found_profile(
            ingredient_name,
            f"{detail} This ingredient may be a mixture, extract, or proprietary blend.",
        )

    if response.status_code != 200:
        return _error_profile(
            ingredient_name,
            f"PubChem returned HTTP {response.status_code}.",
        )

    try:
        data = response.json()
    except ValueError:
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
    return _build_resolved_profile(ingredient_name, props_list[0], ambiguous)


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
