"""ImportYeti / generic bill-of-lading CSV importer.

ImportYeti (https://www.importyeti.com) publishes US sea-import bills of
lading obtained from CBP via FOIA — including shipper (exporter) and
consignee (importer) names — searchable for free after registration.
It has no public API and scraping its site breaks its terms of service,
so this module ingests the CSV files its company pages let you download:

    1. Search a company on importyeti.com and download the CSV
    2. python -m customs_pipeline fetch importyeti --file path/to.csv
       (or point the dashboard's file field at it)

Header names are matched case-insensitively against alias lists, so CSVs
from other BOL sources with similar layouts (e.g. the Data Liberation
Project's CBP manifest extracts) load through the same path. Rows without
an HS code are classified from the free-text cargo description.
"""

import csv
import glob
import os
import re

from ..schema import TradeRecord
from .base import to_float

_ALIASES = {
    "shipper": ["shipper", "shipper name", "supplier", "supplier name"],
    "consignee": ["consignee", "consignee name", "purchaser", "company",
                  "importer", "importer name"],
    "description": ["product description", "description", "cargo description",
                    "product", "goods description", "description of goods"],
    "hs_code": ["hs code", "hscode", "hs", "hts code", "harmonized code"],
    "weight_kg": ["weight (kg)", "weight kg", "gross weight (kg)",
                  "gross weight", "weight"],
    "quantity": ["quantity", "item quantity", "container count", "qty"],
    "quantity_unit": ["quantity unit", "unit", "quantity type"],
    "date": ["arrival date", "date", "shipment date", "actual arrival date"],
    "ref": ["bill of lading", "bill of lading number", "bol", "bol number",
            "identifier", "shipment id"],
    "partner": ["shipper country", "supplier country", "country of origin",
                "origin country", "foreign country",
                "foreign port of lading", "port of lading"],
    "vessel": ["vessel", "vessel name", "ship name"],
}

_DATE_PATTERNS = [
    (re.compile(r"^(\d{4})-(\d{1,2})(?:-\d{1,2})?"), lambda m: (m[1], m[2])),
    (re.compile(r"^(\d{1,2})/\d{1,2}/(\d{4})"), lambda m: (m[2], m[1])),
]


def _index_headers(fieldnames):
    """Map our field names -> actual CSV header, case/space-insensitively."""
    normalized = {(h or "").strip().lower(): h for h in fieldnames}
    mapping = {}
    for field, aliases in _ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[field] = normalized[alias]
                break
    return mapping


def _period_of(text):
    text = (text or "").strip()
    for pattern, extract in _DATE_PATTERNS:
        m = pattern.match(text)
        if m:
            year, month = extract(m)
            return "%s-%02d" % (year, int(month))
    return ""


def fetch(file=None, flow="import", **_):
    """Load one CSV file, a glob pattern, or a directory of CSVs.

    These are US inbound manifests, so reporter is USA and flow defaults
    to "import"; partner is the shipper's country when the CSV carries it.
    """
    if not file:
        raise ValueError(
            "importyeti needs --file pointing to a CSV downloaded from "
            "importyeti.com (a directory or glob pattern also works)")
    if os.path.isdir(file):
        paths = sorted(glob.glob(os.path.join(file, "*.csv")))
    else:
        paths = sorted(glob.glob(file)) or [file]

    records = []
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = _index_headers(reader.fieldnames or [])
            if "shipper" not in headers and "consignee" not in headers:
                raise ValueError(
                    "%s: no shipper/consignee column found; headers were %r"
                    % (path, reader.fieldnames))

            def col(row, field):
                header = headers.get(field)
                return (row.get(header) or "").strip() if header else ""

            for row in reader:
                records.append(TradeRecord(
                    source="importyeti",
                    flow=flow,
                    period=_period_of(col(row, "date")),
                    reporter="USA",
                    partner=col(row, "partner") or "UNKNOWN",
                    hs_code=re.sub(r"\D", "", col(row, "hs_code"))[:6],
                    description=col(row, "description"),
                    shipper=col(row, "shipper"),
                    consignee=col(row, "consignee"),
                    ref=col(row, "ref") or col(row, "date"),
                    quantity=to_float(col(row, "quantity")),
                    quantity_unit=col(row, "quantity_unit"),
                    weight_kg=to_float(col(row, "weight_kg")),
                    raw=dict(row),
                ))
    return records
