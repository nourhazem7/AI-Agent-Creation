#!/usr/bin/env python
"""Builds backend/storage/demo/demo_ecommerce.db — a small local SQLite database used to
smoke-test AgentForge's database-connection, knowledge-asset, and validation flows without
requiring a real Postgres/MySQL/SQL Server instance.

Schema/data adapted from text2sql-framework-main/examples/demo_with_dummy_db.py (that
script also calls TextSQL.ask() in a loop; this one only builds the database).

Usage:
    backend/.venv/Scripts/python.exe backend/scripts/seed_demo_db.py
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "storage", "demo", "demo_ecommerce.db")
DB_PATH = os.path.abspath(DB_PATH)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}")

with engine.connect() as conn:
    for t in ["order_items", "orders", "products", "categories", "customers", "regions"]:
        conn.execute(text(f"DROP TABLE IF EXISTS {t}"))

    conn.execute(text("""
        CREATE TABLE regions (
            region_id INTEGER PRIMARY KEY,
            region_name TEXT NOT NULL,
            country TEXT NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE,
            region_id INTEGER NOT NULL,
            signup_date TEXT NOT NULL,
            FOREIGN KEY (region_id) REFERENCES regions(region_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            category_name TEXT NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            total_amount REAL NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE order_items (
            item_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """))

    conn.execute(text("INSERT INTO regions VALUES (1,'Northeast','USA'),(2,'West Coast','USA'),(3,'Ontario','Canada'),(4,'London','UK'),(5,'Bavaria','Germany')"))
    conn.execute(text("INSERT INTO customers VALUES (1,'Alice','Johnson','alice@ex.com',1,'2023-01-15'),(2,'Bob','Smith','bob@ex.com',2,'2023-02-20'),(3,'Charlie','Brown','charlie@ex.com',3,'2023-03-10'),(4,'Diana','Prince','diana@ex.com',4,'2023-04-05'),(5,'Eve','Williams','eve@ex.com',1,'2023-05-12'),(6,'Frank','Miller','frank@ex.com',2,'2023-06-18'),(7,'Grace','Lee','grace@ex.com',5,'2023-07-22'),(8,'Hank','Davis','hank@ex.com',3,'2023-08-30')"))
    conn.execute(text("INSERT INTO categories VALUES (1,'Electronics'),(2,'Books'),(3,'Clothing'),(4,'Home & Garden')"))
    conn.execute(text("INSERT INTO products VALUES (1,'Wireless Headphones',1,79.99,150),(2,'USB-C Cable',1,12.99,500),(3,'Python Crash Course',2,35.99,200),(4,'Data Science Handbook',2,45.99,120),(5,'Running Shoes',3,89.99,80),(6,'Winter Jacket',3,149.99,45),(7,'Standing Desk',4,399.99,30),(8,'Desk Lamp',4,34.99,200),(9,'Mechanical Keyboard',1,129.99,100),(10,'Monitor 27in',1,299.99,60)"))
    conn.execute(text("INSERT INTO orders VALUES (1,1,'2024-01-05','completed',115.98),(2,1,'2024-01-20','completed',399.99),(3,2,'2024-01-12','completed',35.99),(4,3,'2024-02-01','completed',239.98),(5,4,'2024-02-14','completed',89.99),(6,5,'2024-02-28','completed',549.98),(7,2,'2024-03-05','completed',129.99),(8,6,'2024-03-15','completed',184.98),(9,7,'2024-03-22','completed',79.99),(10,1,'2024-04-01','completed',329.98),(11,3,'2024-04-10','completed',45.99),(12,8,'2024-04-20','completed',434.98),(13,4,'2024-05-01','shipped',164.98),(14,5,'2024-05-15','shipped',89.99),(15,2,'2024-05-20','pending',299.99)"))
    conn.execute(text("INSERT INTO order_items VALUES (1,1,1,1,79.99),(2,1,3,1,35.99),(3,2,7,1,399.99),(4,3,3,1,35.99),(5,4,5,1,89.99),(6,4,6,1,149.99),(7,5,5,1,89.99),(8,6,7,1,399.99),(9,6,6,1,149.99),(10,7,9,1,129.99),(11,8,6,1,149.99),(12,8,3,1,34.99),(13,9,1,1,79.99),(14,10,10,1,299.99),(15,10,2,1,29.99),(16,11,4,1,45.99),(17,12,7,1,399.99),(18,12,8,1,34.99),(19,13,9,1,129.99),(20,13,3,1,34.99),(21,14,5,1,89.99),(22,15,10,1,299.99)"))
    conn.commit()

print(f"Demo database ready at: {DB_PATH}")
