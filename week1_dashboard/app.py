"""
Otacon Inc. — Analytics Dashboard (BigQuery)
Page 1: Executive Summary
"""

import streamlit as st

st.set_page_config(
    page_title="Otacon Inc.",
    page_icon="O",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal global styling
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

# ── KPIs ──
st.markdown("## Executive Summary")
st.caption("Otacon Inc. | 2023 – 2025 | Clean governed views")

total_rev = q(f"SELECT SUM(total_amount) as v FROM {_tbl('v_orders_clean')}").v[0]
total_cust = q(f"SELECT COUNT(*) as v FROM {_tbl('v_customers_clean')}").v[0]
total_orders = q(f"SELECT COUNT(*) as v FROM {_tbl('v_orders_clean')}").v[0]
active_saas = q(f"SELECT COUNT(*) as v FROM {_tbl('v_saas_customers_clean')} WHERE status='active'").v[0]
total_mrr = q(f"SELECT SUM(mrr) as v FROM {_tbl('v_saas_customers_clean')} WHERE status='active'").v[0]
pipeline = q(f"SELECT SUM(amount) as v FROM {_tbl('v_opportunities_clean')} WHERE stage NOT IN ('closed_won','closed_lost')").v[0]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Revenue", f"${total_rev/1e6:.1f}M")
c2.metric("Customers", f"{total_cust:,}")
c3.metric("Orders", f"{total_orders:,}")
c4.metric("Active SaaS", f"{active_saas:,}")
c5.metric("Monthly MRR", f"${total_mrr/1e3:.0f}K")
c6.metric("Open Pipeline", f"${pipeline/1e6:.1f}M")

st.divider()

# ── Revenue trend ──
col_chart, col_yoy = st.columns([2.5, 1])

with col_chart:
    rev = q(f"""
        SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(order_date AS DATE)) as month,
               SUM(total_amount) as revenue,
               COUNT(*) as orders
        FROM {_tbl('v_orders_clean')} GROUP BY month ORDER BY month
    """)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rev.month, y=rev.revenue, mode="lines",
                             line=dict(color=COLORS["blue"], width=2),
                             fill="tozeroy", fillcolor="rgba(37,99,235,0.06)"))
    style_fig(fig, height=360, title_text="Monthly Revenue")
    fig.update_xaxes(dtick=3)
    st.plotly_chart(fig, use_container_width=True)

with col_yoy:
    yoy = q(f"""
        SELECT EXTRACT(YEAR FROM SAFE_CAST(order_date AS DATE)) as year,
               SUM(total_amount) as revenue
        FROM {_tbl('v_orders_clean')} GROUP BY year ORDER BY year
    """)
    yoy["growth"] = yoy.revenue.pct_change() * 100

    st.markdown("**Annual Revenue**")
    for _, r in yoy.iterrows():
        yr = int(r.year) if isinstance(r.year, (int, float)) else r.year
        growth = f" ({r.growth:+.1f}%)" if r.growth == r.growth else ""
        st.text(f"  {yr}:  ${r.revenue/1e6:.1f}M{growth}")

    # Revenue by region
    st.markdown("")
    st.markdown("**By Region**")
    region_rev = q(f"""
        SELECT region, SUM(total_amount) as rev
        FROM {_tbl('v_orders_clean')} GROUP BY region ORDER BY rev DESC
    """)
    total = region_rev.rev.sum()
    for _, r in region_rev.iterrows():
        pct = r.rev / total * 100
        st.text(f"  {r.region}: {pct:.0f}%")

# ── Customer & segment distribution ──
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    seg = q(f"SELECT segment, COUNT(*) as n FROM {_tbl('v_customers_clean')} GROUP BY segment ORDER BY n DESC")
    fig = px.bar(seg, x="segment", y="n", color="segment",
                 color_discrete_map={"enterprise":"#7c3aed","mid_market":"#2563eb","smb":"#16a34a"})
    style_fig(fig, height=300, title_text="Customers by Segment", showlegend=False)
    fig.update_traces(texttemplate="%{y:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    ind = q(f"SELECT industry, COUNT(*) as n FROM {_tbl('v_customers_clean')} GROUP BY industry ORDER BY n DESC")
    fig = px.bar(ind, x="n", y="industry", orientation="h", color_discrete_sequence=[COLORS["blue"]])
    style_fig(fig, height=300, title_text="Customers by Industry")
    fig.update_traces(texttemplate="%{x:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

with col3:
    status = q(f"SELECT status, COUNT(*) as n FROM {_tbl('v_customers_clean')} GROUP BY status ORDER BY n DESC")
    fig = px.pie(status, names="status", values="n", hole=0.5,
                 color="status", color_discrete_map={"active":"#16a34a","churned":"#dc2626","suspended":"#ea580c"})
    style_fig(fig, height=300, title_text="Customer Status")
    fig.update_traces(textinfo="percent+label", textfont_size=11)
    st.plotly_chart(fig, use_container_width=True)

# ── Customer 360: best and worst ──
st.divider()
st.markdown("#### Customer 360")
tab1, tab2 = st.tabs(["Top 10 by Lifetime Value", "Bottom 10 by Health Score"])

with tab1:
    top = q(f"""
        SELECT company_name, region, segment, total_orders,
               ROUND(total_revenue, 0) as revenue,
               saas_plan, account_health,
               ROUND(lifetime_value, 0) as ltv
        FROM {_tbl('customer_360')} WHERE lifetime_value > 0
        ORDER BY lifetime_value DESC LIMIT 10
    """)
    st.dataframe(top, use_container_width=True, hide_index=True)

with tab2:
    bottom = q(f"""
        SELECT company_name, region, segment, account_health,
               saas_plan, ROUND(late_payment_pct * 100, 1) as late_pct,
               total_returns, return_rate
        FROM {_tbl('customer_360')} WHERE account_health IS NOT NULL
        ORDER BY account_health ASC LIMIT 10
    """)
    st.dataframe(bottom, use_container_width=True, hide_index=True)

# ── Sidebar: data quality ──
with st.sidebar.expander("Data Quality"):
    flags = q(f"""
        SELECT rule_id, flag_type, COUNT(*) as n
        FROM {_tbl('data_quality_flags')} GROUP BY rule_id, flag_type ORDER BY rule_id
    """)
    st.dataframe(flags, use_container_width=True, hide_index=True)
    st.caption(f"{flags.n.sum():,} total flags across {len(flags)} rules")
