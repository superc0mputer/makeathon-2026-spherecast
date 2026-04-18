import os
import sys
import sqlite3
import argparse
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.cache_service import init_db
from src.services.fdc_service import FDCService
from src.services.pubchem_service import enrich_ingredient
from src.services.supplier_db_service import ingredient_name_from_sku

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Pre-warm cache for USDA nutrition data and PubChem.")
    parser.add_argument("--max-age", type=int, default=30, help="Max age in days before refetching (default: 30)")
    args = parser.parse_args()

    print("=====================================================")
    print("🌱 SMART INGREDIENT SUBSTITUTION - CACHE SEEDER")
    print("=====================================================")
    
    init_db()
    
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'db.sqlite')
    if not os.path.exists(db_path):
        print(f"❌ Could not find database at {db_path}")
        return

    print("Loading all raw materials from database...")
    try:
        # Load directly from SQLite
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT DISTINCT SKU FROM Product WHERE Type = 'raw-material'")
        skus = [row[0] for row in cur.fetchall()]
        con.close()
        
        # Convert SKUs to real names and deduplicate
        materials = list(set([ingredient_name_from_sku(sku) for sku in skus]))
        print(f"Found {len(materials)} raw materials.")
    except Exception as e:
        print(f"❌ Error loading from database: {e}")
        return

    fdc_api_key = os.environ.get("FDC_API_KEY")
    fdc_service = FDCService(api_key=fdc_api_key)

    print(f"\nStarting seed process checking cache max age of {args.max_age} days. This may take a while depending on API rate limits...")
    
    success_count = 0
    for i, name in enumerate(materials):
        print(f"[{i+1}/{len(materials)}] Fetching data for: {name}")
        
        # 1. PubChem Cache Check/Fetch
        print(f"  -> PubChem... ", end="", flush=True)
        try:
            # Note: enrich_ingredient needs to support max_age_days
            profile = enrich_ingredient(name, rate_limit=True, max_age_days=args.max_age)
            print(f"Status: {profile.status.value if hasattr(profile.status, 'value') else profile.status}")
        except Exception as e:
            print(f"Error: {e}")
            
        # 2. FDC Cache Check/Fetch
        print(f"  -> FoodData Central... ", end="", flush=True)
        try:
            fdc_result = fdc_service.get_nutritional_profile(name, max_age_days=args.max_age)
            print(f"Status: {fdc_result.get('status')}")
        except Exception as e:
            print(f"Error: {e}")
            
        success_count += 1
        
    print("\n=====================================================")
    print(f"✅ Seeding Complete! Processed {success_count} materials.")
    print("=====================================================")

if __name__ == "__main__":
    main()
