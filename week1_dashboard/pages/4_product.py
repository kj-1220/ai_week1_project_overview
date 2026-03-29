"""Page 4: Product Usage and Adoption"""
import streamlit as st
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, _tbl, style_fig, governance_sidebar, COLORS
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.markdown("## Product Usage and Adoption")
st.caption("Events, users, features, AI Insights launch | Clean views")

# ── KPIs ──
events = q(f"SELECT COUNT(*) as v FROM {_tbl('v_usage_events_clean')}").v[0]
users = q(f"SELECT COUNT(DISTINCT user_id) as v FROM {_tbl('v_usage_events_clean')}").v[0]
accounts = q(f"SELECT COUNT(DISTINCT saas_customer_id) as v FROM {_tbl('v_usage_events_clean')}").v[0]
ai_events = q(f"SELECT COUNT(*) as v FROM {_tbl('usage_events')} WHERE feature_module='ai_insights'").v[0]
modules = q(f"SELECT COUNT(DISTINCT feature_module) as v FROM {_tbl('v_usage_events_clean')}").v[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Events", f"{events:,}")
c2.metric("Active Users", f"{users:,}")
c3.metric("Accounts", f"{accounts:,}")
c4.metric("AI Events", f"{ai_events:,}")
c5.metric("Modules", f"{modules}")

st.divider()

# ── 1. Events and active users over time ──
monthly = q(f"""
    SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(event_date AS DATE)) as month,
           COUNT(*) as events,
           COUNT(DISTINCT user_id) as users,
           COUNT(DISTINCT saas_customer_id) as accounts
    FROM {_tbl('v_usage_events_clean')} GROUP BY month ORDER BY month
""")

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Bar(x=monthly.month, y=monthly.events, name="Events",
                     marker_color=COLORS["light_gray"], opacity=0.5), secondary_y=False)
fig.add_trace(go.Scatter(x=monthly.month, y=monthly.users, name="Users",
                         mode="lines", line=dict(color=COLORS["blue"], width=2)),
              secondary_y=True)
fig.add_trace(go.Scatter(x=monthly.month, y=monthly.accounts, name="Accounts",
                         mode="lines", line=dict(color=COLORS["green"], width=2)),
              secondary_y=True)

# AI launch marker
fig.add_shape(type="line", x0="2025-10", x1="2025-10", y0=0, y1=1, yref="paper",
              line=dict(dash="dash", color=COLORS["purple"], width=1))
fig.add_annotation(x="2025-10", y=1.05, yref="paper", text="AI Insights Launch",
                   showarrow=False, font=dict(size=10, color=COLORS["purple"]))

style_fig(fig, height=400, title_text="Monthly Platform Engagement")
fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
fig.update_xaxes(dtick=3)
st.plotly_chart(fig, use_container_width=True)

# ── 2 & 3. Power users and event types ──
col1, col2 = st.columns(2)

with col1:
    user_ev = q(f"SELECT user_id, COUNT(*) as events FROM {_tbl('v_usage_events_clean')} GROUP BY user_id ORDER BY events DESC")
    total = user_ev.events.sum()
    top20 = int(len(user_ev) * 0.2)
    top20_share = user_ev.head(top20).events.sum() / total * 100

    user_ev["cum_pct"] = user_ev.events.cumsum() / total * 100
    user_ev["rank_pct"] = np.arange(1, len(user_ev)+1) / len(user_ev) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=user_ev.rank_pct, y=user_ev.cum_pct, mode="lines",
                             line=dict(color=COLORS["blue"], width=2), fill="tozeroy",
                             fillcolor="rgba(37,99,235,0.06)"))
    fig.add_hline(y=80, line_dash="dot", line_color=COLORS["gray"])
    fig.add_vline(x=20, line_dash="dot", line_color=COLORS["gray"])
    style_fig(fig, height=360, title_text=f"Power Users: Top 20% = {top20_share:.0f}% of events")
    fig.update_xaxes(title_text="% of users (ranked)")
    fig.update_yaxes(title_text="% of total events")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    etypes = q(f"SELECT event_type, COUNT(*) as n FROM {_tbl('v_usage_events_clean')} GROUP BY event_type ORDER BY n DESC")
    fig = px.bar(etypes, x="n", y="event_type", orientation="h",
                 color_discrete_sequence=[COLORS["blue"]])
    style_fig(fig, height=360, title_text="Event Type Distribution")
    fig.update_traces(texttemplate="%{x:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 4. Feature adoption depth ──
adoption = q(f"""
    SELECT feature_module, adoption_depth, COUNT(*) as accounts
    FROM {_tbl('v_feature_adoption_clean')} GROUP BY feature_module, adoption_depth
""")
fig = px.bar(adoption, x="feature_module", y="accounts", color="adoption_depth",
             barmode="stack",
             color_discrete_map={"none":COLORS["red"], "light":COLORS["orange"],
                                  "moderate":"#eab308", "deep":COLORS["green"]},
             category_orders={"adoption_depth": ["none", "light", "moderate", "deep"]})
style_fig(fig, height=380, title_text="Feature Adoption Depth by Module")
fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
st.plotly_chart(fig, use_container_width=True)

# ── 5, 6, 7. AI Insights ──
st.divider()
st.markdown("#### AI Insights Module — Q4 2025 Launch")

col1, col2, col3 = st.columns(3)

with col1:
    ai = q(f"""
        SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(event_date AS DATE)) as month, COUNT(*) as events
        FROM {_tbl('usage_events')} WHERE feature_module = 'ai_insights'
        GROUP BY month ORDER BY month
    """)
    if not ai.empty:
        fig = px.bar(ai, x="month", y="events", color_discrete_sequence=[COLORS["purple"]])
        style_fig(fig, height=300, title_text="AI Events by Month")
        fig.update_traces(texttemplate="%{y:,}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    ai_types = q(f"""
        SELECT event_type, COUNT(*) as n
        FROM {_tbl('usage_events')} WHERE feature_module = 'ai_insights'
        GROUP BY event_type ORDER BY n DESC
    """)
    if not ai_types.empty:
        fig = px.pie(ai_types, names="event_type", values="n", hole=0.5,
                     color_discrete_sequence=[COLORS["purple"], "#a78bfa", "#c4b5fd"])
        style_fig(fig, height=300, title_text="AI Event Types")
        fig.update_traces(textinfo="percent+label", textfont_size=10)
        st.plotly_chart(fig, use_container_width=True)

with col3:
    comp = q(f"""
        SELECT CASE WHEN fa.saas_customer_id IS NOT NULL THEN 'Adopter' ELSE 'Non-Adopter' END as grp,
               AVG(sc.usage_score) as score, COUNT(*) as n
        FROM {_tbl('saas_customers')} sc
        LEFT JOIN (SELECT DISTINCT saas_customer_id FROM {_tbl('feature_adoption')}
                   WHERE feature_module='ai_insights') fa ON sc.saas_customer_id = fa.saas_customer_id
        WHERE sc.status = 'active' GROUP BY grp
    """)
    fig = px.bar(comp, x="grp", y="score", color="grp",
                 color_discrete_map={"Adopter": COLORS["purple"], "Non-Adopter": COLORS["gray"]},
                 text="score")
    style_fig(fig, height=300, title_text="Usage Score: Adopters vs Others", showlegend=False)
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("usage_events", "v_usage_events_clean", [])
