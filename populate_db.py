import os
import psycopg2
from psycopg2 import extras
import csv
from pathlib import Path
import time

from utils import get_db_url


STAGING_CREATE_SQL = """
-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS Region CASCADE;
DROP TABLE IF EXISTS Country CASCADE;
DROP TABLE IF EXISTS Customer CASCADE;
DROP TABLE IF EXISTS ProductCategory CASCADE;
DROP TABLE IF EXISTS Product CASCADE;
DROP TABLE IF EXISTS OrderDetail CASCADE;


  CREATE TABLE Region (
    RegionID INTEGER PRIMARY KEY,
    Region TEXT NOT NULL
  );


  CREATE TABLE Country (
    CountryID INTEGER PRIMARY KEY,
    Country TEXT NOT NULL,
    RegionID INTEGER NOT NULL,
    FOREIGN KEY (RegionID) REFERENCES Region(RegionID)
  );



  CREATE TABLE Customer (
    CustomerID integer primary key,
    FirstName text not null,
    LastName text not null,
    Address text not null,
    City text not null,
    CountryID integer not null,
    FOREIGN KEY (CountryID) REFERENCES Country(CountryID)
  );


  CREATE TABLE ProductCategory (
    ProductCategoryID integer primary key,
    ProductCategory text not null,
    ProductCategoryDescription text not null
  );



  CREATE TABLE Product(
    ProductID integer primary key,
    ProductName text not null,
    ProductUnitPrice real not null,
    ProductCategoryID integer not null,
    FOREIGN KEY (ProductCategoryID) REFERENCES ProductCategory(ProductCategoryID)
  );


  create table OrderDetail (
    OrderID integer primary key,
    CustomerID integer not null,
    ProductID integer not null,
    OrderDate Date not null,
    QuantityOrdered integer not null,
    FOREIGN KEY (CustomerID) REFERENCES Customer(CustomerID),
    FOREIGN KEY (ProductID) REFERENCES Product(ProductID)
  );



"""

FILES = {
    "Region": {
        "filename": "datasets/Region.tsv",
     },
    "Country": {
        "filename": "datasets/Country.tsv",
     },
    "Customer": {
        "filename": "datasets/Customer.tsv",
     },
    "ProductCategory": {
        "filename": "datasets/ProductCategory.tsv",
     },
     "Product": {
        "filename": "datasets/Product.tsv",
     },
     "OrderDetail": {
        "filename": "datasets/OrderDetail.tsv",
     }
}

EXPECTED_COLUMNS = {
    "Region":[
        "RegionID" ,
        "Region" 
    ],
    "Country":[
        "CountryID",
        "Country",
        "RegionID",
    ],
    "Customer":[
        "CustomerID",
        "FirstName",
        "LastName",
        "Address",
        "City",
        "CountryID"
    ],
    "ProductCategory":[
        "ProductCategoryID",
        "ProductCategory",
        "ProductCategoryDescription"
    
    ],
    "Product":[
        "ProductID",
        "ProductName",
        "ProductUnitPrice",
        "ProductCategoryID"
    ],
    "OrderDetail": [
        "OrderID",
        "CustomerID",
        "ProductID",
        "OrderDate",
        "QuantityOrdered"
    ]
}


def load_tsv_to_stage(conn, filepath, stage_table, expected_columns, batch_size=5_000):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {filepath}")

    with path.open("r", encoding="utf-8-sig") as csvfile:
        csv_reader = csv.DictReader(csvfile, delimiter='\t')
        # validate columns
        missing = sorted(set(expected_columns) - set(csv_reader.fieldnames))
        if missing:
            raise ValueError(f"{filepath} missing expected columns: {missing}")

        placeholders = ", ".join(["%s"] * len(expected_columns))
        sql = f"INSERT INTO {stage_table} ({', '.join(expected_columns)}) VALUES ({placeholders})"
        rows = []
        row_count = 0 
        total_count = 0
        cursor = conn.cursor()
        
        cursor.execute(f"DELETE FROM {stage_table}")
        conn.commit()
        print(f"Cleaned up rows from {stage_table}")
        
        log_template = "Inserted another batch of {:,} rows; total: {:,}"
        for row in csv_reader:
            rows.append([row.get(c, None) for c in expected_columns])
            row_count += 1

            if row_count == batch_size:
                extras.execute_batch(cursor, sql, rows)
                conn.commit()
                total_count += len(rows)
                row_count = 0 
                rows = []  
                print(log_template.format(batch_size, total_count))

        if rows:
            extras.execute_batch(cursor, sql, rows)
            conn.commit()
            total_count += len(rows)  
            print(log_template.format(len(rows), total_count))

        cursor.close()
        print(f"Finished loading data into {stage_table}")




# Main execution
if __name__ == "__main__":
    
    DATABASE_URL = get_db_url()
    # Create tables
    print("Creating tables...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(STAGING_CREATE_SQL)
    conn.commit()
    cursor.close()
    conn.close()
    print("Tables created successfully\n")

    # Load staging data
    print("Loading staging data...")
    start_time = time.monotonic()
    conn = psycopg2.connect(DATABASE_URL)
    for name in FILES:
        load_tsv_to_stage(
            conn, 
            FILES[name]["filename"], 
            f"{name}", 
            EXPECTED_COLUMNS[name], 
            FILES[name].get("batch_size", 5_000)
        )
    conn.close()
    end_time = time.monotonic()
    elapsed_time = end_time - start_time
    print(f"\nStaging data loaded. Elapsed time: {elapsed_time:.2f} seconds\n")

   
    
    print("\n✅ Database migration complete!")