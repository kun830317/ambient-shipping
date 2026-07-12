"""Classification of trade records.

Two strategies, applied in order:

1. HS-code based (authoritative). The Harmonized System groups its 97
   chapters into 21 sections; the mapping below carries bilingual labels.
2. Keyword based (fallback). Bill-of-lading cargo descriptions are free
   text and often lack an HS code, so a keyword table maps common cargo
   words onto the same section categories.
"""

import re

# (chapter_start, chapter_end, section, category_en, category_zh)
HS_SECTIONS = [
    (1, 5,   "I",     "Live animals & animal products",            "活動物；動物產品"),
    (6, 14,  "II",    "Vegetable products",                        "植物產品"),
    (15, 15, "III",   "Animal & vegetable fats and oils",          "動植物油脂"),
    (16, 24, "IV",    "Prepared foodstuffs, beverages, tobacco",   "調製食品、飲料、菸酒"),
    (25, 27, "V",     "Mineral products",                          "礦產品"),
    (28, 38, "VI",    "Chemical products",                         "化學品"),
    (39, 40, "VII",   "Plastics & rubber",                         "塑膠及橡膠"),
    (41, 43, "VIII",  "Hides, skins, leather, furs",               "皮革及毛皮"),
    (44, 46, "IX",    "Wood & articles of wood",                   "木及木製品"),
    (47, 49, "X",     "Pulp, paper, printed matter",               "紙漿、紙及印刷品"),
    (50, 63, "XI",    "Textiles & textile articles",               "紡織品"),
    (64, 67, "XII",   "Footwear, headgear, umbrellas",             "鞋、帽、傘"),
    (68, 70, "XIII",  "Stone, cement, ceramics, glass",            "石料、水泥、陶瓷、玻璃"),
    (71, 71, "XIV",   "Precious metals, jewellery",                "珠寶及貴金屬"),
    (72, 83, "XV",    "Base metals & articles",                    "卑金屬及其製品"),
    (84, 85, "XVI",   "Machinery & electrical equipment",          "機械及電機設備"),
    (86, 89, "XVII",  "Vehicles, aircraft, vessels",               "車輛、航空器、船舶"),
    (90, 92, "XVIII", "Optical, precision instruments, clocks",    "光學精密儀器、鐘錶、樂器"),
    (93, 93, "XIX",   "Arms & ammunition",                         "武器及彈藥"),
    (94, 96, "XX",    "Miscellaneous manufactured articles",       "雜項製品"),
    (97, 97, "XXI",   "Works of art, antiques",                    "藝術品及古董"),
]

# Keyword fallback for free-text cargo descriptions (e.g. AMS bills of lading).
# Order matters: first match wins, so put the more specific words first.
KEYWORD_CATEGORIES = [
    (r"semiconductor|integrated circuit|electronic|computer|laptop|phone|"
     r"machin|motor|engine|pump|compressor|transformer|battery",
     "XVI", "Machinery & electrical equipment", "機械及電機設備"),
    (r"vehicle|automobile|auto part|car |cars |truck|bicycle|motorcycle|vessel|aircraft",
     "XVII", "Vehicles, aircraft, vessels", "車輛、航空器、船舶"),
    (r"furniture|chair|table|lamp|mattress|toy|game|sporting",
     "XX", "Miscellaneous manufactured articles", "雜項製品"),
    (r"apparel|garment|textile|fabric|cotton|polyester|yarn|clothing|t-shirt|knit",
     "XI", "Textiles & textile articles", "紡織品"),
    (r"footwear|shoe|boot|sandal|hat|cap|umbrella",
     "XII", "Footwear, headgear, umbrellas", "鞋、帽、傘"),
    (r"plastic|polymer|resin|rubber|tire|tyre",
     "VII", "Plastics & rubber", "塑膠及橡膠"),
    (r"steel|iron|aluminum|aluminium|copper|zinc|metal|nail|screw|wire",
     "XV", "Base metals & articles", "卑金屬及其製品"),
    (r"chemical|acid|fertilizer|pharmaceutical|medicament|paint|dye|soap|cosmetic",
     "VI", "Chemical products", "化學品"),
    (r"wood|timber|lumber|plywood|bamboo",
     "IX", "Wood & articles of wood", "木及木製品"),
    (r"paper|carton|cardboard|pulp|book",
     "X", "Pulp, paper, printed matter", "紙漿、紙及印刷品"),
    (r"petroleum|crude oil|gasoline|diesel|coal|ore|cement clinker|salt",
     "V", "Mineral products", "礦產品"),
    (r"glass|ceramic|tile|marble|granite|stone|cement",
     "XIII", "Stone, cement, ceramics, glass", "石料、水泥、陶瓷、玻璃"),
    (r"frozen|beef|pork|chicken|fish|shrimp|seafood|dairy|milk|cheese|egg",
     "I", "Live animals & animal products", "活動物；動物產品"),
    (r"rice|wheat|corn|soybean|coffee|tea|fruit|vegetable|nut|grain|flour",
     "II", "Vegetable products", "植物產品"),
    (r"food|beverage|wine|beer|juice|sugar|chocolate|snack|sauce|tobacco|cigarette",
     "IV", "Prepared foodstuffs, beverages, tobacco", "調製食品、飲料、菸酒"),
    (r"leather|handbag|fur",
     "VIII", "Hides, skins, leather, furs", "皮革及毛皮"),
    (r"jewel|gold |silver |diamond",
     "XIV", "Precious metals, jewellery", "珠寶及貴金屬"),
    (r"optical|camera|lens|medical instrument|clock|watch",
     "XVIII", "Optical, precision instruments, clocks", "光學精密儀器、鐘錶、樂器"),
]

_KEYWORD_RE = [(re.compile(pat, re.IGNORECASE), sec, en, zh)
               for pat, sec, en, zh in KEYWORD_CATEGORIES]


def classify_hs(hs_code):
    """Return (chapter, section, category_en, category_zh) for an HS code."""
    digits = re.sub(r"\D", "", str(hs_code or ""))
    if not digits:
        return "", "", "", ""
    chapter = int(digits[:2]) if len(digits) >= 2 else int(digits)
    for start, end, section, en, zh in HS_SECTIONS:
        if start <= chapter <= end:
            return "%02d" % chapter, section, en, zh
    return "%02d" % chapter, "", "Unclassified", "未分類"


def classify_text(description):
    """Return (section, category_en, category_zh) from a free-text description."""
    text = description or ""
    for regex, section, en, zh in _KEYWORD_RE:
        if regex.search(text):
            return section, en, zh
    return "", "Unclassified", "未分類"


def classify_record(record):
    """Fill in classification fields on a TradeRecord, in place."""
    chapter, section, en, zh = classify_hs(record.hs_code)
    if not section and record.description:
        section, en, zh = classify_text(record.description)
    record.hs_chapter = chapter
    record.hs_section = section
    record.category_en = en
    record.category_zh = zh
    return record
