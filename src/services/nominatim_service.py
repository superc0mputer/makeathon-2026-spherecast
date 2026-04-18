from __future__ import annotations

import logging
import math
import re
import time
from typing import Any, Optional, Sequence, TypedDict, cast

from src.models.supplier_record import MatchConfidence, MatchMethod, SupplierRecord
from src.api_clients.nominatim_client import NominatimClient
from src.services.cache_service import get_nominatim, set_nominatim

logger = logging.getLogger(__name__)

NOMINATIM_MIN_DELAY_SECONDS = 1.0
CORPORATE_SUFFIXES = {
    "llc", "ltd", "inc", "corp", "corporation", "company", "co", "gmbh",
    "sa", "bv", "plc", "holdings", "group", "usa", "us",
}

class GeocodeResult(TypedDict):
    lat: float
    lng: float
    resolved_address: str
    match_method: MatchMethod
    match_confidence: MatchConfidence
    matched_name: str

class NominatimGeocoder:
    def __init__(self, min_delay_seconds: float = NOMINATIM_MIN_DELAY_SECONDS) -> None:
        self.min_delay_seconds = min_delay_seconds
        self._last_request_timestamp = 0.0

    def geocode_supplier(self, supplier_name: str) -> GeocodeResult:
        cached = get_nominatim(supplier_name)
        if cached:
            return {
                "lat": cached["lat"],
                "lng": cached["lng"],
                "resolved_address": cached["resolved_address"],
                "match_method": cached.get("match_method", "name_only"),
                "match_confidence": cached.get("match_confidence", "high"),
                "matched_name": cached.get("matched_name", supplier_name),
            }

        self._respect_rate_limit()
        try:
            places = NominatimClient.search_supplier(supplier_name)
        except Exception as e:
            # Prevent throwing if network fails
            places = []
        self._last_request_timestamp = time.monotonic()

        if not places:
            # Do not throw an exception, return an empty profile and cache it
            result: GeocodeResult = {
                "lat": 0.0,
                "lng": 0.0,
                "resolved_address": "",
                "match_method": "name_only",
                "match_confidence": "low",
                "matched_name": supplier_name,
            }
            set_nominatim(supplier_name, result)
            return result

        top_place = places[0]
        lat_text = cast(Optional[str], top_place.get("lat"))
        lng_text = cast(Optional[str], top_place.get("lon"))
        if lat_text is None or lng_text is None:
            # Do not throw, cache the failure
            result: GeocodeResult = {
                "lat": 0.0,
                "lng": 0.0,
                "resolved_address": "",
                "match_method": "name_only",
                "match_confidence": "low",
                "matched_name": supplier_name,
            }
            set_nominatim(supplier_name, result)
            return result

        display_name = cast(str, top_place.get("display_name", ""))
        name_parts = [part.strip() for part in display_name.split(",") if part.strip()]
        matched_name = name_parts[0] if name_parts else supplier_name
        confidence = _match_confidence(supplier_name, matched_name)

        result: GeocodeResult = {
            "lat": float(lat_text),
            "lng": float(lng_text),
            "resolved_address": display_name,
            "match_method": "name_only",
            "match_confidence": confidence,
            "matched_name": matched_name,
        }
        set_nominatim(supplier_name, result)
        return result

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_timestamp
        if elapsed < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - elapsed)

def _normalize_supplier_name(value: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    tokens = [token for token in cleaned.split() if token and token not in CORPORATE_SUFFIXES]
    return set(tokens)

def _match_confidence(requested_name: str, matched_name: str) -> MatchConfidence:
    requested_tokens = _normalize_supplier_name(requested_name)
    matched_tokens = _normalize_supplier_name(matched_name)
    if not requested_tokens or not matched_tokens:
        return "low"
    if requested_tokens == matched_tokens:
        return "high"
    overlap = len(requested_tokens & matched_tokens) / len(requested_tokens)
    if overlap >= 0.75:
        return "medium"
    return "low"

def haversine_distance_km(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
) -> float:
    earth_radius_km = 6371.0
    lat1, lng1 = math.radians(origin_lat), math.radians(origin_lng)
    lat2, lng2 = math.radians(dest_lat), math.radians(dest_lng)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def enrich_suppliers_with_geodata(
    suppliers: Sequence[SupplierRecord],
    company_location: tuple[float, float],
    geocoder: Optional[NominatimGeocoder],
) -> list[SupplierRecord]:
    company_lat, company_lng = company_location
    for supplier in suppliers:
        if geocoder is None:
            supplier.address = ""
            supplier.lat, supplier.lng, supplier.distance_km = None, None, None
            supplier.resolved_address = None
            supplier.match_method, supplier.match_confidence = None, None
            continue

        try:
            geocode_result = geocoder.geocode_supplier(supplier.name)
            supplier.address = geocode_result["resolved_address"] or ""
            supplier.resolved_address = geocode_result["resolved_address"] or None
            supplier.match_method = geocode_result["match_method"]
            supplier.match_confidence = geocode_result["match_confidence"]

            if supplier.match_confidence == "low":
                supplier.lat, supplier.lng, supplier.distance_km = None, None, None
                continue

            lat, lng = geocode_result["lat"], geocode_result["lng"]
            supplier.lat, supplier.lng = lat, lng
            supplier.distance_km = haversine_distance_km(company_lat, company_lng, lat, lng)
            
        except Exception as exc:
            logger.warning("Failed to geocode supplier %s: %s", supplier.name, exc)
            supplier.address = ""
            supplier.lat, supplier.lng, supplier.distance_km = None, None, None
            supplier.resolved_address = None
            supplier.match_method = "name_only"
            supplier.match_confidence = "low"

    return list(suppliers)
