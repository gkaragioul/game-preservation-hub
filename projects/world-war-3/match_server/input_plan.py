#!/usr/bin/env python3
"""Build *bounded* synthetic-input plans as data, so they can be proven safe.

The client this drives is a live, hard-to-recover session (`_force_ue_crash.py`
is EAC-blocked on this build, so a wedged client costs a relaunch and a fresh
handshake).  The specific way synthetic input wedges a game is a keydown whose
keyup never arrives -- W held forever, or a mouse button stuck down.

Therefore every action is expressed as a list of events first, checked with
`plan_is_balanced`, and only then executed by `_send_input.py`.  Holds are
clamped to `MAX_HOLD_S` so no single event can hold a key indefinitely even if
the caller asks for it.

Set 1 scan codes (what `SendInput` with `KEYEVENTF_SCANCODE` wants).  UE4 reads
keyboard through raw input, which reports scan codes, so a virtual-key-only
injection is the usual reason "the game ignores my input".
"""
from __future__ import annotations

MAX_HOLD_S = 5.0

SCANCODES: dict[str, int] = {
    "escape": 0x01, "esc": 0x01,
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14,
    "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "enter": 0x1C, "return": 0x1C, "lctrl": 0x1D, "ctrl": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22,
    "h": 0x23, "j": 0x24, "k": 0x25, "l": 0x26,
    "lshift": 0x2A, "shift": 0x2A,
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30,
    "n": 0x31, "m": 0x32,
    "space": 0x39, "capslock": 0x3A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
    "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
}

BUTTONS = ("left", "right")


def _clamp_hold(hold_s: float) -> float:
    if hold_s < 0:
        raise ValueError(f"hold must be >= 0, got {hold_s}")
    return min(float(hold_s), MAX_HOLD_S)


def key_events(key: str, hold_s: float = 0.05) -> list[dict]:
    """down -> sleep(hold) -> up, for one key."""
    name = key.strip().lower()
    if name not in SCANCODES:
        raise KeyError(f"unknown key {key!r}")
    scan = SCANCODES[name]
    hold = _clamp_hold(hold_s)
    return [
        {"type": "key", "key": name, "scan": scan, "down": True},
        {"type": "sleep", "s": hold},
        {"type": "key", "key": name, "scan": scan, "down": False},
    ]


def click_events(x: int, y: int, button: str = "left",
                 hold_s: float = 0.05) -> list[dict]:
    """move to absolute screen (x, y) -> button down -> sleep -> button up."""
    if button not in BUTTONS:
        raise ValueError(f"button must be one of {BUTTONS}, got {button!r}")
    hold = _clamp_hold(hold_s)
    return [
        {"type": "mousemove", "x": int(x), "y": int(y)},
        {"type": "mouse", "button": button, "down": True},
        {"type": "sleep", "s": hold},
        {"type": "mouse", "button": button, "down": False},
    ]


def unbalanced_keys(events) -> list[str]:
    """Names still held down at the end of the plan (empty == safe)."""
    held: dict[str, int] = {}
    for e in events:
        if e["type"] == "key":
            name = e["key"]
        elif e["type"] == "mouse":
            name = f"mouse:{e['button']}"
        else:
            continue
        held[name] = held.get(name, 0) + (1 if e["down"] else -1)
    return sorted(k for k, v in held.items() if v != 0)


def plan_is_balanced(events) -> bool:
    return not unbalanced_keys(events)


def describe(events) -> str:
    parts = []
    for e in events:
        if e["type"] == "key":
            parts.append(f"{e['key']}{'v' if e['down'] else '^'}")
        elif e["type"] == "mouse":
            parts.append(f"{e['button']}{'v' if e['down'] else '^'}")
        elif e["type"] == "mousemove":
            parts.append(f"move({e['x']},{e['y']})")
        elif e["type"] == "sleep":
            parts.append(f"wait{e['s']:g}s")
    return " ".join(parts)
