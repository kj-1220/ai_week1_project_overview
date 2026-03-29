"""Page 5: Payments and Accounts Receivable"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, _tbl, style_fig, governance_sidebar, COLORS, REGION_COLORS
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.markdown("## Payments and AR")
st.caption("Days to pay, late rates, regional patterns | Clean views")

# ── KPIs ──
payments = q(f"SELECT COUNT(*) as v FROM {_tbl('v_payments_clean')}").v[0]
collected = q(f"SELECT SUM(amount) as v FROM {_tbl('v_payments_clean')}").v[0]
avg_dtp = q(f"SELECT AVG(days_to_pay) as v FROM {_tbl('v_payments_clean')}").v[0]
late_pct = q(f"SELECT AVG(is_late)*100 as v FROM {_tbl('v_payments_clean')}").v[0]
invoices = q(f"SELECT COUNT(*) as v FROM {_tbl('v_invoices_clean')}").v[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Payments", f"{payments:,}")
c2.metric("Collected", f"${collected/1e6:.1f}M")
c3.metric("Avg Days to Pay", f"{avg_dtp:.1f}")
c4.metric("Late Rate", f"{late_pct:.1f}%")
c5.metric("Invoices", f"{invoices:,}")

st.divider()

# ── 1. Days to pay trend ──
dtp = q(f"""
    SELECT FORMAT_DATE('%Y-%m', SAFE_CAST(payment_date AS DATE)) as month,
           AVG(days_to_pay) as avg_days,
           ROUND(AVG(is_late)*100, 1) as late_pct,
           SUM(amount) as collected
    FROM {_tbl('v_payments_clean')} GROUP BY month ORDER BY month
""")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.55, 0.45],
                    vertical_spacing=0.08)
fig.add_trace(go.Scatter(x=dtp.month, y=dtp.avg_days, mode="lines",
                         line=dict(color=COLORS["blue"], width=2), name="Avg Days"),
              row=1, col=1)
fig.add_trace(go.Bar(x=dtp.month, y=dtp.late_pct, name="Late %",
                     marker_color=COLORS["red"], opacity=0.6), row=2, col=1)
style_fig(fig, height=450, title_text="Days to Pay and Late Payment Rate")
fig.update_xaxes(dtick=3)
fig.update_yaxes(title_text="Days", row=1, col=1)
fig.update_yaxes(title_text="Late %", row=2, col=1)
fig.update_layout(showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ── 2 & 3. Regional breakdown and segment terms ──
col1, col2 = st.columns(2)

with col1:
    eu = q(f"""
        SELECT CASE WHEN EXTRACT(YEAR FROM SAFE_CAST(p.payment_date AS DATE)) = 2023
                    AND EXTRACT(MONTH FROM SAFE_CAST(p.payment_date AS DATE)) BETWEEN 7 AND 9
                    THEN 'Q3 2023' ELSE 'Other' END as period,
               c.region, AVG(p.days_to_pay) as avg_days
        FROM {_tbl('v_payments_clean')} p
        JOIN {_tbl('invoices')} i ON p.invoice_id = i.invoice_id
        JOIN {_tbl('v_customers_clean')} c ON i.customer_id = c.customer_id
        GROUP BY period, c.region ORDER BY period, c.region
    """)
    fig = px.bar(eu, x="region", y="avg_days", color="period", barmode="group",
                 color_discrete_map={"Q3 2023": COLORS["red"], "Other": COLORS["light_gray"]})
    style_fig(fig, height=360, title_text="Days to Pay: Q3 2023 vs Baseline")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    seg = q(f"""
        SELECT c.segment, AVG(p.days_to_pay) as avg_days,
               ROUND(AVG(p.is_late)*100, 1) as late_pct, COUNT(*) as n
        FROM {_tbl('v_payments_clean')} p
        JOIN {_tbl('invoices')} i ON p.invoice_id = i.invoice_id
        JOIN {_tbl('v_customers_clean')} c ON i.customer_id = c.customer_id
        GROUP BY c.segment
    """)
    terms = {"enterprise": 60, "mid_market": 45, "smb": 30}
    seg["terms"] = seg.segment.map(terms)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=seg.segment, y=seg.avg_days, name="Actual",
                         marker_color=COLORS["blue"], text=seg.avg_days.round(1),
                         textposition="outside"))
    fig.add_trace(go.Bar(x=seg.segment, y=seg.terms, name="Terms",
                         marker_color=COLORS["light_gray"], text=seg.terms,
                         textposition="outside"))
    style_fig(fig, height=360, title_text="Actual vs Payment Terms by Segment", barmode="group")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 4. Days to pay distribution ──
col1, col2 = st.columns(2)

with col1:
    dist = q(f"SELECT days_to_pay FROM {_tbl('v_payments_clean')} WHERE days_to_pay > 0 AND days_to_pay < 120")
    fig = px.histogram(dist, x="days_to_pay", nbins=90, color_discrete_sequence=[COLORS["blue"]])
    fig.add_vline(x=30, line_dash="dash", line_color=COLORS["green"], annotation_text="Net 30")
    fig.add_vline(x=45, line_dash="dash", line_color=COLORS["orange"], annotation_text="Net 45")
    fig.add_vline(x=60, line_dash="dash", line_color=COLORS["red"], annotation_text="Net 60")
    style_fig(fig, height=360, title_text="Days to Pay Distribution")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # ── 5. Payment methods ──
    methods = q(f"""
        SELECT method, COUNT(*) as n, AVG(days_to_pay) as avg_days
        FROM {_tbl('v_payments_clean')} GROUP BY method ORDER BY n DESC
    """)
    fig = px.bar(methods, x="method", y="n", color="avg_days",
                 color_continuous_scale="Blues")
    style_fig(fig, height=360, title_text="Payment Volume by Method")
    fig.update_traces(texttemplate="%{y:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# ── 6 & 7. Quarterly trend and invoice status ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    qtr = q(f"""
        SELECT CONCAT(CAST(EXTRACT(YEAR FROM SAFE_CAST(payment_date AS DATE)) AS STRING), '-Q',
                      CAST(EXTRACT(QUARTER FROM SAFE_CAST(payment_date AS DATE)) AS STRING)) as quarter,
               AVG(days_to_pay) as avg_days,
               ROUND(AVG(is_late)*100, 1) as late_pct
        FROM {_tbl('v_payments_clean')} GROUP BY quarter ORDER BY quarter
    """)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=qtr.quarter, y=qtr.avg_days, name="Days",
                             mode="lines+markers", line=dict(color=COLORS["blue"], width=2)),
                  secondary_y=False)
    fig.add_trace(go.Bar(x=qtr.quarter, y=qtr.late_pct, name="Late %",
                         marker_color=COLORS["red"], opacity=0.3),
                  secondary_y=True)
    style_fig(fig, height=350, title_text="Quarterly AR Trend")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    inv = q(f"""
        SELECT status, CAST(EXTRACT(YEAR FROM SAFE_CAST(invoice_date AS DATE)) AS STRING) as year, COUNT(*) as n
        FROM {_tbl('v_invoices_clean')} GROUP BY status, year ORDER BY year
    """)
    fig = px.bar(inv, x="year", y="n", color="status", barmode="stack",
                 color_discrete_sequence=[COLORS["blue"], COLORS["green"],
                                           COLORS["orange"], COLORS["red"]])
    style_fig(fig, height=350, title_text="Invoice Status by Year")
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("payments", "v_payments_clean", ["payments"])
