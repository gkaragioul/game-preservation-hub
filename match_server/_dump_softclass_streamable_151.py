#!/usr/bin/env python3
"""SoftClassPtr / StreamableManager pending dump for Mag AttachmentId 151 (+ related).

Fast chunked heap scan (1 MiB reads). Read-only. No rematch.

Usage:
  python match_server/_dump_softclass_streamable_151.py
  python match_server/_dump_softclass_streamable_151.py --pid 29480

Writes: match_server/live_log/_softclass_streamable_151_dump.txt
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "live_log" / "_softclass_streamable_151_dump.txt"

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
# PAGE_READONLY / READWRITE / WRITECOPY only (skip RX .text format-string pools
# for residency counts; still probe a short list of fail markers in RX below).
DATA_PROTECTS = (0x02, 0x04, 0x08)
RX_PROTECTS = (0x10, 0x20, 0x40, 0x80)

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CHUNK = 1 << 20  # 1 MiB
MAX_REGION = 64 << 20

TARGETS = {
    151: {
        "cls": "BP_WP_Magazine_108_01",
        "pkg": (
            "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Magazine/"
            "Magazine_108/BP_WP_Magazine_108_01"
        ),
        "role": "Mag SoftClass NewObject gate",
    },
    4606: {
        "cls": "BP_WP_Rail_086_01",
        "pkg": (
            "/Game/Blueprints/Weapons/Attachments/BodyParts/Rail/"
            "Rail_086/BP_WP_Rail_086_01"
        ),
        "role": "Rail SoftClass hang peer",
    },
    101: {
        "cls": "BP_WP_Muzzle_020_01",
        "pkg": (
            "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Muzzle/"
            "Muzzle_020/BP_WP_Muzzle_020_01"
        ),
        "role": "Muzzle SoftClass peer",
    },
    143: {
        "cls": "BP_WP_Magazine_116_01",
        "pkg": (
            "/Game/Blueprints/Weapons/Attachments/WeaponAttachments/Magazine/"
            "Magazine_116/BP_WP_Magazine_116_01"
        ),
        "role": "HK Mag SoftClass",
    },
}


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


def find_pid() -> int:
    r = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-Process WW3-Win64-Shipping -EA SilentlyContinue | Select -First 1).Id",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    s = (r.stdout or "").strip()
    if not s:
        raise SystemExit("WW3-Win64-Shipping not running")
    return int(s)


def u16(s: str) -> bytes:
    return s.encode("utf-16le")


def extract_u16(data: bytes, at: int, nlen: int, before: int = 60, after: int = 140) -> str:
    start = at - (at % 2)
    lim = max(0, at - before * 2)
    while start > lim + 2:
        if data[start - 2] == 0 and data[start - 1] == 0:
            break
        start -= 2
    end = at + nlen
    lim_e = min(len(data), at + nlen + after * 2)
    while end + 1 < lim_e and not (data[end] == 0 and data[end + 1] == 0):
        end += 2
    if (end - start) % 2:
        end -= 1
    try:
        return data[start:end].decode("utf-16le", "replace")
    except Exception:
        return ""


def extract_ascii(data: bytes, at: int, nlen: int, before: int = 50, after: int = 100) -> str:
    start = max(0, at - before)
    end = min(len(data), at + nlen + after)
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data[start:end])


def build_needles() -> list[tuple[str, str, bytes]]:
    """(label, enc, bytes) — short critical set."""
    out: list[tuple[str, str, bytes]] = []

    def add(lab: str, text: str, both: bool = True) -> None:
        out.append((lab, "u16", u16(text)))
        if both and text.isascii():
            out.append((lab + ".a", "a", text.encode("ascii")))

    for mid, info in TARGETS.items():
        cls = info["cls"]
        pkg = info["pkg"]
        add(f"id{mid}.pkg", pkg)
        add(f"id{mid}.pkg_C", f"{pkg}.{cls}_C")
        add(f"id{mid}.bpg", f"BlueprintGeneratedClass'{pkg}.{cls}_C'")
        add(f"id{mid}.default", f"Default__{cls}_C")
        add(f"id{mid}.inst0", f"{cls}_C_0")
        add(f"id{mid}.cls_C", f"{cls}_C")
        add(f"id{mid}.uasset", f"{cls}.uasset")

    for m in (
        "OnAttachmentManagerSynchronized()",
        "OnAttachmentManagerSynchronized",
        "OnSynchronized: Weapons",
        "OnSynchronized: Inventory",
        "WeaponsAttachments: true",
        "WeaponsAttachments: false",
        "InventoryManager: true",
        "InventoryManager: false",
        "CharacterAttachments: true",
        "MapLevels: true",
        "FStreamableManager",
        "StreamableManager",
        "RequestAsyncLoad",
        "LoadPackageAsync",
        "PendingRequests",
        "IsAsyncLoading",
        "Couldn't find file for package",
        "Failed to load package",
        "Failed to find object",
        "Could not find object",
        "SoftObjectPtr was not valid",
        "Async loading of",
        "MainSkinLoadedClass",
        "LogWW3Wpn",
        "BP_ItemDatabase_01",
        "WW3AttachmentData",
        "CreateAttachment",
        "BlockCreateAttachments",
    ):
        add(f"g.{m}", m)

    # Dedup
    seen: set[bytes] = set()
    uniq: list[tuple[str, str, bytes]] = []
    for lab, enc, b in out:
        if b in seen or len(b) < 4:
            continue
        seen.add(b)
        uniq.append((lab, enc, b))
    return uniq


def scan(
    pid: int,
    needles: list[tuple[str, str, bytes]],
    protects: tuple[int, ...],
    max_samples: int,
    progress_every: int = 256,
) -> tuple[dict[str, int], dict[str, list[str]], int, int, list[str]]:
    counts: dict[str, int] = defaultdict(int)
    samples: dict[str, list[str]] = defaultdict(list)
    mag_prox: list[str] = []
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed err={ctypes.get_last_error()}")

    mbi = MBI()
    addr = 0
    read = ctypes.c_size_t()
    buf = ctypes.create_string_buffer(CHUNK)
    regions = 0
    scanned = 0
    # Overlap so needles spanning chunk boundaries aren't missed.
    OVERLAP = 512

    while kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        regions += 1
        if regions % progress_every == 0:
            sys.stdout.buffer.write(
                f"  …regions={regions} scanned_mb={scanned // (1 << 20)}\n".encode()
            )
            sys.stdout.flush()
        base, size = mbi.BaseAddress, mbi.RegionSize
        nxt = base + size
        prot = mbi.Protect & 0xFF
        if (
            mbi.State == MEM_COMMIT
            and prot in protects
            and not (mbi.Protect & PAGE_GUARD)
            and 0 < size <= MAX_REGION
        ):
            off = 0
            prev_tail = b""
            while off < size:
                chunk = min(CHUNK, size - off)
                if not kernel32.ReadProcessMemory(
                    h,
                    ctypes.c_uint64(base + off),
                    buf,
                    chunk,
                    ctypes.byref(read),
                ) or not read.value:
                    break
                body = buf.raw[: read.value]
                scanned += read.value
                data = prev_tail + body if prev_tail else body
                base_off_adjust = len(prev_tail)
                for lab, enc, nd in needles:
                    p = 0
                    hits_here = 0
                    while True:
                        i = data.find(nd, p)
                        if i < 0:
                            break
                        # Skip duplicate hits that live only in the overlap tail
                        # from previous chunk (already counted).
                        if off > 0 and i < base_off_adjust:
                            p = i + len(nd)
                            continue
                        counts[lab] += 1
                        hits_here += 1
                        if len(samples[lab]) < max_samples:
                            if enc == "u16":
                                ctx = extract_u16(data, i, len(nd))
                            else:
                                ctx = extract_ascii(data, i, len(nd))
                            ctx = ctx.replace("\r", " ").replace("\n", " | ")[:220]
                            if ctx and ctx not in samples[lab]:
                                samples[lab].append(ctx)
                        if lab.startswith("id151") and len(mag_prox) < 8:
                            win = data[max(0, i - 160) : i + len(nd) + 160].lower()
                            for fail in (
                                b"couldn't find",
                                b"failed to load",
                                b"could not find",
                                b"not valid",
                                b"pending",
                                b"requestasyncload",
                                b"streamable",
                            ):
                                if fail in win:
                                    mag_prox.append(extract_ascii(data, i, len(nd), 80, 120))
                                    break
                        p = i + len(nd)
                        if hits_here >= 80:
                            break
                prev_tail = body[-OVERLAP:] if len(body) >= OVERLAP else body
                off += chunk
        addr = nxt
        if addr <= base:
            break
    kernel32.CloseHandle(h)
    return counts, samples, regions, scanned, mag_prox


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--max-samples", type=int, default=3)
    args = ap.parse_args()
    pid = args.pid or find_pid()
    needles = build_needles()

    lines: list[str] = []

    def out(s: str = "") -> None:
        lines.append(s)
        sys.stdout.buffer.write((s + "\n").encode("utf-8", "replace"))
        sys.stdout.flush()

    out("# SoftClassPtr / StreamableManager dump — Mag AttachmentId 151")
    out(f"# time={dt.datetime.now().isoformat(timespec='seconds')} pid={pid}")
    out("# PS_REBIND=0 locked; dump-only (no rematch)")
    out(f"needles={len(needles)}")
    out()

    out("## Pass 1 — data pages (SoftClass residency / instances / checklist)")
    c1, s1, r1, b1, prox1 = scan(pid, needles, DATA_PROTECTS, args.max_samples)
    out(f"regions={r1} bytes_scanned={b1}")

    # Slim needle set for RX (format strings / fail markers only)
    rx_labs = {
        "Couldn't find file for package",
        "Failed to load package",
        "Failed to find object",
        "Could not find object",
        "SoftObjectPtr was not valid",
        "RequestAsyncLoad",
        "FStreamableManager",
        "StreamableManager",
        "LoadPackageAsync",
        "PendingRequests",
        "IsAsyncLoading",
        "LogWW3Wpn",
        "Async loading of",
    }
    rx_needles = [
        (lab, enc, b)
        for lab, enc, b in needles
        if any(lab == f"g.{x}" or lab == f"g.{x}.a" for x in rx_labs)
    ]
    out()
    out(f"## Pass 2 — RX pages (format-string / fail markers) needles={len(rx_needles)}")
    c2, s2, r2, b2, _ = scan(pid, rx_needles, RX_PROTECTS, args.max_samples, progress_every=512)
    out(f"regions={r2} bytes_scanned={b2}")

    # Merge: data counts are authoritative for residency; RX adds format hits.
    counts: dict[str, int] = defaultdict(int)
    samples: dict[str, list[str]] = defaultdict(list)
    for d in (c1, c2):
        for k, v in d.items():
            counts[k] += v
    for d in (s1, s2):
        for k, v in d.items():
            for s in v:
                if s not in samples[k] and len(samples[k]) < args.max_samples:
                    samples[k].append(s)
    mag_prox = prox1

    out()
    out("## Per-AttachmentId SoftClass residency (data pages + RX markers)")
    for mid, info in TARGETS.items():
        out(f"\n### id {mid} — {info['cls']} — {info['role']}")
        for k in (
            f"id{mid}.pkg",
            f"id{mid}.pkg_C",
            f"id{mid}.bpg",
            f"id{mid}.default",
            f"id{mid}.inst0",
            f"id{mid}.cls_C",
            f"id{mid}.uasset",
        ):
            cu = counts.get(k, 0)
            ca = counts.get(k + ".a", 0)
            out(f"  {k:24s} u16={cu:5d} ascii={ca:5d}")
        pkg = counts.get(f"id{mid}.pkg", 0) + counts.get(f"id{mid}.pkg.a", 0)
        bpg = counts.get(f"id{mid}.bpg", 0) + counts.get(f"id{mid}.bpg.a", 0)
        default = counts.get(f"id{mid}.default", 0) + counts.get(f"id{mid}.default.a", 0)
        inst = counts.get(f"id{mid}.inst0", 0) + counts.get(f"id{mid}.inst0.a", 0)
        cls_c = counts.get(f"id{mid}.cls_C", 0) + counts.get(f"id{mid}.cls_C.a", 0)
        class_yes = default > 0 or bpg > 0 or cls_c > 0
        out(
            f"  VERDICT: SoftObjectPath={'YES' if pkg else 'NO'}  "
            f"class~={'YES' if class_yes else 'NO/WEAK'} "
            f"(CDO={default} BPG={bpg} cls_C={cls_c})  "
            f"NewObject*_C_0={'YES' if inst else 'NO'} (hits={inst})"
        )

    out("\n## Sync / checklist")
    for key in (
        "OnAttachmentManagerSynchronized()",
        "OnAttachmentManagerSynchronized",
        "OnSynchronized: Weapons",
        "OnSynchronized: Inventory",
        "WeaponsAttachments: true",
        "WeaponsAttachments: false",
        "InventoryManager: true",
        "InventoryManager: false",
        "CharacterAttachments: true",
        "MapLevels: true",
    ):
        cu = counts.get(f"g.{key}", 0)
        ca = counts.get(f"g.{key}.a", 0)
        out(f"  {key:42s} u16={cu:5d} ascii={ca:5d}")
        for s in (samples.get(f"g.{key}", []) + samples.get(f"g.{key}.a", []))[:1]:
            out(f"      sample: {s[:200]}")

    out("\n## StreamableManager / SoftClassPtr / fail markers")
    for key in (
        "FStreamableManager",
        "StreamableManager",
        "RequestAsyncLoad",
        "LoadPackageAsync",
        "PendingRequests",
        "IsAsyncLoading",
        "Couldn't find file for package",
        "Failed to load package",
        "Failed to find object",
        "Could not find object",
        "SoftObjectPtr was not valid",
        "Async loading of",
        "MainSkinLoadedClass",
        "LogWW3Wpn",
        "BP_ItemDatabase_01",
        "WW3AttachmentData",
        "CreateAttachment",
        "BlockCreateAttachments",
    ):
        cu = counts.get(f"g.{key}", 0)
        ca = counts.get(f"g.{key}.a", 0)
        out(f"  {key:40s} u16={cu:5d} ascii={ca:5d}")
        for s in (samples.get(f"g.{key}", []) + samples.get(f"g.{key}.a", []))[:1]:
            out(f"      sample: {s[:200]}")

    out("\n## Mag SoftObjectPath samples")
    for k in ("id151.pkg", "id151.bpg", "id151.default", "id151.inst0", "id151.cls_C"):
        out(f"  -- {k} --")
        ss = samples.get(k, []) or samples.get(k + ".a", [])
        if not ss:
            out("    (none)")
        for s in ss[:2]:
            out(f"    {s[:220]}")

    out("\n## Mag-near fail/pending proximity")
    if not mag_prox:
        out("  (none)")
    else:
        for s in mag_prox:
            out(f"  {s[:220]}")

    # Interpretation
    mag_inst = counts.get("id151.inst0", 0) + counts.get("id151.inst0.a", 0)
    mag_def = counts.get("id151.default", 0) + counts.get("id151.default.a", 0)
    mag_pkg = counts.get("id151.pkg", 0) + counts.get("id151.pkg.a", 0)
    mag_bpg = counts.get("id151.bpg", 0) + counts.get("id151.bpg.a", 0)
    sync = (
        counts.get("g.OnAttachmentManagerSynchronized()", 0)
        + counts.get("g.OnAttachmentManagerSynchronized", 0)
        + counts.get("g.OnAttachmentManagerSynchronized().a", 0)
        + counts.get("g.OnAttachmentManagerSynchronized.a", 0)
    )
    wam_t = counts.get("g.WeaponsAttachments: true", 0) + counts.get(
        "g.WeaponsAttachments: true.a", 0
    )
    wam_f = counts.get("g.WeaponsAttachments: false", 0) + counts.get(
        "g.WeaponsAttachments: false.a", 0
    )
    im_t = counts.get("g.InventoryManager: true", 0) + counts.get(
        "g.InventoryManager: true.a", 0
    )
    im_f = counts.get("g.InventoryManager: false", 0) + counts.get(
        "g.InventoryManager: false.a", 0
    )
    fail_pkg = sum(
        counts.get(f"g.{k}", 0) + counts.get(f"g.{k}.a", 0)
        for k in (
            "Couldn't find file for package",
            "Failed to load package",
            "Failed to find object",
            "Could not find object",
            "SoftObjectPtr was not valid",
        )
    )
    req = counts.get("g.RequestAsyncLoad", 0) + counts.get("g.RequestAsyncLoad.a", 0)
    pending = counts.get("g.PendingRequests", 0) + counts.get("g.PendingRequests.a", 0)

    out("\n## Interpretation")
    out(f"  Mag SoftObjectPath resident: {'YES' if mag_pkg else 'NO'} ({mag_pkg})")
    out(f"  Mag BPG path: {'YES' if mag_bpg else 'NO'} ({mag_bpg})")
    out(f"  Mag Default__CDO: {'YES' if mag_def else 'NO'} ({mag_def})")
    out(f"  Mag*_C_0 NewObject: {'YES' if mag_inst else 'NO'} ({mag_inst})")
    out(f"  Synchronized heap hits~: {sync}")
    out(f"  WAM true/false: {wam_t}/{wam_f}  IM true/false: {im_t}/{im_f}")
    out(f"  RequestAsyncLoad hits: {req}  PendingRequests hits: {pending}")
    out(f"  Fail-load marker hits: {fail_pkg}  Mag-prox fail: {len(mag_prox)}")

    if mag_pkg and not mag_inst:
        out("  ROOT: SoftClass PATH present; Mag*_C_0 ABSENT.")
        out("        Not wrong SoftObjectPath / not missing cooked Mag.")
        if mag_def or mag_bpg:
            out(
                "        Class loadable (CDO/BPG). Gap is AttachmentManager "
                "CreateAttachment/NewObject after SoftClass resolve — not "
                "StreamableManager pending/fail."
            )
        else:
            out(
                "        Weak class signal (no CDO/BPG). SoftClassPtr may not "
                "have resolved to UClass despite path string residency."
            )
        if fail_pkg == 0 and not mag_prox:
            out(
                "        No failed-load / Mag-prox Streamable pending evidence. "
                "Async either never kicked for Mag OnRep SoftClass, or finished "
                "without NewObject."
            )
        out("  REMATCH: no — dump yields no concrete SoftClass wire fix.")
        out(
            "  BLOCKED-ON: Mag SoftClass CreateAttachment trigger "
            "(ItemDatabase ItemClass SoftClassPtr resolve→NewObject), "
            "or non-Mag IM+WAM arm (SPAWN CLOSE)."
        )
    elif mag_inst:
        out("  Mag NewObject PRESENT — SoftClass Sync mid-flight possible.")
        out("  REMATCH: only if POST_STUB mid-flight plan is ready.")
    else:
        out("  Mag SoftObjectPath ABSENT — SoftClassPtr empty/wrong/never looked up.")
        out("  REMATCH: only with a SoftClassPtr force-path fix.")

    out()
    out(f"wrote {OUT}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
