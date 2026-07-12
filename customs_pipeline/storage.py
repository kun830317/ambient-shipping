"""SQLite storage for normalized trade records.

Records are upserted on (source, flow, period, reporter, partner, hs_code,
description) so re-running a fetch for the same period refreshes values
instead of duplicating rows.
"""

import csv
import sqlite3

from .schema import COLUMNS

DEFAULT_DB = "customs.db"

# Columns forming the identity of a record; everything else is refreshed
# on re-fetch. `ref` (e.g. the BOL number) keeps individual shipments from
# bill-of-lading sources distinct; statistics sources leave it empty.
KEY_COLUMNS = ["source", "flow", "period", "reporter", "partner",
               "hs_code", "description", "shipper", "consignee", "ref"]

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
    shipper       TEXT NOT NULL DEFAULT '',
    consignee     TEXT NOT NULL DEFAULT '',
    ref           TEXT NOT NULL DEFAULT '',
    value_usd     REAL,
    value_local   REAL,
    quantity      REAL,
    quantity_unit TEXT,
    weight_kg     REAL,
    raw           TEXT,
    fetched_at    TEXT DEFAULT (datetime('now')),
    UNIQUE (source, flow, period, reporter, partner, hs_code, description,
            shipper, consignee, ref)
);
CREATE INDEX IF NOT EXISTS idx_records_period ON trade_records (period);
CREATE INDEX IF NOT EXISTS idx_records_section ON trade_records (hs_section);
CREATE INDEX IF NOT EXISTS idx_records_company ON trade_records (consignee, shipper);
"""


def _migrate_legacy(conn):
    """Rebuild pre-shipper/consignee databases into the current layout."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trade_records)")]
    if not cols or "shipper" in cols:
        return
    conn.execute("ALTER TABLE trade_records RENAME TO trade_records_legacy")
    for index in ("idx_records_period", "idx_records_section"):
        conn.execute("DROP INDEX IF EXISTS " + index)
    conn.executescript(_CREATE_SQL)
    common = ", ".join(c for c in cols if c in COLUMNS + ["fetched_at"])
    conn.execute("INSERT INTO trade_records (%s) "
                 "SELECT %s FROM trade_records_legacy" % (common, common))
    conn.execute("DROP TABLE trade_records_legacy")
    conn.commit()


def connect(db_path=DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    _migrate_legacy(conn)
    conn.executescript(_CREATE_SQL)
    return conn


def upsert_records(conn, records):
    placeholders = ", ".join(":" + c for c in COLUMNS)
    updates = ", ".join(
        "%s = excluded.%s" % (c, c)
        for c in COLUMNS if c not in KEY_COLUMNS
    )
    sql = (
        "INSERT INTO trade_records (%s) VALUES (%s) "
        "ON CONFLICT (%s) DO UPDATE SET %s, fetched_at = datetime('now')"
        % (", ".join(COLUMNS), placeholders,
           ", ".join(KEY_COLUMNS), updates)
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
