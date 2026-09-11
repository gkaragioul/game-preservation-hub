#!/usr/bin/env python3
"""List content blocks around WAM + keep-dynamic GUIDs in weapon opens."""
from __future__ import annotations

import json
from pathlib import Path

from actor_channel import read_new_actor
from cam_im_resend import (
    WAM_KEEP_REPLICATED,
    WAM_OPEN_FINAL_SRCS,
    _find_wam_block_header,
    _walk_content_blocks,
)
from netguid import GuidReader, PackageMap

HERE = Path(__file__).resolve().parent
STREAM = HERE / "real_replay_stream.json"

# Full open = INIT + FINAL for each channel.
OPEN_SRCS = {
    8314: (14, 15),
    7956: (16, 17),
    9418: (257, 258),
    9426: (259, 260),
}


def main() -> None:
    stream = json.loads(STREAM.read_text(encoding="utf-8"))
    for wam, srcs in OPEN_SRCS.items():
        keep = WAM_KEEP_REPLICATED[wam]
        bits: list[int] = []
        for i in srcs:
            bits.extend(int(c) for c in stream[i]["payload"])
        pm = PackageMap()
        pos = pm.read_export_bunch(bits)["reader"].pos
        gr = GuidReader(bits, pos)
        note = "ok"
        try:
            read_new_actor(gr, pm)
            start = gr.pos
        except Exception as exc:  # noqa: BLE001
            start = pos
            note = f"NA fail: {exc}"
        try:
            blocks = _walk_content_blocks(bits, start)
        except Exception as exc:  # noqa: BLE001
            hdr = _find_wam_block_header(bits, wam)
            print(f"wam={wam} keep={keep} walk fail ({exc}) hdr={hdr}")
            # Brute-scan for packed keep/wam near header
            if hdr:
                window = bits[max(0, hdr["hdr"] - 80) : hdr["payload_end"] + 40]
                print(f"  window_bits={len(window)} around hdr")
            continue
        print(f"=== wam={wam} keep={keep} srcs={srcs} start={start} {note} n={len(blocks)}")
        for b in blocks:
            mark = ""
            if b["subNetGUID"] == wam:
                mark = " <<WAM"
            if b["subNetGUID"] == keep:
                mark = " <<KEEP"
            print(
                f"  sub={b['subNetGUID']} stably={b['stablyNamed']} "
                f"cls={b['classNetGUID']} bits={b['payloadBits']}{mark}"
            )
        # Confirm FINAL-only strip targets still map
        final_src = {v: k for k, v in WAM_OPEN_FINAL_SRCS.items()}[wam]
        final = [int(c) for c in stream[final_src]["payload"]]
        hdr = _find_wam_block_header(final, wam)
        print(f"  FINAL src={final_src} hdr_nbits={hdr and hdr['nbits']}")


if __name__ == "__main__":
    main()
