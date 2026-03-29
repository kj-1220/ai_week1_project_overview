"""Page 6: CRM Pipeline and Activity"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, _tbl, style_fig, governance_sidebar, COLORS
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.markdown("## CRM Pipeline")
st.caption("Accounts, opportunities, sales activity | Clean views")

# ── Query 1: KPIs ──
kpis = q("""
    SELECT
        (SELECT COUNT(*) FROM accounts) as accts,
        (SELECT AVG(health_score) FROM accounts) as health,
        (SELECT COUNT(*) FROM v_opportunities_clean) as opps,
        (SELECT COUNT(*) FROM v_opportunities_clean WHERE stage NOT IN ('closed_won','closed_lost')) as open_opps,
        (SELECT SUM(amount) FROM v_opportunities_clean WHERE stage NOT IN ('closed_won','closed_lost')) as pipeline,
        (SELECT COUNT(*) FROM v_activities_clean) as activities
""")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Accounts", f"{kpis.accts[0]:,}")
c2.metric("Avg Health", f"{kpis.health[0]:.0f}")
c3.metric("Opportunities", f"{kpis.opps[0]:,}")
c4.metric("Open Deals", f"{kpis.open_opps[0]:,}")
c5.metric("Pipeline Value", f"${kpis.pipeline[0]/1e6:.1f}M")
c6.metric("Activities", f"{kpis.activities[0]:,}")

st.divider()

# ── Query 2: Opportunities ──
opps = q("SELECT stage, amount, probability, product_interest FROM v_opportunities_clean")

col1, col2 = st.columns(2)

with col1:
    stages = opps.groupby("stage", as_index=False).agg(
        deals=("amount", "count"),
        value=("amount", "sum"),
        prob=("probability", "mean")
    ).sort_values("prob")
    fig = go.Figure(go.Funnel(
        y=stages.stage, x=stages.deals, textinfo="value+percent initial",
        marker_color=[COLORS["light_gray"], "#93c5fd", COLORS["blue"],
                      "#1d4ed8", COLORS["green"], COLORS["red"]]
    ))
    style_fig(fig, height=400, title_text="Opportunity Funnel")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    open_mask = ~opps.stage.isin(["closed_won", "closed_lost"])
    won_mask = opps.stage == "closed_won"
    open_val = opps[open_mask].groupby("product_interest", as_index=False).agg(open_val=("amount", "sum"))
    won_val = opps[won_mask].groupby("product_interest", as_index=False).agg(won_val=("amount", "sum"))
    by_prod = open_val.merge(won_val, on="product_interest", how="outer").fillna(0).sort_values("open_val", ascending=False)
    fig = px.bar(by_prod, x="product_interest", y=["open_val", "won_val"],
                 barmode="stack", color_discrete_sequence=[COLORS["blue"], COLORS["green"]],
                 labels={"value": "Amount ($)", "variable": ""})
    style_fig(fig, height=400, title_text="Pipeline by Product Interest")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

# ── Query 3: Accounts ──
st.divider()
col1, col2 = st.columns(2)

acct_data = q("SELECT health_score, account_tier FROM accounts")

with col1:
    fig = px.histogram(acct_data, x="health_score", color="account_tier", nbins=30,
                       color_discrete_map={"strategic": COLORS["green"], "growth": COLORS["blue"],
                                           "maintain": COLORS["orange"], "at_risk": COLORS["red"]},
                       category_orders={"account_tier": ["strategic","growth","maintain","at_risk"]})
    style_fig(fig, height=360, title_text="Health Score Distribution by Tier")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    tier = acct_data.groupby("account_tier", as_index=False).agg(
        n=("health_score", "count"),
        health=("health_score", "mean")
    )
    fig = px.bar(tier, x="account_tier", y="n", color="health",
                 color_continuous_scale="RdYlGn", text="n",
                 category_orders={"account_tier": ["strategic","growth","maintain","at_risk"]})
    style_fig(fig, height=360, title_text="Accounts by Tier (color = avg health)", showlegend=False)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# ── Query 4: Activities ──
st.divider()

activities = q("""
    SELECT activity_id, activity_date,
           strftime('%Y-%m', activity_date) as month,
           activity_type, outcome, account_id
    FROM v_activities_clean
""")

act_mo = activities.groupby(["month", "activity_type"]).size().reset_index(name="n")
fig = px.area(act_mo, x="month", y="n", color="activity_type",
              color_discrete_sequence=[COLORS["blue"], COLORS["green"],
                                       COLORS["purple"], COLORS["orange"], COLORS["red"]])
style_fig(fig, height=380, title_text="Monthly CRM Activity by Type")
fig.update_xaxes(dtick=3)
fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
st.plotly_chart(fig, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    outcomes = activities.groupby(["activity_type", "outcome"]).size().reset_index(name="n")
    fig = px.bar(outcomes, x="activity_type", y="n", color="outcome", barmode="stack",
                 color_discrete_map={"positive": COLORS["green"], "neutral": COLORS["gray"],
                                     "negative": COLORS["red"], "follow_up_needed": COLORS["orange"]})
    style_fig(fig, height=360, title_text="Activity Outcomes")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    reps = q("""
        SELECT a2.owner as rep, COUNT(act.activity_id) as activities,
               COUNT(DISTINCT act.account_id) as accounts,
               ROUND(SUM(CASE WHEN act.outcome='positive' THEN 1.0 ELSE 0 END)/COUNT(*)*100, 0) as win_rate
        FROM v_activities_clean act
        JOIN accounts a2 ON act.account_id = a2.account_id
        GROUP BY rep ORDER BY activities DESC
    """)
    fig = px.bar(reps, x="rep", y="activities", color="win_rate",
                 color_continuous_scale="Greens")
    style_fig(fig, height=360, title_text="Sales Rep Activity (color = positive rate %)")
    fig.update_xaxes(tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("activities", "v_activities_clean", ["activities"])
