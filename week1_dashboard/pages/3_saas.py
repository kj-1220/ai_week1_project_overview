"""Page 3: SaaS and MRR"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, _tbl, style_fig, governance_sidebar, COLORS
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.markdown("## SaaS and MRR")
st.caption("Subscriptions, MRR movements, churn, support | Clean views")

# ── KPIs ──
total = q(f"SELECT COUNT(*) as v FROM {_tbl('v_saas_customers_clean')}").v[0]
active = q(f"SELECT COUNT(*) as v FROM {_tbl('v_saas_customers_clean')} WHERE status='active'").v[0]
churned = q(f"SELECT COUNT(*) as v FROM {_tbl('v_saas_customers_clean')} WHERE status='churned'").v[0]
mrr = q(f"SELECT SUM(mrr) as v FROM {_tbl('v_saas_customers_clean')} WHERE status='active'").v[0]
avg_usage = q(f"SELECT AVG(usage_score) as v FROM {_tbl('v_saas_customers_clean')} WHERE status='active'").v[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Subscribers", f"{total:,}")
c2.metric("Active", f"{active:,}", f"{active/total*100:.0f}%")
c3.metric("Churned", f"{churned:,}", f"{churned/total*100:.1f}%")
c4.metric("Active MRR", f"${mrr:,.0f}")
c5.metric("Avg Usage Score", f"{avg_usage:.0f}")

st.divider()

# ── 1. MRR movements by quarter ──
mrr_data = q(f"""
    SELECT CONCAT(CAST(EXTRACT(YEAR FROM SAFE_CAST(movement_date AS DATE)) AS STRING), '-Q',
                  CAST(EXTRACT(QUARTER FROM SAFE_CAST(movement_date AS DATE)) AS STRING)) as quarter,
           movement_type, SUM(amount) as total
    FROM {_tbl('mrr_movements')} GROUP BY quarter, movement_type ORDER BY quarter
""")
pivot = mrr_data.pivot_table(index="quarter", columns="movement_type", values="total", aggfunc="sum").fillna(0)
if "churn" in pivot.columns:
    pivot["churn"] = -abs(pivot["churn"])
if "contraction" in pivot.columns:
    pivot["contraction"] = -abs(pivot["contraction"])

fig = go.Figure()
bar_colors = {"new_business": COLORS["green"], "expansion": COLORS["blue"],
              "churn": COLORS["red"], "contraction": COLORS["orange"]}
for col in ["new_business", "expansion", "churn", "contraction"]:
    if col in pivot.columns:
        fig.add_trace(go.Bar(x=pivot.index, y=pivot[col],
                             name=col.replace("_", " ").title(),
                             marker_color=bar_colors.get(col)))

pivot["net"] = pivot.sum(axis=1)
fig.add_trace(go.Scatter(x=pivot.index, y=pivot.net, name="Net",
                         mode="lines+markers", line=dict(color=COLORS["dark"], width=2)))

style_fig(fig, height=420, title_text="Quarterly MRR Movements", barmode="relative")
fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
st.plotly_chart(fig, use_container_width=True)

# ── 2 & 3. Churn analysis ──
col1, col2 = st.columns(2)

with col1:
    churn_mo = q(f"""
        SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(movement_date AS DATE)) as month,
               COUNT(*) as churns, SUM(ABS(amount)) as lost_mrr
        FROM {_tbl('mrr_movements')} WHERE movement_type = 'churn'
        GROUP BY month ORDER BY month
    """)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=churn_mo.month, y=churn_mo.churns, name="Churns",
                         marker_color=COLORS["red"], opacity=0.7), secondary_y=False)
    fig.add_trace(go.Scatter(x=churn_mo.month, y=churn_mo.lost_mrr, name="Lost MRR",
                             mode="lines", line=dict(color=COLORS["dark"], width=1.5)),
                  secondary_y=True)
    style_fig(fig, height=360, title_text="Monthly Churn Events and Lost MRR")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    fig.update_xaxes(dtick=3)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    tenure = q(f"""
        SELECT DATE_DIFF(SAFE_CAST(m.movement_date AS DATE), SAFE_CAST(s.signup_date AS DATE), DAY) / 30 as months,
               COUNT(*) as churns
        FROM {_tbl('mrr_movements')} m
        JOIN {_tbl('saas_customers')} s ON m.saas_customer_id = s.saas_customer_id
        WHERE m.movement_type = 'churn'
        GROUP BY months HAVING months BETWEEN 1 AND 36 ORDER BY months
    """)
    fig = px.bar(tenure, x="months", y="churns", color_discrete_sequence=[COLORS["red"]])
    fig.add_vrect(x0=9, x1=14, fillcolor="red", opacity=0.05, line_width=0,
                  annotation_text="12-mo", annotation_position="top")
    fig.add_vrect(x0=21, x1=26, fillcolor="red", opacity=0.05, line_width=0,
                  annotation_text="24-mo", annotation_position="top")
    style_fig(fig, height=360, title_text="Churn by Months Active")
    fig.update_xaxes(title_text="Months active at churn")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 4 & 5. Plan distribution and usage scores ──
col1, col2 = st.columns(2)

with col1:
    plan = q(f"""
        SELECT plan_tier, status, COUNT(*) as n
        FROM {_tbl('v_saas_customers_clean')} GROUP BY plan_tier, status ORDER BY plan_tier
    """)
    fig = px.bar(plan, x="plan_tier", y="n", color="status", barmode="stack",
                 color_discrete_map={"active": COLORS["green"], "churned": COLORS["red"]})
    style_fig(fig, height=350, title_text="Subscribers by Plan and Status")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    usage = q(f"SELECT usage_score, status FROM {_tbl('v_saas_customers_clean')}")
    fig = px.histogram(usage, x="usage_score", color="status", barmode="overlay",
                       nbins=40, opacity=0.7,
                       color_discrete_map={"active": COLORS["green"], "churned": COLORS["red"]})
    style_fig(fig, height=350, title_text="Usage Score Distribution by Status")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

# ── 6 & 7. Support tickets ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    tickets = q(f"""
        SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(created_date AS DATE)) as month,
               priority, COUNT(*) as n
        FROM {_tbl('v_support_tickets_clean')} GROUP BY month, priority ORDER BY month
    """)
    fig = px.area(tickets, x="month", y="n", color="priority",
                  color_discrete_map={{"critical":COLORS["red"], "high":COLORS["orange"],
                                       "medium":"#eab308", "low":COLORS["green"]}})
    style_fig(fig, height=350, title_text="Monthly Support Tickets by Priority")
    fig.update_xaxes(dtick=3)
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    res = q(f"""
        SELECT category, COUNT(*) as tickets,
               ROUND(AVG(resolution_hours), 1) as avg_hours
        FROM {_tbl('v_support_tickets_clean')}
        GROUP BY category ORDER BY tickets DESC
    """)
    fig = px.bar(res, x="category", y="tickets", color="avg_hours",
                 color_continuous_scale="OrRd")
    style_fig(fig, height=350, title_text="Tickets by Category (color = avg resolution hrs)")
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("saas_customers", "v_saas_customers_clean", [])
