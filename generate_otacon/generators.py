"""
generators.py — Data generation functions for all five layers + bridge.
Each layer has its own section. Functions are called in order by main.py.
"""

import random
import datetime
import math
from collections import defaultdict

from config import (
    fake, START_DATE, END_DATE, REGIONS, REGION_WEIGHTS, SEGMENTS, SEGMENT_WEIGHTS,
    INDUSTRIES, INDUSTRY_WEIGHTS, CUSTOMER_TYPES, CUSTOMER_TYPE_WEIGHTS,
    CHANNELS, CHANNEL_WEIGHTS, REVENUE_TIERS, REVENUE_TIER_WEIGHTS,
    PRODUCT_CATEGORIES, CATEGORY_WEIGHTS, MONTHLY_MULTIPLIERS, YOY_GROWTH,
    ORDERS_PER_MONTH_BASE, PLAN_TIERS, PLAN_WEIGHTS, PLAN_MRR, PLAN_USER_RANGE,
    FEATURE_MODULES, AI_INSIGHTS_MODULE, AI_INSIGHTS_LAUNCH,
    EVENT_TYPES, AI_EVENT_TYPES, EVENTS_PER_MONTH,
    SALES_REPS, PAYMENT_TERMS,
    is_in_storyline, get_storyline_param, STORYLINES,
)
from helpers import random_date, weighted_choice, make_session_id, clamp


# ═══════════════════════════════════════════════════════════════
# LAYER 1: E-COMMERCE
# ═══════════════════════════════════════════════════════════════

def generate_customers(conn, n=8000):
    print("  Generating customers...")
    rows = []
    acq_start = datetime.date(2020, 1, 1)

    for i in range(n):
        ctype = weighted_choice(CUSTOMER_TYPES, CUSTOMER_TYPE_WEIGHTS)
        region = weighted_choice(REGIONS, REGION_WEIGHTS)
        segment = weighted_choice(SEGMENTS, SEGMENT_WEIGHTS)
        acq_date = random_date(acq_start, END_DATE)

        # Slower H1 2023 new customer growth
        if acq_date.year == 2023 and acq_date.month <= 6:
            if random.random() < 0.30:
                acq_date = random_date(acq_start, datetime.date(2022, 12, 31))

        rows.append((
            fake.company(), ctype, region, segment,
            weighted_choice(INDUSTRIES, INDUSTRY_WEIGHTS),
            acq_date.isoformat(),
            weighted_choice(CHANNELS, CHANNEL_WEIGHTS),
            "active" if random.random() < 0.88 else random.choice(["churned", "suspended"]),
            weighted_choice(REVENUE_TIERS, REVENUE_TIER_WEIGHTS),
        ))

    conn.executemany("""
        INSERT INTO customers (company_name, customer_type, region, segment, industry,
                               acquisition_date, acquisition_channel, status, annual_revenue_tier)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    print(f"    {len(rows)} customers created.")


def generate_products(conn, n=500):
    print("  Generating products...")
    rows = []
    categories = list(PRODUCT_CATEGORIES.keys())

    for i in range(n):
        cat = weighted_choice(categories, CATEGORY_WEIGHTS)
        subcat = random.choice(PRODUCT_CATEGORIES[cat])
        price_ranges = {
            "hardware": (200, 15000), "software": (50, 5000),
            "accessories": (10, 500), "services": (500, 20000), "consumables": (5, 200),
        }
        lo, hi = price_ranges[cat]
        price = round(random.uniform(lo, hi), 2)
        margin = random.uniform(0.20, 0.60)
        cost = round(price * (1 - margin), 2)
        launch = random_date(datetime.date(2019, 1, 1), datetime.date(2024, 6, 30))
        status = "discontinued" if launch < datetime.date(2021, 1, 1) and random.random() < 0.15 else "active"
        adj = random.choice(["Pro", "Elite", "Core", "Max", "Plus", "Ultra", "Edge", "Prime", "Flex", "Swift"])
        name = f"{subcat.replace('_', ' ').title()} {adj} {random.randint(100, 9999)}"
        rows.append((name, cat, subcat, price, cost, launch.isoformat(), status))

    conn.executemany("""
        INSERT INTO products (product_name, category, subcategory, unit_price, cost, launch_date, status)
        VALUES (?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    print(f"    {len(rows)} products created.")


def generate_orders_and_items(conn):
    print("  Generating orders and line items...")
    customers = conn.execute("SELECT customer_id, customer_type, region, segment FROM customers").fetchall()
    products = conn.execute("SELECT product_id, unit_price, category FROM products WHERE status='active'").fetchall()

    order_rows, item_rows = [], []
    order_id_counter = 0
    total_items = 0

    for year in [2023, 2024, 2025]:
        growth = YOY_GROWTH.get(year, 1.0)
        # Compound growth: 2024 = base*1.08, 2025 = base*1.08*1.08
        if year == 2025:
            base = int(ORDERS_PER_MONTH_BASE * YOY_GROWTH[2024] * YOY_GROWTH[2025])
        elif year == 2024:
            base = int(ORDERS_PER_MONTH_BASE * YOY_GROWTH[2024])
        else:
            base = ORDERS_PER_MONTH_BASE

        for month in range(1, 13):
            d = datetime.date(year, month, 1)
            multiplier = MONTHLY_MULTIPLIERS[month]

            # Storyline adjustments
            if is_in_storyline(d, "q2_2025_tariff_volatility"):
                multiplier *= get_storyline_param("q2_2025_tariff_volatility", "ecommerce_multiplier", 1.0)
            if is_in_storyline(d, "q3_2025_stabilization"):
                multiplier *= get_storyline_param("q3_2025_stabilization", "ecommerce_multiplier", 1.0)
            if is_in_storyline(d, "q4_2025_ai_launch") and month == 11:
                multiplier *= get_storyline_param("q4_2025_ai_launch", "november_muting", 1.0)

            n_orders = int(base * multiplier * random.uniform(0.92, 1.08))

            for _ in range(n_orders):
                cust = random.choice(customers)
                cust_id, cust_type, region, segment = cust
                order_date = datetime.date(year, month, random.randint(1, 28))
                ship_date = order_date + datetime.timedelta(days=random.randint(1, 7))
                disc_ranges = {"enterprise": (0.10, 0.25), "mid_market": (0.05, 0.15), "smb": (0, 0.08)}
                disc_pct = round(random.uniform(*disc_ranges[segment]), 2)

                n_items = random.choices(
                    [1,2,3,4,5,6,7,8],
                    weights=[5,10,20,25,20,10,5,5] if cust_type == "wholesale" else [30,40,20,10,0,0,0,0],
                    k=1
                )[0]

                order_total = 0
                order_id_counter += 1

                for _ in range(n_items):
                    prod = random.choice(products)
                    prod_id, base_price, prod_cat = prod

                    # Q2 2025 tariff: price increase on hardware/consumables
                    if is_in_storyline(order_date, "q2_2025_tariff_volatility"):
                        affected = get_storyline_param("q2_2025_tariff_volatility", "affected_categories", [])
                        if prod_cat in affected:
                            lo_inc, hi_inc = get_storyline_param("q2_2025_tariff_volatility", "price_increase_pct", (0, 0))
                            base_price = round(base_price * (1 + random.uniform(lo_inc, hi_inc)), 2)

                    qty = random.choices(range(1, 51), weights=[50-i for i in range(50)], k=1)[0] if cust_type == "wholesale" else random.randint(1, 5)
                    actual_price = round(base_price * (1 - disc_pct), 2)
                    line_total = round(actual_price * qty, 2)
                    order_total += line_total
                    total_items += 1
                    item_rows.append((order_id_counter, prod_id, qty, actual_price, line_total))

                status = "cancelled" if random.random() < 0.02 else ("processing" if random.random() < 0.03 else "completed")
                channel = weighted_choice(["online", "field_sales", "partner", "phone"], [0.40, 0.25, 0.20, 0.15])
                order_rows.append((cust_id, order_date.isoformat(), ship_date.isoformat(),
                                   status, channel, region, round(order_total, 2), disc_pct))

    conn.executemany("INSERT INTO orders (customer_id, order_date, ship_date, status, channel, region, total_amount, discount_pct) VALUES (?,?,?,?,?,?,?,?)", order_rows)
    conn.executemany("INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total) VALUES (?,?,?,?,?)", item_rows)
    conn.commit()
    print(f"    {len(order_rows)} orders, {total_items} line items created.")


def generate_returns(conn):
    print("  Generating returns...")
    completed = conn.execute("SELECT order_id, order_date, total_amount FROM orders WHERE status='completed'").fetchall()
    reasons = ["defective", "wrong_item", "not_as_described", "changed_mind", "late_delivery"]
    reason_wts = [0.25, 0.20, 0.20, 0.25, 0.10]
    rows = []

    for oid, od_str, amount in completed:
        od = datetime.date.fromisoformat(od_str)
        base_rate = 0.06
        rate = base_rate * (1.18 if od.month == 1 else (1.10 if od.month == 12 else random.uniform(0.85, 1.05)))

        # Q2 2025 tariff: higher return rate on wrong_item/changed_mind
        if is_in_storyline(od, "q2_2025_tariff_volatility"):
            rate *= 1.15

        if random.random() < rate:
            rd = od + datetime.timedelta(days=random.randint(7, 45))
            if rd > END_DATE:
                rd = END_DATE
            refund = amount if random.random() < 0.75 else round(amount * random.uniform(0.3, 0.8), 2)
            status = random.choices(["processed", "pending", "denied"], weights=[0.80, 0.15, 0.05], k=1)[0]
            rows.append((oid, rd.isoformat(), weighted_choice(reasons, reason_wts), refund, status))

    conn.executemany("INSERT INTO returns (order_id, return_date, reason, refund_amount, status) VALUES (?,?,?,?,?)", rows)
    conn.commit()
    print(f"    {len(rows)} returns created.")


# ═══════════════════════════════════════════════════════════════
# LAYER 2: SAAS
# ═══════════════════════════════════════════════════════════════

def generate_saas_customers(conn):
    print("  Generating SaaS customers...")
    wholesale = conn.execute("SELECT customer_id, acquisition_date FROM customers WHERE customer_type='wholesale'").fetchall()
    pool = random.sample(wholesale, min(2000, len(wholesale)))
    rows = []

    for cid, acq_str in pool:
        acq = datetime.date.fromisoformat(acq_str)
        signup = acq + datetime.timedelta(days=random.randint(0, 180))
        if signup < START_DATE:
            signup = START_DATE + datetime.timedelta(days=random.randint(0, 60))
        if signup > END_DATE:
            signup = random_date(START_DATE, END_DATE)
        plan = weighted_choice(PLAN_TIERS, PLAN_WEIGHTS)
        mrr = PLAN_MRR[plan]
        if plan == "enterprise":
            mrr = round(mrr * random.uniform(0.8, 2.5), 2)
        elif plan != "free":
            mrr = round(mrr * random.uniform(0.9, 1.3), 2)
        contract = 1 if plan == "free" else random.choice([1, 12, 24])
        rows.append((cid, plan, signup.isoformat(), contract, mrr, "active", 50))

    conn.executemany("INSERT INTO saas_customers (customer_id, plan_tier, signup_date, contract_months, mrr, status, usage_score) VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    print(f"    {len(rows)} SaaS customers created.")


def generate_mrr_movements(conn):
    print("  Generating MRR movements...")
    saas = conn.execute("SELECT saas_customer_id, customer_id, plan_tier, signup_date, contract_months, mrr FROM saas_customers").fetchall()
    rows = []
    churn_map = {}
    status_updates = []

    for sc_id, cid, plan, signup_str, contract, current_mrr in saas:
        if plan == "free":
            continue
        signup = datetime.date.fromisoformat(signup_str)
        months_active = 0
        mrr = current_mrr
        d = signup.replace(day=1)

        while d <= END_DATE:
            months_active += 1
            if months_active == 1:
                rows.append((sc_id, d.isoformat(), "new", mrr, 0, mrr))
                d = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
                continue

            # Churn probability — tuned to hit ~2.5% blended monthly churn
            if months_active <= 3:
                churn_prob = 0.0
            elif months_active in [11, 12, 13]:
                churn_prob = 0.075
            elif months_active in [23, 24, 25]:
                churn_prob = 0.085
            else:
                churn_prob = 0.020

            # Storyline churn adjustments
            if is_in_storyline(d, "q4_2023_holiday_churn"):
                churn_prob *= get_storyline_param("q4_2023_holiday_churn", "churn_multiplier", 1.0)
            if is_in_storyline(d, "q2_2024_enterprise_churn") and plan == "enterprise":
                churn_prob *= get_storyline_param("q2_2024_enterprise_churn", "enterprise_churn_multiplier", 1.0)
            if is_in_storyline(d, "q2_2025_tariff_volatility"):
                churn_prob *= get_storyline_param("q2_2025_tariff_volatility", "churn_multiplier", 1.0)
            if is_in_storyline(d, "q3_2025_stabilization"):
                churn_prob *= get_storyline_param("q3_2025_stabilization", "churn_multiplier", 1.0)

            # Q4 2025 AI launch reduces churn for adopters (simulated probabilistically)
            if is_in_storyline(d, "q4_2025_ai_launch"):
                adoption_rate = get_storyline_param("q4_2025_ai_launch",
                    f"ai_adoption_rate_month{d.month - 9}", 0.12)
                if random.random() < adoption_rate:
                    churn_prob *= get_storyline_param("q4_2025_ai_launch", "churn_reduction_adopters", 1.0)

            if random.random() < churn_prob:
                rows.append((sc_id, d.isoformat(), "churn", -mrr, mrr, 0))
                churn_map[sc_id] = d
                status_updates.append(("churned", max(0, int(15 * random.uniform(0.3, 1.0))), sc_id))
                break

            # Expansion — tuned to hit ~1.8% monthly expansion, ~104% NRR
            # Higher tiers expand more often and by larger amounts to offset churn dollars
            if plan == "enterprise":
                expansion_prob = 0.080
            elif plan == "pro":
                expansion_prob = 0.065
            else:
                expansion_prob = 0.045

            if is_in_storyline(d, "q3_2024_recovery"):
                expansion_prob += get_storyline_param("q3_2024_recovery", "expansion_boost", 0)
            if is_in_storyline(d, "q4_2025_ai_launch"):
                expansion_prob += 0.015

            if random.random() < expansion_prob:
                if plan == "enterprise":
                    amt = round(mrr * random.uniform(0.20, 0.40), 2)
                elif plan == "pro":
                    amt = round(mrr * random.uniform(0.15, 0.30), 2)
                else:
                    amt = round(mrr * random.uniform(0.10, 0.25), 2)
                old = mrr
                mrr = round(mrr + amt, 2)
                rows.append((sc_id, d.isoformat(), "expansion", amt, old, mrr))
            elif random.random() < 0.002:
                amt = round(mrr * random.uniform(0.05, 0.12), 2)
                old = mrr
                mrr = round(max(mrr - amt, PLAN_MRR.get(plan, 49)), 2)
                rows.append((sc_id, d.isoformat(), "contraction", -amt, old, mrr))

            d = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

        if sc_id not in churn_map:
            conn.execute("UPDATE saas_customers SET mrr = ? WHERE saas_customer_id = ?", (mrr, sc_id))

    conn.executemany("INSERT INTO mrr_movements (saas_customer_id, movement_date, movement_type, amount, previous_mrr, new_mrr) VALUES (?,?,?,?,?,?)", rows)
    for s, sc, sid in status_updates:
        conn.execute("UPDATE saas_customers SET status = ?, usage_score = ? WHERE saas_customer_id = ?", (s, sc, sid))
    conn.commit()
    print(f"    {len(rows)} MRR movements created.")
    return churn_map


def generate_support_tickets(conn, churn_map):
    print("  Generating support tickets...")
    saas_ids = [r[0] for r in conn.execute("SELECT saas_customer_id FROM saas_customers WHERE plan_tier != 'free'").fetchall()]
    categories = ["bug", "feature_request", "billing", "onboarding", "integration"]
    cat_wts = [0.30, 0.20, 0.15, 0.20, 0.15]
    priorities = ["low", "medium", "high", "critical"]
    rows = []

    for _ in range(6000):  # More tickets with 3 years
        sc_id = random.choice(saas_ids)
        created = random_date(START_DATE, END_DATE)

        # Storyline ticket spikes
        ticket_mult = 1.0
        if is_in_storyline(created, "q3_2023_eu_payment_delays"):
            ticket_mult = 1.5
        if is_in_storyline(created, "q2_2025_tariff_volatility"):
            ticket_mult *= get_storyline_param("q2_2025_tariff_volatility", "ticket_spike_multiplier", 1.0)

        if random.random() > (1.0 / ticket_mult):
            continue  # Skip to simulate lower volume in non-spike periods

        pri_wts = [0.10, 0.25, 0.35, 0.30] if sc_id in churn_map else [0.30, 0.40, 0.20, 0.10]
        priority = weighted_choice(priorities, pri_wts)
        hrs = round(random.uniform(0.5, 72) if priority in ["low", "medium"] else random.uniform(0.25, 24), 1)
        resolved = (created + datetime.timedelta(hours=hrs)).isoformat()[:10] if random.random() < 0.85 else None
        rows.append((sc_id, created.isoformat(), resolved, weighted_choice(categories, cat_wts), priority, hrs if resolved else None))

    conn.executemany("INSERT INTO support_tickets (saas_customer_id, created_date, resolved_date, category, priority, resolution_hours) VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    print(f"    {len(rows)} support tickets created.")


# ═══════════════════════════════════════════════════════════════
# LAYER 3: PRODUCT ANALYTICS
# ═══════════════════════════════════════════════════════════════

def generate_saas_users(conn):
    print("  Generating SaaS users...")
    saas = conn.execute("SELECT saas_customer_id, plan_tier, signup_date FROM saas_customers").fetchall()
    rows = []
    user_map = defaultdict(list)
    uid = 0

    for sc_id, plan, signup_str in saas:
        signup = datetime.date.fromisoformat(signup_str)
        lo, hi = PLAN_USER_RANGE.get(plan, (1, 2))
        n = random.randint(lo, hi)
        for i in range(n):
            uid += 1
            role = "admin" if i == 0 else random.choices(["analyst", "viewer", "power_user"], weights=[0.40, 0.35, 0.25], k=1)[0]
            created = min(signup + datetime.timedelta(days=random.randint(0, 30) * i), END_DATE)
            rows.append((sc_id, fake.email(), role, created.isoformat(), None, "active" if random.random() < 0.85 else random.choice(["inactive", "deactivated"])))
            user_map[sc_id].append(uid)

    conn.executemany("INSERT INTO saas_users (saas_customer_id, email, role, created_date, last_login_date, status) VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    print(f"    {len(rows)} SaaS users created.")
    return user_map


def generate_usage_events(conn, user_map, churn_map):
    print("  Generating usage events (this may take a moment)...")
    saas = conn.execute("SELECT saas_customer_id, plan_tier, signup_date, status FROM saas_customers").fetchall()
    rows = []
    last_logins = {}
    batch_size = 50000
    total = 0

    hour_weights = [1,1,1,1,1,2,4,8,12,14,14,12,10,12,14,12,8,5,3,2,1,1,1,1]

    for sc_id, plan, signup_str, status in saas:
        if plan == "free" and random.random() < 0.6:
            continue
        signup = datetime.date.fromisoformat(signup_str)
        users = user_map.get(sc_id, [])
        if not users:
            continue

        churn_date = churn_map.get(sc_id)
        account_end = churn_date if churn_date else END_DATE

        # Power user weights
        user_wts = [random.uniform(3.0, 6.0) if random.random() < 0.18 else random.uniform(0.3, 1.5) for _ in users]
        base_events = EVENTS_PER_MONTH.get(plan, 20)

        d = max(signup, START_DATE).replace(day=1)
        while d <= account_end and d <= END_DATE:
            month_end = min((d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1), account_end, END_DATE)
            events_this_month = base_events

            # Churn decay
            if churn_date:
                days_to_churn = (churn_date - d).days
                if days_to_churn < 90:
                    events_this_month = int(base_events * max(0.1, days_to_churn / 90))
                if days_to_churn < 30:
                    events_this_month = max(2, int(base_events * 0.1))

            # Q4 2025 AI launch boost for adopters
            if d >= AI_INSIGHTS_LAUNCH:
                month_offset = (d.year - 2025) * 12 + d.month - 10 + 1
                adoption = min(0.12 * month_offset, 0.35)
                if random.random() < adoption:
                    events_this_month = int(events_this_month * 1.3)

            n_events = max(1, int(events_this_month * random.uniform(0.8, 1.2)))

            for _ in range(n_events):
                uid_picked = random.choices(users, weights=user_wts, k=1)[0]
                event_day = random.randint(d.day, month_end.day)
                try:
                    event_date = datetime.date(d.year, d.month, event_day)
                except ValueError:
                    event_date = month_end
                if event_date.weekday() >= 5 and random.random() < 0.80:
                    event_date -= datetime.timedelta(days=event_date.weekday() - 4)
                    if event_date < d:
                        event_date = d

                hour = random.choices(range(24), weights=hour_weights, k=1)[0]
                event_dt = f"{event_date.isoformat()} {hour:02d}:{random.randint(0,59):02d}:00"

                # Event type selection
                if d >= AI_INSIGHTS_LAUNCH and random.random() < 0.20:
                    etype = random.choice(AI_EVENT_TYPES)
                    module = AI_INSIGHTS_MODULE
                elif churn_date and (churn_date - event_date).days < 30:
                    etype = random.choices(EVENT_TYPES, weights=[50,10,1,5,3,1,1,1,1], k=1)[0]
                    module = random.choices(FEATURE_MODULES, weights=[60,20,5,10,5], k=1)[0]
                else:
                    etype = random.choice(EVENT_TYPES)
                    module = random.choice(FEATURE_MODULES)

                duration = random.randint(5, 1800) if etype != "login" else random.randint(1, 10)
                last_logins[uid_picked] = event_date
                rows.append((uid_picked, sc_id, event_dt, etype, module, make_session_id(), duration))
                total += 1

            if len(rows) >= batch_size:
                conn.executemany("INSERT INTO usage_events (user_id, saas_customer_id, event_date, event_type, feature_module, session_id, duration_seconds) VALUES (?,?,?,?,?,?,?)", rows)
                conn.commit()
                rows = []

            d = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

    if rows:
        conn.executemany("INSERT INTO usage_events (user_id, saas_customer_id, event_date, event_type, feature_module, session_id, duration_seconds) VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()

    for uid_val, last_date in last_logins.items():
        conn.execute("UPDATE saas_users SET last_login_date = ? WHERE user_id = ?", (last_date.isoformat(), uid_val))
    conn.commit()
    print(f"    {total} usage events created.")


def generate_feature_adoption(conn):
    print("  Generating feature adoption rollups...")
    conn.execute("""
        INSERT INTO feature_adoption (saas_customer_id, feature_module, first_used_date,
                                       last_used_date, total_events, monthly_active_users, adoption_depth)
        SELECT saas_customer_id, feature_module, MIN(DATE(event_date)), MAX(DATE(event_date)),
            COUNT(*), COUNT(DISTINCT user_id),
            CASE WHEN COUNT(*) >= 200 THEN 'heavy' WHEN COUNT(*) >= 50 THEN 'moderate'
                 WHEN COUNT(*) >= 10 THEN 'light' ELSE 'none' END
        FROM usage_events GROUP BY saas_customer_id, feature_module
    """)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM feature_adoption").fetchone()[0]
    print(f"    {count} feature adoption records created.")


def compute_usage_scores(conn, churn_map):
    print("  Computing usage scores from event data...")
    recent_date = (END_DATE - datetime.timedelta(days=30)).isoformat()
    stats = conn.execute(f"""
        SELECT saas_customer_id, COUNT(DISTINCT user_id), COUNT(*),
               COUNT(DISTINCT feature_module), AVG(duration_seconds)
        FROM usage_events WHERE DATE(event_date) >= '{recent_date}'
        GROUP BY saas_customer_id
    """).fetchall()
    user_counts = dict(conn.execute("SELECT saas_customer_id, COUNT(*) FROM saas_users WHERE status='active' GROUP BY saas_customer_id").fetchall())
    updates = []
    for sc_id, active, events, modules, avg_dur in stats:
        tot = user_counts.get(sc_id, 1)
        score = int(clamp(
            min(active / max(tot, 1), 1.0) * 35 +
            (modules / 6.0) * 25 +  # 6 modules now (includes ai_insights)
            min(events / 500.0, 1.0) * 25 +
            min((avg_dur or 0) / 600.0, 1.0) * 15,
            0, 100
        ))
        if sc_id in churn_map:
            score = min(score, 20)
        updates.append((score, sc_id))

    conn.executemany("UPDATE saas_customers SET usage_score = ? WHERE saas_customer_id = ?", updates)
    conn.execute("UPDATE saas_customers SET usage_score = 5 WHERE status = 'churned' AND usage_score > 20")
    conn.commit()
    print(f"    {len(updates)} usage scores updated.")


# ═══════════════════════════════════════════════════════════════
# LAYER 4: PAYMENTS
# ═══════════════════════════════════════════════════════════════

def generate_payments(conn):
    print("  Generating invoices and payments...")
    completed = conn.execute("""
        SELECT o.order_id, o.customer_id, o.order_date, o.total_amount, o.region, c.segment
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE o.status = 'completed'
    """).fetchall()

    inv_rows, pay_rows = [], []
    inv_id = 0

    for oid, cid, od_str, amount, region, segment in completed:
        od = datetime.date.fromisoformat(od_str)
        terms = PAYMENT_TERMS.get(segment, 30)
        due = od + datetime.timedelta(days=terms)
        inv_id += 1

        base_dtp = max(1, int(terms * random.gauss(0.70, 0.20)))

        # Storyline payment delays
        if is_in_storyline(od, "q3_2023_eu_payment_delays") and region == "Europe":
            lo, hi = get_storyline_param("q3_2023_eu_payment_delays", "payment_delay_days", (0, 0))
            base_dtp += random.randint(lo, hi)
        if is_in_storyline(od, "q2_2025_tariff_volatility"):
            lo, hi = get_storyline_param("q2_2025_tariff_volatility", "payment_delay_days", (0, 0))
            base_dtp += random.randint(lo, hi)

        # Storyline improvements
        if is_in_storyline(od, "q1_2024_collections_push"):
            base_dtp = int(base_dtp * get_storyline_param("q1_2024_collections_push", "payment_improvement", 1.0))
        if is_in_storyline(od, "q3_2025_stabilization"):
            base_dtp = int(base_dtp * get_storyline_param("q3_2025_stabilization", "payment_improvement", 1.0))

        pay_date = od + datetime.timedelta(days=base_dtp)
        if pay_date > END_DATE + datetime.timedelta(days=90):
            pay_date = END_DATE + datetime.timedelta(days=random.randint(1, 30))

        is_late = 1 if base_dtp > terms else 0
        if is_late and random.random() < 0.05:
            inv_status = "written_off"
        elif random.random() < 0.08 and amount > 500:
            inv_status = "partial"
        elif is_late and pay_date > END_DATE:
            inv_status = "overdue"
        else:
            inv_status = "paid"

        pay_amount = round(amount * random.uniform(0.4, 0.8), 2) if inv_status == "partial" else amount

        inv_rows.append((oid, cid, od.isoformat(), due.isoformat(), amount, inv_status))
        pay_rows.append((inv_id, pay_date.isoformat(), pay_amount,
                         random.choices(["ach", "wire", "credit_card", "check"], weights=[0.35, 0.25, 0.25, 0.15], k=1)[0],
                         base_dtp, is_late))

    conn.executemany("INSERT INTO invoices (order_id, customer_id, invoice_date, due_date, amount, status) VALUES (?,?,?,?,?,?)", inv_rows)
    conn.executemany("INSERT INTO payments (invoice_id, payment_date, amount, method, days_to_pay, is_late) VALUES (?,?,?,?,?,?)", pay_rows)
    conn.commit()
    print(f"    {len(inv_rows)} invoices, {len(pay_rows)} payments created.")


# ═══════════════════════════════════════════════════════════════
# LAYER 5: CRM
# ═══════════════════════════════════════════════════════════════

def generate_crm(conn, churn_map):
    print("  Generating CRM data...")
    customers = conn.execute("SELECT customer_id, company_name, region, segment FROM customers WHERE customer_type='wholesale'").fetchall()
    pool = random.sample(customers, min(2000, len(customers)))

    # Accounts
    acct_rows = []
    for i, (cid, name, region, segment) in enumerate(pool, 1):
        saas = conn.execute("SELECT saas_customer_id, status, usage_score FROM saas_customers WHERE customer_id = ?", (cid,)).fetchone()
        if saas and saas[1] == "churned":
            health, tier = random.randint(10, 35), "at_risk"
        elif saas and saas[2] < 30:
            health, tier = random.randint(25, 50), "at_risk"
        else:
            health = random.randint(40, 100)
            tier = "strategic" if health >= 80 else ("growth" if health >= 60 else "maintain")
        acct_rows.append((cid, random.choice(SALES_REPS), tier, health,
                          random_date(datetime.date(2025, 6, 1), END_DATE).isoformat(),
                          random_date(datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)).isoformat()))

    conn.executemany("INSERT INTO accounts (customer_id, owner, account_tier, health_score, last_contact_date, next_renewal_date) VALUES (?,?,?,?,?,?)", acct_rows)

    # Activities — 7,500 for 3 years
    act_types = ["call", "email", "meeting", "demo", "qbr"]
    act_wts = [0.30, 0.30, 0.20, 0.10, 0.10]
    outcomes = ["positive", "neutral", "negative", "follow_up_needed"]
    out_wts = [0.35, 0.30, 0.10, 0.25]
    note_templates = [
        "Discussed {product} renewal with {contact}. Customer expressed concern about {issue}. Next step: {action}.",
        "Quarterly business review with {contact}. Reviewed usage metrics \u2014 {metric}. Customer interested in {product}.",
        "Follow-up call regarding {issue}. {contact} confirmed {outcome}. Will revisit in {timeframe}.",
        "Demo of {product} for {contact}'s team. {feedback}. Decision expected by {timeframe}.",
        "Email exchange with {contact} about {issue}. Sent {document} for review. Awaiting response.",
        "Onboarding session for {product}. {contact} and team completed initial setup. {feedback}.",
        "Escalation: {contact} reported {issue}. Engaged support team. Resolution expected in {timeframe}.",
        "Strategic planning meeting with {contact}. Discussed expansion to {product}. Budget approval needed from {role}.",
        "Tariff impact review with {contact}. Discussed pricing adjustments for {product}. Customer evaluating alternatives.",
        "AI features walkthrough with {contact}. Demonstrated new AI Insights module. {feedback}.",
    ]
    products = ["Analytics Pro", "Dashboard Suite", "Integration Hub", "Data Connector", "Enterprise Platform", "AI Insights"]
    issues = ["pricing concerns", "performance issues", "feature gaps", "competitor evaluation",
              "integration challenges", "onboarding delays", "billing discrepancy", "contract terms",
              "tariff-related pricing", "supply chain disruption"]
    contacts = [fake.name() for _ in range(50)]
    actions = ["schedule follow-up", "send proposal", "arrange demo", "escalate to manager", "share case study", "provide trial extension", "arrange QBR"]
    metrics = ["usage up 15% QoQ", "3 new users added", "adoption of dashboards module", "declining login frequency", "support tickets trending down", "NPS score: 8/10", "AI Insights adoption: active"]
    feedbacks = ["Very positive reception", "Some concerns about pricing", "Requested additional features", "Compared favorably to competitor", "Team needs more training", "Immediate interest in expansion"]
    timeframes = ["2 weeks", "end of quarter", "next month", "30 days", "Q1 2026"]
    documents = ["ROI analysis", "pricing proposal", "technical spec", "case study", "product roadmap"]
    roles = ["VP of Engineering", "CFO", "Head of Analytics", "CTO", "Director of Operations"]

    act_rows = []
    for _ in range(7500):
        acct_id = random.randint(1, len(acct_rows))
        ad = random_date(START_DATE, END_DATE)
        atype = weighted_choice(act_types, act_wts)
        subj_map = {
            "call": f"Call with {random.choice(contacts)}",
            "email": f"Re: {random.choice(issues).title()}",
            "meeting": f"Meeting: {random.choice(['Pipeline Review', 'Account Planning', 'Technical Discussion', 'Renewal Discussion', 'Tariff Impact Review'])}",
            "demo": f"Demo: {random.choice(products)}",
            "qbr": f"QBR \u2014 Q{(ad.month-1)//3+1} {ad.year}",
        }
        template = random.choice(note_templates)
        notes = template.format(
            product=random.choice(products), contact=random.choice(contacts),
            issue=random.choice(issues), action=random.choice(actions),
            metric=random.choice(metrics), feedback=random.choice(feedbacks),
            outcome=random.choice(["they will proceed", "decision postponed", "need budget approval", "moving forward with pilot"]),
            timeframe=random.choice(timeframes), document=random.choice(documents), role=random.choice(roles),
        )
        act_rows.append((acct_id, ad.isoformat(), atype, subj_map[atype], notes, weighted_choice(outcomes, out_wts)))

    conn.executemany("INSERT INTO activities (account_id, activity_date, activity_type, subject, notes, outcome) VALUES (?,?,?,?,?,?)", act_rows)

    # Opportunities — 2,000 for 3 years
    stage_probs = {"prospecting": 10, "qualification": 25, "proposal": 40, "negotiation": 60, "closed_won": 100, "closed_lost": 0}
    opp_rows = []
    for _ in range(2000):
        acct_id = random.randint(1, len(acct_rows))
        r = random.random()
        stage = "prospecting" if r < 0.20 else ("qualification" if r < 0.35 else ("proposal" if r < 0.50 else ("negotiation" if r < 0.62 else ("closed_won" if r < 0.85 else "closed_lost"))))
        amount = round(random.uniform(5000, 250000) * (0.5 if stage in ["prospecting", "qualification"] else 1.0), 2)
        close = random_date(START_DATE, datetime.date(2026, 6, 30))
        prod = random.choice(products)
        opp_name = f"{random.choice(['Expansion', 'Renewal', 'New', 'Upsell', 'Cross-sell'])} \u2014 {prod}"
        opp_rows.append((acct_id, opp_name, stage, amount, close.isoformat(), stage_probs[stage], prod))

    conn.executemany("INSERT INTO opportunities (account_id, opp_name, stage, amount, close_date, probability, product_interest) VALUES (?,?,?,?,?,?,?)", opp_rows)
    conn.commit()
    print(f"    {len(acct_rows)} accounts, {len(act_rows)} activities, {len(opp_rows)} opportunities created.")


# ═══════════════════════════════════════════════════════════════
# BRIDGE LAYER
# ═══════════════════════════════════════════════════════════════

def build_bridge_tables(conn):
    print("  Building bridge tables...")
    conn.execute("""
        INSERT OR IGNORE INTO customer_xref (customer_id, ecommerce_id, saas_customer_id, account_id, payment_customer_id)
        SELECT c.customer_id, c.customer_id, sc.saas_customer_id, a.account_id, c.customer_id
        FROM customers c
        LEFT JOIN saas_customers sc ON c.customer_id = sc.customer_id
        LEFT JOIN accounts a ON c.customer_id = a.customer_id
    """)

    recent = (END_DATE - datetime.timedelta(days=1)).isoformat()
    recent30 = (END_DATE - datetime.timedelta(days=30)).isoformat()

    conn.execute(f"""
        INSERT OR IGNORE INTO customer_360
        SELECT c.customer_id, c.company_name, c.region, c.segment,
            COALESCE(ord.total_orders, 0), COALESCE(ord.total_revenue, 0),
            COALESCE(ret.total_returns, 0),
            CASE WHEN COALESCE(ord.total_orders, 0) > 0
                 THEN ROUND(CAST(COALESCE(ret.total_returns, 0) AS REAL) / ord.total_orders, 4) ELSE 0 END,
            sc.plan_tier, sc.mrr, sc.usage_score,
            pa.dau_mau_ratio, pa.features_adopted, pa.avg_session_minutes,
            pay.avg_days_to_pay, pay.late_payment_pct,
            a.health_score, act.last_activity_date,
            COALESCE(opp.open_opps, 0),
            COALESCE(ord.total_revenue, 0) + COALESCE(sc.mrr, 0) * 36
        FROM customers c
        LEFT JOIN (SELECT customer_id, COUNT(*) as total_orders, SUM(total_amount) as total_revenue
                   FROM orders WHERE status='completed' GROUP BY customer_id) ord ON c.customer_id = ord.customer_id
        LEFT JOIN (SELECT o.customer_id, COUNT(*) as total_returns FROM returns r
                   JOIN orders o ON r.order_id = o.order_id GROUP BY o.customer_id) ret ON c.customer_id = ret.customer_id
        LEFT JOIN saas_customers sc ON c.customer_id = sc.customer_id
        LEFT JOIN (SELECT saas_customer_id,
                   ROUND(CAST(COUNT(DISTINCT CASE WHEN DATE(event_date) >= '{recent}' THEN user_id END) AS REAL) /
                         NULLIF(COUNT(DISTINCT CASE WHEN DATE(event_date) >= '{recent30}' THEN user_id END), 0), 3) as dau_mau_ratio,
                   COUNT(DISTINCT feature_module) as features_adopted,
                   ROUND(AVG(duration_seconds) / 60.0, 1) as avg_session_minutes
                   FROM usage_events GROUP BY saas_customer_id) pa ON sc.saas_customer_id = pa.saas_customer_id
        LEFT JOIN (SELECT i.customer_id, ROUND(AVG(p.days_to_pay), 1) as avg_days_to_pay,
                   ROUND(CAST(SUM(p.is_late) AS REAL) / COUNT(*), 4) as late_payment_pct
                   FROM payments p JOIN invoices i ON p.invoice_id = i.invoice_id GROUP BY i.customer_id) pay ON c.customer_id = pay.customer_id
        LEFT JOIN accounts a ON c.customer_id = a.customer_id
        LEFT JOIN (SELECT account_id, MAX(activity_date) as last_activity_date FROM activities GROUP BY account_id) act ON a.account_id = act.account_id
        LEFT JOIN (SELECT account_id, COUNT(*) as open_opps FROM opportunities WHERE stage NOT IN ('closed_won', 'closed_lost') GROUP BY account_id) opp ON a.account_id = opp.account_id
    """)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM customer_360").fetchone()[0]
    print(f"    customer_xref and customer_360 built ({count} rows).")
