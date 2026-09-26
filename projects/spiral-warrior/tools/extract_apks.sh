#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
for f in international_latest.xapk cn_9game.apk; do
  if [[ ! -f "$f" ]]; then
    echo "Missing required artifact: $f" >&2
    exit 1
  fi
done
mkdir -p intl_xapk intl_base intl_assets cn_apk
unzip -oq international_latest.xapk -d intl_xapk
unzip -oq intl_xapk/com.oversea.spinarena.apk -d intl_base
unzip -oq intl_xapk/NewAssets.apk -d intl_assets
unzip -oq cn_9game.apk -d cn_apk
echo "Extraction complete under $ROOT"
