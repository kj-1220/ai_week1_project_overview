"""
schema.py — Database table definitions for Otacon Inc.
"""

SCHEMA_SQL = """
-- ══════════════════════════════════
-- LAYER 1: E-COMMERCE
-- ══════════════════════════════════
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    customer_type TEXT NOT NULL,
    region TEXT NOT NULL,
    segment TEXT NOT NULL,
    industry TEXT NOT NULL,
    acquisition_date DATE NOT NULL,
    acquisition_channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    annual_revenue_tier TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    unit_price REAL NOT NULL,
    cost REAL NOT NULL,
    launch_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    ship_date DATE NOT NULL,
    status TEXT NOT NULL,
    channel TEXT NOT NULL,
    region TEXT NOT NULL,
    total_amount REAL NOT NULL,
    discount_pct REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS order_items (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS returns (
    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    return_date DATE NOT NULL,
    reason TEXT NOT NULL,
    refund_amount REAL NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- ══════════════════════════════════
-- LAYER 2: SAAS
-- ══════════════════════════════════
CREATE TABLE IF NOT EXISTS saas_customers (
    saas_customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    plan_tier TEXT NOT NULL,
    signup_date DATE NOT NULL,
    contract_months INTEGER NOT NULL,
    mrr REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    usage_score INTEGER NOT NULL DEFAULT 50,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS mrr_movements (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    saas_customer_id INTEGER NOT NULL,
    movement_date DATE NOT NULL,
    movement_type TEXT NOT NULL,
    amount REAL NOT NULL,
    previous_mrr REAL NOT NULL,
    new_mrr REAL NOT NULL,
    FOREIGN KEY (saas_customer_id) REFERENCES saas_customers(saas_customer_id)
);

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    saas_customer_id INTEGER NOT NULL,
    created_date DATE NOT NULL,
    resolved_date DATE,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    resolution_hours REAL,
    FOREIGN KEY (saas_customer_id) REFERENCES saas_customers(saas_customer_id)
);

-- ══════════════════════════════════
-- LAYER 3: PRODUCT ANALYTICS
-- ══════════════════════════════════
CREATE TABLE IF NOT EXISTS saas_users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    saas_customer_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    created_date DATE NOT NULL,
    last_login_date DATE,
    status TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY (saas_customer_id) REFERENCES saas_customers(saas_customer_id)
);

CREATE TABLE IF NOT EXISTS usage_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    saas_customer_id INTEGER NOT NULL,
    event_date DATETIME NOT NULL,
    event_type TEXT NOT NULL,
    feature_module TEXT NOT NULL,
    session_id TEXT NOT NULL,
    duration_seconds INTEGER,
    FOREIGN KEY (user_id) REFERENCES saas_users(user_id),
    FOREIGN KEY (saas_customer_id) REFERENCES saas_customers(saas_customer_id)
);

CREATE TABLE IF NOT EXISTS feature_adoption (
    adoption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    saas_customer_id INTEGER NOT NULL,
    feature_module TEXT NOT NULL,
    first_used_date DATE,
    last_used_date DATE,
    total_events INTEGER NOT NULL DEFAULT 0,
    monthly_active_users INTEGER NOT NULL DEFAULT 0,
    adoption_depth TEXT NOT NULL DEFAULT 'none',
    FOREIGN KEY (saas_customer_id) REFERENCES saas_customers(saas_customer_id)
);

-- ══════════════════════════════════
-- LAYER 4: PAYMENTS
-- ══════════════════════════════════
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    method TEXT NOT NULL,
    days_to_pay INTEGER NOT NULL,
    is_late INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

-- ══════════════════════════════════
-- LAYER 5: CRM
-- ══════════════════════════════════
CREATE TABLE IF NOT EXISTS accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    owner TEXT NOT NULL,
    account_tier TEXT NOT NULL,
    health_score INTEGER NOT NULL,
    last_contact_date DATE,
    next_renewal_date DATE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    activity_date DATE NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    notes TEXT NOT NULL,
    outcome TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

CREATE TABLE IF NOT EXISTS opportunities (
    opp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    opp_name TEXT NOT NULL,
    stage TEXT NOT NULL,
    amount REAL NOT NULL,
    close_date DATE NOT NULL,
    probability INTEGER NOT NULL,
    product_interest TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

-- ══════════════════════════════════
-- BRIDGE LAYER
-- ══════════════════════════════════
CREATE TABLE IF NOT EXISTS customer_xref (
    customer_id INTEGER PRIMARY KEY,
    ecommerce_id INTEGER,
    saas_customer_id INTEGER,
    account_id INTEGER,
    payment_customer_id INTEGER
);

CREATE TABLE IF NOT EXISTS customer_360 (
    customer_id INTEGER PRIMARY KEY,
    company_name TEXT,
    region TEXT,
    segment TEXT,
    total_orders INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    total_returns INTEGER DEFAULT 0,
    return_rate REAL DEFAULT 0,
    saas_plan TEXT,
    saas_mrr REAL,
    saas_usage_score INTEGER,
    dau_mau_ratio REAL,
    features_adopted INTEGER,
    avg_session_minutes REAL,
    avg_days_to_pay REAL,
    late_payment_pct REAL,
    account_health INTEGER,
    last_activity_date DATE,
    open_opportunities INTEGER DEFAULT 0,
    lifetime_value REAL DEFAULT 0
);
"""


def create_tables(conn):
    """Create all tables."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    print("  Tables created.")