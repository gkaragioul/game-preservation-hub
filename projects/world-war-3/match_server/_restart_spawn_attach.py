#!/usr/bin/env python3
"""Restart match server with WAM_SPAWN_ATTACH bisect knobs.

Usage:
  python _restart_spawn_attach.py                  # full spawn (CLOSE repro)
  python _restart_spawn_attach.py off              # SPAWN=0, CAM baseline
  python _restart_spawn_attach.py export87         # ch87 export-only, no keep
  python _restart_spawn_attach.py spawn87_1        # ch87 ×1 att, keep off
  python _restart_spawn_attach.py spawn87_1_keep   # ch87 ×1 att + strip keep
  python _restart_spawn_attach.py empty87          # ch87 ×1 empty payload, keep off
  python _restart_spawn_attach.py hat87            # ch87 ×1 hat-copy payload, keep off
  python _restart_spawn_attach.py pawn87_1         # Mag on pawn ch3, WAM strip ch87
  python _restart_spawn_attach.py pawn87_1_keep    # pawn host + strip keep
  python _restart_spawn_attach.py pawn_all         # all BP_WP_* on pawn ch3 + keep
  python _restart_spawn_attach.py keep_clothing    # WAM keep 9404/9406 (CAM pattern)
  python _restart_spawn_attach.py softclass_mag    # Mag AttachmentIds splice into capture open + export
  python _restart_spawn_attach.py softclass_mag_muzzle  # Mag+Muzzle splice (no Rail 4606)
  python _restart_spawn_attach.py softclass_mag_barrel  # Mag+Barrel splice (no Rail 4606)
  python _restart_spawn_attach.py softclass_mag_muzzle_barrel  # Mag+Muzzle+Barrel (no 4606)
  python _restart_spawn_attach.py softclass_mag_muzzle_4606  # Mag+Muzzle+Rail 4606
  python _restart_spawn_attach.py softclass_stub4606  # capture shape; 4606→151; OPEN_ONLY
  python _restart_spawn_attach.py softclass_full_openonly  # exact capture SoftClass; OPEN_ONLY
  python _restart_spawn_attach.py softclass_full_cam0  # full SoftClass; CAM_STRIP=0 Sync probe
  python _restart_spawn_attach.py softclass_full_keepskins  # BatchID=2 keep skins/MainId
  python _restart_spawn_attach.py softclass_hist074114  # inv-only strip; SoftClass on ch4/5
  python _restart_spawn_attach.py softclass_hist074114_warm  # hist + early Mag/Rail SoftClass warm
  python _restart_spawn_attach.py softclass_hist074114_warm_poststub4606  # hist+warm; POST_STUB after Mag
  python _restart_spawn_attach.py softclass_hist074114_warm_stub4606  # hist+warm+open 4606→151 (kills Mag)
  python _restart_spawn_attach.py softclass_native_open  # WAM_STRIP=0 native SoftClass opens
  python _restart_spawn_attach.py softclass_norail  # capture catalogs minus Rail 4606
  python _restart_spawn_attach.py softclass_min    # Mag+Rail SoftClass + package-map export
  python _restart_spawn_attach.py softclass_noexport  # SoftClass ids, no export
  python _restart_spawn_attach.py KEY=VAL ...      # raw overrides
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from _read_proc_env import read_env

HERE = Path(__file__).resolve().parent
LOG = HERE / "live_log"

# Ack-OK possession baseline (rematch 131115 / pid 9412). Fresh-client CLOSE
# before Ack was traced to _restart_spawn_attach dropping these when read_env
# lacked them → defaults PS_REBIND=1 + MAX_SPRAYS=4 → "PS rebind" + dual spray
# → ch0 hangup. Pin them so every preset rematch keeps Ack-OK shape.
BASE = {
    "WW3_BOOTSTRAP": "ownership",
    "WW3_PAWN_EXPORT_PREFIX": "1",
    "WW3_CLIENT_RESTART": "1",
    "WW3_CLIENT_RESTART_MUSTMAP": "0",
    "WW3_CLIENT_RESTART_SEND_RETRY": "0",
    "WW3_CLIENT_RESTART_MAX_SPRAYS": "1",
    "WW3_PC_SET_PAWN": "0",
    "WW3_PAWN_SYNTH_PROPS": "0",
    "WW3_PAWN_SYNTH_IN_OPEN": "0",
    "WW3_PS_SET_PLAYERCHAR": "0",
    "WW3_PS_REBIND": "0",
    "WW3_PAWN_NO_SCALE": "0",
    "WW3_ACK_AUDIT": "1",
    "WW3_AMBIENT_LIMIT": "0",
    "WW3_AMBIENT_CHANNELS": "all",
    "WW3_STREAMING_PAUSE_MS": "15000",
    "WW3_WAIT_GAMEPLAY_DOM": "1",
    "WW3_WAM_SPAWN_ATTACH": "1",
    "WW3_WAM_KEEP_DYNAMIC": "0",
    "WW3_WAM_KEEP_CLOTHING": "0",
    "WW3_WAM_SOFTCLASS_CATALOG": "0",
    "WW3_WAM_SOFTCLASS_EXPORT": "1",
    "WW3_WAM_SOFTCLASS_WARM_EXPORT": "0",
    "WW3_WAM_SOFTCLASS_STUB_4606": "0",
    "WW3_WAM_SOFTCLASS_POST_STUB_4606": "0",
    "WW3_WAM_SOFTCLASS_POST_STUB_DELAY_MS": "2500",
    "WW3_WAM_SOFTCLASS_POST_STUB_WAIT_FILE": "",
    "WW3_WAM_SOFTCLASS_POST_STUB_MODE": "stub",
    "WW3_WAM_SOFTCLASS_MODE": "mag",
    "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
    "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
    "WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE": "0",
    "WW3_WAM_STRIP_CATALOG": "1",
    "WW3_WAM_STRIP_CHANNELS": "all",
    "WW3_CAM_STRIP_CATALOG": "1",
    "WW3_WPN_ATTACH": "1",
    "WW3_INV_ATTACH": "1",
    "WW3_CAM_IM_AFTER_ACK": "1",
    "WW3_CLOTHING_RESEND": "1",
    "WW3_WAM_SPAWN_CHANNELS": "all",
    "WW3_WAM_SPAWN_HOST": "weapon",
    "WW3_WAM_SPAWN_ATT_LIMIT": "",
    "WW3_WAM_SPAWN_STRIP_KEEP": "1",
    "WW3_WAM_SPAWN_EXPORT": "1",
    "WW3_WAM_SPAWN_CONTENT": "1",
    "WW3_WAM_SPAWN_PAYLOAD": "min",
    "WW3_WAM_SPAWN_CHECKSUM": "",
    "WW3_WAM_SPAWN_USE_HAT_CLASS": "0",
}

PRESETS = {
    "off": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_SPAWN_HOST": "weapon",
    },
    "export87": {
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_CONTENT": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_SPAWN_EXPORT": "1",
    },
    "spawn87_1": {
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_SPAWN_CONTENT": "1",
        "WW3_WAM_SPAWN_EXPORT": "1",
        "WW3_WAM_SPAWN_PAYLOAD": "min",
    },
    "spawn87_1_keep": {
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_STRIP_KEEP": "1",
        "WW3_WAM_SPAWN_CONTENT": "1",
        "WW3_WAM_SPAWN_EXPORT": "1",
        "WW3_WAM_SPAWN_PAYLOAD": "min",
    },
    "empty87": {
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_SPAWN_PAYLOAD": "empty",
    },
    "hat87": {
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_SPAWN_PAYLOAD": "hat",
    },
    "hatclass87": {
        # Control: spawn clothing hat class (already mapped by CLOTHING_RESEND) on
        # weapon ch87 — isolates BP_WP_* path/load vs any stably=0 on weapon ch.
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_SPAWN_EXPORT": "0",
        "WW3_WAM_SPAWN_CONTENT": "1",
        "WW3_WAM_SPAWN_PAYLOAD": "hat",
        "WW3_WAM_SPAWN_USE_HAT_CLASS": "1",
    },
    # Capture Mag/Rail never open on weapon ch (SoftClass-only). Host on pawn ch3
    # mirrors CAM hat/chest; WAM strip on weapon ch only refs dyn NetGUIDs.
    "pawn87_1": {
        "WW3_WAM_SPAWN_HOST": "pawn",
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_SPAWN_CONTENT": "1",
        "WW3_WAM_SPAWN_EXPORT": "1",
        "WW3_WAM_SPAWN_PAYLOAD": "min",
    },
    "pawn87_1_keep": {
        "WW3_WAM_SPAWN_HOST": "pawn",
        "WW3_WAM_SPAWN_CHANNELS": "87",
        "WW3_WAM_SPAWN_ATT_LIMIT": "1",
        "WW3_WAM_SPAWN_STRIP_KEEP": "1",
        "WW3_WAM_SPAWN_CONTENT": "1",
        "WW3_WAM_SPAWN_EXPORT": "1",
        "WW3_WAM_SPAWN_PAYLOAD": "min",
    },
    "pawn_all": {
        "WW3_WAM_SPAWN_HOST": "pawn",
        "WW3_WAM_SPAWN_CHANNELS": "all",
        "WW3_WAM_SPAWN_STRIP_KEEP": "1",
        "WW3_WAM_SPAWN_CONTENT": "1",
        "WW3_WAM_SPAWN_EXPORT": "1",
        "WW3_WAM_SPAWN_PAYLOAD": "min",
    },
    # SoftClass / ItemDatabase offline — no BP_WP_* stably=0 content.
    "keep_clothing": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "1",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
    },
    # Mag SoftClass only (151/143): splice Mag AttachmentIds into capture open
    # WAM (skins/MainId kept). Avoids Rail 4606; no BP_WP_* stably=0.
    "softclass_mag": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_MODE": "mag",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Mag + one non-Rail SoftClass id via capture-open splice (arm Synchronized bisect).
    "softclass_mag_muzzle": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_MODE": "mag_muzzle",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    "softclass_mag_barrel": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_MODE": "mag_barrel",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    "softclass_mag_muzzle_barrel": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_MODE": "mag_muzzle_barrel",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    "softclass_mag_muzzle_4606": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "mag_muzzle_4606",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Capture order/count; SoftClass 4606→Mag 151. Open SoftClass only (no
    # post-ACK skins=[] overwrite). EXPORT=0 — no unproven package-map paths.
    "softclass_stub4606": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "stub4606",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "1",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # stub4606 open SoftClass, NO post-ACK WAM strip at all (WPN_ATTACH=0).
    # Isolates whether empty BatchID=2 post-ACK cancels Sync arm.
    "softclass_stub4606_nopost": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "stub4606",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "1",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WPN_ATTACH": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Exact capture SoftClass open (bit-identical) + OPEN_ONLY — Sync arm control
    # (expect mid-flight hang on 4606). EXPORT=0.
    "softclass_full_openonly": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "1",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Exact capture SoftClass open, no post-ACK WAM (WPN_ATTACH=0). Expect Sync
    # arm then hang on SoftClass 4606 — control vs stub4606_nopost.
    "softclass_full_nopost": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "1",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WPN_ATTACH": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # MODE=full open SoftClass + CAM_STRIP=0 (historical Sync-arm flag diff).
    # OPEN_ONLY / WPN_ATTACH=0 — leave capture SoftClass on open; no empty post.
    "softclass_full_cam0": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "1",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_CAM_STRIP_CATALOG": "0",
        "WW3_WPN_ATTACH": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # MODE=full open SoftClass + post-ACK BatchID=2 SoftClass with capture
    # skins/MainId kept (not empty strip shape). EXPORT=0.
    "softclass_full_keepskins": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "1",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WPN_ATTACH": "1",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Historical Sync-arm surface (rematch 074114): SoftClass stays on early
    # Glock opens (ch4/ch5); only INV_ATTACH ch86/87 open+post-ACK emptied.
    # Expect mid-flight Sync hang on SoftClass 4606. EXPORT=0. No BP_WP_* stably=0.
    "softclass_hist074114": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_WARM_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_STRIP_CATALOG": "1",
        "WW3_WAM_STRIP_CHANNELS": "inv",
        "WW3_CAM_STRIP_CATALOG": "1",
        "WW3_WPN_ATTACH": "1",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # hist074114 + early SoftClass package-map warm (Mag/Rail BP_WP_* on ch3
    # before SoftClass OnRep). Catalog off / native SoftClass opens. No stably=0.
    "softclass_hist074114_warm": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_WARM_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE": "1",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_STRIP_CATALOG": "1",
        "WW3_WAM_STRIP_CHANNELS": "inv",
        "WW3_CAM_STRIP_CATALOG": "1",
        "WW3_WPN_ATTACH": "1",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # hist074114 + Mag+Rail warm; SoftClass 4606 stays on open (Mag arm). After
    # ACK gate + delay (+ optional wait-file after Mag*_C_0), post SoftClass
    # 4606→151 reinforce on early WAMs so Synchronized can finish → WAM flip.
    "softclass_hist074114_warm_poststub4606": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_WARM_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_STUB_4606": "0",
        "WW3_WAM_SOFTCLASS_POST_STUB_4606": "1",
        "WW3_WAM_SOFTCLASS_POST_STUB_DELAY_MS": "2500",
        "WW3_WAM_SOFTCLASS_POST_STUB_WAIT_FILE": "_post_stub4606.go",
        "WW3_WAM_SOFTCLASS_POST_STUB_MODE": "stub",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_STRIP_CATALOG": "1",
        "WW3_WAM_STRIP_CHANNELS": "inv",
        "WW3_CAM_STRIP_CATALOG": "1",
        "WW3_WPN_ATTACH": "1",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # hist074114 + Mag+Rail warm + SoftClass 4606→151 on early native opens.
    # Open stub kills Mag NewObject — prefer poststub4606 after Mag*_C_0.
    "softclass_hist074114_warm_stub4606": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_WARM_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_STUB_4606": "1",
        "WW3_WAM_SOFTCLASS_POST_STUB_4606": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_STRIP_CATALOG": "1",
        "WW3_WAM_STRIP_CHANNELS": "inv",
        "WW3_CAM_STRIP_CATALOG": "1",
        "WW3_WPN_ATTACH": "1",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Historical Sync-arm surface: NO WAM strip rewrite — native capture SoftClass
    # on early Glock opens (incl. 4606). Expect mid-flight Sync + hang on 4606.
    # SoftClass catalog off (opens carry capture catalogs). EXPORT=0. CAM_STRIP on.
    "softclass_native_open": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_STRIP_CATALOG": "0",
        "WW3_CAM_STRIP_CATALOG": "1",
        "WW3_WPN_ATTACH": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Native WAM opens + CAM_STRIP=0 (both historical-ish flag diffs).
    "softclass_native_cam0": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_STRIP_CATALOG": "0",
        "WW3_CAM_STRIP_CATALOG": "0",
        "WW3_WPN_ATTACH": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    # Native opens + post-ACK full capture WAM resend (WPN_ATTACH, no strip).
    "softclass_native_wpn": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "0",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "full",
        "WW3_WAM_SOFTCLASS_OPEN_ONLY": "0",
        "WW3_WAM_SOFTCLASS_KEEP_SKINS": "0",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_STRIP_CATALOG": "0",
        "WW3_CAM_STRIP_CATALOG": "1",
        "WW3_WPN_ATTACH": "1",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    "softclass_norail": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_MODE": "norail",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    "softclass_min": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "1",
        "WW3_WAM_SOFTCLASS_MODE": "min",
        "WW3_WAM_KEEP_DYNAMIC": "0",
        "WW3_WAM_SPAWN_CHANNELS": "all",
    },
    "softclass_noexport": {
        "WW3_WAM_SPAWN_ATTACH": "0",
        "WW3_WAM_SPAWN_STRIP_KEEP": "0",
        "WW3_WAM_KEEP_CLOTHING": "0",
        "WW3_WAM_SOFTCLASS_CATALOG": "1",
        "WW3_WAM_SOFTCLASS_EXPORT": "0",
        "WW3_WAM_SOFTCLASS_MODE": "mag",
        "WW3_WAM_KEEP_DYNAMIC": "0",
    },
    "full": {},
}


def main() -> int:
    pid_path = LOG / "_match_pid.txt"
    old_pid = int(pid_path.read_text(encoding="utf-8").strip()) if pid_path.exists() else None
    if old_pid is None:
        raise SystemExit("no _match_pid.txt")
    env = read_env(old_pid)
    ww3 = {k: v for k, v in env.items() if k.startswith("WW3_")}
    force = dict(BASE)
    args = list(sys.argv[1:])
    if args and args[0] in PRESETS and "=" not in args[0]:
        force.update(PRESETS[args[0]])
        args = args[1:]
    for a in args:
        if "=" not in a:
            raise SystemExit(f"unknown arg {a!r}; presets={sorted(PRESETS)}")
        k, v = a.split("=", 1)
        force[k] = v
    ww3.update(force)
    print(f"old_pid={old_pid} forcing:")
    for k in sorted(force):
        print(f"  {k}={ww3.get(k)}")

    subprocess.run(["taskkill", "/PID", str(old_pid), "/F"], check=False)
    time.sleep(1.0)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    console = LOG / f"match_console_{stamp}.out.txt"
    new_env = os.environ.copy()
    for k in list(new_env):
        if k.startswith("WW3_"):
            del new_env[k]
    new_env.update(ww3)
    new_env["PYTHONUNBUFFERED"] = "1"
    out = open(console, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(HERE / "server.py"), "7871"],
        cwd=str(HERE),
        env=new_env,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    (LOG / "CURRENT_CONSOLE.txt").write_text(str(console), encoding="utf-8")
    time.sleep(1.5)
    alive = proc.poll() is None
    print(f"new_pid={proc.pid} alive={alive} console={console}")
    text = console.read_text(encoding="utf-8", errors="replace")
    print("--- console head ---")
    print("\n".join(text.splitlines()[:45]))
    return 0 if alive else 1


if __name__ == "__main__":
    raise SystemExit(main())
