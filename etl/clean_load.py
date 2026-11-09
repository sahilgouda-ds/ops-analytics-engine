import pandas as pd
from sqlalchemy import text
from db import get_engine

engine = get_engine()


def read(table):
    return pd.read_sql(f"SELECT * FROM staging.{table}", engine)


def num(series, integer=False):
    s = pd.to_numeric(series, errors="coerce")
    return s.round().astype("Int64") if integer else s


def load(df, table):
    df.to_sql(table, engine, schema="warehouse", if_exists="append",
              index=False, chunksize=5000)
    print(f"{table}: {len(df):,} rows loaded")


def keep_valid(df, mask, name):
    dropped = (~mask).sum()
    if dropped:
        print(f"  {name}: {dropped} rows dropped (foreign key missing)")
    return df[mask]


def clean_customers():
    df = read("customers").drop_duplicates("customer_id")
    df["customer_zip_code_prefix"] = num(df["customer_zip_code_prefix"], True)
    df["customer_city"] = df["customer_city"].str.strip().str.title()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    return df


def clean_sellers():
    df = read("sellers").drop_duplicates("seller_id")
    df["seller_zip_code_prefix"] = num(df["seller_zip_code_prefix"], True)
    df["seller_city"] = df["seller_city"].str.strip().str.title()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    return df


def clean_products():
    df = read("products").drop_duplicates("product_id")
    df = df.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    trans = read("category_translation")
    df = df.merge(trans, on="product_category_name", how="left")
    df = df.rename(columns={"product_category_name_english": "product_category_english"})

    df["product_category_english"] = (
        df["product_category_english"]
        .fillna(df["product_category_name"])
        .fillna("unknown")
    )
    df["product_category_name"] = df["product_category_name"].fillna("unknown")

    int_cols = ["product_name_length", "product_description_length", "product_photos_qty"]
    dec_cols = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
    for c in int_cols:
        df[c] = num(df[c])
        df[c] = df[c].fillna(df[c].median()).round().astype("Int64")
    for c in dec_cols:
        df[c] = num(df[c])
        df[c] = df[c].fillna(df[c].median())

    return df[["product_id", "product_category_name", "product_category_english"]
              + int_cols + dec_cols]


def clean_orders():
    df = read("orders").drop_duplicates("order_id")
    date_cols = ["order_purchase_timestamp", "order_approved_at",
                 "order_delivered_carrier_date", "order_delivered_customer_date",
                 "order_estimated_delivery_date"]
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    delivered = df["order_delivered_customer_date"]
    estimated = df["order_estimated_delivery_date"]
    df["delivery_delay_days"] = (delivered - estimated).dt.days.astype("Int64")
    df["is_late"] = (delivered > estimated).astype("boolean").mask(delivered.isna())
    return df


def clean_items():
    df = read("order_items").drop_duplicates(["order_id", "order_item_id"])
    df["order_item_id"] = num(df["order_item_id"], True)
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")
    df["price"] = num(df["price"])
    df["freight_value"] = num(df["freight_value"])
    return df


def clean_payments():
    df = read("order_payments").drop_duplicates(["order_id", "payment_sequential"])
    df["payment_sequential"] = num(df["payment_sequential"], True)
    df["payment_installments"] = num(df["payment_installments"], True)
    df["payment_value"] = num(df["payment_value"])
    return df


def clean_reviews():
    df = read("order_reviews")
    df["review_score"] = num(df["review_score"], True)
    df["review_creation_date"] = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    return df


if __name__ == "__main__":
    customers = clean_customers()
    sellers = clean_sellers()
    products = clean_products()

    orders = clean_orders()
    orders = keep_valid(orders, orders["customer_id"].isin(customers["customer_id"]), "orders")

    items = clean_items()
    items = keep_valid(
        items,
        items["order_id"].isin(orders["order_id"])
        & items["product_id"].isin(products["product_id"])
        & items["seller_id"].isin(sellers["seller_id"]),
        "order_items",
    )

    payments = clean_payments()
    payments = keep_valid(payments, payments["order_id"].isin(orders["order_id"]), "payments")

    reviews = clean_reviews()
    reviews = keep_valid(reviews, reviews["order_id"].isin(orders["order_id"]), "reviews")

    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE warehouse.fact_reviews, warehouse.fact_payments, "
            "warehouse.fact_order_items, warehouse.fact_orders, "
            "warehouse.dim_products, warehouse.dim_sellers, "
            "warehouse.dim_customers RESTART IDENTITY CASCADE"
        ))

    load(customers, "dim_customers")
    load(sellers, "dim_sellers")
    load(products, "dim_products")
    load(orders, "fact_orders")
    load(items, "fact_order_items")
    load(payments, "fact_payments")
    load(reviews, "fact_reviews")
    print("Warehouse load complete")