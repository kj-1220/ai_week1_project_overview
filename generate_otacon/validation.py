"""
validation.py — Calibration benchmark validation and reporting.
"""

from config import MONTHLY_MULTIPLIERS, STORYLINES


def validate(conn):
    """Print calibration benchmark validation report."""
    print("\n" + "=" * 65)
    print("  CALIBRATION BENCHMARK VALIDATION")
    print("=" * 65)
    c = conn.cursor()

    # ── Row Counts ──
    tables = [
        "customers", "products", "orders", "order_items", "returns",
        "saas_customers", "mrr_movements", "support_tickets",
        "saas_users", "usage_events", "feature_adoption",
        "invoices", "payments",
        "accounts", "activities", "opportunities",
        "customer_xref", "customer_360"
    ]
    print("\n  TABLE ROW COUNTS:")
    for t in tables:
        count = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"    {t:25s} {count:>10,}")

    # ── Monthly Multipliers ──
    print("\n  E-COMMERCE MONTHLY MULTIPLIERS (vs baseline avg):")
    monthly = c.execute("""
        SELECT strftime('%m', order_date) as month, SUM(total_amount)
        FROM orders WHERE status='completed' GROUP BY month ORDER BY month
    """).fetchall()
    if monthly:
        avg = sum(r[1] for r in monthly) / len(monthly)
        for ms, rev in monthly:
            mult = rev / avg
            target = MONTHLY_MULTIPLIERS.get(int(ms), 1.0)
            flag = " \u2713" if abs(mult - target) < 0.15 else " \u2190"
            print(f"    Month {ms}: {mult:.2f}x (target: {target:.2f}x){flag}")

    # ── YoY Growth ──
    for y1, y2 in [(2023, 2024), (2024, 2025)]:
        r1 = c.execute(f"SELECT SUM(total_amount) FROM orders WHERE strftime('%Y', order_date)='{y1}' AND status='completed'").fetchone()[0] or 0
        r2 = c.execute(f"SELECT SUM(total_amount) FROM orders WHERE strftime('%Y', order_date)='{y2}' AND status='completed'").fetchone()[0] or 0
        if r1 > 0:
            yoy = (r2 - r1) / r1 * 100
            print(f"\n  YoY REVENUE GROWTH {y1}\u2192{y2}: {yoy:.1f}% (target: ~8%)")

    # ── January Returns ──
    jan_orders = c.execute("SELECT COUNT(*) FROM orders WHERE strftime('%m', order_date)='01' AND status='completed'").fetchone()[0]
    jan_returns = c.execute("SELECT COUNT(*) FROM returns r JOIN orders o ON r.order_id=o.order_id WHERE strftime('%m', o.order_date)='01'").fetchone()[0]
    total_orders = c.execute("SELECT COUNT(*) FROM orders WHERE status='completed'").fetchone()[0]
    total_returns = c.execute("SELECT COUNT(*) FROM returns").fetchone()[0]
    n_months = 36  # 3 years
    if total_returns > 0 and total_orders > 0:
        jan_rate = jan_returns / max(jan_orders, 1)
        avg_rate = (total_returns / n_months) / (total_orders / n_months)
        spike = (jan_rate - avg_rate) / avg_rate * 100 if avg_rate > 0 else 0
        print(f"  JANUARY RETURN SPIKE: {spike:.1f}% above baseline (target: ~17%)")

    # ── SaaS Churn ──
    churned = c.execute("SELECT COUNT(*) FROM saas_customers WHERE status='churned' AND plan_tier != 'free'").fetchone()[0]
    paid = c.execute("SELECT COUNT(*) FROM saas_customers WHERE plan_tier != 'free'").fetchone()[0]
    if paid > 0:
        monthly_churn = churned / (paid * 18) * 100  # ~18 avg months active
        print(f"\n  SAAS MONTHLY CHURN: ~{monthly_churn:.1f}% (target: ~2.5%)")

    # ── NRR ──
    beginning = c.execute("SELECT COALESCE(SUM(new_mrr), 0) FROM mrr_movements WHERE movement_type='new' AND movement_date < '2024-01-01'").fetchone()[0]
    expansion = c.execute("SELECT COALESCE(SUM(amount), 0) FROM mrr_movements WHERE movement_type='expansion' AND movement_date >= '2024-01-01' AND movement_date <= '2024-12-31'").fetchone()[0]
    contraction = c.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM mrr_movements WHERE movement_type='contraction' AND movement_date >= '2024-01-01' AND movement_date <= '2024-12-31'").fetchone()[0]
    churn_mrr = c.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM mrr_movements WHERE movement_type='churn' AND movement_date >= '2024-01-01' AND movement_date <= '2024-12-31'").fetchone()[0]
    if beginning > 0:
        nrr = (beginning + expansion - contraction - churn_mrr) / beginning * 100
        print(f"  NRR (2024 cohort): {nrr:.0f}% (target: ~104%)")

    # ── Churn Clustering ──
    print("\n  CHURN BY MONTHS ACTIVE (clustering at 11-13, 23-25):")
    churn_months = c.execute("""
        SELECT CAST((julianday(m.movement_date) - julianday(sc.signup_date)) / 30 AS INTEGER) as months_active, COUNT(*)
        FROM mrr_movements m JOIN saas_customers sc ON m.saas_customer_id = sc.saas_customer_id
        WHERE m.movement_type = 'churn' GROUP BY months_active ORDER BY months_active
    """).fetchall()
    for ma, cnt in churn_months:
        bar = "\u2588" * min(cnt, 40)
        flag = " \u2190 CLUSTER" if ma in [11, 12, 13, 23, 24, 25] else ""
        print(f"    Month {ma:2d}: {cnt:3d} {bar}{flag}")

    # ── European Payment Delays ──
    print("\n  EUROPEAN PAYMENT DELAYS (Q3 2023 vs baseline):")
    eu_q3 = c.execute("""
        SELECT AVG(p.days_to_pay) FROM payments p JOIN invoices i ON p.invoice_id = i.invoice_id
        JOIN orders o ON i.order_id = o.order_id
        WHERE o.region='Europe' AND strftime('%Y', o.order_date)='2023'
        AND CAST(strftime('%m', o.order_date) AS INTEGER) BETWEEN 7 AND 9
    """).fetchone()[0]
    eu_base = c.execute("""
        SELECT AVG(p.days_to_pay) FROM payments p JOIN invoices i ON p.invoice_id = i.invoice_id
        JOIN orders o ON i.order_id = o.order_id
        WHERE o.region='Europe' AND NOT (strftime('%Y', o.order_date)='2023'
        AND CAST(strftime('%m', o.order_date) AS INTEGER) BETWEEN 7 AND 9)
    """).fetchone()[0]
    if eu_q3 and eu_base:
        print(f"    Europe Q3 2023: {eu_q3:.1f} days (baseline: {eu_base:.1f}, delta: +{eu_q3-eu_base:.1f})")

    # ── Q2 2025 Tariff Impact ──
    print("\n  Q2 2025 TARIFF VOLATILITY:")
    q2_rev = c.execute("SELECT SUM(total_amount) FROM orders WHERE strftime('%Y', order_date)='2025' AND CAST(strftime('%m', order_date) AS INTEGER) BETWEEN 4 AND 6 AND status='completed'").fetchone()[0] or 0
    q1_rev = c.execute("SELECT SUM(total_amount) FROM orders WHERE strftime('%Y', order_date)='2025' AND CAST(strftime('%m', order_date) AS INTEGER) BETWEEN 1 AND 3 AND status='completed'").fetchone()[0] or 0
    if q1_rev > 0:
        dip = (q2_rev - q1_rev) / q1_rev * 100
        print(f"    Q2 vs Q1 2025 revenue: {dip:+.1f}% (target: ~-10 to -15%)")

    q2_dtp = c.execute("""
        SELECT AVG(p.days_to_pay) FROM payments p JOIN invoices i ON p.invoice_id = i.invoice_id
        JOIN orders o ON i.order_id = o.order_id
        WHERE strftime('%Y', o.order_date)='2025' AND CAST(strftime('%m', o.order_date) AS INTEGER) BETWEEN 4 AND 6
    """).fetchone()[0]
    baseline_dtp = c.execute("""
        SELECT AVG(p.days_to_pay) FROM payments p JOIN invoices i ON p.invoice_id = i.invoice_id
        JOIN orders o ON i.order_id = o.order_id
        WHERE strftime('%Y', o.order_date)='2024' AND CAST(strftime('%m', o.order_date) AS INTEGER) BETWEEN 4 AND 6
    """).fetchone()[0]
    if q2_dtp and baseline_dtp:
        print(f"    Q2 2025 avg days-to-pay: {q2_dtp:.1f} (Q2 2024 baseline: {baseline_dtp:.1f}, delta: +{q2_dtp-baseline_dtp:.1f})")

    # ── Q4 2025 AI Launch ──
    print("\n  Q4 2025 AI INSIGHTS LAUNCH:")
    ai_events = c.execute("SELECT COUNT(*) FROM usage_events WHERE feature_module = 'ai_insights'").fetchone()[0]
    ai_accounts = c.execute("SELECT COUNT(DISTINCT saas_customer_id) FROM usage_events WHERE feature_module = 'ai_insights'").fetchone()[0]
    total_active = c.execute("SELECT COUNT(*) FROM saas_customers WHERE status='active'").fetchone()[0]
    print(f"    AI Insights events: {ai_events:,}")
    print(f"    Accounts using AI Insights: {ai_accounts} / {total_active} active ({ai_accounts/max(total_active,1)*100:.0f}%)")

    # ── Product Analytics ──
    print("\n  PRODUCT ANALYTICS:")
    events = c.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0]
    users = c.execute("SELECT COUNT(*) FROM saas_users").fetchone()[0]
    print(f"    Total events: {events:,}")
    print(f"    Total users: {users:,}")

    power = c.execute("SELECT user_id, COUNT(*) as events FROM usage_events GROUP BY user_id ORDER BY events DESC").fetchall()
    if power:
        top20 = int(len(power) * 0.20)
        top20_events = sum(r[1] for r in power[:top20])
        all_events = sum(r[1] for r in power)
        ratio = top20_events / all_events * 100 if all_events > 0 else 0
        print(f"    Top 20% users generate {ratio:.0f}% of events (target: ~60%+)")

    # ── Storyline Summary ──
    print("\n  ENGINEERED STORYLINES:")
    for key, story in STORYLINES.items():
        print(f"    {key}: {story['description']}")

    print("\n" + "=" * 65)
    print("  GENERATION COMPLETE \u2014 otacon.db ready")
    print("=" * 65)
