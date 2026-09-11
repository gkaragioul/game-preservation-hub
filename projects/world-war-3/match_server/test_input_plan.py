#!/usr/bin/env python3
"""RED-first tests for `input_plan` -- the pure part of the bounded input driver.

The hazard this guards against is a *stuck key*.  Synthesised input goes to a
live game client that this project must not wedge; a plan that emits a keydown
without its matching keyup leaves W held forever and makes every later
measurement meaningless (and the pawn unrecoverable without a restart).

So the plan is built as data, proven balanced, and only then executed.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from input_plan import (  # noqa: E402
    MAX_HOLD_S,
    SCANCODES,
    click_events,
    key_events,
    plan_is_balanced,
    unbalanced_keys,
)


class TestScancodes(unittest.TestCase):
    def test_keys_the_deploy_flow_needs_are_present(self):
        for k in ("w", "a", "s", "d", "m", "tab", "esc", "space", "enter"):
            self.assertIn(k, SCANCODES, f"missing scancode for {k!r}")

    def test_scancodes_are_bytes(self):
        for k, sc in SCANCODES.items():
            self.assertTrue(0 < sc <= 0xFF, f"{k} -> {sc:#x}")


class TestKeyEvents(unittest.TestCase):
    def test_a_key_press_is_down_hold_up(self):
        ev = key_events("w", 0.5)
        self.assertEqual([e["type"] for e in ev], ["key", "sleep", "key"])
        self.assertTrue(ev[0]["down"])
        self.assertFalse(ev[2]["down"])
        self.assertEqual(ev[0]["scan"], ev[2]["scan"])
        self.assertEqual(ev[0]["scan"], SCANCODES["w"])
        self.assertAlmostEqual(ev[1]["s"], 0.5)

    def test_case_is_ignored(self):
        self.assertEqual(key_events("W", 0.1)[0]["scan"], SCANCODES["w"])

    def test_unknown_key_is_rejected(self):
        with self.assertRaises(KeyError):
            key_events("f13", 0.1)

    def test_hold_is_clamped_so_nothing_can_be_held_forever(self):
        ev = key_events("w", 999.0)
        self.assertEqual(ev[1]["s"], MAX_HOLD_S)

    def test_negative_hold_is_rejected(self):
        with self.assertRaises(ValueError):
            key_events("w", -1.0)

    def test_plan_is_balanced(self):
        self.assertTrue(plan_is_balanced(key_events("w", 0.2)))
        self.assertEqual(unbalanced_keys(key_events("w", 0.2)), [])


class TestClickEvents(unittest.TestCase):
    def test_click_is_move_down_hold_up(self):
        ev = click_events(100, 200, hold_s=0.05)
        self.assertEqual([e["type"] for e in ev],
                         ["mousemove", "mouse", "sleep", "mouse"])
        self.assertEqual((ev[0]["x"], ev[0]["y"]), (100, 200))
        self.assertTrue(ev[1]["down"])
        self.assertFalse(ev[3]["down"])
        self.assertEqual(ev[1]["button"], "left")

    def test_right_button(self):
        self.assertEqual(click_events(1, 2, button="right")[1]["button"], "right")

    def test_unknown_button_is_rejected(self):
        with self.assertRaises(ValueError):
            click_events(1, 2, button="middle-ish")

    def test_click_plan_is_balanced(self):
        self.assertTrue(plan_is_balanced(click_events(5, 5)))


class TestBalanceDetection(unittest.TestCase):
    def test_a_missing_keyup_is_caught(self):
        bad = [{"type": "key", "scan": SCANCODES["w"], "down": True, "key": "w"}]
        self.assertFalse(plan_is_balanced(bad))
        self.assertEqual(unbalanced_keys(bad), ["w"])

    def test_a_missing_mouseup_is_caught(self):
        bad = [{"type": "mouse", "button": "left", "down": True}]
        self.assertFalse(plan_is_balanced(bad))
        self.assertEqual(unbalanced_keys(bad), ["mouse:left"])

    def test_double_down_without_up_is_caught(self):
        bad = key_events("w", 0.1)[:1] + key_events("a", 0.1)[:1]
        self.assertFalse(plan_is_balanced(bad))
        self.assertEqual(sorted(unbalanced_keys(bad)), ["a", "w"])

    def test_a_full_plan_of_several_actions_is_balanced(self):
        plan = key_events("m", 0.05) + click_events(3, 4) + key_events("w", 0.3)
        self.assertTrue(plan_is_balanced(plan))


if __name__ == "__main__":
    unittest.main(verbosity=2)
