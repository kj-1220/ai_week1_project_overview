"""Page 6: CRM Pipeline and Activity"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, governance_sidebar, BLUE, GREEN, RED, ORANGE, PURPLE, GRAY, LIGHT_GRAY, DARK
import altair as alt

st.markdown("## CRM Pipeline")
st.caption("Accounts, opportunities, sales activity | Clean views")

# ── KPIs ──
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

# ── 1. Funnel ──
col1, col2 = st.columns(2)

with col1:
    stages = q("""
        SELECT stage, COUNT(*) as deals, SUM(amount) as value, AVG(probability) as prob
        FROM v_opportunities_clean GROUP BY stage ORDER BY prob
    """)
    chart = alt.Chart(stages).mark_bar(color=BLUE).encode(
        x=alt.X("deals:Q", title="Deals"),
        y=alt.Y("stage:N", title=None, sort=alt.EncodingSortField(field="prob", order="descending")),
        color=alt.Color("prob:Q", scale=alt.Scale(scheme="blues"), title="Probability")
    ).properties(title="Opportunity Funnel", height=380)
    st.altair_chart(chart, use_container_width=True)

with col2:
    by_prod = q("""
        SELECT product_interest,
               SUM(CASE WHEN stage NOT IN ('closed_won','closed_lost') THEN amount ELSE 0 END) as open_val,
               SUM(CASE WHEN stage='closed_won' THEN amount ELSE 0 END) as won_val
        FROM v_opportunities_clean GROUP BY product_interest ORDER BY open_val DESC
    """)
    import pandas as pd
    melted = pd.melt(by_prod, id_vars=["product_interest"], value_vars=["open_val","won_val"],
                     var_name="type", value_name="amount")
    chart = alt.Chart(melted).mark_bar().encode(
        x=alt.X("product_interest:N", title=None, sort=by_prod.product_interest.tolist()),
        y=alt.Y("amount:Q", title="Amount ($)", stack=True),
        color=alt.Color("type:N", scale=alt.Scale(domain=["open_val","won_val"], range=[BLUE, GREEN]))
    ).properties(title="Pipeline by Product Interest", height=380)
    st.altair_chart(chart, use_container_width=True)

# ── 3 & 4. Account health ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    acct_data = q("SELECT health_score, account_tier FROM accounts")
    tier_order = ["strategic","growth","maintain","at_risk"]
    chart = alt.Chart(acct_data).mark_bar(opacity=0.7).encode(
        x=alt.X("health_score:Q", bin=alt.Bin(maxbins=30), title="Health Score"),
        y=alt.Y("count()", title="Accounts"),
        color=alt.Color("account_tier:N",
                         scale=alt.Scale(domain=tier_order, range=[GREEN, BLUE, ORANGE, RED]),
                         sort=tier_order)
    ).properties(title="Health Score Distribution by Tier", height=340)
    st.altair_chart(chart, use_container_width=True)

with col2:
    tier = q("SELECT account_tier, COUNT(*) as n, AVG(health_score) as health FROM accounts GROUP BY account_tier")
    chart = alt.Chart(tier).mark_bar().encode(
        x=alt.X("account_tier:N", title=None, sort=tier_order),
        y=alt.Y("n:Q", title="Count"),
        color=alt.Color("health:Q", scale=alt.Scale(scheme="redyellowgreen"), title="Avg Health")
    ).properties(title="Accounts by Tier (color = avg health)", height=340)
    text = alt.Chart(tier).mark_text(dy=-10, fontSize=12).encode(
        x=alt.X("account_tier:N", sort=tier_order), y="n:Q", text="n:Q"
    )
    st.altair_chart(chart + text, use_container_width=True)

# ── 5. Activity volume over time ──
st.divider()

act = q("""
    SELECT strftime('%Y-%m', activity_date) as month, activity_type, COUNT(*) as n
    FROM v_activities_clean GROUP BY month, activity_type ORDER BY month
""")
chart = alt.Chart(act).mark_area().encode(
    x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=act.month.unique().tolist()[::3])),
    y=alt.Y("n:Q", title="Activities", stack=True),
    color="activity_type:N"
).properties(title="Monthly CRM Activity by Type", height=360)
st.altair_chart(chart, use_container_width=True)

# ── 6 & 7. Outcomes + rep leaderboard ──
col1, col2 = st.columns(2)

with col1:
    outcomes = q("""
        SELECT activity_type, outcome, COUNT(*) as n
        FROM v_activities_clean GROUP BY activity_type, outcome
    """)
    chart = alt.Chart(outcomes).mark_bar().encode(
        x=alt.X("activity_type:N", title=None),
        y=alt.Y("n:Q", title="Count", stack=True),
        color=alt.Color("outcome:N",
                         scale=alt.Scale(domain=["positive","neutral","negative","follow_up_needed"],
                                         range=[GREEN, GRAY, RED, ORANGE]))
    ).properties(title="Activity Outcomes", height=340)
    st.altair_chart(chart, use_container_width=True)

with col2:
    reps = q("""
        SELECT a2.owner as rep, COUNT(act.activity_id) as activities,
               COUNT(DISTINCT act.account_id) as accounts,
               ROUND(SUM(CASE WHEN act.outcome='positive' THEN 1.0 ELSE 0 END)/COUNT(*)*100, 0) as win_rate
        FROM v_activities_clean act
        JOIN accounts a2 ON act.account_id = a2.account_id
        GROUP BY rep ORDER BY activities DESC
    """)
    chart = alt.Chart(reps).mark_bar().encode(
        x=alt.X("rep:N", title=None, sort="-y", axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("activities:Q", title="Activities"),
        color=alt.Color("win_rate:Q", scale=alt.Scale(scheme="greens"), title="Positive %")
    ).properties(title="Sales Rep Activity (color = positive rate %)", height=340)
    st.altair_chart(chart, use_container_width=True)

governance_sidebar("activities", "v_activities_clean", ["activities"])
