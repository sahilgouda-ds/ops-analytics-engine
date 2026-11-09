import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent / "etl"))
from db import get_engine
from loader import load_to_warehouse

st.set_page_config(page_title="Ops Analytics Engine", page_icon="📊", layout="wide")

st.markdown(
    """
<style>
.block-container {padding-top: 1.5rem; max-width: 1300px;}
.hero {background: linear-gradient(135deg,#1F3A5F 0%,#2A9D8F 100%);
       padding: 28px 32px; border-radius: 16px; margin-bottom: 20px;}
.hero h1 {margin: 0; font-size: 2.1rem; color: #ffffff;}
.hero p {margin: 6px 0 0; color: #E6F4F1; font-size: 1rem;}
.kpi {background: #161B26; border: 1px solid #263041; border-radius: 14px;
      padding: 18px 20px;}
.kpi .label {color: #8B95A7; font-size: 0.78rem; text-transform: uppercase;
             letter-spacing: 0.06em;}
.kpi .value {color: #ffffff; font-size: 1.9rem; font-weight: 700; margin-top: 4px;}
.kpi .sub {color: #2A9D8F; font-size: 0.8rem; margin-top: 2px;}
</style>
""",
    unsafe_allow_html=True,
)

REQUIRED = {
    "customers": ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                  "customer_city", "customer_state"],
    "sellers": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    "orders": ["order_id", "customer_id", "order_status", "order_purchase_timestamp"],
    "order_items": ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    "order_payments": ["order_id", "payment_sequential", "payment_type", "payment_value"],
    "order_reviews": ["review_id", "order_id", "review_score"],
    "products": ["product_id", "product_category_name"],
}

TABLES = ["dim_customers", "dim_sellers", "dim_products", "fact_orders",
          "fact_order_items", "fact_payments", "fact_reviews"]


def detect_table(columns):
    cols = set(columns)
    for name, required in REQUIRED.items():
        if set(required) <= cols:
            return name
    return None


@st.cache_resource
def cached_engine():
    return get_engine()


@st.cache_data(ttl=60, show_spinner=False)
def run_query(sql):
    return pd.read_sql(sql, cached_engine())


def style(fig, height=360):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=50, b=10),
        height=height,
        title_font_size=16,
    )
    return fig


def kpi_card(col, label, value, sub):
    col.markdown(
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


KPI_SQL = """
SELECT
  CAST((SELECT SUM(price) FROM warehouse.fact_order_items) AS DOUBLE PRECISION) AS revenue,
  (SELECT COUNT(*) FROM warehouse.fact_orders) AS orders,
  CAST((SELECT 100.0 * AVG(CASE WHEN is_late THEN 0 ELSE 1 END)
        FROM warehouse.fact_orders
        WHERE order_status = 'delivered' AND is_late IS NOT NULL) AS DOUBLE PRECISION) AS on_time,
  CAST((SELECT AVG(review_score) FROM warehouse.fact_reviews) AS DOUBLE PRECISION) AS review
"""


def dashboard_tab():
    k = run_query(KPI_SQL).iloc[0]
    revenue, orders = float(k["revenue"]), int(k["orders"])
    on_time, review = float(k["on_time"]), float(k["review"])

    c1, c2, c3, c4, c5 = st.columns(5)
    kpi_card(c1, "Total revenue", f"R$ {revenue / 1e6:.2f}M", "item price total")
    kpi_card(c2, "Total orders", f"{orders:,}", "unique orders")
    kpi_card(c3, "Avg order value", f"R$ {revenue / orders:.2f}", "per order")
    kpi_card(c4, "On-time delivery", f"{on_time:.2f}%", f"{100 - on_time:.2f}% delivered late")
    kpi_card(c5, "Avg review score", f"{review:.2f}", "out of 5")
    st.write("")

    monthly = run_query(
        "SELECT order_month, orders, CAST(revenue AS DOUBLE PRECISION) AS revenue, "
        "CAST(revenue_mom_pct AS DOUBLE PRECISION) AS revenue_mom_pct "
        "FROM analytics.vw_monthly_kpis WHERE orders > 100 ORDER BY order_month"
    )
    status = run_query(
        "SELECT order_status, COUNT(*) AS orders FROM warehouse.fact_orders "
        "GROUP BY order_status ORDER BY orders DESC"
    )
    cat = run_query(
        "SELECT category, CAST(revenue AS DOUBLE PRECISION) AS revenue "
        "FROM analytics.vw_category_performance ORDER BY revenue DESC LIMIT 10"
    )
    state = run_query(
        "SELECT customer_state, delivered_orders, CAST(late_pct AS DOUBLE PRECISION) AS late_pct "
        "FROM analytics.vw_state_delivery ORDER BY late_pct DESC LIMIT 10"
    )

    left, right = st.columns([2, 1])
    fig = px.area(monthly, x="order_month", y="revenue", title="Monthly revenue trend",
                  color_discrete_sequence=["#2A9D8F"])
    left.plotly_chart(style(fig), use_container_width=True)
    fig = px.pie(status, names="order_status", values="orders", hole=0.55,
                 title="Orders by status",
                 color_discrete_sequence=px.colors.sequential.Teal_r)
    right.plotly_chart(style(fig), use_container_width=True)

    left, right = st.columns(2)
    fig = px.bar(cat.sort_values("revenue"), x="revenue", y="category", orientation="h",
                 title="Top 10 categories by revenue", color="revenue",
                 color_continuous_scale="Teal")
    fig.update_coloraxes(showscale=False)
    left.plotly_chart(style(fig), use_container_width=True)
    fig = px.bar(state.sort_values("late_pct"), x="late_pct", y="customer_state", orientation="h",
                 title="Late delivery % by state (top 10)", color="late_pct",
                 color_continuous_scale="Reds")
    fig.update_coloraxes(showscale=False)
    right.plotly_chart(style(fig), use_container_width=True)

    top = state.iloc[0]
    st.info(
        f"Insight: {top['customer_state']} has the highest late-delivery rate at "
        f"{top['late_pct']:.1f}%, against an overall rate of {100 - on_time:.1f}%."
    )

    with st.expander("Monthly KPI table"):
        st.dataframe(monthly, hide_index=True, use_container_width=True)


def loader_tab():
    st.subheader("Upload an Olist CSV")
    st.caption("Load order: customers, sellers, products, then orders, then items, payments, reviews.")
    file = st.file_uploader("Drop a CSV file here", type="csv")
    if file is None:
        st.info("Waiting for a file...")
        return

    df = pd.read_csv(file, dtype=str)
    table = detect_table(df.columns)

    m1, m2, m3 = st.columns(3)
    m1.metric("Rows", f"{len(df):,}")
    m2.metric("Columns", df.shape[1])
    m3.metric("Duplicate rows", f"{df.duplicated().sum():,}")

    if table is None:
        st.error("This file was not recognised. Please upload an Olist CSV.")
        return
    st.success(f"Detected table: {table}")

    with st.expander("Preview (first 10 rows)", expanded=True):
        st.dataframe(df.head(10), use_container_width=True)

    st.markdown("#### Data quality")
    report = pd.DataFrame({
        "column": df.columns,
        "missing": df.isna().sum().values,
        "missing_pct": (df.isna().mean() * 100).round(2).values,
    })
    st.dataframe(
        report, hide_index=True, use_container_width=True,
        column_config={"missing_pct": st.column_config.ProgressColumn(
            "missing %", min_value=0, max_value=100, format="%.2f")},
    )

    if st.button("Clean and load to warehouse", type="primary"):
        with st.spinner("Cleaning and loading..."):
            stats = load_to_warehouse(table, df, cached_engine())
        st.cache_data.clear()
        st.toast("Load complete")
        st.success(f"Loaded into {stats['target_table']}")
        a, b, c = st.columns(3)
        a.metric("Rows inserted", f"{stats['rows_inserted']:,}")
        b.metric("Skipped (already exist)", f"{stats['skipped_already_exists']:,}")
        c.metric("Skipped (missing parent)", f"{stats['skipped_missing_parent']:,}")


def explorer_tab():
    st.subheader("Warehouse tables")
    counts = run_query(" UNION ALL ".join(
        f"SELECT '{t}' AS table_name, COUNT(*) AS row_count FROM warehouse.{t}" for t in TABLES
    ))
    left, right = st.columns([1, 2])
    left.dataframe(counts, hide_index=True, use_container_width=True)
    fig = px.bar(counts, x="table_name", y="row_count", title="Rows per table",
                 color_discrete_sequence=["#2A9D8F"])
    right.plotly_chart(style(fig, 320), use_container_width=True)

    choice = st.selectbox("Preview a table", TABLES, index=3)
    st.dataframe(run_query(f"SELECT * FROM warehouse.{choice} LIMIT 100"),
                 use_container_width=True)


with st.sidebar:
    st.markdown("### 📊 Ops Analytics Engine")
    try:
        run_query("SELECT 1")
        st.success("PostgreSQL connected")
    except Exception as e:
        st.error("Database connection failed")
        st.caption(str(e))
        st.stop()
    st.markdown("---")
    st.markdown("**Pipeline**")
    st.markdown("1. Raw CSV\n2. Clean (Pandas)\n3. Staging\n4. Warehouse\n5. SQL views\n6. Dashboards")
    st.markdown("---")
    st.caption("PostgreSQL | Pandas | Streamlit | Power BI")

st.markdown(
    '<div class="hero"><h1>Operations Analytics Engine</h1>'
    "<p>Live KPIs from the PostgreSQL warehouse, plus an automated CSV cleaning and loading pipeline.</p></div>",
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["📈 Dashboard", "⬆️ Data Loader", "🗄️ Warehouse Explorer"])
with tab1:
    dashboard_tab()
with tab2:
    loader_tab()
with tab3:
    explorer_tab()