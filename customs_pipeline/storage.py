"""SQLite storage for normalized trade records.

Records are upserted on (source, flow, period, reporter, partner, hs_code,
description) so re-running a fetch for the same period refreshes values
instead of duplicating rows.
"""

import csv
import sqlite3

from .schema import COLUMNS

DEFAULT_DB = "customs.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS trade_records (
    source        TEXT NOT NULL,
    flow          TEXT NOT NULL,
    period        TEXT NOT NULL,
    reporter      TEXT NOT NULL,
    partner       TEXT NOT NULL,
    hs_code       TEXT NOT NULL DEFAULT '',
    hs_chapter    TEXT,
    hs_section    TEXT,
    category_en   TEXT,
    category_zh   TEXT,
    description   TEXT NOT NULL DEFAULT '',
    value_usd     REAL,
    value_local   REAL,
    quantity      REAL,
    quantity_unit TEXT,
    weight_kg     REAL,
    raw           TEXT,
    fetched_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (source, flow, period, reporter, partner, hs_code, description)
);
CREATE INDEX IF NOT EXISTS idx_records_period ON trade_records (period);
CREATE INDEX IF NOT EXISTS idx_records_section ON trade_records (hs_section);
"""


def connect(db_path=DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.executescript(_CREATE_SQL)
    return conn


def upsert_records(conn, records):
    placeholders = ", ".join(":" + c for c in COLUMNS)
    updates = ", ".join(
        "%s = excluded.%s" % (c, c)
        for c in COLUMNS
        if c not in ("source", "flow", "period", "reporter", "partner",
                     "hs_code", "description")
    )
    sql = (
        "INSERT INTO trade_records (%s) VALUES (%s) "
        "ON CONFLICT (source, flow, period, reporter, partner, hs_code, description) "
        "DO UPDATE SET %s, fetched_at = datetime('now')"
        % (", ".join(COLUMNS), placeholders, updates)
    )
    with conn:
        conn.executemany(sql, [r.as_row() for r in records])
    return len(records)


def export_csv(conn, out_path, where="1=1", params=()):
    cur = conn.execute(
        "SELECT %s, fetched_at FROM trade_records WHERE %s "
        "ORDER BY period, source, hs_code" % (", ".join(COLUMNS), where),
        params,
    )
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS + ["fetched_at"])
        writer.writerows(cur)
    return out_path


def category_summary(conn, period=None):
    """Total USD value per category, optionally for one period."""
    where, params = "1=1", []
    if period:
        where, params = "period = ?", [period]
    return conn.execute(
        "SELECT hs_section, category_zh, category_en, flow, "
        "       COUNT(*) AS rows, SUM(value_usd) AS total_usd "
        "FROM trade_records WHERE %s "
        "GROUP BY hs_section, flow ORDER BY total_usd DESC" % where,
        params,
    ).fetchall()
