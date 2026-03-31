"""
Otacon Inc. — Analytics Dashboard
Page 1: Executive Summary
"""
import streamlit as st

st.set_page_config(page_title="Otacon Inc.", page_icon="O", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #6b7280; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import q, BLUE, GREEN, RED, ORANGE, PURPLE, GRAY, DARK
import altair as alt

# ── Sidebar ──
st.sidebar.markdown("### Otacon Inc.")
st.sidebar.caption("Analytics Dashboard")
st.sidebar.divider()

# ── KPIs ──
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

# ── Revenue trend ──
col_chart, col_yoy = st.columns([2.5, 1])

monthly_rev = q("""
    SELECT strftime('%Y-%m', order_date) as month,
           SUM(total_amount) as revenue, COUNT(*) as orders
    FROM v_orders_clean GROUP BY month ORDER BY month
""")

with col_chart:
    chart = alt.Chart(monthly_rev).mark_area(
        line={"color": BLUE, "strokeWidth": 2},
        color=alt.Gradient(gradient="linear", stops=[
            alt.GradientStop(color=BLUE, offset=1),
            alt.GradientStop(color="rgba(37,99,235,0.05)", offset=0)
        ], x1=1, x2=1, y1=1, y2=0)
    ).encode(
        x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=monthly_rev.month.tolist()[::3])),
        y=alt.Y("revenue:Q", title="Revenue ($)")
    ).properties(title="Monthly Revenue", height=340)
    st.altair_chart(chart, use_container_width=True)

with col_yoy:
    yoy = q("""
        SELECT CAST(strftime('%Y', order_date) AS INTEGER) as year,
               SUM(total_amount) as revenue
        FROM v_orders_clean GROUP BY year ORDER BY year
    """)
    yoy["growth"] = yoy.revenue.pct_change() * 100

    st.markdown("**Annual Revenue**")
    for _, r in yoy.iterrows():
        growth = f" ({r.growth:+.1f}%)" if r.growth == r.growth else ""
        st.text(f"  {int(r.year)}:  ${r.revenue/1e6:.1f}M{growth}")

    st.markdown("")
    st.markdown("**By Region**")
    region_rev = q("SELECT region, SUM(total_amount) as rev FROM v_orders_clean GROUP BY region ORDER BY rev DESC")
    total = region_rev.rev.sum()
    for _, r in region_rev.iterrows():
        st.text(f"  {r.region}: {r.rev / total * 100:.0f}%")

# ── Customer distributions ──
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    seg = q("SELECT segment, COUNT(*) as n FROM v_customers_clean GROUP BY segment ORDER BY n DESC")
    chart = alt.Chart(seg).mark_bar().encode(
        x=alt.X("segment:N", title=None, sort="-y"),
        y=alt.Y("n:Q", title="Count"),
        color=alt.Color("segment:N", scale=alt.Scale(domain=["enterprise","mid_market","smb"],
                         range=["#7c3aed","#2563eb","#16a34a"]), legend=None)
    ).properties(title="Customers by Segment", height=280)
    st.altair_chart(chart, use_container_width=True)

with col2:
    ind = q("SELECT industry, COUNT(*) as n FROM v_customers_clean GROUP BY industry ORDER BY n DESC")
    chart = alt.Chart(ind).mark_bar().encode(
        y=alt.Y("industry:N", title=None, sort="-x"),
        x=alt.X("n:Q", title="Count"),
        color=alt.value(BLUE)
    ).properties(title="Customers by Industry", height=280)
    st.altair_chart(chart, use_container_width=True)

with col3:
    status = q("SELECT status, COUNT(*) as n FROM v_customers_clean GROUP BY status ORDER BY n DESC")
    chart = alt.Chart(status).mark_arc(innerRadius=50).encode(
        theta=alt.Theta("n:Q"),
        color=alt.Color("status:N", scale=alt.Scale(domain=["active","churned","suspended"],
                         range=[GREEN, RED, ORANGE]), legend=alt.Legend(orient="bottom"))
    ).properties(title="Customer Status", height=280)
    st.altair_chart(chart, use_container_width=True)

# ── Customer 360 ──
st.divider()
st.markdown("#### Customer 360")
tab1, tab2 = st.tabs(["Top 10 by Lifetime Value", "Bottom 10 by Health Score"])

with tab1:
    top = q("""
        SELECT company_name, region, segment, total_orders,
               ROUND(total_revenue, 0) as revenue, saas_plan, account_health,
               ROUND(lifetime_value, 0) as ltv
        FROM customer_360 WHERE lifetime_value > 0
        ORDER BY lifetime_value DESC LIMIT 10
    """)
    st.dataframe(top, use_container_width=True, hide_index=True)

with tab2:
    bottom = q("""
        SELECT company_name, region, segment, account_health,
               saas_plan, ROUND(late_payment_pct * 100, 1) as late_pct,
               total_returns, return_rate
        FROM customer_360 WHERE account_health IS NOT NULL
        ORDER BY account_health ASC LIMIT 10
    """)
    st.dataframe(bottom, use_container_width=True, hide_index=True)

# ── Sidebar: data quality ──
with st.sidebar.expander("Data Quality"):
    flags = q("""
        SELECT rule_id, flag_type, COUNT(*) as n
        FROM data_quality_flags GROUP BY rule_id, flag_type ORDER BY rule_id
    """)
    st.dataframe(flags, use_container_width=True, hide_index=True)
    st.caption(f"{flags.n.sum():,} total flags across {len(flags)} rules")
