#!/usr/bin/env python3
"""Deterministic tests for the Windows UDP WSAECONNRESET receive path."""
from __future__ import annotations

import sys
import io
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import server as srvmod  # noqa: E402


class FakeReset(ConnectionResetError):
    def __init__(self, winerror):
        super().__init__(winerror, "synthetic UDP reset")
        self.winerror = winerror


class SequenceSocket:
    def __init__(self, events):
        self.events = list(events)
        self.calls = 0

    def recvfrom(self, _size):
        self.calls += 1
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event


def test_wsaeconnreset_is_ignored_and_next_datagram_is_returned():
    srv = srvmod.MatchServer()
    fake = SequenceSocket([
        FakeReset(10054),
        FakeReset(10054),
        (b"next", ("127.0.0.1", 7871)),
    ])

    recv = getattr(srv, "recvfrom_resilient", None)
    assert callable(recv), "receive loop must expose the resilient WinError 10054 helper"
    data, addr = recv(fake)

    assert (data, addr) == (b"next", ("127.0.0.1", 7871))
    assert fake.calls == 3
    assert srv._udp_reset_count == 2
    print("[ok] WinError 10054 does not terminate the UDP receive loop")


def test_other_connection_reset_is_not_swallowed():
    srv = srvmod.MatchServer()
    fake = SequenceSocket([FakeReset(10053)])
    try:
        recv = getattr(srv, "recvfrom_resilient", None)
        assert callable(recv), "receive loop must expose the resilient WinError 10054 helper"
        recv(fake)
    except ConnectionResetError as exc:
        assert exc.winerror == 10053
    else:
        raise AssertionError("non-10054 ConnectionResetError must propagate")
    print("[ok] unrelated ConnectionResetError still propagates")


def test_reset_logging_is_bounded_after_first_three():
    srv = srvmod.MatchServer()
    fake = SequenceSocket(
        [FakeReset(10054) for _ in range(5)]
        + [(b"next", ("127.0.0.1", 7871))]
    )
    output = io.StringIO()
    with redirect_stdout(output):
        assert srv.recvfrom_resilient(fake)[0] == b"next"
    lines = [line for line in output.getvalue().splitlines() if "WinError 10054" in line]
    assert len(lines) == 3, lines
    assert "count=1" in lines[0] and "count=3" in lines[-1]
    print("[ok] UDP reset audit logging is bounded after the first three events")


if __name__ == "__main__":
    test_wsaeconnreset_is_ignored_and_next_datagram_is_returned()
    test_other_connection_reset_is_not_swallowed()
    test_reset_logging_is_bounded_after_first_three()
    print("ALL UDP listener tests passed")
