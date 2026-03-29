"""
load_to_bigquery.py — Upload otacon.db tables and clean views to BigQuery
===========================================================================
Run once after generating otacon.db. Creates a BigQuery dataset and loads
all tables + materialized clean views.

Usage:
    pip install google-cloud-bigquery db-dtypes pandas
    python load_to_bigquery.py --project YOUR_PROJECT_ID --dataset otacon

Prerequisites:
    - gcloud CLI installed and authenticated (gcloud auth application-default login)
    - A GCP project with BigQuery API enabled
    - otacon.db in the current directory
"""

import sqlite3
import argparse
import pandas as pd
from google.cloud import bigquery


# Tables to upload directly
TABLES = [
    "customers", "products", "orders", "order_items", "returns",
    "saas_customers", "mrr_movements", "support_tickets",
    "saas_users", "usage_events", "feature_adoption",
    "invoices", "payments",
    "accounts", "activities", "opportunities",
    "customer_xref", "customer_360",
    "data_quality_flags", "_messiness_duplicates", "region_mapping",
]

# Clean views to materialize as tables (BigQuery doesn't use SQLite views)
CLEAN_VIEWS = [
    "v_customers_clean", "v_orders_clean", "v_order_items_clean",
    "v_returns_clean", "v_saas_customers_clean", "v_support_tickets_clean",
    "v_usage_events_clean", "v_feature_adoption_clean",
    "v_invoices_clean", "v_payments_clean",
    "v_activities_clean", "v_opportunities_clean",
]


def load_table(sqlite_conn, bq_client, dataset_ref, table_name, source_name=None):
    """Load a SQLite table/view into BigQuery."""
    source = source_name or table_name
    # Clean up table name for BigQuery (no leading underscores in some contexts)
    bq_table_name = table_name.lstrip("_") if table_name.startswith("_") else table_name

    try:
        df = pd.read_sql_query(f"SELECT * FROM {source}", sqlite_conn)
    except Exception as e:
        print(f"  SKIP {source}: {e}")
        return

    if df.empty:
        print(f"  SKIP {source}: empty")
        return

    table_id = f"{dataset_ref}.{bq_table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )

    job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # Wait for completion

    loaded = bq_client.get_table(table_id)
    print(f"  {bq_table_name}: {loaded.num_rows:,} rows loaded")


def main():
    parser = argparse.ArgumentParser(description="Load otacon.db into BigQuery")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--dataset", default="otacon", help="BigQuery dataset name")
    parser.add_argument("--db", default="otacon.db", help="Path to SQLite database")
    parser.add_argument("--location", default="US", help="BigQuery dataset location")
    args = parser.parse_args()

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(args.db)
    print(f"Connected to {args.db}")

    # Connect to BigQuery
    bq_client = bigquery.Client(project=args.project)

    # Create dataset if it doesn't exist
    dataset_ref = f"{args.project}.{args.dataset}"
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = args.location
    try:
        bq_client.create_dataset(dataset, exists_ok=True)
        print(f"Dataset: {dataset_ref}")
    except Exception as e:
        print(f"Dataset error: {e}")
        return

    # Load raw tables
    print(f"\n{'='*50}")
    print("Loading raw tables...")
    print(f"{'='*50}")
    for table in TABLES:
        load_table(sqlite_conn, bq_client, dataset_ref, table)

    # Materialize clean views as tables
    print(f"\n{'='*50}")
    print("Materializing clean views...")
    print(f"{'='*50}")
    for view in CLEAN_VIEWS:
        load_table(sqlite_conn, bq_client, dataset_ref, view, source_name=view)

    sqlite_conn.close()

    # Summary
    tables = list(bq_client.list_tables(dataset_ref))
    print(f"\n{'='*50}")
    print(f"Done. {len(tables)} tables in {dataset_ref}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
