"""
db.py — Database connection, query helper, and Altair theme.
"""
import streamlit as st
import pandas as pd
import altair as alt
import os
import sqlite3

DB_PATH = os.environ.get("OTACON_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "otacon.db"))

@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def _tbl(name):
    return name

@st.cache_data(ttl=600, show_spinner=False)
def q(sql):
    return pd.read_sql_query(sql, get_conn())

def governance_sidebar(raw_table, clean_view, flag_tables=None):
    with st.sidebar.expander("Data Quality"):
        counts = q(f"""
            SELECT
                (SELECT COUNT(*) FROM {raw_table}) as raw_n,
                (SELECT COUNT(*) FROM {clean_view}) as clean_n
        """)
        raw_n = counts.raw_n[0]
        clean_n = counts.clean_n[0]
        excluded = raw_n - clean_n
        st.caption(f"**{raw_table}**: {raw_n:,} raw | {clean_n:,} clean | {excluded:,} excluded")
        if flag_tables:
            tbl_list = ", ".join(f"'{t}'" for t in flag_tables)
            flags = q(f"""
                SELECT rule_id, flag_type, COUNT(*) as n
                FROM data_quality_flags WHERE table_name IN ({tbl_list})
                GROUP BY rule_id, flag_type ORDER BY rule_id
            """)
            if not flags.empty:
                st.dataframe(flags, use_container_width=True, hide_index=True)

# ── Color palette ──
BLUE = "#2563eb"
GREEN = "#16a34a"
RED = "#dc2626"
ORANGE = "#ea580c"
PURPLE = "#7c3aed"
GRAY = "#6b7280"
LIGHT_GRAY = "#d1d5db"
DARK = "#1e293b"

PALETTE = [BLUE, GREEN, PURPLE, ORANGE, RED, GRAY]

# ── Altair theme ──
def otacon_theme():
    return {
        "config": {
            "background": "white",
            "title": {"font": "Inter, system-ui, sans-serif", "fontSize": 14, "color": DARK},
            "axis": {
                "labelFont": "Inter, system-ui, sans-serif",
                "labelFontSize": 11,
                "labelColor": GRAY,
                "titleFont": "Inter, system-ui, sans-serif",
                "titleFontSize": 12,
                "titleColor": GRAY,
                "gridColor": "#f3f4f6",
                "domainColor": "#e5e7eb",
            },
            "legend": {
                "labelFont": "Inter, system-ui, sans-serif",
                "labelFontSize": 11,
                "titleFont": "Inter, system-ui, sans-serif",
                "orient": "top",
            },
            "view": {"strokeWidth": 0},
            "range": {"category": PALETTE},
        }
    }

alt.themes.register("otacon", otacon_theme)
alt.themes.enable("otacon")
