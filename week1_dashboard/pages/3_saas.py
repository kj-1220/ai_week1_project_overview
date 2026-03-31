"""Page 3: SaaS and MRR"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, governance_sidebar, BLUE, GREEN, RED, ORANGE, PURPLE, GRAY, DARK
import altair as alt

st.markdown("## SaaS and MRR")
st.caption("Subscriptions, MRR movements, churn, support | Clean views")

# ── KPIs ──
kpis = q("""
    SELECT
        (SELECT COUNT(*) FROM v_saas_customers_clean) as total,
        (SELECT COUNT(*) FROM v_saas_customers_clean WHERE status='active') as active,
        (SELECT COUNT(*) FROM v_saas_customers_clean WHERE status='churned') as churned,
        (SELECT SUM(mrr) FROM v_saas_customers_clean WHERE status='active') as mrr,
        (SELECT AVG(usage_score) FROM v_saas_customers_clean WHERE status='active') as avg_usage
""")
total = kpis.total[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Subscribers", f"{total:,}")
c2.metric("Active", f"{kpis.active[0]:,}", f"{kpis.active[0]/total*100:.0f}%")
c3.metric("Churned", f"{kpis.churned[0]:,}", f"{kpis.churned[0]/total*100:.1f}%")
c4.metric("Active MRR", f"${kpis.mrr[0]:,.0f}")
c5.metric("Avg Usage Score", f"{kpis.avg_usage[0]:.0f}")

st.divider()

# ── 1. MRR movements by quarter ──
mrr_data = q("""
    SELECT strftime('%Y', movement_date) || '-Q' || ((CAST(strftime('%m', movement_date) AS INTEGER) - 1) / 3 + 1) as quarter,
           movement_type, SUM(amount) as total
    FROM mrr_movements GROUP BY quarter, movement_type ORDER BY quarter
""")
# Make churn/contraction negative
mrr_data.loc[mrr_data.movement_type.isin(["churn", "contraction"]), "total"] = \
    -mrr_data.loc[mrr_data.movement_type.isin(["churn", "contraction"]), "total"].abs()

type_order = ["new_business", "expansion", "contraction", "churn"]
chart = alt.Chart(mrr_data).mark_bar().encode(
    x=alt.X("quarter:O", title=None),
    y=alt.Y("total:Q", title="MRR ($)", stack=True),
    color=alt.Color("movement_type:N",
                     scale=alt.Scale(domain=type_order, range=[GREEN, BLUE, ORANGE, RED]),
                     sort=type_order)
).properties(title="Quarterly MRR Movements", height=400)

net = mrr_data.groupby("quarter", as_index=False).agg(net=("total", "sum"))
net_line = alt.Chart(net).mark_line(color=DARK, strokeWidth=2, point=True).encode(
    x="quarter:O", y=alt.Y("net:Q")
)
st.altair_chart(chart + net_line, use_container_width=True)

# ── 2 & 3. Churn analysis ──
col1, col2 = st.columns(2)

with col1:
    churn_mo = q("""
        SELECT strftime('%Y-%m', movement_date) as month,
               COUNT(*) as churns, SUM(ABS(amount)) as lost_mrr
        FROM mrr_movements WHERE movement_type = 'churn'
        GROUP BY month ORDER BY month
    """)
    base = alt.Chart(churn_mo).encode(x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=churn_mo.month.tolist()[::3])))
    bars = base.mark_bar(color=RED, opacity=0.7).encode(y=alt.Y("churns:Q", title="Churns"))
    line = base.mark_line(color=DARK, strokeWidth=1.5).encode(y=alt.Y("lost_mrr:Q", title="Lost MRR"))
    chart = alt.layer(bars, line).resolve_scale(y="independent").properties(title="Monthly Churn Events and Lost MRR", height=340)
    st.altair_chart(chart, use_container_width=True)

with col2:
    tenure = q("""
        SELECT CAST((julianday(m.movement_date) - julianday(s.signup_date)) / 30 AS INTEGER) as months,
               COUNT(*) as churns
        FROM mrr_movements m
        JOIN saas_customers s ON m.saas_customer_id = s.saas_customer_id
        WHERE m.movement_type = 'churn'
        GROUP BY months HAVING months BETWEEN 1 AND 36 ORDER BY months
    """)
    chart = alt.Chart(tenure).mark_bar(color=RED).encode(
        x=alt.X("months:Q", title="Months active at churn"),
        y=alt.Y("churns:Q", title="Churns")
    ).properties(title="Churn by Months Active", height=340)
    st.altair_chart(chart, use_container_width=True)

st.divider()

# ── 4 & 5. Plan distribution and usage scores ──
col1, col2 = st.columns(2)

with col1:
    plan = q("SELECT plan_tier, status, COUNT(*) as n FROM v_saas_customers_clean GROUP BY plan_tier, status ORDER BY plan_tier")
    chart = alt.Chart(plan).mark_bar().encode(
        x=alt.X("plan_tier:N", title=None),
        y=alt.Y("n:Q", title="Count", stack=True),
        color=alt.Color("status:N", scale=alt.Scale(domain=["active","churned"], range=[GREEN, RED]))
    ).properties(title="Subscribers by Plan and Status", height=330)
    st.altair_chart(chart, use_container_width=True)

with col2:
    usage = q("SELECT usage_score, status FROM v_saas_customers_clean")
    chart = alt.Chart(usage).mark_bar(opacity=0.7).encode(
        x=alt.X("usage_score:Q", bin=alt.Bin(maxbins=40), title="Usage Score"),
        y=alt.Y("count()", title="Count", stack=None),
        color=alt.Color("status:N", scale=alt.Scale(domain=["active","churned"], range=[GREEN, RED]))
    ).properties(title="Usage Score Distribution by Status", height=330)
    st.altair_chart(chart, use_container_width=True)

# ── 6 & 7. Support tickets ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    tickets = q("""
        SELECT strftime('%Y-%m', created_date) as month, priority, COUNT(*) as n
        FROM v_support_tickets_clean GROUP BY month, priority ORDER BY month
    """)
    chart = alt.Chart(tickets).mark_area().encode(
        x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=tickets.month.unique().tolist()[::3])),
        y=alt.Y("n:Q", title="Tickets", stack=True),
        color=alt.Color("priority:N",
                         scale=alt.Scale(domain=["critical","high","medium","low"],
                                         range=[RED, ORANGE, "#eab308", GREEN]))
    ).properties(title="Monthly Support Tickets by Priority", height=330)
    st.altair_chart(chart, use_container_width=True)

with col2:
    res = q("""
        SELECT category, COUNT(*) as tickets, ROUND(AVG(resolution_hours), 1) as avg_hours
        FROM v_support_tickets_clean GROUP BY category ORDER BY tickets DESC
    """)
    chart = alt.Chart(res).mark_bar().encode(
        x=alt.X("category:N", title=None, sort="-y"),
        y=alt.Y("tickets:Q", title="Tickets"),
        color=alt.Color("avg_hours:Q", scale=alt.Scale(scheme="orangered"), title="Avg Hrs")
    ).properties(title="Tickets by Category (color = avg resolution hrs)", height=330)
    st.altair_chart(chart, use_container_width=True)

governance_sidebar("saas_customers", "v_saas_customers_clean", [])
