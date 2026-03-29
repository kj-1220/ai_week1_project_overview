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

# ── KPIs ──
total_rev = q(f"SELECT SUM(total_amount) as v FROM {_tbl('v_orders_clean')}").v[0]
total_orders = q(f"SELECT COUNT(*) as v FROM {_tbl('v_orders_clean')}").v[0]
aov = total_rev / total_orders
returns = q(f"SELECT COUNT(*) as v FROM {_tbl('v_returns_clean')}").v[0]
return_rate = returns / total_orders * 100
avg_disc = q(f"SELECT AVG(discount_pct)*100 as v FROM {_tbl('v_orders_clean')}").v[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue", f"${total_rev/1e6:.1f}M")
c2.metric("Orders", f"{total_orders:,}")
c3.metric("Avg Order Value", f"${aov:,.0f}")
c4.metric("Return Rate", f"{return_rate:.1f}%")
c5.metric("Avg Discount", f"{avg_disc:.1f}%")

st.divider()

# ── 1. Revenue and volume trend (dual axis) ──
rev = q(f"""
    SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(order_date AS DATE)) as month,
           SUM(total_amount) as revenue, COUNT(*) as orders,
           AVG(total_amount) as aov
    FROM {_tbl('v_orders_clean')} GROUP BY month ORDER BY month
""")

fig = make_subplots(specs=[[{{"secondary_y": True}}]])
fig.add_trace(go.Bar(x=rev.month, y=rev.orders, name="Orders",
                     marker_color=COLORS["light_gray"], opacity=0.6),
              secondary_y=False)
fig.add_trace(go.Scatter(x=rev.month, y=rev.revenue, name="Revenue",
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
    qtr = q(f"""
        SELECT CAST(EXTRACT(YEAR FROM SAFE_CAST(order_date AS DATE)) AS STRING) as year,
               'Q' || CAST(EXTRACT(QUARTER FROM SAFE_CAST(order_date AS DATE)) AS STRING) as quarter,
               SUM(total_amount) as revenue
        FROM {_tbl('v_orders_clean')} GROUP BY year, quarter ORDER BY year, quarter
    """)
    pivot = qtr.pivot(index="year", columns="quarter", values="revenue")
    fig = px.imshow(pivot / 1e6, text_auto=".0f", color_continuous_scale="Blues",
                    labels={{"color": "Revenue ($M)"}})
    style_fig(fig, height=280, title_text="Quarterly Revenue ($M)")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # ── 3. Seasonality multipliers ──
    monthly = q(f"""
        SELECT EXTRACT(MONTH FROM SAFE_CAST(order_date AS DATE)) as mo, COUNT(*) as orders
        FROM {_tbl('v_orders_clean')} GROUP BY mo ORDER BY mo
    """)
    avg = monthly.orders.mean()
    monthly["mult"] = (monthly.orders / avg).round(2)
    month_names = {{1:"J",2:"F",3:"M",4:"A",5:"M",6:"J",7:"J",8:"A",9:"S",10:"O",11:"N",12:"D"}}
    monthly["label"] = monthly.mo.map(month_names)

    fig = px.bar(monthly, x="label", y="mult", color_discrete_sequence=[COLORS["blue"]],
                 text="mult")
    fig.add_hline(y=1.0, line_dash="dot", line_color=COLORS["gray"])
    style_fig(fig, height=280, title_text="Monthly Seasonality Index")
    fig.update_traces(textposition="outside", textfont_size=10)
    fig.update_yaxes(title_text="Multiplier")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 4. Q2 tariff impact by category ──
col1, col2 = st.columns(2)

with col1:
    tariff = q(f"""
        SELECT CAST(EXTRACT(YEAR FROM SAFE_CAST(o.order_date AS DATE)) AS STRING) as year, p.category,
               SUM(oi.line_total) as revenue
        FROM {_tbl('v_order_items_clean')} oi
        JOIN {_tbl('v_orders_clean')} o ON oi.order_id = o.order_id
        JOIN {_tbl('products')} p ON oi.product_id = p.product_id
        WHERE EXTRACT(MONTH FROM SAFE_CAST(o.order_date AS DATE)) BETWEEN 4 AND 6
        GROUP BY year, category ORDER BY year, category
    """)
    fig = px.bar(tariff, x="category", y="revenue", color="year", barmode="group",
                 color_discrete_sequence=[COLORS["light_gray"], COLORS["blue"], COLORS["red"]])
    style_fig(fig, height=380, title_text="Q2 Revenue by Category — Year over Year")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # ── 5. Revenue by category over time ──
    cat = q(f"""
        SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(o.order_date AS DATE)) as month, p.category,
               SUM(oi.line_total) as revenue
        FROM {_tbl('v_order_items_clean')} oi
        JOIN {_tbl('v_orders_clean')} o ON oi.order_id = o.order_id
        JOIN {_tbl('products')} p ON oi.product_id = p.product_id
        GROUP BY month, category ORDER BY month
    """)
    fig = px.line(cat, x="month", y="revenue", color="category",
                  color_discrete_sequence=[COLORS["blue"], COLORS["green"],
                                            COLORS["purple"], COLORS["orange"], COLORS["red"]])
    style_fig(fig, height=380, title_text="Monthly Revenue by Category")
    fig.update_xaxes(dtick=3)
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

# ── 6. Product treemap ──
products = q(f"""
    SELECT p.category, p.subcategory,
           SUM(oi.line_total) as revenue, COUNT(DISTINCT oi.order_id) as orders
    FROM {_tbl('v_order_items_clean')} oi
    JOIN {_tbl('products')} p ON oi.product_id = p.product_id
    GROUP BY p.category, p.subcategory ORDER BY revenue DESC
""")
fig = px.treemap(products, path=["category", "subcategory"], values="revenue",
                 color="orders", color_continuous_scale="Blues")
style_fig(fig, height=420, title_text="Revenue by Category and Subcategory")
st.plotly_chart(fig, use_container_width=True)

# ── 7 & 8. Returns ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    ret = q(f"""
        SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(return_date AS DATE)) as month, COUNT(*) as returns
        FROM {_tbl('v_returns_clean')} GROUP BY month ORDER BY month
    """)
    ord_mo = q(f"SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(order_date AS DATE)) as month, COUNT(*) as orders FROM {_tbl('v_orders_clean')} GROUP BY month")
    merged = ret.merge(ord_mo, on="month")
    merged["rate"] = (merged.returns / merged.orders * 100).round(2)

    fig = make_subplots(specs=[[{{"secondary_y": True}}]])
    fig.add_trace(go.Bar(x=merged.month, y=merged.returns, name="Returns",
                         marker_color=COLORS["orange"], opacity=0.7), secondary_y=False)
    fig.add_trace(go.Scatter(x=merged.month, y=merged.rate, name="Rate %",
                             mode="lines", line=dict(color=COLORS["red"], width=2)),
                  secondary_y=True)
    style_fig(fig, height=350, title_text="Monthly Returns and Return Rate")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    reasons = q(f"SELECT reason, COUNT(*) as n FROM {_tbl('v_returns_clean')} GROUP BY reason ORDER BY n DESC")
    fig = px.bar(reasons, x="n", y="reason", orientation="h",
                 color_discrete_sequence=[COLORS["orange"]])
    style_fig(fig, height=350, title_text="Return Reasons")
    fig.update_traces(texttemplate="%{{x:,}}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("orders", "v_orders_clean", ["customers", "orders", "order_items"])
