#!/usr/bin/env python3
r"""
render_pdf.py <markdown_file> <theme: manual|dossier> <out_pdf> [title]
Converts a Markdown deliverable into a styled, print-ready PDF via Chrome headless.
Two themes: 'manual' (clean readable curriculum) and 'dossier' (dark industrial case study).
"""
import sys, os, re, subprocess, markdown

MD, THEME, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
TITLE = sys.argv[4] if len(sys.argv) > 4 else os.path.basename(MD)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

raw = open(MD, encoding="utf-8").read()
# task-list checkboxes -> glyphs
raw = re.sub(r'(?m)^(\s*[-*])\s+\[ \]\s+', r'\1 ☐ ', raw)
raw = re.sub(r'(?m)^(\s*[-*])\s+\[[xX]\]\s+', r'\1 ☑ ', raw)
body = markdown.markdown(raw, extensions=["extra", "sane_lists", "toc", "attr_list"])

FONTS = ('--display:"Bahnschrift","Segoe UI Variable Display",sans-serif;'
         '--body:"Segoe UI","Segoe UI Variable Text",system-ui,sans-serif;'
         '--mono:"Cascadia Mono","Consolas",ui-monospace,monospace;')

MANUAL_CSS = f""":root{{{FONTS}
  --paper:#F4F3EF;--ink:#1B1D21;--soft:#41454B;--faint:#71757B;--hair:#D7D5CC;
  --accent:#A65F0C;--accent2:#33414E;--panel:#ECEAE3;--gun:#15181C;--ok:#2E7D51;--warn:#B0480F;}}
*{{box-sizing:border-box}} html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@page{{size:A4;margin:16mm 15mm 15mm}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:10.3pt;line-height:1.55}}
h1,h2,h3,h4{{font-family:var(--display);line-height:1.12;text-wrap:balance;margin:0}}
h1{{font-size:30pt;font-weight:700;margin:0 0 4mm;letter-spacing:.3px}}
h2{{font-size:18pt;font-weight:700;margin:11mm 0 3mm;padding:3mm 0 2mm;border-bottom:2.5px solid var(--ink);
   break-after:avoid;break-inside:avoid;letter-spacing:.2px}}
h3{{font-size:13pt;font-weight:600;margin:6mm 0 2mm;color:var(--accent2);break-after:avoid}}
h3::before{{content:"▎";color:var(--accent);margin-right:5px}}
h4{{font-size:11pt;margin:4mm 0 1.5mm;break-after:avoid}}
p{{margin:0 0 6pt}} strong{{font-weight:600}}
a{{color:var(--accent);text-decoration:none}}
code{{font-family:var(--mono);font-size:8.6pt;background:var(--panel);padding:1px 4px;border-radius:3px}}
pre{{background:var(--gun);color:#D6D9DE;font-family:var(--mono);font-size:8.2pt;line-height:1.5;
   padding:9pt 11pt;border-radius:5px;overflow-x:auto;break-inside:avoid;margin:4mm 0}}
pre code{{background:none;padding:0;color:inherit;font-size:8.2pt}}
blockquote{{margin:4mm 0;padding:7pt 11pt;background:#FBF3E6;border-left:4px solid var(--warn);
   border-radius:2px;break-inside:avoid;color:#4a3a22}}
blockquote p:last-child{{margin-bottom:0}}
table{{width:100%;border-collapse:collapse;margin:4mm 0;font-size:8.9pt;break-inside:avoid}}
th{{font-family:var(--mono);font-size:7.4pt;letter-spacing:.6px;text-transform:uppercase;text-align:left;
   background:var(--accent2);color:#fff;padding:5pt 7pt;border:1px solid var(--accent2)}}
td{{padding:5pt 7pt;border:1px solid var(--hair);vertical-align:top}}
tr:nth-child(even) td{{background:rgba(0,0,0,.025)}}
ul,ol{{margin:3mm 0 4mm;padding-left:7mm}} li{{margin-bottom:2.5pt}}
hr{{border:0;border-top:1px solid var(--hair);margin:8mm 0}}
"""

DOSSIER_CSS = f""":root{{{FONTS}
  --gun:#111418;--gun2:#181C21;--line:#2A2F36;--paper:#E8E6DF;--faint:#9BA1A8;
  --amber:#E7A21C;--amber2:#C98A16;--olive:#8A8A4E;--ink-panel:#1C2126;--ok:#54c98a;--warn:#E7A21C;}}
*{{box-sizing:border-box}} html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@page{{size:A4;margin:15mm 14mm}}
body{{margin:0;background:var(--gun);color:var(--paper);font-family:var(--body);font-size:10.2pt;line-height:1.55;
  background-image:linear-gradient(var(--line) .6px,transparent .6px),linear-gradient(90deg,var(--line) .6px,transparent .6px);
  background-size:16mm 16mm}}
h1,h2,h3,h4{{font-family:var(--display);line-height:1.12;text-wrap:balance;margin:0;color:#fff}}
h1{{font-size:34pt;font-weight:700;margin:0 0 4mm;color:var(--amber);letter-spacing:.4px}}
h2{{font-size:18pt;font-weight:700;margin:11mm 0 3mm;padding-bottom:2mm;border-bottom:2px solid var(--amber);
  break-after:avoid;break-inside:avoid;color:#fff;letter-spacing:.2px}}
h3{{font-size:12.5pt;font-weight:600;margin:6mm 0 2mm;color:var(--amber);break-after:avoid}}
h3::before{{content:"▚ ";color:var(--amber2)}}
h4{{font-size:11pt;margin:4mm 0 1.5mm;color:var(--paper);break-after:avoid}}
p{{margin:0 0 6pt}} strong{{font-weight:600;color:#fff}}
a{{color:var(--amber);text-decoration:none}}
em{{color:var(--faint);font-style:normal;font-family:var(--mono);font-size:8.4pt;letter-spacing:.5px}}
code{{font-family:var(--mono);font-size:8.6pt;background:#0C0E11;color:#D9C8A6;padding:1px 4px;border-radius:3px}}
pre{{background:#0B0D10;color:#C9CDD2;font-family:var(--mono);font-size:8.1pt;line-height:1.5;padding:9pt 11pt;
  border:1px solid var(--line);border-radius:5px;overflow-x:auto;break-inside:avoid;margin:4mm 0}}
pre code{{background:none;padding:0;color:inherit}}
blockquote{{margin:4mm 0;padding:7pt 11pt;background:var(--ink-panel);border-left:4px solid var(--amber);
  border-radius:2px;break-inside:avoid;color:#D9DCE0}}
blockquote p:last-child{{margin-bottom:0}}
table{{width:100%;border-collapse:collapse;margin:4mm 0;font-size:8.8pt;break-inside:avoid}}
th{{font-family:var(--mono);font-size:7.3pt;letter-spacing:.6px;text-transform:uppercase;text-align:left;
  background:#0C0E11;color:var(--amber);padding:5pt 7pt;border:1px solid var(--line)}}
td{{padding:5pt 7pt;border:1px solid var(--line);vertical-align:top}}
tr:nth-child(even) td{{background:rgba(255,255,255,.02)}}
ul,ol{{margin:3mm 0 4mm;padding-left:7mm}} li{{margin-bottom:2.5pt}}
hr{{border:0;border-top:1px solid var(--line);margin:8mm 0}}
"""

css = DOSSIER_CSS if THEME == "dossier" else MANUAL_CSS
html = f"<!doctype html><meta charset='utf-8'><title>{TITLE}</title><style>{css}</style><body>{body}</body>"
htmlpath = OUT.replace(".pdf", ".render.html")
open(htmlpath, "w", encoding="utf-8").write(html)
subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={OUT}", "file:///" + htmlpath.replace("\\", "/")],
               capture_output=True)
print(f"[OK] {THEME} PDF -> {OUT}  ({os.path.getsize(OUT)//1024} KB)" if os.path.exists(OUT) else "[FAIL] no PDF")
