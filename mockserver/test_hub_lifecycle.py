#!/usr/bin/env python3
"""Regression tests for the capture-faithful lobby revision sequence."""
from __future__ import annotations

import asyncio
import json

import hub_server


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, payload):
        self.messages.append(json.loads(payload))


def test_match_started_advances_lobby_revision_to_four():
    ws = FakeWebSocket()
    lob = hub_server.Lobby({}, hub_server.PLAYER_ID)
    original_sleep = hub_server.asyncio.sleep

    async def no_sleep(_seconds):
        return None

    hub_server.asyncio.sleep = no_sleep
    try:
        asyncio.run(hub_server.lobby_lifecycle(ws, lob))
    finally:
        hub_server.asyncio.sleep = original_sleep

    ready = next(m for m in ws.messages if m["type"] == "LobbyReadyStateChange")
    started = next(m for m in ws.messages if m["type"] == "LobbyMatchStarted")
    assert ready["target"]["version"] == ready["lobby"]["version"] == 3
    assert started["lobby"]["state"] == 4
    assert started["lobby"]["version"] == 4
    assert lob.version == 4


if __name__ == "__main__":
    test_match_started_advances_lobby_revision_to_four()
    print("ALL hub lifecycle tests passed")
