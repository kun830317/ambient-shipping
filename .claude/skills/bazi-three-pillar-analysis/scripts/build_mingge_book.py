#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命格書渲染器 — markdown → PDF。三柱版與四柱版共用。

用法:
    python3 build_mingge_book.py --md 報告.md --out 報告.pdf [--fonts ~/fonts-web] [--screenshot chk.png]

標記語法見 references/report-layout.md。
"""
import argparse, html, os, pathlib, re, shutil, subprocess, sys, tempfile

NAVY, SEAL, INK = "#1f3864", "#c0392b", "#2b2b2b"
ELEM = {"木": "#2e7d32", "火": "#c62828", "土": "#8d6e63", "金": "#b8860b", "水": "#1565c0"}
SHENSHA_KIND = {"吉神": "#2e7d32", "凶煞": "#c0392b", "中性": "#8d6e63"}
GAN_ELEM = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土",
            "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
ZHI_ELEM = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
            "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
CN_NUM = ["壹", "貳", "參", "肆", "伍", "陸", "柒", "捌", "玖", "拾"]
CHROMIUM = ["/opt/pw-browsers/chromium", "/usr/bin/chromium", "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome"]


def elem_of(ch):
    return GAN_ELEM.get(ch) or ZHI_ELEM.get(ch)


def inline(s):
    """行內語法: **粗體** / {五行|詞} / `標籤`"""
    s = html.escape(s, quote=False)
    s = re.sub(r"\{(木|火|土|金|水)\|(.+?)\}",
               lambda m: f'<span style="color:{ELEM[m.group(1)]};font-weight:700">{m.group(2)}</span>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r'<span class="tag">\1</span>', s)
    return s


def color_ganzhi(ch, size):
    e = elem_of(ch)
    c = ELEM.get(e, INK)
    return f'<span style="color:{c};font-size:{size};font-weight:700">{ch}</span>'


class Doc:
    def __init__(self):
        self.meta, self.pillars, self.chart = {}, [], []
        self.interactions, self.dayun, self.keyyears = {}, [], []
        self.body = []


def parse(md):
    d = Doc()
    lines = md.splitlines()
    i, n = 0, len(lines)
    tbl = []

    def flush_tbl():
        nonlocal tbl
        if not tbl:
            return
        rows = [r for r in tbl if not re.match(r"^\|[\s\-:|]+\|$", r)]
        out = ['<table><thead>']
        for ri, r in enumerate(rows):
            cells = [c.strip() for c in r.strip().strip("|").split("|")]
            tag = "th" if ri == 0 else "td"
            if ri == 1:
                out.append("</thead><tbody>")
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
        out.append("</tbody></table>")
        d.body.append("".join(out))
        tbl = []

    def block(start):
        """收集 @xxx ... @end,回傳 (內容行, 下一個索引)"""
        buf, j = [], start
        while j < n and lines[j].strip() != "@end":
            buf.append(lines[j])
            j += 1
        return buf, j + 1

    while i < n:
        raw = lines[i]
        s = raw.strip()

        if s.startswith("|"):
            tbl.append(s); i += 1; continue
        flush_tbl()

        if s == "@meta":
            buf, i = block(i + 1)
            for b in buf:
                if ":" in b:
                    k, v = b.split(":", 1)
                    d.meta[k.strip()] = v.strip()
            continue
        if s == "@pillars":
            buf, i = block(i + 1)
            for b in buf:
                p = [x.strip() for x in b.split("|")]
                if len(p) >= 3:
                    d.pillars.append(p)
            continue
        if s == "@chart":
            buf, i = block(i + 1)
            for b in buf:
                p = [x.strip() for x in b.split("|")]
                if len(p) >= 2:
                    d.chart.append(p)
            continue
        if s == "@interactions":
            buf, i = block(i + 1)
            for b in buf:
                if ":" in b:
                    k, v = b.split(":", 1)
                    d.interactions[k.strip()] = v.strip()
            continue
        if s == "@dayun":
            buf, i = block(i + 1)
            for b in buf:
                p = [x.strip() for x in b.split("|")]
                if len(p) >= 4:
                    d.dayun.append(p)
            continue
        if s == "@keyyears":
            buf, i = block(i + 1)
            for b in buf:
                p = [x.strip() for x in b.split("|")]
                if len(p) >= 3:
                    d.keyyears.append(p)
            continue
        if s.startswith("@terrain "):
            head = s[len("@terrain "):]
            parts = [x.strip() for x in head.split("|")]
            el = parts[0] if parts else "木"
            label = parts[1] if len(parts) > 1 else ""
            headline = parts[2] if len(parts) > 2 else ""
            buf, i = block(i + 1)
            paras = "".join(f"<p>{inline(x.strip())}</p>" for x in buf if x.strip())
            d.body.append(
                f'<div class="terrain"><div class="badge" style="background:{ELEM.get(el, NAVY)}">{el}</div>'
                f'<div class="tbody"><div class="tlabel">{inline(label)}</div>'
                f'<div class="thead">{inline(headline)}</div>{paras}</div></div>')
            continue
        if s == "@os":
            buf, i = block(i + 1)
            d.body.append('<div class="os">' +
                          "".join(f"<p>{inline(x.strip())}</p>" for x in buf if x.strip()) + "</div>")
            continue
        if s == "@callout":
            buf, i = block(i + 1)
            d.body.append('<div class="callout">' +
                          "".join(f"<p>{inline(x.strip())}</p>" for x in buf if x.strip()) + "</div>")
            continue
        if s == "@bars":
            buf, i = block(i + 1)
            rows = [[x.strip() for x in b.split("|")] for b in buf if b.strip()]
            vals = []
            for r in rows:
                try:
                    vals.append(float(r[1]))
                except (IndexError, ValueError):
                    vals.append(0.0)
            mx = max(vals) or 1.0
            out = ['<div class="bars">']
            for r, v in zip(rows, vals):
                name = r[0]
                el = r[2] if len(r) > 2 else ""
                note = r[3] if len(r) > 3 else ""
                pct = max(v / mx * 100, 0)
                col = ELEM.get(el, "#999")
                shown = ("0.0 空" if v == 0 else f"{v:g}")
                out.append(
                    f'<div class="bar"><div class="bname">{name}</div>'
                    f'<div class="btrack"><div class="bfill" style="width:{pct:.1f}%;background:{col}"></div></div>'
                    f'<div class="bval">{shown}{("　" + note) if note else ""}</div></div>')
            out.append("</div>")
            d.body.append("".join(out))
            continue
        if s.startswith("@appendix ") or s.startswith("@letter "):
            kind = "appendix" if s.startswith("@appendix ") else "letter"
            title = s.split(" ", 1)[1].strip()
            cls = "page-appendix" if kind == "appendix" else "page-letter"
            d.body.append(f'<section class="{cls}"><h2 class="{kind}-title">{inline(title)}</h2>')
            i += 1
            continue
        if s == "@endsection":
            d.body.append("</section>"); i += 1; continue

        if s.startswith("## "):
            parts = s[3:].split("|")
            num = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else ""
            sub = parts[2].strip() if len(parts) > 2 else ""
            idx = CN_NUM.index(num) + 1 if num in CN_NUM else 0
            side = f"第{'一二三四五六七八九十'[idx-1]}章 · {name}" if idx else name
            d.body.append(
                f'<section class="chapter"><div class="chead">'
                f'<div class="cseal">{num}</div>'
                f'<div class="ctitle"><h2>{inline(name)}</h2><div class="csub">{inline(sub)}</div></div>'
                f'<div class="cside">{side}</div></div><div class="crule"></div>')
            i += 1
            continue
        if s.startswith("#### "):
            d.body.append(f'<div class="act">{inline(s[5:])}</div>'); i += 1; continue
        if s.startswith("### "):
            d.body.append(f'<h3><span class="dia">◆</span> {inline(s[4:])}</h3>'); i += 1; continue
        if s.startswith("# "):
            i += 1; continue
        if not s or s == "---":
            i += 1; continue

        d.body.append(f"<p>{inline(s)}</p>")
        i += 1

    flush_tbl()
    return d


def cover(d):
    cards = ""
    for p in d.pillars:
        lab, g, z = p[0], p[1], p[2]
        cards += (f'<div class="pcard"><div class="plab">{lab}</div>'
                  f'<div class="pgz">{color_ganzhi(g, "23pt")}<br>{color_ganzhi(z, "23pt")}</div></div>')
    seal = d.meta.get("印", "坤")
    ring = ('<svg width="46" height="46" viewBox="0 0 46 46">'
            '<circle cx="23" cy="23" r="15" fill="none" stroke="#ccc" stroke-width="1"/>' +
            "".join(f'<circle cx="{23+15*__import__("math").cos(a*3.14159/180):.1f}" '
                    f'cy="{23+15*__import__("math").sin(a*3.14159/180):.1f}" r="3" fill="{c}"/>'
                    for a, c in zip([270, 342, 54, 126, 198], list(ELEM.values()))) + "</svg>")
    return f"""<section class="cover"><div class="cframe">
<div class="ckicker">八 字 命 盤 深 度 解 析</div>
<div class="cmain">命 格 書</div>
<div class="cwho">{inline(d.meta.get('日主','').split('・')[0])}日主 · {inline(d.meta.get('稱呼',''))}</div>
<div class="pcards">{cards}</div>
<div class="credline"></div>
<div class="cpattern">{inline(d.meta.get('格局',''))}</div>
<div class="cvert">依你的盤 · 如實寫下</div>
<div class="cring">{ring}</div>
<div class="cseal-box">{seal}</div>
</div></section>"""


def chart_page(d):
    ncol = len(d.pillars) or 3
    labels = [p[0] for p in d.pillars] or ["年柱", "月柱", "日柱"]
    meta_keys = ["性別", "出生", "出生地", "節氣", "生肖", "日主", "月令", "起運"]
    cells = "".join(
        f'<div class="mi"><span class="mk">{k}</span><span class="mv">{inline(d.meta.get(k,""))}</span></div>'
        for k in meta_keys if d.meta.get(k))
    head = "".join(
        f'<th class="{"selfcol" if ("日" in l) else ""}">{l}</th>' for l in labels)

    rows = ""
    for r in d.chart:
        label, vals = r[0], r[1:1 + ncol]
        tds = ""
        for v in vals:
            if label in ("天干", "地支"):
                tds += f'<td class="big">{color_ganzhi(v.strip(), "19pt") if len(v.strip())==1 else inline(v)}</td>'
            elif label == "藏干":
                tds += ('<td class="hid">' +
                        "".join(color_ganzhi(c, "9.5pt") for c in v.strip() if elem_of(c)) + "</td>")
            elif label == "神煞":
                items = []
                for it in v.split(","):
                    it = it.strip()
                    if not it or it == "—":
                        continue
                    nm, _, kd = it.partition(":")
                    items.append(f'<div style="color:{SHENSHA_KIND.get(kd.strip(), INK)}">{nm}</div>')
                tds += f'<td class="ss">{"".join(items) or "—"}</td>'
            else:
                tds += f"<td>{inline(v)}</td>"
        rows += f'<tr><th class="rlab">{label}</th>{tds}</tr>'

    inter = "".join(
        f'<div class="ix"><span class="ik">{k}</span>{inline(v)}</div>'
        for k, v in d.interactions.items())

    dy = ""
    for e in d.dayun:
        gz, tg, age = e[0], e[1], e[2]
        cur = "cur" if len(e) > 4 and e[4] else ""
        dy += (f'<div class="dcell {cur}"><div class="dgz">{gz}</div>'
               f'<div class="dtg">{tg}</div><div class="dage">{age}</div></div>')

    note = d.meta.get("標註", "")
    return f"""<section class="page"><div class="corners"></div>
<h2 class="pgtitle">◈ {'三' if ncol==3 else '四'}柱命盤</h2>
<div class="mgrid">{cells}</div>
<table class="chart"><thead><tr><th class="rlab"></th>{head}</tr></thead><tbody>{rows}</tbody></table>
<div class="legend">圖例:<span style="color:#2e7d32">■ 吉神</span> <span style="color:#c0392b">■ 凶煞</span> <span style="color:#8d6e63">■ 中性</span></div>
{inter}
<div class="dtitle">大 運 流 轉</div><div class="dstrip">{dy}</div>
<div class="chartnote">{inline(note)}</div>
</section>"""


def dayun_chart(d):
    if not d.dayun:
        return ""
    W, H, PADL, PADB = 700, 190, 34, 26
    n = len(d.dayun)
    bw = (W - PADL - 10) / n
    mid = (H - PADB) / 2
    unit = (H - PADB) / 5.0
    parts = [f'<svg viewBox="0 0 {W} {H}" class="dchart">']
    for lv, lab in [(2, "大吉"), (1, "吉"), (0, "平"), (-1, "凶"), (-2, "大凶")]:
        y = mid - lv * unit
        parts.append(f'<text x="4" y="{y+3:.0f}" class="ylab">{lab}</text>')
        if lv == 0:
            parts.append(f'<line x1="{PADL}" y1="{y:.0f}" x2="{W-10}" y2="{y:.0f}" stroke="#2e7d32" stroke-width="1.2"/>')
    for k, e in enumerate(d.dayun):
        try:
            sc = float(e[3] or 0)
        except ValueError:
            sc = 0.0
        x = PADL + k * bw
        y = mid - sc * unit
        top, hgt = min(y, mid), abs(mid - y)
        col = "#2e7d32" if sc > 0 else ("#c0392b" if sc < 0 else "#999")
        if hgt > 0.5:
            parts.append(f'<rect x="{x:.0f}" y="{top:.0f}" width="{bw-2:.0f}" height="{hgt:.0f}" '
                         f'fill="{col}" opacity="0.18"/>')
        parts.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x+bw-2:.0f}" y2="{y:.0f}" stroke="{col}" stroke-width="1.6"/>')
        parts.append(f'<text x="{x+bw/2:.0f}" y="{H-12}" class="xlab">{e[0]}</text>')
        parts.append(f'<text x="{x+bw/2:.0f}" y="{H-2}" class="xage">{e[2]}</text>')
        if len(e) > 4 and e[4]:
            parts.append(f'<line x1="{x:.0f}" y1="6" x2="{x:.0f}" y2="{H-PADB:.0f}" '
                         f'stroke="{NAVY}" stroke-width="1" stroke-dasharray="3,3"/>')
            parts.append(f'<text x="{x+3:.0f}" y="12" class="nowlab">現在</text>')
    # 關鍵流年圓點:依歲數定位
    ages = []
    for e in d.dayun:
        try:
            ages.append(float(e[2]))
        except ValueError:
            ages.append(0.0)
    span = (ages[-1] - ages[0] + 10) if len(ages) > 1 else 10
    for ky in d.keyyears:
        try:
            age, sc = float(ky[1]), float(ky[2])
        except ValueError:
            continue
        x = PADL + (age - ages[0]) / span * (W - PADL - 10)
        y = mid - sc * unit
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3.4" '
                     f'fill="{"#2e7d32" if sc>0 else "#c0392b"}"/>')
    parts.append("</svg>")
    return "".join(parts)


CSS = f"""
:root {{ --navy:{NAVY}; --seal:{SEAL}; --ink:{INK}; --line:#d8d8d8; --band:#f5f6f8; --card:#faf9f6; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
@page {{ size:A4; margin:18mm 16mm 20mm; }}
body {{ font-family:'Noto Serif TC',serif; font-size:10.5pt; color:var(--ink); line-height:1.95; text-align:justify; }}
p {{ margin:0 0 .7em; }}
strong {{ color:var(--navy); }}
.tag {{ font-family:'Noto Sans TC',sans-serif; font-size:8.5pt; color:var(--seal);
        border:1px solid #e6cfcb; border-radius:3px; padding:1px 5px; margin-left:4px; white-space:nowrap; }}

/* 封面 */
.cover {{ page-break-after:always; height:252mm; position:relative; }}
.cframe {{ position:absolute; inset:0; border:1.5px solid #c9bfa5; outline:1px solid #c9bfa5;
           outline-offset:4px; display:flex; flex-direction:column; align-items:center;
           justify-content:center; text-align:center;
           background-image:radial-gradient(#e8e4da 0.7px, transparent 0.7px);
           background-size:14px 14px; }}
.ckicker {{ font-family:'Noto Sans TC',sans-serif; font-size:9.5pt; color:#9a9a9a;
            letter-spacing:.5em; text-indent:.5em; margin-bottom:16px; }}
.cmain {{ font-size:34pt; font-weight:700; color:var(--navy); letter-spacing:.14em; text-indent:.14em; }}
.cwho {{ font-family:'Noto Sans TC',sans-serif; font-size:12pt; color:#555; letter-spacing:.22em;
         text-indent:.22em; margin:14px 0 30px; }}
.pcards {{ display:flex; gap:16px; }}
.pcard {{ border:1px solid #d5d5d5; background:#fff; border-radius:3px; padding:9px 15px 12px; min-width:60px; }}
.plab {{ font-family:'Noto Sans TC',sans-serif; font-size:8pt; color:#8a8a8a;
         letter-spacing:.2em; text-indent:.2em; margin-bottom:5px; }}
.pgz {{ line-height:1.25; }}
.credline {{ width:44mm; border-top:1.4px solid var(--seal); margin:26px 0 14px; }}
.cpattern {{ font-family:'Noto Sans TC',sans-serif; font-size:9.5pt; color:#666;
             letter-spacing:.16em; text-indent:.16em; }}
.cvert {{ position:absolute; right:12mm; top:44%; writing-mode:vertical-rl; font-size:9pt;
          color:#9a9a9a; letter-spacing:.35em; }}
.cring {{ position:absolute; left:12mm; bottom:12mm; }}
.cseal-box {{ position:absolute; right:12mm; bottom:12mm; width:34px; height:34px; background:var(--seal);
              color:#fff; font-family:'Noto Sans TC',sans-serif; font-weight:700; font-size:15pt;
              display:flex; align-items:center; justify-content:center; border-radius:2px; }}

/* 通用頁 */
.page, .page-appendix, .page-letter {{ page-break-before:always; position:relative; padding-top:4mm; }}
.pgtitle {{ text-align:center; font-family:'Noto Sans TC',sans-serif; font-size:14pt; color:var(--navy);
            letter-spacing:.18em; margin-bottom:14px; }}
.mgrid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:3px 14px; margin-bottom:14px;
          font-family:'Noto Sans TC',sans-serif; font-size:9pt; }}
.mk {{ color:var(--navy); font-weight:700; margin-right:8px; }}
.mv {{ color:#555; }}

/* 命盤主表 */
table.chart {{ width:100%; border-collapse:collapse; font-family:'Noto Sans TC',sans-serif; font-size:9pt; }}
table.chart th, table.chart td {{ border:1px solid #e3e3e3; padding:4px 6px; text-align:center; }}
table.chart thead th {{ background:var(--navy); color:#fff; font-weight:500; font-size:9.5pt; padding:6px; }}
table.chart thead th.selfcol {{ background:var(--seal); }}
table.chart th.rlab {{ background:#fff; color:#9a9a9a; font-weight:500; width:46px; font-size:8.5pt; }}
table.chart td.big {{ padding:2px; }}
table.chart td.hid span {{ margin:0 1px; }}
table.chart td.ss {{ font-size:8pt; line-height:1.5; }}
.legend {{ text-align:right; font-family:'Noto Sans TC',sans-serif; font-size:8pt; color:#9a9a9a; margin:4px 0 10px; }}
.ix {{ font-family:'Noto Sans TC',sans-serif; font-size:9pt; line-height:1.8; }}
.ik {{ color:var(--navy); font-weight:700; margin-right:8px; }}
.dtitle {{ text-align:center; font-family:'Noto Sans TC',sans-serif; color:var(--navy); font-weight:700;
           letter-spacing:.3em; margin:14px 0 6px; font-size:10pt; }}
.dstrip {{ display:flex; gap:4px; }}
.dcell {{ flex:1; border:1px solid #e3e3e3; text-align:center; padding:5px 2px;
          font-family:'Noto Sans TC',sans-serif; }}
.dcell.cur {{ border:1.6px solid var(--navy); background:#eef2f8; }}
.dgz {{ font-weight:700; color:var(--navy); font-size:10pt; }}
.dtg {{ font-size:7.5pt; color:#777; }}
.dage {{ font-size:7pt; color:#aaa; }}
.chartnote {{ margin-top:12px; font-size:8.5pt; color:#9a9a9a; text-align:center; }}
.corners {{ position:absolute; inset:0; pointer-events:none;
  background:
   linear-gradient(var(--navy),var(--navy)) left  1mm top 1mm/10mm .8px no-repeat,
   linear-gradient(var(--navy),var(--navy)) left  1mm top 1mm/.8px 10mm no-repeat,
   linear-gradient(var(--navy),var(--navy)) right 1mm top 1mm/10mm .8px no-repeat,
   linear-gradient(var(--navy),var(--navy)) right 1mm top 1mm/.8px 10mm no-repeat; opacity:.55; }}

/* 章首 */
.chapter {{ page-break-before:always; padding-top:2mm; }}
.chead {{ display:flex; align-items:flex-start; gap:12px; position:relative; }}
.cseal {{ width:30px; height:30px; border:1.6px solid var(--seal); color:var(--seal);
          font-family:'Noto Sans TC',sans-serif; font-weight:700; font-size:13pt;
          display:flex; align-items:center; justify-content:center; flex:0 0 auto; }}
.ctitle h2 {{ font-family:'Noto Sans TC',sans-serif; font-size:16pt; color:var(--navy); line-height:1.3; }}
.csub {{ font-size:9pt; color:#8a8a8a; margin-top:2px; }}
.cside {{ position:absolute; right:0; top:0; writing-mode:vertical-rl; font-size:7.5pt;
          color:#b0b0b0; letter-spacing:.14em; max-height:32mm; }}
.crule {{ border-top:1.6px solid var(--navy); margin:10px 0 16px; }}

h3 {{ font-family:'Noto Sans TC',sans-serif; font-size:12pt; color:var(--navy); font-weight:700;
      margin:1.5em 0 .6em; line-height:1.5; page-break-after:avoid; }}
h3 .dia {{ color:var(--seal); margin-right:3px; }}
.act {{ font-family:'Noto Sans TC',sans-serif; color:var(--seal); font-size:10pt; font-weight:700;
        letter-spacing:.28em; text-indent:.28em; margin:1.3em 0 .7em; page-break-after:avoid; }}

/* 地形卡 */
.terrain {{ display:flex; gap:10px; background:var(--card); border:1px solid #ece7dc; border-radius:5px;
            padding:11px 13px; margin:0 0 10px; page-break-inside:avoid; }}
.badge {{ width:22px; height:22px; border-radius:50%; color:#fff; font-family:'Noto Sans TC',sans-serif;
          font-size:10pt; font-weight:700; display:flex; align-items:center; justify-content:center; flex:0 0 auto; }}
.tlabel {{ font-family:'Noto Sans TC',sans-serif; font-size:8.5pt; color:#9a9a9a; }}
.thead {{ font-family:'Noto Sans TC',sans-serif; font-size:11pt; font-weight:700; color:var(--navy);
          margin:1px 0 6px; line-height:1.45; }}
.tbody p {{ font-size:10pt; margin-bottom:.5em; }}

.os {{ border-left:3px solid #cfcfcf; padding:2px 0 2px 12px; margin:.5em 0 1em; color:#6b6b6b; }}
.os p {{ font-size:10pt; margin:0; }}
.callout {{ background:var(--band); border-left:4px solid var(--seal); padding:12px 15px;
            margin:1.2em 0; page-break-inside:avoid; }}
.callout p {{ color:var(--navy); font-weight:700; margin:0; }}

/* 能量條 */
.bars {{ margin:.6em 0 1em; font-family:'Noto Sans TC',sans-serif; }}
.bar {{ display:flex; align-items:center; gap:8px; margin-bottom:5px; }}
.bname {{ width:34px; font-size:9pt; font-weight:700; color:var(--navy); text-align:right; }}
.btrack {{ flex:1; background:#eee; height:13px; border-radius:2px; }}
.bfill {{ height:13px; border-radius:2px; }}
.bval {{ width:88px; font-size:8.5pt; color:#777; }}
.dchart {{ width:100%; height:auto; margin:6px 0 4px; }}
.ylab {{ font-size:7px; fill:#999; font-family:'Noto Sans TC',sans-serif; }}
.xlab {{ font-size:8px; fill:#444; text-anchor:middle; font-family:'Noto Sans TC',sans-serif; }}
.xage {{ font-size:6.5px; fill:#aaa; text-anchor:middle; font-family:'Noto Sans TC',sans-serif; }}
.nowlab {{ font-size:7px; fill:{NAVY}; font-family:'Noto Sans TC',sans-serif; }}
.cap {{ font-size:8pt; color:#9a9a9a; margin-bottom:1em; }}

/* 表格 */
table {{ width:100%; border-collapse:collapse; margin:.4em 0 1em; font-size:9pt;
         font-family:'Noto Sans TC',sans-serif; line-height:1.65; page-break-inside:avoid; }}
th {{ background:var(--navy); color:#fff; font-weight:500; padding:6px 8px; text-align:left; }}
td {{ padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
tbody tr:nth-child(even) {{ background:#f7f8fa; }}
td strong {{ color:var(--seal); }}

/* 附錄與信 */
.appendix-title, .letter-title {{ text-align:center; font-family:'Noto Sans TC',sans-serif;
   font-size:13pt; color:var(--navy); letter-spacing:.32em; text-indent:.32em; margin:6mm 0 8mm; }}
.page-letter p {{ margin-bottom:.9em; }}
"""


def build_html(d):
    body = "".join(d.body)
    # 大運走勢圖插在第七章(大運篇)章首橫線後
    chart = dayun_chart(d)
    if chart:
        # 插在大運篇(柒)章首橫線之後
        m = re.search(r'<section class="chapter"><div class="chead"><div class="cseal">柒</div>.*?'
                      r'<div class="crule"></div>', body, re.S)
        if m:
            body = body[:m.end()] + chart + body[m.end():]
    return f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">
<link rel="stylesheet" href="fonts.css"><style>{CSS}</style></head><body>
{cover(d)}{chart_page(d)}{body}
</body></html>"""


def find_chromium():
    for c in CHROMIUM:
        if os.path.exists(c):
            return c
    w = shutil.which("chromium") or shutil.which("google-chrome")
    if w:
        return w
    sys.exit("找不到 Chromium(勿執行 playwright install)。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts", default=os.path.expanduser("~/fonts-web"))
    ap.add_argument("--screenshot")
    a = ap.parse_args()

    d = parse(pathlib.Path(a.md).read_text(encoding="utf-8"))
    wd = tempfile.mkdtemp(prefix="mingge-")
    fonts = os.path.expanduser(a.fonts)
    if os.path.exists(os.path.join(fonts, "fonts.css")):
        for f in os.listdir(fonts):
            shutil.copy(os.path.join(fonts, f), wd)
    else:
        print(f"警告:{fonts}/fonts.css 不存在,中文可能以點陣字型輸出。", file=sys.stderr)
        pathlib.Path(os.path.join(wd, "fonts.css")).write_text("", encoding="utf-8")

    hp = os.path.join(wd, "book.html")
    pathlib.Path(hp).write_text(build_html(d), encoding="utf-8")

    ch = find_chromium()
    base = [ch, "--headless=new", "--no-sandbox", "--disable-gpu",
            "--allow-file-access-from-files", "--virtual-time-budget=20000"]
    subprocess.run(base + ["--no-pdf-header-footer",
                           f"--print-to-pdf={os.path.abspath(a.out)}", f"file://{hp}"],
                   check=True, capture_output=True)
    if a.screenshot:
        subprocess.run(base + ["--window-size=1000,1414",
                               f"--screenshot={os.path.abspath(a.screenshot)}", f"file://{hp}"],
                       check=True, capture_output=True)
    sz = os.path.getsize(a.out)
    print(f"PDF 完成:{a.out}({sz/1e6:.1f} MB) · 命柱 {len(d.pillars)} 柱 · 大運 {len(d.dayun)} 步")
    if sz < 300_000:
        print("警告:檔案偏小,字型可能未嵌入。", file=sys.stderr)


if __name__ == "__main__":
    main()
