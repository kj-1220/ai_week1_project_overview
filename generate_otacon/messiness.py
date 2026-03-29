"""
messiness.py — Controlled Data Quality Degradation for Otacon Inc.
===================================================================
Post-processes otacon.db to inject realistic enterprise data quality
issues. Every mess type has a known rate and is deterministic (seeded),
so downstream projects can validate whether they handle it correctly.

Usage (standalone):
    python -m generate_otacon.messiness          # apply defaults
    python -m generate_otacon.messiness --dry-run # preview without changes

Usage (from __main__.py):
    from messiness import apply_messiness
    apply_messiness(conn)

The MESSINESS_CONFIG dict controls every knob. Set any rate to 0.0
to disable that category entirely.

SCHEMA REFERENCE (columns that actually exist):
  customers:        customer_id (INT PK), company_name, customer_type, region, segment,
                    industry, acquisition_date, acquisition_channel, status, annual_revenue_tier
  orders:           order_id (INT PK), customer_id, order_date, ship_date, status, channel,
                    region, total_amount, discount_pct
  order_items:      line_id (INT PK), order_id, product_id, quantity, unit_price, line_total
  returns:          return_id, order_id, return_date, reason, refund_amount, status
  saas_customers:   saas_customer_id, customer_id, plan_tier, signup_date, contract_months,
                    mrr, status, usage_score
  support_tickets:  ticket_id, saas_customer_id, created_date, resolved_date, category,
                    priority, resolution_hours
  saas_users:       user_id, saas_customer_id, email, role, created_date, last_login_date, status
  usage_events:     event_id, user_id, saas_customer_id, event_date, event_type,
                    feature_module, session_id, duration_seconds
  feature_adoption: adoption_id, saas_customer_id, feature_module, first_used_date,
                    last_used_date, total_events, monthly_active_users, adoption_depth
  invoices:         invoice_id, order_id, customer_id, invoice_date, due_date, amount, status
  payments:         payment_id, invoice_id, payment_date, amount, method, days_to_pay, is_late
  accounts:         account_id, customer_id, owner, account_tier, health_score,
                    last_contact_date, next_renewal_date
  activities:       activity_id, account_id, activity_date, activity_type, subject, notes, outcome
  opportunities:    opp_id, account_id, opp_name, stage, amount, close_date, probability,
                    product_interest
"""

import sqlite3
import random
import string
import datetime
import os
import sys
import json

# ═══════════════════════════════════════════════════════════════
# DEFAULT CONFIGURATION
# ═══════════════════════════════════════════════════════════════

MESSINESS_CONFIG = {
    # ── Master switch ──
    "enabled": True,
    "random_seed": 99,          # Separate seed so messiness is reproducible

    # ── 1. Missing Values ──
    # Nullable fields get NULLed at these rates.
    # Only targets columns that are either already nullable in the schema
    # or where SQLite allows the UPDATE (no strict mode).
    "missing_values": {
        "enabled": True,
        "rules": [
            # E-Commerce layer
            {"table": "orders",           "column": "ship_date",       "rate": 0.05},   # Orders "in transit" forever
            {"table": "returns",          "column": "reason",          "rate": 0.15},   # "Unknown" return reasons

            # SaaS layer
            {"table": "support_tickets",  "column": "resolved_date",   "rate": 0.10},   # Tickets never closed
            {"table": "support_tickets",  "column": "resolution_hours","rate": 0.10},   # No resolution time recorded

            # Product Analytics layer
            {"table": "usage_events",     "column": "session_id",      "rate": 0.04},   # Orphaned events
            {"table": "usage_events",     "column": "duration_seconds","rate": 0.06},   # Missing duration
            {"table": "feature_adoption", "column": "last_used_date",  "rate": 0.07},   # Last use not tracked

            # CRM layer
            {"table": "activities",       "column": "notes",           "rate": 0.18},   # Sales reps skip notes
            {"table": "accounts",         "column": "last_contact_date","rate": 0.08},  # No contact date recorded
            {"table": "accounts",         "column": "next_renewal_date","rate": 0.06},  # Renewal date not set
        ],
    },

    # ── 2. Format Inconsistencies ──
    # Realistic formatting chaos in text fields
    "format_inconsistencies": {
        "enabled": True,
        "company_name_rate": 0.12,       # "Acme Corp" → "ACME CORP", "acme corp.", etc.
        "region_spelling_rate": 0.05,    # "North America" → "N. America", "NA", "north america"
        "whitespace_rate": 0.06,         # Leading/trailing spaces, double spaces
    },

    # ── 3. Duplicate-Adjacent Records ──
    # Same entity, slightly different data.
    # Since customer_id is INTEGER AUTOINCREMENT, duplicates get new IDs.
    # A _messiness_duplicates tracking table records which IDs are dupes.
    "near_duplicates": {
        "enabled": True,
        "customer_rate": 0.03,           # 3% of customers get a near-duplicate
    },

    # ── 4. Temporal Anomalies ──
    # Backdated records, future-dated typos, out-of-order events
    "temporal_anomalies": {
        "enabled": True,
        "backdated_payment_rate": 0.04,  # Payment date pushed forward 3-7 days
        "future_date_typo_rate": 0.005,  # Obvious typos: 2025 → 2052
    },

    # ── 5. Numeric Outliers & Zeros ──
    # Suspicious values that a real pipeline would need to flag
    "numeric_anomalies": {
        "enabled": True,
        "zero_amount_rate": 0.008,       # $0 line items (test orders? comps?)
        "negative_amount_rate": 0.003,   # Negative amounts (refunds miscoded as orders)
        "extreme_outlier_rate": 0.002,   # 10x-100x normal values (decimal point errors)
    },

    # ── 6. Referential Integrity Issues ──
    # Orphaned foreign keys (rare but realistic).
    # Uses integer IDs in the 90001+ range that don't exist.
    "orphaned_references": {
        "enabled": True,
        "orphan_rate": 0.005,            # 0.5% of FKs point to nonexistent records
        "ghost_id_start": 90001,         # Orphan IDs start here (well above 8K customers)
    },

    # ── 7. Encoding & Special Characters ──
    # Unicode issues, mojibake, truncated strings
    "encoding_issues": {
        "enabled": True,
        "mojibake_rate": 0.02,           # "Müller" → "MÃ¼ller"
        "truncated_rate": 0.01,          # Field cut off mid-word
    },
}


# ═══════════════════════════════════════════════════════════════
# MESSINESS FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _get_row_ids(conn, table, limit=None):
    """Get all rowids from a table."""
    q = f"SELECT rowid FROM {table}"
    if limit:
        q += f" LIMIT {limit}"
    return [r[0] for r in conn.execute(q).fetchall()]


def _sample_ids(ids, rate):
    """Return a random sample of IDs at the given rate."""
    k = max(1, int(len(ids) * rate))
    if k >= len(ids):
        return ids
    return random.sample(ids, k)


def _null_column(conn, table, column, rate, stats):
    """Set a column to NULL for a percentage of rows."""
    ids = _get_row_ids(conn, table)
    if not ids:
        return
    targets = _sample_ids(ids, rate)
    if not targets:
        return
    placeholders = ",".join("?" * len(targets))
    conn.execute(
        f"UPDATE {table} SET {column} = NULL WHERE rowid IN ({placeholders})",
        targets
    )
    key = f"nulled:{table}.{column}"
    stats[key] = len(targets)


def apply_missing_values(conn, config, stats):
    """Category 1: Inject NULL values into nullable fields."""
    cfg = config.get("missing_values", {})
    if not cfg.get("enabled", False):
        return
    for rule in cfg.get("rules", []):
        try:
            _null_column(conn, rule["table"], rule["column"], rule["rate"], stats)
        except Exception as e:
            stats[f"skip:{rule['table']}.{rule['column']}"] = str(e)


# ── Company name variations ──
_NAME_VARIATIONS = [
    lambda n: n.upper(),                              # "ACME CORP"
    lambda n: n.lower(),                              # "acme corp"
    lambda n: n.replace(" Inc.", "").replace(" Corp.", "").replace(" LLC", ""),  # Strip suffix
    lambda n: n.replace("Corp.", "Corporation").replace("Inc.", "Incorporated"),
    lambda n: n + ".",                                 # Trailing period
    lambda n: " " + n,                                 # Leading space
    lambda n: n + "  ",                                # Trailing spaces
]

_REGION_VARIANTS = {
    "North America": ["N. America", "NA", "north america", "North_America", "NorthAmerica"],
    "Europe": ["EU", "europe", "EMEA", "Europe "],
    "APAC": ["Asia Pacific", "apac", "Asia-Pacific", "AP"],
    "LATAM": ["Latin America", "latam", "LATAM ", "South America"],
}


def apply_format_inconsistencies(conn, config, stats):
    """Category 2: Inject formatting chaos into text fields."""
    cfg = config.get("format_inconsistencies", {})
    if not cfg.get("enabled", False):
        return

    # Company names in customers table
    rate = cfg.get("company_name_rate", 0.0)
    if rate > 0:
        rows = conn.execute(
            "SELECT rowid, company_name FROM customers WHERE company_name IS NOT NULL"
        ).fetchall()
        if rows:
            targets = random.sample(rows, max(1, int(len(rows) * rate)))
            for rowid, name in targets:
                variation = random.choice(_NAME_VARIATIONS)(name)
                conn.execute(
                    "UPDATE customers SET company_name = ? WHERE rowid = ?",
                    (variation, rowid)
                )
            stats["format:company_names"] = len(targets)

    # Region spelling variations (on customers table)
    rate = cfg.get("region_spelling_rate", 0.0)
    if rate > 0:
        rows = conn.execute(
            "SELECT rowid, region FROM customers WHERE region IS NOT NULL"
        ).fetchall()
        if rows:
            targets = random.sample(rows, max(1, int(len(rows) * rate)))
            count = 0
            for rowid, region in targets:
                variants = _REGION_VARIANTS.get(region, [])
                if variants:
                    conn.execute(
                        "UPDATE customers SET region = ? WHERE rowid = ?",
                        (random.choice(variants), rowid)
                    )
                    count += 1
            stats["format:regions"] = count

    # Whitespace issues (company_name and activities.notes)
    rate = cfg.get("whitespace_rate", 0.0)
    if rate > 0:
        for table, col in [("customers", "company_name"), ("activities", "notes")]:
            try:
                rows = conn.execute(
                    f"SELECT rowid, {col} FROM {table} WHERE {col} IS NOT NULL"
                ).fetchall()
                if rows:
                    targets = random.sample(rows, max(1, int(len(rows) * rate)))
                    for rowid, val in targets:
                        mangled = random.choice([
                            " " + val,                      # Leading space
                            val + "  ",                     # Trailing spaces
                            val.replace(" ", "  ", 1),      # Double space
                        ])
                        conn.execute(
                            f"UPDATE {table} SET {col} = ? WHERE rowid = ?",
                            (mangled, rowid)
                        )
                    stats[f"format:whitespace:{table}.{col}"] = len(targets)
            except Exception:
                pass


def apply_near_duplicates(conn, config, stats):
    """
    Category 3: Create near-duplicate customer records.

    Since customer_id is INTEGER AUTOINCREMENT, duplicates get new sequential IDs.
    We track them in a _messiness_duplicates table so governance.py can exclude them.
    """
    cfg = config.get("near_duplicates", {})
    if not cfg.get("enabled", False):
        return

    rate = cfg.get("customer_rate", 0.0)
    if rate <= 0:
        return

    # Create tracking table
    conn.execute("DROP TABLE IF EXISTS _messiness_duplicates")
    conn.execute("""
        CREATE TABLE _messiness_duplicates (
            duplicate_customer_id INTEGER PRIMARY KEY,
            original_customer_id INTEGER NOT NULL,
            variation_type TEXT NOT NULL
        )
    """)

    rows = conn.execute("""
        SELECT customer_id, company_name, region, segment, industry,
               customer_type, acquisition_date, acquisition_channel,
               status, annual_revenue_tier
        FROM customers
    """).fetchall()

    targets = random.sample(rows, max(1, int(len(rows) * rate)))
    count = 0

    for row in targets:
        (cid, name, region, segment, industry,
         ctype, acq_date, acq_channel, status, rev_tier) = row

        # Generate a slightly different company name
        variation_type = random.choice(["upper", "lower", "strip_suffix", "add_period"])

        if variation_type == "upper":
            new_name = name.upper()
        elif variation_type == "lower":
            new_name = name.lower()
        elif variation_type == "strip_suffix":
            new_name = (name.replace(" Inc.", "").replace(" Corp.", "")
                        .replace(" LLC", "").replace(" Ltd.", ""))
            if new_name == name:
                new_name = name + " Inc"
        else:  # add_period
            new_name = name + "."

        try:
            cursor = conn.execute("""
                INSERT INTO customers
                    (company_name, customer_type, region, segment, industry,
                     acquisition_date, acquisition_channel, status, annual_revenue_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_name, ctype, region, segment, industry,
                  acq_date, acq_channel, status, rev_tier))

            new_id = cursor.lastrowid
            conn.execute("""
                INSERT INTO _messiness_duplicates
                    (duplicate_customer_id, original_customer_id, variation_type)
                VALUES (?, ?, ?)
            """, (new_id, cid, variation_type))
            count += 1
        except Exception:
            pass

    stats["duplicates:customers"] = count


def apply_temporal_anomalies(conn, config, stats):
    """Category 4: Inject time-based data quality issues."""
    cfg = config.get("temporal_anomalies", {})
    if not cfg.get("enabled", False):
        return

    # Backdated payments: push payment_date forward 3-7 days
    rate = cfg.get("backdated_payment_rate", 0.0)
    if rate > 0:
        try:
            rows = conn.execute("""
                SELECT p.rowid, p.payment_date
                FROM payments p
                WHERE p.payment_date IS NOT NULL
            """).fetchall()
            if rows:
                targets = random.sample(rows, max(1, int(len(rows) * rate)))
                for rowid, pdate in targets:
                    try:
                        dt = datetime.datetime.strptime(pdate[:10], "%Y-%m-%d")
                        delay = random.randint(3, 7)
                        new_dt = dt + datetime.timedelta(days=delay)
                        conn.execute(
                            "UPDATE payments SET payment_date = ? WHERE rowid = ?",
                            (new_dt.strftime("%Y-%m-%d"), rowid)
                        )
                    except (ValueError, TypeError):
                        pass
                stats["temporal:backdated_payments"] = len(targets)
        except Exception:
            pass

    # Future date typos: year digit transposition
    # Tables with date columns: orders.order_date, activities.activity_date
    rate = cfg.get("future_date_typo_rate", 0.0)
    if rate > 0:
        for table, col in [("orders", "order_date"), ("activities", "activity_date")]:
            try:
                rows = conn.execute(
                    f"SELECT rowid, {col} FROM {table} WHERE {col} IS NOT NULL"
                ).fetchall()
                if rows:
                    targets = random.sample(rows, max(1, int(len(rows) * rate)))
                    for rowid, val in targets:
                        # Swap 2025 → 2052, 2024 → 2042, 2023 → 2032
                        mangled = (val.replace("2025", "2052")
                                      .replace("2024", "2042")
                                      .replace("2023", "2032"))
                        conn.execute(
                            f"UPDATE {table} SET {col} = ? WHERE rowid = ?",
                            (mangled, rowid)
                        )
                    stats[f"temporal:future_typo:{table}.{col}"] = len(targets)
            except Exception:
                pass


def apply_numeric_anomalies(conn, config, stats):
    """Category 5: Inject suspicious numeric values."""
    cfg = config.get("numeric_anomalies", {})
    if not cfg.get("enabled", False):
        return

    # Zero amounts in order_items.unit_price
    rate = cfg.get("zero_amount_rate", 0.0)
    if rate > 0:
        try:
            rows = conn.execute(
                "SELECT rowid FROM order_items WHERE unit_price > 0"
            ).fetchall()
            ids = [r[0] for r in rows]
            if ids:
                targets = _sample_ids(ids, rate)
                placeholders = ",".join("?" * len(targets))
                conn.execute(
                    f"UPDATE order_items SET unit_price = 0.0 WHERE rowid IN ({placeholders})",
                    targets
                )
                stats["numeric:zero_amounts"] = len(targets)
        except Exception:
            pass

    # Negative amounts in order_items.unit_price
    rate = cfg.get("negative_amount_rate", 0.0)
    if rate > 0:
        try:
            rows = conn.execute(
                "SELECT rowid, unit_price FROM order_items WHERE unit_price > 0"
            ).fetchall()
            if rows:
                targets = random.sample(rows, max(1, int(len(rows) * rate)))
                for rowid, price in targets:
                    conn.execute(
                        "UPDATE order_items SET unit_price = ? WHERE rowid = ?",
                        (-abs(price), rowid)
                    )
                stats["numeric:negative_amounts"] = len(targets)
        except Exception:
            pass

    # Extreme outliers (decimal point errors: $45.99 → $4599.00)
    rate = cfg.get("extreme_outlier_rate", 0.0)
    if rate > 0:
        try:
            rows = conn.execute(
                "SELECT rowid, unit_price FROM order_items WHERE unit_price > 0"
            ).fetchall()
            if rows:
                targets = random.sample(rows, max(1, int(len(rows) * rate)))
                for rowid, price in targets:
                    multiplier = random.choice([100, 1000])  # Decimal shift
                    conn.execute(
                        "UPDATE order_items SET unit_price = ? WHERE rowid = ?",
                        (price * multiplier, rowid)
                    )
                stats["numeric:extreme_outliers"] = len(targets)
        except Exception:
            pass


def apply_orphaned_references(conn, config, stats):
    """
    Category 6: Create orphaned foreign key references.

    Since all PKs are integers, we set FK values to integers in the 90001+
    range that don't correspond to any real record.
    """
    cfg = config.get("orphaned_references", {})
    if not cfg.get("enabled", False):
        return

    rate = cfg.get("orphan_rate", 0.0)
    if rate <= 0:
        return

    ghost_start = cfg.get("ghost_id_start", 90001)

    # Orphan some orders.customer_id → point to nonexistent customer
    try:
        rows = conn.execute("SELECT rowid FROM orders").fetchall()
        ids = [r[0] for r in rows]
        if ids:
            targets = _sample_ids(ids, rate)
            for i, rowid in enumerate(targets):
                ghost_id = ghost_start + i
                conn.execute(
                    "UPDATE orders SET customer_id = ? WHERE rowid = ?",
                    (ghost_id, rowid)
                )
            stats["orphans:orders.customer_id"] = len(targets)
    except Exception:
        pass

    # Orphan some payments.invoice_id → point to nonexistent invoice
    try:
        max_inv = conn.execute("SELECT MAX(invoice_id) FROM invoices").fetchone()[0] or 0
        ghost_inv_start = max_inv + 10001

        rows = conn.execute("SELECT rowid FROM payments").fetchall()
        ids = [r[0] for r in rows]
        if ids:
            targets = _sample_ids(ids, rate)
            for i, rowid in enumerate(targets):
                ghost_id = ghost_inv_start + i
                conn.execute(
                    "UPDATE payments SET invoice_id = ? WHERE rowid = ?",
                    (ghost_id, rowid)
                )
            stats["orphans:payments.invoice_id"] = len(targets)
    except Exception:
        pass


def apply_encoding_issues(conn, config, stats):
    """Category 7: Inject encoding and truncation problems."""
    cfg = config.get("encoding_issues", {})
    if not cfg.get("enabled", False):
        return

    # Mojibake: simulate UTF-8 → Latin-1 → UTF-8 round-trip damage
    _MOJIBAKE_MAP = {
        "ü": "Ã¼", "ö": "Ã¶", "ä": "Ã¤", "é": "Ã©", "è": "Ã¨",
        "ñ": "Ã±", "ß": "ÃŸ", "ø": "Ã¸", "å": "Ã¥", "ç": "Ã§",
    }

    rate = cfg.get("mojibake_rate", 0.0)
    if rate > 0:
        try:
            rows = conn.execute(
                "SELECT rowid, company_name FROM customers WHERE company_name IS NOT NULL"
            ).fetchall()
            if rows:
                targets = random.sample(rows, max(1, int(len(rows) * rate)))
                count = 0
                for rowid, name in targets:
                    mangled = name
                    for orig, broken in _MOJIBAKE_MAP.items():
                        mangled = mangled.replace(orig, broken)
                    if mangled != name:
                        conn.execute(
                            "UPDATE customers SET company_name = ? WHERE rowid = ?",
                            (mangled, rowid)
                        )
                        count += 1
                stats["encoding:mojibake"] = count
        except Exception:
            pass

    # Truncated strings in activities.notes
    rate = cfg.get("truncated_rate", 0.0)
    if rate > 0:
        try:
            rows = conn.execute("""
                SELECT rowid, notes FROM activities
                WHERE notes IS NOT NULL AND length(notes) > 20
            """).fetchall()
            if rows:
                targets = random.sample(rows, max(1, int(len(rows) * rate)))
                for rowid, notes in targets:
                    cut_point = random.randint(10, len(notes) // 2)
                    conn.execute(
                        "UPDATE activities SET notes = ? WHERE rowid = ?",
                        (notes[:cut_point], rowid)
                    )
                stats["encoding:truncated"] = len(targets)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def apply_messiness(conn, config=None):
    """
    Apply all messiness categories to the database.

    Args:
        conn: sqlite3 connection (must be open, caller manages commit)
        config: dict overriding MESSINESS_CONFIG defaults. Pass None for defaults.

    Returns:
        dict of stats showing what was changed
    """
    cfg = {**MESSINESS_CONFIG, **(config or {})}

    if not cfg.get("enabled", True):
        print("  Messiness: DISABLED (config.enabled = False)")
        return {}

    random.seed(cfg.get("random_seed", 99))
    stats = {}

    print("  Applying data quality degradation...")
    print(f"  Seed: {cfg['random_seed']}")

    steps = [
        ("Missing values",        apply_missing_values),
        ("Format inconsistencies", apply_format_inconsistencies),
        ("Near duplicates",       apply_near_duplicates),
        ("Temporal anomalies",    apply_temporal_anomalies),
        ("Numeric anomalies",     apply_numeric_anomalies),
        ("Orphaned references",   apply_orphaned_references),
        ("Encoding issues",       apply_encoding_issues),
    ]

    for label, func in steps:
        before = len(stats)
        func(conn, cfg, stats)
        changes = len(stats) - before
        print(f"    {label}: {changes} rule(s) applied")

    conn.commit()

    # Summary
    total_affected = sum(v for v in stats.values() if isinstance(v, int))
    print(f"\n  Messiness complete: {total_affected:,} records affected across {len(stats)} rules")

    return stats


def print_report(stats):
    """Print a readable summary of what was changed."""
    print("\n" + "=" * 60)
    print("  MESSINESS REPORT")
    print("=" * 60)

    categories = {}
    for key, val in sorted(stats.items()):
        cat = key.split(":")[0]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((key, val))

    for cat, items in categories.items():
        print(f"\n  [{cat.upper()}]")
        for key, val in items:
            detail = key.split(":", 1)[1] if ":" in key else key
            if isinstance(val, int):
                print(f"    {detail}: {val:,} records")
            else:
                print(f"    {detail}: {val}")

    total = sum(v for v in stats.values() if isinstance(v, int))
    print(f"\n  TOTAL: {total:,} records affected")
    print("=" * 60)


# ── CLI entry point ──
if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    db_path = "otacon.db"

    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found. Run `python -m generate_otacon` first.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    if dry_run:
        print("DRY RUN — no changes will be written")
        for rule in MESSINESS_CONFIG.get("missing_values", {}).get("rules", []):
            try:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {rule['table']} WHERE {rule['column']} IS NOT NULL"
                ).fetchone()[0]
                would_affect = int(count * rule["rate"])
                print(f"  Would NULL {would_affect:,} of {count:,} {rule['table']}.{rule['column']}")
            except Exception as e:
                print(f"  Skip {rule['table']}.{rule['column']}: {e}")
    else:
        stats = apply_messiness(conn)
        print_report(stats)

    conn.close()