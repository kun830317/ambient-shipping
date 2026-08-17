# 交付版面規範(Report Layout Spec)

這份規範管的是「讀者拿到的東西長什麼樣」。**三柱版與四柱版共用同一份規範、同一支腳本、同一組色票**——除了封面命柱卡是三張或四張、以及三柱版多一行標註與一節收尾附註,兩者的版面不得有任何差異。版面是產品識別,不是每次重新設計的東西。

## 交付雙檔原則

| 檔案 | 用途 | 命名 |
|---|---|---|
| `.md` | 內容本體、可再編輯 | `{稱呼}_三柱論命解析_{日期}.md` |
| `.pdf` | 交付版、排版完成品 | `{稱呼}_三柱論命解析_{日期}.pdf` |

(四柱版對應命名為 `{稱呼}_八字深度解析_{日期}`。)

markdown 是唯一內容來源,PDF 由腳本從 markdown 生成——**嚴禁為了排版好看而在 PDF 階段改動內容**,要改就改 markdown 再重跑。

## 色票(固定,不隨命盤變動)

| 用途 | 色值 | 說明 |
|---|---|---|
| 主色・藏藍 | `#1c3d5a` | 主標、章標、表頭、`<strong>` |
| 輔色・酒紅 | `#8b2635` | 章別標籤、小節側線、表格內強調、附註框邊 |
| 內文墨色 | `#26282c` | 正文 |
| 分隔線 | `#d9dde3` | 表格列線、封面短線 |
| 表格斑馬 | `#f5f7f9` | 偶數列底 |
| 附註框底 | `#f7f4ef` | 時辰解鎖清單 |

**不要**依命盤用神換色票。用神顏色是報告「內容」裡給讀者的建議,不是版面配色;每份報告長得不一樣會直接毀掉產品識別。

## 版面規格

- 紙張 A4,邊界 `20mm 17mm 22mm`
- 內文:Noto Serif TC(思源宋體)10.5pt / 行高 2.0 / 左右對齊
- 標題與表格:Noto Sans TC(思源黑體)
- **封面**(獨立一頁,置中):
  1. kicker 小字「三柱論命・深度解析」——酒紅、字距 .6em
  2. 主標 30pt 藏藍粗體
  3. 稱呼 13pt 灰、字距 .3em
  4. 命柱卡:每柱一張藏藍描邊圓角卡,卡內上方小字柱名(酒紅)、下方干支直排 24pt 粗體
  5. 短分隔線
  6. 標註行(三柱版:「時辰未知,以年月日三柱(六字)論命」)+ 產出日期
- **章首**:每章另起新頁。章別小字(酒紅、字距 .45em)+ 主標 17pt 藏藍 + 2.5px 藏藍底線
- **小節**:Noto Sans TC 粗體 12pt 藏藍,左側 4px 酒紅側線,`page-break-after: avoid`
- **表格**:藏藍表頭白字、偶列斑馬底、`page-break-inside: avoid`;表格內 `**粗體**` 轉酒紅
- **附註框**(時辰解鎖清單):米色底 + 4px 酒紅左邊框,字級 9.8pt

## 字型取得

環境常只有點陣中文字型(如文泉驛),直接輸出會很醜。首選思源字型,取得方式:

```bash
# 從 Google Fonts 抓 woff2 子集並組成本地 CSS(不需要系統安裝)
python3 - <<'PY'
import re, urllib.request, os
base = os.path.expanduser("~/fonts-web"); os.makedirs(base, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
css = ""
for fam, wts in [("Noto+Serif+TC", "400;700"), ("Noto+Sans+TC", "500;700")]:
    u = f"https://fonts.googleapis.com/css2?family={fam}:wght@{wts}&display=swap"
    css += urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode() + "\n"
for i, u in enumerate(sorted(set(re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css)))):
    fn = f"f{i:03d}.woff2"
    open(os.path.join(base, fn), "wb").write(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
    css = css.replace(u, fn)
open(os.path.join(base, "fonts.css"), "w").write(css)
PY
```

注意:GitHub 上的 noto-cjk 字型檔走 Git LFS,直接 `curl` 只會拿到 378 bytes 的指標檔——**抓完務必檢查檔案大小**。

## 產生 PDF

用 skill 內附的腳本,不要每次重寫:

```bash
python3 {skill}/scripts/build_report_pdf.py \
  --md "報告.md" --out "報告.pdf" --fonts ~/fonts-web
```

腳本自動判斷三柱/四柱(讀開頭的 `**三柱**` 或 `**四柱**` 行決定封面卡數量),自行完成 markdown→HTML→PDF。PDF 以無頭 Chromium 列印(環境已預裝於 `/opt/pw-browsers/chromium`,勿執行 `playwright install`)。

## 交付前版面檢查

- [ ] 中文沒有出現方框或缺字(抽查封面與任一章首,可用 `--screenshot` 目視)
- [ ] 封面命柱卡數量 = 實際柱數(三柱三張、四柱四張)
- [ ] 每章都從新頁開始,沒有標題孤行在頁尾
- [ ] 表格沒有跨頁斷裂
- [ ] 頁數落在合理範圍(全篇約 8000~9000 字 → 11~13 頁)
- [ ] 檔案內已嵌入字型(換裝置開啟不跑版)
