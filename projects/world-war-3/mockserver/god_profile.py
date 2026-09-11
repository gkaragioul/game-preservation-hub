#!/usr/bin/env python3
r"""
god_profile.py -- rewrite the mock's profile/inventory responses so the player
has EVERYTHING: max level, huge currency, every item owned, weapons maxed.

Edits replay_map.json in place (backs up to replay_map.pre_godprofile.json).
Run:  python god_profile.py       then restart the mock (ww3_mock.ps1 down/up).
"""
import json, os

MAX_LEVEL = 100
BIG = 999_999_999

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay_map.json")
m = json.load(open(path, encoding="utf-8"))
http = m["http"]
json.dump(m, open(path.replace(".json", ".pre_godprofile.json"), "w", encoding="utf-8"), ensure_ascii=False)

# --- 1. the full item catalog = progression-tree rewards + season/BP award IDs
all_ids = set()
prog = http["GET /progression/getProgressionTree"]["body"]["result"]
for ent in prog.get("entities", []):
    for lvl in ent.get("levels", []):
        for it in lvl.get("rewards", {}).get("items", []):
            try: all_ids.add(int(it))
            except (ValueError, TypeError): pass
print(f"[*] item catalog from progression tree: {len(all_ids)} unique item IDs")

def collect_award_ids(node, into):
    """Pull numeric awardId / item ids from season & shop-shaped JSON."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("awardId", "itemId", "item") and v is not None:
                try:
                    into.add(int(v))
                except (ValueError, TypeError):
                    pass
            elif k == "items" and isinstance(v, list):
                for it in v:
                    try:
                        into.add(int(it))
                    except (ValueError, TypeError):
                        pass
            else:
                collect_award_ids(v, into)
    elif isinstance(node, list):
        for v in node:
            collect_award_ids(v, into)

bp_ids = set()
seas_pre = http.get("GET /season/getSeason", {}).get("body", {}).get("result", {})
if isinstance(seas_pre, dict):
    collect_award_ids(seas_pre, bp_ids)
    # Do NOT merge into all_ids — BP rewards must be earned from play.
    print(f"[*] season/BP award IDs noted (not auto-granted): {len(bp_ids)}")

# --- 2. profile: max level + currency
acc = http["GET /profileNew/{id}"]["body"]["AccountInfo"]
acc["playerLevel"] = MAX_LEVEL
acc["totalExperience"] = 999_999_999
acc["playerSeasonLevel"] = MAX_LEVEL
acc["playerSeasonExperience"] = 999_999
acc.setdefault("wallet", {})
acc["wallet"]["soft"] = BIG
acc["wallet"]["premium"] = BIG
print(f"[*] profile: level {MAX_LEVEL}, wallet soft/premium = {BIG}")

# --- 3. inventory: own everything + max weapon levels
inv = http["GET /inventory/get"]["body"]["result"]
owned = {it["id"] for it in inv.get("player", []) if isinstance(it, dict)} | \
        {it["id"] for it in inv.get("items", []) if isinstance(it, dict)}
added = 0
for iid in sorted(all_ids):
    if iid not in owned:
        inv.setdefault("player", []).append({"id": iid, "visited": True, "attachments": []})
        added += 1
for it in inv.get("items", []):
    if isinstance(it, dict):
        it["level"] = MAX_LEVEL
        it["experience"] = 0
print(f"[*] inventory: +{added} items (now {len(inv.get('player', []))} owned); "
      f"{len(inv.get('items', []))} leveled items maxed to L{MAX_LEVEL}")

# --- 3b. PROGRESSION STATE: max soldier level (unlocks all loadout slots) + weapon levels
pg = http.get("GET /progression/get", {}).get("body", {}).get("result", {})
if isinstance(pg, dict):
    pp = [e for e in prog.get("entities", []) if e.get("levels") and e["levels"][0].get("type") == "playerProgression"]
    smax = pp[0]["levels"][-1]["level"] if pp else 52
    sxp = (pp[0]["levels"][-1].get("requiredExperience", 999999) if pp else 999999) + 1_000_000
    if "player" in pg:
        pg["player"]["level"] = smax
        pg["player"]["experience"] = sxp
    for ent in pg.get("entities", []):
        if isinstance(ent, dict):
            ent["level"] = MAX_LEVEL
            ent["experience"] = 9_999_999
    acc["playerLevel"] = smax   # keep displayed rank == soldier progression cap
    print(f"[*] progression: soldier level -> {smax} (unlocks all loadout slots), "
          f"{len(pg.get('entities', []))} weapon progressions maxed")

# --- 4. season / battle pass: own the pass, but leave the track at 0 for real grind ---
seas = http.get("GET /season/getSeason", {}).get("body", {}).get("result", {})
if isinstance(seas, dict):
    seas["battlePassStatus"] = "activated"
    seas["isVisitedSeason"] = True
    if isinstance(seas.get("progression"), dict):
        seas["progression"]["level"] = 0
        seas["progression"]["experience"] = 0
    acc["playerSeasonLevel"] = 0
    acc["playerSeasonExperience"] = 0

    supported = seas.get("supportedBattlePasses") or {}
    premium_id = supported.get("premium") if isinstance(supported, dict) else None
    bp = seas.get("battlePass")
    if isinstance(bp, dict):
        bp["unlockedLevels"] = 0
        if premium_id is not None:
            bp["id"] = premium_id
        print(f"[*] season/BP: status=activated, track reset to 0 "
              f"(passId={bp.get('id')}) — levels unlock from play, not god-mode")
    else:
        print("[*] season: battlePass object missing; status forced activated at level 0")

    # Do not pre-grant season awardIds into inventory (collected above only for counting).
    # Strip any that were added by older god runs.
    inv = http.get("GET /inventory/get", {}).get("body", {}).get("result", {})
    if isinstance(inv, dict) and bp_ids:
        before = len(inv.get("player") or [])
        inv["player"] = [
            it for it in (inv.get("player") or [])
            if not (isinstance(it, dict) and it.get("id") in bp_ids)
        ]
        print(f"[*] stripped {before - len(inv['player'])} BP award items from inventory "
              f"({len(bp_ids)} season award ids)")

json.dump(m, open(path, "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n[OK] god-profile written to replay_map.json  (backup: replay_map.pre_godprofile.json)")
print("     restart the mock to load it:  ww3_mock.ps1 down  then  up")
