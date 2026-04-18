from __future__ import annotations

import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Any, Optional, Sequence, TypedDict, Union, cast

import requests

from src.models.supplier_record import MatchConfidence, MatchMethod, SupplierRecord


logger = logging.getLogger(__name__)

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent.parent / "cache" / "supplier_geocodes.json"
REQUEST_TIMEOUT = 10
NOMINATIM_MIN_DELAY_SECONDS = 1.0
USER_AGENT = "makeathon-2026-spherecast/0.1 (supplier geocoding prototype)"
CORPORATE_SUFFIXES = {
    "llc", "ltd", "inc", "corp", "corporation", "company", "co", "gmbh",
    "sa", "bv", "plc", "holdings", "group", "usa", "us",
}


class GeocodeResult(TypedDict):
    lat: float
    lng: float
    resolved_address: str
    google_place_id: Optional[str]
    match_method: MatchMethod
    match_confidence: MatchConfidence
    matched_name: str


class NominatimGeocoder:
    def __init__(
        self,
        cache_path: Union[str, Path] = DEFAULT_CACHE_PATH,
        min_delay_seconds: float = NOMINATIM_MIN_DELAY_SECONDS,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.min_delay_seconds = min_delay_seconds
        self._cache: dict[str, GeocodeResult] = self._load_cache()
        self._last_request_timestamp = 0.0

    def geocode_supplier(self, supplier_name: str) -> GeocodeResult:
        cache_key = supplier_name.strip().lower()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        self._respect_rate_limit()
        response = requests.get(
            NOMINATIM_SEARCH_URL,
            params={
                "q": supplier_name,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        self._last_request_timestamp = time.monotonic()
        response.raise_for_status()

        places = cast(list[dict[str, Any]], response.json())
        if not places:
            raise ValueError(f"No Nominatim match returned for supplier: {supplier_name}")

        top_place = places[0]
        lat_text = cast(Optional[str], top_place.get("lat"))
        lng_text = cast(Optional[str], top_place.get("lon"))
        if lat_text is None or lng_text is None:
            raise ValueError(f"Nominatim returned no coordinates for supplier: {supplier_name}")

        display_name = cast(str, top_place.get("display_name", ""))
        name_parts = [part.strip() for part in display_name.split(",") if part.strip()]
        matched_name = name_parts[0] if name_parts else supplier_name
        confidence = _match_confidence(supplier_name, matched_name)

        result: GeocodeResult = {
            "lat": float(lat_text),
            "lng": float(lng_text),
            "resolved_address": display_name,
            "google_place_id": None,
            "match_method": "name_only",
            "match_confidence": confidence,
            "matched_name": matched_name,
        }
        self._cache[cache_key] = result
        self._persist_cache()
        return result

    def _load_cache(self) -> dict[str, GeocodeResult]:
        if not self.cache_path.exists():
            return {}
        with self.cache_path.open("r", encoding="utf-8") as cache_file:
            data = json.load(cache_file)
        if isinstance(data, dict):
            return cast(dict[str, GeocodeResult], data)
        return {}

    def _persist_cache(self) -> None:
        with self.cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(self._cache, cache_file, indent=2, sort_keys=True)

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
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> float:
    earth_radius_km = 6371.0
    lat1 = math.radians(origin_lat)
    lng1 = math.radians(origin_lng)
    lat2 = math.radians(dest_lat)
    lng2 = math.radians(dest_lng)

    # noinspection SpellCheckingInspection
    dlat = lat2 - lat1
    # noinspection SpellCheckingInspection
    dlng = lng2 - lng1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def enrich_suppliers_with_geodata(
    suppliers: Sequence[SupplierRecord],
    company_location: tuple[float, float],
    geocoder: Optional[NominatimGeocoder],
) -> list[SupplierRecord]:
    company_lat, company_lng = company_location
    for supplier in suppliers:
        if geocoder is None:
            logger.warning(
                "Skipping geocoding for supplier %s because no Nominatim geocoder was configured.",
                supplier.name,
            )
            supplier.address = ""
            supplier.lat = None
            supplier.lng = None
            supplier.distance_km = None
            supplier.resolved_address = None
            supplier.google_place_id = None
            supplier.match_method = None
            supplier.match_confidence = None
            continue

        try:
            geocode_result = geocoder.geocode_supplier(supplier.name)
            supplier.address = geocode_result["resolved_address"] or ""
            supplier.resolved_address = geocode_result["resolved_address"] or None
            supplier.google_place_id = geocode_result["google_place_id"]
            supplier.match_method = geocode_result["match_method"]
            supplier.match_confidence = geocode_result["match_confidence"]

            if supplier.match_confidence == "low":
                logger.warning(
                    "Low-confidence Nominatim match for supplier %s: %s",
                    supplier.name,
                    geocode_result["matched_name"],
                )
                supplier.lat = None
                supplier.lng = None
                supplier.distance_km = None
                continue

            lat = geocode_result["lat"]
            lng = geocode_result["lng"]
            supplier.lat = lat
            supplier.lng = lng
            supplier.distance_km = haversine_distance_km(
                company_lat,
                company_lng,
                lat,
                lng,
            )
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "Failed to geocode supplier %s: %s",
                supplier.name,
                exc,
            )
            supplier.address = ""
            supplier.lat = None
            supplier.lng = None
            supplier.distance_km = None
            supplier.resolved_address = None
            supplier.google_place_id = None
            supplier.match_method = "name_only"
            supplier.match_confidence = "low"

    return list(suppliers)
