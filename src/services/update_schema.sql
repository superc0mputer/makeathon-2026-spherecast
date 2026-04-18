-- update_schema.sql
-- Run this in your SQLite client to add the nutrition table

CREATE TABLE IF NOT EXISTS Product_Nutrition (
    ProductId INTEGER PRIMARY KEY,
    FdcId INTEGER,
    Description TEXT,
    Protein_g REAL,
    Fat_g REAL,
    Carbs_g REAL,
    Water_g REAL,
    FOREIGN KEY (ProductId) REFERENCES Product(Id)
);