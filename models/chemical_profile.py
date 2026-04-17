from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    API_ERROR = "api_error"


RESOLVED_STATUSES = {ResolutionStatus.RESOLVED, ResolutionStatus.AMBIGUOUS}


@dataclass
class ChemicalProfile:
    """
    Normalised chemical profile for a single ingredient.
    This is the object passed to the LLM in Phase 2.

    Fields set to None mean the data was not available from PubChem —
    the LLM should treat these with lower confidence.
    """

    query_name: str
    status: ResolutionStatus
    status_detail: str
    cid: Optional[int] = None
    iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    inchikey: Optional[str] = None
    xlogp: Optional[float] = None
    charge: Optional[int] = None
    is_salt: bool = False
    is_organic: bool = False
    element_set: list[str] = field(default_factory=list)

    def to_llm_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "query_name": self.query_name,
            "resolved": self.status in RESOLVED_STATUSES,
            "status_detail": self.status_detail,
        }
        if self.cid is not None:
            d["cid"] = self.cid
        if self.iupac_name:
            d["iupac_name"] = self.iupac_name
        if self.molecular_formula:
            d["molecular_formula"] = self.molecular_formula
        if self.molecular_weight is not None:
            d["molecular_weight_g_mol"] = self.molecular_weight
        if self.inchikey:
            d["inchikey"] = self.inchikey
        if self.xlogp is not None:
            d["xlogp"] = self.xlogp
        if self.charge is not None:
            d["charge"] = self.charge
        if self.element_set:
            d["elements"] = self.element_set
        d["is_salt"] = self.is_salt
        d["is_organic"] = self.is_organic
        return d

    def same_compound_as(self, other: "ChemicalProfile") -> Optional[bool]:
        """
        Returns True if both profiles are resolved and share the same InChIKey
        (deterministically the same compound, regardless of common name).
        Returns None if either profile is unresolved — cannot determine.
        """
        if self.status not in RESOLVED_STATUSES:
            return None
        if other.status not in RESOLVED_STATUSES:
            return None
        return self.inchikey == other.inchikey
