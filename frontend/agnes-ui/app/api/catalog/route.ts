import { execFileSync } from 'node:child_process'
import path from 'node:path'

import { NextRequest, NextResponse } from 'next/server'

const dbPath = path.resolve(process.cwd(), '..', '..', 'db.sqlite')

const pythonScript = `
import json
import sqlite3
import sys

db_path = sys.argv[1]
company_id = sys.argv[2]
product_id = sys.argv[3]

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

def decode_sku(sku: str) -> str:
    parts = sku.split('-')
    if len(parts) >= 4 and parts[0] == 'RM':
        return ' '.join(parts[2:-1]).replace('-', ' ')
    return sku

response = {}

companies = conn.execute(
    """
    SELECT c.Id, c.Name, COUNT(p.Id) AS product_count
    FROM Company c
    JOIN Product p
      ON p.CompanyId = c.Id
     AND p.Type = 'finished-good'
    GROUP BY c.Id, c.Name
    ORDER BY c.Name
    """
).fetchall()

response["companies"] = [
    {
        "id": row["Id"],
        "name": row["Name"],
        "productCount": row["product_count"],
    }
    for row in companies
]

if company_id and company_id != "null":
    products = conn.execute(
        """
        SELECT p.Id, p.SKU, COUNT(bc.ConsumedProductId) AS ingredient_count
        FROM Product p
        LEFT JOIN BOM b
          ON b.ProducedProductId = p.Id
        LEFT JOIN BOM_Component bc
          ON bc.BOMId = b.Id
        WHERE p.Type = 'finished-good'
          AND p.CompanyId = ?
        GROUP BY p.Id, p.SKU
        ORDER BY p.SKU
        """,
        (company_id,),
    ).fetchall()

    response["products"] = [
        {
            "id": row["Id"],
            "sku": row["SKU"],
            "label": row["SKU"].replace("FG-", "").replace("-", " "),
            "ingredientCount": row["ingredient_count"],
        }
        for row in products
    ]

if product_id and product_id != "null":
    product = conn.execute(
        """
        SELECT p.Id, p.SKU, c.Id AS company_id, c.Name AS company_name
        FROM Product p
        JOIN Company c
          ON c.Id = p.CompanyId
        WHERE p.Id = ?
        """,
        (product_id,),
    ).fetchone()

    ingredients = conn.execute(
        """
        SELECT rp.Id, rp.SKU
        FROM BOM b
        JOIN BOM_Component bc
          ON bc.BOMId = b.Id
        JOIN Product rp
          ON rp.Id = bc.ConsumedProductId
        WHERE b.ProducedProductId = ?
        ORDER BY rp.SKU
        """,
        (product_id,),
    ).fetchall()

    response["selectedProduct"] = (
        {
            "id": product["Id"],
            "sku": product["SKU"],
            "label": product["SKU"].replace("FG-", "").replace("-", " "),
            "companyId": product["company_id"],
            "companyName": product["company_name"],
            "ingredients": [
                {
                    "id": row["Id"],
                    "sku": row["SKU"],
                    "name": decode_sku(row["SKU"]).title(),
                }
                for row in ingredients
            ],
        }
        if product
        else None
    )

conn.close()
print(json.dumps(response))
`

export async function GET(request: NextRequest) {
  try {
    const companyId = request.nextUrl.searchParams.get('companyId')
    const productId = request.nextUrl.searchParams.get('productId')

    const raw = execFileSync('python3', ['-c', pythonScript, dbPath, companyId ?? 'null', productId ?? 'null'], {
      encoding: 'utf-8',
    })

    return NextResponse.json(JSON.parse(raw))
  } catch (error) {
    console.error('Failed to load catalog data', error)
    return NextResponse.json({ error: 'Failed to load catalog data' }, { status: 500 })
  }
}
