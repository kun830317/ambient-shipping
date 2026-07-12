# 海關進出口數據來源總整理

> 整理日期：2026-07-12。搭配 [`customs_pipeline/`](../customs_pipeline/README.md) 使用；
> 標註 ✅ 的來源已有現成 fetcher，指令可直接執行。

## 快速索引：我想查＿＿，該走哪條路？

| 需求 | 建議路線 | 指令 / 入口 |
|---|---|---|
| 美國每月進出口（HS × 國家） | ✅ US Census API | `fetch us-census --period 2026-03` |
| 台灣每月進出口 | ✅ 財政部開放資料 | `fetch taiwan-mof` |
| 越南（或任何國家）官方申報資料 | ✅ UN Comtrade | `fetch un-comtrade --reporter 704` |
| 最新月份、對方國還沒發布 | ✅ 鏡像資料（對手國視角） | `fetch us-census --partner 5520` |
| 某艘船/某公司實際載了什麼（提單層級） | Data Liberation Project / 商業來源 | 見第三節 |
| 台灣特定稅則深度查詢 | 關港貿單一窗口（人工） | portal.sw.nat.gov.tw |

---

## 一、統計彙總層級（HS 碼 × 國家 × 月份）— 免費、可自動化

### ✅ 1. US Census International Trade API
- **內容**：美國每月進出口金額，HS 2/4/6 碼 × 貿易夥伴國，2013 至今
- **費用**：免費；[申請 API key](https://api.census.gov/data/key_signup.html) 後每日額度較高（設 `CENSUS_API_KEY`）
- **更新**：每月初發布約兩個月前的資料
- **文件**：https://www.census.gov/data/developers/data-sets/international-trade.html
- **指令**：
  ```bash
  python -m customs_pipeline fetch us-census --flow import --period 2026-03 --partner 5830 --hs-level HS4
  ```

### ✅ 2. UN Comtrade+（全球官方貿易統計）
- **內容**：多數國家官方申報，年資料 1988 起、月資料 2000 起
- **費用**：免費；[註冊 key](https://uncomtrade.org/docs/how-to-create-an-account/) 後每日 500 次、每次 10 萬筆（設 `COMTRADE_API_KEY`）；無 key 走 preview 端點限 500 筆
- **注意**：各國上傳有數月延遲；台灣不是申報國（只能當 partner，代碼 490 "Other Asia, nes"）
- **入口**：https://comtradeplus.un.org/
- **指令**：
  ```bash
  python -m customs_pipeline fetch un-comtrade --reporter 704 --flow import --period 202601
  ```

### ✅ 3. 台灣 財政部關務署（政府資料開放平臺 #6053）
- **內容**：海關進出口貿易統計，每月更新，開放授權
- **注意**：金額單位是「美元（千元）」，跨來源比較記得 ×1000
- **入口**：https://data.gov.tw/dataset/6053
- **指令**：`python -m customs_pipeline fetch taiwan-mof`

### 4. 台灣深度查詢（人工操作，無穩定 API）
- [關港貿單一窗口 統計資料庫 GA30](https://portal.sw.nat.gov.tw/APGA/GA30)：稅則 × 國家 × 量值綜合查詢
- [國際貿易署 貿易統計系統](https://publicinfo.trade.gov.tw/cuswebo/)：可匯出 CSV

### 5. 越南官方（人工下載）
- [國家統計局 NSO/GSO 進出口專頁](https://www.nso.gov.vn/en/import-export/)：每月初步統計，多為 Excel/網頁表格
- 海關總局 customs.gov.vn：有統計專頁、無公開 API
- 程式化替代：Comtrade reporter=704（越南自報）＋ 鏡像資料（見下）

### 6. 輔助/交叉驗證來源
- [USITC DataWeb](https://dataweb.usitc.gov/)：美國貿易資料，免費註冊、含 API
- [World Bank WITS](https://wits.worldbank.org/)：整合 Comtrade，含關稅資料
- [CBP Public Data Portal](https://www.cbp.gov/newsroom/stats/cbp-public-data-portal)：美國海關執法/查驗統計
- [OEC 國家概況](https://oec.world/)：免費視覺化彙總（如 [越南](https://oec.world/en/profile/country/vnm)）

---

## 二、鏡像資料（Mirror Data）技巧

一個國家沒發布或延遲時，用**貿易對手國的視角**反推：

> 越南對美出口 ≈ 美國自越南進口（US Census，`--partner 5520`，更新最快）
> 台灣對日出口 ≈ 日本自台灣進口（Comtrade，`--reporter 392 --partner 490`）

注意鏡像值有系統性差異（CIF/FOB 計價、轉口歸屬），趨勢分析可用，精確對帳不行。

---

## 三、提單/報單層級（Bill of Lading）— 看「哪家公司、哪艘船、載什麼」

美國 CBP 依法公開 AMS 艙單欄位（船名、收貨人、託運人、貨物描述），但不提供官方下載：

| 管道 | 費用 | 說明 |
|---|---|---|
| [Data Liberation Project — CBP Bills of Lading](https://www.data-liberation-project.org/requests/cbp-bills-of-lading/) | 免費 | FOIA 取得 2013 起艙單並整理公開，**免費來源中最有希望** |
| 自行 FOIA 申請 | 免費 | 直接向 CBP 申請，需等數月 |
| [ImportInfo](https://www.importinfo.com/) | 部分免費 | 2012 起美國進口艙單，可免費查詢部分記錄 |
| [OEC Bill of Lading bulk](https://oec.world/en/resources/bulk-download/bill-of-lading) | 付費 | 已清理的 CBP 提單資料 |
| [PIERS (S&P Global)](https://www.spglobal.com/market-intelligence/en/solutions/products/piers) | 付費 | 業界標準，每日處理約 6 萬筆提單 |
| [AWS Marketplace US Imports](https://aws.amazon.com/marketplace/pp/prodview-ei2gunhs6akus) | 付費 | 雲端交付 |

- **越南報單層級**：無公開管道，只有商業供應商（vietnamexportdata.com、tradeint.com 等）
- **台灣報單層級**：不公開（關務資料保密），只有統計彙總

取得提單資料後的接法：新增 `sources/cbp_bol.py` fetcher → 貨物描述用
`classify.classify_text()` 分類 → 以船名＋到港日 join AIS 觀測（恢復本 repo 原始功能）。

---

## 四、常用國家代碼對照

| 國家/地區 | Census CTY_CODE（us-census 用） | UN M49（un-comtrade 用） |
|---|---|---|
| 台灣 | 5830 | 490（列為 "Other Asia, nes"） |
| 越南 | 5520 | 704 |
| 中國 | 5700 | 156 |
| 日本 | 5880 | 392 |
| 南韓 | 5800 | 410 |
| 香港 | 5820 | 344 |
| 新加坡 | 5590 | 702 |
| 美國 | —（reporter 本身） | 842 |

完整清單：[Census Schedule C](https://www.census.gov/foreign-trade/schedules/c/countrycodes.html)（使用前建議對一次官方表）·
[UN M49](https://unstats.un.org/unsd/methodology/m49/)

---

## 五、已完成 / 待辦

- [x] pipeline 三來源 fetcher、HS 21 類雙語分類、關鍵字分類、SQLite 去重、CLI、離線測試 6/6 通過
- [ ] 在有網路的機器上實跑三個 fetcher 驗證（開發沙箱無法對外連線）
- [ ] 申請 Comtrade / Census 免費 API key
- [ ] 追蹤 Data Liberation Project 提單資料集進度，寫 `sources/cbp_bol.py`
- [ ] （選配）越南 NSO Excel 月報 fetcher、提單資料與 AIS join
