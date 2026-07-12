"""US Census Bureau International Trade API.

Monthly US imports/exports by Harmonized System code, 2013-present.
Docs: https://www.census.gov/data/developers/data-sets/international-trade.html

Free. An API key (https://api.census.gov/data/key_signup.html) is optional
for light use but required beyond ~500 requests/day; set CENSUS_API_KEY.

Example:
    records = fetch(flow="import", period="2026-03", hs_level="HS2")
"""

import os

from ..schema import TradeRecord
from .base import get, to_float

BASE = "https://api.census.gov/data/timeseries/intltrade"

# The imports and exports endpoints use different field prefixes.
_ENDPOINTS = {
    "import": {
        "url": BASE + "/imports/hs",
        "commodity": "I_COMMODITY",
        "desc": "I_COMMODITY_SDESC",
        "value": "GEN_VAL_MO",       # general imports, monthly value (USD)
    },
    "export": {
        "url": BASE + "/exports/hs",
        "commodity": "E_COMMODITY",
        "desc": "E_COMMODITY_SDESC",
        "value": "ALL_VAL_MO",       # total exports, monthly value (USD)
    },
}


def fetch(flow="import", period=None, hs_level="HS2", partner=None, **_):
    """Fetch one month of US trade data.

    flow:     "import" or "export"
    period:   "YYYY-MM"
    hs_level: "HS2", "HS4" or "HS6" (detail level of commodity codes)
    partner:  optional Census CTY_CODE (e.g. "5830" = Taiwan); default all
    """
    if period is None:
        raise ValueError("period is required, e.g. period='2026-03'")
    ep = _ENDPOINTS[flow]

    fields = ["CTY_CODE", "CTY_NAME", ep["commodity"], ep["desc"], ep["value"]]
    params = {
        "get": ",".join(fields),
        "time": period,
        "COMM_LVL": hs_level,
    }
    if partner:
        params["CTY_CODE"] = partner
    api_key = os.environ.get("CENSUS_API_KEY")
    if api_key:
        params["key"] = api_key

    rows = get(ep["url"], params=params).json()
    header, data = rows[0], rows[1:]
    idx = {name: i for i, name in enumerate(header)}

    records = []
    for row in data:
        raw = dict(zip(header, row))
        records.append(TradeRecord(
            source="us_census",
            flow=flow,
            period=period,
            reporter="USA",
            partner=row[idx["CTY_NAME"]] or row[idx["CTY_CODE"]],
            hs_code=row[idx[ep["commodity"]]] or "",
            description=row[idx[ep["desc"]]] or "",
            value_usd=to_float(row[idx[ep["value"]]]),
            raw=raw,
        ))
    return records
