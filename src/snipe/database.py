"""SQLite database schema and initialization for SNIPE scanner."""

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "snipe.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    industry TEXT,
    market_cap REAL,
    shares_outstanding REAL,
    added_date TEXT,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS daily_prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    adj_close REAL,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    symbol TEXT NOT NULL,
    quarter TEXT NOT NULL,
    fiscal_year INTEGER,
    eps REAL,
    revenue REAL,
    roe REAL,
    net_profit REAL,
    eps_growth_qoq REAL,
    revenue_growth_qoq REAL,
    fii_holding_pct REAL,
    dii_holding_pct REAL,
    mf_schemes_count INTEGER,
    promoter_holding_pct REAL,
    last_updated TEXT,
    PRIMARY KEY (symbol, quarter)
);

CREATE TABLE IF NOT EXISTS scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trend_template_score INTEGER,
    trend_template_pass INTEGER,
    vcp_detected INTEGER,
    vcp_quality_score REAL,
    vcp_contractions INTEGER,
    pivot_price REAL,
    stage TEXT,
    stage_confirmed INTEGER,
    breakout_detected INTEGER,
    hv1_edge INTEGER,
    hve_edge INTEGER,
    volume_ratio REAL,
    canslim_score INTEGER,
    rs_percentile REAL,
    edge_count INTEGER,
    composite_score REAL,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

CREATE TABLE IF NOT EXISTS watchlist_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date TEXT NOT NULL,
    rank INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    sector TEXT,
    current_price REAL,
    pivot_price REAL,
    distance_to_pivot_pct REAL,
    stop_price REAL,
    stop_distance_pct REAL,
    composite_score REAL,
    edge_count INTEGER,
    edges TEXT,
    trend_template_score INTEGER,
    vcp_quality REAL,
    canslim_score INTEGER,
    suggested_shares INTEGER,
    position_value REAL,
    risk_reward_ratio REAL,
    entry_triggered INTEGER DEFAULT 0,
    entry_date TEXT,
    outcome TEXT,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    entry_price REAL NOT NULL,
    entry_date TEXT NOT NULL,
    shares INTEGER NOT NULL,
    stop_price REAL NOT NULL,
    initial_risk REAL,
    edge_count INTEGER,
    edges TEXT,
    target_1 REAL,
    target_2 REAL,
    target_3 REAL,
    current_stop REAL,
    trailing_stop_active INTEGER DEFAULT 0,
    status TEXT DEFAULT 'open',
    exit_price REAL,
    exit_date TEXT,
    exit_reason TEXT,
    pnl REAL,
    r_multiple REAL,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

CREATE TABLE IF NOT EXISTS regime_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    regime TEXT NOT NULL,
    breadth_50dma REAL,
    breadth_200dma REAL,
    index_vs_150dma_pct REAL,
    index_ma_slope TEXT,
    fii_net_5d REAL,
    fii_net_20d REAL,
    previous_regime TEXT,
    transition_reason TEXT
);

CREATE TABLE IF NOT EXISTS fii_dii_flows (
    date TEXT PRIMARY KEY,
    fii_buy REAL,
    fii_sell REAL,
    fii_net REAL,
    dii_buy REAL,
    dii_sell REAL,
    dii_net REAL
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol ON daily_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(date);
CREATE INDEX IF NOT EXISTS idx_scan_results_date ON scan_results(scan_date);
CREATE INDEX IF NOT EXISTS idx_watchlist_date ON watchlist_history(scan_date);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_regime_date ON regime_history(date);
"""


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Initialize the SNIPE database with schema.

    Args:
        db_path: Path to SQLite database file. Defaults to project root snipe.db.

    Returns:
        Active database connection.
    """
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection (creates DB if not exists).

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Active database connection with row_factory set.
    """
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn
