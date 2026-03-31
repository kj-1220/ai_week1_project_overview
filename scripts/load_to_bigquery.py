"""
load_to_bigquery.py — Upload otacon.db tables and clean views to BigQuery
===========================================================================
Run once after generating otacon.db. Creates a BigQuery dataset and loads
all tables + materialized clean views with correct column types.

Usage:
    pip install google-cloud-bigquery db-dtypes pandas pyarrow
    python scripts/load_to_bigquery.py --project otacon-inc --dataset otacon

Prerequisites:
    - gcloud CLI authenticated: gcloud auth application-default login
    - A GCP project with BigQuery API enabled
    - otacon.db in the project root (or pass --db path/to/otacon.db)
"""

import sqlite3
import argparse
import pandas as pd
from google.cloud import bigquery


# ---------------------------------------------------------------------------
# Tables to upload directly
# ---------------------------------------------------------------------------
TABLES = [
    "customers", "products", "orders", "order_items", "returns",
    "saas_customers", "mrr_movements", "support_tickets",
    "saas_users", "usage_events", "feature_adoption",
    "invoices", "payments",
    "accounts", "activities", "opportunities",
    "customer_xref", "customer_360",
    "data_quality_flags", "_messiness_duplicates", "region_mapping",
]

# Clean views to materialize as BigQuery tables
CLEAN_VIEWS = [
    "v_customers_clean", "v_orders_clean", "v_order_items_clean",
    "v_returns_clean", "v_saas_customers_clean", "v_support_tickets_clean",
    "v_usage_events_clean", "v_feature_adoption_clean",
    "v_invoices_clean", "v_payments_clean",
    "v_activities_clean", "v_opportunities_clean",
]

# ---------------------------------------------------------------------------
# Explicit DATE columns per table.
# Every column listed here will be cast to BQ DATE type.
# All other columns use autodetect (INTEGER/FLOAT/STRING land correctly).
# ---------------------------------------------------------------------------
DATE_COLUMNS: dict[str, list[str]] = {
    "customers":               ["signup_date", "created_date"],
    "products":                ["created_date"],
    "orders":                  ["order_date", "ship_date", "created_date"],
    "order_items":             [],
    "returns":                 ["return_date", "created_date"],
    "saas_customers":          ["signup_date", "created_date"],
    "mrr_movements":           ["movement_date"],
    "support_tickets":         ["created_date", "resolved_date"],
    "saas_users":              ["signup_date", "created_date"],
    "usage_events":            ["event_date"],
    "feature_adoption":        ["activity_date", "created_date"],
    "invoices":                ["invoice_date", "due_date", "created_date"],
    "payments":                ["payment_date", "created_date"],
    "accounts":                ["created_date"],
    "activities":              ["activity_date", "created_date"],
    "opportunities":           ["created_date", "close_date"],
    "customer_xref":           ["created_date"],
    "customer_360":            [],
    "data_quality_flags":      ["created_date"],
    "_messiness_duplicates":   [],
    "region_mapping":          [],
    # Clean views inherit the same date columns as their base tables
    "v_customers_clean":       ["signup_date", "created_date"],
    "v_orders_clean":          ["order_date", "ship_date", "created_date"],
    "v_order_items_clean":     [],
    "v_returns_clean":         ["return_date", "created_date"],
    "v_saas_customers_clean":  ["signup_date", "created_date"],
    "v_support_tickets_clean": ["created_date", "resolved_date"],
    "v_usage_events_clean":    ["event_date"],
    "v_feature_adoption_clean":["activity_date", "created_date"],
    "v_invoices_clean":        ["invoice_date", "due_date", "created_date"],
    "v_payments_clean":        ["payment_date", "created_date"],
    "v_activities_clean":      ["activity_date", "created_date"],
    "v_opportunities_clean":   ["created_date", "close_date"],
}


def coerce_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    """
    Convert date columns from SQLite string (YYYY-MM-DD) to datetime.date objects.
    BigQuery's load_table_from_dataframe maps Python date objects -> BQ DATE.
    Null/unparseable values become NaT, which loads as NULL.
    """
    df = df.copy()
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


def build_schema(df: pd.DataFrame, date_cols: list[str]) -> list[bigquery.SchemaField]:
    """
    Build a full explicit BQ schema from the DataFrame.
    Date columns get type DATE; everything else is inferred from pandas dtype.
    Providing a full schema (not just date overrides) prevents autodetect from
    second-guessing any column.
    """
    date_set = set(date_cols)
    fields = []
    for col in df.columns:
        if col in date_set:
            bq_type = "DATE"
        else:
            dtype = str(df[col].dtype)
            if "int" in dtype:
                bq_type = "INTEGER"
            elif "float" in dtype:
                bq_type = "FLOAT"
            elif dtype == "bool":
                bq_type = "BOOLEAN"
            else:
                bq_type = "STRING"
        fields.append(bigquery.SchemaField(col, bq_type, mode="NULLABLE"))
    return fields


def load_table(
    sqlite_conn: sqlite3.Connection,
    bq_client: bigquery.Client,
    dataset_ref: str,
    table_name: str,
    source_name: str | None = None,
) -> None:
    """Load one SQLite table/view into BigQuery with correct types."""
    source = source_name or table_name
    bq_table_name = table_name.lstrip("_") if table_name.startswith("_") else table_name
    table_id = f"{dataset_ref}.{bq_table_name}"

    try:
        df = pd.read_sql_query(f'SELECT * FROM "{source}"', sqlite_conn)
    except Exception as e:
        print(f"  SKIP {source}: {e}")
        return

    if df.empty:
        print(f"  SKIP {source}: empty")
        return

    date_cols = DATE_COLUMNS.get(table_name, [])
    df = coerce_dates(df, date_cols)
    schema = build_schema(df, date_cols)

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
    )

    job = bq_client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()

    loaded = bq_client.get_table(table_id)
    date_note = f"  [DATE: {', '.join(date_cols)}]" if date_cols else ""
    print(f"  {bq_table_name}: {loaded.num_rows:,} rows{date_note}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load otacon.db into BigQuery")
    parser.add_argument("--project",  default="otacon-inc",  help="GCP project ID")
    parser.add_argument("--dataset",  default="otacon",      help="BigQuery dataset name")
    parser.add_argument("--db",       default="otacon.db",   help="Path to SQLite database")
    parser.add_argument("--location", default="US",          help="BigQuery dataset location")
    args = parser.parse_args()

    sqlite_conn = sqlite3.connect(args.db)
    print(f"Connected to {args.db}")

    bq_client = bigquery.Client(project=args.project)
    dataset_ref = f"{args.project}.{args.dataset}"

    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = args.location
    bq_client.create_dataset(dataset, exists_ok=True)
    print(f"Dataset: {dataset_ref}\n")

    print("Loading raw tables...")
    print("=" * 52)
    for table in TABLES:
        load_table(sqlite_conn, bq_client, dataset_ref, table)

    print("\nMaterializing clean views...")
    print("=" * 52)
    for view in CLEAN_VIEWS:
        load_table(sqlite_conn, bq_client, dataset_ref, view, source_name=view)

    sqlite_conn.close()

    all_tables = list(bq_client.list_tables(dataset_ref))
    print(f"\nDone. {len(all_tables)} tables in {dataset_ref}")


if __name__ == "__main__":
    main()
