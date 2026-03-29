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

# ── Query 1: All SaaS customers ──
saas = q("SELECT status, plan_tier, mrr, usage_score FROM v_saas_customers_clean")

total = len(saas)
active_mask = saas.status == "active"
active = active_mask.sum()
churned = (saas.status == "churned").sum()
mrr = saas.loc[active_mask, "mrr"].sum()
avg_usage = saas.loc[active_mask, "usage_score"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Subscribers", f"{total:,}")
c2.metric("Active", f"{active:,}", f"{active/total*100:.0f}%")
c3.metric("Churned", f"{churned:,}", f"{churned/total*100:.1f}%")
c4.metric("Active MRR", f"${mrr:,.0f}")
c5.metric("Avg Usage Score", f"{avg_usage:.0f}")

st.divider()

# ── Query 2: MRR movements ──
mrr_raw = q("""
    SELECT movement_date,
           strftime('%Y-%m', movement_date) as month,
           strftime('%Y', movement_date) || '-Q' || ((CAST(strftime('%m', movement_date) AS INTEGER) - 1) / 3 + 1) as quarter,
           movement_type, amount
    FROM mrr_movements
""")

# ── 1. MRR movements by quarter ──
mrr_data = mrr_raw.groupby(["quarter", "movement_type"], as_index=False).agg(total=("amount", "sum"))
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
    churn_data = mrr_raw[mrr_raw.movement_type == "churn"]
    churn_mo = churn_data.groupby("month", as_index=False).agg(
        churns=("amount", "count"),
        lost_mrr=("amount", lambda x: x.abs().sum())
    )
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
    tenure = q("""
        SELECT CAST((julianday(m.movement_date) - julianday(s.signup_date)) / 30 AS INTEGER) as months,
               COUNT(*) as churns
        FROM mrr_movements m
        JOIN saas_customers s ON m.saas_customer_id = s.saas_customer_id
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
    plan = saas.groupby(["plan_tier", "status"]).size().reset_index(name="n")
    fig = px.bar(plan, x="plan_tier", y="n", color="status", barmode="stack",
                 color_discrete_map={"active": COLORS["green"], "churned": COLORS["red"]})
    style_fig(fig, height=350, title_text="Subscribers by Plan and Status")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = px.histogram(saas, x="usage_score", color="status", barmode="overlay",
                       nbins=40, opacity=0.7,
                       color_discrete_map={"active": COLORS["green"], "churned": COLORS["red"]})
    style_fig(fig, height=350, title_text="Usage Score Distribution by Status")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

# ── Query 3: Support tickets ──
st.divider()
col1, col2 = st.columns(2)

tickets = q("""
    SELECT strftime('%Y-%m', created_date) as month,
           priority, category, resolution_hours
    FROM v_support_tickets_clean
""")

with col1:
    tk_mo = tickets.groupby(["month", "priority"]).size().reset_index(name="n")
    fig = px.area(tk_mo, x="month", y="n", color="priority",
                  color_discrete_map={"critical": COLORS["red"], "high": COLORS["orange"],
                                      "medium": "#eab308", "low": COLORS["green"]})
    style_fig(fig, height=350, title_text="Monthly Support Tickets by Priority")
    fig.update_xaxes(dtick=3)
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    res = tickets.groupby("category", as_index=False).agg(
        ticket_count=("category", "count"),
        avg_hours=("resolution_hours", "mean")
    ).sort_values("ticket_count", ascending=False)
    res["avg_hours"] = res.avg_hours.round(1)
    fig = px.bar(res, x="category", y="ticket_count", color="avg_hours",
                 color_continuous_scale="OrRd")
    style_fig(fig, height=350, title_text="Tickets by Category (color = avg resolution hrs)")
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("saas_customers", "v_saas_customers_clean", [])
