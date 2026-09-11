#!/usr/bin/env python3
"""Probe Engine PlayerController.h RPC declaration order vs live wire anchors."""
from __future__ import annotations

import re
from pathlib import Path

path = Path(
    r"C:\Users\georg\.cursor\projects\f-Dev-Work-GameDev-WW3\agent-tools"
    r"\c6a68307-0e84-4bf1-bbb0-632e44cbf541.txt"
)
text = path.read_text(encoding="utf-8").splitlines()
funcs: list[str] = []
i = 0
while i < len(text):
    line = text[i]
    if "UFUNCTION" in line:
        j = i
        while j < len(text) and ")" not in "".join(text[i : j + 1]):
            j += 1
        attrs = " ".join(text[i : j + 1])
        is_cs = bool(re.search(r"\b(Client|Server)\b", attrs, re.I))
        if is_cs:
            k = j + 1
            name = None
            while k < len(text) and k < j + 20:
                m = re.search(r"\b((?:Client|Server)\w+)\s*\(", text[k])
                if m:
                    name = m.group(1)
                    break
                # also lowercase UFUNCTION(server) then void ServerFoo
                m = re.search(r"\bvoid\s+((?:Client|Server)\w+)\s*\(", text[k])
                if m:
                    name = m.group(1)
                    break
                k += 1
            if name:
                funcs.append(name)
        i = j + 1
        continue
    i += 1

seen: set[str] = set()
ordered: list[str] = []
for n in funcs:
    if n in seen:
        continue
    seen.add(n)
    ordered.append(n)

print("count", len(ordered))
keys = {
    "ClientRestart",
    "ClientRetryClientRestart",
    "ClientSetHUD",
    "ServerAcknowledgePossession",
    "ServerCheckClientPossession",
    "ServerCheckClientPossessionReliable",
    "ServerNotifyLoadedWorld",
    "ClientReset",
    "ClientCapBandwidth",
}
for idx, n in enumerate(ordered):
    mark = " <<<<" if n in keys else ""
    if mark or idx < 60:
        print(f"{idx:3} {n}{mark}")

print("--- keys ---")
for want in [
    "ClientRestart",
    "ClientRetryClientRestart",
    "ClientSetHUD",
    "ServerAcknowledgePossession",
    "ServerCheckClientPossession",
    "ServerCheckClientPossessionReliable",
    "ServerNotifyLoadedWorld",
]:
    print(want, ordered.index(want) if want in ordered else "MISSING")

if "ClientSetHUD" in ordered and "ClientRestart" in ordered:
    hud_i = ordered.index("ClientSetHUD")
    cr_i = ordered.index("ClientRestart")
    print("predicted ClientRestart wire", 24 - (hud_i - cr_i))
    if "ClientRetryClientRestart" in ordered:
        print(
            "predicted Retry wire",
            24 - (hud_i - ordered.index("ClientRetryClientRestart")),
        )
if "ServerAcknowledgePossession" in ordered and "ClientSetHUD" in ordered:
    ack_i = ordered.index("ServerAcknowledgePossession")
    hud_i = ordered.index("ClientSetHUD")
    pred = 24 + (ack_i - hud_i)
    print("predicted Ack wire from HUD", pred, "actual 34 delta", 34 - pred)
