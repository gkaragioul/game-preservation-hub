#!/usr/bin/env python3
"""
polish_offline.py -- apply the six offline menu polish edits to replay_map.json

1) Challenges kept active with fresh reset timers (progress from play, not pre-completed)
2) Friends list (sanitized placeholders)
3) Richer notifications
4) Minimal shop stub (from season BP shop products)
5) (buy/claim live updates live in rest_server.py)
6) (queue map preference lives in hub_server.py)

Run:  python polish_offline.py
Then restart mocks.
"""
from __future__ import annotations

import copy
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "replay_map.json")
BACKUP = os.path.join(HERE, "replay_map.pre_polish.json")


def main():
    m = json.load(open(PATH, encoding="utf-8"))
    json.dump(m, open(BACKUP, "w", encoding="utf-8"), ensure_ascii=False)
    http = m["http"]
    rpc = m.setdefault("rpc", {})
    now = int(time.time() * 1000)

    # --- 1) Challenges: keep ACTIVE (not auto-completed), fresh reset timers ---
    ch = http.get("GET /challenges", {}).get("body", {}).get("result", {})
    now = int(time.time() * 1000)
    daily_ms = now + 24 * 3600 * 1000
    weekly_ms = now + 7 * 24 * 3600 * 1000
    n_ch = 0
    if isinstance(ch, dict):
        for bucket, exp in (
            ("dailyChallenges", daily_ms),
            ("weeklyChallenges", weekly_ms),
            ("seasonChallenges", weekly_ms),
        ):
            for c in ch.get(bucket) or []:
                if not isinstance(c, dict):
                    continue
                c["completed"] = False
                c["active"] = True
                c["completionDate"] = None
                c["expiryDate"] = exp
                sc = c.get("successCondition")
                if isinstance(sc, dict):
                    sc["currentValue"] = 0
                n_ch += 1
    print(f"[*] challenges reset active (incomplete): {n_ch}")

    # --- 2) Friends: replace Invalid Token with sanitized offline friends ---
    friends = [
        {
            "id": 100002,
            "uniqueName": "OfflineTeammate",
            "status": 1,
            "lastseen": "2026-08-03T12:00:00.000Z",
            "level": 52,
            "levelIconId": 0,
            "bannerAttachmentsIds": [6382, 7953, 7224],
            "xmppAccount": {"username": "prod-100002"},
        },
        {
            "id": 100003,
            "uniqueName": "SquadBot",
            "status": 1,
            "lastseen": "2026-08-03T12:00:00.000Z",
            "level": 40,
            "levelIconId": 0,
            "bannerAttachmentsIds": [6382, 6624, 7224],
            "xmppAccount": {"username": "prod-100003"},
        },
        {
            "id": 100004,
            "uniqueName": "PreservationAlly",
            "status": 0,
            "lastseen": "2026-08-02T18:30:00.000Z",
            "level": 52,
            "levelIconId": 0,
            "bannerAttachmentsIds": [7859, 6624, 7858],
            "xmppAccount": {"username": "prod-100004"},
        },
    ]
    http["GET /friends/getAll"] = {"status": "200 OK", "body": {"result": friends}}
    http.setdefault(
        "GET /friends/getReceivedInvitations",
        {"status": "200 OK", "body": {"result": []}},
    )
    http.setdefault(
        "GET /friends/getSentInvitations",
        {"status": "200 OK", "body": {"result": []}},
    )
    print(f"[*] friends/getAll -> {len(friends)} offline placeholders")

    # --- 3) Notifications: prepend offline preservation news ---
    notif = rpc.get("notifications.getNotifications")
    if not isinstance(notif, dict):
        notif = {"notifications": {"news": []}}
    news = (notif.get("notifications") or {}).setdefault("news", [])
    if not isinstance(news, list):
        news = []
        notif.setdefault("notifications", {})["news"] = news
    banner = {
        "_id": "offline-preservation-banner",
        "id": "offline_preservation",
        "category": "news",
        "content": {
            "us": (
                "### Offline preservation mode\n\n"
                "Official servers are offline. You are running the local mock stack.\n\n"
                "- Battle Pass: owned, track starts at 0 (earn via play)\n"
                "- Inventory: god profile\n"
                "- Shop: minimal stub (BP offers only)\n"
                "- Matchmaking: local lobby handoff (Stage 2 match server still required for real fights)\n"
            ),
            "en": (
                "### Offline preservation mode\n\n"
                "Official servers are offline. You are running the local mock stack.\n"
            ),
        },
    }
    # avoid dupes on re-run
    news[:] = [n for n in news if isinstance(n, dict) and n.get("id") != "offline_preservation"]
    news.insert(0, banner)
    rpc["notifications.getNotifications"] = notif
    print(f"[*] notifications news entries: {len(news)}")

    # --- 4) Shop stub from season BP products ---
    seas = http.get("GET /season/getSeason", {}).get("body", {}).get("result", {})
    items = []
    shop_bp = seas.get("supportedBattlePassesInShop") if isinstance(seas, dict) else None
    if isinstance(shop_bp, dict):
        for key in ("premium", "normal"):
            prod = shop_bp.get(key)
            if isinstance(prod, dict):
                entry = copy.deepcopy(prod)
                entry.setdefault("id", prod.get("productId") or key)
                entry.setdefault("shopSlot", key)
                items.append(entry)
    bp = seas.get("battlePass") if isinstance(seas, dict) else None
    if isinstance(bp, dict) and isinstance(bp.get("tier"), dict):
        tier = copy.deepcopy(bp["tier"])
        tier.setdefault("shopSlot", "tierSkip")
        items.append(tier)

    shop_body = {
        "result": {
            "items": items,
            "offers": items,
            "shopItems": items,
            "seasonId": seas.get("id") if isinstance(seas, dict) else None,
            "battlePasses": shop_bp if isinstance(shop_bp, dict) else {},
            "generated": "offline-stub",
        }
    }
    http["GET /shop/getShopItems"] = {"status": "200 OK", "body": shop_body}
    print(f"[*] shop/getShopItems stub with {len(items)} offers")

    # Season/BP: own the pass, track starts at 0 (real dedicated-server grind)
    if isinstance(seas, dict):
        seas["battlePassStatus"] = "activated"
        seas["isVisitedSeason"] = True
        if isinstance(seas.get("progression"), dict):
            seas["progression"]["level"] = 0
            seas["progression"]["experience"] = 0
        if isinstance(bp, dict):
            bp["unlockedLevels"] = 0
            supported = seas.get("supportedBattlePasses") or {}
            if isinstance(supported, dict) and supported.get("premium") is not None:
                bp["id"] = supported["premium"]
        # profile season fields if present
        acc = http.get("GET /profileNew/{id}", {}).get("body", {}).get("AccountInfo")
        if isinstance(acc, dict):
            acc["playerSeasonLevel"] = 0
            acc["playerSeasonExperience"] = 0

    json.dump(m, open(PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n[OK] wrote {PATH}")
    print(f"     backup: {BACKUP}")
    print("     restart mocks to load: ww3_mock.ps1 down / up")


if __name__ == "__main__":
    main()
