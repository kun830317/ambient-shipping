"""UN Comtrade+ API — official trade statistics for most countries.

Docs: https://comtradedeveloper.un.org / https://uncomtrade.org
Free tier: register for an API key (500 calls/day, 100k records/call);
set COMTRADE_API_KEY. Without a key this module falls back to the public
preview endpoint, which is limited to 500 records per call.

Example:
    # Taiwan is not a UN Comtrade reporter; use partners' mirror data.
    # e.g. USA (842) imports from China (156), monthly 2026-01, HS2:
    records = fetch(reporter="842", partner="156", flow="import",
                    period="202601")
"""

import os

from ..schema import TradeRecord
from .base import get, to_float

DATA_URL = "https://comtradeapi.un.org/data/v1/get/C/M/HS"        # keyed
PREVIEW_URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"  # keyless

_FLOW_CODES = {"import": "M", "export": "X"}


def fetch(flow="import", period=None, reporter="842", partner=None,
          hs_level="HS2", **_):
    """Fetch monthly trade for one reporter country.

    flow:     "import" or "export"
    period:   "YYYYMM" (also accepts "YYYY-MM")
    reporter: UN M49 numeric code as string (842=USA, 392=Japan, 410=Korea)
    partner:  M49 code, or None for all partners ("0" = world total)
    hs_level: HS2 / HS4 / HS6 — mapped to Comtrade aggregate level
    """
    if period is None:
        raise ValueError("period is required, e.g. period='202601'")
    period = period.replace("-", "")

    params = {
        "reporterCode": reporter,
        "period": period,
        "flowCode": _FLOW_CODES[flow],
        "aggrLevel": {"HS2": 2, "HS4": 4, "HS6": 6}[hs_level],
        "includeDesc": "true",
    }
    if partner is not None:
        params["partnerCode"] = partner

    api_key = os.environ.get("COMTRADE_API_KEY")
    url = DATA_URL if api_key else PREVIEW_URL
    headers = {"Ocp-Apim-Subscription-Key": api_key} if api_key else {}

    payload = get(url, params=params, headers=headers).json()
    rows = payload.get("data") or []

    records = []
    for row in rows:
        records.append(TradeRecord(
            source="un_comtrade",
            flow=flow,
            period="%s-%s" % (period[:4], period[4:6]),
            reporter=row.get("reporterDesc") or str(row.get("reporterCode", "")),
            partner=row.get("partnerDesc") or str(row.get("partnerCode", "")),
            hs_code=str(row.get("cmdCode", "")),
            description=row.get("cmdDesc") or "",
            value_usd=to_float(row.get("primaryValue")),
            quantity=to_float(row.get("qty")),
            quantity_unit=row.get("qtyUnitAbbr") or "",
            weight_kg=to_float(row.get("netWgt")),
            raw=row,
        ))
    return records
