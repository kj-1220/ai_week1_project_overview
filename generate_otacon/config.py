"""
config.py — Otacon Inc. Data Generator Configuration
=====================================================
All constants, calibration targets, weights, and storyline parameters.
Edit this file to tune benchmarks without touching generator logic.
"""

import datetime
from faker import Faker

fake = Faker()
Faker.seed(42)

# ── Time Range ──
START_DATE = datetime.date(2023, 1, 1)
END_DATE = datetime.date(2025, 12, 31)
DB_PATH = "otacon.db"
RANDOM_SEED = 42

# ── Regions ──
REGIONS = ["North America", "Europe", "APAC", "LATAM"]
REGION_WEIGHTS = [0.45, 0.25, 0.20, 0.10]

# ── Segments ──
SEGMENTS = ["enterprise", "mid_market", "smb"]
SEGMENT_WEIGHTS = [0.15, 0.35, 0.50]

# ── Industries ──
INDUSTRIES = ["technology", "manufacturing", "retail", "healthcare", "finance"]
INDUSTRY_WEIGHTS = [0.25, 0.20, 0.20, 0.20, 0.15]

# ── Customer Types ──
CUSTOMER_TYPES = ["wholesale", "dtc"]
CUSTOMER_TYPE_WEIGHTS = [0.60, 0.40]

# ── Acquisition Channels ──
CHANNELS = ["direct_sales", "partner", "inbound", "trade_show", "referral"]
CHANNEL_WEIGHTS = [0.30, 0.25, 0.20, 0.15, 0.10]

# ── Revenue Tiers ──
REVENUE_TIERS = ["under_1m", "1m_10m", "10m_50m", "50m_plus"]
REVENUE_TIER_WEIGHTS = [0.40, 0.30, 0.20, 0.10]

# ── Product Categories ──
PRODUCT_CATEGORIES = {
    "hardware": ["servers", "networking", "storage", "peripherals", "workstations"],
    "software": ["analytics", "security", "collaboration", "automation", "monitoring"],
    "accessories": ["cables", "adapters", "cases", "mounts", "docks"],
    "services": ["consulting", "implementation", "training", "support", "managed_services"],
    "consumables": ["toner", "labels", "packaging", "cleaning", "replacement_parts"],
}
CATEGORY_WEIGHTS = [0.25, 0.30, 0.15, 0.20, 0.10]

# ── E-Commerce Monthly Multipliers (B2B seasonality) ──
MONTHLY_MULTIPLIERS = {
    1: 0.85,   # Jan — post-holiday dip + returns
    2: 0.90,
    3: 0.95,
    4: 1.00,
    5: 1.05,
    6: 1.10,   # Q2 budget flush
    7: 0.90,   # Summer slowdown
    8: 0.88,
    9: 1.05,   # Q3 ramp
    10: 1.15,  # Q4 budget planning
    11: 1.38,  # B2B holiday pull-forward
    12: 0.95,  # Orders already placed
}

# ── YoY Growth Rates ──
YOY_GROWTH = {
    2023: 1.00,   # Baseline year
    2024: 1.08,   # 8% growth
    2025: 1.08,   # 8% continued growth over 2024
}

# ── Orders Per Month (2023 baseline) ──
ORDERS_PER_MONTH_BASE = 1800

# ── SaaS Plan Tiers ──
PLAN_TIERS = ["free", "basic", "pro", "enterprise"]
PLAN_WEIGHTS = [0.25, 0.35, 0.25, 0.15]
PLAN_MRR = {"free": 0, "basic": 99, "pro": 299, "enterprise": 999}
PLAN_USER_RANGE = {"free": (1, 2), "basic": (2, 5), "pro": (5, 12), "enterprise": (10, 20)}

# ── Product Analytics ──
FEATURE_MODULES = ["analytics", "dashboards", "integrations", "admin", "data_management"]
# AI Insights module launches Q4 2025
AI_INSIGHTS_MODULE = "ai_insights"
AI_INSIGHTS_LAUNCH = datetime.date(2025, 10, 1)

EVENT_TYPES = [
    "login", "report_run", "dashboard_create", "dashboard_view",
    "export", "invite_user", "integration_setup", "settings_change", "data_upload"
]
# AI-specific events added Q4 2025
AI_EVENT_TYPES = ["ai_query", "ai_insight_view", "ai_report_generate"]

EVENTS_PER_MONTH = {"free": 8, "basic": 20, "pro": 40, "enterprise": 80}

# ── CRM ──
SALES_REPS = [fake.name() for _ in range(12)]

# ── Payment Terms by Segment ──
PAYMENT_TERMS = {"enterprise": 60, "mid_market": 45, "smb": 30}

# ═══════════════════════════════════════════════════════════════
# STORYLINE PARAMETERS
# ═══════════════════════════════════════════════════════════════
# These control the engineered business narratives in the data.

STORYLINES = {
    # 2023 storylines
    "q2_2023_strong_growth": {
        "description": "Strong growth quarter across all layers",
        "months": [(2023, 4), (2023, 5), (2023, 6)],
    },
    "q3_2023_eu_payment_delays": {
        "description": "Payment delays increase in European region. SaaS support tickets spike.",
        "months": [(2023, 7), (2023, 8), (2023, 9)],
        "payment_delay_days": (15, 25),
        "region": "Europe",
    },
    "q4_2023_holiday_churn": {
        "description": "Holiday e-commerce peak. New SaaS acquisitions. Churn elevated.",
        "months": [(2023, 10), (2023, 11), (2023, 12)],
        "churn_multiplier": 1.3,
    },

    # 2024 storylines
    "q1_2024_collections_push": {
        "description": "Collections effort improves AR metrics. CRM outreach increases.",
        "months": [(2024, 1), (2024, 2), (2024, 3)],
        "payment_improvement": 0.85,
    },
    "q2_2024_enterprise_churn": {
        "description": "Two enterprise SaaS customers churn. Usage had declined 90 days prior.",
        "months": [(2024, 4), (2024, 5), (2024, 6)],
        "enterprise_churn_multiplier": 2.0,
    },
    "q3_2024_recovery": {
        "description": "Recovery — expansion MRR exceeds churn MRR for first time in three quarters.",
        "months": [(2024, 7), (2024, 8), (2024, 9)],
        "expansion_boost": 0.05,
    },

    # 2025 storylines
    "q1_2025_steady": {
        "description": "Steady continuation of recovery. Growth normalizing, pipeline healthy.",
        "months": [(2025, 1), (2025, 2), (2025, 3)],
    },
    "q2_2025_tariff_volatility": {
        "description": "Tariff-based volatility. Import costs spike for hardware/consumables. Customers delay orders. Payment terms stretch. SaaS churn ticks up.",
        "months": [(2025, 4), (2025, 5), (2025, 6)],
        "ecommerce_multiplier": 0.75,           # ~15% revenue dip
        "affected_categories": ["hardware", "consumables"],
        "price_increase_pct": (0.08, 0.18),      # 8-18% cost increase
        "payment_delay_days": (10, 20),           # Broader than 2023 (all regions)
        "churn_multiplier": 1.4,
        "ticket_spike_multiplier": 1.8,
    },
    "q3_2025_stabilization": {
        "description": "Stabilization. Companies adjust pricing, find alternatives. Volume recovers partially. Churn drops below baseline.",
        "months": [(2025, 7), (2025, 8), (2025, 9)],
        "ecommerce_multiplier": 0.95,            # Partial recovery
        "churn_multiplier": 0.7,                 # Below baseline — survivors are committed
        "payment_improvement": 0.90,
    },
    "q4_2025_ai_launch": {
        "description": "AI Insights module launches. Adoption starts slow, accelerates through Q4. Adopters show higher usage scores. November e-commerce spike slightly muted.",
        "months": [(2025, 10), (2025, 11), (2025, 12)],
        "ai_adoption_rate_month1": 0.12,         # 12% of accounts adopt in Oct
        "ai_adoption_rate_month2": 0.25,         # 25% by Nov
        "ai_adoption_rate_month3": 0.35,         # 35% by Dec
        "november_muting": 0.93,                 # Nov spike reduced to 1.28x
        "usage_score_boost_adopters": 15,        # +15 usage score for AI adopters
        "churn_reduction_adopters": 0.4,         # 60% less likely to churn
    },
}


def is_in_storyline(date, storyline_key):
    """Check if a date falls within a storyline's active months."""
    story = STORYLINES.get(storyline_key, {})
    months = story.get("months", [])
    return (date.year, date.month) in months


def get_storyline_param(storyline_key, param, default=None):
    """Get a parameter value from a storyline."""
    return STORYLINES.get(storyline_key, {}).get(param, default)
