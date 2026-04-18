import sqlite3
import json
import os

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
            data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pubchem_cache (
            ingredient_name TEXT PRIMARY KEY,
            data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

# Initialize tables on import
init_db()

def get_fdc(ingredient_name: str) -> dict:
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT data FROM fdc_cache WHERE ingredient_name = ?", (ingredient_name.lower(),))
    row = cur.fetchone()
    con.close()
    if row:
        return json.loads(row["data"])
    return None

def set_fdc(ingredient_name: str, data: dict):
    con = _get_connection()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO fdc_cache (ingredient_name, data, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(ingredient_name) DO UPDATE SET 
        data=excluded.data, updated_at=CURRENT_TIMESTAMP
    """, (ingredient_name.lower(), json.dumps(data)))
    con.commit()
    con.close()

def get_pubchem(ingredient_name: str) -> dict:
    con = _get_connection()
    cur = con.cursor()
    cur.execute("SELECT data FROM pubchem_cache WHERE ingredient_name = ?", (ingredient_name.lower(),))
    row = cur.fetchone()
    con.close()
    if row:
        return json.loads(row["data"])
    return None

def set_pubchem(ingredient_name: str, data: dict):
    con = _get_connection()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO pubchem_cache (ingredient_name, data, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(ingredient_name) DO UPDATE SET 
        data=excluded.data, updated_at=CURRENT_TIMESTAMP
    """, (ingredient_name.lower(), json.dumps(data)))
    con.commit()
    con.close()
