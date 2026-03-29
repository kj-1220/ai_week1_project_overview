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

# ── KPIs ──
accts = q(f"SELECT COUNT(*) as v FROM {_tbl('accounts')}").v[0]
health = q(f"SELECT AVG(health_score) as v FROM {_tbl('accounts')}").v[0]
opps = q(f"SELECT COUNT(*) as v FROM {_tbl('v_opportunities_clean')}").v[0]
open_opps = q(f"SELECT COUNT(*) as v FROM {_tbl('v_opportunities_clean')} WHERE stage NOT IN ('closed_won','closed_lost')").v[0]
pipeline = q(f"SELECT SUM(amount) as v FROM {_tbl('v_opportunities_clean')} WHERE stage NOT IN ('closed_won','closed_lost')").v[0]
activities = q(f"SELECT COUNT(*) as v FROM {_tbl('v_activities_clean')}").v[0]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Accounts", f"{accts:,}")
c2.metric("Avg Health", f"{health:.0f}")
c3.metric("Opportunities", f"{opps:,}")
c4.metric("Open Deals", f"{open_opps:,}")
c5.metric("Pipeline Value", f"${pipeline/1e6:.1f}M")
c6.metric("Activities", f"{activities:,}")

st.divider()

# ── 1. Pipeline funnel + 2. Pipeline by product ──
col1, col2 = st.columns(2)

with col1:
    stages = q(f"""
        SELECT stage, COUNT(*) as deals, SUM(amount) as value, AVG(probability) as prob
        FROM {_tbl('v_opportunities_clean')} GROUP BY stage ORDER BY prob
    """)
    fig = go.Figure(go.Funnel(
        y=stages.stage, x=stages.deals, textinfo="value+percent initial",
        marker_color=[COLORS["light_gray"], "#93c5fd", COLORS["blue"],
                      "#1d4ed8", COLORS["green"], COLORS["red"]]
    ))
    style_fig(fig, height=400, title_text="Opportunity Funnel")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    by_prod = q(f"""
        SELECT product_interest,
               SUM(CASE WHEN stage NOT IN ('closed_won','closed_lost') THEN amount ELSE 0 END) as open_val,
               SUM(CASE WHEN stage='closed_won' THEN amount ELSE 0 END) as won_val
        FROM {_tbl('v_opportunities_clean')} GROUP BY product_interest ORDER BY open_val DESC
    """)
    fig = px.bar(by_prod, x="product_interest", y=["open_val", "won_val"],
                 barmode="stack", color_discrete_sequence=[COLORS["blue"], COLORS["green"]],
                 labels={"value": "Amount ($)", "variable": ""})
    style_fig(fig, height=400, title_text="Pipeline by Product Interest")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

# ── 3. Account health distribution + 4. Tier breakdown ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    acct_data = q(f"SELECT health_score, account_tier FROM {_tbl('accounts')}")
    fig = px.histogram(acct_data, x="health_score", color="account_tier", nbins=30,
                       color_discrete_map={"strategic":COLORS["green"], "growth":COLORS["blue"],
                                            "maintain":COLORS["orange"], "at_risk":COLORS["red"]},
                       category_orders={"account_tier": ["strategic","growth","maintain","at_risk"]})
    style_fig(fig, height=360, title_text="Health Score Distribution by Tier")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    tier = q(f"SELECT account_tier, COUNT(*) as n, AVG(health_score) as health FROM {_tbl('accounts')} GROUP BY account_tier")
    fig = px.bar(tier, x="account_tier", y="n", color="health",
                 color_continuous_scale="RdYlGn", text="n",
                 category_orders={"account_tier": ["strategic","growth","maintain","at_risk"]})
    style_fig(fig, height=360, title_text="Accounts by Tier (color = avg health)", showlegend=False)
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# ── 5. Activity volume over time ──
st.divider()
act = q(f"""
    SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(activity_date AS DATE)) as month,
           activity_type, COUNT(*) as n
    FROM {_tbl('v_activities_clean')} GROUP BY month, activity_type ORDER BY month
""")
fig = px.area(act, x="month", y="n", color="activity_type",
              color_discrete_sequence=[COLORS["blue"], COLORS["green"],
                                        COLORS["purple"], COLORS["orange"], COLORS["red"]])
style_fig(fig, height=380, title_text="Monthly CRM Activity by Type")
fig.update_xaxes(dtick=3)
fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
st.plotly_chart(fig, use_container_width=True)

# ── 6 & 7. Outcomes + rep leaderboard ──
col1, col2 = st.columns(2)

with col1:
    outcomes = q(f"""
        SELECT activity_type, outcome, COUNT(*) as n
        FROM {_tbl('v_activities_clean')} GROUP BY activity_type, outcome
    """)
    fig = px.bar(outcomes, x="activity_type", y="n", color="outcome", barmode="stack",
                 color_discrete_map={"positive":COLORS["green"], "neutral":COLORS["gray"],
                                      "negative":COLORS["red"], "follow_up_needed":COLORS["orange"]})
    style_fig(fig, height=360, title_text="Activity Outcomes")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    reps = q(f"""
        SELECT a2.owner as rep, COUNT(act.activity_id) as activities,
               COUNT(DISTINCT act.account_id) as accounts,
               ROUND(SUM(CASE WHEN act.outcome='positive' THEN 1.0 ELSE 0 END)/COUNT(*)*100, 0) as win_rate
        FROM {_tbl('v_activities_clean')} act
        JOIN {_tbl('accounts')} a2 ON act.account_id = a2.account_id
        GROUP BY rep ORDER BY activities DESC
    """)
    fig = px.bar(reps, x="rep", y="activities", color="win_rate",
                 color_continuous_scale="Greens")
    style_fig(fig, height=360, title_text="Sales Rep Activity (color = positive rate %)")
    fig.update_xaxes(tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("activities", "v_activities_clean", ["activities"])
