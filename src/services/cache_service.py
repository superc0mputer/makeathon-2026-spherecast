import sqlite3
import json
import os
from datetime import datetime, timedelta

CACHE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cache.sqlite")

def _get_connection():
    con = sqlite3.connect(CACHE_DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = _get_connection()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fdc_cache (
            ingredient_name TEXT PRIMARY KEY,
            status TEXT,
            fdc_id INTEGER,
            description TEXT,
            category TEXT,
            protein_g REAL,
            fat_g REAL,
            carbs_g REAL,
            water_g REAL,
            other_nutrients_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pubchem_cache (
            ingredient_name TEXT PRIMARY KEY,
            status TEXT,
            cid INTEGER,
            title TEXT,
            iupac_name TEXT,
            molecular_formula TEXT,
            molecular_weight REAL,
            inchikey TEXT,
            xlogp REAL,
            charge REAL,
            is_salt INTEGER,
            is_organic INTEGER,
            description TEXT,
            synonyms_json TEXT,
            safety_hazards_json TEXT,
            element_set_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

# Initialize tables on import
init_db()

def get_fdc(ingredient_name: str, max_age_days: int = None) -> dict:
    con = _get_connection()
    cur = con.cursor()
    if max_age_days is not None:
        cur.execute("SELECT * FROM fdc_cache WHERE ingredient_name = ? AND updated_at >= datetime('now', ? || ' days')", (ingredient_name.lower(), -max_age_days))
    else:
        cur.execute("SELECT * FROM fdc_cache WHERE ingredient_name = ?", (ingredient_name.lower(),))
    row = cur.fetchone()
    con.close()
    if row:
        nutrients = json.loads(row["other_nutrients_json"] or "{}")
        
        # Restore formatted values for LLM
        if row["protein_g"] > 0: nutrients["Protein"] = f"{row['protein_g']} G"
        if row["fat_g"] > 0: nutrients["Total lipid (fat)"] = f"{row['fat_g']} G"
        if row["carbs_g"] > 0: nutrients["Carbohydrate, by difference"] = f"{row['carbs_g']} G"
        if row["water_g"] > 0: nutrients["Water"] = f"{row['water_g']} G"
        
        return {
            "status": row["status"],
            "profile": {
                "fdc_id": row["fdc_id"],
                "description": row["description"],
                "category": row["category"],
                "nutrients": nutrients
            }
        }
    return None

def set_fdc(ingredient_name: str, data: dict):
    con = _get_connection()
    cur = con.cursor()
    
    status = data.get("status")
    profile = data.get("profile", {})
    fdc_id = profile.get("fdc_id")
    desc = profile.get("description", "")
    cat = profile.get("category", "Unknown")
    
    # Extract macros as floats
    nutrients = profile.get("nutrients", {})
    def pop_float(key):
        val_str = nutrients.pop(key, None)
        if not val_str: return 0.0
        try: return float(str(val_str).split()[0].strip())
        except: return 0.0
        
    protein_g = pop_float("Protein")
    fat_g = pop_float("Total lipid (fat)")
    carbs_g = pop_float("Carbohydrate, by difference")
    water_g = pop_float("Water")
    
    other_nutrients_json = json.dumps(nutrients)
    
    cur.execute("""
        INSERT INTO fdc_cache (
            ingredient_name, status, fdc_id, description, category, 
            protein_g, fat_g, carbs_g, water_g, other_nutrients_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(ingredient_name) DO UPDATE SET 
            status=excluded.status,
            fdc_id=excluded.fdc_id,
            description=excluded.description,
            category=excluded.category,
            protein_g=excluded.protein_g,
            fat_g=excluded.fat_g,
            carbs_g=excluded.carbs_g,
            water_g=excluded.water_g,
            other_nutrients_json=excluded.other_nutrients_json,
            updated_at=CURRENT_TIMESTAMP
    """, (
        ingredient_name.lower(), status, fdc_id, desc, cat,
        protein_g, fat_g, carbs_g, water_g, other_nutrients_json
    ))
    con.commit()
    con.close()

def get_pubchem(ingredient_name: str, max_age_days: int = None) -> dict:
    con = _get_connection()
    cur = con.cursor()
    if max_age_days is not None:
        cur.execute("SELECT * FROM pubchem_cache WHERE ingredient_name = ? AND updated_at >= datetime('now', ? || ' days')", (ingredient_name.lower(), -max_age_days))
    else:
        cur.execute("SELECT * FROM pubchem_cache WHERE ingredient_name = ?", (ingredient_name.lower(),))
    row = cur.fetchone()
    con.close()
    if row:
        return {
            "query_name": row["ingredient_name"],
            "status": row["status"],
            "status_detail": "",  # Dropped from cache to save space
            "cid": row["cid"],
            "title": row["title"],
            "iupac_name": row["iupac_name"],
            "molecular_formula": row["molecular_formula"],
            "molecular_weight": row["molecular_weight"],
            "inchikey": row["inchikey"],
            "xlogp": row["xlogp"],
            "charge": row["charge"],
            "is_salt": bool(row["is_salt"]),
            "is_organic": bool(row["is_organic"]),
            "description": row["description"],
            "synonyms": json.loads(row["synonyms_json"] or "[]"),
            "safety_hazards": json.loads(row["safety_hazards_json"] or "[]"),
            "element_set": json.loads(row["element_set_json"] or "[]")
        }
    return None

def set_pubchem(ingredient_name: str, data: dict):
    con = _get_connection()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO pubchem_cache (
            ingredient_name, status, cid, title, iupac_name,
            molecular_formula, molecular_weight, inchikey, xlogp, charge,
            is_salt, is_organic, description, synonyms_json, safety_hazards_json, element_set_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(ingredient_name) DO UPDATE SET 
            status=excluded.status,
            cid=excluded.cid,
            title=excluded.title,
            iupac_name=excluded.iupac_name,
            molecular_formula=excluded.molecular_formula,
            molecular_weight=excluded.molecular_weight,
            inchikey=excluded.inchikey,
            xlogp=excluded.xlogp,
            charge=excluded.charge,
            is_salt=excluded.is_salt,
            is_organic=excluded.is_organic,
            description=excluded.description,
            synonyms_json=excluded.synonyms_json,
            safety_hazards_json=excluded.safety_hazards_json,
            element_set_json=excluded.element_set_json,
            updated_at=CURRENT_TIMESTAMP
    """, (
        ingredient_name.lower(),
        str(data.get("status")),
        data.get("cid"),
        data.get("title"),
        data.get("iupac_name"),
        data.get("molecular_formula"),
        data.get("molecular_weight"),
        data.get("inchikey"),
        data.get("xlogp"),
        data.get("charge"),
        1 if data.get("is_salt") else 0,
        1 if data.get("is_organic") else 0,
        data.get("description"),
        json.dumps(data.get("synonyms", [])),
        json.dumps(data.get("safety_hazards", [])),
        json.dumps(data.get("element_set", []))
    ))
    con.commit()
    con.close()
