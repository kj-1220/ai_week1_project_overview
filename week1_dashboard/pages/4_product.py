"""Page 4: Product Usage and Adoption"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, governance_sidebar, BLUE, GREEN, RED, ORANGE, PURPLE, GRAY, LIGHT_GRAY
import altair as alt
import numpy as np

st.markdown("## Product Usage and Adoption")
st.caption("Events, users, features, AI Insights launch | Clean views")

# ── KPIs ──
kpis = q("""
    SELECT
        (SELECT COUNT(*) FROM v_usage_events_clean) as events,
        (SELECT COUNT(DISTINCT user_id) FROM v_usage_events_clean) as users,
        (SELECT COUNT(DISTINCT saas_customer_id) FROM v_usage_events_clean) as accounts,
        (SELECT COUNT(*) FROM usage_events WHERE feature_module='ai_insights') as ai_events,
        (SELECT COUNT(DISTINCT feature_module) FROM v_usage_events_clean) as modules
""")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Events", f"{kpis.events[0]:,}")
c2.metric("Active Users", f"{kpis.users[0]:,}")
c3.metric("Accounts", f"{kpis.accounts[0]:,}")
c4.metric("AI Events", f"{kpis.ai_events[0]:,}")
c5.metric("Modules", f"{kpis.modules[0]}")

st.divider()

# ── 1. Events and active users over time ──
monthly = q("""
    SELECT strftime('%Y-%m', event_date) as month,
           COUNT(*) as events,
           COUNT(DISTINCT user_id) as users,
           COUNT(DISTINCT saas_customer_id) as accounts
    FROM v_usage_events_clean GROUP BY month ORDER BY month
""")

base = alt.Chart(monthly).encode(x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=monthly.month.tolist()[::3])))
bars = base.mark_bar(color=LIGHT_GRAY, opacity=0.5).encode(y=alt.Y("events:Q", title="Events"))
users_line = base.mark_line(color=BLUE, strokeWidth=2).encode(y=alt.Y("users:Q", title="Users / Accounts"))
accts_line = base.mark_line(color=GREEN, strokeWidth=2).encode(y="accounts:Q")

chart = alt.layer(bars, users_line, accts_line).resolve_scale(y="independent").properties(
    title="Monthly Platform Engagement", height=380)
st.altair_chart(chart, use_container_width=True)

# ── 2 & 3. Power users and event types ──
col1, col2 = st.columns(2)

with col1:
    user_ev = q("""
        SELECT user_id, COUNT(*) as events
        FROM v_usage_events_clean GROUP BY user_id ORDER BY events DESC
    """)
    total = user_ev.events.sum()
    top20 = int(len(user_ev) * 0.2)
    top20_share = user_ev.head(top20).events.sum() / total * 100

    # Downsample for chart performance
    user_ev["cum_pct"] = user_ev.events.cumsum() / total * 100
    user_ev["rank_pct"] = np.arange(1, len(user_ev)+1) / len(user_ev) * 100
    sampled = user_ev.iloc[::max(1, len(user_ev)//200)]

    chart = alt.Chart(sampled).mark_area(
        line={"color": BLUE, "strokeWidth": 2},
        color=alt.Gradient(gradient="linear", stops=[
            alt.GradientStop(color=BLUE, offset=1),
            alt.GradientStop(color="rgba(37,99,235,0.06)", offset=0)
        ], x1=1, x2=1, y1=1, y2=0)
    ).encode(
        x=alt.X("rank_pct:Q", title="% of users (ranked)"),
        y=alt.Y("cum_pct:Q", title="% of total events")
    ).properties(title=f"Power Users: Top 20% = {top20_share:.0f}% of events", height=340)
    st.altair_chart(chart, use_container_width=True)

with col2:
    etypes = q("SELECT event_type, COUNT(*) as n FROM v_usage_events_clean GROUP BY event_type ORDER BY n DESC")
    chart = alt.Chart(etypes).mark_bar(color=BLUE).encode(
        x=alt.X("n:Q", title="Count"),
        y=alt.Y("event_type:N", title=None, sort="-x")
    ).properties(title="Event Type Distribution", height=340)
    st.altair_chart(chart, use_container_width=True)

st.divider()

# ── 4. Feature adoption depth ──
adoption = q("""
    SELECT feature_module, adoption_depth, COUNT(*) as accounts
    FROM v_feature_adoption_clean GROUP BY feature_module, adoption_depth
""")
depth_order = ["none", "light", "moderate", "deep"]
chart = alt.Chart(adoption).mark_bar().encode(
    x=alt.X("feature_module:N", title=None),
    y=alt.Y("accounts:Q", title="Accounts", stack=True),
    color=alt.Color("adoption_depth:N",
                     scale=alt.Scale(domain=depth_order, range=[RED, ORANGE, "#eab308", GREEN]),
                     sort=depth_order)
).properties(title="Feature Adoption Depth by Module", height=360)
st.altair_chart(chart, use_container_width=True)

# ── 5, 6, 7. AI Insights ──
st.divider()
st.markdown("#### AI Insights Module — Q4 2025 Launch")

col1, col2, col3 = st.columns(3)

with col1:
    ai = q("""
        SELECT strftime('%Y-%m', event_date) as month, COUNT(*) as events
        FROM usage_events WHERE feature_module = 'ai_insights'
        GROUP BY month ORDER BY month
    """)
    if not ai.empty:
        chart = alt.Chart(ai).mark_bar(color=PURPLE).encode(
            x=alt.X("month:O", title=None), y=alt.Y("events:Q", title="Events")
        ).properties(title="AI Events by Month", height=280)
        st.altair_chart(chart, use_container_width=True)

with col2:
    ai_types = q("""
        SELECT event_type, COUNT(*) as n
        FROM usage_events WHERE feature_module = 'ai_insights'
        GROUP BY event_type ORDER BY n DESC
    """)
    if not ai_types.empty:
        chart = alt.Chart(ai_types).mark_arc(innerRadius=50).encode(
            theta="n:Q",
            color=alt.Color("event_type:N", scale=alt.Scale(range=[PURPLE, "#a78bfa", "#c4b5fd"]))
        ).properties(title="AI Event Types", height=280)
        st.altair_chart(chart, use_container_width=True)

with col3:
    comp = q("""
        SELECT CASE WHEN fa.saas_customer_id IS NOT NULL THEN 'Adopter' ELSE 'Non-Adopter' END as grp,
               AVG(sc.usage_score) as score, COUNT(*) as n
        FROM saas_customers sc
        LEFT JOIN (SELECT DISTINCT saas_customer_id FROM feature_adoption
                   WHERE feature_module='ai_insights') fa ON sc.saas_customer_id = fa.saas_customer_id
        WHERE sc.status = 'active' GROUP BY grp
    """)
    chart = alt.Chart(comp).mark_bar().encode(
        x=alt.X("grp:N", title=None),
        y=alt.Y("score:Q", title="Avg Usage Score"),
        color=alt.Color("grp:N", scale=alt.Scale(domain=["Adopter","Non-Adopter"], range=[PURPLE, GRAY]), legend=None)
    ).properties(title="Usage Score: Adopters vs Others", height=280)
    text = alt.Chart(comp).mark_text(dy=-10, fontSize=12).encode(x="grp:N", y="score:Q", text=alt.Text("score:Q", format=".0f"))
    st.altair_chart(chart + text, use_container_width=True)

governance_sidebar("usage_events", "v_usage_events_clean", [])
