"""
governance.py — Data Governance Implementation for Otacon Inc.
===============================================================
Implements the policies defined in governance.md by creating:

1. Clean views (v_*_clean) that apply exclusion, normalization,
   and imputation rules at query time
2. A data_quality_flags table that tags suspicious records
3. A region_mapping table for canonical region standardization

These are created AFTER messiness.py runs, so they govern the
messy data. Dashboards and agents query clean views. Data quality
profiling queries raw tables.

Usage (from __main__.py):
    from governance import apply_governance
    apply_governance(conn)

Usage (standalone):
    python -m generate_otacon.governance

SCHEMA REFERENCE (columns that actually exist):
  customers:        customer_id (INT PK AUTO), company_name, customer_type, region, segment,
                    industry, acquisition_date, acquisition_channel, status, annual_revenue_tier
  orders:           order_id (INT PK AUTO), customer_id (INT FK), order_date, ship_date,
                    status, channel, region, total_amount, discount_pct
  order_items:      line_id (INT PK AUTO), order_id, product_id, quantity, unit_price, line_total
  returns:          return_id, order_id, return_date, reason, refund_amount, status
  saas_customers:   saas_customer_id, customer_id, plan_tier, signup_date, contract_months,
                    mrr, status, usage_score
  support_tickets:  ticket_id, saas_customer_id, created_date, resolved_date, category,
                    priority, resolution_hours
  usage_events:     event_id, user_id, saas_customer_id, event_date, event_type,
                    feature_module, session_id, duration_seconds
  feature_adoption: adoption_id, saas_customer_id, feature_module, first_used_date,
                    last_used_date, total_events, monthly_active_users, adoption_depth
  invoices:         invoice_id, order_id, customer_id, invoice_date, due_date, amount, status
  payments:         payment_id (INT PK AUTO), invoice_id (INT FK), payment_date, amount,
                    method, days_to_pay, is_late
  accounts:         account_id, customer_id, owner, account_tier, health_score,
                    last_contact_date, next_renewal_date
  activities:       activity_id, account_id, activity_date, activity_type, subject, notes, outcome
  opportunities:    opp_id, account_id, opp_name, stage, amount, close_date, probability,
                    product_interest

MESSINESS REFERENCE (what messiness.py does that governance must handle):
  - _messiness_duplicates table tracks duplicate customer_ids
  - Orphaned orders have customer_id >= 90001 (no matching customer record)
  - Orphaned payments have invoice_id > MAX(real invoice_id) + 10000
  - Future date typos: years like 2032, 2042, 2052 in order_date, activity_date
  - Region variants: "NA", "EU", "apac", etc. in customers.region
  - Mojibake in customers.company_name
  - Truncated activities.notes
  - NULLed: orders.ship_date, returns.reason, support_tickets.resolved_date,
    support_tickets.resolution_hours, usage_events.session_id,
    usage_events.duration_seconds, feature_adoption.last_used_date,
    activities.notes, accounts.last_contact_date, accounts.next_renewal_date
"""

import sqlite3
import os
import sys


# ═══════════════════════════════════════════════════════════════
# REGION MAPPING (NRM-001 through NRM-004, Section 2.2)
# ═══════════════════════════════════════════════════════════════

REGION_MAP = {
    # Canonical: North America
    "NORTH AMERICA": "North America",
    "N. AMERICA": "North America",
    "NA": "North America",
    "NORTH_AMERICA": "North America",
    "NORTHAMERICA": "North America",
    # Canonical: Europe
    "EUROPE": "Europe",
    "EU": "Europe",
    "EMEA": "Europe",
    # Canonical: APAC
    "APAC": "APAC",
    "ASIA PACIFIC": "APAC",
    "ASIA-PACIFIC": "APAC",
    "AP": "APAC",
    # Canonical: LATAM
    "LATAM": "LATAM",
    "LATIN AMERICA": "LATAM",
    "SOUTH AMERICA": "LATAM",
}


def _create_region_mapping_table(conn):
    """Create a lookup table for region standardization."""
    conn.execute("DROP TABLE IF EXISTS region_mapping")
    conn.execute("""
        CREATE TABLE region_mapping (
            variant TEXT PRIMARY KEY,
            canonical TEXT NOT NULL
        )
    """)
    conn.executemany(
        "INSERT INTO region_mapping (variant, canonical) VALUES (?, ?)",
        [(k, v) for k, v in REGION_MAP.items()]
    )


# ═══════════════════════════════════════════════════════════════
# CLEAN VIEWS (Section 5 of governance.md)
# ═══════════════════════════════════════════════════════════════
#
# Design notes:
#   - customer_id is INTEGER, so exclusions use numeric comparisons
#     and the _messiness_duplicates tracking table
#   - payments FK is invoice_id (not order_id)
#   - Table names: activities, opportunities, accounts (no crm_ prefix)
#   - Column names: resolved_date, created_date, last_used_date,
#     acquisition_date, line_id (not resolved_at, created_at, etc.)

_CLEAN_VIEWS = {

    # ── E-Commerce ──

    "v_customers_clean": """
        CREATE VIEW v_customers_clean AS
        SELECT
            c.customer_id,
            UPPER(TRIM(c.company_name)) AS company_name,
            COALESCE(
                (SELECT rm.canonical FROM region_mapping rm
                 WHERE rm.variant = UPPER(TRIM(c.region))),
                'Unknown'
            ) AS region,
            c.segment,
            c.industry,
            c.customer_type,
            c.acquisition_date,
            c.acquisition_channel,
            c.status,
            c.annual_revenue_tier
        FROM customers c
        WHERE c.customer_id NOT IN (
            SELECT duplicate_customer_id FROM _messiness_duplicates
        )
        AND c.customer_id <= 8000
    """,

    "v_orders_clean": """
        CREATE VIEW v_orders_clean AS
        SELECT o.*
        FROM orders o
        WHERE o.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000)
          AND o.order_date <= '2025-12-31'
    """,

    "v_order_items_clean": """
        CREATE VIEW v_order_items_clean AS
        SELECT
            oi.line_id,
            oi.order_id,
            oi.product_id,
            oi.quantity,
            oi.unit_price,
            oi.line_total
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.unit_price > 0
          AND oi.unit_price < 10000
          AND o.order_date <= '2025-12-31'
          AND o.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000)
    """,

    "v_returns_clean": """
        CREATE VIEW v_returns_clean AS
        SELECT
            r.return_id,
            r.order_id,
            r.return_date,
            CASE WHEN r.reason IS NULL THEN 'Not recorded' ELSE r.reason END AS reason,
            r.refund_amount,
            r.status
        FROM returns r
        JOIN orders o ON r.order_id = o.order_id
        WHERE o.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000)
          AND o.order_date <= '2025-12-31'
    """,

    # ── SaaS ──

    "v_saas_customers_clean": """
        CREATE VIEW v_saas_customers_clean AS
        SELECT sc.*
        FROM saas_customers sc
        WHERE sc.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000)
    """,

    "v_support_tickets_clean": """
        CREATE VIEW v_support_tickets_clean AS
        SELECT
            st.ticket_id,
            st.saas_customer_id,
            st.created_date,
            st.resolved_date,
            st.category,
            st.priority,
            st.resolution_hours,
            CASE
                WHEN st.resolved_date IS NULL THEN 'Open'
                ELSE st.resolved_date
            END AS resolution_display
        FROM support_tickets st
    """,

    # ── Product Analytics ──

    "v_usage_events_clean": """
        CREATE VIEW v_usage_events_clean AS
        SELECT *
        FROM usage_events
        WHERE session_id IS NOT NULL
    """,

    "v_feature_adoption_clean": """
        CREATE VIEW v_feature_adoption_clean AS
        SELECT
            fa.adoption_id,
            fa.saas_customer_id,
            fa.feature_module,
            fa.first_used_date,
            fa.last_used_date,
            fa.total_events,
            fa.monthly_active_users,
            fa.adoption_depth
        FROM feature_adoption fa
    """,

    # ── Payments ──

    "v_invoices_clean": """
        CREATE VIEW v_invoices_clean AS
        SELECT i.*
        FROM invoices i
        WHERE i.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000)
    """,

    "v_payments_clean": """
        CREATE VIEW v_payments_clean AS
        SELECT p.*
        FROM payments p
        WHERE p.invoice_id IN (SELECT invoice_id FROM invoices)
          AND p.payment_date <= '2025-12-31'
    """,

    # ── CRM ──

    "v_activities_clean": """
        CREATE VIEW v_activities_clean AS
        SELECT
            a.activity_id,
            a.account_id,
            a.activity_date,
            a.activity_type,
            a.subject,
            TRIM(a.notes) AS notes,
            CASE WHEN a.notes IS NULL THEN 'No notes recorded'
                 ELSE TRIM(a.notes) END AS notes_display,
            a.outcome
        FROM activities a
        WHERE a.activity_date <= '2025-12-31'
    """,

    "v_opportunities_clean": """
        CREATE VIEW v_opportunities_clean AS
        SELECT
            o.opp_id,
            o.account_id,
            o.opp_name,
            o.stage,
            o.amount,
            o.close_date,
            o.probability,
            o.product_interest
        FROM opportunities o
        WHERE o.close_date <= '2025-12-31'
    """,
}


def _create_clean_views(conn):
    """Create all clean views, dropping existing ones first."""
    for view_name, ddl in _CLEAN_VIEWS.items():
        conn.execute(f"DROP VIEW IF EXISTS {view_name}")
        conn.execute(ddl)


# ═══════════════════════════════════════════════════════════════
# DATA QUALITY FLAGS TABLE (Section 4 of governance.md)
# ═══════════════════════════════════════════════════════════════

def _create_flags_table(conn):
    """Create and populate the data_quality_flags table."""
    conn.execute("DROP TABLE IF EXISTS data_quality_flags")
    conn.execute("""
        CREATE TABLE data_quality_flags (
            flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            record_rowid INTEGER,
            flag_type TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    flags = []

    # FLG-001: Numeric outliers in order_items.unit_price
    try:
        stats = conn.execute("""
            SELECT AVG(unit_price), AVG(unit_price * unit_price)
            FROM order_items WHERE unit_price > 0
        """).fetchone()
        if stats[0] is not None:
            mean = stats[0]
            variance = stats[1] - (mean ** 2)
            std = variance ** 0.5 if variance > 0 else 0
            upper = mean + 3 * std

            rows = conn.execute("""
                SELECT rowid, line_id FROM order_items
                WHERE unit_price > ? AND unit_price > 0
            """, (upper,)).fetchall()
            for rowid, line_id in rows:
                flags.append(("FLG-001", "order_items", line_id, rowid, "outlier",
                              f"unit_price exceeds 3 std devs (threshold: {upper:.2f})"))
    except Exception:
        pass

    # FLG-002: Near-duplicate customers (from _messiness_duplicates tracking table)
    try:
        # Flag the duplicate records
        rows = conn.execute("""
            SELECT md.duplicate_customer_id, c.rowid
            FROM _messiness_duplicates md
            JOIN customers c ON md.duplicate_customer_id = c.customer_id
        """).fetchall()
        for dup_id, rowid in rows:
            flags.append(("FLG-002", "customers", dup_id, rowid, "duplicate_suspect",
                          "Near-duplicate record (tracked in _messiness_duplicates)"))

        # Flag originals that have duplicates
        originals = conn.execute("""
            SELECT md.original_customer_id, c.rowid
            FROM _messiness_duplicates md
            JOIN customers c ON md.original_customer_id = c.customer_id
        """).fetchall()
        for orig_id, rowid in originals:
            flags.append(("FLG-002", "customers", orig_id, rowid, "duplicate_suspect",
                          "Original record has one or more near-duplicates"))

        # Also flag by name + region clustering (catches any the tracking table misses)
        clusters = conn.execute("""
            SELECT UPPER(TRIM(company_name)) AS norm, region,
                   GROUP_CONCAT(customer_id) AS ids, COUNT(*) AS cnt
            FROM customers
            WHERE company_name IS NOT NULL
            GROUP BY UPPER(TRIM(company_name)), region
            HAVING COUNT(*) > 1
        """).fetchall()
        already_flagged = {r[0] for r in rows + originals}
        for norm, region, ids_str, cnt in clusters:
            for cid_str in ids_str.split(","):
                cid = int(cid_str.strip())
                if cid not in already_flagged:
                    row = conn.execute(
                        "SELECT rowid FROM customers WHERE customer_id = ?", (cid,)
                    ).fetchone()
                    if row:
                        flags.append(("FLG-002", "customers", cid, row[0], "duplicate_suspect",
                                      f"Matches duplicate cluster: {norm} / {region}"))
    except Exception:
        pass

    # FLG-003: Truncated notes in activities
    try:
        rows = conn.execute("""
            SELECT rowid, activity_id, notes FROM activities
            WHERE notes IS NOT NULL
            AND length(notes) > 10
        """).fetchall()
        for rowid, activity_id, notes in rows:
            if notes and len(notes) > 10:
                stripped = notes.strip()
                if stripped:
                    last_char = stripped[-1]
                    # Likely truncated if ends mid-word on an uncommon ending letter
                    if (last_char.isalpha() and
                            last_char not in ("c", "g", "d", "s", "t", "n", "e", "y")):
                        flags.append(("FLG-003", "activities", activity_id, rowid,
                                      "possibly_truncated",
                                      "Notes may be truncated (ends mid-word)"))
    except Exception:
        pass

    # FLG-004: Mojibake in company names
    mojibake_patterns = ["Ã¼", "Ã¶", "Ã¤", "Ã©", "Ã¨", "Ã±", "ÃŸ", "Ã¸", "Ã¥", "Ã§"]
    try:
        for pattern in mojibake_patterns:
            rows = conn.execute("""
                SELECT rowid, customer_id FROM customers
                WHERE company_name LIKE ?
            """, (f"%{pattern}%",)).fetchall()
            for rowid, cid in rows:
                flags.append(("FLG-004", "customers", cid, rowid, "encoding_issue",
                              f"Company name contains mojibake pattern: {pattern}"))
    except Exception:
        pass

    # FLG-005: Orphaned orders (customer_id doesn't match any real customer)
    try:
        rows = conn.execute("""
            SELECT o.rowid, o.order_id, o.customer_id
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            WHERE c.customer_id IS NULL
        """).fetchall()
        for rowid, order_id, ghost_cid in rows:
            flags.append(("FLG-005", "orders", order_id, rowid, "orphaned_fk",
                          f"customer_id={ghost_cid} does not match any customer"))
    except Exception:
        pass

    # FLG-006: Orphaned payments (invoice_id doesn't match any real invoice)
    try:
        rows = conn.execute("""
            SELECT p.rowid, p.payment_id, p.invoice_id
            FROM payments p
            LEFT JOIN invoices i ON p.invoice_id = i.invoice_id
            WHERE i.invoice_id IS NULL
        """).fetchall()
        for rowid, payment_id, ghost_inv in rows:
            flags.append(("FLG-006", "payments", payment_id, rowid, "orphaned_fk",
                          f"invoice_id={ghost_inv} does not match any invoice"))
    except Exception:
        pass

    # FLG-007: Whitespace issues in company names
    try:
        rows = conn.execute("""
            SELECT rowid, customer_id FROM customers
            WHERE company_name IS NOT NULL
            AND (company_name LIKE ' %' OR company_name LIKE '% '
                 OR company_name LIKE '%  %')
        """).fetchall()
        for rowid, cid in rows:
            flags.append(("FLG-007", "customers", cid, rowid, "whitespace_issue",
                          "Company name has leading/trailing/double whitespace"))
    except Exception:
        pass

    # FLG-008: Future date typos
    try:
        for table, col, pk in [("orders", "order_date", "order_id"),
                                ("activities", "activity_date", "activity_id")]:
            rows = conn.execute(f"""
                SELECT rowid, {pk}, {col} FROM {table}
                WHERE {col} > '2025-12-31'
            """).fetchall()
            for rowid, record_id, date_val in rows:
                flags.append(("FLG-008", table, record_id, rowid, "future_date",
                              f"{col}={date_val} is beyond data range"))
    except Exception:
        pass

    # Bulk insert
    if flags:
        conn.executemany("""
            INSERT INTO data_quality_flags
                (rule_id, table_name, record_id, record_rowid, flag_type, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, flags)

    return len(flags)


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def apply_governance(conn):
    """
    Apply all governance rules to the database:
    1. Create region_mapping lookup table
    2. Create clean views (v_*_clean)
    3. Create and populate data_quality_flags table
    """
    print("  Creating region mapping table...")
    _create_region_mapping_table(conn)

    print("  Creating clean views...")
    _create_clean_views(conn)
    print(f"    {len(_CLEAN_VIEWS)} views created")

    print("  Populating data quality flags...")
    flag_count = _create_flags_table(conn)
    print(f"    {flag_count:,} flags generated")

    conn.commit()

    # Summary by rule
    rows = conn.execute("""
        SELECT rule_id, flag_type, COUNT(*)
        FROM data_quality_flags
        GROUP BY rule_id, flag_type
        ORDER BY rule_id
    """).fetchall()

    for rule_id, flag_type, count in rows:
        print(f"    {rule_id} ({flag_type}): {count:,}")

    # Verify clean views return data
    print("\n  Verifying clean views...")
    for view_name in _CLEAN_VIEWS:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
            # Derive raw table name for comparison
            raw_table = (view_name
                         .replace("v_", "", 1)
                         .replace("_clean", ""))
            try:
                raw_count = conn.execute(
                    f"SELECT COUNT(*) FROM {raw_table}"
                ).fetchone()[0]
                excluded = raw_count - count
                print(f"    {view_name}: {count:,} rows "
                      f"({excluded:,} excluded from {raw_count:,})")
            except Exception:
                print(f"    {view_name}: {count:,} rows")
        except Exception as e:
            print(f"    {view_name}: ERROR - {e}")


# ── CLI entry point ──
if __name__ == "__main__":
    db_path = "otacon.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found. Run `python -m generate_otacon` first.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    apply_governance(conn)
    conn.close()
    print("\nDone.")