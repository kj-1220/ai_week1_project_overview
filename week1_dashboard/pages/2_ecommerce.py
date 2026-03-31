"""Page 2: E-Commerce"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, governance_sidebar, BLUE, GREEN, RED, ORANGE, PURPLE, GRAY, LIGHT_GRAY
import altair as alt

st.markdown("## E-Commerce")
st.caption("Orders, revenue, product mix, returns | Clean views")

# ── KPIs ──
kpis = q("""
    SELECT
        (SELECT SUM(total_amount) FROM v_orders_clean) as total_rev,
        (SELECT COUNT(*) FROM v_orders_clean) as total_orders,
        (SELECT AVG(discount_pct)*100 FROM v_orders_clean) as avg_disc,
        (SELECT COUNT(*) FROM v_returns_clean) as returns
""")
total_rev = kpis.total_rev[0]
total_orders = kpis.total_orders[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue", f"${total_rev/1e6:.1f}M")
c2.metric("Orders", f"{total_orders:,}")
c3.metric("Avg Order Value", f"${total_rev/total_orders:,.0f}")
c4.metric("Return Rate", f"{kpis.returns[0]/total_orders*100:.1f}%")
c5.metric("Avg Discount", f"{kpis.avg_disc[0]:.1f}%")

st.divider()

# ── 1. Revenue and order volume ──
monthly = q("""
    SELECT strftime('%Y-%m', order_date) as month,
           SUM(total_amount) as revenue, COUNT(*) as orders
    FROM v_orders_clean GROUP BY month ORDER BY month
""")

base = alt.Chart(monthly).encode(x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=monthly.month.tolist()[::3])))
bars = base.mark_bar(color=LIGHT_GRAY, opacity=0.6).encode(y=alt.Y("orders:Q", title="Orders"))
line = base.mark_line(color=BLUE, strokeWidth=2.5).encode(y=alt.Y("revenue:Q", title="Revenue ($)"))
chart = alt.layer(bars, line).resolve_scale(y="independent").properties(title="Monthly Revenue and Order Volume", height=380)
st.altair_chart(chart, use_container_width=True)

# ── 2. Quarterly heatmap & 3. Seasonality ──
col1, col2 = st.columns([1.2, 1])

with col1:
    qtr = q("""
        SELECT CAST(strftime('%Y', order_date) AS TEXT) as year,
               'Q' || ((CAST(strftime('%m', order_date) AS INTEGER) - 1) / 3 + 1) as quarter,
               ROUND(SUM(total_amount) / 1000000.0, 0) as rev_m
        FROM v_orders_clean GROUP BY year, quarter ORDER BY year, quarter
    """)
    chart = alt.Chart(qtr).mark_rect().encode(
        x=alt.X("quarter:O", title=None),
        y=alt.Y("year:O", title=None),
        color=alt.Color("rev_m:Q", scale=alt.Scale(scheme="blues"), title="Revenue ($M)")
    ).properties(title="Quarterly Revenue ($M)", height=260)
    text = alt.Chart(qtr).mark_text(fontSize=12).encode(
        x="quarter:O", y="year:O", text=alt.Text("rev_m:Q", format=".0f"),
        color=alt.condition(alt.datum.rev_m > qtr.rev_m.median(), alt.value("white"), alt.value("black"))
    )
    st.altair_chart(chart + text, use_container_width=True)

with col2:
    mo = q("""
        SELECT CAST(strftime('%m', order_date) AS INTEGER) as mo, COUNT(*) as orders
        FROM v_orders_clean GROUP BY mo ORDER BY mo
    """)
    avg = mo.orders.mean()
    mo["mult"] = (mo.orders / avg).round(2)
    names = {1:"J",2:"F",3:"M",4:"A",5:"M",6:"J",7:"J",8:"A",9:"S",10:"O",11:"N",12:"D"}
    mo["label"] = mo.mo.map(names)

    chart = alt.Chart(mo).mark_bar(color=BLUE).encode(
        x=alt.X("label:N", title=None, sort=list(names.values())),
        y=alt.Y("mult:Q", title="Multiplier")
    ).properties(title="Monthly Seasonality Index", height=260)
    rule = alt.Chart(mo).mark_rule(color=GRAY, strokeDash=[4, 4]).encode(y=alt.datum(1.0))
    text = alt.Chart(mo).mark_text(dy=-10, fontSize=10).encode(
        x=alt.X("label:N", sort=list(names.values())), y="mult:Q", text=alt.Text("mult:Q", format=".2f")
    )
    st.altair_chart(chart + rule + text, use_container_width=True)

st.divider()

# ── 4. Q2 tariff impact & 5. Revenue by category ──
col1, col2 = st.columns(2)

with col1:
    tariff = q("""
        SELECT CAST(strftime('%Y', o.order_date) AS TEXT) as year, p.category,
               SUM(oi.line_total) as revenue
        FROM v_order_items_clean oi
        JOIN v_orders_clean o ON oi.order_id = o.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE CAST(strftime('%m', o.order_date) AS INTEGER) BETWEEN 4 AND 6
        GROUP BY year, category ORDER BY year, category
    """)
    chart = alt.Chart(tariff).mark_bar().encode(
        x=alt.X("category:N", title=None),
        y=alt.Y("revenue:Q", title="Revenue ($)"),
        color=alt.Color("year:N", scale=alt.Scale(range=[LIGHT_GRAY, BLUE, RED])),
        xOffset="year:N"
    ).properties(title="Q2 Revenue by Category — YoY", height=360)
    st.altair_chart(chart, use_container_width=True)

with col2:
    cat = q("""
        SELECT strftime('%Y-%m', o.order_date) as month, p.category,
               SUM(oi.line_total) as revenue
        FROM v_order_items_clean oi
        JOIN v_orders_clean o ON oi.order_id = o.order_id
        JOIN products p ON oi.product_id = p.product_id
        GROUP BY month, category ORDER BY month
    """)
    chart = alt.Chart(cat).mark_line(strokeWidth=2).encode(
        x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=cat.month.unique().tolist()[::3])),
        y=alt.Y("revenue:Q", title="Revenue ($)"),
        color=alt.Color("category:N")
    ).properties(title="Monthly Revenue by Category", height=360)
    st.altair_chart(chart, use_container_width=True)

# ── 6. Product treemap (use bar chart — Altair doesn't have treemap) ──
products = q("""
    SELECT p.category, p.subcategory,
           SUM(oi.line_total) as revenue
    FROM v_order_items_clean oi
    JOIN products p ON oi.product_id = p.product_id
    GROUP BY p.category, p.subcategory ORDER BY revenue DESC
    LIMIT 20
""")
chart = alt.Chart(products).mark_bar().encode(
    x=alt.X("revenue:Q", title="Revenue ($)"),
    y=alt.Y("subcategory:N", title=None, sort="-x"),
    color=alt.Color("category:N")
).properties(title="Top 20 Subcategories by Revenue", height=420)
st.altair_chart(chart, use_container_width=True)

# ── 7 & 8. Returns ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    merged = q("""
        SELECT r.month, r.returns, o.orders,
               ROUND(CAST(r.returns AS REAL) / o.orders * 100, 2) as rate
        FROM (SELECT strftime('%Y-%m', return_date) as month, COUNT(*) as returns
              FROM v_returns_clean GROUP BY month) r
        JOIN (SELECT strftime('%Y-%m', order_date) as month, COUNT(*) as orders
              FROM v_orders_clean GROUP BY month) o ON r.month = o.month
        ORDER BY r.month
    """)
    base = alt.Chart(merged).encode(x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=merged.month.tolist()[::3])))
    bars = base.mark_bar(color=ORANGE, opacity=0.7).encode(y=alt.Y("returns:Q", title="Returns"))
    line = base.mark_line(color=RED, strokeWidth=2).encode(y=alt.Y("rate:Q", title="Rate %"))
    chart = alt.layer(bars, line).resolve_scale(y="independent").properties(title="Monthly Returns and Return Rate", height=330)
    st.altair_chart(chart, use_container_width=True)

with col2:
    reasons = q("SELECT reason, COUNT(*) as n FROM v_returns_clean GROUP BY reason ORDER BY n DESC")
    chart = alt.Chart(reasons).mark_bar(color=ORANGE).encode(
        x=alt.X("n:Q", title="Count"),
        y=alt.Y("reason:N", title=None, sort="-x")
    ).properties(title="Return Reasons", height=330)
    st.altair_chart(chart, use_container_width=True)

governance_sidebar("orders", "v_orders_clean", ["customers", "orders", "order_items"])
