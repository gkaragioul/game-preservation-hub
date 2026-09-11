#!/usr/bin/env python3
"""Runtime season / challenge progression applied when dedicated servers report results.

Does NOT invent grind — only applies XP / events that arrive on DS-facing endpoints.
"""
from __future__ import annotations

import time
from typing import Any


def now_ms() -> int:
    return int(time.time() * 1000)


def _season(replay: dict) -> dict | None:
    entry = replay.get("GET /season/getSeason")
    if not isinstance(entry, dict):
        return None
    body = entry.get("body")
    if isinstance(body, dict) and isinstance(body.get("result"), dict):
        return body["result"]
    return None


def _profile(replay: dict) -> dict | None:
    entry = replay.get("GET /profileNew/{id}")
    if not isinstance(entry, dict):
        return None
    body = entry.get("body")
    if isinstance(body, dict) and isinstance(body.get("AccountInfo"), dict):
        return body["AccountInfo"]
    return None


def _inventory(replay: dict) -> dict | None:
    entry = replay.get("GET /inventory/get")
    if not isinstance(entry, dict):
        return None
    body = entry.get("body")
    if isinstance(body, dict) and isinstance(body.get("result"), dict):
        return body["result"]
    return None


def _challenges(replay: dict) -> dict | None:
    entry = replay.get("GET /challenges")
    if not isinstance(entry, dict):
        return None
    body = entry.get("body")
    if isinstance(body, dict) and isinstance(body.get("result"), dict):
        return body["result"]
    return None


def _grant_award(replay: dict, award_id: Any) -> bool:
    try:
        iid = int(award_id)
    except (TypeError, ValueError):
        return False
    inv = _inventory(replay)
    if not isinstance(inv, dict):
        return False
    owned = {it.get("id") for it in (inv.get("player") or []) if isinstance(it, dict)}
    if iid in owned:
        return False
    inv.setdefault("player", []).append({"id": iid, "visited": True, "attachments": []})
    return True


def apply_season_xp(replay: dict, amount: float, multiplier: float = 1.0) -> dict:
    """Add season XP and unlock track levels + inventory awards as thresholds are crossed."""
    seas = _season(replay)
    if not isinstance(seas, dict):
        return {"ok": False, "reason": "no season"}
    try:
        amount = float(amount) * float(multiplier)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad amount"}
    if amount <= 0:
        return {"ok": True, "added": 0}

    prog = seas.setdefault("progression", {"id": "player", "level": 0, "experience": 0})
    level = int(prog.get("level") or 0)
    xp = float(prog.get("experience") or 0) + amount
    levels = (seas.get("progressionTree") or {}).get("levels") or []
    # Map level number -> requiredExperience to reach/clear that level
    req = {}
    for lv in levels:
        if isinstance(lv, dict) and lv.get("level") is not None:
            req[int(lv["level"])] = float(lv.get("requiredExperience") or 0)

    unlocked_awards = []
    max_level = max(req.keys()) if req else level
    # Spend XP climbing levels (requiredExperience is cost TO complete that level)
    guard = 0
    while guard < 200:
        guard += 1
        next_lvl = level + 1
        cost = req.get(next_lvl)
        if cost is None or cost <= 0:
            # no more paid ladder entries — keep residual XP on current level
            break
        if xp < cost:
            break
        xp -= cost
        level = next_lvl
        # Grant rewards for levels that are now reached
        for lv in levels:
            if not isinstance(lv, dict) or int(lv.get("level") or -1) != level:
                continue
            # Free levels always; paid levels require activated pass
            ltype = (lv.get("type") or "")
            status = (seas.get("battlePassStatus") or "").lower()
            if "paid" in ltype.lower() and status not in ("activated", "premium", "purchased"):
                continue
            for rew in lv.get("rewards") or []:
                if isinstance(rew, dict) and rew.get("awardId") is not None:
                    if _grant_award(replay, rew["awardId"]):
                        unlocked_awards.append(rew["awardId"])

    prog["level"] = level
    prog["experience"] = xp
    bp = seas.get("battlePass")
    if isinstance(bp, dict):
        bp["unlockedLevels"] = max(int(bp.get("unlockedLevels") or 0), level)

    acc = _profile(replay)
    if isinstance(acc, dict):
        acc["playerSeasonLevel"] = level
        acc["playerSeasonExperience"] = xp

    print(f"[PROG] season XP +{amount:.1f} (x{multiplier}) -> level={level} xp={xp:.1f} "
          f"awards+={len(unlocked_awards)}")
    return {"ok": True, "added": amount, "level": level, "experience": xp, "awards": unlocked_awards}


def apply_challenge_progress(replay: dict, challenge_id: str | None = None,
                             event_type: str | None = None, amount: int = 1) -> dict:
    """Increment matching active challenges (by id and/or eventType)."""
    ch = _challenges(replay)
    if not isinstance(ch, dict):
        return {"ok": False}
    bumped = []
    for bucket in ("dailyChallenges", "weeklyChallenges", "seasonChallenges"):
        for c in ch.get(bucket) or []:
            if not isinstance(c, dict) or c.get("completed") or not c.get("active", True):
                continue
            if challenge_id and c.get("id") != challenge_id:
                continue
            sc = c.get("successCondition")
            if not isinstance(sc, dict):
                continue
            if event_type and sc.get("eventType") and sc.get("eventType") != event_type:
                continue
            tgt = sc.get("targetValue")
            if not isinstance(tgt, (int, float)):
                continue
            cur = int(sc.get("currentValue") or 0) + int(amount)
            sc["currentValue"] = min(int(tgt), cur)
            if sc["currentValue"] >= int(tgt):
                c["completed"] = True
                c["completionDate"] = now_ms()
            bumped.append(c.get("id"))
    if bumped:
        print(f"[PROG] challenges updated: {bumped}")
    return {"ok": True, "updated": bumped}


def ingest_ds_payload(replay: dict, path: str, body: Any, xp_mult: float = 1.0) -> None:
    """Best-effort parse of dedicated-server / meta write payloads."""
    low = path.lower()
    data = body
    if isinstance(body, (bytes, bytearray)):
        try:
            import json
            data = json.loads(body.decode("utf-8", "replace") or "{}")
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}

    # Season XP fields seen in live profiles / possible DS posts
    for key in ("seasonExperienceDelta", "seasonXp", "seasonXP", "xp", "experience",
                "playerSeasonExperienceDelta", "addedSeasonExperience"):
        if key in data and isinstance(data[key], (int, float)):
            apply_season_xp(replay, data[key], xp_mult)
            break
    else:
        # Nested
        for nest in ("result", "progress", "player", "summary", "rewards"):
            sub = data.get(nest)
            if isinstance(sub, dict):
                for key in ("seasonExperienceDelta", "seasonXp", "xp", "experience"):
                    if key in sub and isinstance(sub[key], (int, float)):
                        apply_season_xp(replay, sub[key], xp_mult)
                        break

    # Challenge updates
    if "challenge" in low:
        apply_challenge_progress(
            replay,
            challenge_id=data.get("id") or data.get("challengeId"),
            event_type=data.get("eventType"),
            amount=int(data.get("amount") or data.get("value") or 1),
        )
    # Batch events
    events = data.get("events") or data.get("challengeEvents") or []
    if isinstance(events, list):
        for ev in events:
            if not isinstance(ev, dict):
                continue
            et = ev.get("eventType") or ev.get("type")
            if et:
                apply_challenge_progress(replay, event_type=str(et),
                                         amount=int(ev.get("amount") or 1))
