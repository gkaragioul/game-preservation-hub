#!/usr/bin/env python3
"""Entitlement tiers for the offline mock (public / watcher x2 / helper god)."""
from __future__ import annotations

import json
import os
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "entitlements.json")

_DEFAULT = {
    "default_tier": "public",
    "xp_multipliers": {"public": 1.0, "watcher": 2.0, "helper": 1.0},
    "players": {},
    "helpers": [],
    "watchers": [],
}


def load() -> dict:
    if not os.path.exists(PATH):
        return dict(_DEFAULT)
    try:
        data = json.load(open(PATH, encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(_DEFAULT)
        return data
    except Exception:
        return dict(_DEFAULT)


def resolve_tier(player_ids: list[Any] | None = None) -> str:
    cfg = load()
    ids = []
    for x in player_ids or []:
        if x is None:
            continue
        ids.append(str(x).strip())
    players = cfg.get("players") or {}
    helpers = {str(x) for x in (cfg.get("helpers") or [])}
    watchers = {str(x) for x in (cfg.get("watchers") or [])}
    for i in ids:
        if i in players:
            return str(players[i])
        if i in helpers:
            return "helper"
        if i in watchers:
            return "watcher"
    return str(cfg.get("default_tier") or "public")


def xp_multiplier(tier: str) -> float:
    cfg = load()
    mults = cfg.get("xp_multipliers") or {}
    try:
        return float(mults.get(tier, 1.0))
    except (TypeError, ValueError):
        return 1.0
