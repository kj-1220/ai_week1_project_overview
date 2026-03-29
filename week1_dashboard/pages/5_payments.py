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

# ── Query 1: All payments ──
payments = q("""
    SELECT payment_date,
           strftime('%Y-%m', payment_date) as month,
           strftime('%Y', payment_date) || '-Q' || ((CAST(strftime('%m', payment_date) AS INTEGER) - 1) / 3 + 1) as quarter,
           amount, days_to_pay, is_late, method, invoice_id
    FROM v_payments_clean
""")

total_payments = len(payments)
collected = payments.amount.sum()
avg_dtp = payments.days_to_pay.mean()
late_pct = payments.is_late.mean() * 100
invoices = q("SELECT COUNT(*) as v FROM v_invoices_clean").v[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Payments", f"{total_payments:,}")
c2.metric("Collected", f"${collected/1e6:.1f}M")
c3.metric("Avg Days to Pay", f"{avg_dtp:.1f}")
c4.metric("Late Rate", f"{late_pct:.1f}%")
c5.metric("Invoices", f"{invoices:,}")

st.divider()

# ── 1. Days to pay trend ──
dtp = payments.groupby("month", as_index=False).agg(
    avg_days=("days_to_pay", "mean"),
    late_pct_mo=("is_late", lambda x: round(x.mean() * 100, 1)),
    collected_mo=("amount", "sum")
)

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.55, 0.45],
                    vertical_spacing=0.08)
fig.add_trace(go.Scatter(x=dtp.month, y=dtp.avg_days, mode="lines",
                         line=dict(color=COLORS["blue"], width=2), name="Avg Days"),
              row=1, col=1)
fig.add_trace(go.Bar(x=dtp.month, y=dtp.late_pct_mo, name="Late %",
                     marker_color=COLORS["red"], opacity=0.6), row=2, col=1)
style_fig(fig, height=450, title_text="Days to Pay and Late Payment Rate")
fig.update_xaxes(dtick=3)
fig.update_yaxes(title_text="Days", row=1, col=1)
fig.update_yaxes(title_text="Late %", row=2, col=1)
fig.update_layout(showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ── Query 2: Payments joined with customers ──
col1, col2 = st.columns(2)

pay_cust = q("""
    SELECT p.payment_date, p.days_to_pay, p.is_late,
           CAST(strftime('%Y', p.payment_date) AS INTEGER) as yr,
           CAST(strftime('%m', p.payment_date) AS INTEGER) as mo,
           c.region, c.segment
    FROM v_payments_clean p
    JOIN invoices i ON p.invoice_id = i.invoice_id
    JOIN v_customers_clean c ON i.customer_id = c.customer_id
""")

with col1:
    pay_cust["period"] = pay_cust.apply(
        lambda r: "Q3 2023" if (r.yr == 2023 and r.mo in (7, 8, 9)) else "Other", axis=1
    )
    eu = pay_cust.groupby(["period", "region"], as_index=False).agg(avg_days=("days_to_pay", "mean"))
    fig = px.bar(eu, x="region", y="avg_days", color="period", barmode="group",
                 color_discrete_map={"Q3 2023": COLORS["red"], "Other": COLORS["light_gray"]})
    style_fig(fig, height=360, title_text="Days to Pay: Q3 2023 vs Baseline")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    seg = pay_cust.groupby("segment", as_index=False).agg(
        avg_days=("days_to_pay", "mean"),
        late_pct_seg=("is_late", lambda x: round(x.mean() * 100, 1)),
        n=("days_to_pay", "count")
    )
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

# ── 4 & 5. Distribution and methods ──
col1, col2 = st.columns(2)

with col1:
    dist = payments[(payments.days_to_pay > 0) & (payments.days_to_pay < 120)]
    fig = px.histogram(dist, x="days_to_pay", nbins=90, color_discrete_sequence=[COLORS["blue"]])
    fig.add_vline(x=30, line_dash="dash", line_color=COLORS["green"], annotation_text="Net 30")
    fig.add_vline(x=45, line_dash="dash", line_color=COLORS["orange"], annotation_text="Net 45")
    fig.add_vline(x=60, line_dash="dash", line_color=COLORS["red"], annotation_text="Net 60")
    style_fig(fig, height=360, title_text="Days to Pay Distribution")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    methods = payments.groupby("method", as_index=False).agg(
        n=("method", "count"),
        avg_days=("days_to_pay", "mean")
    ).sort_values("n", ascending=False)
    fig = px.bar(methods, x="method", y="n", color="avg_days",
                 color_continuous_scale="Blues")
    style_fig(fig, height=360, title_text="Payment Volume by Method")
    fig.update_traces(texttemplate="%{y:,}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# ── 6 & 7. Quarterly trend and invoice status ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    qtr = payments.groupby("quarter", as_index=False).agg(
        avg_days=("days_to_pay", "mean"),
        late_pct_q=("is_late", lambda x: round(x.mean() * 100, 1))
    )
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=qtr.quarter, y=qtr.avg_days, name="Days",
                             mode="lines+markers", line=dict(color=COLORS["blue"], width=2)),
                  secondary_y=False)
    fig.add_trace(go.Bar(x=qtr.quarter, y=qtr.late_pct_q, name="Late %",
                         marker_color=COLORS["red"], opacity=0.3),
                  secondary_y=True)
    style_fig(fig, height=350, title_text="Quarterly AR Trend")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    inv = q("""
        SELECT status,
               strftime('%Y', invoice_date) as year,
               COUNT(*) as n
        FROM v_invoices_clean GROUP BY status, year ORDER BY year
    """)
    fig = px.bar(inv, x="year", y="n", color="status", barmode="stack",
                 color_discrete_sequence=[COLORS["blue"], COLORS["green"],
                                          COLORS["orange"], COLORS["red"]])
    style_fig(fig, height=350, title_text="Invoice Status by Year")
    st.plotly_chart(fig, use_container_width=True)

governance_sidebar("payments", "v_payments_clean", ["payments"])
