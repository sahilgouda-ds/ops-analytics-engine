CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.vw_sales_detail AS
SELECT
    oi.order_id,
    oi.order_item_id,
    o.order_status,
    CAST(o.order_purchase_timestamp AS DATE) AS order_date,
    CAST(DATE_TRUNC('month', o.order_purchase_timestamp) AS DATE) AS order_month,
    c.customer_state,
    c.customer_city,
    p.product_category_english AS category,
    s.seller_state,
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value AS item_total,
    o.is_late,
    o.delivery_delay_days
FROM warehouse.fact_order_items oi
JOIN warehouse.fact_orders   o ON o.order_id    = oi.order_id
JOIN warehouse.dim_customers c ON c.customer_id = o.customer_id
JOIN warehouse.dim_products  p ON p.product_id  = oi.product_id
JOIN warehouse.dim_sellers   s ON s.seller_id   = oi.seller_id;


CREATE OR REPLACE VIEW analytics.vw_monthly_kpis AS
WITH sales AS (
    SELECT order_month,
           COUNT(DISTINCT order_id) AS orders,
           SUM(price) AS revenue
    FROM analytics.vw_sales_detail
    WHERE order_status <> 'canceled'
    GROUP BY order_month
),
delivery AS (
    SELECT CAST(DATE_TRUNC('month', order_purchase_timestamp) AS DATE) AS order_month,
           ROUND(100.0 * AVG(CASE WHEN is_late THEN 0 ELSE 1 END), 2) AS on_time_pct,
           ROUND(AVG(EXTRACT(DAY FROM (order_delivered_customer_date - order_purchase_timestamp))), 1) AS avg_delivery_days
    FROM warehouse.fact_orders
    WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL
    GROUP BY 1
)
SELECT s.order_month,
       s.orders,
       s.revenue,
       ROUND(s.revenue / s.orders, 2) AS avg_order_value,
       d.on_time_pct,
       d.avg_delivery_days,
       ROUND(100.0 * (s.revenue - LAG(s.revenue) OVER (ORDER BY s.order_month))
             / NULLIF(LAG(s.revenue) OVER (ORDER BY s.order_month), 0), 2) AS revenue_mom_pct
FROM sales s
LEFT JOIN delivery d USING (order_month);


CREATE OR REPLACE VIEW analytics.vw_state_delivery AS
SELECT
    c.customer_state,
    COUNT(*) AS delivered_orders,
    ROUND(100.0 * AVG(CASE WHEN o.is_late THEN 1 ELSE 0 END), 2) AS late_pct,
    ROUND(AVG(EXTRACT(DAY FROM (o.order_delivered_customer_date - o.order_purchase_timestamp))), 1) AS avg_delivery_days,
    RANK() OVER (ORDER BY AVG(CASE WHEN o.is_late THEN 1 ELSE 0 END) DESC) AS late_rank
FROM warehouse.fact_orders o
JOIN warehouse.dim_customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state;



CREATE OR REPLACE VIEW analytics.vw_category_performance AS
WITH cat AS (
    SELECT p.product_category_english AS category,
           COUNT(*) AS items_sold,
           SUM(oi.price) AS revenue
    FROM warehouse.fact_order_items oi
    JOIN warehouse.dim_products p ON p.product_id = oi.product_id
    GROUP BY p.product_category_english
),
rev AS (
    SELECT p.product_category_english AS category,
           ROUND(AVG(r.review_score), 2) AS avg_review_score
    FROM warehouse.fact_order_items oi
    JOIN warehouse.dim_products p ON p.product_id = oi.product_id
    JOIN warehouse.fact_reviews r ON r.order_id = oi.order_id
    GROUP BY p.product_category_english
)
SELECT c.category,
       c.items_sold,
       c.revenue,
       rv.avg_review_score,
       RANK() OVER (ORDER BY c.revenue DESC) AS revenue_rank
FROM cat c
LEFT JOIN rev rv USING (category);