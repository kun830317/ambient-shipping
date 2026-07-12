"""Command-line interface.

Fetch one month from the US Census API, classify, store:
    python -m customs_pipeline fetch us-census --flow import --period 2026-03

Fetch US imports from China via UN Comtrade (free key in COMTRADE_API_KEY):
    python -m customs_pipeline fetch un-comtrade --reporter 842 --partner 156 \
        --flow import --period 2026-01

Download Taiwan MOF open-data files:
    python -m customs_pipeline fetch taiwan-mof --limit-files 2

Summarize what's stored, or export to CSV:
    python -m customs_pipeline summary --period 2026-03
    python -m customs_pipeline export --out trade.csv
"""

import argparse
import sys

from . import classify, storage
from .sources import FETCHERS


def main(argv=None):
    parser = argparse.ArgumentParser(prog="customs_pipeline",
                                     description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=storage.DEFAULT_DB,
                        help="SQLite database path (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="fetch, classify and store one source")
    p_fetch.add_argument("source", choices=sorted(FETCHERS))
    p_fetch.add_argument("--flow", choices=["import", "export"], default="import")
    p_fetch.add_argument("--period", help="YYYY-MM (Census/Taiwan) or YYYYMM (Comtrade)")
    p_fetch.add_argument("--hs-level", default="HS2", choices=["HS2", "HS4", "HS6"])
    p_fetch.add_argument("--reporter", default="842",
                         help="un-comtrade: reporter M49 code (default 842=USA)")
    p_fetch.add_argument("--partner",
                         help="partner code (Census CTY_CODE / Comtrade M49)")
    p_fetch.add_argument("--limit-files", type=int,
                         help="taiwan-mof: only download first N files")

    p_summary = sub.add_parser("summary", help="value totals per category")
    p_summary.add_argument("--period")

    p_export = sub.add_parser("export", help="dump stored records to CSV")
    p_export.add_argument("--out", default="trade_records.csv")
    p_export.add_argument("--period")

    p_serve = sub.add_parser("serve", help="start the local web dashboard")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)

    if args.command == "serve":
        from .webapp import serve
        serve(db_path=args.db, host=args.host, port=args.port)
        return

    conn = storage.connect(args.db)

    if args.command == "fetch":
        records = FETCHERS[args.source](
            flow=args.flow, period=args.period, hs_level=args.hs_level,
            reporter=args.reporter, partner=args.partner,
            limit_files=args.limit_files,
        )
        for record in records:
            classify.classify_record(record)
        n = storage.upsert_records(conn, records)
        print("stored %d records from %s into %s" % (n, args.source, args.db))

    elif args.command == "summary":
        rows = storage.category_summary(conn, args.period)
        print("%-7s %-22s %-6s %8s %18s" %
              ("section", "category", "flow", "rows", "total_usd"))
        for section, zh, _en, flow, count, total in rows:
            total_s = format(total, ",.0f") if total is not None else "-"
            print("%-7s %-22s %-6s %8d %18s" %
                  (section or "-", zh or "未分類", flow, count, total_s))

    elif args.command == "export":
        where, params = "1=1", ()
        if args.period:
            where, params = "period = ?", (args.period,)
        path = storage.export_csv(conn, args.out, where, params)
        print("exported to %s" % path)


if __name__ == "__main__":
    sys.exit(main())
