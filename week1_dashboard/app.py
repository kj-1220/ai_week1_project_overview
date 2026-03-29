"""
Otacon Inc. — Analytics Dashboard
Page 1: Executive Summary
"""

import streamlit as st

st.set_page_config(
    page_title="Otacon Inc.",
    page_icon="O",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #6b7280; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import q, _tbl, style_fig, COLORS, REGION_COLORS

import plotly.express as px
import plotly.graph_objects as go

# ── Sidebar ──
st.sidebar.markdown("### Otacon Inc.")
st.sidebar.caption("Analytics Dashboard")
st.sidebar.divider()

# ── All KPIs in one query ──
st.markdown("## Executive Summary")
st.caption("Otacon Inc. | 2023 – 2025 | Clean governed views")

kpis = q("""
    SELECT
        (SELECT SUM(total_amount) FROM v_orders_clean) as total_rev,
        (SELECT COUNT(*) FROM v_customers_clean) as total_cust,
        (SELECT COUNT(*) FROM v_orders_clean) as total_orders,
        (SELECT COUNT(*) FROM v_saas_customers_clean WHERE status='active') as active_saas,
        (SELECT SUM(mrr) FROM v_saas_customers_clean WHERE status='active') as total_mrr,
        (SELECT SUM(amount) FROM v_opportunities_clean WHERE stage NOT IN ('closed_won','closed_lost')) as pipeline
""")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Revenue", f"${kpis.total_rev[0]/1e6:.1f}M")
c2.metric("Customers", f"{kpis.total_cust[0]:,}")
c3.metric("Orders", f"{kpis.total_orders[0]:,}")
c4.metric("Active SaaS", f"{kpis.active_saas[0]:,}")
c5.metric("Monthly MRR", f"${kpis.total_mrr[0]/1e3:.0f}K")
c6.metric("Open Pipeline", f"${kpis.pipeline[0]/1e6:.1f}M")

st.divider()

# ── Revenue trend + YoY + region in one query ──
col_chart, col_yoy = st.columns([2.5, 1])

rev = q("""
    SELECT strftime('%Y-%m', order_date) as month,
           CAST(strftime('%Y', order_date) AS INTEGER) as year,
           region,
           SUM(total_amount) as revenue,
           COUNT(*) as orders
    FROM v_orders_clean GROUP BY month, year, region ORDER BY month
""")

with col_chart:
    monthly = rev.groupby("month", as_index=False).agg({"revenue": "sum", "orders": "sum"})
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly.month, y=monthly.revenue, mode="lines",
                             line=dict(color=COLORS["blue"], width=2),
                             fill="tozeroy", fillcolor="rgba(37,99,235,0.06)"))
    style_fig(fig, height=360, title_text="Monthly Revenue")
    fig.update_xaxes(dtick=3)
    st.plotly_chart(fig, use_container_width=True)

with col_yoy:
    yoy = rev.groupby("year", as_index=False).agg({"revenue": "sum"})
    yoy["growth"] = yoy.revenue.pct_change() * 100

    st.markdown("**Annual Revenue**")
    for _, r in yoy.iterrows():
        yr = int(r.year)
        growth = f" ({r.growth:+.1f}%)" if r.growth == r.growth else ""
        st.text(f"  {yr}:  ${r.revenue/1e6:.1f}M{growth}")

    st.markdown("")
    st.markdown("**By Region**")
    region_rev = rev.groupby("region", as_index=False).agg({"revenue": "sum"}).sort_values("revenue", ascending=False)
    total = region_rev.revenue.sum()
    for _, r in region_rev.iterrows():
        pct = r.revenue / total * 100
        st.text(f"  {r.region}: {pct:.0f}%")

# ── Customer distributions in one query ──
st.divider()
col1, col2, col3 = st.columns(3)

cust = q("SELECT segment, industry, status FROM v_customers_clean")

with col1:
    seg = cust.groupby("segment").size().reset_index(name="n").sort_values("n", ascending=False)
    fig = px.bar(seg, x="segment", y="n", color="segment",
                 color_discrete_map={"enterprise":"#7c3aed","mid_market":"#2563eb","smb":"#16a34a"})
    style_fig(fig, height=300, title_text="Customers by Segment", showlegend=False)
    fig.update_traces(texttemplate="%{y:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    ind = cust.groupby("industry").size().reset_index(name="n").sort_values("n", ascending=False)
    fig = px.bar(ind, x="n", y="industry", orientation="h", color_discrete_sequence=[COLORS["blue"]])
    style_fig(fig, height=300, title_text="Customers by Industry")
    fig.update_traces(texttemplate="%{x:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

with col3:
    status = cust.groupby("status").size().reset_index(name="n").sort_values("n", ascending=False)
    fig = px.pie(status, names="status", values="n", hole=0.5,
                 color="status", color_discrete_map={"active":"#16a34a","churned":"#dc2626","suspended":"#ea580c"})
    style_fig(fig, height=300, title_text="Customer Status")
    fig.update_traces(textinfo="percent+label", textfont_size=11)
    st.plotly_chart(fig, use_container_width=True)

# ── Customer 360 ──
st.divider()
st.markdown("#### Customer 360")
tab1, tab2 = st.tabs(["Top 10 by Lifetime Value", "Bottom 10 by Health Score"])

c360 = q("""
    SELECT company_name, region, segment, total_orders,
           ROUND(total_revenue, 0) as revenue,
           saas_plan, account_health,
           ROUND(lifetime_value, 0) as ltv,
           ROUND(late_payment_pct * 100, 1) as late_pct,
           total_returns, return_rate
    FROM customer_360
""")

with tab1:
    top = c360[c360.ltv > 0].nlargest(10, "ltv")[
        ["company_name", "region", "segment", "total_orders", "revenue", "saas_plan", "account_health", "ltv"]
    ]
    st.dataframe(top, use_container_width=True, hide_index=True)

with tab2:
    bottom = c360[c360.account_health.notna()].nsmallest(10, "account_health")[
        ["company_name", "region", "segment", "account_health", "saas_plan", "late_pct", "total_returns", "return_rate"]
    ]
    st.dataframe(bottom, use_container_width=True, hide_index=True)

# ── Sidebar: data quality ──
with st.sidebar.expander("Data Quality"):
    flags = q("""
        SELECT rule_id, flag_type, COUNT(*) as n
        FROM data_quality_flags GROUP BY rule_id, flag_type ORDER BY rule_id
    """)
    st.dataframe(flags, use_container_width=True, hide_index=True)
    st.caption(f"{flags.n.sum():,} total flags across {len(flags)} rules")
