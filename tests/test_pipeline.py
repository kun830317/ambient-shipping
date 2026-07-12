"""Offline end-to-end tests for customs_pipeline.

The sandbox this repo is developed in has no egress to the data-source
hosts, so each fetcher is exercised against a canned response that matches
the real API's documented wire format. Run with:

    python3 -m unittest discover tests
"""

import json
import unittest
from unittest import mock

from customs_pipeline import classify, storage
from customs_pipeline.sources import taiwan_mof, un_comtrade, us_census


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload


# --- wire-format fixtures -------------------------------------------------

CENSUS_IMPORTS = [
    ["CTY_CODE", "CTY_NAME", "I_COMMODITY", "I_COMMODITY_SDESC",
     "GEN_VAL_MO", "time"],
    ["5830", "TAIWAN", "85",
     "ELECTRIC MACHINERY ETC; SOUND EQUIP; TV EQUIP; PTS",
     "9403871234", "2026-01"],
    ["5830", "TAIWAN", "84",
     "NUCLEAR REACTORS, BOILERS, MACHINERY ETC.; PARTS",
     "5210459876", "2026-01"],
    ["5830", "TAIWAN", "03",
     "FISH, CRUSTACEANS & AQUATIC INVERTEBRATES",
     "18234567", "2026-01"],
]

COMTRADE_PAGE = {
    "elapsedTime": "0.1 secs",
    "count": 2,
    "data": [
        {"reporterCode": 842, "reporterDesc": "USA",
         "partnerCode": 490, "partnerDesc": "Other Asia, nes",
         "flowCode": "M", "cmdCode": "85",
         "cmdDesc": "Electrical machinery and equipment and parts thereof",
         "primaryValue": 9403871234.0, "netWgt": 120345678.0,
         "qty": None, "qtyUnitAbbr": None},
        {"reporterCode": 842, "reporterDesc": "USA",
         "partnerCode": 490, "partnerDesc": "Other Asia, nes",
         "flowCode": "M", "cmdCode": "64",
         "cmdDesc": "Footwear, gaiters and the like",
         "primaryValue": 51234567.0, "netWgt": 8345678.0,
         "qty": 1234567.0, "qtyUnitAbbr": "u"},
    ],
}

TAIWAN_META = {
    "result": {
        "distribution": [
            {"resourceDescription": "海關進出口貿易統計(月)",
             "resourceFormat": "CSV",
             "resourceDownloadUrl": "https://example.gov.tw/trade.csv"},
        ],
    },
}

TAIWAN_CSV = "﻿" + (
    "年月,進出口別,稅則號別,貨名,國家,美元(千元),重量(公斤)\n"
    "11501,進口,8542,積體電路,南韓,1234567,890123\n"
    "11501,出口,8471,自動資料處理機,美國,7654321,456789\n"
    "11502,出口,0306,甲殼類動物,日本,4321,98765\n"
)


class CensusTest(unittest.TestCase):
    def test_parse_and_classify(self):
        with mock.patch.object(us_census, "get",
                               return_value=FakeResponse(CENSUS_IMPORTS)):
            records = us_census.fetch(flow="import", period="2026-01",
                                      partner="5830")
        self.assertEqual(len(records), 3)
        rec = records[0]
        self.assertEqual((rec.source, rec.flow, rec.partner),
                         ("us_census", "import", "TAIWAN"))
        self.assertEqual(rec.value_usd, 9403871234.0)
        classify.classify_record(rec)
        self.assertEqual(rec.hs_section, "XVI")
        self.assertEqual(rec.category_zh, "機械及電機設備")
        fish = classify.classify_record(records[2])
        self.assertEqual(fish.hs_section, "I")

    def test_period_required(self):
        with self.assertRaises(ValueError):
            us_census.fetch(flow="import")


class ComtradeTest(unittest.TestCase):
    def test_parse(self):
        with mock.patch.object(un_comtrade, "get",
                               return_value=FakeResponse(COMTRADE_PAGE)):
            records = un_comtrade.fetch(flow="import", period="2026-01",
                                        reporter="842", partner="490")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].period, "2026-01")
        self.assertEqual(records[0].reporter, "USA")
        self.assertEqual(records[0].weight_kg, 120345678.0)
        shoes = classify.classify_record(records[1])
        self.assertEqual(shoes.hs_section, "XII")
        self.assertEqual(shoes.category_zh, "鞋、帽、傘")


class TaiwanTest(unittest.TestCase):
    def test_parse_roc_dates_and_flow(self):
        responses = {
            taiwan_mof.DATASET_META_URL: FakeResponse(TAIWAN_META),
            "https://example.gov.tw/trade.csv":
                FakeResponse(content=TAIWAN_CSV.encode("utf-8")),
        }
        with mock.patch.object(taiwan_mof, "get",
                               side_effect=lambda url, **kw: responses[url]):
            records = taiwan_mof.fetch()
        self.assertEqual(len(records), 3)
        ic = records[0]
        self.assertEqual(ic.period, "2026-01")   # ROC 11501 -> 2026-01
        self.assertEqual(ic.flow, "import")
        self.assertEqual(ic.partner, "南韓")
        self.assertEqual(classify.classify_record(ic).hs_section, "XVI")
        self.assertEqual(records[1].flow, "export")

    def test_period_filter(self):
        responses = {
            taiwan_mof.DATASET_META_URL: FakeResponse(TAIWAN_META),
            "https://example.gov.tw/trade.csv":
                FakeResponse(content=TAIWAN_CSV.encode("utf-8")),
        }
        with mock.patch.object(taiwan_mof, "get",
                               side_effect=lambda url, **kw: responses[url]):
            records = taiwan_mof.fetch(period="2026-02")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].description, "甲殼類動物")


class StorageTest(unittest.TestCase):
    def test_upsert_idempotent_and_summary(self):
        with mock.patch.object(us_census, "get",
                               return_value=FakeResponse(CENSUS_IMPORTS)):
            records = us_census.fetch(flow="import", period="2026-01")
        for rec in records:
            classify.classify_record(rec)
        conn = storage.connect(":memory:")
        storage.upsert_records(conn, records)
        storage.upsert_records(conn, records)  # re-run must not duplicate
        count, = conn.execute("SELECT COUNT(*) FROM trade_records").fetchone()
        self.assertEqual(count, 3)
        summary = storage.category_summary(conn, "2026-01")
        self.assertEqual(summary[0][0], "XVI")  # machinery is the biggest
        # raw column must round-trip as JSON
        raw, = conn.execute("SELECT raw FROM trade_records LIMIT 1").fetchone()
        self.assertIn("CTY_NAME", json.loads(raw))


if __name__ == "__main__":
    unittest.main()
