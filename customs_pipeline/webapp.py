"""Local web UI for the customs data pipeline.

Stdlib-only (http.server + sqlite3) so the whole project still depends on
nothing but `requests`. Start it with:

    python -m customs_pipeline serve --port 8765

then open http://127.0.0.1:8765 — fetch data with a form instead of CLI
flags, browse/filter stored records, see value-by-category charts, and
download CSV extracts. Binds to localhost only; it is a personal tool,
not a hardened public server.
"""

import csv
import io
import json
import os
import sqlite3
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import classify, storage
from .schema import COLUMNS
from .sources import FETCHERS

INDEX_HTML = os.path.join(os.path.dirname(__file__), "web", "index.html")

MAX_PAGE_SIZE = 500


def _records_query(params):
    """Build (where_sql, args) from validated query-string filters."""
    where, args = ["1=1"], []
    for field in ("period", "flow", "source", "hs_section"):
        value = params.get(field)
        if value:
            where.append("%s = ?" % field)
            args.append(value)
    partner = params.get("partner")
    if partner:
        where.append("partner LIKE ?")
        args.append("%" + partner + "%")
    hs_code = params.get("hs_code")
    if hs_code:
        where.append("hs_code LIKE ?")   # prefix match: 85 hits 8542, 8517…
        args.append(hs_code + "%")
    company = params.get("company")
    if company:
        where.append("(shipper LIKE ? OR consignee LIKE ?)")
        args.extend(["%" + company + "%"] * 2)
    q = params.get("q")
    if q:
        where.append("description LIKE ?")
        args.append("%" + q + "%")
    return " AND ".join(where), args


class Handler(BaseHTTPRequestHandler):
    db_path = storage.DEFAULT_DB

    # --- plumbing ---------------------------------------------------------

    def _send(self, code, body, content_type="application/json; charset=utf-8",
              extra_headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _params(self):
        parsed = urlparse(self.path)
        return {k: v[0] for k, v in parse_qs(parsed.query).items()}

    def _conn(self):
        return storage.connect(self.db_path)

    def log_message(self, fmt, *args):  # quieter default logging
        print("[webapp] %s" % (fmt % args))

    # --- routes -----------------------------------------------------------

    def do_GET(self):
        route = urlparse(self.path).path
        try:
            if route == "/":
                with open(INDEX_HTML, encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif route == "/api/meta":
                self._meta()
            elif route == "/api/summary":
                self._summary()
            elif route == "/api/records":
                self._records()
            elif route == "/api/export.csv":
                self._export()
            else:
                self._send(404, {"error": "not found"})
        except Exception as err:
            traceback.print_exc()
            self._send(500, {"error": str(err)})

    def do_POST(self):
        route = urlparse(self.path).path
        try:
            if route == "/api/fetch":
                self._fetch()
            else:
                self._send(404, {"error": "not found"})
        except Exception as err:
            traceback.print_exc()
            self._send(500, {"error": str(err)})

    # --- handlers ---------------------------------------------------------

    def _meta(self):
        conn = self._conn()
        periods = [r[0] for r in conn.execute(
            "SELECT DISTINCT period FROM trade_records ORDER BY period DESC")]
        sources = [r[0] for r in conn.execute(
            "SELECT DISTINCT source FROM trade_records ORDER BY source")]
        total, = conn.execute("SELECT COUNT(*) FROM trade_records").fetchone()
        self._send(200, {"periods": periods, "sources": sources,
                         "total_records": total,
                         "available_sources": sorted(FETCHERS),
                         "db_path": os.path.abspath(self.db_path)})

    def _summary(self):
        period = self._params().get("period") or None
        rows = storage.category_summary(self._conn(), period)
        self._send(200, [
            {"section": s or "-", "category_zh": zh or "未分類",
             "category_en": en or "Unclassified", "flow": flow,
             "rows": count, "total_usd": total}
            for s, zh, en, flow, count, total in rows
        ])

    def _records(self):
        params = self._params()
        where, args = _records_query(params)
        limit = min(int(params.get("limit", 50)), MAX_PAGE_SIZE)
        offset = max(int(params.get("offset", 0)), 0)
        conn = self._conn()
        count, = conn.execute(
            "SELECT COUNT(*) FROM trade_records WHERE " + where, args).fetchone()
        display_cols = [c for c in COLUMNS if c != "raw"]
        cur = conn.execute(
            "SELECT %s FROM trade_records WHERE %s "
            "ORDER BY value_usd DESC LIMIT ? OFFSET ?"
            % (", ".join(display_cols), where),
            args + [limit, offset])
        rows = [dict(zip(display_cols, row)) for row in cur]
        self._send(200, {"count": count, "rows": rows,
                         "limit": limit, "offset": offset})

    def _export(self):
        where, args = _records_query(self._params())
        conn = self._conn()
        cur = conn.execute(
            "SELECT %s, fetched_at FROM trade_records WHERE %s "
            "ORDER BY period, source, hs_code" % (", ".join(COLUMNS), where),
            args)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(COLUMNS + ["fetched_at"])
        writer.writerows(cur)
        self._send(200, "﻿" + buf.getvalue(), "text/csv; charset=utf-8",
                   {"Content-Disposition":
                    "attachment; filename=trade_records.csv"})

    def _fetch(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        source = body.get("source")
        if source not in FETCHERS:
            self._send(400, {"error": "unknown source: %r" % source})
            return
        kwargs = {
            "flow": body.get("flow", "import"),
            "period": body.get("period") or None,
            "hs_level": body.get("hs_level", "HS2"),
            "reporter": body.get("reporter") or "842",
            "partner": body.get("partner") or None,
            "limit_files": body.get("limit_files") or None,
            "file": body.get("file") or None,
        }
        records = FETCHERS[source](**kwargs)
        for record in records:
            classify.classify_record(record)
        stored = storage.upsert_records(self._conn(), records)
        self._send(200, {"stored": stored, "source": source})


def serve(db_path=storage.DEFAULT_DB, host="127.0.0.1", port=8765):
    storage.connect(db_path).close()  # create schema up front
    handler = type("BoundHandler", (Handler,), {"db_path": db_path})
    server = ThreadingHTTPServer((host, port), handler)
    print("customs pipeline web UI: http://%s:%d  (db: %s)"
          % (host, port, os.path.abspath(db_path)))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
