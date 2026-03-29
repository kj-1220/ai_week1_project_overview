# Otacon Inc. — Synthetic Enterprise Data Platform

Week 1 project for an AI Engineering learning plan. A complete synthetic data generator that produces a realistic 93 MB SQLite database with five interconnected business data layers, engineered storylines, controlled data quality issues, and a governance layer — designed as a foundation for EDA, dashboards, semantic layers, and AI agents in later weeks.

## What This Builds

**`otacon.db`** — 3 years of enterprise data (2023–2025) across 18 tables:

| Layer | Tables | Key Records |
|-------|--------|-------------|
| E-Commerce | `customers`, `products`, `orders`, `order_items`, `returns` | 8,000 customers, ~70K orders, ~235K line items |
| SaaS | `saas_customers`, `mrr_movements`, `support_tickets` | 2,000 SaaS accounts, MRR tracking, 5,600 tickets |
| Product Analytics | `saas_users`, `usage_events`, `feature_adoption` | 11,600 users, 1M+ events |
| Payments | `invoices`, `payments` | 66K invoice/payment pairs |
| CRM | `accounts`, `activities`, `opportunities` | 2,000 accounts, 7,500 activities, 2,000 opps |
| Bridge | `customer_xref`, `customer_360` | Cross-layer identity resolution |

### Engineered Storylines
The data contains 10 business narratives baked into the numbers — discoverable through analysis:

- **Q2 2025 Tariff Volatility** — hardware/consumable orders drop ~15%, payment terms stretch
- **Q3 2023 EU Payment Delays** — European region days-to-pay spikes +19 days
- **Q4 2025 AI Insights Launch** — new feature module, adoption ramps 12% → 35%
- **Q2 2024 Enterprise Churn** — two large accounts churn after 90-day usage decline
- And 6 more (see `config.py` STORYLINES dict)

### Messiness Layer
25 rules inject realistic data quality problems (separate seed for reproducibility):
- NULL values in nullable fields (5–18% rates)
- Region spelling variants ("North America" → "NA", "N. America", etc.)
- Near-duplicate customers (240 records)
- Orphaned foreign keys, future date typos, mojibake, truncated strings, numeric outliers

### Governance Layer
- 12 clean views (`v_*_clean`) that exclude duplicates, orphans, and future dates
- `data_quality_flags` table with ~3,200 flags across 8 rules
- `region_mapping` lookup table for standardization

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate the database (takes ~30 seconds)
python -m generate_otacon

# Run the Streamlit dashboard
cd streamlit_dashboard
cp ../otacon.db .
streamlit run app.py
```

## Project Structure

```
ai_week1_project_overview/
├── generate_otacon/          # Data generator package
│   ├── __main__.py           # Pipeline orchestrator (9 steps)
│   ├── config.py             # All constants, storylines, calibration targets
│   ├── schema.py             # 18 CREATE TABLE statements
│   ├── generators.py         # Data generation for all 5 layers + bridge
│   ├── helpers.py            # Utility functions
│   ├── validation.py         # Post-generation benchmark checks
│   ├── messiness.py          # 25 controlled data quality degradation rules
│   └── governance.py         # 12 clean views + flags + region mapping
├── notebooks/                # EDA notebooks (Plotly, one per layer)
│   ├── 01_ecommerce_eda.ipynb
│   ├── 02_saas_eda.ipynb
│   ├── 03_product_analytics_eda.ipynb
│   ├── 04_payments_eda.ipynb
│   └── 05_crm_eda.ipynb
├── streamlit_dashboard/      # 6-page analytics dashboard
│   ├── app.py                # Executive Summary (entry point)
│   ├── helpers.py            # Shared DB connection + components
│   ├── requirements.txt
│   └── pages/
│       ├── 2_ecommerce.py
│       ├── 3_saas.py
│       ├── 4_product.py
│       ├── 5_payments.py
│       └── 6_crm.py
├── governance.md             # Data governance policy document
├── .gitignore
├── requirements.txt
└── README.md
```

## Querying the Data

```python
import sqlite3
conn = sqlite3.connect("otacon.db")

# Use clean views for analysis (governed data)
df = pd.read_sql("SELECT * FROM v_customers_clean", conn)

# Use raw tables for data quality profiling
df_raw = pd.read_sql("SELECT * FROM customers", conn)

# Check data quality flags
flags = pd.read_sql("SELECT * FROM data_quality_flags", conn)
```

## What's Next

- **Week 2:** Versioned prompt library with eval harness
- **Week 3:** YAML-based semantic layer (metrics, entities, business rules)
- **Weeks 5–7:** AI agents that query this database using the semantic layer
