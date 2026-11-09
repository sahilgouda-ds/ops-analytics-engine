import pandas as pd
from sqlalchemy import text


def _num(series, integer=False):
    s = pd.to_numeric(series, errors="coerce")
    return s.round().astype("Int64") if integer else s


def clean_customers(df, engine):
    df = df.drop_duplicates("customer_id").copy()
    df["customer_zip_code_prefix"] = _num(df["customer_zip_code_prefix"], True)
    df["customer_city"] = df["customer_city"].str.strip().str.title()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    return df[["customer_id", "customer_unique_id", "customer_zip_code_prefix",
               "customer_city", "customer_state"]]


def clean_sellers(df, engine):
    df = df.drop_duplicates("seller_id").copy()
    df["seller_zip_code_prefix"] = _num(df["seller_zip_code_prefix"], True)
    df["seller_city"] = df["seller_city"].str.strip().str.title()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    return df[["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"]]


def clean_products(df, engine):
    df = df.drop_duplicates("product_id").copy()
    df = df.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    trans = pd.read_sql("SELECT * FROM staging.category_translation", engine)
    df = df.merge(trans, on="product_category_name", how="left")
    df = df.rename(columns={"product_category_name_english": "product_category_english"})
    df["product_category_english"] = (
        df["product_category_english"].fillna(df["product_category_name"]).fillna("unknown")
    )
    df["product_category_name"] = df["product_category_name"].fillna("unknown")

    int_cols = ["product_name_length", "product_description_length", "product_photos_qty"]
    dec_cols = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
    for c in int_cols:
        df[c] = _num(df[c])
        df[c] = df[c].fillna(df[c].median()).round().astype("Int64")
    for c in dec_cols:
        df[c] = _num(df[c])
        df[c] = df[c].fillna(df[c].median())
    return df[["product_id", "product_category_name", "product_category_english"]
              + int_cols + dec_cols]


def clean_orders(df, engine):
    df = df.drop_duplicates("order_id").copy()
    date_cols = ["order_purchase_timestamp", "order_approved_at",
                 "order_delivered_carrier_date", "order_delivered_customer_date",
                 "order_estimated_delivery_date"]
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    delivered = df["order_delivered_customer_date"]
    estimated = df["order_estimated_delivery_date"]
    df["delivery_delay_days"] = (delivered - estimated).dt.days.astype("Int64")
    df["is_late"] = (delivered > estimated).astype("boolean").mask(delivered.isna())
    return df[["order_id", "customer_id", "order_status"] + date_cols
              + ["delivery_delay_days", "is_late"]]


def clean_items(df, engine):
    df = df.drop_duplicates(["order_id", "order_item_id"]).copy()
    df["order_item_id"] = _num(df["order_item_id"], True)
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")
    df["price"] = _num(df["price"])
    df["freight_value"] = _num(df["freight_value"])
    return df[["order_id", "order_item_id", "product_id", "seller_id",
               "shipping_limit_date", "price", "freight_value"]]


def clean_payments(df, engine):
    df = df.drop_duplicates(["order_id", "payment_sequential"]).copy()
    df["payment_sequential"] = _num(df["payment_sequential"], True)
    df["payment_installments"] = _num(df["payment_installments"], True)
    df["payment_value"] = _num(df["payment_value"])
    return df[["order_id", "payment_sequential", "payment_type",
               "payment_installments", "payment_value"]]


def clean_reviews(df, engine):
    df = df.copy()
    df["review_score"] = _num(df["review_score"], True)
    df["review_creation_date"] = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    return df[["review_id", "order_id", "review_score", "review_comment_title",
               "review_comment_message", "review_creation_date", "review_answer_timestamp"]]


CLEANERS = {
    "customers": clean_customers,
    "sellers": clean_sellers,
    "products": clean_products,
    "orders": clean_orders,
    "order_items": clean_items,
    "order_payments": clean_payments,
    "order_reviews": clean_reviews,
}

# key: (warehouse table, unique key columns, [(column, parent table, parent column)])
TARGETS = {
    "customers": ("dim_customers", ["customer_id"], []),
    "sellers": ("dim_sellers", ["seller_id"], []),
    "products": ("dim_products", ["product_id"], []),
    "orders": ("fact_orders", ["order_id"],
               [("customer_id", "dim_customers", "customer_id")]),
    "order_items": ("fact_order_items", ["order_id", "order_item_id"],
                    [("order_id", "fact_orders", "order_id"),
                     ("product_id", "dim_products", "product_id"),
                     ("seller_id", "dim_sellers", "seller_id")]),
    "order_payments": ("fact_payments", ["order_id", "payment_sequential"],
                       [("order_id", "fact_orders", "order_id")]),
    "order_reviews": ("fact_reviews", None,
                      [("order_id", "fact_orders", "order_id")]),
}


def load_to_warehouse(key, raw_df, engine):
    clean_df = CLEANERS[key](raw_df, engine)
    target, conflict, parents = TARGETS[key]

    ready = clean_df
    for col, ptable, pcol in parents:
        valid = pd.read_sql(f"SELECT {pcol} FROM warehouse.{ptable}", engine)[pcol]
        ready = ready[ready[col].isin(valid)]

    inserted = 0
    if not ready.empty:
        tmp = f"tmp_{target}"
        cols = ", ".join(ready.columns)
        if conflict:
            sql = (f"INSERT INTO warehouse.{target} ({cols}) "
                   f"SELECT {cols} FROM warehouse.{tmp} "
                   f"ON CONFLICT ({', '.join(conflict)}) DO NOTHING")
        else:
            sql = (f"INSERT INTO warehouse.{target} ({cols}) "
                   f"SELECT {cols} FROM warehouse.{tmp} s "
                   f"WHERE NOT EXISTS (SELECT 1 FROM warehouse.{target} t "
                   f"WHERE t.review_id = s.review_id AND t.order_id = s.order_id)")
        with engine.begin() as conn:
            ready.to_sql(tmp, conn, schema="warehouse", if_exists="replace",
                         index=False, chunksize=5000)
            inserted = conn.execute(text(sql)).rowcount
            conn.execute(text(f"DROP TABLE warehouse.{tmp}"))

    return {
        "target_table": f"warehouse.{target}",
        "rows_uploaded": len(raw_df),
        "rows_after_cleaning": len(clean_df),
        "skipped_missing_parent": len(clean_df) - len(ready),
        "skipped_already_exists": len(ready) - inserted,
        "rows_inserted": inserted,
    }