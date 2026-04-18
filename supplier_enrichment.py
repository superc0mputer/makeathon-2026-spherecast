from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping, Sequence, Union

from models import SupplierRecord, SupplierRecordDict
from services import (
    NominatimGeocoder,
    enrich_suppliers_with_geodata,
    find_suppliers_for_ingredients,
)


logging.basicConfig(level=logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_ROOT / "db.sqlite"

# Temporary until the substitute-generation phase is wired in.
# noinspection SpellCheckingInspection
MOCK_SHORTLISTED_SUBSTITUTES = [
    "RM-C2-ascorbic-acid-4823fabf",
    "RM-C1-magnesium-stearate-fdedf242",
    "RM-unknown-substitute-00000000",
]


def enrich_shortlisted_substitutes_with_suppliers(
    shortlisted_substitutes: Sequence[str],
    company_coords: tuple[float, float],
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> dict[str, list[SupplierRecord]]:
    suppliers_by_ingredient = find_suppliers_for_ingredients(
        db_path=str(db_path),
        ingredient_skus=shortlisted_substitutes,
    )

    geocoder = NominatimGeocoder()

    for ingredient_sku, suppliers in suppliers_by_ingredient.items():
        suppliers_by_ingredient[ingredient_sku] = enrich_suppliers_with_geodata(
            suppliers=suppliers,
            company_location=company_coords,
            geocoder=geocoder,
        )

    return suppliers_by_ingredient


def supplier_results_to_dict(
    suppliers_by_ingredient: Mapping[str, Sequence[SupplierRecord]],
) -> dict[str, list[SupplierRecordDict]]:
    return {
        ingredient_sku: [supplier.to_dict() for supplier in suppliers]
        for ingredient_sku, suppliers in suppliers_by_ingredient.items()
    }


if __name__ == "__main__":
    company_coords = (48.1351, 11.5820)  # Inject from pipeline input in real runs.

    enriched = enrich_shortlisted_substitutes_with_suppliers(
        shortlisted_substitutes=MOCK_SHORTLISTED_SUBSTITUTES,
        company_coords=company_coords,
    )
    print(json.dumps(supplier_results_to_dict(enriched), indent=2))
