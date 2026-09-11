#!/usr/bin/env python3
import json
import os

os.environ["WW3_WAM_STRIP_CATALOG"] = "1"
os.environ["WW3_WAM_SOFTCLASS_CATALOG"] = "1"
os.environ["WW3_WAM_SOFTCLASS_MODE"] = "full"

from cam_im_resend import (  # noqa: E402
    HERE,
    WAM_OPEN_FINAL_SRCS,
    _find_wam_block_header,
    rewrite_weapon_final_strip_wam,
)

stream = json.loads((HERE / "real_replay_stream.json").read_text(encoding="utf-8"))
for src, ng in WAM_OPEN_FINAL_SRCS.items():
    raw = [int(c) for c in stream[src]["payload"]]
    out = rewrite_weapon_final_strip_wam(raw, ng, batch_id=1)
    hdr_r = _find_wam_block_header(raw, ng)
    hdr_o = _find_wam_block_header(out, ng)
    pl_r = raw[hdr_r["payload_start"] : hdr_r["payload_end"]]
    pl_o = out[hdr_o["payload_start"] : hdr_o["payload_end"]]
    print(
        f"src={src} ng={ng} final {len(raw)}->{len(out)} "
        f"identical_final={raw == out}"
    )
    print(
        f"  payload {len(pl_r)}->{len(pl_o)} identical_payload={pl_r == pl_o}"
    )
    print(
        f"  nbits_pos raw={hdr_r['nbits_pos']} out={hdr_o['nbits_pos']} "
        f"payload_start raw={hdr_r['payload_start']} out={hdr_o['payload_start']}"
    )
    if raw != out:
        for i, (a, b) in enumerate(zip(raw, out)):
            if a != b:
                print(
                    f"  first_final_diff @{i} "
                    f"(nbits_pos={hdr_r['nbits_pos']}, "
                    f"payload=[{hdr_r['payload_start']}:{hdr_r['payload_end']}])"
                )
                break
        else:
            print("  len_diff only")
