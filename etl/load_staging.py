
import pandas as pd
from pathlib import Path
from db import get_engine

RAW = Path("data/raw")

FILES = {
    "customers":            "olist_customers_dataset.csv",
    "geolocation":          "olist_geolocation_dataset.csv",
    "order_items":          "olist_order_items_dataset.csv",
    "order_payments":       "olist_order_payments_dataset.csv",
    "order_reviews":        "olist_order_reviews_dataset.csv",
    "orders":               "olist_orders_dataset.csv",
    "products":             "olist_products_dataset.csv",
    "sellers":              "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

engine = get_engine()

for table, filename in FILES.items():
    df = pd.read_csv(RAW / filename, dtype=str)
    df.to_sql(
        table,
        engine,
        schema="staging",
        if_exists="replace",
        index=False,
        chunksize=5000,
    )
    print(f"{table}: {len(df):,} rows loaded")

print("Staging load complete")