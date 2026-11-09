CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;

DROP TABLE IF EXISTS
    warehouse.fact_reviews,
    warehouse.fact_payments,
    warehouse.fact_order_items,
    warehouse.fact_orders,
    warehouse.dim_products,
    warehouse.dim_sellers,
    warehouse.dim_customers
CASCADE;

CREATE TABLE warehouse.dim_customers (
    customer_id              VARCHAR(32) PRIMARY KEY,
    customer_unique_id       VARCHAR(32) NOT NULL,
    customer_zip_code_prefix INTEGER,
    customer_city            VARCHAR(100),
    customer_state           CHAR(2)
);

CREATE TABLE warehouse.dim_sellers (
    seller_id              VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix INTEGER,
    seller_city            VARCHAR(100),
    seller_state           CHAR(2)
);

CREATE TABLE warehouse.dim_products (
    product_id                  VARCHAR(32) PRIMARY KEY,
    product_category_name       VARCHAR(100),
    product_category_english    VARCHAR(100),
    product_name_length         INTEGER,
    product_description_length  INTEGER,
    product_photos_qty          INTEGER,
    product_weight_g            NUMERIC(10,2),
    product_length_cm           NUMERIC(10,2),
    product_height_cm           NUMERIC(10,2),
    product_width_cm            NUMERIC(10,2)
);

CREATE TABLE warehouse.fact_orders (
    order_id                      VARCHAR(32) PRIMARY KEY,
    customer_id                   VARCHAR(32) NOT NULL
        REFERENCES warehouse.dim_customers (customer_id),
    order_status                  VARCHAR(20) NOT NULL,
    order_purchase_timestamp      TIMESTAMP,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    delivery_delay_days           INTEGER,
    is_late                       BOOLEAN
);

CREATE TABLE warehouse.fact_order_items (
    order_id            VARCHAR(32) NOT NULL
        REFERENCES warehouse.fact_orders (order_id),
    order_item_id       INTEGER NOT NULL,
    product_id          VARCHAR(32) NOT NULL
        REFERENCES warehouse.dim_products (product_id),
    seller_id           VARCHAR(32) NOT NULL
        REFERENCES warehouse.dim_sellers (seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(10,2),
    freight_value       NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE warehouse.fact_payments (
    order_id             VARCHAR(32) NOT NULL
        REFERENCES warehouse.fact_orders (order_id),
    payment_sequential   INTEGER NOT NULL,
    payment_type         VARCHAR(30),
    payment_installments INTEGER,
    payment_value        NUMERIC(10,2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE warehouse.fact_reviews (
    review_sk               SERIAL PRIMARY KEY,
    review_id               VARCHAR(32),
    order_id                VARCHAR(32) NOT NULL
        REFERENCES warehouse.fact_orders (order_id),
    review_score            INTEGER,
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);