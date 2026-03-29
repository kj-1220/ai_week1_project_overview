"""
Otacon Inc. — Analytics Portal
================================
Enterprise dashboard platform landing page.
Each project card links to an independently deployed Cloud Run service.
Add new entries to PROJECTS as you complete each week.
"""

import streamlit as st

st.set_page_config(
    page_title="Otacon Inc. | Analytics Portal",
    page_icon="O",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Project Registry ──────────────────────────────────────────────────────────
# Add new projects here. Each gets a card on the portal.
# status: "live" shows a link button, "coming_soon" shows a muted label.
# url: replace __WEEK1_URL__ with your actual Cloud Run URL after deployment.
PROJECTS = [
    {
        "title": "Week 1 — Enterprise Data Platform & EDA",
        "description": (
            "Full-stack synthetic data platform for Otacon Inc. "
            "Five interconnected business layers — E-Commerce, SaaS, Product Analytics, "
            "Payments & AR, and CRM Pipeline — with 33 BigQuery tables, 12 governed clean views, "
            "engineered storylines, and controlled data quality issues."
        ),
        "tech": ["Python", "BigQuery", "Streamlit", "Plotly", "Cloud Run"],
        "url": "__WEEK1_URL__",
        "status": "live",
    },
    {
        "title": "Week 3 — Dashboard Component Library",
        "description": (
            "Reusable, contract-driven Streamlit components — KPI cards, trend charts, "
            "filter panels, data tables, and comparison views — designed for import by "
            "downstream AI agents and future dashboards."
        ),
        "tech": ["Python", "Streamlit", "Component Architecture"],
        "url": "",
        "status": "coming_soon",
    },
    {
        "title": "Weeks 5–7 — AI Agent Dashboards",
        "description": (
            "Natural language query interface, anomaly detection, and automated insight "
            "generation powered by LLM agents operating over the Otacon data platform."
        ),
        "tech": ["LangChain", "Claude API", "BigQuery", "Streamlit"],
        "url": "",
        "status": "coming_soon",
    },
]


# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Base ── */
    .block-container { max-width: 820px; padding-top: 2.5rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { display: none; }

    /* ── Header ── */
    .portal-header {
        text-align: center;
        margin-bottom: 2.5rem;
    }
    .portal-header h1 {
        font-size: 2rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    .portal-header .subtitle {
        font-size: 1.05rem;
        color: #6b7280;
        font-weight: 400;
        margin-top: 0;
    }
    .portal-header .divider-line {
        width: 60px;
        height: 3px;
        background: #2563eb;
        margin: 1.2rem auto 0 auto;
        border-radius: 2px;
    }

    /* ── Project Cards ── */
    .project-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1.6rem 1.8rem;
        margin-bottom: 1.25rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .project-card:hover {
        border-color: #2563eb;
        box-shadow: 0 2px 12px rgba(37, 99, 235, 0.08);
    }
    .project-card h3 {
        font-size: 1.1rem;
        font-weight: 600;
        color: #111827;
        margin: 0 0 0.5rem 0;
    }
    .project-card p {
        font-size: 0.9rem;
        color: #4b5563;
        line-height: 1.55;
        margin: 0 0 0.85rem 0;
    }

    /* ── Status Badges ── */
    .status-live {
        display: inline-block;
        background: #ecfdf5;
        color: #059669;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 20px;
        margin-left: 8px;
        vertical-align: middle;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }
    .status-soon {
        display: inline-block;
        background: #f3f4f6;
        color: #9ca3af;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 20px;
        margin-left: 8px;
        vertical-align: middle;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }

    /* ── Tech Tags ── */
    .tech-tag {
        display: inline-block;
        background: #f0f4ff;
        color: #3b60a0;
        font-size: 0.73rem;
        font-weight: 500;
        padding: 3px 10px;
        border-radius: 4px;
        margin-right: 6px;
        margin-bottom: 4px;
    }

    /* ── Footer ── */
    .portal-footer {
        text-align: center;
        margin-top: 2.5rem;
        padding-top: 1.5rem;
        border-top: 1px solid #e5e7eb;
        color: #9ca3af;
        font-size: 0.82rem;
        line-height: 1.8;
    }
    .portal-footer a {
        color: #6b7280;
        text-decoration: none;
        font-weight: 500;
    }
    .portal-footer a:hover {
        color: #2563eb;
    }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="portal-header">
    <h1>Otacon Inc.</h1>
    <p class="subtitle">Analytics Portal</p>
    <div class="divider-line"></div>
</div>
""", unsafe_allow_html=True)

st.markdown(
    "Each dashboard is independently deployed on Google Cloud Run, "
    "querying a governed BigQuery data warehouse."
)

st.markdown("---")


# ── Project Cards ─────────────────────────────────────────────────────────────
for project in PROJECTS:
    status_badge = (
        '<span class="status-live">Live</span>'
        if project["status"] == "live"
        else '<span class="status-soon">Coming Soon</span>'
    )
    tech_html = "".join(
        f'<span class="tech-tag">{t}</span>' for t in project["tech"]
    )

    st.markdown(f"""
    <div class="project-card">
        <h3>{project["title"]} {status_badge}</h3>
        <p>{project["description"]}</p>
        {tech_html}
    </div>
    """, unsafe_allow_html=True)

    if project["status"] == "live" and project["url"] != "__WEEK1_URL__":
        st.link_button(f"Open Dashboard", project["url"], use_container_width=True)
    elif project["status"] == "live":
        st.caption(
            "Replace __WEEK1_URL__ in app.py with your deployed Week 1 dashboard URL"
        )


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="portal-footer">
    Built with Streamlit &middot; Deployed on Google Cloud Run &middot; Data in BigQuery<br>
    <a href="https://github.com/kj-1220" target="_blank">GitHub</a>
    &nbsp;&middot;&nbsp;
    <a href="#" target="_blank">LinkedIn</a>
</div>
""", unsafe_allow_html=True)
