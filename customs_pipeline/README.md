# Customs Data Pipeline 海關數據自動抓取與分類

自動抓取公開海關進出口數據、正規化成統一格式、依 HS 稅則分類，並存入 SQLite 供分析。
本模組取代原本依賴的 Enigma Public API（該服務已於 2019 年後關閉）。

## 一、公開海關數據來源總覽

### 免費、可程式化存取（本 pipeline 已實作）

| 來源 | 內容 | 涵蓋範圍 | 存取方式 |
|---|---|---|---|
| [US Census International Trade API](https://www.census.gov/data/developers/data-sets/international-trade.html) | 美國每月進出口值，依 HS 2/4/6 碼 × 貿易夥伴國 | 2013 至今，每月更新 | REST API，免費（[申請 API key](https://api.census.gov/data/key_signup.html) 後額度較高） |
| [UN Comtrade+](https://comtradeplus.un.org/) | 全球多數國家官方貿易統計，HS 碼 × 國家 | 年資料 1988 起、月資料 2000 起 | REST API，[免費註冊](https://uncomtrade.org/docs/how-to-create-an-account/) 每日 500 次、每次 10 萬筆 |
| [台灣 政府資料開放平臺 #6053](https://data.gov.tw/dataset/6053) | 財政部關務署海關進出口貿易統計 | 每月更新 | 開放授權檔案下載 |

### 提單（Bill of Lading）層級資料 — 本 repo 原本的用途

美國 CBP 依法必須公開 AMS 艙單的部分欄位（船名、收貨人、託運人、貨物描述等），
但 CBP 自己不提供下載，取得管道：

- [Data Liberation Project — CBP Bills of Lading](https://www.data-liberation-project.org/requests/cbp-bills-of-lading/)：透過 FOIA 向 CBP 索取 2013 年起的艙單資料並整理公開，是目前最有希望的**免費**大宗提單來源
- [OEC Bill of Lading bulk download](https://oec.world/en/resources/bulk-download/bill-of-lading)：已清理的 CBP 提單資料，需購買
- [ImportInfo](https://www.importinfo.com/)（可免費查詢部分記錄）、[PIERS (S&P Global)](https://www.spglobal.com/market-intelligence/en/solutions/products/piers)、[AWS Marketplace US Imports Data](https://aws.amazon.com/marketplace/pp/prodview-ei2gunhs6akus) 等商業來源
- 自行向 CBP 提出 FOIA 申請（免費但需數月）

### 台灣深度查詢（互動式，無穩定 API）

- [關港貿單一窗口 統計資料庫](https://portal.sw.nat.gov.tw/APGA/GA30)：稅則 × 國家 × 量值綜合查詢
- [國際貿易署 貿易統計系統](https://publicinfo.trade.gov.tw/cuswebo/)：可匯出 CSV

### 其他輔助來源

- [CBP Public Data Portal](https://www.cbp.gov/newsroom/stats/cbp-public-data-portal)：美國海關執法/查驗統計
- [USITC DataWeb](https://dataweb.usitc.gov/)：美國貿易資料查詢（免費註冊，含 API）
- [World Bank WITS](https://wits.worldbank.org/)：整合 Comtrade 的關稅與貿易資料

## 二、架構設計

```
                 ┌─────────────────────────────┐
   排程(cron)──▶ │  sources/   各來源 fetcher    │   每個 fetcher 負責一個 API/檔案格式
                 │  us_census / un_comtrade /   │   輸出統一的 TradeRecord
                 │  taiwan_mof                  │
                 └──────────────┬──────────────┘
                                ▼
                 ┌─────────────────────────────┐
                 │  schema.TradeRecord 正規化    │   來源/流向/期間/國家/HS碼/貨名/金額…
                 └──────────────┬──────────────┘
                                ▼
                 ┌─────────────────────────────┐
                 │  classify.py 兩層分類         │   1. HS 章 → 21 個 HS 類（權威）
                 │                              │   2. 貨名關鍵字 → 類別（提單自由文字用）
                 └──────────────┬──────────────┘
                                ▼
                 ┌─────────────────────────────┐
                 │  storage.py  SQLite upsert   │   唯一鍵去重、可重跑、可匯出 CSV
                 └─────────────────────────────┘
```

設計重點：

- **統一 schema**：所有來源都轉成 `TradeRecord`，下游分析不用管資料從哪來
- **兩層分類**：有 HS 碼就用 HS 章對應到 21 個 HS 類（中英文標籤）；
  只有自由文字貨名（例如提單）就用關鍵字表歸到同一套類別
- **可重跑（idempotent）**：以 (來源, 流向, 期間, 國家, HS碼, 貨名) 為唯一鍵 upsert，
  排程重複執行不會產生重複資料
- **禮貌抓取**：自訂 User-Agent、指數退避重試、尊重 rate limit

## 三、使用方式

```bash
pip install requests   # 唯一的第三方相依

# 抓美國 2026-03 進口（HS 2 碼 × 全部國家），分類後存入 customs.db
python -m customs_pipeline fetch us-census --flow import --period 2026-03

# 只抓美國從台灣(CTY_CODE=5830)的進口，HS 4 碼
python -m customs_pipeline fetch us-census --period 2026-03 --partner 5830 --hs-level HS4

# UN Comtrade：美國(842)自中國(156)進口，2026-01（建議先設定免費 key）
export COMTRADE_API_KEY=你的key
python -m customs_pipeline fetch un-comtrade --reporter 842 --partner 156 --period 202601

# 台灣財政部開放資料
python -m customs_pipeline fetch taiwan-mof

# 各類別金額統計 / 匯出 CSV
python -m customs_pipeline summary --period 2026-03
python -m customs_pipeline export --out trade.csv
```

### 自動排程（每月官方資料發布後抓取）

```cron
# 美國 Census 約每月初發布前兩個月資料；每月 10 日抓一次
0 6 10 * * cd /path/to/ambient-shipping && python -m customs_pipeline fetch us-census --period $(date -d "2 months ago" +\%Y-\%m) >> customs.log 2>&1
0 7 10 * * cd /path/to/ambient-shipping && python -m customs_pipeline fetch taiwan-mof >> customs.log 2>&1
```

## 四、與 AIS 功能的銜接（下一步）

原本的流程是 AIS 訊號 → MMSI → 船名 → Enigma 提單查詢。Enigma 已關閉，建議：

1. 取得 Data Liberation Project 的 CBP 提單資料集（或 FOIA/商業來源）後，
   寫一個 `sources/cbp_bol.py` fetcher 把提單載入同一個 SQLite
2. 提單的貨物描述是自由文字，直接用 `classify.classify_text()` 分類
3. 以船名 (vessel name) + 到港日期 join AIS 觀測，即可還原
   「這艘經過的船上載著什麼」的原始功能
