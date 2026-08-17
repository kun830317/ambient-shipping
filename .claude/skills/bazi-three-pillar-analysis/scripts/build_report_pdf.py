#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命理報告 markdown → PDF。三柱版與四柱版共用,版面規範見 references/report-layout.md。

用法:
    python3 build_report_pdf.py --md 報告.md --out 報告.pdf [--fonts ~/fonts-web] [--screenshot cover.png]

封面命柱卡數量由報告開頭的 `**三柱**` / `**四柱**` 行自動判斷。
"""
import argparse, html, os, pathlib, re, shutil, subprocess, sys, tempfile

CHROMIUM_CANDIDATES = [
    "/opt/pw-browsers/chromium",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
]

CSS = """
:root { --navy:#1c3d5a; --wine:#8b2635; --ink:#26282c; --line:#d9dde3; }
* { margin:0; padding:0; box-sizing:border-box; }
@page { size: A4; margin: 20mm 17mm 22mm; }
body { font-family:'Noto Serif TC', serif; font-size:10.5pt; color:var(--ink);
       line-height:2.0; text-align:justify; }
p { margin: 0 0 .85em; }
strong { color: var(--navy); }

.cover { page-break-after: always; display:flex; flex-direction:column;
         justify-content:center; align-items:center; height:235mm; text-align:center; }
.cover .kicker { font-family:'Noto Sans TC',sans-serif; font-weight:500; letter-spacing:.6em;
                 text-indent:.6em; color:var(--wine); font-size:10pt; margin-bottom:14px; }
.cover h1 { font-size:30pt; font-weight:700; color:var(--navy); letter-spacing:.08em; margin-bottom:6px; }
.cover .name { font-family:'Noto Sans TC',sans-serif; font-size:13pt; color:#555;
               margin-bottom:38px; letter-spacing:.3em; text-indent:.3em; }
.pillars { display:flex; gap:22px; margin-bottom:40px; }
.pillar { border:1.5px solid var(--navy); border-radius:6px; padding:14px 20px 16px; min-width:72px; }
.pillar .pl { font-family:'Noto Sans TC',sans-serif; font-size:9pt; color:var(--wine);
              letter-spacing:.35em; text-indent:.35em; margin-bottom:8px; }
.pillar .pg { font-size:24pt; font-weight:700; color:var(--navy); line-height:1.35; }
.cover .meta { font-family:'Noto Sans TC',sans-serif; font-size:9.5pt; color:#777; line-height:1.9; }
.cover .rule { width:58mm; border-top:1px solid var(--line); margin:26px 0; }

.chapter { page-break-before: always; margin:0 0 26px; padding-top:6mm; }
.chap-label { font-family:'Noto Sans TC',sans-serif; font-weight:500; color:var(--wine);
              font-size:10pt; letter-spacing:.45em; text-indent:.45em; margin-bottom:10px; }
.chapter h2 { font-size:17pt; font-weight:700; color:var(--navy); line-height:1.6;
              padding-bottom:12px; border-bottom:2.5px solid var(--navy); }
h3 { font-family:'Noto Sans TC',sans-serif; font-weight:700; font-size:12pt; color:var(--navy);
     margin:1.7em 0 .8em; padding-left:11px; border-left:4px solid var(--wine); line-height:1.5;
     page-break-after: avoid; }

table { width:100%; border-collapse:collapse; margin:.4em 0 1.1em; font-size:9.5pt;
        font-family:'Noto Sans TC',sans-serif; line-height:1.7; page-break-inside: avoid; }
th { background:var(--navy); color:#fff; font-weight:500; padding:7px 10px; text-align:left; }
td { padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
tbody tr:nth-child(even) { background:#f5f7f9; }
td strong { color:var(--wine); }

.epilogue { margin-top:30px; background:#f7f4ef; border-left:4px solid var(--wine);
            padding:16px 20px 8px; page-break-inside: avoid; }
.epilogue h4 { font-family:'Noto Sans TC',sans-serif; font-size:11pt; color:var(--wine); margin-bottom:10px; }
.epilogue p { font-size:9.8pt; line-height:1.95; }
"""


def inline(s):
    s = html.escape(s, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def md_to_html(md_text, kicker_default="深度解析"):
    lines = md_text.splitlines()
    i = 0
    name, pillars, note, date = "", [], "", ""
    pillar_word = ""

    # ---- header block: everything before the first '## '
    while i < len(lines) and not lines[i].startswith("## "):
        ln = lines[i].strip()
        if ln.startswith("# "):
            name = ln[2:].split("|")[0].strip()
        elif re.match(r"\*\*(三柱|四柱)\*\*", ln):
            pillar_word = re.match(r"\*\*(三柱|四柱)\*\*", ln).group(1)
            pillars = re.findall(r"(年柱|月柱|日柱|時柱)\s*(\S\S)", ln)
        elif ln.startswith("**標註**"):
            note = re.sub(r"\*\*標註\*\*[:：]\s*", "", ln)
        elif ln.startswith("**產出日期**"):
            date = re.sub(r"\*\*產出日期\*\*[:：]\s*", "", ln)
        i += 1

    body, tbl = [], []

    def flush_table():
        nonlocal tbl
        if not tbl:
            return
        rows = [r for r in tbl if not re.match(r"^\|[\s\-:|]+\|$", r)]
        out = ["<table>"]
        for ri, r in enumerate(rows):
            cells = [c.strip() for c in r.strip().strip("|").split("|")]
            tag = "th" if ri == 0 else "td"
            if ri == 0:
                out.append("<thead>")
            if ri == 1:
                out.append("<tbody>")
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            if ri == 0:
                out.append("</thead>")
        out.append("</tbody></table>")
        body.append("\n".join(out))
        tbl = []

    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("|"):
            tbl.append(ln.strip())
            i += 1
            continue
        flush_table()
        s = ln.strip()
        if not s or s == "---":
            i += 1
            continue
        if s.startswith("### "):
            t = s[4:]
            if t.startswith("附:") or t.startswith("附："):
                body.append(f'<div class="epilogue"><h4>{inline(t)}</h4>')
                i += 1
                while i < len(lines):
                    p = lines[i].strip()
                    if p and p != "---":
                        body.append(f"<p>{inline(p)}</p>")
                    i += 1
                body.append("</div>")
                break
            body.append(f"<h3>{inline(t)}</h3>")
        elif s.startswith("## "):
            parts = s[3:].split("|")
            chap = parts[0].strip()
            sub = parts[1].strip() if len(parts) > 1 else ""
            body.append(
                f'<section class="chapter"><div class="chap-label">{inline(chap)}</div>'
                f"<h2>{inline(sub)}</h2></section>"
            )
        elif s.startswith("# "):
            pass
        else:
            body.append(f"<p>{inline(s)}</p>")
        i += 1
    flush_table()

    cards = "".join(
        f'<div class="pillar"><div class="pl">{lab}</div>'
        f'<div class="pg">{gz[0]}<br>{gz[1]}</div></div>'
        for lab, gz in pillars
    )
    kicker = f"{pillar_word}論命・深度解析" if pillar_word == "三柱" else "八字命盤・深度解析"
    title = "三柱論命深度解析" if pillar_word == "三柱" else "八字深度解析"
    meta = (f"{inline(note)}<br>" if note else "") + f"產出日期&nbsp;{inline(date)}"

    return f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<link rel="stylesheet" href="fonts.css">
<style>{CSS}</style></head><body>
<div class="cover">
  <div class="kicker">{kicker}</div>
  <h1>{title}</h1>
  <div class="name">{inline(name)}</div>
  <div class="pillars">{cards}</div>
  <div class="rule"></div>
  <div class="meta">{meta}</div>
</div>
{"".join(body)}
</body></html>"""


def find_chromium():
    for c in CHROMIUM_CANDIDATES:
        if os.path.exists(c):
            return c
    which = shutil.which("chromium") or shutil.which("google-chrome")
    if which:
        return which
    sys.exit("找不到 Chromium。請確認 /opt/pw-browsers/chromium 存在(勿執行 playwright install)。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts", default=os.path.expanduser("~/fonts-web"),
                    help="含 fonts.css 與 woff2 的目錄(見 report-layout.md)")
    ap.add_argument("--screenshot", help="另存一張首頁截圖供目視檢查")
    args = ap.parse_args()

    md_text = pathlib.Path(args.md).read_text(encoding="utf-8")
    workdir = tempfile.mkdtemp(prefix="bazi-pdf-")

    fonts_dir = os.path.expanduser(args.fonts)
    css_path = os.path.join(fonts_dir, "fonts.css")
    if os.path.exists(css_path):
        for f in os.listdir(fonts_dir):
            shutil.copy(os.path.join(fonts_dir, f), workdir)
    else:
        print(f"警告:{css_path} 不存在,中文可能以系統點陣字型輸出。請先依 "
              f"report-layout.md 準備字型。", file=sys.stderr)
        pathlib.Path(os.path.join(workdir, "fonts.css")).write_text("", encoding="utf-8")

    html_path = os.path.join(workdir, "report.html")
    pathlib.Path(html_path).write_text(md_to_html(md_text), encoding="utf-8")

    chromium = find_chromium()
    base = [chromium, "--headless=new", "--no-sandbox", "--disable-gpu",
            "--allow-file-access-from-files", "--virtual-time-budget=15000"]
    subprocess.run(base + ["--no-pdf-header-footer",
                           f"--print-to-pdf={os.path.abspath(args.out)}",
                           f"file://{html_path}"],
                   check=True, capture_output=True)
    if args.screenshot:
        subprocess.run(base + ["--window-size=1000,1414",
                               f"--screenshot={os.path.abspath(args.screenshot)}",
                               f"file://{html_path}"],
                       check=True, capture_output=True)

    size = os.path.getsize(args.out)
    print(f"PDF 完成:{args.out}({size/1e6:.1f} MB)")
    if size < 300_000:
        print("警告:檔案偏小,字型可能未嵌入——請檢查 fonts.css。", file=sys.stderr)


if __name__ == "__main__":
    main()
