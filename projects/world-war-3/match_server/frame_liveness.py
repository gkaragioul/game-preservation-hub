#!/usr/bin/env python3
"""Decide whether a sequence of captured frames is a *live* surface or a stale one.

Checkpoint 18 rejected screenshots as evidence because two captures minutes apart
were byte-identical.  That is the right call for a single pair of images, but it
generalises badly: "the bytes changed" is not the same as "the game is drawing",
and "the bytes did not change" is not the same as "the capture is broken".

So the verdict is a rule, applied to N consecutive frames of the same region:

  live  <=>  some consecutive pair differs in at least `min_changed_frac` of its
             pixels

The fraction (not a digest) is what matters: a digest flips on one byte of JPEG-ish
noise or one cursor pixel, which is exactly the false positive that would let a
frozen game masquerade as a running one.  Both quantities are reported so the
caller can show its work.

Pure and dependency-light on purpose -- only numpy -- so it is unit-testable
without a Windows desktop.  The win32 capture that feeds it lives in
`_live_frame.py`.
"""
from __future__ import annotations

import hashlib

import numpy as np

# A UE4 game that is running redraws essentially the whole frame; even a static
# menu animates a cursor, a spinner or an FPS counter.  0.1% of pixels is far
# above capture noise and far below anything a live frame produces.
DEFAULT_MIN_CHANGED_FRAC = 0.001


def _as_array(frame) -> np.ndarray:
    arr = np.asarray(frame)
    if arr.ndim not in (2, 3):
        raise ValueError(f"frame must be HxW or HxWxC, got shape {arr.shape}")
    return arr


def frame_digest(frame) -> str:
    """SHA-256 over the frame's raw bytes -- content addressing, not a verdict."""
    arr = np.ascontiguousarray(_as_array(frame))
    return hashlib.sha256(arr.tobytes()).hexdigest()


def frame_delta(a, b) -> dict:
    """Per-pixel difference between two frames of identical shape."""
    aa, bb = _as_array(a), _as_array(b)
    if aa.shape != bb.shape:
        raise ValueError(f"shape mismatch: {aa.shape} vs {bb.shape}")
    diff = np.abs(aa.astype(np.int16) - bb.astype(np.int16))
    # A pixel counts as changed if any of its channels moved.
    per_pixel = diff.max(axis=2) if diff.ndim == 3 else diff
    changed = int(np.count_nonzero(per_pixel))
    total = int(per_pixel.size)
    return {
        "changed_pixels": changed,
        "total_pixels": total,
        "changed_frac": (changed / total) if total else 0.0,
        "max_abs": int(diff.max()) if diff.size else 0,
        "mean_abs": float(diff.mean()) if diff.size else 0.0,
    }


def liveness_verdict(frames, min_changed_frac: float = DEFAULT_MIN_CHANGED_FRAC) -> dict:
    """`live` iff some consecutive pair of frames moved by more than the threshold."""
    frames = list(frames)
    digests = [frame_digest(f) for f in frames]
    pairs = []
    for i in range(len(frames) - 1):
        d = frame_delta(frames[i], frames[i + 1])
        d["index"] = i
        d["moved"] = d["changed_frac"] >= min_changed_frac
        pairs.append(d)
    return {
        "frames": len(frames),
        "digests": digests,
        "distinct_digests": len(set(digests)),
        "pairs": pairs,
        "max_changed_frac": max((p["changed_frac"] for p in pairs), default=0.0),
        "min_changed_frac": min_changed_frac,
        "live": any(p["moved"] for p in pairs),
    }
