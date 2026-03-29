# Otacon Inc. — Data Governance Policies & Procedures

**Effective:** Week 1 (applies to all downstream projects, Weeks 2–12)  
**Scope:** All queries, dashboards, prompts, and agents that touch `otacon.db`  
**Owner:** You — the analyst who built the data and is responsible for its integrity

---

## Purpose

This document defines how messy, incomplete, and inconsistent data in `otacon.db` is handled. Every dashboard, notebook, prompt, and agent in this portfolio follows these rules. No one reinvents data cleaning decisions on a per-query basis.

If a rule isn't in this document, the default is: **surface the issue to the user, don't silently hide it.**

---

## 1. Exclusion Rules

These records are filtered out of all standard analysis. They are not deleted from the database — they are excluded at query time using WHERE clauses.

All primary keys in `otacon.db` are INTEGER AUTOINCREMENT. Orphaned and duplicate records are identified by numeric range or tracking table, not string patterns.

| Rule ID | Table | Condition | Reason | Standard Filter |
|---------|-------|-----------|--------|-----------------|
| EX-001 | `order_items` | `unit_price = 0` | Test orders or comps — not real revenue | `WHERE unit_price > 0` |
| EX-002 | `order_items` | `unit_price < 0` | Miscoded refunds — should be in returns table | `WHERE unit_price > 0` |
| EX-003 | `orders` | `customer_id` not in `customers` table | Orphaned records — parent customer doesn't exist (ghost IDs ≥ 90001) | `WHERE customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000)` |
| EX-004 | `payments` | `invoice_id` not in `invoices` table | Orphaned records — parent invoice doesn't exist | `WHERE invoice_id IN (SELECT invoice_id FROM invoices)` |
| EX-005 | `orders` | `order_date > '2025-12-31'` | Future date typos (e.g., 2052, 2042) | `WHERE order_date <= '2025-12-31'` |
| EX-006 | `activities` | `activity_date > '2025-12-31'` | Future date typos | `WHERE activity_date <= '2025-12-31'` |
| EX-007 | `payments` | `payment_date > '2025-12-31'` | Future date typos | `WHERE payment_date <= '2025-12-31'` |
| EX-008 | `customers` | `customer_id` in `_messiness_duplicates` table | Known duplicates — use original record only | `WHERE customer_id NOT IN (SELECT duplicate_customer_id FROM _messiness_duplicates)` |

**When to override:** If analysis specifically requires examining excluded records (e.g., "how many test orders exist?" or "show me the duplicate clusters"), the exclusion can be lifted for that query. The dashboard or report must clearly label the data as "including excluded records."

---

## 2. Normalization Rules

These transformations are applied before any grouping, joining, or comparison. They do not modify the underlying data — they are applied at query time or in a clean views layer.

### 2.1 Text Normalization

| Rule ID | Field | Transformation | Example |
|---------|-------|---------------|---------|
| NRM-001 | `customers.company_name` | `UPPER(TRIM(company_name))` | "  Acme Corp. " → "ACME CORP." |
| NRM-002 | `activities.notes` | `TRIM(notes)` | Remove leading/trailing whitespace |

> **Note:** The `customers` table does not have `email`, `phone`, or `website` columns. The only user-facing email field is `saas_users.email`.

### 2.2 Region Standardization

All region values must be mapped to one of four canonical values before any GROUP BY or filter operation.

| Canonical Value | Accepted Variants |
|----------------|-------------------|
| North America | "N. America", "NA", "north america", "North_America", "NorthAmerica" |
| Europe | "EU", "europe", "EMEA", "Europe " (trailing space) |
| APAC | "Asia Pacific", "apac", "Asia-Pacific", "AP" |
| LATAM | "Latin America", "latam", "LATAM " (trailing space), "South America" |

**Implementation:** A `region_mapping` table is created by `governance.py`. Clean views use it via subquery. For ad-hoc queries, use a CASE statement:

```sql
CASE 
    WHEN UPPER(TRIM(region)) IN ('NORTH AMERICA', 'N. AMERICA', 'NA', 'NORTH_AMERICA', 'NORTHAMERICA') THEN 'North America'
    WHEN UPPER(TRIM(region)) IN ('EUROPE', 'EU', 'EMEA') THEN 'Europe'
    WHEN UPPER(TRIM(region)) IN ('APAC', 'ASIA PACIFIC', 'ASIA-PACIFIC', 'AP') THEN 'APAC'
    WHEN UPPER(TRIM(region)) IN ('LATAM', 'LATIN AMERICA', 'SOUTH AMERICA') THEN 'LATAM'
    ELSE 'Unknown'
END AS region_clean
```

### 2.3 Numeric Normalization

| Rule ID | Field | Transformation | Reason |
|---------|-------|---------------|--------|
| NRM-003 | `order_items.unit_price` | Cap at 99th percentile for AVG calculations | Prevents decimal-shift outliers ($14,999) from skewing averages |
| NRM-004 | `orders.discount_pct` | `COALESCE(discount_pct, 0)` | NULL discount means no discount, not unknown discount |

> **Note:** `discount_pct` is on the `orders` table, not on `order_items`. The `order_items` table has `unit_price`, `quantity`, and `line_total`.

---

## 3. Imputation Rules

How to handle NULL values. The goal is consistency — the same NULL is treated the same way everywhere.

| Rule ID | Table.Column | NULL Means | Imputation | Display Value |
|---------|-------------|------------|------------|---------------|
| IMP-001 | `orders.ship_date` | Unfulfilled or digital product | Do not impute — treat as unfulfilled | "Pending" |
| IMP-002 | `returns.reason` | Not captured by customer service | Do not impute | "Not recorded" |
| IMP-003 | `support_tickets.resolved_date` | Ticket still open or abandoned | Do not impute | "Open" |
| IMP-004 | `support_tickets.resolution_hours` | No resolution recorded | Do not impute | "N/A" |
| IMP-005 | `activities.notes` | Sales rep didn't enter notes | Do not impute | "No notes recorded" |
| IMP-006 | `accounts.last_contact_date` | No contact date recorded | Do not impute | "Not on file" |
| IMP-007 | `accounts.next_renewal_date` | Renewal date not set | Do not impute | "TBD" |
| IMP-008 | `usage_events.session_id` | Orphaned event — no session context | Do not impute — flag as orphaned | "No session" |
| IMP-009 | `usage_events.duration_seconds` | Duration not recorded | Do not impute | "N/A" |
| IMP-010 | `feature_adoption.last_used_date` | Feature adopted but last use not tracked | Do not impute | "Unknown" |

**General principle:** Do not impute categorical values. Do not guess an industry, a return reason, or a close date. If it's missing, say it's missing.

**Impact on aggregations:**
- `COUNT(*)` counts all rows including those with NULLs in other columns
- `COUNT(column)` counts only non-NULL values — use this when reporting "X out of Y have data"
- `AVG(column)` automatically excludes NULLs — this is usually the correct behavior
- For revenue calculations, NULL amounts must be excluded explicitly and the exclusion must be noted

---

## 4. Flagging Rules

These records are suspicious but not excluded. They get a flag so dashboards can offer "clean" vs "all data" views. Flags are stored in the `data_quality_flags` table, populated by `governance.py`.

| Rule ID | Table | Condition | Flag Type | Action |
|---------|-------|-----------|-----------|--------|
| FLG-001 | `order_items` | `unit_price > (mean + 3*stddev)` | `outlier` | Show in dashboards with toggle; exclude from AVG by default |
| FLG-002 | `customers` | Tracked in `_messiness_duplicates` or matches another customer on `UPPER(TRIM(company_name))` + `region` | `duplicate_suspect` | Surface in data quality panel; do not auto-merge |
| FLG-003 | `activities` | `notes` does not end in sentence-ending punctuation and length > 10 | `possibly_truncated` | Note in any summarization: "This note may be incomplete" |
| FLG-004 | `customers` | `company_name` contains mojibake patterns (Ã¼, Ã¶, etc.) | `encoding_issue` | Surface in data quality panel; use original value in reports |
| FLG-005 | `orders` | `customer_id` not found in `customers` table | `orphaned_fk` | Excluded by clean views; counted in data quality panel |
| FLG-006 | `payments` | `invoice_id` not found in `invoices` table | `orphaned_fk` | Excluded by clean views; counted in data quality panel |
| FLG-007 | `customers` | `company_name` has leading/trailing whitespace or double spaces | `whitespace_issue` | Apply TRIM before display; note in data quality panel |
| FLG-008 | `orders`, `activities` | Date columns contain values beyond `2025-12-31` | `future_date` | Excluded by clean views; counted in data quality panel |

**Implementation:** The `data_quality_flags` table is populated by `governance.py` during Step 9 of the generator pipeline. Each flag has a `rule_id`, `table_name`, `record_id`, `flag_type`, and `description`. Query it independently for data quality reporting.

---

## 5. Clean Views

These SQL views implement the exclusion, normalization, and imputation rules above. All dashboards and agents should query these views instead of the raw tables.

### 5.1 View Definitions

**`v_customers_clean`** — Canonical customer records with normalized fields, excluding known duplicates and orphans.

```sql
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
AND c.customer_id <= 8000;
```

**`v_orders_clean`** — Excludes orphaned and future-dated orders.

```sql
CREATE VIEW v_orders_clean AS
SELECT o.*
FROM orders o
WHERE o.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000)
  AND o.order_date <= '2025-12-31';
```

**`v_order_items_clean`** — Excludes test orders, negative amounts, and extreme outliers.

```sql
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
  AND o.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000);
```

**`v_returns_clean`** — Handles NULL reasons, excludes orphaned orders.

```sql
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
  AND o.order_date <= '2025-12-31';
```

**`v_payments_clean`** — Excludes orphaned and future-dated payments.

```sql
CREATE VIEW v_payments_clean AS
SELECT p.*
FROM payments p
WHERE p.invoice_id IN (SELECT invoice_id FROM invoices)
  AND p.payment_date <= '2025-12-31';
```

**`v_support_tickets_clean`** — Adds resolution display for NULL resolved_date.

```sql
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
FROM support_tickets st;
```

**`v_activities_clean`** — Excludes future-dated activities, trims whitespace.

```sql
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
WHERE a.activity_date <= '2025-12-31';
```

**`v_opportunities_clean`** — Filters to data range.

```sql
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
WHERE o.close_date <= '2025-12-31';
```

**`v_usage_events_clean`** — Excludes orphaned events (no session).

```sql
CREATE VIEW v_usage_events_clean AS
SELECT *
FROM usage_events
WHERE session_id IS NOT NULL;
```

**`v_feature_adoption_clean`** — All feature adoption records (no exclusions needed).

```sql
CREATE VIEW v_feature_adoption_clean AS
SELECT *
FROM feature_adoption;
```

**`v_saas_customers_clean`** — Excludes customers linked to duplicate parent records.

```sql
CREATE VIEW v_saas_customers_clean AS
SELECT sc.*
FROM saas_customers sc
WHERE sc.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000);
```

**`v_invoices_clean`** — Excludes invoices linked to orphaned customers.

```sql
CREATE VIEW v_invoices_clean AS
SELECT i.*
FROM invoices i
WHERE i.customer_id IN (SELECT customer_id FROM customers WHERE customer_id <= 8000);
```

### 5.2 When to Use Raw Tables vs Clean Views

| Scenario | Use |
|----------|-----|
| Building dashboards | Clean views (`v_*_clean`) |
| Writing prompts that reference data | Clean views |
| Agent-generated SQL | Clean views |
| Data quality profiling / auditing | Raw tables |
| Investigating specific anomalies | Raw tables |
| Counting total records including bad data | Raw tables |
| Measuring data quality improvement over time | Raw tables (compare against flags) |

---

## 6. Data Quality Reporting

### 6.1 In Week 1 (Validation Step)

After `messiness.py` runs, the validation output includes a data quality section:

- Completeness: NULL rate per column, flagged if > 5%
- Orphaned FKs: count and percentage per relationship (`orders.customer_id`, `payments.invoice_id`)
- Outliers: count per numeric column beyond 3 standard deviations
- Encoding: count of mojibake patterns detected
- Future dates: count per date column (`orders.order_date`, `activities.activity_date`)
- Duplicates: number of records in `_messiness_duplicates` table

This output is the **baseline audit**. Save it alongside the database.

### 6.2 In Week 3 (Dashboard Library)

Each dashboard page includes a data quality callout relevant to that page's data:

- **Executive Summary:** "Revenue excludes X test orders and Y orphaned records per governance policy EX-001 through EX-004"
- **E-Commerce:** "Z orders have $0 line items (excluded). W returns have no reason recorded."
- **SaaS Analytics:** "X tickets have no resolution date (treated as open). Y accounts flagged as possible duplicates."
- **Product Usage:** "X usage events have no session ID (orphaned). Feature adoption `last_used_date` is missing for Y records."
- **Financial Health:** "X payments have future dates (excluded). Y payments are linked to nonexistent invoices (excluded)."

These are not separate pages. They are callout sections within each existing page.

### 6.3 In Weeks 4–6 (Agents)

Agent system prompts include governance rules:

```
DATA GOVERNANCE RULES — follow these for every query:
1. Query clean views (v_*_clean), not raw tables
2. If a clean view doesn't exist for a table, apply exclusion rules EX-001 through EX-008
3. Use COALESCE for display of NULL fields per imputation rules IMP-001 through IMP-010
4. When reporting averages on financial fields, exclude outliers (FLG-001) by default
5. When reporting record counts, note how many records were excluded and why
6. If asked about data quality specifically, query raw tables and report against governance rules
```

---

## 7. Change Management

If a governance rule needs to change:

1. Update this document first
2. Update the corresponding clean view definition in `governance.py`
3. Update any agent system prompts that reference the rule
4. Note the change and date at the bottom of this document

### Change Log

| Date | Rule | Change | Reason |
|------|------|--------|--------|
| Week 1 | All | Initial governance policies established | Baseline |
| Week 1 | EX-003, EX-004, EX-008 | Updated from string pattern matching to integer-based exclusions | All PKs are INTEGER AUTOINCREMENT; orphans use ghost IDs ≥ 90001; duplicates tracked in `_messiness_duplicates` |
| Week 1 | NRM-002, NRM-003 | Removed email/phone normalization rules | `customers` table has no `email`, `phone`, or `website` columns |
| Week 1 | IMP-001–012 | Renumbered to IMP-001–010; removed rules for nonexistent columns | Aligned with actual nullable columns in schema |
| Week 1 | FLG-001–006 | Renumbered to FLG-001–008; added orphan FK and future date flags | Expanded to cover all messiness categories |
| Week 1 | Section 5 | Rewrote all clean view SQL; added views for `feature_adoption`, `invoices`, `saas_customers` | Aligned with actual schema column and table names |