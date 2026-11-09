CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts ON warehouse.fact_orders (order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_orders_customer    ON warehouse.fact_orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_items_product      ON warehouse.fact_order_items (product_id);
CREATE INDEX IF NOT EXISTS idx_items_seller       ON warehouse.fact_order_items (seller_id);
CREATE INDEX IF NOT EXISTS idx_reviews_order      ON warehouse.fact_reviews (order_id);
CREATE INDEX IF NOT EXISTS idx_customers_state    ON warehouse.dim_customers (customer_state);

ANALYZE;