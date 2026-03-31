"""Page 5: Payments and Accounts Receivable"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import q, governance_sidebar, BLUE, GREEN, RED, ORANGE, GRAY, LIGHT_GRAY
import altair as alt

st.markdown("## Payments and AR")
st.caption("Days to pay, late rates, regional patterns | Clean views")

# ── KPIs ──
kpis = q("""
    SELECT
        (SELECT COUNT(*) FROM v_payments_clean) as payments,
        (SELECT SUM(amount) FROM v_payments_clean) as collected,
        (SELECT AVG(days_to_pay) FROM v_payments_clean) as avg_dtp,
        (SELECT AVG(is_late)*100 FROM v_payments_clean) as late_pct,
        (SELECT COUNT(*) FROM v_invoices_clean) as invoices
""")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Payments", f"{kpis.payments[0]:,}")
c2.metric("Collected", f"${kpis.collected[0]/1e6:.1f}M")
c3.metric("Avg Days to Pay", f"{kpis.avg_dtp[0]:.1f}")
c4.metric("Late Rate", f"{kpis.late_pct[0]:.1f}%")
c5.metric("Invoices", f"{kpis.invoices[0]:,}")

st.divider()

# ── 1. Days to pay trend ──
dtp = q("""
    SELECT strftime('%Y-%m', payment_date) as month,
           AVG(days_to_pay) as avg_days,
           ROUND(AVG(is_late)*100, 1) as late_pct
    FROM v_payments_clean GROUP BY month ORDER BY month
""")

base = alt.Chart(dtp).encode(x=alt.X("month:O", title=None, axis=alt.Axis(labelAngle=-45, values=dtp.month.tolist()[::3])))
line = base.mark_line(color=BLUE, strokeWidth=2).encode(y=alt.Y("avg_days:Q", title="Avg Days to Pay"))
bars = base.mark_bar(color=RED, opacity=0.4).encode(y=alt.Y("late_pct:Q", title="Late %"))
chart = alt.layer(line, bars).resolve_scale(y="independent").properties(title="Days to Pay and Late Payment Rate", height=420)
st.altair_chart(chart, use_container_width=True)

# ── 2 & 3. Regional breakdown and segment terms ──
col1, col2 = st.columns(2)

with col1:
    eu = q("""
        SELECT CASE WHEN CAST(strftime('%Y', p.payment_date) AS INTEGER) = 2023
                    AND CAST(strftime('%m', p.payment_date) AS INTEGER) BETWEEN 7 AND 9
                    THEN 'Q3 2023' ELSE 'Other' END as period,
               c.region, AVG(p.days_to_pay) as avg_days
        FROM v_payments_clean p
        JOIN invoices i ON p.invoice_id = i.invoice_id
        JOIN v_customers_clean c ON i.customer_id = c.customer_id
        GROUP BY period, c.region ORDER BY period, c.region
    """)
    chart = alt.Chart(eu).mark_bar().encode(
        x=alt.X("region:N", title=None),
        y=alt.Y("avg_days:Q", title="Avg Days to Pay"),
        color=alt.Color("period:N", scale=alt.Scale(domain=["Q3 2023","Other"], range=[RED, LIGHT_GRAY])),
        xOffset="period:N"
    ).properties(title="Days to Pay: Q3 2023 vs Baseline", height=340)
    st.altair_chart(chart, use_container_width=True)

with col2:
    seg = q("""
        SELECT c.segment, ROUND(AVG(p.days_to_pay), 1) as avg_days
        FROM v_payments_clean p
        JOIN invoices i ON p.invoice_id = i.invoice_id
        JOIN v_customers_clean c ON i.customer_id = c.customer_id
        GROUP BY c.segment
    """)
    import pandas as pd
    terms_df = pd.DataFrame({"segment": ["enterprise","mid_market","smb"], "terms": [60, 45, 30]})
    seg = seg.merge(terms_df, on="segment")
    melted = pd.melt(seg, id_vars=["segment"], value_vars=["avg_days","terms"], var_name="type", value_name="days")

    chart = alt.Chart(melted).mark_bar().encode(
        x=alt.X("segment:N", title=None),
        y=alt.Y("days:Q", title="Days"),
        color=alt.Color("type:N", scale=alt.Scale(domain=["avg_days","terms"], range=[BLUE, LIGHT_GRAY])),
        xOffset="type:N"
    ).properties(title="Actual vs Payment Terms by Segment", height=340)
    st.altair_chart(chart, use_container_width=True)

st.divider()

# ── 4 & 5. Distribution and methods ──
col1, col2 = st.columns(2)

with col1:
    dist = q("SELECT days_to_pay FROM v_payments_clean WHERE days_to_pay > 0 AND days_to_pay < 120")
    chart = alt.Chart(dist).mark_bar(color=BLUE).encode(
        x=alt.X("days_to_pay:Q", bin=alt.Bin(maxbins=90), title="Days to Pay"),
        y=alt.Y("count()", title="Payments")
    ).properties(title="Days to Pay Distribution", height=340)

    rules = alt.Chart(pd.DataFrame({"x": [30, 45, 60], "label": ["Net 30","Net 45","Net 60"],
                                     "c": [GREEN, ORANGE, RED]})).mark_rule(strokeDash=[4,4]).encode(
        x="x:Q", color=alt.Color("c:N", scale=None)
    )
    st.altair_chart(chart + rules, use_container_width=True)

with col2:
    methods = q("""
        SELECT method, COUNT(*) as n, AVG(days_to_pay) as avg_days
        FROM v_payments_clean GROUP BY method ORDER BY n DESC
    """)
    chart = alt.Chart(methods).mark_bar().encode(
        x=alt.X("method:N", title=None, sort="-y"),
        y=alt.Y("n:Q", title="Count"),
        color=alt.Color("avg_days:Q", scale=alt.Scale(scheme="blues"), title="Avg Days")
    ).properties(title="Payment Volume by Method", height=340)
    st.altair_chart(chart, use_container_width=True)

# ── 6 & 7. Quarterly trend and invoice status ──
st.divider()
col1, col2 = st.columns(2)

with col1:
    qtr = q("""
        SELECT strftime('%Y', payment_date) || '-Q' || ((CAST(strftime('%m', payment_date) AS INTEGER) - 1) / 3 + 1) as quarter,
               AVG(days_to_pay) as avg_days,
               ROUND(AVG(is_late)*100, 1) as late_pct
        FROM v_payments_clean GROUP BY quarter ORDER BY quarter
    """)
    base = alt.Chart(qtr).encode(x=alt.X("quarter:O", title=None))
    line = base.mark_line(color=BLUE, strokeWidth=2, point=True).encode(y=alt.Y("avg_days:Q", title="Days"))
    bars = base.mark_bar(color=RED, opacity=0.3).encode(y=alt.Y("late_pct:Q", title="Late %"))
    chart = alt.layer(line, bars).resolve_scale(y="independent").properties(title="Quarterly AR Trend", height=330)
    st.altair_chart(chart, use_container_width=True)

with col2:
    inv = q("""
        SELECT status, strftime('%Y', invoice_date) as year, COUNT(*) as n
        FROM v_invoices_clean GROUP BY status, year ORDER BY year
    """)
    chart = alt.Chart(inv).mark_bar().encode(
        x=alt.X("year:O", title=None),
        y=alt.Y("n:Q", title="Count", stack=True),
        color="status:N"
    ).properties(title="Invoice Status by Year", height=330)
    st.altair_chart(chart, use_container_width=True)

governance_sidebar("payments", "v_payments_clean", ["payments"])
