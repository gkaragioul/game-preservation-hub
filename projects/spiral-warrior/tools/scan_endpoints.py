#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["intl_base", "intl_assets", "cn_apk", "strings"]
URL_RE = re.compile(rb"https?://[A-Za-z0-9_./:?=&%#@+\-]+")
IP_RE = re.compile(rb"(?<![0-9])(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?(?![0-9])")
NOISE = [b"adobe.com", b"w3.org", b"android.com", b"apache.org", b"github.com", b"schemas.android"]

def binary_scan(path: Path):
    try:
        data = path.read_bytes()
    except Exception:
        return []
    found=[]
    for regex in (URL_RE, IP_RE):
        for m in regex.findall(data):
            if any(n in m for n in NOISE):
                continue
            s=m.decode('utf-8','ignore').rstrip('\\')
            found.append(s)
    return found

def main():
    inventory={}
    for target in TARGETS:
        base=ROOT/target
        if not base.exists():
            continue
        for p in base.rglob('*'):
            if not p.is_file():
                continue
            for item in binary_scan(p):
                inventory.setdefault(item,set()).add(str(p.relative_to(ROOT)))
    out=ROOT/'research/endpoint_inventory.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w',encoding='utf-8') as f:
        f.write('# Endpoint Inventory\n\n')
        f.write('Generated from local extracted artifacts. Entries may include SDK/ad/library noise; prioritize `17m3`, `spinarena`, and `lxys` hosts.\n\n')
        for item in sorted(inventory):
            f.write(f'## `{item}`\n\n')
            for src in sorted(inventory[item])[:20]:
                f.write(f'- `{src}`\n')
            if len(inventory[item])>20:
                f.write(f'- ... {len(inventory[item])-20} more sources\n')
            f.write('\n')
    print(out)
    print(f'{len(inventory)} unique endpoint-like strings')

if __name__ == '__main__':
    main()
