from dataclasses import dataclass, field
from typing import Literal, Optional, TypedDict


MatchMethod = Literal["name_only"]
MatchConfidence = Literal["high", "medium", "low"]


class SupplierRecordDict(TypedDict):
    supplier_id: int
    name: str
    address: str
    stocked_ingredients: list[str]
    lat: Optional[float]
    lng: Optional[float]
    distance_km: Optional[float]
    resolved_address: Optional[str]
    match_method: Optional[MatchMethod]
    match_confidence: Optional[MatchConfidence]


@dataclass
class SupplierRecord:
    supplier_id: int
    name: str
    address: str = ""
    stocked_ingredients: list[str] = field(default_factory=list)
    lat: Optional[float] = None
    lng: Optional[float] = None
    distance_km: Optional[float] = None
    resolved_address: Optional[str] = None
    match_method: Optional[MatchMethod] = None
    match_confidence: Optional[MatchConfidence] = None

    def to_dict(self) -> SupplierRecordDict:
        return {
            "supplier_id": self.supplier_id,
            "name": self.name,
            "address": self.address,
            "stocked_ingredients": self.stocked_ingredients,
            "lat": self.lat,
            "lng": self.lng,
            "distance_km": self.distance_km,
            "resolved_address": self.resolved_address,
            "match_method": self.match_method,
            "match_confidence": self.match_confidence,
        }
