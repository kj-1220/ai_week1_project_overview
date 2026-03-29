"""Page 2: E-Commerce"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, _tbl, style_fig, governance_sidebar, COLORS, REGION_COLORS
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.markdown("## E-Commerce")
st.caption("Orders, revenue, product mix, returns | Clean views")

# ── Query 1: All orders ──
orders = q("""
    SELECT order_date,
           strftime('%Y-%m', order_date) as month,
           CAST(strftime('%Y', order_date) AS INTEGER) as year,
           ((CAST(strftime('%m', order_date) AS INTEGER) - 1) / 3 + 1) as quarter,
           CAST(strftime('%m', order_date) AS INTEGER) as mo,
           total_amount, discount_pct
    FROM v_orders_clean
""")

total_rev = orders.total_amount.sum()
total_orders = len(orders)
aov = total_rev / total_orders
avg_disc = orders.discount_pct.mean() * 100

# ── Query 2: Returns ──
returns_df = q("""
    SELECT return_date, strftime('%Y-%m', return_date) as month, reason
    FROM v_returns_clean
""")
return_rate = len(returns_df) / total_orders * 100

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue", f"${total_rev/1e6:.1f}M")
c2.metric("Orders", f"{total_orders:,}")
c3.metric("Avg Order Value", f"${aov:,.0f}")
c4.metric("Return Rate", f"{return_rate:.1f}%")
c5.metric("Avg Discount", f"{avg_disc:.1f}%")

st.divider()

# ── 1. Revenue and volume trend (dual axis) ──
monthly = orders.groupby("month", as_index=False).agg(
    revenue=("total_amount", "sum"),
    order_count=("total_amount", "count"),
    aov=("total_amount", "mean")
)

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Bar(x=monthly.month, y=monthly.order_count, name="Orders",
                     marker_color=COLORS["light_gray"], opacity=0.6),
              secondary_y=False)
fig.add_trace(go.Scatter(x=monthly.month, y=monthly.revenue, name="Revenue",
                         mode="lines", line=dict(color=COLORS["blue"], width=2.5)),
              secondary_y=True)
style_fig(fig, height=400, title_text="Monthly Revenue and Order Volume")
fig.update_yaxes(title_text="Orders", secondary_y=False)
fig.update_yaxes(title_text="Revenue ($)", secondary_y=True)
fig.update_xaxes(dtick=3)
fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
st.plotly_chart(fig, use_container_width=True)

# ── 2. Quarterly revenue heatmap ──
col1, col2 = st.columns([1.2, 1])

with col1:
    orders["year_str"] = orders.year.astype(str)
    orders["qtr_str"] = "Q" + orders.quarter.astype(str)
    qtr = orders.groupby(["year_str", "qtr_str"], as_index=False).agg(revenue=("total_amount", "sum"))
    pivot = qtr.pivot(index="year_str", columns="qtr_str", values="revenue")
    fig = px.imshow(pivot / 1e6, text_auto=".0f", color_continuous_scale="Blues",
                    labels={"color": "Revenue ($M)"})
    style_fig(fig, height=280, title_text="Quarterly Revenue ($M)")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    mo_counts = orders.groupby("mo").size().reset_index(name="order_count").sort_values("mo")
    avg = mo_counts.order_count.mean()
    mo_counts["mult"] = (mo_counts.order_count / avg).round(2)
    month_names = {1:"J",2:"F",3:"M",4:"A",5:"M",6:"J",7:"J",8:"A",9:"S",10:"O",11:"N",12:"D"}
    mo_counts["label"] = mo_counts.mo.map(month_names)

    fig = px.bar(mo_counts, x="label", y="mult", color_discrete_sequence=[COLORS["blue"]],
                 text="mult")
    fig.add_hline(y=1.0, line_dash="dot", line_color=COLORS["gray"])
    style_fig(fig, height=280, title_text="Monthly Seasonality Index")
    fig.update_traces(textposition="outside", textfont_size=10)
    fig.update_yaxes(title_text="Multiplier")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Query 3: Product-level data ──
items = q("""
    SELECT oi.line_total, oi.order_id, oi.product_id,
           strftime('%Y-%m', o.order_date) as month,
           CAST(strftime('%Y', o.order_date) AS INTEGER) as year,
           CAST(strftime('%m', o.order_date) AS INTEGER) as mo,
           p.category, p.subcategory
    FROM v_order_items_clean oi
    JOIN v_orders_clean o ON oi.order_id = o.order_id
    JOIN products p ON oi.product_id = p.product_id
""")

# ── 4. Q2 tariff impact by category ──
col1, col2 = st.columns(2)

with col1:
    q2 = items[items.mo.between(4, 6)]
    tariff = q2.groupby(["year", "category"], as_index=False).agg(revenue=("line_total", "sum"))
    tariff["year"] = tariff["year"].astype(str)
    fig = px.bar(tariff, x="category", y="revenue", color="year", barmode="group",
                 color_discrete_sequence=[COLORS["light_gray"], COLORS["blue"], COLORS["red"]])
    style_fig(fig, height=380, title_text="Q2 Revenue by Category — Year over Year")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    cat = items.groupby(["month", "category"], as_index=False).agg(revenue=("line_total", "sum"))
    fig = px.line(cat, x="month", y="revenue", color="category",
                  color_discrete_sequence=[COLORS["blue"], COLORS["green"],
                                           COLORS["purple"], COLORS["orange"], COLORS["red"]])
    style_fig(fig, height=380, title_text="Monthly Revenue by Category")
    fig.update_xaxes(dtick=3)
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

# ── 6. Product treemap ──
products = items.groupby(["category", "subcategory"], as_index=False).agg(
    revenue=("line_total", "sum"),
    orders=("order_id", "nunique")
)
fig = px.treemap(products, path=["category", "subcategory"], values="revenue",
                 color="orders", color_continuous_scale="Blues")
style_fig(fig, height=420, title_text="Revenue by Category and Subcategory")
st.plotly_chart(fig, use_container_width=True)

# ── 7 & 8. Returns ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    ret_mo = returns_df.groupby("month").size().reset_index(name="returns")
    ord_mo = orders.groupby("month").size().reset_index(name="order_count")
    merged = ret_mo.merge(ord_mo, on="month")
    merged["rate"] = (merged.returns / merged.order_count * 100).round(2)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=merged.month, y=merged.returns, name="Returns",
                         marker_color=COLORS["orange"], opacity=0.7), secondary_y=False)
    fig.add_trace(go.Scatter(x=merged.month, y=merged.rate, name="Rate %",
                             mode="lines", line=dict(color=COLORS["red"], width=2)),
                  secondary_y=True)
    style_fig(fig, height=350, title_text="Monthly Returns and Return Rate")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    reasons = returns_df.groupby("reason").size().reset_index(name="n").sort_values("n", ascending=False)
    fig = px.bar(reasons, x="n", y="reason", orientation="h",
                 color_discrete_sequence=[COLORS["orange"]])
    style_fig(fig, height=350, title_text="Return Reasons")
    fig.update_traces(texttemplate="%{x:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("orders", "v_orders_clean", ["customers", "orders", "order_items"])
