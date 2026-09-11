#!/usr/bin/env python3
"""RED-first tests for `frame_liveness` -- the pure part of the live-frame oracle.

Checkpoint 18 recorded that two `auto_ui.py shot` captures minutes apart were
byte-identical down to the FPS counter, i.e. a stale surface rather than a live
frame, and concluded screenshots are unusable as evidence.  That conclusion is
only safe if "stale" is *decided by a rule* instead of by eyeballing, so the rule
lives here and is tested on synthetic frames where the answer is known.

The oracle must be conservative in both directions:

  * identical frames  -> NOT live (that is the stale-surface case)
  * one flipped pixel -> NOT live (sampling/compression noise must not pass)
  * a real frame delta -> live
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from frame_liveness import (  # noqa: E402
    DEFAULT_MIN_CHANGED_FRAC,
    frame_delta,
    frame_digest,
    liveness_verdict,
)


def _frame(seed: int, h: int = 64, w: int = 96) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


class TestFrameDigest(unittest.TestCase):
    def test_digest_is_stable_and_content_addressed(self):
        a = _frame(1)
        self.assertEqual(frame_digest(a), frame_digest(a.copy()))
        self.assertEqual(len(frame_digest(a)), 64)

    def test_digest_changes_with_a_single_byte(self):
        a = _frame(1)
        b = a.copy()
        b[0, 0, 0] = (int(b[0, 0, 0]) + 1) % 256
        self.assertNotEqual(frame_digest(a), frame_digest(b))


class TestFrameDelta(unittest.TestCase):
    def test_identical_frames_have_zero_delta(self):
        a = _frame(2)
        d = frame_delta(a, a.copy())
        self.assertEqual(d["changed_pixels"], 0)
        self.assertEqual(d["changed_frac"], 0.0)
        self.assertEqual(d["max_abs"], 0)

    def test_single_pixel_change_is_counted_but_tiny(self):
        a = _frame(3)
        b = a.copy()
        b[5, 7, :] = 255 - b[5, 7, :]
        d = frame_delta(a, b)
        self.assertEqual(d["changed_pixels"], 1)
        self.assertGreater(d["max_abs"], 0)
        self.assertLess(d["changed_frac"], DEFAULT_MIN_CHANGED_FRAC)

    def test_mismatched_shapes_are_rejected(self):
        with self.assertRaises(ValueError):
            frame_delta(_frame(4, 10, 10), _frame(4, 11, 10))


class TestLivenessVerdict(unittest.TestCase):
    def test_identical_frames_are_not_live(self):
        a = _frame(5)
        v = liveness_verdict([a, a.copy(), a.copy()])
        self.assertFalse(v["live"])
        self.assertEqual(v["distinct_digests"], 1)
        self.assertEqual(v["max_changed_frac"], 0.0)

    def test_one_pixel_of_noise_is_not_live(self):
        a = _frame(6)
        b = a.copy()
        b[1, 1, :] = 0
        v = liveness_verdict([a, b])
        self.assertEqual(v["distinct_digests"], 2, "digests must still differ")
        self.assertFalse(v["live"], "a single pixel must not count as a live frame")

    def test_a_real_frame_delta_is_live(self):
        a = _frame(7)
        b = _frame(8)
        v = liveness_verdict([a, b])
        self.assertTrue(v["live"])
        self.assertGreater(v["max_changed_frac"], DEFAULT_MIN_CHANGED_FRAC)

    def test_live_if_any_consecutive_pair_moves(self):
        a = _frame(9)
        v = liveness_verdict([a, a.copy(), _frame(10)])
        self.assertTrue(v["live"])
        self.assertEqual(len(v["pairs"]), 2)

    def test_fewer_than_two_frames_cannot_be_live(self):
        v = liveness_verdict([_frame(11)])
        self.assertFalse(v["live"])
        self.assertEqual(v["pairs"], [])

    def test_threshold_is_honoured(self):
        a = _frame(12, 100, 100)
        b = a.copy()
        b[:2, :, :] = 0  # 2% of pixels
        self.assertFalse(liveness_verdict([a, b], min_changed_frac=0.10)["live"])
        self.assertTrue(liveness_verdict([a, b], min_changed_frac=0.005)["live"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
