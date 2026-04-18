import sqlite3
import json
import random
import re

def generate_mock_pricing():
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute("SELECT SKU FROM Product WHERE Type='raw-material'")
    rows = c.fetchall()
    
    prices = {}
    for r in rows:
        sku = r[0] # e.g., RM-C1-calcium-citrate-05c28cc3
        
        # Extract the name part between the prefix and the hex ID
        match = re.search(r'RM-[a-zA-Z0-9]+-(.+)-[a-f0-9]+', sku)
        if match:
            name = match.group(1).replace('-', ' ').title()
        else:
            name = sku.title()

        # Seed random with name so prices are consistent across regenerations
        random.seed(name)
        prices[name] = {"price_per_kg": round(random.uniform(1.0, 50.0), 2)}

    with open('src/data/mock_database.json', 'w') as f:
        json.dump(prices, f, indent=4)

if __name__ == "__main__":
    generate_mock_pricing()
    print("Generated mock pricing for all raw materials in db.sqlite")