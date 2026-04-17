from __future__ import annotations

import re
import sqlite3
from typing import Sequence, cast

from models import SupplierRecord


RAW_MATERIAL_SKU_RE = re.compile(r"^RM-[^-]+-(?P<slug>.+)-[0-9a-f]{8}$")


def ingredient_name_from_sku(sku: str) -> str:
    match = RAW_MATERIAL_SKU_RE.match(sku)
    if not match:
        return sku
    return match.group("slug").replace("-", " ")


def find_suppliers_for_ingredients(
    db_path: str,
    ingredient_skus: Sequence[str],
) -> dict[str, list[SupplierRecord]]:
    requested_skus = list(dict.fromkeys(sku for sku in ingredient_skus if sku))
    suppliers_by_ingredient = {sku: [] for sku in requested_skus}
    if not requested_skus:
        return suppliers_by_ingredient

    placeholders = ",".join("?" for _ in requested_skus)
    query = f"""
        SELECT
            target.SKU AS target_ingredient_sku,
            s.Id AS supplier_id,
            s.Name AS supplier_name,
            stocked.SKU AS stocked_ingredient_sku
        FROM Product AS target
        JOIN Supplier_Product AS target_sp
            ON target_sp.ProductId = target.Id
        JOIN Supplier AS s
            ON s.Id = target_sp.SupplierId
        JOIN Supplier_Product AS stocked_sp
            ON stocked_sp.SupplierId = s.Id
        JOIN Product AS stocked
            ON stocked.Id = stocked_sp.ProductId
        WHERE target.Type = 'raw-material'
          AND stocked.Type = 'raw-material'
          AND target.SKU IN ({placeholders})
        ORDER BY target.SKU, s.Id, stocked.SKU
    """

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, requested_skus).fetchall()

    grouped: dict[str, dict[int, SupplierRecord]] = {
        sku: {} for sku in requested_skus
    }
    for row in rows:
        ingredient_sku = cast(str, row["target_ingredient_sku"])
        supplier_id = int(row["supplier_id"])
        supplier = grouped[ingredient_sku].get(supplier_id)
        if supplier is None:
            supplier = SupplierRecord(
                supplier_id=supplier_id,
                name=cast(str, row["supplier_name"]),
            )
            grouped[ingredient_sku][supplier_id] = supplier

        stocked_ingredient = ingredient_name_from_sku(cast(str, row["stocked_ingredient_sku"]))
        if stocked_ingredient not in supplier.stocked_ingredients:
            supplier.stocked_ingredients.append(stocked_ingredient)

    for ingredient_sku, supplier_map in grouped.items():
        suppliers_by_ingredient[ingredient_sku] = list(supplier_map.values())

    return suppliers_by_ingredient
