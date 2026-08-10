#!/usr/bin/env python3
"""Offline smoke test for the deploy-path `maybe_*` methods.

Why this exists: `maybe_replay_capture_points` shipped with a `NameError` in its
log line (a `first_open` left behind by a rewrite).  The exception was raised
before the print and swallowed somewhere up the call stack, so the method looked
like it simply "didn't fire" -- and it cost a full live match cycle (~5 minutes of
client restart, menu, load, deploy screen) to discover that the run had tested
nothing at all.

These methods are only ever exercised against a live client, so a typo in a
rarely-taken branch is invisible until it wastes a cycle.  This calls each of
them against a stub connection with a stub socket, so at minimum every line is
compiled and the happy path executes end to end.

It asserts behaviour that is cheap and stable to check:
  * the method runs without raising,
  * with its flag off it is a no-op,
  * with its flag on it queues/sends something,
  * capture-point selection sends at most ONE open per channel by default, and
    excludes the dangling NetGUID identity-export open.  That is a regression
    guard, not a style preference: sending it as a second bOpen on ch84 makes the
    client re-open the channel, which resets the actor and discards the property
    updates behind it.  Measured live on the capture point as
    EntireCapturePointTeamOwner 0 -> 255 and bIsEntireCapturePointActive 1 -> 0.
    `WW3_CAPTUREPOINT_IDENTITY_EXPORT=1` re-enables it for experiments.

Run:  python match_server/test_deploy_paths_smoke.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import server  # noqa: E402


class StubConn:
    """Just enough connection state for the deploy-path methods."""

    def __init__(self):
        self.pc_channel = 2
        self.ps_channel = 7
        self.replay_queue = []
        self.chan_seq = {}


class StubServer:
    """Captures outbound packets instead of touching a socket."""

    def __init__(self):
        self.sent = []

    def flush_acks(self, *_a, **_k):
        return None

    def send_packet(self, _s, _addr, _conn, bunch=None, bunches=None, **_k):
        self.sent.append(bunches if bunches is not None else [bunch])

    def next_chan_seq(self, conn, ch):
        conn.chan_seq[ch] = conn.chan_seq.get(ch, 0) + 1
        return conn.chan_seq[ch]

    def build_replay_bunch(self, _conn, spec):
        return dict(spec)

    # The capture-spec loader is pure (reads the stream file and validates every
    # bunch header plus a SHA-256), so use the real one -- that way the smoke test
    # also fails if a spec table drifts out of sync with real_replay_stream.json.
    def _load_validated_capture_specs(self, conn, specs, label):
        return server.MatchServer._load_validated_capture_specs(
            self, conn, specs, label)

    def _load_validated_transition_spec(self):
        return server.MatchServer._load_validated_transition_spec(self)


def bind(name):
    """Bind a MatchServer method onto the stub."""
    return getattr(server.MatchServer, name)


def check(cond, msg):
    if not cond:
        print(f"  FAIL: {msg}")
        return 1
    print(f"  ok: {msg}")
    return 0


def main() -> int:
    fails = 0

    print("[smoke] maybe_replay_capture_points")
    os.environ["WW3_CAPTUREPOINT_REPLAY"] = "0"
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_replay_capture_points")(srv, None, None, conn)
    fails += check(r is False and not conn.replay_queue, "flag off -> no-op")

    os.environ["WW3_CAPTUREPOINT_REPLAY"] = "1"
    os.environ["WW3_CAPTUREPOINT_LIMIT"] = "40"
    os.environ["WW3_CAPTUREPOINT_IDENTITY_EXPORT"] = "0"
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_replay_capture_points")(srv, None, None, conn)
    fails += check(r is True, "flag on -> ran without raising")
    fails += check(len(conn.replay_queue) > 0, "queued bunches")
    # Default must NOT include the dangling identity export: sending it as a
    # second bOpen on ch84 re-opens the channel and resets the actor, measured
    # live as owner 0->255 / active 1->0 on the capture point.
    opens = [b for b in conn.replay_queue if int(b.get("bOpen", 0)) == 1]
    fails += check(not any(b.get("_dangling_export") for b in opens),
                   "default excludes the identity-export second OPEN")
    fails += check(len({int(b["chIndex"]) for b in opens}) == len(opens),
                   "at most one OPEN per channel by default")

    os.environ["WW3_CAPTUREPOINT_IDENTITY_EXPORT"] = "1"
    srv, conn2 = StubServer(), StubConn()
    bind("maybe_replay_capture_points")(srv, None, None, conn2)
    fails += check(any(b.get("_dangling_export") for b in conn2.replay_queue),
                   "opt-in flag re-enables the identity export")
    os.environ["WW3_CAPTUREPOINT_IDENTITY_EXPORT"] = "0"
    # one-shot
    n = len(conn.replay_queue)
    bind("maybe_replay_capture_points")(srv, None, None, conn)
    fails += check(len(conn.replay_queue) == n, "second call is a no-op (one-shot)")

    print("[smoke] maybe_replay_capturepoint_exports")
    os.environ["WW3_CP_EXPORT_REPLAY"] = "0"
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_replay_capturepoint_exports")(srv, None, None, conn)
    fails += check(r is False and not conn.replay_queue, "flag off -> no-op")
    os.environ["WW3_CP_EXPORT_REPLAY"] = "1"
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_replay_capturepoint_exports")(srv, None, None, conn)
    fails += check(r is True and len(conn.replay_queue) == 2, "queued both export opens")
    exps = sorted({e for b in conn.replay_queue for e in b.get("_exports", [])})
    fails += check(any("BP_CapturePoint" in e for e in exps),
                   "exports name BP_CapturePoint_A/B")
    fails += check(any("First Spawn Zone" in e for e in exps),
                   "exports include the First Spawn Zone child (the h287 target)")
    os.environ["WW3_CP_EXPORT_REPLAY"] = "0"

    print("[smoke] maybe_answer_spectate_attach")
    os.environ["WW3_SPECTATE_POINT_REPLY"] = "0"
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_answer_spectate_attach")(srv, None, None, conn)
    fails += check(r is False and not srv.sent, "flag off -> no-op")

    os.environ["WW3_SPECTATE_POINT_REPLY"] = "1"
    os.environ["WW3_SPECTATE_POINT_REPLY_MAX"] = "3"
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_answer_spectate_attach")(srv, None, None, conn)
    fails += check(r is True and len(srv.sent) == 1, "first reply sent")
    fails += check(len(srv.sent[0]) == 2,
                   "first reply is ClientSetViewTarget + Client_UpdateSpectatePoint")
    bind("maybe_answer_spectate_attach")(srv, None, None, conn)
    bind("maybe_answer_spectate_attach")(srv, None, None, conn)
    r = bind("maybe_answer_spectate_attach")(srv, None, None, conn)
    fails += check(r is False and len(srv.sent) == 3, "bounded by REPLY_MAX=3")

    print("[smoke] maybe_mark_deploy_eligible")
    os.environ["WW3_DEPLOY_MARK_DEAD"] = "1"
    os.environ["WW3_DEPLOY_DEAD_HEALTH"] = "0"
    os.environ["WW3_DEPLOY_PLAYING_STATE"] = ""
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_mark_deploy_eligible")(srv, None, None, conn)
    fails += check(r is True and len(srv.sent) == 1, "health write sent")

    print("[smoke] maybe_revive_after_deploy")
    os.environ["WW3_DEPLOY_REVIVE_ON_ANSWER"] = "1"
    srv, conn = StubServer(), StubConn()
    r = bind("maybe_revive_after_deploy")(srv, None, None, conn)
    fails += check(r is True and len(srv.sent) == 1, "revive write sent")

    print()
    if fails:
        print(f"[smoke] {fails} FAILURE(S)")
        return 1
    print("[smoke] all deploy-path methods execute cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
