"""
Otacon Inc. — Synthetic Data Generator
===================================================
Usage:
  pip install faker
  python -m generate_otacon

Output:
  otacon.db (SQLite, ~100+ MB)
  Five data layers + bridge tables + clean views
  Three years of data (2023-2025) with engineered storylines
  Controlled data quality issues + governance layer
"""

import sqlite3
import random
import os
import sys

# Add the package directory to path so non-relative imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH, RANDOM_SEED
from schema import create_tables
from generators import (
    generate_customers, generate_products, generate_orders_and_items, generate_returns,
    generate_saas_customers, generate_mrr_movements, generate_support_tickets,
    generate_saas_users, generate_usage_events, generate_feature_adoption, compute_usage_scores,
    generate_payments,
    generate_crm,
    build_bridge_tables,
)
from validation import validate
from messiness import apply_messiness
from governance import apply_governance


def main():
    random.seed(RANDOM_SEED)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    print("=" * 65)
    print("  OTACON INC. — Synthetic Data Generator")
    print("  3 years × 5 layers × engineered storylines")
    print("  + controlled messiness + governance layer")
    print("=" * 65)

    print("\n[1/9] Creating tables...")
    create_tables(conn)

    print("\n[2/9] Layer 1: E-Commerce...")
    generate_customers(conn)
    generate_products(conn)
    generate_orders_and_items(conn)
    generate_returns(conn)

    print("\n[3/9] Layer 2: SaaS...")
    generate_saas_customers(conn)
    churn_map = generate_mrr_movements(conn)
    generate_support_tickets(conn, churn_map)

    print("\n[4/9] Layer 3: Product Analytics...")
    user_map = generate_saas_users(conn)
    generate_usage_events(conn, user_map, churn_map)
    generate_feature_adoption(conn)
    compute_usage_scores(conn, churn_map)

    print("\n[5/9] Layer 4: Payments...")
    generate_payments(conn)

    print("\n[6/9] Layer 5: CRM...")
    generate_crm(conn, churn_map)

    print("\n[7/9] Bridge Layer...")
    build_bridge_tables(conn)

    print("\n[8/9] Applying data quality degradation...")
    messiness_stats = apply_messiness(conn)

    print("\n[9/9] Applying governance layer...")
    apply_governance(conn)

    validate(conn)

    conn.close()
    size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"\n{'=' * 65}")
    print(f"  Database size: {size_mb:.1f} MB")
    print(f"  File: {os.path.abspath(DB_PATH)}")
    print(f"  Clean views: query v_*_clean tables for governed data")
    print(f"  Raw tables: query directly for data quality analysis")
    print(f"  Flags: query data_quality_flags for flagged records")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
