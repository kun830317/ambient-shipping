"""Normalized record schema shared by every data source.

Each fetcher converts its raw API/file rows into TradeRecord instances so the
classifier and storage layers never need source-specific logic.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class TradeRecord:
    source: str                     # "us_census" | "un_comtrade" | "taiwan_mof"
    flow: str                       # "import" | "export"
    period: str                     # "YYYY-MM" (or "YYYY" for annual data)
    reporter: str                   # reporting country/economy, ISO name or code
    partner: str                    # partner country ("WORLD" for totals)
    hs_code: str                    # HS commodity code, 2/4/6 digits ("" if unknown)
    description: str                # commodity description as given by the source
    shipper: str = ""               # exporter of record (bill-of-lading sources)
    consignee: str = ""             # importer of record (bill-of-lading sources)
    ref: str = ""                   # shipment reference, e.g. BOL number; keeps
                                    # per-shipment rows distinct in the unique key
    value_usd: Optional[float] = None       # trade value in USD
    value_local: Optional[float] = None     # trade value in reporter's currency
    quantity: Optional[float] = None
    quantity_unit: str = ""
    weight_kg: Optional[float] = None
    # Filled in by classify.classify_record():
    hs_chapter: str = ""            # 2-digit chapter
    hs_section: str = ""            # roman numeral section (I..XXI)
    category_en: str = ""
    category_zh: str = ""
    raw: dict = field(default_factory=dict)  # original row, kept for debugging

    def as_row(self):
        d = asdict(self)
        d["raw"] = json.dumps(d["raw"], ensure_ascii=False, default=str)
        return d


# Column order used for SQLite table and CSV export.
COLUMNS = [
    "source", "flow", "period", "reporter", "partner",
    "hs_code", "hs_chapter", "hs_section", "category_en", "category_zh",
    "description", "shipper", "consignee", "ref", "value_usd", "value_local",
    "quantity", "quantity_unit", "weight_kg", "raw",
]
