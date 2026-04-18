"""
fetch_nutrition.py
Fetches nutritional data from the USDA FoodData Central API for raw materials.
"""

import sqlite3
import requests
import time
import re

# Get your free key at https://fdc.nal.usda.gov/api-key-signup.html
FDC_API_KEY = "***REMOVED***"
SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
DEFAULT_DB = "/Users/simon/Universitaet/Makeathon/makeathon-2026-spherecast/db.sqlite"

# Your exact regex pattern
RAW_MATERIAL_SKU_RE = re.compile(r"^RM-[^-]+-(?P<slug>.+)-[0-9a-f]{8}$")


def translate_sku_to_search_term(sku: str) -> str:
    """
    Extracts the clean ingredient name from the internal SKU format.
    Example: 'RM-C3-sugar-ef04e1fd' -> 'sugar'
    """
    match = RAW_MATERIAL_SKU_RE.match(sku)
    if not match:
        return sku  # Fallback to the raw SKU if it doesn't match the pattern

    return match.group("slug").replace("-", " ")


def fetch_nutrition_vector(search_term: str) -> dict:
    params = {
        "query": search_term,
        "api_key": FDC_API_KEY,
        "pageSize": 1,
        "dataType": ["Foundation", "SR Legacy"]
    }

    try:
        response = requests.get(SEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get('foods'):
            return None

        food = data['foods'][0]
        nutrients = {n['nutrientName']: n['value'] for n in food['foodNutrients']}

        return {
            "FdcId": food.get('fdcId'),
            "Description": food.get('description'),
            "Protein_g": nutrients.get("Protein", 0.0),
            "Fat_g": nutrients.get("Total lipid (fat)", 0.0),
            "Carbs_g": nutrients.get("Carbohydrate, by difference", 0.0),
            "Water_g": nutrients.get("Water", 0.0)
        }
    except Exception as e:
        print(f"      [!] API Error for '{search_term}': {e}")
        return None


def main():
    con = sqlite3.connect(DEFAULT_DB)
    cursor = con.cursor()

    # Get all raw materials that don't already have nutrition data
    query = """
            SELECT Id, SKU \
            FROM Product
            WHERE Type = 'raw-material'
              AND Id NOT IN (SELECT ProductId FROM Product_Nutrition) \
            """
    cursor.execute(query)
    raw_materials = cursor.fetchall()

    print(f"Found {len(raw_materials)} raw materials needing nutrition data.")

    for prod_id, sku in raw_materials:
        search_term = translate_sku_to_search_term(sku)

        if not search_term:
            print(f"  [-] Skipping {sku} (No search term mapping found)")
            continue

        print(f"  [+] Fetching data for {sku} as '{search_term}'...")
        nutrition_data = fetch_nutrition_vector(search_term)

        if nutrition_data:
            cursor.execute("""
                           INSERT INTO Product_Nutrition
                               (ProductId, FdcId, Description, Protein_g, Fat_g, Carbs_g, Water_g)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           """, (
                               prod_id,
                               nutrition_data['FdcId'],
                               nutrition_data['Description'],
                               nutrition_data['Protein_g'],
                               nutrition_data['Fat_g'],
                               nutrition_data['Carbs_g'],
                               nutrition_data['Water_g']
                           ))
            con.commit()
        else:
            print(f"      [!] No USDA results found for '{search_term}'")

        # Be polite to the API
        time.sleep(0.5)

    con.close()
    print("Finished updating nutrition data.")


if __name__ == "__main__":
    main()