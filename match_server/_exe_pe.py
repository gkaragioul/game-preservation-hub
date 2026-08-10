#!/usr/bin/env python3
"""Minimal PE reader + rip-relative `lea` cross-reference scanner for the
shipping client.

The client is a stripped UE4.21 shipping build, so the only handholds are the
format strings it still carries.  This module turns "a string lives at file
offset N" into "these code addresses load it", which is what static analysis of
`AWW3PlayerState`'s synchronization predicate needs.

Used by `_ps_sync_predicate.py`.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

EXE = Path(r"E:\WW3_Playable_Backup\World War 3\WW3\Binaries\Win64\WW3-Win64-Shipping.exe")


@dataclass(frozen=True)
class Section:
    name: str
    va: int          # virtual address (absolute, image base included)
    vsize: int
    raw: int         # file offset
    rsize: int
    characteristics: int

    @property
    def executable(self) -> bool:
        return bool(self.characteristics & 0x20000000)


class PE:
    def __init__(self, path: Path = EXE):
        self.path = path
        self.data = path.read_bytes()
        d = self.data
        e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
        assert d[e_lfanew:e_lfanew + 4] == b"PE\0\0", "not a PE"
        coff = e_lfanew + 4
        n_sections, = struct.unpack_from("<H", d, coff + 2)
        opt_size, = struct.unpack_from("<H", d, coff + 16)
        opt = coff + 20
        magic, = struct.unpack_from("<H", d, opt)
        assert magic == 0x20B, f"expected PE32+, got {magic:#x}"
        self.image_base, = struct.unpack_from("<Q", d, opt + 24)
        sec_off = opt + opt_size
        self.sections: list[Section] = []
        for i in range(n_sections):
            o = sec_off + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, va, rsize, raw = struct.unpack_from("<IIII", d, o + 8)
            chars, = struct.unpack_from("<I", d, o + 36)
            self.sections.append(
                Section(name, self.image_base + va, vsize, raw, rsize, chars))

    # --- address conversions -------------------------------------------------
    def off_to_va(self, off: int) -> int | None:
        for s in self.sections:
            if s.raw <= off < s.raw + s.rsize:
                return s.va + (off - s.raw)
        return None

    def va_to_off(self, va: int) -> int | None:
        for s in self.sections:
            if s.va <= va < s.va + s.vsize:
                delta = va - s.va
                if delta < s.rsize:
                    return s.raw + delta
        return None

    def section_of_va(self, va: int) -> Section | None:
        for s in self.sections:
            if s.va <= va < s.va + s.vsize:
                return s
        return None

    def read_va(self, va: int, n: int) -> bytes:
        off = self.va_to_off(va)
        if off is None:
            return b""
        return self.data[off:off + n]

    def cstring_at_va(self, va: int, limit: int = 512) -> str | None:
        raw = self.read_va(va, limit)
        if not raw:
            return None
        end = raw.find(b"\0")
        if end < 0:
            return None
        try:
            return raw[:end].decode("utf-8")
        except UnicodeDecodeError:
            return None

    def wstring_at_va(self, va: int, limit: int = 1024) -> str | None:
        raw = self.read_va(va, limit)
        if not raw:
            return None
        out = []
        for i in range(0, len(raw) - 1, 2):
            ch = raw[i] | (raw[i + 1] << 8)
            if ch == 0:
                return "".join(out)
            if ch < 0x20 and ch not in (9, 10, 13):
                return None
            out.append(chr(ch))
        return None

    # --- xref scanning -------------------------------------------------------
    def lea_xrefs(self, targets: set[int]) -> dict[int, list[int]]:
        """Map target VA -> list of instruction VAs doing `lea r64, [rip+disp]`.

        Only 64-bit `lea` (REX.W) is considered; that is how UE4 shipping code
        materialises string literals for its logging macros.
        """
        hits: dict[int, list[int]] = {t: [] for t in targets}
        for s in self.sections:
            if not s.executable:
                continue
            blob = self.data[s.raw:s.raw + s.rsize]
            base = s.va
            i = 0
            n = len(blob)
            while i < n - 7:
                b = blob[i]
                if 0x48 <= b <= 0x4F and blob[i + 1] == 0x8D and (blob[i + 2] & 0xC7) == 0x05:
                    disp = struct.unpack_from("<i", blob, i + 3)[0]
                    tgt = base + i + 7 + disp
                    if tgt in hits:
                        hits[tgt].append(base + i)
                    i += 7
                    continue
                i += 1
        return hits

    def imm_xrefs(self, targets: set[int]) -> dict[int, list[int]]:
        """Map target VA -> instruction VAs embedding it as a `mov r64, imm64`."""
        hits: dict[int, list[int]] = {t: [] for t in targets}
        wanted = {struct.pack("<Q", t): t for t in targets}
        for s in self.sections:
            if not s.executable:
                continue
            blob = self.data[s.raw:s.raw + s.rsize]
            for pat, tgt in wanted.items():
                start = 0
                while True:
                    k = blob.find(pat, start)
                    if k < 0:
                        break
                    hits[tgt].append(s.va + k)
                    start = k + 1
        return hits


def find_strings(pe: PE, needles: list[bytes]) -> dict[bytes, list[int]]:
    """Locate every occurrence of each needle, returning VAs."""
    out: dict[bytes, list[int]] = {}
    for needle in needles:
        vas = []
        start = 0
        while True:
            k = pe.data.find(needle, start)
            if k < 0:
                break
            va = pe.off_to_va(k)
            if va is not None:
                vas.append(va)
            start = k + 1
        out[needle] = vas
    return out


if __name__ == "__main__":
    pe = PE()
    print(f"{pe.path}\nimage_base={pe.image_base:#x}")
    for s in pe.sections:
        print(f"  {s.name:<8} va={s.va:#014x} vsize={s.vsize:#x} "
              f"raw={s.raw:#x} rsize={s.rsize:#x} exec={s.executable}")
