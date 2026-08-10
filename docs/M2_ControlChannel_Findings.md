# M2 — Control Channel: decoded from the real capture

Source: `captures/24July26/W3_match_full_2.pcapng`, match server `213.183.62.18:7868`.
All values are **real, live-on-the-wire bytes** (this capture started before the client joined,
so the whole connection is intact). Decoded with `match_server/ue4_bits.py` +
`match_analysis/pcap_tools.py` (pcapng reader). This is the ground truth for building the
M2 control-channel handler in `server.py`.

## Packet framing (LOCKED)

WW3 uses UE4's **legacy** connection format (NOT `FNetPacketNotify` — the packets are far too
small for a 32-bit packed header + history word). Every post-handshake UDP packet:

```
bit  0        bHandshakePacket = 0        (the StatelessConnect handler prepends this; 1 = handshake)
bits 1..14    PacketId  (14-bit sequence) LSB-first, increments by exactly 1 per packet, per direction
bits 15..     packet content: ack(s) and/or bunch(es)
last set bit  terminator                  (UE4 end-of-packet 1-bit marker)
```

Verified: C→S sequence ran 14383,14384,14385,… and S→C ran 7961,7962,7963,… (delta = 1 each).
The smallest packets (3 bytes = 16 payload bits) are `handshake(0) + 14-bit seq + 1 bit + terminator`
— keep-alive / ack carriers with no bunch.

Next to pin (from the ack packets, e.g. C→S `62 | f0 19 1f 80 1a 1f 80 | 01` which acks server
packet-ids 0x19,0x1a): the exact per-entry format of an **ack** vs a **bunch** in the legacy stream.
Reference: UE4.21 `Engine/Source/Runtime/Engine/Private/DataChannel.cpp` +
`NetConnection.cpp` (the `bUseNetPacketNotify == false` path).

## Control-message sequence (channel 0)

From the packet order + sizes after the handshake (packets [4]+):

| pkt | dir | len | meaning |
|----|-----|----:|---------|
| [4]  | C→S | 18  | **NMT_Hello** (client → server, first control message) |
| [5]  | S→C | 22  | **NMT_Challenge** (server → client; carries a ~32-char challenge FString) |
| [7]  | C→S | 701 | **NMT_Login** (client → server; URL + UniqueId + lobbyToken) — decoded below |
| [8],[10],[11] | C→S | small | ack bunches (ack server packet-ids) |
| [12] | S→C | 173 | server reply — **NMT_Welcome / map** (assigns the match map from the token) |
| [13]+ | both | small | acks + channel opens |

## NMT_Login — the join credential (DECODED)

The client's NMT_Login (packet [7]) presents **three** fields the match server consumes:

**1. URL** (FString, 109 chars):
```
/Game/Maps/Main/Hub/WW3_Hub_P?Name=Player?BuildIdOverride=51?EosProductUserId=00000000000000000000000000000000
```
- The map part is the client's **current** map (the Hub) — the server assigns the real match
  map (`WW3_Gobi_New_P`, from the token) via NMT_Welcome.
- Options our server must read: `Name`, `BuildIdOverride` (=51), `EosProductUserId`.

**2. UniqueId** — the player's SteamID (`76561198000000001`), as `FUniqueNetIdRepl`.

**3. lobbyToken** — a **separate trailing FString** (535 chars, NOT a URL option), immediately
after the UniqueId. This is the admission credential:

```json
// HS256 JWT header {"alg":"HS256","typ":"JWT"}, payload:
{
  "type": "LobbyToken",
  "lobbyId": 70121,
  "playerId": 100002,
  "serverGroup": "default",
  "team": { "id": 1 },
  "isServerAssigned": true,
  "server": {
    "serverId": 17659577,
    "matchId": "17659577-1784897330704",
    "address": "213.183.62.18",
    "gamePort": 7868,          // note: match game port = the connect port (not 7871)
    "queryPort": 27112,
    "serverGroup": "default",
    "map": "WW3_Gobi_New_P",
    "gameMode": 47
  },
  "iat": 1784897698,
  "exp": 1784901298            // iat + 3600s
}
```

**This matches our M1 spec and what `hub_server.py` (M2) already mints, field-for-field** — the
only alignments to make in our mock: `gamePort=7868` and `queryPort=27112` (we were using 7871/27115).
Because it's HS256, our server both mints (via the hub) and validates (at the match server) with
**our own secret** (`"ww3-local-private"`) — no studio key.

## What the M2 handler in server.py must do

1. Parse the legacy packet header (14-bit seq) and the bunch/ack stream.
2. On the control channel (0): receive **NMT_Hello** → send **NMT_Challenge**;
   receive **NMT_Login** → read the URL options + UniqueId + the trailing lobbyToken FString →
   **validate the token** (HS256, our secret; check `exp`, `server.map`, team) → send **NMT_Welcome**
   (Map = `server.map` from the token, e.g. `WW3_Gobi_New_P`, GameMode from `server.gameMode`).
3. Ack the client's packets (legacy ack entries) and keep the sequence advancing.
4. That gets the client past login → it starts loading the map → M3 (send the map / empty world).

FString on the wire = `int32 length` (incl. null terminator; negative ⇒ UTF-16) then the chars.
Bit-packed LSB-first, so fields are **not** byte-aligned — always read through `ue4_bits.BitReader`.
