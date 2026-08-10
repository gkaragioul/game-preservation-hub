#!/usr/bin/env python3
"""Build the minimal M4 ownership bootstrap slice from real_replay_stream.json.

WW3 Client Synchronization gates LOADING MAP on:
  Controller, PlayerState, InventoryManager, CharacterAttachments,
  WeaponsAttachments, GameState, LocalClientConfigs, MapLevels.

Modes (WW3_BOOTSTRAP / --mode):
  ownership (default): PS 9362 early (after PC) so PC RepLayout can bind, then
    HUD → streaming → pawn → weapons → nudges → GameState.
  capture_order: do NOT move PS early — match capture join order through weapons,
    then local PS, then GameState. Use when debugging pawn ch3 reject (live:
    bit-exact pawn open but client never maps NetGUID 9372 / never sends on ch3).

Pawn open notes (investigation 2026-08-05):
  - Live S->C ch3 open is bit-identical to capture src 10–11.
  - SerializeNewActor has_scale; scale body is 109 bits then velocity=0 then
    subobject stubs 9374–9384 (InventoryManager has 98-bit RepLayout).
  - Archetype export guid 21 has network checksum; subobjects outer=9372 bNoLoad.
  - ClientRestart handle 9 framing OK; without mapped 9372, possession cannot Ack.

WW3_PAWN_SYNTH_IN_OPEN (default 0): inject APawn::PlayerState(17)/Controller(18)
into the ch3 open body (src 11) after SerializeNewActor and *before* subobject
stubs — the same order PC/PS opens use. Capture pawn open has no actor RepLayout;
post-open synth (WW3_PAWN_SYNTH_PROPS) did not flip the sync checklist.

WW3_PAWN_EXPORT_PREFIX (default 0, see pawn_export_prefix.py): re-emits the pawn open's own
archetype+level NetGUID export chain (guids 21/23, 5/7/9) as a standalone bunch on the
already-open PC channel (ch2) immediately before the (untouched) pawn ch3 open, so those
statics are registered before the client resolves the open bunch's own copy of them.

WW3_INV_ATTACH (default 0): also include the local player's inventory actors that the
clothing bunch's InventoryManager payload references — MSP 9402 (ch85 src 205–206),
secondary Glock 9412 (ch86 src 257–258), primary HK417 9410 (ch87 src 259–260), repair
kit 9408 (ch88 src 261–262). Without these, IM's WeaponsPreloadRequest object refs never
resolve. Pair with server-side CAM/IM resend (`cam_im_resend.py`) after ownership.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
STREAM = HERE / "real_replay_stream.json"
OUT = HERE / "ownership_bootstrap.json"

RANGES_OWNERSHIP = [
    (0, 1),
    (20, 21),
    (2, 17),
    (9, 9),
    (181, 181),
    (192, 192),
    (212, 213),
    (119, 121),
    # The real join stream opens the adjacent world actor channels (54-59)
    # immediately after GameState.  Keep these in the pre-possession bootstrap;
    # sending them only as post-ownership ambient traffic is too late for
    # UWW3ClientConnectionController to complete LoadingMap -> InGame.
    (122, 133),
    (215, 215),
    (275, 275),
]

RANGES_CAPTURE_ORDER = [
    (0, 17),
    (20, 21),
    (9, 9),
    (181, 181),
    (192, 192),
    (212, 213),
    (119, 121),
    (215, 215),
    (275, 275),
]

# Spliced into either mode when WW3_INV_ATTACH=1 (after nudges, around clothing).
INV_ATTACH_RANGES = [
    (205, 206),  # ch85 MobileSpawnPoint 9402
    (257, 262),  # ch86 secondary 9412, ch87 primary 9410, ch88 repair 9408
]

# WW3_WORLD_FILL=1: the rest of the capture's pre-deploy world.  The curated slice
# opens 16 channels; the working server had 108 (ch2..ch110) open before the client
# reported Server_OnMapOpened, and its last wave (ch95..ch110, src 966..996) lands
# immediately before that.  Without the capture points / bases / spawn points the
# deploy map widget has nothing to show, which is why the live client emits
# Server_OnMapClosed without ever emitting Server_OnMapOpened.
#
# Upper bounds are extended past the last open to keep every partial chain whole
# (180->183, 354->359, 996->997).
WORLD_FILL_RANGES = [
    (18, 118),    # ch6, ch8..ch52
    (134, 183),   # ch60..ch83
    (354, 359),   # ch84
    (400, 403),   # ch89, ch90
    (435, 436),   # ch91
    (938, 997),   # ch92..ch110 — the wave that precedes h281/h65
]
# Channels the curated ownership slice owns and patches (SteamID, pawn synth props,
# WAM/CAM strips).  World fill must never re-open or race those.
WORLD_FILL_LOCAL_CHANNELS = frozenset({2, 3, 4, 5, 7, 85, 86, 87, 88})


def _world_fill_indices(stream: list) -> list[int]:
    return [
        i
        for lo, hi in WORLD_FILL_RANGES
        for i in range(lo, min(hi, len(stream) - 1) + 1)
        if stream[i]["chIndex"] not in WORLD_FILL_LOCAL_CHANNELS
    ]


def _with_inv_attach(ranges: list) -> list:
    """Insert local-inventory actor opens around clothing when WW3_INV_ATTACH=1."""
    if os.environ.get("WW3_INV_ATTACH", "0") != "1":
        return ranges
    out: list = []
    inserted_pre = False
    inserted_post = False
    for a, b in ranges:
        # MSP sits between nudges and clothing in capture.
        if not inserted_pre and a >= 212:
            out.append((205, 206))
            inserted_pre = True
        out.append((a, b))
        if not inserted_post and b >= 213:
            out.append((257, 262))
            inserted_post = True
    if not inserted_pre:
        out.append((205, 206))
    if not inserted_post:
        out.append((257, 262))
    return out


def build(stream: list, ranges: list) -> list:
    out: list = []
    seen: set[int] = set()
    for a, b in ranges:
        for i in range(a, b + 1):
            if i >= len(stream):
                continue
            resent = a == 9 and b == 9 and i == 9 and i in seen
            if i in seen and not resent:
                continue
            bunch = dict(stream[i])
            bunch["_src_idx"] = i
            if resent:
                bunch["_resent"] = 1
            out.append(bunch)
            seen.add(i)
    return out


def write_bootstrap(mode=None):
    """Regenerate ownership_bootstrap.json. Safe to call from server.py (ignores sys.argv)."""
    mode = (mode or os.environ.get("WW3_BOOTSTRAP") or "ownership").strip().lower()
    if mode in ("capture", "capture_order", "capture-order", "linear"):
        ranges = RANGES_CAPTURE_ORDER
        mode_name = "capture_order"
    else:
        ranges = RANGES_OWNERSHIP
        mode_name = "ownership"

    ranges = _with_inv_attach(list(ranges))
    inv = os.environ.get("WW3_INV_ATTACH", "0") == "1"
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    boot = build(stream, ranges)
    world_fill = os.environ.get("WW3_WORLD_FILL", "0") == "1"
    if world_fill:
        owned = {int(b["_src_idx"]) for b in boot}
        # Append in capture order, after the curated local-player + GameState slice,
        # so nothing the possession path depends on is reordered.
        for i in _world_fill_indices(stream):
            if i in owned:
                continue
            bunch = dict(stream[i])
            bunch["_src_idx"] = i
            bunch["_world_fill"] = 1
            boot.append(bunch)
    from pawn_export_prefix import maybe_insert_pawn_export_prefix
    boot = maybe_insert_pawn_export_prefix(boot)
    OUT.write_text(json.dumps(boot), encoding="utf-8")
    bits = sum(b["bits"] for b in boot)
    chs = sorted({b["chIndex"] for b in boot if b.get("bOpen")})
    print(f"[OK] wrote {OUT.name}: mode={mode_name} inv_attach={int(inv)} "
          f"world_fill={int(world_fill)} {len(boot)} bunches, {bits} bits, "
          f"open_chs={chs}")
    for b in boot:
        if b.get("_world_fill"):
            continue  # 218 world bunches would bury the curated slice in the log
        flags = []
        if b.get("bOpen"):
            flags.append("OPEN")
        if b.get("bHasPackageMapExports"):
            flags.append("EXP")
        if b.get("_resent"):
            flags.append("RESEND")
        print(f"  src={b['_src_idx']:3} ch={b['chIndex']:3} bits={b['bits']:5} {' '.join(flags)}")
    return boot


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        default=os.environ.get("WW3_BOOTSTRAP", "ownership"),
        help="ownership | capture_order",
    )
    args = ap.parse_args(argv)
    write_bootstrap(args.mode)


if __name__ == "__main__":
    main()
