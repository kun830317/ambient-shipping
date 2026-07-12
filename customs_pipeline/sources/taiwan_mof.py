"""Taiwan customs trade statistics (財政部關務署 海關進出口貿易統計).

Two access paths:

1. data.gov.tw dataset #6053「海關進出口貿易統計」— monthly files published
   under the Open Government Data License. This module reads the dataset
   metadata API and downloads every CSV distribution it lists.
   https://data.gov.tw/dataset/6053

2. 關港貿單一窗口 (https://portal.sw.nat.gov.tw/APGA/GA30) — the interactive
   query system. It has no stable public API; for ad-hoc deep queries use
   the website manually, or 貿易統計資料庫 of the 國際貿易署
   (https://publicinfo.trade.gov.tw/cuswebo/) which offers CSV export.

Monthly aggregate values are published in TWD and USD; rows are keyed by
稅則號別 (the Taiwanese HS-based tariff code), so the standard HS chapter
classifier applies.
"""

import csv
import io

from ..schema import TradeRecord
from .base import get, to_float

DATASET_META_URL = "https://data.gov.tw/api/v2/rest/dataset/6053"

# Column-name candidates seen across the published files (names vary by year).
_COL_ALIASES = {
    "hs_code": ["稅則號別", "貨品分類號列", "CCC Code", "HS Code", "hs_code"],
    "description": ["貨名", "中文貨名", "貨品名稱", "Description", "英文貨名"],
    "value_usd": ["美元(千元)", "美元", "USD", "value_usd", "金額(美元)"],
    "value_local": ["新臺幣(千元)", "新台幣", "TWD", "金額(新臺幣)"],
    "weight_kg": ["重量(公斤)", "重量", "weight"],
    "quantity": ["數量", "quantity"],
    "quantity_unit": ["數量單位", "單位", "unit"],
    "partner": ["國家", "國別", "貿易國", "Country"],
    "flow": ["進出口別", "進出口", "flow"],
    "period": ["年月", "資料年月", "period"],
}


def _pick(row, key):
    for alias in _COL_ALIASES[key]:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return ""


def _flow_of(row, default_flow):
    label = str(_pick(row, "flow"))
    if "出" in label or label.lower().startswith("ex"):
        return "export"
    if "進" in label or label.lower().startswith("im"):
        return "import"
    return default_flow


def list_distributions():
    """Return [(title, download_url), ...] for dataset 6053."""
    meta = get(DATASET_META_URL).json()
    result = meta.get("result", meta)
    out = []
    for dist in result.get("distribution", []):
        url = (dist.get("resourceDownloadUrl") or dist.get("downloadURL")
               or dist.get("accessURL"))
        fmt = (dist.get("resourceFormat") or dist.get("format") or "").lower()
        if url and fmt in ("csv", ""):
            out.append((dist.get("resourceDescription")
                        or dist.get("title") or url, url))
    return out


def fetch(flow="import", period=None, limit_files=None, **_):
    """Download and normalize the data.gov.tw CSV distributions.

    flow:        default flow label used when a file has no 進出口別 column
    period:      optional "YYYY-MM" filter applied after parsing
    limit_files: fetch only the first N distributions (for testing)
    """
    records = []
    distributions = list_distributions()
    if limit_files:
        distributions = distributions[:limit_files]

    for title, url in distributions:
        resp = get(url)
        # Taiwanese government CSVs are usually UTF-8 with BOM; fall back to CP950.
        try:
            text = resp.content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = resp.content.decode("cp950", errors="replace")

        for row in csv.DictReader(io.StringIO(text)):
            row_period = str(_pick(row, "period")).strip()
            # normalize 11305 / 2024-05 / 202405 style year-months
            if row_period.isdigit() and len(row_period) == 5:  # ROC year
                row_period = "%d-%s" % (int(row_period[:3]) + 1911,
                                        row_period[3:])
            elif row_period.isdigit() and len(row_period) == 6:
                row_period = row_period[:4] + "-" + row_period[4:]
            if period and row_period and row_period != period:
                continue

            records.append(TradeRecord(
                source="taiwan_mof",
                flow=_flow_of(row, flow),
                period=row_period or (period or ""),
                reporter="Taiwan",
                partner=str(_pick(row, "partner")) or "WORLD",
                hs_code=str(_pick(row, "hs_code")),
                description=str(_pick(row, "description")),
                value_usd=to_float(_pick(row, "value_usd")),
                value_local=to_float(_pick(row, "value_local")),
                quantity=to_float(_pick(row, "quantity")),
                quantity_unit=str(_pick(row, "quantity_unit")),
                weight_kg=to_float(_pick(row, "weight_kg")),
                raw=dict(row),
            ))
    return records
