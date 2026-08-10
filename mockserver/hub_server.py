#!/usr/bin/env python3
"""
WW3 Hub WebSocket mock -- port 8700 (build 1795; was 8705 in June).
Speaks the WW3 JSON-RPC protocol; the client connects to
ws://<hub>:8700/client/<JWT> and drives the menu through
{"type":"RpcRequest",...} / {"type":"RpcResponse",...} messages,
plus HeartbeatPing/Pong keepalives.

Replays the REAL captured RPC results from replay_map.json (built by
build_replay_map.py), with fallbacks for the few calls we didn't capture.
"""
import asyncio, json, logging, re, sys, os
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [HUB] %(message)s")
log = logging.getLogger("hub")

MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay_map.json")
RPC = (json.load(open(MAP_PATH, encoding="utf-8")).get("rpc", {})
       if os.path.exists(MAP_PATH) else {})

# onlineParameters.getParameters was NOT captured (sniffer joined mid-stream).
# Known-good shape from the June working-day log -- ping cfg unblocks the menu.
ONLINE_PARAMETERS = {
    "type": "OnlineParameters",
    "pingPongInterval": 4000,
    "pingPongTimeout": 10000,
    "logsConfig": [
        {"category": "LogOnlineWW3", "verbosity": "Display"},
        {"category": "LogTemp", "verbosity": "Warning"},
    ],
}

# =====================================================================================
# M4 OBSERVABILITY -- client log relay
#
# The WW3 client uploads its own UE log lines back to the backend as
#   {"context":"debug","method":"log","args":[{"logs":[{"msg":"...","timestamp":...}],
#                                              "topic":"live.client.global.errors"}]}
# Warning/Error lines are included by default (proven in the 2026-08-05 crash log:
# LogTemp/LogConsoleManager Warnings and the ConnectionTimeout Error all arrived here).
# That is exactly the severity at which UE prints WHY an actor open bunch was rejected:
#   LogNet: Warning: UActorChannel::ProcessBunch: SerializeNewActor failed to find/spawn actor
#   LogNet: Warning: UActorChannel::ProcessQueuedBunches: Queued bunches for longer than...
#   LogNetPackageMap: Warning: InternalLoadObject: Unable to resolve object from path
#   LogNetPartialBunch: Warning: Corrupt partial bunch...
# The hub used to drop every one of these on the floor ("keep debug spam quiet").
# Now they are written to disk, so a stuck LOADING MAP can be diagnosed from the
# CLIENT's point of view without crashing it to flush its in-memory log ring.
# =====================================================================================
CLIENT_LOG_CAPTURE = os.environ.get("WW3_CLIENT_LOG_CAPTURE", "1") != "0"
CLIENT_LOG_DIR = os.environ.get("WW3_CLIENT_LOG_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "match_server", "live_log", "client_log")
# Lines matching this go to the *_net.log sidecar and are echoed to the hub console.
CLIENT_LOG_NET_PAT = re.compile(
    r"\bLog(?:Net\w*|Spawn|PlayerController|Pawn|Actor\w*|World|Level\w*|Streaming|"
    r"WW3Player|WW3ClientSynchronization)\s*:"
    r"|SerializeNewActor|ActorChannel|ProcessBunch|QueuedBunches|PackageMap|NetGUID"
    r"|AcknowledgePossession|ClientRestart|PossessedBy|UnPossess|Archetype",
    re.IGNORECASE)
# Opt-in: ask the client to raise verbosity on the networking categories. OFF by default
# because VeryVerbose LogNetTraffic in a live match is a lot of log volume and we have not
# measured what the client's uploader does with it.
if os.environ.get("WW3_CLIENT_LOG_NET", "0") == "1":
    ONLINE_PARAMETERS["logsConfig"] += [
        {"category": "LogNet", "verbosity": "Verbose"},
        {"category": "LogNetPackageMap", "verbosity": "VeryVerbose"},
        {"category": "LogNetPartialBunch", "verbosity": "VeryVerbose"},
        {"category": "LogNetTraffic", "verbosity": "Verbose"},
        {"category": "LogSpawn", "verbosity": "Verbose"},
    ]

_CLIENT_LOG_STATE = {"all": None, "net": None, "n": 0, "nnet": 0}


def _client_log_open():
    if _CLIENT_LOG_STATE["all"] is not None:
        return
    os.makedirs(CLIENT_LOG_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(CLIENT_LOG_DIR, f"client_{ts}")
    _CLIENT_LOG_STATE["all"] = open(base + ".log", "a", encoding="utf-8", errors="replace")
    _CLIENT_LOG_STATE["net"] = open(base + "_net.log", "a", encoding="utf-8", errors="replace")
    latest = os.path.join(CLIENT_LOG_DIR, "CURRENT_CLIENT_LOG.txt")
    with open(latest, "w", encoding="utf-8") as fh:
        fh.write(base + ".log\n" + base + "_net.log\n")
    log.info(f"[CLIENTLOG] capturing client-uploaded UE log -> {base}.log (+ _net.log)")


def capture_client_logs(args):
    """Persist the client's own UE log lines (context=debug, method=log)."""
    if not CLIENT_LOG_CAPTURE:
        return
    try:
        _client_log_open()
        payload = args[0] if args and isinstance(args[0], dict) else {}
        topic = payload.get("topic") or ""
        for entry in payload.get("logs") or []:
            if not isinstance(entry, dict):
                continue
            msg = str(entry.get("msg", "")).rstrip()
            if not msg:
                continue
            line = f"[{entry.get('timestamp','')}] {msg}"
            if topic and "errors" in topic:
                line = f"[{entry.get('timestamp','')}] (ERRORTOPIC) {msg}"
            _CLIENT_LOG_STATE["all"].write(line + "\n")
            _CLIENT_LOG_STATE["n"] += 1
            if CLIENT_LOG_NET_PAT.search(msg):
                _CLIENT_LOG_STATE["net"].write(line + "\n")
                _CLIENT_LOG_STATE["nnet"] += 1
                log.info(f"[CLIENTLOG-NET] {msg[:220]}")
        _CLIENT_LOG_STATE["all"].flush()
        _CLIENT_LOG_STATE["net"].flush()
    except Exception as e:      # never let logging break the menu
        log.info(f"[CLIENTLOG] capture failed: {e}")

# =====================================================================================
# M2 -- MATCHMAKING / LOBBY LAYER  (implements docs/M1_Match_Orchestration_Spec.md)
#
# Answers the client's matchmaking RPC, runs the lobby lifecycle, and hands the client
# a server + a freshly minted lobbyToken pointing at OUR LOCAL match server. The token
# is HS256 -- issuer and verifier are both us, so no studio secret is needed.
# =====================================================================================
import hmac, hashlib, base64, time, random, datetime

M2_ENABLED    = os.environ.get("WW3_M2", "1") != "0"
LOBBY_SECRET  = b"ww3-local-private"                    # our HS256 signing secret
PLAYER_ID     = 100001
# Must match capture local PS PlayerName (src 21 RepLayout = "Player"). Login URL Name=
# OfflinePlayer left PlayerState sync false while PS still said Player.
PLAYER_NAME   = os.environ.get("WW3_PLAYER_NAME", "Player")
MATCH_SERVER  = {                                       # where M3 will host
    "address":   os.environ.get("WW3_MATCH_ADDR", "127.0.0.1"),
    "gamePort":  int(os.environ.get("WW3_MATCH_PORT", "7871")),
    "queryPort": int(os.environ.get("WW3_MATCH_QPORT", "27115")),
    "serverGroup": "default",
}
READY_DELAY   = float(os.environ.get("WW3_READY_DELAY", "2.0"))   # lobby -> ready
# Hands-off match trigger: HTTP control port (curl) + optional auto after hub connect.
# Does not touch the user's mouse — agent can start a match while you keep working.
CONTROL_PORT  = int(os.environ.get("WW3_HUB_CONTROL_PORT", "8701"))
AUTO_MATCH_S  = float(os.environ.get("WW3_HUB_AUTO_MATCH_S", "0"))  # 0 = off
ACTIVE_CLIENT = {"ws": None, "peer": None}

# Prefer these maps when the client offers a list (or when it sends none).
# Override with WW3_PREF_MAP=WW3_Shibuya_P etc.
PREFERRED_MAPS = [
    os.environ.get("WW3_PREF_MAP", "WW3_Landmark_P"),
    "WW3_Landmark_P",
    "WW3_Moscow_Senate_P",
    "WW3_Shibuya_P",
    "WW3_Berlin_Backyards_02_P",
    "WW3_Warsaw_Shopping_Mall_P",
    "WW3_DMZ_P",
]
# TDM_M alias from maps/getAll for Landmark / Senate / Shibuya-style playlists
TDM_ALIAS = 10

def pick_lobby_map(req):
    # Hard override for live match tests (ignore client's playlist).
    forced = os.environ.get("WW3_FORCE_LOBBY_MAP") or ""
    if forced.strip():
        log.info(f"[M2] FORCE_LOBBY_MAP={forced}")
        return forced.strip()
    client_maps = req.get("maps") if isinstance(req, dict) else None
    if not isinstance(client_maps, list):
        client_maps = []
    for pref in PREFERRED_MAPS:
        if not pref:
            continue
        if not client_maps or pref in client_maps:
            return pref
    if client_maps:
        return client_maps[0]
    return "WW3_Landmark_P"

def pick_lobby_mode(req, chosen_map):
    forced = os.environ.get("WW3_FORCE_LOBBY_MODE") or ""
    if forced.strip():
        try:
            return int(forced.strip())
        except ValueError:
            pass
    modes = req.get("gameModes") if isinstance(req, dict) else None
    if isinstance(modes, list) and modes:
        return modes[0]
    # Landmark (and most TDM playlist maps) use TDM alias 10 when unspecified
    if chosen_map and "Landmark" in chosen_map:
        return TDM_ALIAS
    if chosen_map and "Gobi" in chosen_map:
        return 47  # Domination-Newbie — matches our spawn capture
    return 47

def _b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def mint_lobby_token(payload):
    """HS256 JWT, same shape the real hub issued (see M1 spec section 5)."""
    seg = lambda o: _b64u(json.dumps(o, separators=(",", ":")).encode())
    signing = seg({"alg": "HS256", "typ": "JWT"}) + "." + seg(payload)
    sig = hmac.new(LOBBY_SECRET, signing.encode(), hashlib.sha256).digest()
    return signing + "." + _b64u(sig)

def make_player(pid, team=0):
    return {"playerId": pid, "playerName": PLAYER_NAME, "level": 52, "status": 4,
            "lastseen": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "xmppAccount": {"username": f"prod-{pid}"},
            "levelIconId": 0, "bannerAttachmentsIds": [6382, 7953, 7224],
            "teamId": team, "squadId": None}

class Lobby:
    _next = 67000
    def __init__(self, req, pid):
        Lobby._next += 1
        self.id       = Lobby._next
        self.map      = pick_lobby_map(req)
        self.gameMode = pick_lobby_mode(req, self.map)
        self.group    = req.get("serverGroup", "default")
        self.player   = make_player(pid)
        self.version  = 1
        self.serverId = random.randint(200_000_000, 399_999_999)
        self.matchId  = f"{self.serverId}-{int(time.time()*1000)}"

    def server_obj(self):
        return {"serverId": self.serverId, "matchId": self.matchId,
                "address": MATCH_SERVER["address"], "gamePort": MATCH_SERVER["gamePort"],
                "queryPort": MATCH_SERVER["queryPort"], "serverGroup": self.group,
                "gameMode": self.gameMode, "map": self.map}

    def teams(self):
        return [{"id": 0, "size": 8, "players": [self.player["playerId"]], "squads": [],
                 "supportsSquads": False, "nextSquadId": 1},
                {"id": 1, "size": 8, "players": [], "squads": [],
                 "supportsSquads": False, "nextSquadId": 9}]

    def obj(self, state):
        return {"id": self.id, "playersLimit": 16, "gameMode": self.gameMode, "map": self.map,
                "players": [self.player], "teams": self.teams(), "state": state,
                "gameStartTimestamp": int(time.time()*1000) + int(READY_DELAY*1000),
                "version": self.version, "serverGroup": self.group, "supportsSquads": False}

    def token(self):
        now = int(time.time())
        return mint_lobby_token({"type": "LobbyToken", "lobbyId": self.id,
                                 "playerId": self.player["playerId"], "serverGroup": self.group,
                                 "team": {"id": self.player["teamId"]}, "isServerAssigned": False,
                                 "server": self.server_obj(), "iat": now, "exp": now + 3600})

LOBBIES = {}

async def lobby_lifecycle(ws, lob):
    """Push LobbyChange -> LobbyReadyStateChange (server + token) -> LobbyMatchStarted."""
    try:
        await asyncio.sleep(0.5)
        lob.version = 2
        await ws.send(json.dumps({"type": "LobbyChange", "target": {
            "id": lob.id, "players": {"added": [lob.player], "removed": []}, "version": 2}}))
        log.info(f"[M2] lobby {lob.id}: player {lob.player['playerId']} -> team {lob.player['teamId']}")

        await asyncio.sleep(READY_DELAY)
        lob.version = 3
        await ws.send(json.dumps({"type": "LobbyReadyStateChange",
            "target": {"id": lob.id, "state": 3, "server": lob.server_obj(), "version": 3},
            "lobby": lob.obj(3), "stateType": "Ready", "lobbyToken": lob.token()}))
        log.info(f"[M2] lobby {lob.id} READY -> {MATCH_SERVER['address']}:{MATCH_SERVER['gamePort']} "
                 f"map={lob.map} mode={lob.gameMode} match={lob.matchId} (lobbyToken minted)")

        await asyncio.sleep(1.0)
        # The captured hub increments the optimistic-concurrency revision for
        # every lifecycle transition: Ready is version 3, MatchStarted is 4.
        # Keeping state=4 at stale version=3 lets the client connect but leaves
        # its connection controller with an internally inconsistent lobby.
        lob.version = 4
        await ws.send(json.dumps({"type": "LobbyMatchStarted", "stateType": "MatchStarted",
                                  "target": {"id": lob.id}, "lobby": lob.obj(4)}))
        log.info(f"[M2] lobby {lob.id} MATCH STARTED -- client should now connect to the match server")
    except Exception as e:
        log.info(f"[M2] lobby {lob.id} lifecycle stopped: {e}")

def route(context, method, args):
    """Result value for an RPC call: captured response first, then fallbacks."""
    key = f"{context}.{method}"
    if key in RPC:
        return RPC[key]
    if context == "onlineParameters":
        return ONLINE_PARAMETERS
    if context == "friends" and method in ("getAll", "getReceivedInvitations", "getSentInvitations"):
        return []
    if context == "notifications":
        return {"notifications": {"news": []}}
    # never leave a request unanswered -- an unanswered id is what hangs the client
    return True

def make_response(rid, result):
    return json.dumps({"type": "RpcResponse", "id": rid, "result": result})

# --- M3: game-mode config the dedicated server's GameModeConfigReader needs ---
def _load_gamemode_params():
    try:
        http = json.load(open(MAP_PATH, encoding="utf-8")).get("http", {})
        for k, v in http.items():
            if "getGameModesParameters" in k or "GameModesParameters" in k:
                b = v.get("body", {})
                return b.get("result", b)
    except Exception:
        pass
    return {}
GAMEMODE_PARAMS = _load_gamemode_params()

def server_route(context, method, args):
    """Answer a dedicated-server's RPC. Serve game-mode config to its GameModeConfigReader;
    never leave an RPC unanswered (an unanswered id stalls the server)."""
    log.info(f"[M3-SRV] <- {context}.{method} {str(args)[:70]}")
    key = f"{context}.{method}"
    if "gamemode" in context.lower() or "gamemode" in method.lower() or "gamemodes" in method.lower():
        return GAMEMODE_PARAMS
    if context == "onlineParameters":
        return ONLINE_PARAMETERS
    if key in RPC:
        return RPC[key]
    return True

async def server_handler(ws):
    """The headless dedicated match server's hub connection (ws://.../server/<token>)."""
    peer = getattr(ws, "remote_address", "?")
    log.info(f"[M3] >>> DEDICATED SERVER connected {peer} <<<")
    hb = asyncio.ensure_future(heartbeat_sender(ws))
    try:
        async for raw in ws:
            try: msg = json.loads(raw)
            except Exception: continue
            mtype = msg.get("type")
            if mtype == "RpcRequest":
                rid, ctx, meth = msg.get("id"), msg.get("context"), msg.get("method")
                await ws.send(make_response(rid, server_route(ctx, meth, msg.get("args", []))))
            elif mtype == "HeartbeatPing":
                await ws.send(json.dumps({"type": "HeartbeatPong"}))
            elif mtype in ("HeartbeatPong", "RpcResponse"):
                pass
            else:
                log.info(f"[M3-SRV] <- {mtype}: {str(msg)[:90]}")
    except websockets.ConnectionClosed:
        log.info(f"[M3] dedicated server disconnected {peer}")
    except Exception as e:
        log.info(f"[M3] server handler error: {e}")
    finally:
        hb.cancel()

HEARTBEAT_INTERVAL = ONLINE_PARAMETERS["pingPongInterval"] / 1000.0   # 4s: the client
# expects the SERVER to push HeartbeatPing this often; without it the "communication
# service" times out and shows "lost connection / reconnecting" every ~2 min.

async def heartbeat_sender(ws):
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await ws.send(json.dumps({"type": "HeartbeatPing"}))
    except Exception:
        pass

async def start_forced_lobby(ws, reason="control"):
    """Push a full lobby lifecycle to a connected client (no findLobby click needed).

    Best-effort: client normally expects this after findLobbyForParty. Works when the
    menu is already listening for Lobby* pushes; otherwise use silent postclick UI.
    """
    req = {
        "playerId": PLAYER_ID,
        "maps": [os.environ.get("WW3_FORCE_LOBBY_MAP") or PREFERRED_MAPS[0]],
        "gameModes": [int(os.environ.get("WW3_FORCE_LOBBY_MODE") or TDM_ALIAS)],
    }
    lob = Lobby(req, PLAYER_ID)
    LOBBIES[lob.id] = lob
    log.info(f"[M2] FORCE MATCH ({reason}): map={lob.map} mode={lob.gameMode} lobby={lob.id}")
    await ws.send(json.dumps({"type": "LobbyChange", "target": {
        "id": lob.id, "players": {"added": [lob.player], "removed": []}, "version": 1}}))
    asyncio.ensure_future(lobby_lifecycle(ws, lob))
    return lob


async def control_http(reader, writer):
    """Minimal HTTP: GET /status  GET /match  GET /clearlobbies"""
    try:
        req = await asyncio.wait_for(reader.read(2048), timeout=2.0)
        line = req.decode("latin-1", errors="ignore").split("\r\n", 1)[0]
        path = line.split(" ")[1] if " " in line else "/"
        ws = ACTIVE_CLIENT.get("ws")
        if path.startswith("/status"):
            body = json.dumps({
                "client": bool(ws),
                "peer": str(ACTIVE_CLIENT.get("peer")),
                "lobbies": list(LOBBIES.keys()),
                "match": f"{MATCH_SERVER['address']}:{MATCH_SERVER['gamePort']}",
            })
            code = "200 OK"
        elif path.startswith("/clearlobbies"):
            # Drop forced/active lobbies so a stuck LOADING client can return to menu
            # without another travel. Sends LobbyLeft when a hub client is present.
            cleared = list(LOBBIES.keys())
            for lid in cleared:
                if ws:
                    try:
                        await ws.send(json.dumps({"type": "LobbyLeft", "target": {"id": lid}}))
                    except Exception as e:
                        log.info(f"[CTRL] LobbyLeft {lid} failed: {e}")
                LOBBIES.pop(lid, None)
            body = json.dumps({"ok": True, "cleared": cleared})
            code = "200 OK"
            log.info(f"[CTRL] /clearlobbies -> {cleared}")
        elif path.startswith("/match"):
            if not ws:
                body = json.dumps({"ok": False, "error": "no client connected to hub"})
                code = "409 Conflict"
            else:
                lob = await start_forced_lobby(ws, reason="http /match")
                body = json.dumps({"ok": True, "lobbyId": lob.id, "map": lob.map, "mode": lob.gameMode})
                code = "200 OK"
        else:
            body = json.dumps({"endpoints": ["/status", "/match", "/clearlobbies"]})
            code = "200 OK"
        resp = (
            f"HTTP/1.1 {code}\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}"
        )
        writer.write(resp.encode())
        await writer.drain()
    except Exception as e:
        log.info(f"[CTRL] http error: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def auto_match_after_connect(ws):
    if AUTO_MATCH_S <= 0:
        return
    log.info(f"[M2] AUTO_MATCH armed: will force lobby in {AUTO_MATCH_S}s")
    try:
        await asyncio.sleep(AUTO_MATCH_S)
        if ACTIVE_CLIENT.get("ws") is ws:
            await start_forced_lobby(ws, reason=f"auto after {AUTO_MATCH_S}s")
    except Exception as e:
        log.info(f"[M2] AUTO_MATCH failed: {e}")


async def handler(ws):
    # dispatch by URL path: the dedicated server connects to /server/<token>,
    # the game client to /client/<token>.
    path = ""
    try: path = ws.request.path
    except Exception:
        try: path = ws.path
        except Exception: path = ""
    if "/server/" in path:
        await server_handler(ws)
        return
    peer = getattr(ws, "remote_address", "?")
    log.info(f"[+] client connected {peer}")
    ACTIVE_CLIENT["ws"] = ws
    ACTIVE_CLIENT["peer"] = peer
    hb = asyncio.ensure_future(heartbeat_sender(ws))   # keep the comms service alive
    asyncio.ensure_future(auto_match_after_connect(ws))
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            if mtype == "RpcRequest":
                rid, ctx, meth = msg.get("id"), msg.get("context"), msg.get("method")
                args = msg.get("args", [])

                # ---- M2: real matchmaking instead of replaying a captured lobby ----
                if M2_ENABLED and ctx == "lobby" and meth in ("findLobbyForParty", "findCustomLobbyForParty"):
                    req = args[0] if args and isinstance(args[0], dict) else {}
                    lob = Lobby(req, req.get("playerId", PLAYER_ID))
                    LOBBIES[lob.id] = lob
                    log.info(f"[M2] {meth}: map={lob.map} mode={lob.gameMode} -> lobby {lob.id}")
                    await ws.send(make_response(rid, {"lobby": lob.obj(1)}))
                    asyncio.ensure_future(lobby_lifecycle(ws, lob))
                    continue
                if M2_ENABLED and ctx == "lobby" and meth in ("cancelMatchmaking", "removePlayerFromLobby"):
                    for lid in list(LOBBIES):
                        await ws.send(json.dumps({"type": "LobbyLeft", "target": {"id": lid}}))
                        LOBBIES.pop(lid, None)
                    log.info(f"[M2] {meth} -> lobbies cleared")
                    await ws.send(make_response(rid, True))
                    continue

                if ctx == "debug" and meth == "log":
                    capture_client_logs(args)               # M4: keep the client's own UE log

                result = route(ctx, meth, args)
                await ws.send(make_response(rid, result))
                if not (ctx == "debug" and meth == "log"):   # keep debug spam quiet
                    src = "replay" if f"{ctx}.{meth}" in RPC else "fallback"
                    log.info(f"[<] {ctx}.{meth} id={rid} -> [{src}] {str(result)[:60]}")
            elif mtype == "HeartbeatPing":
                await ws.send(json.dumps({"type": "HeartbeatPong"}))   # client-initiated ping
            elif mtype in ("HeartbeatPong", "RpcResponse"):
                pass  # client acking our ping / server-initiated request; ignore
            else:
                log.info(f"[<] {mtype}: {str(msg)[:80]}")
    except websockets.ConnectionClosed:
        log.info(f"[-] client disconnected {peer}")
    except Exception as e:
        log.info(f"[!] handler error: {e}")
    finally:
        hb.cancel()
        if ACTIVE_CLIENT.get("ws") is ws:
            ACTIVE_CLIENT["ws"] = None
            ACTIVE_CLIENT["peer"] = None

async def main(port):
    log.info(f"[*] WW3 Hub mock on ws://0.0.0.0:{port}/  ({len(RPC)} captured RPC methods)")
    log.info(f"[*] Hub control HTTP on http://127.0.0.1:{CONTROL_PORT}/  (GET /status /match)")
    if AUTO_MATCH_S > 0:
        log.info(f"[*] WW3_HUB_AUTO_MATCH_S={AUTO_MATCH_S} (force lobby after client hub connect)")
    ctrl = await asyncio.start_server(control_http, "127.0.0.1", CONTROL_PORT)
    async with websockets.serve(handler, "0.0.0.0", port, ping_interval=None, max_size=None), ctrl:
        await asyncio.Future()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8700
    try:
        asyncio.run(main(port))
    except KeyboardInterrupt:
        log.info("Hub stopped.")
