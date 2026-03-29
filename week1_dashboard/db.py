"""
db.py — Database connection and query helpers for the Otacon dashboard.
BigQuery version — queries GCP instead of local SQLite.
"""

import streamlit as st
import pandas as pd
import os

GCP_PROJECT = os.environ.get("GCP_PROJECT", "otacon-inc")
BQ_DATASET = os.environ.get("BQ_DATASET", "otacon")


@st.cache_resource
def get_client():
    """Singleton BigQuery client."""
    from google.cloud import bigquery
    return bigquery.Client(project=GCP_PROJECT)


def _tbl(name):
    """Return fully qualified BigQuery table name."""
    return f"`{GCP_PROJECT}.{BQ_DATASET}.{name}`"


@st.cache_data(ttl=600, show_spinner=False)
def q(sql):
    """Run a query and return a DataFrame. Cached for 10 minutes."""
    return get_client().query(sql).to_dataframe()


def metric_card(col, label, value, subtitle=None):
    """Render a single metric in a column."""
    if subtitle:
        col.metric(label, value, subtitle)
    else:
        col.metric(label, value)


def governance_sidebar(raw_table, clean_view, flag_tables=None):
    """Data quality info in the sidebar."""
    with st.sidebar.expander("Data Quality"):
        raw_n = q(f"SELECT COUNT(*) as n FROM {_tbl(raw_table)}").n[0]
        clean_n = q(f"SELECT COUNT(*) as n FROM {_tbl(clean_view)}").n[0]
        excluded = raw_n - clean_n
        st.caption(f"**{raw_table}**: {raw_n:,} raw | {clean_n:,} clean | {excluded:,} excluded")
        if flag_tables:
            for tbl in flag_tables:
                flags = q(f"""
                    SELECT rule_id, flag_type, COUNT(*) as n
                    FROM {_tbl('data_quality_flags')} WHERE table_name = '{tbl}'
                    GROUP BY rule_id, flag_type ORDER BY rule_id
                """)
                if not flags.empty:
                    st.dataframe(flags, use_container_width=True, hide_index=True)


# ── Chart defaults ──
COLORS = {
    "blue": "#2563eb",
    "green": "#16a34a",
    "red": "#dc2626",
    "orange": "#ea580c",
    "purple": "#7c3aed",
    "gray": "#6b7280",
    "light_gray": "#d1d5db",
    "dark": "#1e293b",
}

REGION_COLORS = {
    "North America": "#2563eb",
    "Europe": "#16a34a",
    "APAC": "#ea580c",
    "LATAM": "#dc2626",
    "Unknown": "#6b7280",
}

SEGMENT_COLORS = {
    "enterprise": "#7c3aed",
    "mid_market": "#2563eb",
    "smb": "#16a34a",
}

CHART_LAYOUT = dict(
    font=dict(family="Inter, system-ui, sans-serif", size=12, color="#374151"),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(t=45, b=40, l=50, r=20),
    title_font=dict(size=14, color="#1e293b"),
    xaxis=dict(gridcolor="#f3f4f6", linecolor="#e5e7eb"),
    yaxis=dict(gridcolor="#f3f4f6", linecolor="#e5e7eb"),
)


def style_fig(fig, height=400, **kwargs):
    """Apply consistent styling to a Plotly figure."""
    layout = {**CHART_LAYOUT, "height": height, **kwargs}
    fig.update_layout(**layout)
    return fig
