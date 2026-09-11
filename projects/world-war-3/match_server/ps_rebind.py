#!/usr/bin/env python3
"""Post-NotifyLoadedWorld PlayerState rebind helpers.

Live evidence (identity-aligned session 2026-08-04): Login Name/Steam match PS,
but PlayerState sync stays false. Client sends ServerNotifyLoadedWorld (map paths
on ch2) before/during ownership drip. Re-sending local PS + PC RepLayout after
both (a) client loaded world and (b) PS channel opened gives the controller a
second chance to bind NetGUID 9362 once the client is ready.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from actor_channel import Bits, read_content_blocks, read_new_actor, write_content_block
from netguid import PackageMap, GuidReader, GuidWriter
from ps_identity import bits_to_bytes

HERE = Path(__file__).resolve().parent
MAP_PATH_MARKERS = (b"/Game/Maps/", b"WW3_Gobi", b"Dunhuang", b"Dunghuang")


def payload_has_loaded_world_marker(bits: list[int]) -> bool:
    """True if bunch payload looks like ServerNotifyLoadedWorld (streamed map paths)."""
    if len(bits) < 64:
        return False
    for off in range(8):
        raw = bits_to_bytes(bits, off)
        if any(m in raw for m in MAP_PATH_MARKERS):
            return True
    return False


GAMEPLAY_DOM_MARKERS = (
    b"Gameplay_New_DOM",
    b"Dunhuang_Gameplay",
    b"Gameplay_DOM",
)

SPAWN_LEVEL_MARKERS = (
    b"WW3_Dunghuang_Kwein_New_L",
    b"Dunghuang_Kwein_New_L",
    b"Gameplay_New_DOM",
    b"Gameplay_DOM",
)


def payload_has_spawn_level_visibility(bits: list[int]) -> bool:
    """True when an incoming level-visibility RPC names the match spawn level."""
    if len(bits) < 32:
        return False
    for off in range(8):
        raw = bits_to_bytes(bits, off)
        if any(m in raw for m in SPAWN_LEVEL_MARKERS):
            return True
    return False


def payload_has_gameplay_dom(bits: list[int]) -> bool:
    """True if NotifyLoadedWorld (or similar) payload mentions Gameplay_DOM sublevel."""
    if len(bits) < 64:
        return False
    for off in range(8):
        raw = bits_to_bytes(bits, off)
        if any(m in raw for m in GAMEPLAY_DOM_MARKERS):
            return True
    return False


def extract_map_path_strings(bits: list[int]) -> list[str]:
    """Best-effort ASCII /Game/Maps/... strings from a bit payload (any bit offset)."""
    found: set[str] = set()
    if len(bits) < 64:
        return []
    import re
    for off in range(8):
        raw = bits_to_bytes(bits, off)
        for m in re.findall(rb"/Game/Maps/[A-Za-z0-9_/\.]+", raw):
            found.add(m.decode("ascii", errors="ignore"))
    return sorted(found)


def bunch_payload_bits(bunch: dict) -> list[int]:
    r = bunch["reader"]
    start = bunch["payloadStart"]
    nbits = bunch["bunchDataBits"]
    return [((r.data[(start + i) >> 3] >> ((start + i) & 7)) & 1) for i in range(nbits)]


def extract_pc_rep_layout_bits(stream_path: Optional[Path] = None) -> list[int]:
    """819-bit PC actor RepLayout from capture PC open (stream idx 0–1)."""
    path = stream_path or (HERE / "real_replay_stream.json")
    stream = json.loads(path.read_text(encoding="utf-8"))
    bits: list[int] = []
    for i in (0, 1):
        bits.extend(int(c) for c in stream[i]["payload"])
    pm = PackageMap()
    gr = GuidReader(bits)
    gr.bit()
    n = gr.i32()
    for _ in range(n):
        pm.load_object(gr, exporting=True)
    r = Bits(bits, gr.pos)
    info = read_new_actor(r, pm)
    assert not info.get("incomplete"), info
    blocks = read_content_blocks(r)
    assert blocks and blocks[0].get("isActor") and blocks[0].get("hasRepLayout")
    return list(blocks[0]["payload"])


def build_pc_rep_layout_bunch_bits(rep_bits: Optional[list[int]] = None) -> list[int]:
    """Framed actor content block carrying the PC RepLayout (no NewActor header)."""
    rep = rep_bits if rep_bits is not None else extract_pc_rep_layout_bits()
    w = GuidWriter()
    write_content_block(w, rep, has_rep_layout=1)
    raw = w.get_bytes()
    out: list[int] = []
    for i in range(w.num):
        out.append((raw[i >> 3] >> (i & 7)) & 1)
    return out


def rebind_src_indices() -> list[int]:
    """Capture stream indices to re-send after NotifyLoadedWorld (PS + small PC RPCs)."""
    return [20, 21, 3, 4, 9]


def sanitize_rebind_spec(spec: dict) -> dict:
    """Re-send must NOT bOpen an already-open channel (live saw ch7 OPEN twice)."""
    out = dict(spec)
    out["bOpen"] = 0
    out["bClose"] = 0
    # Keep partial flags only if this is still a multi-bunch payload split;
    # PS 20–21 is a normal partial pair — allow Partial, but never Open.
    return out
