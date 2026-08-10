#!/usr/bin/env python3
r"""
server.py -- WW3 match server (Path B).

Milestone ladder:
  M1  StatelessConnect handshake          [DONE] stateless_handshake.py -- byte-exact vs capture
  M2  Control channel (NMT_Hello/Login)   [DONE] control_channel.py + NMT state machine
  M3  Load a map -> client into empty world [DONE] NMT_Welcome -> client NMT_Join
  M4  Replicate PC/pawn -> you can move   [IN PROGRESS] capture-faithful PC open + world drip-feed
        on NMT_Join; rotation codec pinned; live ownership still needs client validation

Run:  python server.py 7871
Point a WW3 client here via the M2 matchmaking handoff (hub returns 127.0.0.1:7871 + a
lobbyToken minted with the same secret -- see lobby_token.py / mockserver/hub_server.py).

NOTE: M1 + the control-channel codec are validated byte-for-byte against the real capture.
The state machine's live behavior (reliable resend, exact NMT_Welcome map path / game name,
initial sequence values) needs tuning against a live client -- marked [TUNE] inline.
"""
import socket, sys, time, os, json, threading, hashlib
from stateless_handshake import StatelessHandshake, sequences_from_cookie, MAX_CHSEQUENCE
import control_channel as cc
from lobby_token import validate as validate_token, decode as decode_token
from netguid import GuidWriter
from actor_channel import (write_export_block, write_new_actor, write_content_block,
                           write_subobject_content_block, write_rep_properties)
from ps_identity import (patch_ps_steam, steam_from_login_bits, name_from_login_url,
                         find_ascii_in_bits, CAPTURE_PS_STEAM)
from ps_rebind import (payload_has_loaded_world_marker, payload_has_gameplay_dom,
                       payload_has_spawn_level_visibility,
                       extract_map_path_strings, bunch_payload_bits,
                       build_pc_rep_layout_bunch_bits, rebind_src_indices,
                       sanitize_rebind_spec)
import action_replicator
import inventory_sync
from possess_rpc import (build_char_health_bits, build_ps_playing_state_bits,
                         build_client_restart_bits, build_client_retry_restart_bits,
                         build_pawn_bind_props_bits, build_pc_set_pawn_bits,
                         build_pc_set_playerstate_bits,
                         build_ps_set_playerchar_bits, PC_NETGUID,
                         PC_REP_HANDLE_PLAYERSTATE,
                       is_ack_possession_null, is_ack_possession_pawn,
                         is_check_possession, parse_actor_rpc_fields,
                         build_zero_arg_rpc_bits, build_raw_rpc_bits,
                         build_object_param_bits,
                         build_before_spectator_param_bits,
                         build_stop_spectator_before_deploy_param_bits,
                         build_character_respawn_success_param_bits,
                         build_gamestate_inprogress_bits,
                         _bits_from_writer,
                         restart_handles, retry_handles,
                         RPC_CLIENT_RETRY_RESTART, pc_pawn_handle,
                         ps_playerchar_handle,
                         PAWN_NETGUID, PS_NETGUID, restart_pawn_guid,
                         restart_calibration_pawn_guid,
                         handle_value_max, handle_bits, forced_handle_bits,
                         rpc_send_bit)
from cam_im_resend import (
    build_cam_im_resend_bits,
    build_cam_strip_resend_bits,
    build_wam_attach_export_bits,
    build_wam_attach_spawn_bits,
    build_wam_resend_bits,
    build_wam_strip_resend_bits,
    cam_im_ack_timeout_s,
    cam_im_after_ack_enabled,
    cam_strip_catalog_enabled,
    clothing_resend_enabled,
    clothing_resend_specs,
    CAM_NETGUID,
    IM_NETGUID,
    inv_attach_enabled,
    maybe_strip_wam_in_weapon_open_bits,
    build_wam_post_stub_4606_resend_bits,
    maybe_stub_softclass_4606_in_weapon_open_bits,
    WAM_CHANNELS,
    WAM_OPEN_FINAL_SRCS,
    WAM_PRIMARY,
    WAM_SECONDARY,
    WAM_STRIP_NETGUIDS,
    wam_keep_clothing_enabled,
    wam_keep_dynamic_enabled,
    collect_wam_softclass_export_specs,
    collect_wam_softclass_warm_export_specs,
    collect_wam_spawn_specs,
    wam_open_strip_srcs,
    wam_post_stub_4606_target_netguids,
    wam_softclass_catalog_enabled,
    wam_softclass_export_enabled,
    wam_softclass_warm_export_enabled,
    wam_softclass_stub_4606_enabled,
    wam_softclass_post_stub_4606_enabled,
    wam_softclass_post_stub_delay_ms,
    wam_softclass_post_stub_mode,
    wam_softclass_post_stub_wait_file,
    wam_softclass_mode,
    wam_softclass_keep_skins,
    wam_softclass_open_only,
    wam_early_empty_parts_reinforce_enabled,
    build_wam_early_empty_parts_resend_bits,
    WAM_EARLY_CH4,
    WAM_EARLY_CH5,
    wam_spawn_attach_enabled,
    wam_spawn_content_enabled,
    wam_spawn_export_enabled,
    wam_spawn_host_ch,
    wam_spawn_host_is_shared,
    wam_spawn_payload_mode,
    wam_spawn_specs_for,
    wam_spawn_strip_keep_enabled,
    wam_spawn_target_netguids,
    wam_strip_catalog_enabled,
    wam_strip_target_netguids,
    wpn_attach_enabled,
)

# Live-session packet log: every datagram in/out, hex + timestamp, for post-test analysis.
# This is the whole point of a live-client run -- capture what the REAL client does with us.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_log")

# ---------------------------------------------------------------------------------
# M4 OBSERVABILITY -- WW3_ACK_AUDIT
#
# We have never checked the client's ACK list. UE4 acks at the PACKET layer in
# UNetConnection::ReceivedPacket, but it deliberately SKIPS the ack when a channel's
# UChannel::ReceivedNextBunch returns bOutSkipAck (the partial-bunch reassembly paths
# that refuse a bunch without erroring the connection). So:
#
#   pawn-open packet ACKED     -> the datagram reached the channel layer intact; the
#                                 pawn is being rejected LATER (SerializeNewActor /
#                                 archetype / queued-bunch), i.e. above the wire.
#   pawn-open packet NOT ACKED -> the client threw the bunch away during reassembly,
#                                 which is a framing problem after all, and one that
#                                 bit-comparing against the pcap cannot see because it
#                                 depends on the client's live per-channel partial state.
#
# On loopback there is no real packet loss, so a missing ack is signal, not noise.
# Zero wire change: this only reads acks we already receive and never resends anything.
# ---------------------------------------------------------------------------------
ACK_AUDIT = os.environ.get("WW3_ACK_AUDIT", "0") == "1"
ACK_AUDIT_VERDICT_S = float(os.environ.get("WW3_ACK_AUDIT_VERDICT_S", "3.0"))

# Every experiment knob is an env var read from the LAUNCHER's environment, but the
# launcher prints its banner to its own PowerShell host while the server's stdout goes to
# match_console_<ts>.out.txt. Session 20260805_193023 was analysed for a missing
# ClientRestart with no way to tell from the console that the launch had set
# WW3_CLIENT_RESTART=0. The server now states its own flags in its own log.
POSSESSION_FLAGS = (
    ("WW3_BOOTSTRAP", "capture"),
    ("WW3_PAWN_EXPORT_PREFIX", "0"),
    ("WW3_CLIENT_RESTART", "1"),
    ("WW3_CLIENT_STOP_SPECTATOR_BEFORE_DEPLOY", "0"),
    ("WW3_CLIENT_STOP_SPECTATOR", "0"),
    ("WW3_CLIENT_SHOW_INFANTRY_WIDGET", "0"),
    ("WW3_FORCE_GAMESTATE_INPROGRESS", "0"),
    ("WW3_CHARACTER_RESPAWN_SUCCESS", "0"),
    ("WW3_POST_SPECTATOR_ONLINE_SESSION", "0"),
    ("WW3_DEPLOY_ON_PRELOAD", "0"),
    ("WW3_FINAL_VIEW_TARGET_ONLY", "0"),
    ("WW3_REPLAY_GAMESTATE_TAIL_AFTER_SPECTATOR", "0"),
    ("WW3_STRICT_PLAYER_IN_GAME_ORDER", "0"),
    ("WW3_PROFILE_PROLOGUE", "0"),
    ("WW3_PROFILE_PROLOGUE_DELAY_S", "2.0"),
    ("WW3_PROFILE_PROLOGUE_MODE", "min"),
    ("WW3_PROFILE_PROLOGUE_STEP_S", "0.200"),
    ("WW3_PS_MASTER_LINK", "0"),
    ("WW3_PS_LOCK_VEHICLE_REPLY", "0"),
    ("WW3_TEAM_ACTION_REPLICATOR", "0"),
    ("WW3_TEAM_ACTION_REPLICATOR_DELAY_S", "2.0"),
    ("WW3_ACTION_PROBE", "0"),
    ("WW3_ACTION_PROBE_DELAY_S", "2.0"),
    ("WW3_ACTION_PROBE_LIVENESS_S", "2.0"),
    ("WW3_TEAM_SYNC_BIND", "0"),
    ("WW3_TEAM_SYNC_BIND_DELAY_S", "3.0"),
    ("WW3_TEAM_SYNC_BIND_LIVENESS_S", "2.0"),
    ("WW3_TEAM_SYNC_BIND_NET_ID", "811019"),
    ("WW3_TEAM_SYNC_BIND_UNIQUE_ID", "1"),
    ("WW3_TEAM_SYNC_BIND_NAME", ""),
    ("WW3_TEAM_SYNC_BIND_REQUIRE_PROBE_ACK", "0"),
    ("WW3_ACTION_REPLICATOR_ALLOW_DOUBLE_OPEN", "0"),
    ("WW3_DEPLOY_RELEASE", "0"),
    ("WW3_DEPLOY_RELEASE_DELAY_S", "3.0"),
    ("WW3_DEPLOY_RELEASE_LIVENESS_S", "2.0"),
    ("WW3_DEPLOY_AFTER_SPECTATOR", "0"),
    ("WW3_DEPLOY_AFTER_SPECTATOR_DELAY_S", "0.0"),
    ("WW3_DEPLOY_REPEAT_AFTER_SPECTATOR", "0"),
    ("WW3_DEPLOY_REPEAT_AFTER_SPECTATOR_DELAY_S", "0.0"),
    ("WW3_INV_SYNC_BIND", "0"),
    ("WW3_INV_SYNC_BIND_DELAY_S", "6.0"),
    ("WW3_INV_SYNC_BIND_LIVENESS_S", "2.0"),
    ("WW3_INV_SYNC_BIND_MODE", "weapons"),
    ("WW3_INV_SYNC_BIND_PRIMARY", "9410"),
    ("WW3_INV_SYNC_BIND_SECONDARY", "9412"),
    ("WW3_WORLD_FILL", "0"),
    # Turn 10: the capture's deploy-screen block (src 1637..1856), which our
    # replay skipped entirely.  DEPLOY_SCREEN_CHAIN replays the spectator view
    # target + five Client_UpdateSpectatePoint; DEPLOY_STATUS_BEFORE_TRANSITION
    # puts Client_OnCapturePointRespawnRequestStatusChanged (src 1856) back in
    # front of source 1934, which is where the capture has it.
    ("WW3_DEPLOY_SCREEN_CHAIN", "0"),
    ("WW3_DEPLOY_STATUS_BEFORE_TRANSITION", "0"),
    ("WW3_DEPLOY_ANSWER_H287", "1"),
    # Turn 10: replay the two capture-point actor channels (83/84) the capture
    # opens at pkt 370 and our world stream never did.  Re-extracted from the raw
    # pcap because the sanitiser left only a dangling partial-initial of each.
    ("WW3_DEPLOY_MARK_DEAD", "0"),
    ("WW3_DEPLOY_DEAD_HEALTH", "0"),
    ("WW3_DEPLOY_PLAYING_STATE", ""),
    ("WW3_DEPLOY_REVIVE_ON_ANSWER", "1"),
    ("WW3_DEPLOY_REVIVE_HEALTH", "100"),
    ("WW3_SPECTATE_POINT_REPLY", "1"),
    ("WW3_SPECTATE_POINT_REPLY_MAX", "12"),
    ("WW3_CP_EXPORT_REPLAY", "0"),
    ("WW3_CAPTUREPOINT_REPLAY", "0"),
    ("WW3_CAPTUREPOINT_LIMIT", "40"),
    ("WW3_CLIENT_RESTART_MUSTMAP", "0"),
    ("WW3_CLIENT_RESTART_SEND_RETRY", "0"),
    ("WW3_CLIENT_RESTART_MAX_SPRAYS", "4"),
    ("WW3_CLIENT_RESTART_AFTER_PAWN_MS", "0"),
    ("WW3_CLIENT_RESTART_REQUIRE_CH3_ACK", "0"),
    ("WW3_CLIENT_RESTART_GATE_TIMEOUT_S", "20"),
    ("WW3_CLIENT_RESTART_MBM_FALLBACK_S", "0"),
    ("WW3_RESTART_CALIBRATE", ""),
    ("WW3_CLIENT_RESTART_PAWN_GUID", ""),
    ("WW3_PC_SET_PAWN", "0"),
    ("WW3_PAWN_SYNTH_PROPS", "0"),
    ("WW3_PAWN_SYNTH_IN_OPEN", "0"),
    ("WW3_PS_SET_PLAYERCHAR", "0"),
    ("WW3_INV_ATTACH", "0"),
    ("WW3_CAM_IM_AFTER_ACK", "0"),
    ("WW3_CAM_IM_ACK_TIMEOUT_S", "3.0"),
    ("WW3_WPN_ATTACH", "0"),
    ("WW3_CLOTHING_RESEND", "0"),
    ("WW3_CAM_STRIP_CATALOG", "0"),
    ("WW3_WAM_STRIP_CATALOG", "0"),
    ("WW3_WAM_STRIP_CHANNELS", "all"),
    ("WW3_WAM_KEEP_DYNAMIC", "0"),
    ("WW3_WAM_KEEP_CLOTHING", "0"),
    ("WW3_WAM_SOFTCLASS_CATALOG", "0"),
    ("WW3_WAM_SOFTCLASS_EXPORT", "1"),
    ("WW3_WAM_SOFTCLASS_WARM_EXPORT", "0"),
    ("WW3_WAM_SOFTCLASS_STUB_4606", "0"),
    ("WW3_WAM_SOFTCLASS_POST_STUB_4606", "0"),
    ("WW3_WAM_SOFTCLASS_POST_STUB_DELAY_MS", "2500"),
    ("WW3_WAM_SOFTCLASS_POST_STUB_WAIT_FILE", ""),
    ("WW3_WAM_SOFTCLASS_POST_STUB_MODE", "stub"),
    ("WW3_WAM_SOFTCLASS_MODE", "mag"),
    ("WW3_WAM_SOFTCLASS_OPEN_ONLY", "0"),
    ("WW3_WAM_SOFTCLASS_KEEP_SKINS", "0"),
    ("WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE", "0"),
    ("WW3_ISOLATE_EARLY_WPN", "1"),
    ("WW3_WAM_SPAWN_ATTACH", "0"),
    ("WW3_WAM_SPAWN_CHANNELS", "all"),
    ("WW3_WAM_SPAWN_HOST", "weapon"),
    ("WW3_WAM_SPAWN_ATT_LIMIT", ""),
    ("WW3_WAM_SPAWN_STRIP_KEEP", "1"),
    ("WW3_WAM_SPAWN_EXPORT", "1"),
    ("WW3_WAM_SPAWN_CONTENT", "1"),
    ("WW3_WAM_SPAWN_PAYLOAD", "min"),
    ("WW3_WAM_SPAWN_CHECKSUM", ""),
    ("WW3_WAM_SPAWN_USE_HAT_CLASS", "0"),
    ("WW3_PAWN_SET_OWNER", "0"),
    ("WW3_PS_REBIND", "1"),
    ("WW3_PAWN_NO_SCALE", "0"),
    ("WW3_STRIP_EXPORT_CHECKSUM", "0"),
    ("WW3_ACK_AUDIT", "0"),
    ("WW3_AMBIENT_LIMIT", "120"),
    ("WW3_AMBIENT_START", "18"),
    ("WW3_AMBIENT_CHANNELS", "7,53"),
    ("WW3_AMBIENT_PREREQS", ""),
)


def print_flag_banner():
    """Log the resolved possession flags (env value or built-in default) at startup."""
    print("[match] === possession flags (value <- env, or default) ===")
    for name, default in POSSESSION_FLAGS:
        raw = os.environ.get(name)
        src = "env" if raw is not None else "default"
        print(f"[match]     {name}={raw if raw is not None else default} ({src})")
    other = sorted(k for k, _ in os.environ.items()
                   if k.startswith("WW3_") and k not in {n for n, _ in POSSESSION_FLAGS})
    if other:
        print("[match]     other WW3_*: "
              + " ".join(f"{k}={os.environ[k]}" for k in other))
    print(f"[match]     restart_handles={restart_handles()} retry_handles={retry_handles()} "
          f"pc_pawn_handle={pc_pawn_handle()} ps_playerchar_handle={ps_playerchar_handle()}")
    # RPC field framing. Until 2026-08-07 the handle was written at a fixed 8 bits, which
    # is correct for every handle >= 59 (i.e. everything the client sends) but one bit
    # short for ClientRestart's 39 -- the client then read NumPayloadBits=72 out of a
    # 32-bit block and SetOverflowed before ClientRestart_Implementation could run.
    _rh = restart_handles()[0] if restart_handles() else 39
    print(f"[match]     rpc framing: handle_value_max={handle_value_max()} "
          f"(handle {_rh} -> {handle_bits(_rh)} bits, forced={forced_handle_bits()}) "
          f"send_bit={rpc_send_bit()}")
    # Owner / RemoteRole re-encode is intentionally unimplemented: the capture-faithful
    # pawn open has no actor RepLayout in the open bunch (M4 fact #2), and BP_PlayerPawn
    # FRepLayout handles for Owner/RemoteRole are unknown (ClassNetCache 6/7 are a
    # different index space). Guessing would CHANNEL CLOSE like WW3_PS_REBIND did.
    if os.environ.get("WW3_PAWN_SET_OWNER", "0") == "1":
        print("[match]     *** WW3_PAWN_SET_OWNER=1 ignored: pawn Owner/RemoteRole "
              "RepLayout handles unknown — refuse to guess (see README M4 #3) ***")

class PacketLog:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        self.path = os.path.join(LOG_DIR, time.strftime("session_%Y%m%d_%H%M%S.jsonl"))
        self.f = open(self.path, "a", buffering=1)
        self.t0 = time.time()
        print(f"[match] logging packets -> {self.path}")
    def write(self, direction, addr, data):
        self.f.write(json.dumps({"t": round(time.time()-self.t0, 6), "dir": direction,
                                 "peer": f"{addr[0]}:{addr[1]}", "len": len(data),
                                 "hex": data.hex()}) + "\n")
        # Keep live sessions inspectable while the client is stuck in LoadingMap.
        # The previous buffered writer left the session file at zero bytes until
        # process exit, which hid the current transition evidence.
        self.f.flush()

# Real NMT_Welcome field values, read off the wire (captures/24July26). The map's internal
# folder is "Dunhuang" (Gobi). gameMode 47 = Domination-Newbie (a Blueprint game mode).
MAP_PACKAGE_PATH = {  # short map name -> full LevelName package path (READ OFF THE WIRE)
    "WW3_Gobi_New_P": "/Game/Maps/Main/Dunhuang_v3/WW3_Gobi_New_P",   # Gobi = "Dunhuang_v3"
    "WW3_Warsaw_P":   "/Game/Maps/Main/Warsaw/WW3_Warsaw_P",
    "WW3_Tokio_P":    "/Game/Maps/Main/Tokio/WW3_Tokio_P",
    "WW3_DMZ_P":      "/Game/Maps/Main/DMZ/WW3_DMZ_P",
    "WW3_Polarnyj_P": "/Game/Maps/Main/Polarnyj/WW3_Polarnyj_P",
    "WW3_Berlin_P":   "/Game/Maps/Main/Berlin/WW3_Berlin_P",
    "WW3_Moscow_P":   "/Game/Maps/Main/Moscow/WW3_Moscow_P",
    # TDM maps live under a DIFFERENT ROOT (/Game/Maps/TDM/, not /Game/Maps/Main/) and the
    # folder casing does not follow the map name ("Warsaw_Shopping_mall" vs ..._Mall_P).
    # None of this is inferable -- each TDM map needs its own capture.
    "WW3_Warsaw_Shopping_Mall_P":
        "/Game/Maps/TDM/Warsaw_Shopping_mall/WW3_Warsaw_Shopping_Mall_P",
    "WW3_Shibuya_P":                                   # folder is "Tokyo_Streets" (!)
        "/Game/Maps/TDM/Tokyo_Streets/WW3_Shibuya_P",
    "WW3_Berlin_Backyards_02_P":
        "/Game/Maps/TDM/Berlin_Backyards_02/WW3_Berlin_Backyards_02_P",
    # VERIFIED from captures/3Aug27/war_smolensk.pcapng (UDP 7869 Welcome path):
    "WW3_Smolensk_P": "/Game/Maps/Main/Smolensk/WW3_Smolensk_P",
}
# M3 spawn: the PlayerController class per game mode (read off the wire) and the NetGUIDs /
# location we mirror from the real server's first replication bunch.
PLAYER_CONTROLLER = {   # gameMode alias -> (package, archetype) -- all READ OFF THE WIRE
    47: ("/Game/Blueprints/Player/Controllers/BP_WW3_DominationPlayerController_01",
         "Default__BP_WW3_DominationPlayerController_01_C"),          # DOM_N
     2: ("/Game/Blueprints/Player/Controllers/BP_WW3_DominationPlayerController_01",
         "Default__BP_WW3_DominationPlayerController_01_C"),          # WAR_M
    10: ("/Game/Blueprints/Player/Controllers/BP_WW3TeamDeathmatchPlayerController_01",
         "Default__BP_WW3TeamDeathmatchPlayerController_01_C"),       # TDM_M (26 Jul)
}
# Supporting classes per mode, from the NetGUID exports (needed once we replicate a world).
MODE_CLASSES = {
    10: {"hud":        "/Game/Blueprints/HUD/BP_WW3TeamDeathmatchHUD",
         "gameState":  "/Game/Blueprints/GameState/BP_WW3TeamDeathmatchGameState",
         "playerState":"/Game/Blueprints/Player/BP_WW3TeamDeathmatchPlayerState",
         "pawn":       "/Game/Blueprints/Player/BP_PlayerPawn_01"},
}
ACTOR_NETGUID  = 9360                      # even = dynamic (runtime-spawned)
SPAWN_LOCATION = (-1787.0, -10060.0, -562.5)
SPAWN_ROTATION = (1.40625, 90.0, 0.0)       # degrees; capture uses 3x SerializeInt(512)
PS_RPC_HANDLE_VALUE_MAX = 82               # AWW3DominationPlayerState ClassNetCache bound
PS_RPC_PLAYER_IN_GAME_NOTIFY = 65           # C->S, zero params
PS_REJOIN_REPLY_SOURCE = 1056               # S->C Client_RejoinIsPossible(bool)
# `_decode_all_blocks.py --ch 7` over the whole capture: the local PlayerState gets
# exactly two property updates before the client reports h281/h65, and our bootstrap
# sends neither.  Both are UNRELIABLE in the capture; build_replay_bunch honours that.
#   src 372  h54 bIsConnectedToMaster = true  -- lands right after the client's first
#            C->S h279, and is the only thing that ever tells the local PlayerState it
#            is linked to the master server.
#   src 888  h40 LockVehicleMode = 3          -- the capture's answer to C->S PS h71
#            Server_SetLockVehicleMode, which we currently only use as a timing anchor.
PS_MASTER_LINK_SOURCE = 372
PS_MASTER_LINK_BITS = 112
PS_MASTER_LINK_SHA256 = "876504b14b1674d3a6c99b152142f034902ada284faef1e90afcc21c95e20d36"
PS_LOCK_VEHICLE_REPLY_SOURCE = 888
PS_LOCK_VEHICLE_REPLY_BITS = 29
PS_LOCK_VEHICLE_REPLY_SHA256 = "a0bba55366492c6a8a77b005353e9de4184f0d91d1e16507c7506088232e795d"
# Capture-grounded sequence immediately following PS::Server_PlayerInGameNotify.
# Delays are relative to source1056 / Client_RejoinIsPossible, measured in
# captures/24July26/W3_match_full_2.pcapng.  Hashing the complete bit strings makes
# this opt-in experiment fail closed if real_replay_stream.json is regenerated.
STRICT_H71_TO_H65_FALLBACK_S = 0.564
STRICT_PROFILE_SYNC_SPECS = (
    # source, delay_s, bits, sha256(payload bit string)
    (1063, 0.033, 4188, "dcbfd301bcdb2be14c83453fd357efbd986b82ff0705e936aacd733db9b9f839"),
    (1097, 0.199, 4188, "3829699672d1cbb9ac166c8e07143383e73cc1561f8acefa6aabcde5feaca9f9"),
    (1127, 0.366, 4188, "b670680c291128d80092dcced1c2657c7077f09c65b0e219afe003cb27eaeb79"),
    (1133, 0.400, 262, "1c9c07aee8515db25b46dd5a993e5b8d1d7a152b1b68d7f437759e844849cf10"),
    (1158, 0.534, 2446, "ffcdfe58da6a2e86e735c36f90e4b0996ea031956dc24f70b9a435dea1981499"),
    (1166, 0.567, 92, "1a5348178d9b889ea2742165914020d7e5bc208f66e4bcda293b167da7f87c98"),
    (1191, 0.700, 4188, "445288bc97a75a23b434d574b4e4bea08ee5d21e9906849cf6e95e6fb95a5b6d"),
    (1222, 0.867, 4188, "43875d03080931d7f569f001c09d5f70f2514f8b79c03e521bb64a05f7c41172"),
    (1251, 1.039, 4188, "d4323471af89e44337659f2f9fc6d9aacf52cfd33d539b2f2b060eb83846ea47"),
    (1285, 1.202, 4188, "91e8692cba8d104fe5fb1eb7bfa8a253f684d6dd76469d1e7a286cd4aaaf5a73"),
    (1318, 1.368, 4188, "e68cec572be753b54feda6c60969de9c8093bedc304a0a06f8b17f58a61ef824"),
    (1348, 1.535, 4188, "245e40f9ab05bfa68d47d9c9627a18f659db7a461e65126ec6b9cc7baa0cc949"),
    (1385, 1.702, 2590, "28e6d05a8489b2ef35e18182cf45eabc0e6d80cd76b878ee61db11efebd38853"),
)
STRICT_PROFILE_SYNC_SOURCES = tuple(spec[0] for spec in STRICT_PROFILE_SYNC_SPECS)
# The capture opens profile replication ~0.35 s after the spawn burst and *before*
# the client reports Server_OnMapOpened / Server_PlayerInGameNotify, so this is a
# prerequisite of h65 rather than a consequence of it.  Our bootstrap skipped the
# whole conversation: src 8 is the only one of its 51 bunches carrying an RPC.
# These two are the self-contained captured bunches that start it; the client
# answers the second with C->S h177 Server_ClientReceivedServerStartDate.
PC_RPC_CLIENT_RECEIVED_SERVER_START_DATE = 177
# AWW3GamePlayerController::Server_OnMapOpened -- the client's own report that
# its deploy/spawn screen is up.  Handle from `derive_net_handles.py`
# (WW3GamePlayerController FieldsBase=217), the model that scores 8/8 on the
# wire anchors.
PC_RPC_ON_MAP_OPENED = 281
# AWW3GamePlayerController::Server_RequestRespawnAtCapturePoint -- the DEPLOY
# button.  In the capture this is src~1841 and the server answers it with the
# transition bundle at src 1934.
PC_RPC_REQUEST_RESPAWN_AT_CAPTURE_POINT = 287
# AWW3GamePlayerController::Server_StartSpectator -- the client's own report that
# it has entered the deploy spectator camera.  In the capture it rides with h208
# `Server_SetProfileMainEquipmentLoadoutIndex` at src~1626, and every server
# answer to the deploy sequence (h50/h273, then source 1934) comes *after* it.
PC_RPC_START_SPECTATOR = 310
# AWW3GamePlayerController::Client_OnCapturePointRespawnRequestStatusChanged --
# the server's answer to h287, 78 ms before the transition bundle.  Turn 10 found
# our server skips it: we replay the strict profile chain up to src 1385 and then
# jump straight to src 1934, so the whole deploy-screen block (1637..1856) is
# missing.  That matches what the live client shows -- `SvRespawnRequest` and
# `ClObjectResponsibleForRespawn` both NULL, an empty spawn list and a DEPLOY
# button reading NOT READY -- so `Client_OnStopSpectatorBeforeDeploy` inside 1934
# arrives with no pending request to deploy onto and the client stays spectating.
PC_RPC_CAPTURE_POINT_RESPAWN_STATUS = 231
# AWW3GamePlayerController::Server_SpectatorAttachToCapturePoint -- the client
# selecting a spawn point on the deploy screen.  Confirmed on four independent
# clean captures (24July StrongHold/DMZ/full_3, 3Aug war_smolensk): the client
# streams this per tick (~30 ms, incrementing ChSequence, value may change
# mid-burst) and the server answers each one STRICTLY 1:1 with
# `ClientSetViewTarget` + `Client_UpdateSpectatePoint` echoing the same capture
# point.  Only after that does the client send h287, and h287 targets the capture
# point's "First Spawn Zone" CHILD object, not the actor itself.
PC_RPC_SPECTATOR_ATTACH_CAPTURE_POINT = 305
# AWW3GamePlayerController::Client_UpdateSpectatePoint -- that 1:1 answer.  The
# capture's own copies are the 47-bit bunches at sources 1640/1641/1650/1651/1657
# (all byte-identical), already validated in DEPLOY_SPECTATE_SPECS.
PC_RPC_CLIENT_UPDATE_SPECTATE_POINT = 273
# The capture's deploy-screen block, replayed verbatim.  Source 1639 is the
# bPartial/bPartialFinal half of 1637's ClientSetViewTarget and is deliberately
# excluded: `_load_validated_capture_specs` requires whole bunches.
DEPLOY_SPECTATE_SPECS = (
    # source, delay_s, bits, sha256(payload bit string)
    (1637, 0.000, 113, "a28f10fd72cbfd344fdf53f436c97866504cd6f3dd902f4bcbcd6c3593f4e008"),
    (1640, 0.050, 47, "b93d521344a7797a066934ef26bc2caed0f04e88c0d583289d9de13723173475"),
    (1641, 0.100, 47, "b93d521344a7797a066934ef26bc2caed0f04e88c0d583289d9de13723173475"),
    (1650, 0.150, 47, "b93d521344a7797a066934ef26bc2caed0f04e88c0d583289d9de13723173475"),
    (1651, 0.200, 47, "b93d521344a7797a066934ef26bc2caed0f04e88c0d583289d9de13723173475"),
    (1657, 0.250, 47, "b93d521344a7797a066934ef26bc2caed0f04e88c0d583289d9de13723173475"),
)
DEPLOY_RESPAWN_STATUS_SPECS = (
    (1856, 0.000, 31, "d49e158622a197bd40cf5e32f9cdaf462e24e020e7ddb248060630850639f03f"),
)
STRICT_PROFILE_PROLOGUE_SPECS = (
    # source, delay_s, bits, sha256(payload bit string)
    (204, 0.000, 26, "5d85eab8fb7658f9d0f3345a07fefec87bca68b85cd916ecccbf623270c7b472"),
    (321, 0.200, 91, "06c6631a8f1a7f6dd7c2b4b89dd72723a2038b5b25a0eb9f3e1b7e9db6fbf71c"),
)
STRICT_PROFILE_PROLOGUE_SOURCES = tuple(spec[0] for spec in STRICT_PROFILE_PROLOGUE_SPECS)
# `min` above only *opens* the list.  Between the capture client's first
# Server_OnClientPreloadWeaponsFinished (C->S h279, src~354) and its
# Server_OnMapOpened + PS Server_PlayerInGameNotify (src~1050) the working server
# sends nothing else at all -- 33 ch2 bunches, all profile conversation:
# h111 clear, 20x h140 pages, two h110 finishes, h132/h133/h137/h146.
# Regenerate with `_gen_profile_prologue_specs.py`.  The delays below are a
# uniform WW3_PROFILE_PROLOGUE_STEP_S grid, not capture deltas: the capture's
# ~30 s spacing is the live server's profile-broadcast cadence with real players
# joining, not a protocol requirement.
STRICT_PROFILE_PROLOGUE_FULL_SPECS = (
    # source, delay_s, bits, sha256(payload bit string)
    (204, 0.000, 26, "5d85eab8fb7658f9d0f3345a07fefec87bca68b85cd916ecccbf623270c7b472"),
    (211, 0.200, 4371, "af502ed46f397c1c291f8e72bf32ffc4784acc6e37e3d1a557a88faf06da6ef2"),
    (310, 0.400, 4188, "2d206e702bc7a32f07652d987555651b6ab1c56397f61752f778a3ec1129dd56"),
    (321, 0.600, 91, "06c6631a8f1a7f6dd7c2b4b89dd72723a2038b5b25a0eb9f3e1b7e9db6fbf71c"),
    (381, 0.800, 4188, "305a9e96563944a3185b991b1f7756565af54a26a0fe51fbd8f9734c97a217ff"),
    (415, 1.000, 29, "fb99e04729ae78a3f4a71c44017134d7332ca56ccc5a6e0a350e197898c40ae3"),
    (434, 1.200, 4188, "07a49238eaa0b7929d60334afb29e97220cfddef814160c60204cd8285c2d872"),
    (471, 1.400, 44, "79217410ff2aca46ba4053dab9b00369dd0795ccdda9a552048ff7b3d7b97956"),
    (480, 1.600, 4188, "aeb578448b5a424ae114449b48cad1f91c2935f3804fcb48c9dee4b4f17346e1"),
    (522, 1.800, 4188, "71293ccdfb47a1e5d8126e5178392f53e15faca81e3edb442240ea33d394fddc"),
    (569, 2.000, 2390, "516e0056e02cdac8fe829212edc5888d3a12001fad3111d7642724143a8f74aa"),
    (578, 2.200, 92, "8283d9d1b6a7be3ad8fbf8472a6768b5a842bc0d8aad4642ada5d5766ba30144"),
    (614, 2.400, 4188, "990f7bb524717ee0b8d5ca471858704d6e0c1cc52832bbbbf832648a81e21d13"),
    (657, 2.600, 4188, "a0d8400d67547d04d912325044aeacb6f9ba7404d72f1bf830ddaea77b64b779"),
    (683, 2.800, 27, "8316d3fa82bfe86b14e775c0fa216fe105f9b1c3c41e5edc87dc276df082dd4e"),
    (699, 3.000, 4188, "c52dcd770c82b2b40c2b6edac5b42873d9a05ba57c2e34c6a431387be42b061c"),
    (731, 3.200, 44, "5c7ed4b8e13c0d4a67c6bead8805043a4d2fb09a822a6edeaa5d0f669a2f8412"),
    (739, 3.400, 4188, "e90ddb150bccc67a0949de2aeb7b495b103bd0ac5fae0c406b65a5fe6a16b077"),
    (776, 3.600, 4188, "74973db83d44b5a92031e72ca0e91bbc09319db3b7cb51c2b9158df01bbf5d28"),
    (818, 3.800, 4188, "73b36d8d2dd08d3605f82d49d556d96b32ad9b85bf620ec4b1ed845cd48b6447"),
    (858, 4.000, 2598, "2eaa9eb3a257a735a8709e5c3f195fd2b2e719b5d2dec5fb4f5cc81204e0e072"),
    (868, 4.200, 92, "9b8d1a9a389b4b52eb4d36f45c556a578c577b1d6246a2c16a0bb2216d3d6329"),
    (878, 4.400, 4188, "2d206e702bc7a32f07652d987555651b6ab1c56397f61752f778a3ec1129dd56"),
    (879, 4.600, 91, "06c6631a8f1a7f6dd7c2b4b89dd72723a2038b5b25a0eb9f3e1b7e9db6fbf71c"),
    (880, 4.800, 92, "8283d9d1b6a7be3ad8fbf8472a6768b5a842bc0d8aad4642ada5d5766ba30144"),
    (881, 5.000, 4188, "990f7bb524717ee0b8d5ca471858704d6e0c1cc52832bbbbf832648a81e21d13"),
    (882, 5.200, 4188, "a0d8400d67547d04d912325044aeacb6f9ba7404d72f1bf830ddaea77b64b779"),
    (907, 5.400, 4188, "ddee208f2cff8150459d9aeacf4bdce2eae3ea5c7f91a10da19d723c7e875367"),
    (915, 5.600, 4188, "74973db83d44b5a92031e72ca0e91bbc09319db3b7cb51c2b9158df01bbf5d28"),
    (916, 5.800, 4188, "73b36d8d2dd08d3605f82d49d556d96b32ad9b85bf620ec4b1ed845cd48b6447"),
    (959, 6.000, 4188, "276cba00d0febd015ab4f4e3f90fbc07f851003894c678267f955db4c6cd031d"),
    (1022, 6.200, 44, "d819ec79c0ee643c42bccf85f08ef50d26fd7ba4bf5129f05f9d2f509477fce8"),
    (1031, 6.400, 4188, "36bbf51bdc2c43c34b235945c3e19222584fc0b91eac8786972f9e7fa12100bd"),
)
STRICT_PROFILE_PROLOGUE_FULL_SOURCES = tuple(
    spec[0] for spec in STRICT_PROFILE_PROLOGUE_FULL_SPECS)
# ch80 AWW3ActionReplicator — the actor that carries the team/squad graph.
#
# The client's "Client Synchronization" checklist is a single bitmask byte
# (FSync+0x48; bit1 = PlayerState), and disassembly of WW3-Win64-Shipping.exe
# shows the PlayerState bit is set by exactly one predicate:
#
#     if (IsValid(Character->GetPlayerState()->[0x710])) MarkSynchronized(0x02)
#     else                                               [0x5a0].Add(retry callback)
#
# and the Dumper-7 SDK names 0x710 `UWW3SquadObject* AWW3PlayerState::CurrentSquad`.
# `UWW3SquadObject` has no Net properties at all — the client builds the
# Team -> Squad -> Slot -> PlayerState graph locally from `UWW3ReplicatedAction_TM_*`
# objects delivered by an `AWW3ActionReplicator`.  The working capture opens
# exactly one, and our curated bootstrap has never sent it.
#
# See `_ps_sync_predicate.py`, `_exe_field.py` and `_channel_class_map.py`.
TEAM_ACTION_REPLICATOR_CHANNEL = 80
TEAM_ACTION_REPLICATOR_SPECS = (
    # source, bits, sha256(payload bit string)
    (174, 1369, "53d64ba816e00da0d5121417f0daa451eb64eb16c212827ef60bf4e2cf795191"),
    (175, 79, "a0c7f3a9f1ff5aa288b5ddcd92bdf19fe3b634aa66fd1d6f23866a065c7b6be1"),
)
TEAM_ACTION_REPLICATOR_SOURCES = tuple(spec[0] for spec in TEAM_ACTION_REPLICATOR_SPECS)


def bootstrap_opens_action_replicator(specs):
    """True when the queued bootstrap already opens ch80 itself.

    `WW3_WORLD_FILL=1` replays the capture's whole pre-deploy world, and that
    range *contains* src 174/175 -- the same channel, the same NetGUID 9400 and
    the same actor `WW3_TEAM_ACTION_REPLICATOR` sends.  Measured from the
    generator: world fill 0 -> `ch80=0`, world fill 1 -> `ch80=2, src174=True,
    src175=True`.  Opening the channel a second time is the one thing the
    capture never does, and its effect is racy -- turn 8 kept the actor and
    answered the probe in 19 ms, turn 9 ended with zero live
    `WW3.WW3ActionReplicator` instances and no ack at all.
    """
    return any(int(b.get("chIndex", -1)) == TEAM_ACTION_REPLICATOR_CHANNEL
               and int(b.get("bOpen", 0)) == 1
               for b in (specs or ()))

# WW3_ACTION_PROBE: one `Client_ReceivePacket` (ch80 handle 10) carrying a
# well-formed but EMPTY `TM_Synchronize`.  Zero teams means the client's load
# path creates no team/squad/slot objects, so this changes no game state at all —
# it exists only to prove the field header, the `TArray<uint8>` parameter and the
# packet framing.  Its oracle is the client's own unconditional reply,
# `Server_AckActionsReceived` (ch80 handle 12); see `action_replicator.py` for
# where every byte comes from.  Pinned here so a payload edit cannot reach a live
# reliable channel without also being a reviewed change to this constant.
ACTION_PROBE_PACKET_BYTES = 25
ACTION_PROBE_PACKET_SHA256 = (
    "b6d2b409db3eaa14dc3bc956300f989b52ef1f1a296da2ce7d9d7d0cc945203b")

# WW3_TEAM_SYNC_BIND: one `Client_ReceivePacket` carrying a NON-empty
# `TM_Synchronize` -- one team, one squad, one slot already bound to this
# connection's own PlayerState.  Unlike the probe above this changes client
# state: the handler at 0x140969db0 walks the slot, sees `+0x60`, and calls
# 0x1409739b0, which matches `slot->[0x30]`/`[0x34]` against the live
# `AWW3PlayerState`'s `InternalNetId`/`PlayerStateUniqueID` and then calls
# `SetCurrentSquad` (0x1410fb3c0) -- the only thing that can make the checklist's
# `PlayerState` bit true.  Defaults come from `_slot_bind_gates.py` reading the
# running client; the SHA pins the exact bytes so a layout or identity edit
# cannot reach a live reliable channel unreviewed.
TEAM_SYNC_BIND_PACKET_BYTES = action_replicator.LOCAL_BIND_PACKET_BYTES
TEAM_SYNC_BIND_PACKET_SHA256 = action_replicator.LOCAL_BIND_PACKET_SHA256
TEAM_SYNC_BIND_DEFAULT_NET_ID = 811019       # AWW3PlayerState::InternalNetId
TEAM_SYNC_BIND_DEFAULT_UNIQUE_ID = 1         # AWW3PlayerState::PlayerStateUniqueID

# WW3_INV_SYNC_BIND: one ch3 content block for the capture's own InventoryManager
# subobject (9384) carrying `CurrentItemRepInfo` + `SvReplicatedInventory`.
# Both remaining checklist bits are set by 0x1411c0f30, which is bound (measured,
# `_delegate_live.py`) to the multicast delegate at UWW3InventoryManagerBase+0xF0
# and broadcast from exactly two sites, both gated on
# `UWW3InventoryManagerBase::IsSynchronized` (0x140c37770).  On a client that
# predicate needs a non-null `ClientCurrentItem`, `+0x2B9` set by
# `OnRep_ReplicatedInventory`, and a `SvReplicatedInventory` that passes
# `FWW3ReplicatedInventory::IsValid` (0x140ca45d0).  `_inv_sync_gates.py` reads
# all three as unsatisfied on the live client, and `_im_stream_scan.py` shows the
# working server never sent h10..h21 -- so this is a synthesis on capture-grounded
# framing, exactly like TM_Synchronize.  The SHA pins the bytes.
INV_SYNC_PACKET_SHA256 = inventory_sync.INV_SYNC_PACKET_SHA256
INV_SYNC_PACKET_BITS = 231

STRICT_TRANSITION_SOURCE = 1934
STRICT_TRANSITION_BITS = 509
STRICT_TRANSITION_SHA256 = "8bbbcc0c9f5a07d942a6cf802ed7c6a11bbd12ae31509bada62d16c9f9aa9537"
PC_ARCH_CHECKSUM = 0x8a0cc758              # real NetworkChecksum of the PC archetype
PC_SUBOBJECTS = [                          # (NetGUID, name, NetworkChecksum) -- from the capture
    (9364, "AntiCheatComponent",             0xcaaaee3e),
    (9366, "SquadManagerRequester",          0xcaaaee3e),
    (9368, "WorldPositionMarkersManager",    0xc1b2bf4f),
    (9370, "InGameCustomizationDataManager", 0xcaaaee3e),
]

GAMEMODE_CLASS = {   # numeric gameMode -> (GameName class path, RedirectURL short code)
    47: ("/Game/Blueprints/GameModes/BP_DominationNewbie_GameMode_01_01.BP_DominationNewbie_GameMode_01_01_C", "DOM_N"),
     2: ("/Game/Blueprints/GameModes/BP_DominationGameMode_01_01.BP_DominationGameMode_01_01_C", "DOM"),
    10: ("/Game/Blueprints/GameModes/BP_TeamDeathmatchGameMode_02_01.BP_TeamDeathmatchGameMode_02_01_C", "TDM_M"),
}

class Conn:
    def __init__(self):
        self.state = "HANDSHAKING"     # -> CONNECTED -> LOGGED_IN
        self.since = time.time()
        self.out_seq = 0               # our packet sequence  (set from the cookie at handshake)
        self.out_chseq = 0             # control-channel reliable sequence (from the cookie)
        self.init_reliable = 0         # InitOutReliable -- every channel starts here
        self.chan_seq = {}             # chIndex -> current reliable sequence (PER CHANNEL)
        self.in_seq = 0                # the client's expected starting packet sequence
        self.spawned = False           # have we sent the PlayerController spawn?
        self.replay_queue = []         # captured bunches waiting to be drip-fed
        self.replay_total = 0
        self.replay_sent = 0
        self.pawn_sent = False
        self.pending_acks = []         # client packet-ids we still owe an ack for
        self.challenge = None
        self.claims = None
        self.pkt_audit = {}            # WW3_ACK_AUDIT: our packet-id -> {t, tag, acked}
        self.pc_channel = 2             # local PlayerController is opened on UE's ch2

class LoggingSock:
    """Wraps the UDP socket so every outgoing datagram is logged too."""
    def __init__(self, sock, plog): self.sock=sock; self.plog=plog
    def sendto(self, data, addr):
        self.plog.write("S->C", addr, data)
        return self.sock.sendto(data, addr)

class MatchServer:
    def __init__(self, port=7871):
        self.port = port
        self.hs = StatelessHandshake()
        self.conns = {}
        self.start = time.time()
        self.plog = None
        self._udp_reset_count = 0

    def server_time(self):
        return time.time() - self.start

    def keepalive_loop(self, s):
        """The real server sends packets CONTINUOUSLY (~every 200ms), even when idle -- see
        the capture. Our server used to be purely reactive, so while the client was loading
        the map (seconds of client silence) we sent nothing at all, which risks a client-side
        connection timeout. Mirror the real server and keep a trickle going."""
        while True:
            time.sleep(0.2)
            for key, conn in list(self.conns.items()):
                if conn.state in ("HANDSHAKING", "CLOSED"):
                    continue
                try:
                    ip, port = key.rsplit(":", 1)
                    addr = (ip, int(port))
                    if ACK_AUDIT and conn.pkt_audit:
                        self.audit_tick(conn)
                    self.maybe_service_profile_prologue(s, addr, conn)
                    self.maybe_service_team_action_replicator(s, addr, conn)
                    self.maybe_send_action_probe(s, addr, conn)
                    self.maybe_send_team_sync_bind(s, addr, conn)
                    self.maybe_send_inv_sync_bind(s, addr, conn)
                    self.maybe_release_deploy_transition(s, addr, conn)
                    self.maybe_service_strict_player_in_game(s, addr, conn)
                    due_attach = getattr(conn, "_deferred_attachment_release_at", 0)
                    if (due_attach and time.time() >= due_attach
                            and not getattr(conn, "_deferred_attachments_released", False)):
                        self._release_deferred_attachments(conn)
                    if conn.replay_queue:
                        sent = self.drain_replay(s, addr, conn)
                        # During streaming settle, drain returns 0 while the queue is
                        # still non-empty — still send a keepalive or the client hits
                        # UNetConnection's 20s timeout (seen live with 15s pause).
                        if not sent:
                            self.send_packet(s, addr, conn)
                    else:
                        now = time.time()
                        acked = getattr(conn, "_ack_possess_pawn", False)
                        due = getattr(conn, "_delayed_restart_at", 0)
                        if due and now >= due and not acked:
                            # Cleared inside maybe_send_client_restart on success; a gate
                            # that isn't ready yet re-arms it, so this keeps retrying.
                            conn._delayed_restart_at = 0
                            self.maybe_send_client_restart(s, addr, conn, reason="delayed")
                        fb = getattr(conn, "_mbm_fallback_at", 0)
                        if fb and now >= fb and not acked:
                            conn._mbm_fallback_at = 0
                            self.maybe_send_client_restart(s, addr, conn,
                                                           reason="mbm-fallback")
                        # Delayed CAM/IM (+ optional WAM) after clothing/weapon ACKs.
                        if getattr(conn, "_ownership_done", False):
                            self.maybe_send_cam_im_resend(s, addr, conn)
                            self.maybe_send_wpn_attach_resend(s, addr, conn)
                            if getattr(conn, "_late_ps_rebind_pending", False):
                                self.maybe_send_late_ps_rebind(s, addr, conn)
                            self.maybe_send_softclass_post_stub_4606(s, addr, conn)
                            self.maybe_send_post_attachment_gate_retry(s, addr, conn)
                            # The captured deploy transition can arrive before the
                            # attachment graph is fully resolved.  Give UE one
                            # bounded, explicit replay after the ownership window
                            # has settled, independent of whether the restart gate
                            # itself was eligible to fire.
                            settle_retry_at = getattr(conn, "_late_transition_settle_retry_at", 0.0)
                            if (settle_retry_at and time.time() >= settle_retry_at
                                    and not getattr(conn, "_late_transition_settle_retry_done", False)):
                                conn._late_transition_settle_retry_done = True
                                self.maybe_send_late_transition(s, addr, conn, force=True)
                                self.maybe_send_auto_deploy(s, addr, conn)
                                print("[match]       *** M4: bounded late deploy transition replayed "
                                      "after ownership settle ***")
                            cam_retry_at = getattr(conn, "_camera_retry_at", 0.0)
                            if (cam_retry_at and time.time() >= cam_retry_at
                                    and not getattr(conn, "_camera_retry_done", False)):
                                conn._camera_retry_done = True
                                self.maybe_send_camera_rebind(s, addr, conn, force=True)
                                # The first gameplay callbacks may have run while the
                                # camera target was still invalid. Re-fire them once the
                                # delayed camera bind has been accepted.
                                self.maybe_send_game_started(s, addr, conn, force=True)
                                self.maybe_send_domination_match_started(s, addr, conn, force=True)
                        self.send_packet(s, addr, conn)
                except Exception:
                    pass

    def recvfrom_resilient(self, raw):
        """Receive one UDP datagram without letting stale-peer ICMP kill Windows UDP.

        Winsock reports an ICMP port-unreachable as WSAECONNRESET/WinError 10054 on
        the next ``recvfrom``. It is not a failure of this unconnected listener. Keep
        receiving, while bounding console noise to the first three events and then one
        audit line per hundred. Other connection-reset errors retain normal fail-fast
        behavior.
        """
        while True:
            try:
                return raw.recvfrom(65535)
            except ConnectionResetError as e:
                if getattr(e, "winerror", None) != 10054:
                    raise
                self._udp_reset_count += 1
                n = self._udp_reset_count
                if n <= 3 or n % 100 == 0:
                    print("[match] ignored UDP reset from a closed peer "
                          f"(WinError 10054, count={n})")

    def run(self):
        self.plog = PacketLog()
        raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        raw.bind(("0.0.0.0", self.port))
        s = LoggingSock(raw, self.plog)
        threading.Thread(target=self.keepalive_loop, args=(s,), daemon=True).start()
        print_flag_banner()
        print(f"[match] listening UDP :{self.port}  (M1 handshake + M2 control channel)")
        print(f"[match] waiting for a WW3 client... (matchmake in-game; the hub hands off to here)")
        while True:
            data, addr = self.recvfrom_resilient(raw)
            self.plog.write("C->S", addr, data)
            try:
                self.handle(s, data, addr)
            except Exception as e:
                import traceback; traceback.print_exc()
                print(f"[match] handler error from {addr}: {e}")

    # ---- outgoing: build+send a packet carrying a control bunch (or just acks) ----
    def send_packet(self, s, addr, conn, bunch=None, acks=None, bunches=None, audit_tag=None):
        """One datagram. `bunches` packs SEVERAL bunches into a single packet, which is what
        the real server does: it averages 11.5 bunches per packet (up to 33) at ~411 bytes.
        Sending one bunch per packet floods the client with ~11x the packet rate and it
        drops the connection after roughly a thousand packets."""
        payload = bunches if bunches is not None else ([bunch] if bunch else [])
        pkt_id = conn.out_seq
        pkt = cc.write_packet(pkt_id, acks or [], payload)
        conn.out_seq = (conn.out_seq + 1) & (cc.MAX_PACKETID - 1)
        s.sendto(pkt, addr)
        if ACK_AUDIT and audit_tag:
            conn.pkt_audit[pkt_id] = {"t": time.time(), "tag": audit_tag, "acked": None}
            print(f"[match]       [ack-audit] watching packet {pkt_id} ({audit_tag})")
        return pkt

    def audit_note_acks(self, conn, acks):
        """Mark watched packet-ids the client acknowledged."""
        for a in acks or []:
            rec = conn.pkt_audit.pop(a, None)
            if rec:
                tag = rec["tag"]
                if "ch3 OPEN" in tag:
                    conn._ch3_open_acked = True
                # INV_ATTACH timing gate: clothing + local weapon opens.
                if "src=212" in tag or "src=213" in tag:
                    conn._clothing_acked = True
                if "clothing FULL" in tag:
                    conn._late_ps_rebind_pending = True
                if "ch85" in tag or "src=205" in tag or "src=206" in tag:
                    conn._ch85_acked = True
                if "ch86" in tag or "src=257" in tag or "src=258" in tag:
                    conn._ch86_acked = True
                if "ch87" in tag or "src=259" in tag or "src=260" in tag:
                    conn._ch87_acked = True
                print(f"[match]       [ack-audit] packet {a} ACKED after "
                      f"{(time.time() - rec['t']) * 1000:.0f}ms ({tag})")

    def audit_tick(self, conn):
        """Give a verdict on watched packets the client never acked."""
        now = time.time()
        for pid, rec in list(conn.pkt_audit.items()):
            if now - rec["t"] < ACK_AUDIT_VERDICT_S:
                continue
            print(f"[match]       [ack-audit] *** packet {pid} NOT ACKED after "
                  f"{ACK_AUDIT_VERDICT_S:.1f}s ({rec['tag']}) -- the client skipped the ack, "
                  f"so this bunch died in reassembly, not in SerializeNewActor ***")
            conn.pkt_audit.pop(pid, None)

    def flush_acks(self, s, addr, conn):
        """The real server sends acks in their OWN packets (never mixed with bunches) --
        see the capture: every bunch-carrying packet has acks=[]. Mirror that."""
        if conn.pending_acks:
            acks = conn.pending_acks; conn.pending_acks = []
            self.send_packet(s, addr, conn, acks=acks)

    def send_control_msg(self, s, addr, conn, msg_writer, bOpen=0):
        self.flush_acks(s, addr, conn)                # ack first, in its own packet
        conn.out_chseq = (conn.out_chseq + 1) % MAX_CHSEQUENCE
        bunch = cc.make_control_bunch(msg_writer, conn.out_chseq, bOpen=bOpen, direction_s2c=True)
        self.send_packet(s, addr, conn, bunch=bunch)

    def next_chan_seq(self, conn, ch_index):
        """Reliable sequences are PER CHANNEL and every channel starts at InitOutReliable+1
        (confirmed in the capture: ch2/ch3/ch4/ch5 all began at the same value)."""
        cur = conn.chan_seq.get(ch_index, conn.init_reliable)
        cur = (cur + 1) % MAX_CHSEQUENCE
        conn.chan_seq[ch_index] = cur
        return cur

    # ---- M3 experiment: replay the REAL server's whole early replication stream ----
    def queue_replay_stream(self, conn, path):
        """WW3_REPLAY_FULL=1: queue the captured server's early replication (1200+ bunches,
        ~136 actor spawns across ~91 channels) to be drip-fed like the real server did.
        This is what the client is waiting for at 'LOADING MAP' -- the rest of the world."""
        stream = json.load(open(path))
        # Drop partial-FINAL bunches whose partial-INITIAL fell outside our extraction window
        # -- a half message would desync the channel.
        pending = {}
        cleaned = []
        for b in stream:
            ch = b["chIndex"]
            if b.get("bPartial") and b.get("bPartialFinal") and not pending.get(ch):
                continue
            if b.get("bPartial") and b.get("bPartialInitial"): pending[ch] = True
            elif b.get("bPartial") and b.get("bPartialFinal"): pending[ch] = False
            cleaned.append(b)
        if len(cleaned) != len(stream):
            print(f"[match]       dropped {len(stream)-len(cleaned)} orphaned partial bunches")
        conn.replay_queue = cleaned
        print(f"[match]       queued {len(conn.replay_queue)} captured replication bunches "
              f"({sum(b['bits'] for b in conn.replay_queue)//8//1024} KB) for drip-feed")

    def build_replay_bunch(self, conn, spec):
        """Serialize one captured bunch (does NOT send -- callers batch several per packet)."""
        bits = [int(c) for c in spec["payload"]]
        # Optional: drop NetworkChecksum on NetGUID exports (pawn archetype reject theory).
        if (os.environ.get("WW3_STRIP_EXPORT_CHECKSUM", "0") == "1"
                and spec.get("bHasPackageMapExports")
                and int(spec.get("chIndex", -1)) in (3, 4, 5)):
            try:
                from export_checksum import strip_export_checksums
                before = len(bits)
                bits = strip_export_checksums(bits)
                if not getattr(conn, "_strip_cs_logged", False):
                    conn._strip_cs_logged = True
                    print(f"[match]       *** M4: stripped export checksums on ch"
                          f"{spec['chIndex']} ({before}->{len(bits)} bits) ***")
            except Exception as e:
                print(f"[match]       ! checksum strip failed: {e}")
        # Optional: clear SerializeNewActor scale on pawn partial-final (src 11).
        if (os.environ.get("WW3_PAWN_NO_SCALE", "0") == "1"
                and int(spec.get("chIndex", -1)) == 3
                and not spec.get("bHasPackageMapExports")
                and int(spec.get("_src_idx", -1)) in (11, -1)):
            try:
                from pawn_patch import strip_newactor_scale
                before = len(bits)
                bits = strip_newactor_scale(bits)
                if before != len(bits) and not getattr(conn, "_noscale_logged", False):
                    conn._noscale_logged = True
                    print(f"[match]       *** M4: pawn NewActor scale stripped "
                          f"({before}->{len(bits)} bits) ***")
            except Exception as e:
                print(f"[match]       ! pawn scale strip failed: {e}")
        # Optional: inject APawn::PlayerState/Controller into the ch3 OPEN body
        # (src 11), before subobject stubs — same order as PC/PS opens
        # (SerializeNewActor → ACTOR_REP → SUBs). PostNetInit latches before a
        # post-open follow-up can land (see LIVE_STATUS / NEXT_EXPERIMENT).
        if (os.environ.get("WW3_PAWN_SYNTH_IN_OPEN", "0") == "1"
                and int(spec.get("chIndex", -1)) == 3
                and not spec.get("bHasPackageMapExports")
                and int(spec.get("_src_idx", -1)) in (11, -1)):
            try:
                from pawn_patch import inject_pawn_open_synth_props
                before = len(bits)
                bits = inject_pawn_open_synth_props(bits)
                if before != len(bits) and not getattr(conn, "_pawn_synth_in_open_logged", False):
                    conn._pawn_synth_in_open_logged = True
                    conn._pawn_synth_props_done = True  # skip post-open duplicate
                    print(f"[match]       *** M4: pawn open inject PlayerState(17)->"
                          f"{PS_NETGUID} Controller(18)->{PC_NETGUID} "
                          f"({before}->{len(bits)} bits, WW3_PAWN_SYNTH_IN_OPEN) ***")
            except Exception as e:
                print(f"[match]       ! pawn open synth inject failed: {e}")
        # WW3_WAM_STRIP_CATALOG: rewrite weapon-open FINALs before SoftClass waits
        # arm. SoftClass off → empty catalog. SoftClass on → Mag/min AttachmentIds
        # spliced into capture open RepLayout (skins/MainId kept). Must cover
        # ownership early Glocks (src 15/17 / ch4–5 WAM 8314/7956 — SoftClass id
        # 4606) as well as INV_ATTACH ch86/87 (src 258/260).
        src_for_wam = int(spec.get("_src_idx", -1))
        if src_for_wam in wam_open_strip_srcs():
            try:
                rewritten = maybe_strip_wam_in_weapon_open_bits(bits, src_for_wam)
                if rewritten is not None:
                    before = len(bits)
                    bits = rewritten
                    logged = getattr(conn, "_wam_open_strip_logged", set())
                    if src_for_wam not in logged:
                        logged.add(src_for_wam)
                        conn._wam_open_strip_logged = logged
                        ng = wam_open_strip_srcs()[src_for_wam]
                        if wam_softclass_catalog_enabled():
                            kind = (f"SoftClass {wam_softclass_mode()} "
                                    f"AttachmentIds splice (skins/MainId kept)")
                        else:
                            kind = "empty catalog"
                        print(f"[match]       *** M4: WAM STRIP in open "
                              f"(src={src_for_wam} {ng}@ch{spec['chIndex']}, "
                              f"{kind}, {before}->{len(bits)} bits, "
                              f"WW3_WAM_STRIP_CATALOG) ***")
            except Exception as e:
                print(f"[match]       ! WAM open strip failed src={src_for_wam}: {e}")
        # Hist SoftClass native (STRIP_CHANNELS=inv): Mag NewObject can arm, then
        # SoftClass Rail 4606 hangs mid-flight. Optional in-place 4606→151 splice
        # on early opens finishes/skips Rail without emptying SoftClass catalogs.
        if (wam_softclass_stub_4606_enabled()
                and src_for_wam in WAM_OPEN_FINAL_SRCS
                and src_for_wam not in wam_open_strip_srcs()):
            try:
                stubbed = maybe_stub_softclass_4606_in_weapon_open_bits(
                    bits, src_for_wam)
                if stubbed is not None:
                    before = len(bits)
                    bits = stubbed
                    logged = getattr(conn, "_wam_stub4606_logged", set())
                    if src_for_wam not in logged:
                        logged.add(src_for_wam)
                        conn._wam_stub4606_logged = logged
                        ng = WAM_OPEN_FINAL_SRCS[src_for_wam]
                        print(f"[match]       *** M4: SoftClass STUB 4606->151 "
                              f"(src={src_for_wam} {ng}@ch{spec['chIndex']}, "
                              f"{before}->{len(bits)} bits, "
                              f"WW3_WAM_SOFTCLASS_STUB_4606) ***")
            except Exception as e:
                print(f"[match]       ! SoftClass stub 4606 failed "
                      f"src={src_for_wam}: {e}")
        # Local PS RepLayout (src 21) carries the capture player's SteamID. Patch it to the
        # live client's NMT_Login UniqueId so PlayerState OnSynchronized can bind.
        steam = getattr(conn, "steam_id", None)
        src = spec.get("_src_idx")
        if steam and (src == 21 or find_ascii_in_bits(bits, CAPTURE_PS_STEAM)):
            if patch_ps_steam(bits, steam):
                if not getattr(conn, "_ps_steam_patched", False):
                    conn._ps_steam_patched = True
                    print(f"[match]       *** M4: patched PS SteamID -> {steam} "
                          f"(was {CAPTURE_PS_STEAM.decode()}) ***")
        by = bytearray((len(bits) + 7) // 8)
        for i, b in enumerate(bits):
            if b: by[i >> 3] |= (1 << (i & 7))
        # Honour the captured bReliable! 73% of the real stream is UNRELIABLE; sending it all
        # as reliable overflows the client's per-channel reliable buffer (it closed on us at
        # ~480 bunches). Unreliable bunches carry no ChSequence.
        reliable = spec.get("bReliable", 1)
        # NOTE: real_replay_stream.json never captured bHasMustBeMappedGUIDs (the field
        # is absent from every spec dict -- it was dropped by whatever one-off script
        # produced that JSON from the pcap). Ground-truthed directly against the original
        # capture (captures/24July26/W3_match_full_2.pcapng) via
        # _ground_truth_mbm.py: the pawn open/partial-final and the pawn RepLayout/
        # clothing bunches (src 10,11,181,192,212,213) all have this bit == 0 on the
        # real wire, so defaulting to 0 here is capture-faithful, not a guess. Threading
        # spec.get(...) through (instead of hardcoding 0) means a future, more complete
        # re-extraction of real_replay_stream.json would be honoured automatically.
        bunch = cc.make_bunch(len(bits), bytes(by), ch_index=spec["chIndex"],
                              ch_seq=self.next_chan_seq(conn, spec["chIndex"]) if reliable else 0,
                              ch_type=spec.get("chType") or cc.CHTYPE_ACTOR,
                              bOpen=spec.get("bOpen", 0), bClose=spec.get("bClose", 0),
                              bReliable=reliable,
                              bHasPackageMapExports=spec.get("bHasPackageMapExports", 0),
                              bHasMustBeMappedGUIDs=spec.get("bHasMustBeMappedGUIDs", 0),
                              bPartial=spec.get("bPartial", 0),
                              bPartialInitial=spec.get("bPartialInitial", 0),
                              bPartialFinal=spec.get("bPartialFinal", 0))
        return bunch

    @staticmethod
    def _audit_tag_for(specs):
        """Label a replay packet for WW3_ACK_AUDIT, or None if it isn't pawn-critical.

        Pawn/weapon channels 3/4/5 plus INV_ATTACH inventory channels 85–88. Tagging
        the whole stream would bury the signal in ambient noise.
        """
        if not ACK_AUDIT:
            return None
        hot_chs = {3, 4, 5, 85, 86, 87, 88}
        hot = [sp for sp in specs if int(sp.get("chIndex", -1)) in hot_chs]
        if not hot:
            return None
        parts = []
        for sp in hot:
            parts.append("ch{}{}{} src={}".format(
                sp.get("chIndex"),
                " OPEN" if sp.get("bOpen") else "",
                " partial{}".format("-init" if sp.get("bPartialInitial")
                                    else "-final" if sp.get("bPartialFinal") else "")
                if sp.get("bPartial") else "",
                sp.get("_src_idx")))
        return "; ".join(parts)

    def drain_replay(self, s, addr, conn, budget=60):
        """Send up to `budget` queued bunches per tick (the real server spread its initial
        replication over a few seconds; flooding it in one go is not what the client saw)."""
        # Deferred attachment channels must be opened serially.  Releasing the whole
        # attachment queue in one tick lets UE receive a reliable payload for ch4/ch5/
        # ch85+ before it has committed the preceding open bunch, which leaves the
        # client in Loading Map with "reliable bunch before channel was fully open".
        deferred_pacing = getattr(conn, "_deferred_attachments_active", False)
        if deferred_pacing:
            now = time.time()
            if now < getattr(conn, "_deferred_next_send_at", 0.0):
                return 0
            budget = min(int(budget), 4)
        # After map-streaming RPC (src 5–7), give the client time to load Gameplay_DOM
        # before we send the pawn / GameState. Default pause via WW3_STREAMING_PAUSE_MS.
        # WW3_WAIT_GAMEPLAY_DOM=1 (default): hold until Gameplay_DOM is seen OR pause ends.
        try:
            settle_ms = int(os.environ.get("WW3_STREAMING_PAUSE_MS", "8000"))
        except ValueError:
            settle_ms = 2500
        wait_dom = os.environ.get("WW3_WAIT_GAMEPLAY_DOM", "1") == "1"
        settle_until = getattr(conn, "_streaming_settle_until", 0) or 0
        if settle_until:
            now = time.time()
            if now < settle_until:
                return 0
            else:
                conn._streaming_settle_until = 0
                if (wait_dom and not getattr(conn, "_gameplay_dom_loaded", False)
                        and not getattr(conn, "_gameplay_dom_miss_logged", False)):
                    conn._gameplay_dom_miss_logged = True
                    print("[match]       *** M4: WARN Gameplay_DOM not reported by client "
                          f"after {settle_ms}ms — continuing pawn drip ***")

        MAX_BUNCHES_PER_PACKET = 12          # the real server averages 11.5
        MAX_PAYLOAD_BITS       = 6000        # keeps datagrams near the observed <=1024 bytes
        INV_CHS = {85, 86, 87, 88}           # WW3_INV_ATTACH local inventory actors
        # Early SoftClass Glock WAMs (ch4/ch5). Ownership bootstrap places ch5
        # open (src 16/17) adjacent to pawn RepLayout nudges (src 181/192);
        # co-bundling made live 193402 skip-ack packet 7558 (ch5 died in
        # reassembly). Isolate like INV_CHS. Opt-out: WW3_ISOLATE_EARLY_WPN=0.
        EARLY_WPN_CHS = {4, 5}
        isolate_early_wpn = os.environ.get("WW3_ISOLATE_EARLY_WPN", "1") == "1"

        def _is_inv_ch(spec):
            return int(spec.get("chIndex", -1)) in INV_CHS

        def _packet_family(spec):
            ch = int(spec.get("chIndex", -1))
            if ch in INV_CHS:
                return "inv"
            if isolate_early_wpn and ch in EARLY_WPN_CHS:
                return "early_wpn"
            if isolate_early_wpn and ch == 3:
                return "pawn"
            return "other"

        sent = 0
        while conn.replay_queue and sent < budget:
            # Don't start the next bunch if we're about to hit a post-streaming settle.
            nxt = conn.replay_queue[0]
            # Do not open the pawn until the client has acknowledged the streamed
            # level that owns it.  This is the real UE gate behind the recurring
            # "Failed to find streaming level object" warning; the old pause alone
            # allowed ch3 to arrive too early and be parked forever.
            if (os.environ.get("WW3_WAIT_SPAWN_LEVEL_VIS", "1") == "1"
                    and int(nxt.get("chIndex", -1)) == 3
                    and not getattr(conn, "_spawn_level_visible", False)):
                started = getattr(conn, "_spawn_level_gate_t", None)
                if started is None:
                    conn._spawn_level_gate_t = time.time()
                    started = conn._spawn_level_gate_t
                    print("[match]       *** M4: holding pawn open for "
                          "ServerUpdateLevelVisibility(spawn level) ***")
                try:
                    timeout_s = max(1.0, float(os.environ.get(
                        "WW3_SPAWN_LEVEL_VIS_TIMEOUT_S", "30")))
                except ValueError:
                    timeout_s = 30.0
                if time.time() - started < timeout_s:
                    return sent
                if not getattr(conn, "_spawn_level_gate_timeout_logged", False):
                    conn._spawn_level_gate_timeout_logged = True
                    print(f"[match]       *** M4: WARN spawn level visibility not seen "
                          f"after {timeout_s:.0f}s; releasing pawn gate ***")
            if (settle_ms > 0
                    and getattr(conn, "_streaming_seen", False)
                    and not getattr(conn, "_streaming_settled", False)
                    and int(nxt.get("_src_idx", -1)) > 7):
                conn._streaming_settled = True
                conn._streaming_settle_until = time.time() + settle_ms / 1000.0
                print(f"[match]       *** M4: pausing {settle_ms}ms after streaming "
                      f"for Gameplay_DOM settle (WW3_STREAMING_PAUSE_MS) ***")
                break

            # SoftClass warm: package-map Mag/Rail BP_WP_* on ch3 BEFORE early
            # Glock SoftClass OnRep (src 15/17). Export-only — no stably=0 content.
            peek_src = int(nxt.get("_src_idx", -1))
            if (peek_src >= 14 and wam_softclass_warm_export_enabled()
                    and not getattr(conn, "_softclass_warm_export_done", False)):
                if self.maybe_send_softclass_warm_export(s, addr, conn):
                    # Count as progress so we don't starve warm behind budget=0 loops.
                    sent += 1
                    if sent >= budget:
                        break

            batch, bits, specs = [], 0, []
            while (conn.replay_queue and len(batch) < MAX_BUNCHES_PER_PACKET
                   and sent < budget
                   and (not batch or bits + conn.replay_queue[0]["bits"] < MAX_PAYLOAD_BITS)):
                # Keep streaming partial chain in one drain burst; settle after src 7.
                peek = conn.replay_queue[0]
                if (settle_ms > 0
                        and getattr(conn, "_streaming_seen", False)
                        and not getattr(conn, "_streaming_settled", False)
                        and int(peek.get("_src_idx", -1)) > 7
                        and batch):
                    break
                # SoftClass warm must land BEFORE early weapon SoftClass OnRep.
                # Don't pull src>=14 into a batch that started earlier (src 11–13
                # + src 14 fit under 6000 bits) — break so outer loop can warm.
                if (batch and wam_softclass_warm_export_enabled()
                        and not getattr(conn, "_softclass_warm_export_done", False)
                        and int(peek.get("_src_idx", -1)) >= 14):
                    break
                # Isolate exclusive channel families so one skip-ack cannot kill
                # SoftClass opens or inventory opens:
                #   inv (85–88) — live 063950 MSP+ch5 skip-ack
                #   early_wpn (4/5) vs pawn (3) — live 193402 pkt 7558 ch5 OPEN
                #     + src 181/192 NOT ACKED (reassembly skip)
                # Exclusive packets stay pure (no "other" co-bundle).
                if batch:
                    # During deferred release, keep each datagram to one channel so
                    # the client's channel-open bookkeeping cannot be overtaken by a
                    # reliable bunch from the next attachment actor.  More importantly,
                    # partial OPEN chains must not share a datagram: UE can acknowledge
                    # the packet while still leaving the channel in its pre-open state,
                    # and then rejects the next reliable bunch as "before channel was
                    # fully open".  One bunch per datagram is intentional here.
                    if deferred_pacing:
                        break
                    batch_fams = {_packet_family(sp) for sp in specs}
                    peek_fam = _packet_family(peek)
                    batch_ex = batch_fams - {"other"}
                    if batch_ex:
                        if peek_fam != next(iter(batch_ex)):
                            break
                    elif peek_fam != "other":
                        break
                spec = conn.replay_queue.pop(0)
                batch.append(self.build_replay_bunch(conn, spec))
                specs.append(spec)
                bits += spec["bits"]; sent += 1
            if batch:
                self.send_packet(s, addr, conn, bunches=batch,
                                 audit_tag=self._audit_tag_for(specs))
                if deferred_pacing:
                    # Leave a receive/ACK window between every attachment bunch.
                    conn._deferred_next_send_at = time.time() + 0.45
                for spec in specs:
                    conn.replay_sent = getattr(conn, "replay_sent", 0) + 1
                    if getattr(conn, "_bootstrap_opens_action_replicator", False):
                        self.note_replay_bunch_sent(conn, spec)
                    if spec.get("bOpen") and spec.get("chIndex") == 3 and not getattr(conn, "pawn_sent", False):
                        conn.pawn_sent = True
                        conn._pawn_open_t = time.time()
                        print(f"[match]       *** M4: PlayerPawn channel OPEN (ch3) sent — "
                              f"same spawn as PC ***")
                    src = spec.get("_src_idx")
                    if src == 2:
                        print(f"[match]       *** M4: HUD export/RPC (bootstrap src=2) ***")
                    if src == 5:
                        print(f"[match]       *** M4: map streaming payload (bootstrap src=5) ***")
                        conn._streaming_seen = True
                    if src == 7:
                        conn._streaming_seen = True
                    if src == 20:
                        print(f"[match]       *** M4: local PlayerState OPEN (ch7 / PS 9362) ***")
                        conn.ps_opened = True
                        conn.ps_channel = int(spec["chIndex"])
                    if src == 181:
                        print(f"[match]       *** M4: pawn RepLayout nudge (src=181/192) ***")
                    if src == 212:
                        print(f"[match]       *** M4: pawn clothing/CharacterAttachments "
                              f"(bootstrap src=212–213) ***")
                    if src == 205:
                        print(f"[match]       *** M4: local MSP OPEN (ch85 / 9402, "
                              f"WW3_INV_ATTACH) ***")
                    if src == 257:
                        print(f"[match]       *** M4: local secondary weapon OPEN "
                              f"(ch86 / 9412, WW3_INV_ATTACH) ***")
                    if src == 259:
                        print(f"[match]       *** M4: local primary weapon OPEN "
                              f"(ch87 / 9410 HK417, WW3_INV_ATTACH) ***")
                    if src == 261:
                        print(f"[match]       *** M4: local repair kit OPEN "
                              f"(ch88 / 9408, WW3_INV_ATTACH) ***")
                    if spec.get("bOpen") and spec.get("chIndex") == 53:
                        print(f"[match]       *** M4: GameState channel OPEN (ch53) ***")
                    if spec.get("bOpen") and spec.get("chIndex") == 4:
                        print(f"[match]       *** M4: local weapon OPEN (ch4) ***")
                    if spec.get("_ambient") and spec.get("bOpen") and not getattr(conn, "_ambient_logged", False):
                        conn._ambient_logged = True
                        print(f"[match]       *** M5: ambient world drip starting "
                              f"(src={spec.get('_src_idx')}, ch{spec.get('chIndex')}) ***")
        if sent and not conn.replay_queue:
            # In deferred-attachment mode the first queue completion is the
            # attachment-free ownership phase. Do not fire the normal
            # ownership-complete side effects a second time when the deferred
            # attachment queue drains after AckPossession(Pawn).
            deferred_phase = getattr(conn, "_deferred_attachments_active", False)
            if deferred_phase:
                conn._deferred_attachments_active = False
                print("[match]       *** M4: deferred attachment phase fully sent ***")
                self.maybe_send_post_attachment_restart(s, addr, conn)
                return sent
            print(f"[match]       *** M4 ownership+ambient stream fully sent "
                  f"({conn.replay_total} bunches, pawn_sent={getattr(conn,'pawn_sent',False)}) ***")
            conn._ownership_done = True
            conn._ownership_done_t = time.time()
            # The capture exports BP_CapturePoint_A/B (and their "First Spawn
            # Zone" children) on other players' PlayerState opens at pkt 174/216,
            # BEFORE the capture-point channels open at pkt 280/370.  Preserve
            # that order: the exports must land before anything references them.
            self.maybe_replay_capturepoint_exports(s, addr, conn)
            # The capture opens both capture-point channels at pkt 370, i.e. while
            # the world is still coming up and long before the deploy screen.
            self.maybe_replay_capture_points(s, addr, conn)
            conn._delayed_restart_at = time.time() + float(
                os.environ.get("WW3_CLIENT_RESTART_DELAY_S", "2.0"))
            self.maybe_send_ps_rebind(s, addr, conn)
            reason = "ownership+queued-check" if getattr(conn, "_restart_on_ownership", False) else "ownership"
            self.maybe_send_client_restart(s, addr, conn, reason=reason)
            # AFTER_ACK mode: Restart goes out without CAM/IM; arm wait log + poll
            # from keepalive once clothing/weapon packets ACK.
            if cam_im_after_ack_enabled() and inv_attach_enabled():
                self.maybe_send_cam_im_resend(s, addr, conn)
            if cam_im_after_ack_enabled() and wpn_attach_enabled():
                self.maybe_send_wpn_attach_resend(s, addr, conn)
            if cam_im_after_ack_enabled() and wam_softclass_post_stub_4606_enabled():
                self.maybe_send_softclass_post_stub_4606(s, addr, conn)
        return sent

    def maybe_send_post_attachment_restart(self, s, addr, conn):
        """Re-run the client possession/restart path after attachment channels are open.

        The first ClientRestart is necessarily sent while the pawn is being spawned.
        WW3's LoadingMap gate can still be waiting on weapon/inventory attachment
        managers at that point; once those channels finish, a final non-MustBeMapped
        restart is the native trigger that re-evaluates the gate and installs the
        player camera.  Keep this to one shot per connection.
        """
        if os.environ.get("WW3_POST_ATTACH_RESTART", "1") == "0":
            return False
        if getattr(conn, "_post_attachment_restart_done", False):
            return False
        if not getattr(conn, "_ack_possess_pawn", False):
            return False
        handles = restart_handles()
        if not handles:
            return False
        # Re-state the object graph after every attachment channel is open.  The
        # initial bind blocks can arrive while the pawn/PlayerState NetGUIDs are
        # still unresolved; a later restart alone does not cause UE to replay
        # those properties.  Send each bind as its own reliable bunch so ch2's
        # ordering is unambiguous, then restart on the same channel.
        if os.environ.get("WW3_PC_SET_PAWN", "0") == "1":
            self.maybe_send_pc_set_pawn(s, addr, conn, force=True)
        if os.environ.get("WW3_PS_SET_PLAYERCHAR", "0") == "1":
            self.maybe_send_ps_set_playerchar(s, addr, conn, force=True)
        if os.environ.get("WW3_PAWN_SYNTH_PROPS", "0") == "1":
            self.maybe_send_pawn_synth_props(s, addr, conn, force=True)
        # A captured listen-server transition is only meaningful once the pawn's
        # character/weapon graph is mapped.  Re-send the complete transition bundle
        # at this point, not just ClientRestart; the earlier post-ack spray can be
        # ACKed while its object references are still unresolved.
        if (os.environ.get("WW3_POST_ATTACHMENT_TRANSITION", "1") == "1"
                and not getattr(conn, "_post_attachment_transition_done", False)):
            self.maybe_send_post_pawn_pc_state(
                s, addr, conn, force=True, audit_tag="post-attachment PC src=8")
            self.maybe_send_player_respawned(s, addr, conn, force=True)
            self.maybe_send_player_respawned_with_movement_type(s, addr, conn, force=True)
            self.maybe_clear_spectator_waiting(s, addr, conn)
            self.maybe_send_client_goto_state(s, addr, conn)
            self.maybe_send_client_stream_status(s, addr, conn)
            self.maybe_send_game_started(s, addr, conn, force=True)
            self.maybe_send_late_transition(s, addr, conn, force=True)
            self.maybe_send_camera_rebind(s, addr, conn)
            self.maybe_send_post_spawn_finalize_rpcs(s, addr, conn, force=True)
            conn._post_attachment_transition_done = True
        pawn_arg = restart_pawn_guid()
        h = handles[0]
        bits = build_client_restart_bits(pawn_arg, handle=h, must_be_mapped=False)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunch=cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1))
        conn._post_attachment_restart_done = True
        print(f"[match]       *** M4: post-attachment ClientRestart (Pawn {pawn_arg}) "
              f"handle={h} — rechecking LoadingMap attachment gate ***")
        return True

    def maybe_send_post_attachment_gate_retry(self, s, addr, conn):
        """Bounded late retries for the LoadingMap attachment gate.

        Attachment objects can resolve after the first post-ACK restart.  UE only
        reevaluates the native gate when ClientRestart is received, so retry that
        idempotent RPC a few times while the client is still in the possession
        window.  Do not replay the transition bundle or attachment payloads.
        """
        if not getattr(conn, "_post_attachment_restart_done", False):
            return False
        if getattr(conn, "_post_attachment_gate_retry_count", 0) >= 5:
            return False
        now = time.time()
        due = getattr(conn, "_post_attachment_gate_retry_at", 0.0)
        if due and now < due:
            return False
        handles = restart_handles()
        if not handles:
            return False
        pawn_arg = restart_pawn_guid()
        bits = build_client_restart_bits(pawn_arg, handle=handles[0], must_be_mapped=False)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunch=cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1))
        n = int(getattr(conn, "_post_attachment_gate_retry_count", 0)) + 1
        conn._post_attachment_gate_retry_count = n
        conn._post_attachment_gate_retry_at = now + 4.0
        if n == 3 and os.environ.get("WW3_POST_ATTACHMENT_TRANSITION_RETRY", "1") == "1":
            # WAM completion may lag the first transition by several seconds.
            # Replay the captured gameplay-start bundle once, immediately before
            # the next gate retry, so UE observes it after native sync callbacks.
            self.maybe_send_post_pawn_pc_state(
                s, addr, conn, force=True, audit_tag="late post-attachment PC src=8")
            self.maybe_send_player_respawned(s, addr, conn, force=True)
            self.maybe_send_player_respawned_with_movement_type(s, addr, conn, force=True)
            self.maybe_clear_spectator_waiting(s, addr, conn)
            self.maybe_send_client_goto_state(s, addr, conn)
            self.maybe_send_client_stream_status(s, addr, conn)
            self.maybe_send_game_started(s, addr, conn, force=True)
            self.maybe_send_late_transition(s, addr, conn, force=True)
            self.maybe_send_camera_rebind(s, addr, conn)
            self.maybe_send_post_spawn_finalize_rpcs(s, addr, conn, force=True)
            print("[match]       *** M4: late gameplay transition replayed after "
                  "attachment settle ***")
        print(f"[match]       *** M4: late attachment-gate ClientRestart retry {n}/5 "
              f"(Pawn {pawn_arg}, handle={handles[0]}) ***")
        return True

    def _release_deferred_attachments(self, conn):
        """Release attachment channels after the initial possession sync window."""
        deferred = getattr(conn, "_deferred_attachment_queue", None)
        if not deferred or getattr(conn, "_deferred_attachments_released", False):
            return False
        conn._deferred_attachments_released = True
        conn._deferred_attachment_release_at = 0
        conn._deferred_attachments_active = True
        conn.replay_queue.extend(deferred)
        conn.replay_total += len(deferred)
        print(f"[match]       *** M4: releasing {len(deferred)} deferred attachment "
              "bunches after possession sync hold ***")
        return True

    def _restart_skip(self, conn, why):
        """Log (once per distinct cause) why a ClientRestart attempt did NOT go out.

        Silence used to be indistinguishable from "the flag was off" — that ambiguity is
        exactly what cost session 20260805_193023 (launched WW3_CLIENT_RESTART=0, analysed
        as if Restart had been attempted and failed).
        """
        seen = getattr(conn, "_restart_skips", None)
        if seen is None:
            seen = conn._restart_skips = set()
        if why not in seen:
            seen.add(why)
            print(f"[match]       *** M4: ClientRestart NOT sent - {why} ***")
        return False

    def _note_restart_reaction(self, conn, label):
        """Always-printed (not gated) causal correlation for handle-calibration runs.

        The existing Ack/CheckPossession prints below are gated 'once per connection',
        which docs/M4_Possession_Findings.md fact #10 flagged as unable to distinguish
        the client's own spontaneous retries from an actual reaction to our RPC. This
        prints every time, with the elapsed ms since the last ClientRestart send, so a
        calibration run's verdict is readable straight off the console.
        """
        last = getattr(conn, "_last_restart_send_t", 0)
        if not last:
            print(f"[match]       [calib] {label} (no ClientRestart sent yet this connection)")
            return
        dt = (time.time() - last) * 1000
        tag = "REACTION" if dt < 5000 else "stale/unrelated"
        print(f"[match]       [calib] {label} t+{dt:.0f}ms after last ClientRestart send ({tag})")

    def restart_gates_ready(self, conn):
        """(ready, why_not) for the 'must be strictly AFTER the pawn open' gates."""
        # ServerCheckClientPossession can arrive while the streamed map is still
        # settling.  It used to bypass that phase and fire ClientRestart within
        # milliseconds of the pawn open, which made the client close ch0 before
        # its camera/attachment managers were initialized.  All restart causes
        # must observe the same streaming settle barrier.
        settle_until = getattr(conn, "_streaming_settle_until", 0) or 0
        if settle_until and time.time() < settle_until:
            remaining = max(1, int((settle_until - time.time()) * 1000))
            return False, f"waiting {remaining}ms for map streaming settle"
        after_ms = int(os.environ.get("WW3_CLIENT_RESTART_AFTER_PAWN_MS", "0"))
        need_ack = os.environ.get("WW3_CLIENT_RESTART_REQUIRE_CH3_ACK", "0") == "1"
        timeout_s = float(os.environ.get("WW3_CLIENT_RESTART_GATE_TIMEOUT_S", "20"))
        t_open = getattr(conn, "_pawn_open_t", 0) or 0
        if not t_open:
            return False, "pawn ch3 open not sent yet"
        waited = time.time() - t_open
        if waited >= timeout_s:
            return True, None                      # never let a gate stall the run forever
        if after_ms and waited * 1000.0 < after_ms:
            return False, (f"waiting {after_ms}ms after pawn open "
                           f"(WW3_CLIENT_RESTART_AFTER_PAWN_MS)")
        if need_ack and ACK_AUDIT and not getattr(conn, "_ch3_open_acked", False):
            return False, "ch3 OPEN packet not ACKED yet (WW3_CLIENT_RESTART_REQUIRE_CH3_ACK)"
        return True, None

    def maybe_send_client_restart(self, s, addr, conn, reason="ownership"):
        """Send ClientRestart(Pawn=9372) so the client AcknowledgesPossession.

        Capture has no S->C ClientRestart (listen-server). Wire handle 39 is the
        dump-derived ClientRestart index (class_net_cache_ww3.json schema v2).

        Live session 20260805_164147: pawn open is bit-exact vs capture, but client
        never maps NetGUID 9372 (no ch3 C->S). MustBeMapped Restart queued forever.
        WW3_CLIENT_RESTART_MUSTMAP picks the framing; WW3_CLIENT_RESTART_MBM_FALLBACK_S
        sends the opposite framing once if the first shot stays silent, so a MustBeMapped
        run still yields an oracle instead of nothing.

        Ordering: WW3_CLIENT_RESTART_AFTER_PAWN_MS / _REQUIRE_CH3_ACK hold the RPC until
        the pawn open (and its export prefix) is demonstrably on the client.
        """
        if os.environ.get("WW3_CLIENT_RESTART", "1") == "0":
            return self._restart_skip(conn, "WW3_CLIENT_RESTART=0 (launcher disabled it)")
        if getattr(conn, "_ack_possess_pawn", False):
            return False
        if not getattr(conn, "pawn_sent", False):
            # Too early — remember to fire once the pawn channel opens.
            if reason in ("ack-null", "check-possess"):
                conn._restart_on_ownership = True
            return False
        sprays = getattr(conn, "_client_restart_sprays", 0)
        max_sprays = int(os.environ.get("WW3_CLIENT_RESTART_MAX_SPRAYS", "4"))
        if sprays >= max_sprays:
            return self._restart_skip(conn, f"spray budget spent ({sprays}/{max_sprays})")
        if sprays == 0 and not getattr(conn, "_ownership_done", False):
            if reason not in ("check-possess", "ack-null"):
                return False
            conn._restart_on_ownership = True
            return False
        ready, why_not = self.restart_gates_ready(conn)
        if not ready:
            # Keep the keepalive loop retrying instead of dropping the attempt.
            conn._delayed_restart_at = time.time() + 0.25
            return self._restart_skip(conn, why_not)
        # Default OFF: live sessions showed MBM Restart queued forever because the client
        # never mapped NetGUID 9372 (no C->S traffic with 9372 / no ch3). Without MBM the
        # RPC at least runs (null or real pawn). Set WW3_CLIENT_RESTART_MUSTMAP=1 to retry MBM.
        use_mbm = os.environ.get("WW3_CLIENT_RESTART_MUSTMAP", "0") == "1"
        # Ordering is not a preference. A MustBeMapped bunch whose GUID never resolves sits
        # in UActorChannel::QueuedBunches, and every LATER reliable bunch on that channel
        # queues behind it. Live session 20260805_194518 sent MustBeMapped first and the
        # non-MustBeMapped follow-up 8s later got no reply at all (the client stayed
        # connected, 10894 more C->S bunches) — head-of-line blocked, not ignored. So when
        # both framings are wanted, the executable one must go first.
        if float(os.environ.get("WW3_CLIENT_RESTART_MBM_FALLBACK_S", "0")) > 0:
            use_mbm = (reason == "mbm-fallback")
        # Retry is opt-in only. Earlier builds forced Retry on ownership/ack-null and the
        # `retry_handles() or [10]` fallback re-introduced handle 10 → lobby kicks.
        send_retry = os.environ.get("WW3_CLIENT_RESTART_SEND_RETRY", "0") == "1"
        conn._client_restart_sprays = sprays + 1
        calib = restart_calibration_pawn_guid()
        pawn_arg = restart_pawn_guid()
        if calib is not None:
            # Calibration run: never chase MustBeMapped for a GUID that isn't a pawn.
            use_mbm = False
        else:
            # The captured listen-server transition bundle (bootstrap src=8) contains
            # more than ClientRestart: it also sets the pawn as the view target and
            # selects the gameplay camera.  In the capture it is sent before the pawn
            # open, but our replay has no engine-side MustBeMapped queue, so those
            # object-reference calls execute against null and are lost.  Re-send the
            # exact captured bundle once the pawn is known to exist, before our final
            # dedicated-server Restart shot.
            self.maybe_send_pc_set_pawn(s, addr, conn)
            self.maybe_send_ps_set_playerchar(s, addr, conn)
            # Replay the captured transition only after the PC/Pawn and
            # PlayerState/Pawn bindings are present.  Src=8 contains
            # ClientRestart, Client_OnPlayerRespawned and ClientGameStarted;
            # sending it before those bindings makes the UObject references
            # resolve to null even though ch3 is already open.
            self.maybe_send_post_pawn_pc_state(s, addr, conn)
            if not (os.environ.get("WW3_PAWN_SYNTH_AFTER_ACK_ONLY", "0") == "1"
                    and not getattr(conn, "_ack_possess_pawn", False)):
                self.maybe_send_pawn_synth_props(s, addr, conn)
            # Immediate CAM/IM only when not waiting for clothing/weapon ACKs.
            if not cam_im_after_ack_enabled():
                self.maybe_send_cam_im_resend(s, addr, conn)
                self.maybe_send_wpn_attach_resend(s, addr, conn)
        batch = []
        handles = []
        for h in restart_handles():
            bits = build_client_restart_bits(pawn_arg, handle=h, must_be_mapped=use_mbm)
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= (1 << (i & 7))
            batch.append(cc.make_bunch(
                len(bits), bytes(by), ch_index=2,
                ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
                bOpen=0, bReliable=1, bHasMustBeMappedGUIDs=1 if use_mbm else 0))
            handles.append(h)
        if send_retry:
            for h in retry_handles():
                if h in handles:
                    continue
                bits = build_client_retry_restart_bits(
                    pawn_arg, handle=h, must_be_mapped=use_mbm)
                by = bytearray((len(bits) + 7) // 8)
                for i, bit in enumerate(bits):
                    if bit:
                        by[i >> 3] |= (1 << (i & 7))
                batch.append(cc.make_bunch(
                    len(bits), bytes(by), ch_index=2,
                    ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
                    bOpen=0, bReliable=1, bHasMustBeMappedGUIDs=1 if use_mbm else 0))
                handles.append(f"R{h}")
        self.flush_acks(s, addr, conn)
        for i in range(0, len(batch), 4):
            self.send_packet(s, addr, conn, bunches=batch[i:i + 4])
        conn._delayed_restart_at = 0
        waited_ms = (time.time() - (getattr(conn, "_pawn_open_t", 0) or time.time())) * 1000
        calib_tag = f" CALIBRATE(arg={pawn_arg} != real pawn {PAWN_NETGUID})" if calib is not None else ""
        conn._last_restart_send_t = time.time()
        print(f"[match]       *** M4: ClientRestart (Pawn {pawn_arg}){calib_tag} "
              f"handles={handles} mustMap={use_mbm} reason={reason} "
              f"spray={conn._client_restart_sprays}/{max_sprays} "
              f"t+{waited_ms:.0f}ms after pawn open ***")
        # A MustBeMapped Restart is silent when the GUID never maps (fact #6 in
        # docs/M4_Possession_Findings.md). Optionally follow up ONCE with the opposite
        # framing so the run still produces an Ack of some kind to reason about.
        fallback_s = float(os.environ.get("WW3_CLIENT_RESTART_MBM_FALLBACK_S", "0"))
        if calib is None and fallback_s > 0 and reason != "mbm-fallback":
            conn._mbm_fallback_at = time.time() + fallback_s
            print(f"[match]       (mbm fallback armed: one mustMap={not use_mbm} shot in "
                  f"{fallback_s:.0f}s unless AckPossession(Pawn) arrives; "
                  f"non-MustBeMapped goes first so it can't be head-of-line blocked)")
        return True

    def maybe_send_post_pawn_pc_state(self, s, addr, conn, force=False,
                                      audit_tag="post-pawn PC src=8"):
        """Replay capture bootstrap src=8 after pawn mapping.

        Src 8 is the listen-server's post-spawn PC state: ClientRestart(9372),
        ClientSetViewTarget(9372), camera mode, and rotation/state updates.  The
        dedicated replay sends the same bytes before ch3 exists, where UObject refs
        resolve to null.  A single exact replay after ch3 opens lets the client run
        the transition instead of remaining on the map briefing screen.
        """
        if getattr(conn, "_post_pawn_pc_state_done", False) and not force:
            return False
        if os.environ.get("WW3_POST_PAWN_PC_STATE", "1") != "1":
            conn._post_pawn_pc_state_done = True
            return False
        if not getattr(conn, "pawn_sent", False):
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "ownership_bootstrap.json")
        try:
            boot = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"[match]       ! post-pawn PC state unavailable: {e}")
            conn._post_pawn_pc_state_done = True
            return False
        spec = next((dict(b) for b in boot if int(b.get("_src_idx", -1)) == 8
                     and int(b.get("chIndex", -1)) == 2), None)
        if spec is None:
            print("[match]       ! post-pawn PC state src=8 missing from bootstrap")
            conn._post_pawn_pc_state_done = True
            return False
        bunch = self.build_replay_bunch(conn, spec)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[bunch], audit_tag=audit_tag)
        conn._post_pawn_pc_state_done = True
        print(f"[match]       *** M4: {audit_tag} replayed "
              "(ClientRestart + ViewTarget/Camera) ***")
        return True

    def maybe_send_game_started(self, s, addr, conn, force=False):
        """Send ClientGameStarted separately after confirmed possession."""
        if getattr(conn, "_game_started_rpc_done", False) and not force:
            return False
        if os.environ.get("WW3_CLIENT_GAME_STARTED", "1") != "1":
            if not force:
                conn._game_started_rpc_done = True
            return False
        bits = build_zero_arg_rpc_bits(88)  # PlayerController::ClientGameStarted
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._game_started_rpc_done = True
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack ClientGameStarted")
        print("[match]       *** M4: isolated ClientGameStarted (handle 88) sent after possession ***")
        return True

    def maybe_send_domination_match_started(self, s, addr, conn, force=False):
        """Enter WW3's domination gameplay state after the network pawn is ready.

        This is a WW3PlayerController client RPC (handle 154), distinct from the
        engine-level ClientGameStarted.  The real game-mode controller uses it to
        leave the LoadingMap/briefing state and create the local domination HUD and
        camera.  A transport ACK only proves the bunch was consumed; without this
        mode-specific transition the client can remain in LoadingMap with a null PC.
        """
        if getattr(conn, "_domination_match_started_rpc_done", False) and not force:
            return False
        if os.environ.get("WW3_CLIENT_START_DOMINATION", "1") != "1":
            if not force:
                conn._domination_match_started_rpc_done = True
            return False
        bits = build_zero_arg_rpc_bits(154)  # WW3PlayerController::Client_StartDominationMatch
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._domination_match_started_rpc_done = True
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack Client_StartDominationMatch")
        print("[match]       *** M4: Client_StartDominationMatch (handle 154) sent after possession ***")
        return True

    def maybe_send_infantry_widget(self, s, addr, conn, force=False):
        """Show WW3's local infantry HUD after confirmed pawn possession.

        The SDK marks ``Client_ShowInfantryWidget`` as a reliable, zero-argument
        client RPC (controller handle 151).  Keep the callback opt-in until a live
        run proves that it dismisses the map briefing and exposes the gameplay HUD.
        """
        if getattr(conn, "_infantry_widget_rpc_done", False) and not force:
            return False
        if os.environ.get("WW3_CLIENT_SHOW_INFANTRY_WIDGET", "0") != "1":
            if not force:
                conn._infantry_widget_rpc_done = True
            return False
        bits = build_zero_arg_rpc_bits(151)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._infantry_widget_rpc_done = True
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack Client_ShowInfantryWidget")
        print("[match]       *** M4: Client_ShowInfantryWidget (handle 151) sent after possession ***")
        return True

    def maybe_send_auto_deploy(self, s, addr, conn, force=False):
        """Ask the WW3 controller to leave the deploy/briefing overlay.

        ``Client_OnStopSpectatorBeforeDeploy`` is only the pre-deploy callback;
        the controller's netfield table also exposes ``Client_PerformAutoDeploy``
        (handle 261), which is the actual no-argument deploy action.  A listen
        server sends this after the player is ready; the replay capture ended
        before that user-facing action, so dedicated runs need one bounded call.
        """
        if getattr(conn, "_auto_deploy_rpc_done", False) and not force:
            return False
        if os.environ.get("WW3_CLIENT_AUTO_DEPLOY", "1") != "1":
            if not force:
                conn._auto_deploy_rpc_done = True
            return False
        conn._auto_deploy_rpc_done = True
        # Some WW3 builds remain in the briefing overlay without ever emitting
        # Server_OnClientPreloadWeaponsFinished (279).  Keep the normal
        # readiness-gated path, but allow a dedicated-server A/B run to probe
        # the preceding callback explicitly before arming deployment.
        if os.environ.get("WW3_BEFORE_SPECTATOR_EAGER", "0") == "1":
            # The readiness path may already have sent 226 immediately before
            # entering this method.  Repeating this stateful callback suppresses
            # the client's 299/282 post-spectator response, so preserve its
            # single-shot guard even when the deploy bundle itself is forced.
            self.maybe_send_before_spectator_return(s, addr, conn, force=False)
        self.flush_acks(s, addr, conn)
        # These two no-argument callbacks arm the round-start spawn path; the
        # final auto-deploy call then executes it.  They are idempotent on the
        # native controller and are sent as separate reliable bunches to keep
        # the order observable by UE.
        deploy_rpcs = [(270, "Client_SpectatorReturnToGame")]
        # The live client can acknowledge possession yet continue emitting
        # ServerSetSpectatorLocation/Server_SpectatorAttachToCapturePoint.  Probe
        # the native pre-deploy stop callback independently; it is opt-in until
        # a live run proves that those spectator RPCs cease.
        if os.environ.get("WW3_CLIENT_STOP_SPECTATOR_BEFORE_DEPLOY", "0") == "1":
            deploy_rpcs.append((254, "Client_OnStopSpectatorBeforeDeploy"))
        if os.environ.get("WW3_CLIENT_STOP_SPECTATOR", "0") == "1":
            deploy_rpcs.append((271, "Client_StopSpectator"))
        deploy_rpcs.extend(((220, "Client_EnableSpawnAfterDeath"),
                            (222, "Client_ForceSpawnOnRoundBegin"),
                            (261, "Client_PerformAutoDeploy")))
        for handle, label in deploy_rpcs:
            if handle == 254:
                params = build_stop_spectator_before_deploy_param_bits(
                    SPAWN_LOCATION, leave_source=3)
                bits = build_raw_rpc_bits(handle, params)
            elif handle == 222:
                # bInIsFirstRound (bool) is the sole parameter.
                bits = build_raw_rpc_bits(handle, [1])
            else:
                bits = build_zero_arg_rpc_bits(handle)
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= 1 << (i & 7)
            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                len(bits), bytes(by), ch_index=2,
                ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
                bOpen=0, bReliable=1)], audit_tag=f"post-ownership {label}")
            print(f"[match]       *** M4: {label} (handle {handle}) sent ***")
        # Re-apply the authoritative captured spectator-leave transition after the
        # spawn arm callbacks.  The first replay can arrive while the controller is
        # still in spectator mode; this second pass is idempotent and preserves the
        # capture's exact payload instead of synthesizing another speculative RPC.
        self.maybe_send_late_transition(s, addr, conn, force=True)
        # Rebind the possessed pawn as the view target after the deploy callbacks;
        # the earlier camera packet may have run while the controller was still
        # in spectator mode.
        self.maybe_send_camera_rebind(s, addr, conn, force=True)
        return True

    def maybe_send_before_spectator_return(self, s, addr, conn, force=False):
        """Send Client_OnBeforeSpectatorReturnToGame (handle 226).

        Both parameters are normal RPC properties: an object reference followed
        by a float, each with its RepLayout send bit.  Keep this opt-in while the
        exact build's callback is validated; malformed framing is rejected by UE
        with a property mismatch and leaves the rest of the transition unusable.
        """
        if os.environ.get("WW3_BEFORE_SPECTATOR_RETURN", "0") != "1":
            return False
        if getattr(conn, "_before_spectator_return_done", False) and not force:
            return False
        conn._before_spectator_return_done = True
        try:
            ps_guid = int(os.environ.get("WW3_BEFORE_SPECTATOR_PS_GUID", str(PS_NETGUID)))
            delay = float(os.environ.get("WW3_BEFORE_SPECTATOR_DELAY", "0"))
        except ValueError:
            ps_guid, delay = PS_NETGUID, 0.0
        layout = os.environ.get("WW3_BEFORE_SPECTATOR_LAYOUT", "sendbits")
        force_float = (os.environ.get("WW3_BEFORE_SPECTATOR_FORCE_FLOAT", "0") == "1")
        try:
            params = build_before_spectator_param_bits(ps_guid, delay, layout, force_float)
        except ValueError as exc:
            print(f"[match]       *** Client_OnBeforeSpectatorReturnToGame skipped: {exc} ***")
            return False
        bits = build_raw_rpc_bits(226, params)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-preload Client_OnBeforeSpectatorReturnToGame")
        print(f"[match]       *** Client_OnBeforeSpectatorReturnToGame (handle 226, PS {ps_guid}, delay {delay:g}, layout {layout}) sent ({len(bits)} bits) ***")
        return True

    def maybe_send_post_preload_deploy(self, s, addr, conn):
        """Finish the deploy transition after the client reports weapon preload.

        The native controller emits Server_OnClientPreloadWeaponsFinished (wire
        handle 279) only after the local weapon managers have completed.  In the
        real game that callback is the point at which the server advances the
        spectator/deploy state.  Our replay used to send the deploy callbacks
        before this acknowledgement and never re-issued them, leaving the client
        in the briefing while all packets were transport-ACKed.
        """
        if self.strict_player_in_game_order_enabled():
            # A h279 observed before h65/profile completion belongs to the earlier
            # bootstrap attempt.  Do not latch it: strict mode requires a fresh
            # callback after the capture-grounded player-in-game sequence.
            if not getattr(conn, "_strict_profiles_complete", False):
                if not getattr(conn, "_strict_early_h279_logged", False):
                    conn._strict_early_h279_logged = True
                    print("[match]       *** strict order: pre-profile h279 ignored; "
                          "a fresh h279 is required after profile completion ***")
                return False
            if getattr(conn, "_strict_post_profile_h279_done", False):
                return False
            conn._strict_post_profile_h279_done = True
            conn._strict_post_profile_h279_ready = True
            conn._preload_weapons_finished = True
            sent = self.maybe_send_late_transition(s, addr, conn, force=False)
            print("[match]       *** strict order: fresh post-profile h279 accepted; "
                  "captured source1934 released once ***")
            return sent
        conn._preload_weapons_finished = True
        # Treat handle 279 as readiness, not permission to consume the deploy
        # one-shot immediately.  Live runs show that an immediate 270 bundle is
        # ACKed but produces no 299/282 response, while the bounded ownership-
        # settle path does.  Retain the eager path only as an explicit A/B.
        if os.environ.get("WW3_DEPLOY_ON_PRELOAD", "0") != "1":
            return False
        if getattr(conn, "_post_preload_deploy_done", False):
            return False
        conn._post_preload_deploy_done = True
        # The native controller emits this callback only after local weapon
        # preload has completed; sending it earlier leaves the client in the
        # briefing state and can produce a property mismatch.
        self.maybe_send_before_spectator_return(s, addr, conn, force=True)
        self.maybe_send_auto_deploy(s, addr, conn, force=True)
        self.maybe_send_player_respawned(s, addr, conn, force=True)
        self.maybe_send_game_started(s, addr, conn, force=True)
        self.maybe_send_domination_match_started(s, addr, conn, force=True)
        self.maybe_send_camera_rebind(s, addr, conn)
        print("[match]       *** post-preload deploy transition replayed (Server_OnClientPreloadWeaponsFinished) ***")
        return True

    def maybe_finalize_post_spectator(self, s, addr, conn):
        """Complete spawn after the client confirms it left spectator mode.

        Handle 282 (``Server_OnPostSpectatorReturnToGame``) is the native
        ordering barrier.  Replaying respawn/camera callbacks before it is
        harmless but semantically early; once it arrives, re-issue the captured
        post-possession state exactly once in gameplay order.
        """
        if getattr(conn, "_post_spectator_finalize_done", False):
            return False
        conn._post_spectator_finalize_done = True
        self.maybe_force_gamestate_inprogress(s, addr, conn, force=True)
        self.maybe_replay_captured_gamestate_tail(s, addr, conn, force=True)
        self.maybe_send_post_spectator_wam_sync_kick(s, addr, conn)
        if os.environ.get("WW3_POST_SPECTATOR_CAM_IM_REBIND", "0") == "1":
            self.maybe_send_cam_im_resend(s, addr, conn, force=True)
        self.maybe_send_post_pawn_pc_state(s, addr, conn, force=True)
        self.maybe_send_player_respawned(s, addr, conn, force=True)
        self.maybe_send_game_started(s, addr, conn, force=True)
        self.maybe_send_domination_match_started(s, addr, conn, force=True)
        self.maybe_send_infantry_widget(s, addr, conn, force=True)
        self.maybe_send_camera_rebind(s, addr, conn, force=True)
        self.maybe_send_final_view_target_only(s, addr, conn, force=True)
        if os.environ.get("WW3_POST_SPECTATOR_ONLINE_SESSION", "0") == "1":
            self.maybe_send_online_session_started(s, addr, conn, force=True)
        print("[match]       *** post-spectator gameplay finalized (Server_OnPostSpectatorReturnToGame) ***")
        return True

    def maybe_send_post_spectator_wam_sync_kick(self, s, addr, conn):
        """Replay one new WAM generation after the client's spectator barrier."""
        if os.environ.get("WW3_POST_SPECTATOR_WAM_SYNC_KICK", "0") != "1":
            return False
        if getattr(conn, "_post_spectator_wam_sync_kick_done", False):
            return False

        batch = []
        sizes = []
        for netguid in (WAM_EARLY_CH4, WAM_EARLY_CH5,
                        WAM_SECONDARY, WAM_PRIMARY):
            if netguid in (WAM_EARLY_CH4, WAM_EARLY_CH5):
                bits = build_wam_early_empty_parts_resend_bits(
                    netguid, batch_id=3)
            else:
                bits = build_wam_strip_resend_bits(netguid, batch_id=3)
            payload = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    payload[i >> 3] |= 1 << (i & 7)
            ch = WAM_CHANNELS[netguid]
            batch.append(cc.make_bunch(
                len(bits), bytes(payload), ch_index=ch,
                ch_seq=self.next_chan_seq(conn, ch),
                ch_type=cc.CHTYPE_ACTOR, bOpen=0, bReliable=1))
            sizes.append(f"{netguid}@{ch}:{len(bits)}")

        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=batch,
                         audit_tag="post-spectator WAM BatchID=3")
        conn._post_spectator_wam_sync_kick_done = True
        print("[match]       *** post-spectator WAM SYNC KICK BatchID=3 "
              f"({', '.join(sizes)}, WW3_POST_SPECTATOR_WAM_SYNC_KICK) ***")
        return True

    def maybe_replay_captured_gamestate_tail(self, s, addr, conn, force=False):
        """Replay the capture's only two late GameState property updates.

        Unlike the experimental h20/h21 MatchState writer, these are bit-exact
        source bunches (215 and 275) from the same ch53 actor used by the
        ownership bootstrap.  Keep this opt-in and single-shot even when a
        finalizer requests ``force``; repeating reliable RepLayout updates adds
        no diagnostic value.
        """
        if os.environ.get("WW3_REPLAY_GAMESTATE_TAIL_AFTER_SPECTATOR", "0") != "1":
            return False
        if getattr(conn, "_captured_gamestate_tail_done", False):
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            stream = json.load(open(os.path.join(here, "real_replay_stream.json"), encoding="utf-8"))
            specs = []
            for src in (215, 275):
                spec = dict(stream[src])
                if int(spec.get("chIndex", -1)) != 53:
                    raise ValueError(f"source {src} is not GameState ch53")
                spec["_src_idx"] = src
                specs.append(spec)
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! captured GameState tail unavailable: {exc}")
            return False
        self.flush_acks(s, addr, conn)
        for spec in specs:
            self.send_packet(s, addr, conn,
                             bunch=self.build_replay_bunch(conn, spec),
                             audit_tag=f"post-spectator captured GameState src={spec['_src_idx']}")
        conn._captured_gamestate_tail_done = True
        print("[match]       *** captured GameState tail replayed after spectator "
              "(src215 + src275, bit-exact) ***")
        return True

    def maybe_force_gamestate_inprogress(self, s, addr, conn, force=False):
        """Trigger AGameState's native match-start OnRep after deployment."""
        if getattr(conn, "_gamestate_inprogress_done", False) and not force:
            return False
        if os.environ.get("WW3_FORCE_GAMESTATE_INPROGRESS", "0") != "1":
            if not force:
                conn._gamestate_inprogress_done = True
            return False
        bits = build_gamestate_inprogress_bits(elapsed_time=1)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._gamestate_inprogress_done = True
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=53,
            ch_seq=self.next_chan_seq(conn, 53), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-spectator GameState InProgress")
        print("[match]       *** GameState MatchState=InProgress, ElapsedTime=1 sent ***")
        return True

    def maybe_accept_character_respawn(self, s, addr, conn):
        """Accept the client's near-squad-leader spawn request once.

        The client sends handle 299 together with its post-spectator callback.
        WW3 expects a status update (234) and a success result (235) before the
        later PlayerRespawned notification.  Reuse the capture's bit-exact spawn
        location/yaw so every parameter after the status enum is grounded.
        """
        if getattr(conn, "_character_respawn_accepted", False):
            return False
        conn._character_respawn_accepted = True
        # No authoritative capture exists for handle 235's parameter layout.
        # The synthetic 64- and 67-bit variants both produce a client-side
        # ReceivePropertiesForRPC mismatch, so keep this diagnostic off unless
        # an explicit framing experiment requests it.
        if os.environ.get("WW3_CHARACTER_RESPAWN_SUCCESS", "0") != "1":
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            boot = json.load(open(os.path.join(here, "ownership_bootstrap.json"),
                                  encoding="utf-8"))
            spec = next(b for b in boot if int(b.get("_src_idx", -1)) == 8
                        and int(b.get("chIndex", -1)) == 2)
            fields = parse_actor_rpc_fields([int(x) for x in spec["payload"]])
            player_params = next(p for h, p in fields if int(h) == 240)
            rpc_specs = ((
                235, build_character_respawn_success_param_bits(player_params, status=1),
                "Client_OnCharacterRespawnRequestSucceeded"),)
        except (OSError, ValueError, StopIteration) as exc:
            print(f"[match]       ! character respawn acceptance unavailable: {exc}")
            return False
        self.flush_acks(s, addr, conn)
        for handle, params, label in rpc_specs:
            bits = build_raw_rpc_bits(handle, params)
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= 1 << (i & 7)
            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                len(bits), bytes(by), ch_index=2,
                ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
                bOpen=0, bReliable=1)], audit_tag=f"post-request {label}")
            print(f"[match]       *** {label} (handle {handle}) sent ***")
        return True

    def maybe_send_online_session_started(self, s, addr, conn, force=False):
        """Notify the client that the replicated online session has started.

        Unreal's PlayerController owns this reliable zero-argument RPC.  A real
        listen/dedicated server emits it as part of the join transition; omitting
        it leaves WW3's online-state machine in LoadingMap even when the pawn and
        level have already loaded.  Keep an opt-out for wire A/B comparisons.
        """
        if getattr(conn, "_online_session_started_rpc_done", False) and not force:
            return False
        if os.environ.get("WW3_CLIENT_START_ONLINE_SESSION", "1") != "1":
            if not force:
                conn._online_session_started_rpc_done = True
            return False
        bits = build_zero_arg_rpc_bits(52)  # PlayerController::ClientStartOnlineSession
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._online_session_started_rpc_done = True
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack ClientStartOnlineSession")
        print("[match]       *** M4: ClientStartOnlineSession (handle 52) sent after possession ***")
        return True

    def maybe_send_player_respawned(self, s, addr, conn, force=False):
        """Replay the captured Client_OnPlayerRespawned RPC after possession.

        The listen-server's source-8 bundle contains this nontrivial RPC between
        camera setup and ClientGameStarted.  Replaying the whole bundle after the
        pawn is acknowledged still leaves the client on the briefing screen, so
        isolate handle 240 while retaining its captured parameter bit payload.
        """
        if getattr(conn, "_player_respawned_rpc_done", False) and not force:
            return False
        if os.environ.get("WW3_CLIENT_PLAYER_RESPAWNED", "1") != "1":
            conn._player_respawned_rpc_done = True
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            boot = json.load(open(os.path.join(here, "ownership_bootstrap.json"), encoding="utf-8"))
            spec = next(b for b in boot if int(b.get("_src_idx", -1)) == 8
                        and int(b.get("chIndex", -1)) == 2)
            fields = parse_actor_rpc_fields([int(x) for x in spec["payload"]])
            params = next(p for h, p in fields if int(h) == 240)
            bits = build_raw_rpc_bits(240, params)
        except (OSError, ValueError, StopIteration) as e:
            if not force:
                conn._player_respawned_rpc_done = True
            print(f"[match]       ! isolated Client_OnPlayerRespawned unavailable: {e}")
            return False
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._player_respawned_rpc_done = True
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack Client_OnPlayerRespawned")
        print(f"[match]       *** M4: isolated Client_OnPlayerRespawned (handle 240) sent "
              f"after possession ({len(bits)} bits) ***")
        return True

    def maybe_send_player_respawned_with_movement_type(self, s, addr, conn, force=False):
        """Send the build's movement-aware respawn callback after possession.

        This build has a second respawn RPC (handle 241) whose extra enum tells the
        client which movement pose to install.  The captured older callback (240)
        contains the same spawn vector/yaw/inventory values; insert the captured
        movement enum at its documented wire position rather than inventing a new
        spawn location.
        """
        if getattr(conn, "_player_respawned_movement_rpc_done", False) and not force:
            return False
        if os.environ.get("WW3_CLIENT_PLAYER_RESPAWNED_MOVEMENT", "0") != "1":
            if not force:
                conn._player_respawned_movement_rpc_done = True
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            boot = json.load(open(os.path.join(here, "ownership_bootstrap.json"), encoding="utf-8"))
            spec = next(b for b in boot if int(b.get("_src_idx", -1)) == 8
                        and int(b.get("chIndex", -1)) == 2)
            fields = parse_actor_rpc_fields([int(x) for x in spec["payload"]])
            params = next(p for h, p in fields if int(h) == 240)
            # FVector_NetQuantize (48 bits), yaw (8 bits), and inventory bool (1 bit),
            # each preceded by its RepLayout send bit: 60 bits total for handle 240.
            if len(params) != 60:
                raise ValueError(f"unexpected handle 240 payload width: {len(params)}")
            # EnumProperty serializes against MAX=10, so UE's SerializeInt uses 4 bits.
            # The enum is the third argument (after the captured location/yaw bits);
            # preserve the captured trailing keep-inventory bit(s) unchanged.
            enum_bits = [(2 >> i) & 1 for i in range(4)]  # EWW3MovementPosition::Stand
            movement_params = list(params[:58]) + enum_bits + list(params[58:])
            bits = build_raw_rpc_bits(241, movement_params)
        except (OSError, ValueError, StopIteration) as e:
            if not force:
                conn._player_respawned_movement_rpc_done = True
            print(f"[match]       ! movement-aware respawn unavailable: {e}")
            return False
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._player_respawned_movement_rpc_done = True
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack Client_OnPlayerRespawnedWithMovementType")
        print(f"[match]       *** M4: isolated Client_OnPlayerRespawnedWithMovementType "
              f"(handle 241, Stand) sent after possession ({len(bits)} bits) ***")
        return True

    def maybe_clear_spectator_waiting(self, s, addr, conn):
        """Clear the controller's spectator-waiting flag after real possession.

        This is gated because the captured listen-server stream does not contain
        handle 49; it is an A/B diagnostic for the persistent briefing overlay.
        """
        if getattr(conn, "_spectator_waiting_clear_done", False):
            return False
        conn._spectator_waiting_clear_done = True
        if os.environ.get("WW3_CLEAR_SPECTATOR_WAITING", "0") != "1":
            return False
        # This native engine RPC serializes its bool directly.  A two-bit
        # presence/value attempt was consumed as one bool plus trailing garbage.
        bits = build_raw_rpc_bits(49, [0])
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack ClientSetSpectatorWaiting(false)")
        print("[match]       *** post-ack ClientSetSpectatorWaiting(false) sent ***")
        return True

    def maybe_send_client_goto_state(self, s, addr, conn):
        """Optionally drive APlayerController's native client state machine."""
        state = os.environ.get("WW3_CLIENT_GOTO_STATE", "")
        if getattr(conn, "_client_goto_state_done", False) or not state:
            return False
        conn._client_goto_state_done = True
        # FName NetSerialize.  Most names use the FString form; UE's built-in
        # state names can instead be encoded as a hardcoded EName index.  Keep
        # the latter behind an explicit diagnostic switch because the index is
        # engine-version dependent (UE4.21 vs newer builds).
        w = GuidWriter()
        w.write_bit(1)                 # RPC property send/present bit
        if os.environ.get("WW3_CLIENT_GOTO_HARDCODED", "0") == "1":
            try:
                hardcoded_index = int(os.environ.get("WW3_CLIENT_GOTO_HARDCODED_INDEX", "320"))
            except ValueError:
                hardcoded_index = 320
            w.write_bit(1)
            w.write_packed(hardcoded_index)
        else:
            w.write_bit(0)
            w.write_fstring(state)
        params = _bits_from_writer(w)
        bits = build_raw_rpc_bits(24, params)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag=f"post-ack ClientGotoState({state})")
        print(f"[match]       *** post-ack ClientGotoState({state}) sent ***")
        return True

    def maybe_send_client_stream_status(self, s, addr, conn, force=False):
        """Optionally request a streamed gameplay level on the client.

        UE4's PlayerController RPC is FName + three booleans + LODIndex.  The
        Kwein level is present in the native map but the client has repeatedly
        logged that its streaming-level object is missing, so keep this behind
        an explicit A/B path rather than changing the normal replay stream.
        """
        path = (os.environ.get("WW3_CLIENT_STREAM_STATUS_PATH", "") or "").strip()
        if not path or (getattr(conn, "_client_stream_status_done", False) and not force):
            return False
        w = GuidWriter()
        w.write_bit(1)                 # RPC property send/present bit
        w.write_bit(0)                 # non-hardcoded FName
        w.write_fstring(path)
        w.write_bit(1)                 # should be loaded
        w.write_bit(1)                 # should be visible
        w.write_bit(1)                 # block on load
        w.write_bits(0, 32)             # LODIndex
        bits = build_raw_rpc_bits(59, _bits_from_writer(w))
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="post-ack ClientUpdateLevelStreamingStatus")
        conn._client_stream_status_done = True
        print(f"[match]       *** post-ack ClientUpdateLevelStreamingStatus({path}) sent ***")
        return True

    def maybe_send_camera_rebind(self, s, addr, conn, force=False):
        """Replay captured view-target/camera RPCs after owned objects are mapped."""
        # A controlled final-view-target run deliberately leaves the capture's
        # ClientSetViewTarget as the last camera mutation.  Do not let a delayed
        # camera retry overwrite it with ClientSetCameraMode/ClientSetRotation.
        if getattr(conn, "_final_view_target_only_done", False):
            return False
        if os.environ.get("WW3_CAMERA_REBIND", "1") != "1":
            if not force:
                conn._camera_rebind_done = True
            return False
        if getattr(conn, "_camera_rebind_done", False) and not force:
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            boot = json.load(open(os.path.join(here, "ownership_bootstrap.json"), encoding="utf-8"))
            spec = next(b for b in boot if int(b.get("_src_idx", -1)) == 8
                        and int(b.get("chIndex", -1)) == 2)
            fields = parse_actor_rpc_fields([int(x) for x in spec["payload"]])
            selected = [(int(h), p) for h, p in fields if int(h) in (50, 45, 11)]
            if not selected:
                raise ValueError("source-8 camera fields missing")
        except (OSError, ValueError, StopIteration) as e:
            conn._camera_rebind_done = True
            print(f"[match]       ! isolated camera rebind unavailable: {e}")
            return False
        self.flush_acks(s, addr, conn)
        labels = {50: "ClientSetViewTarget", 45: "ClientSetCameraMode", 11: "ClientSetRotation"}
        for handle, params in selected:
            bits = build_raw_rpc_bits(handle, params)
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= 1 << (i & 7)
            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                len(bits), bytes(by), ch_index=2,
                ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
                bOpen=0, bReliable=1)], audit_tag=f"post-attachment {labels.get(handle, handle)}")
        conn._camera_rebind_done = True
        print(f"[match]       *** M4: isolated camera rebind sent after attachment "
              f"({', '.join(labels.get(h, str(h)) for h, _ in selected)}) ***")
        return True

    def maybe_send_final_view_target_only(self, s, addr, conn, force=False):
        """Make captured ClientSetViewTarget(Pawn) the final camera mutation.

        This is an opt-in, capture-grounded diagnostic for the persistent
        LoadingMap/briefing state.  Source 8 contains the exact handle-50 payload
        targeting Pawn NetGUID 9372.  Once sent, later full camera rebind retries
        are suppressed so handles 45/11 cannot overwrite the result.
        """
        if os.environ.get("WW3_FINAL_VIEW_TARGET_ONLY", "0") != "1":
            return False
        if getattr(conn, "_final_view_target_only_done", False):
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            boot = json.load(open(os.path.join(here, "ownership_bootstrap.json"), encoding="utf-8"))
            spec = next(b for b in boot if int(b.get("_src_idx", -1)) == 8
                        and int(b.get("chIndex", -1)) == 2)
            fields = parse_actor_rpc_fields([int(x) for x in spec["payload"]])
            params = next(p for h, p in fields if int(h) == 50)
        except (OSError, ValueError, StopIteration) as e:
            print(f"[match]       ! final captured ClientSetViewTarget unavailable: {e}")
            return False
        bits = build_raw_rpc_bits(50, params)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="final captured ClientSetViewTarget")
        conn._final_view_target_only_done = True
        print("[match]       *** final captured ClientSetViewTarget(Pawn 9372) sent; "
              "later camera retries suppressed ***")
        return True

    def maybe_send_post_spawn_finalize_rpcs(self, s, addr, conn, force=False):
        """Replay capture post-spawn finalizers that are safe once possession exists.

        The listen-server source-8 bundle carries ClientFlushLevelStreaming and
        ClientGetServerID after the camera/restart sequence.  They were omitted
        from the isolated transition replay, leaving the dedicated client in
        LoadingMap even though the pawn and streamed level were acknowledged.
        Reuse the exact captured parameter payloads so this remains build-specific
        and does not invent RPC arguments.
        """
        if getattr(conn, "_post_spawn_finalize_done", False) and not force:
            return False
        if os.environ.get("WW3_POST_SPAWN_FINALIZE_RPCS", "1") != "1":
            if not force:
                conn._post_spawn_finalize_done = True
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            boot = json.load(open(os.path.join(here, "ownership_bootstrap.json"), encoding="utf-8"))
            spec = next(b for b in boot if int(b.get("_src_idx", -1)) == 8
                        and int(b.get("chIndex", -1)) == 2)
            fields = parse_actor_rpc_fields([int(x) for x in spec["payload"]])
            selected = [(int(h), p) for h, p in fields if int(h) in (21, 158)]
            if not selected:
                raise ValueError("source-8 finalizer fields missing")
        except (OSError, ValueError, StopIteration) as e:
            if not force:
                conn._post_spawn_finalize_done = True
            print(f"[match]       ! post-spawn finalizers unavailable: {e}")
            return False
        self.flush_acks(s, addr, conn)
        labels = {21: "ClientFlushLevelStreaming", 158: "ClientGetServerID"}
        for handle, params in selected:
            bits = build_raw_rpc_bits(handle, params)
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= 1 << (i & 7)
            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                len(bits), bytes(by), ch_index=2,
                ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
                bOpen=0, bReliable=1)], audit_tag=f"post-spawn {labels.get(handle, handle)}")
        conn._post_spawn_finalize_done = True
        print(f"[match]       *** post-spawn finalizers replayed after possession "
              f"({', '.join(labels.get(h, str(h)) for h, _ in selected)}) ***")
        return True

    def maybe_send_late_transition(self, s, addr, conn, force=False):
        """Replay the captured late gameplay-transition bunch after attachments map."""
        if (self.deploy_after_spectator_enabled()
                and not getattr(conn, "_client_start_spectator", False)):
            # Turn 8 measured source 1934 going out 288 console lines *before*
            # the client sent h310 Server_StartSpectator, so the client restarted
            # and then walked its own flow back into spectator, where it stayed.
            # In the capture the bundle only ever answers a client that is
            # already spectating.  This is the one central hold: it covers every
            # caller -- force=True, the strict fresh-h279 path and the timers --
            # so nothing can consume the one-shot early.
            if not getattr(conn, "_deploy_after_spectator_hold_logged", False):
                conn._deploy_after_spectator_hold_logged = True
                print("[match]       deploy transition held until the client sends "
                      f"h{PC_RPC_START_SPECTATOR} Server_StartSpectator "
                      "(WW3_DEPLOY_AFTER_SPECTATOR)")
            return False
        if self.strict_player_in_game_order_enabled():
            # This central guard covers every timer/post-ACK/post-attachment caller.
            # Even force=True cannot bypass the strict ordering experiment.
            if not getattr(conn, "_strict_post_profile_h279_ready", False):
                return False
            if getattr(conn, "_strict_transition_done", False):
                return False
        if getattr(conn, "_late_transition_done", False) and not force:
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            stream = json.load(open(os.path.join(here, "real_replay_stream.json"), encoding="utf-8"))
            spec = dict(stream[STRICT_TRANSITION_SOURCE])
        except (OSError, ValueError, IndexError) as e:
            conn._late_transition_done = True
            print(f"[match]       ! late transition unavailable: {e}")
            return False
        if self.strict_player_in_game_order_enabled():
            payload = spec.get("payload", "")
            if (int(spec.get("chIndex", -1)) != 2
                    or int(spec.get("bits", -1)) != STRICT_TRANSITION_BITS
                    or int(spec.get("bOpen", 0)) != 0
                    or int(spec.get("bClose", 0)) != 0
                    or int(spec.get("bReliable", 0)) != 1
                    or int(spec.get("bPartial", 0)) != 0
                    or int(spec.get("bPartialInitial", 0)) != 0
                    or int(spec.get("bPartialFinal", 0)) != 0
                    or int(spec.get("bHasPackageMapExports", 0)) != 0
                    or int(spec.get("bHasMustBeMappedGUIDs", 0)) != 0
                    or int(spec.get("chType", -1)) != cc.CHTYPE_ACTOR
                    or len(payload) != STRICT_TRANSITION_BITS
                    or hashlib.sha256(payload.encode("ascii")).hexdigest()
                    != STRICT_TRANSITION_SHA256):
                print("[match]       ! strict source1934 identity mismatch; refusing")
                conn._strict_transition_failed = True
                return False
            spec["chIndex"] = int(getattr(conn, "pc_channel", 2))
            spec["_src_idx"] = STRICT_TRANSITION_SOURCE
        bunch = self.build_replay_bunch(conn, spec)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[bunch], audit_tag="post-attachment late transition")
        conn._late_transition_done = True
        if self.strict_player_in_game_order_enabled():
            conn._strict_transition_done = True
        print("[match]       *** M4: captured late transition replayed (stream index 1934) ***")
        return True

    def maybe_send_pc_set_pawn(self, s, addr, conn, force=False):
        """Experiment #3B: set APlayerController::Pawn = 9372 right before ClientRestart.

        The ownership bootstrap already replays the capture's PC RepLayout carrying this
        property (src=13), but that goes out *before* ch3 opens. This re-states the binding
        with the pawn channel already open, immediately ahead of the Restart RPC.
        """
        if os.environ.get("WW3_PC_SET_PAWN", "0") != "1":
            return False
        if getattr(conn, "_pc_set_pawn_done", False) and not force:
            return False
        conn._pc_set_pawn_done = True
        pawn_bits = build_pc_set_pawn_bits(PAWN_NETGUID)
        ps_bits = build_pc_set_playerstate_bits(PS_NETGUID)
        payloads = []
        for bits in (ps_bits, pawn_bits):
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= (1 << (i & 7))
            payloads.append((len(bits), bytes(by)))
        self.flush_acks(s, addr, conn)
        bunches = [cc.make_bunch(
            nbits, data, ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1) for nbits, data in payloads]
        self.send_packet(s, addr, conn, bunches=bunches)
        print(f"[match]       *** M4: PC RepLayout PlayerState (handle {PC_REP_HANDLE_PLAYERSTATE}) "
              f"-> NetGUID {PS_NETGUID}; Pawn (handle {pc_pawn_handle()}) "
              f"-> NetGUID {PAWN_NETGUID} sent before ClientRestart "
              f"({sum(n for n, _ in payloads)} bits, WW3_PC_SET_PAWN) ***")
        return True

    def maybe_send_ps_set_playerchar(self, s, addr, conn, force=False):
        """Re-state AWW3PlayerStateBase::PlayerCharacter = 9372 on ch7 before ClientRestart.

        Ownership bootstrap already replays the capture PS open with this property, but
        that bunch is sent before ch3 maps NetGUID 9372. Checklist `PlayerState` stayed
        false after pawn→PS synth A/B; this is the PS→pawn reverse bind once the pawn
        exists. Off by default (`WW3_PS_SET_PLAYERCHAR=1`).
        """
        if os.environ.get("WW3_PS_SET_PLAYERCHAR", "0") != "1":
            return False
        if getattr(conn, "_ps_set_playerchar_done", False) and not force:
            return False
        conn._ps_set_playerchar_done = True
        bits = build_ps_set_playerchar_bits(PAWN_NETGUID)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= (1 << (i & 7))
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=7,
            ch_seq=self.next_chan_seq(conn, 7), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)])
        print(f"[match]       *** M4: PS RepLayout PlayerCharacter "
              f"(handle {ps_playerchar_handle()}) -> NetGUID {PAWN_NETGUID} "
              f"on ch7 before ClientRestart "
              f"({len(bits)} bits, WW3_PS_SET_PLAYERCHAR) ***")
        return True

    def maybe_send_pawn_synth_props(self, s, addr, conn, force=False):
        """Set APawn::PlayerState / APawn::Controller on ch3, right before ClientRestart.

        The four remaining `Client Synchronization` falses all hang off the pawn, and
        `PlayerState` is the one we can address directly: the capture's ch3 actor block
        only ever carries RemoteRole and the ch3 open has no actor block at all, so
        nothing we replay ever tells the client which PlayerState its pawn belongs to.

        This is the first *synthesised* (not capture-replayed) property block we send, so
        it stays off by default. Prefer `WW3_PAWN_SYNTH_IN_OPEN=1` (inject into the open
        bunch before PostNetInit); this post-open path is the A/B control. Encoding
        validated by `_decode_all_blocks.py` / `_verify_synth_block.py`.
        """
        if os.environ.get("WW3_PAWN_SYNTH_PROPS", "0") != "1":
            return False
        if os.environ.get("WW3_PAWN_SYNTH_IN_OPEN", "0") == "1":
            return False  # already (or about to be) injected into the open
        if getattr(conn, "_pawn_synth_props_done", False) and not force:
            return False
        conn._pawn_synth_props_done = True
        bits = build_pawn_bind_props_bits(PS_NETGUID, PC_NETGUID)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= (1 << (i & 7))
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=3,
            ch_seq=self.next_chan_seq(conn, 3), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)])
        print(f"[match]       *** M4: pawn RepLayout PlayerState(17)->{PS_NETGUID} "
              f"Controller(18)->{PC_NETGUID} on ch3 before ClientRestart "
              f"({len(bits)} bits, WW3_PAWN_SYNTH_PROPS) ***")
        return True

    def _inv_attach_gate_ready(self, conn):
        """True when clothing + ch86/87 opens are ACKED, or ACK-wait timed out.

        Used by WW3_CAM_IM_AFTER_ACK / WW3_WPN_ATTACH. Without AFTER_ACK the gate is
        immediately open (caller still decides whether to send). Timeout falls back so a
        missing ack-audit tag cannot stall the experiment forever.
        """
        if not cam_im_after_ack_enabled():
            return True, "immediate"
        cloth = getattr(conn, "_clothing_acked", False)
        c85 = getattr(conn, "_ch85_acked", False)
        c86 = getattr(conn, "_ch86_acked", False)
        c87 = getattr(conn, "_ch87_acked", False)
        if cloth and c85 and c86 and c87:
            return True, "acks"
        owned_t = getattr(conn, "_ownership_done_t", None)
        if owned_t is None:
            # ownership_done just flipped — stamp now for timeout math.
            if getattr(conn, "_ownership_done", False):
                conn._ownership_done_t = time.time()
                owned_t = conn._ownership_done_t
            else:
                return False, "ownership-pending"
        waited = time.time() - owned_t
        timeout = cam_im_ack_timeout_s()
        if waited >= timeout:
            return True, (f"timeout {waited:.1f}s "
                          f"(cloth={int(cloth)} ch85={int(c85)} "
                          f"ch86={int(c86)} ch87={int(c87)})")
        return False, (f"waiting acks cloth={int(cloth)} ch85={int(c85)} "
                       f"ch86={int(c86)} ch87={int(c87)} "
                       f"t={waited:.1f}/{timeout:.1f}s")

    def maybe_send_cam_im_resend(self, s, addr, conn, force=False):
        """Re-send clothing CAM/IM (or full clothing) after local weapons map.

        Clothing src 212–213 already carries these, but they trail dynamic hat/chest
        spawns in the same bunch — and IM's WeaponsPreloadRequest refs 9410/9412 which
        only open later (ch86/87). `WW3_INV_ATTACH=1` adds those opens to the bootstrap
        and enables this resend so OnRep fires once the GUIDs resolve. Off unless set.

        `WW3_CAM_IM_AFTER_ACK=1` holds the resend until ack-audit reports clothing +
        ch86/87 opens ACKED (or WW3_CAM_IM_ACK_TIMEOUT_S after ownership_done). Live
        INV_ATTACH showed resend+Restart ~1.4s *before* those ACKs landed.

        `WW3_CLOTHING_RESEND=1` re-plays the full clothing partial chain (exports +
        hat 9404 + chest 9406 + CAM + IM) instead of CAM/IM-only. CAM's
        ReplicatedAttachments[] refs 9404/9406 — without them OnRep cannot finish
        CharacterAttachments OnSynchronized.

        `WW3_CAM_STRIP_CATALOG=1` follows with a CAM-only block: empty AttachmentIds
        + empty skins Parts, BatchID=2, still refs 9404/9406. Drops SoftClass waits
        on the 9 non-channel catalog IDs + 5 skin SoftClasses.
        """
        if not inv_attach_enabled():
            return False
        if getattr(conn, "_cam_im_resend_done", False) and not force:
            return False
        if not getattr(conn, "_ownership_done", False):
            return False
        # Attachment channels are intentionally withheld during the possession
        # window.  Do not emit CAM/IM follow-ups (which reference ch85-88) while
        # their OPEN chains are still deferred; those reliable bunches would be
        # the first traffic the client sees on an unopened channel.
        if (os.environ.get("WW3_SKIP_ATTACHMENTS") == "1"
                and not getattr(conn, "_deferred_attachments_released", False)):
            return False
        ready, why = (True, "post-spectator") if force else self._inv_attach_gate_ready(conn)
        if not ready:
            # Log once so the wait is visible without spamming every keepalive tick.
            if not getattr(conn, "_cam_im_wait_logged", False):
                conn._cam_im_wait_logged = True
                print(f"[match]       *** M4: CAM/IM resend held ({why}, "
                      f"WW3_CAM_IM_AFTER_ACK) ***")
            return False
        conn._cam_im_resend_done = True
        self.flush_acks(s, addr, conn)
        if clothing_resend_enabled():
            bunches = []
            sizes = []
            for spec in clothing_resend_specs():
                bunch = self.build_replay_bunch(conn, spec)
                bunches.append(bunch)
                sizes.append(f"src={spec['_src_idx']}:{spec['bits']}")
            self.send_packet(s, addr, conn, bunches=bunches,
                             audit_tag="post-attachment clothing FULL src=212/213")
            print(f"[match]       *** M4: clothing FULL resend ({', '.join(sizes)}, "
                  f"gate={why}, WW3_CLOTHING_RESEND"
                  f"{'+AFTER_ACK' if cam_im_after_ack_enabled() else ''}) ***")
        else:
            bits = build_cam_im_resend_bits()
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= (1 << (i & 7))
            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                len(bits), bytes(by), ch_index=3,
                ch_seq=self.next_chan_seq(conn, 3), ch_type=cc.CHTYPE_ACTOR,
                bOpen=0, bReliable=1)])
            print(f"[match]       *** M4: CAM({CAM_NETGUID})+IM({IM_NETGUID}) resend on ch3 "
                  f"({len(bits)} bits, gate={why}, WW3_INV_ATTACH"
                  f"{'+AFTER_ACK' if cam_im_after_ack_enabled() else ''}) ***")
        if cam_strip_catalog_enabled():
            strip = build_cam_strip_resend_bits(batch_id=2)
            by = bytearray((len(strip) + 7) // 8)
            for i, bit in enumerate(strip):
                if bit:
                    by[i >> 3] |= (1 << (i & 7))
            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                len(strip), bytes(by), ch_index=3,
                ch_seq=self.next_chan_seq(conn, 3), ch_type=cc.CHTYPE_ACTOR,
                bOpen=0, bReliable=1)])
            print(f"[match]       *** M4: CAM STRIP catalog (BatchID=2, "
                  f"AttachmentIds=[], skins=[], keep 9404+9406, "
                  f"{len(strip)} bits, WW3_CAM_STRIP_CATALOG) ***")
        return True

    def maybe_send_softclass_warm_export(self, s, addr, conn) -> bool:
        """Package-map Mag/Rail SoftClass BP_WP_* on ch3 before early SoftClass OnRep.

        ``WW3_WAM_SOFTCLASS_WARM_EXPORT=1`` — independent of SoftClass catalog rewrite
        so hist074114 native SoftClass opens still fire. Export-only (no stably=0
        BP_WP_* content) — avoids weapon-channel CLOSE. Marks done even on empty
        specs so we never re-enter.
        """
        if getattr(conn, "_softclass_warm_export_done", False):
            return False
        if not wam_softclass_warm_export_enabled():
            return False
        # Require pawn channel open so package-map exports land on a live actor ch.
        if not getattr(conn, "pawn_sent", False):
            return False
        uniq = list(collect_wam_softclass_warm_export_specs())
        conn._softclass_warm_export_done = True
        if not uniq:
            print("[match]       *** M4: SoftClass WARM EXPORT skipped "
                  "(no Mag/Rail specs, WW3_WAM_SOFTCLASS_WARM_EXPORT) ***")
            return False
        host = 3
        exp_bits = build_wam_attach_export_bits(tuple(uniq))
        exp_by = bytearray((len(exp_bits) + 7) // 8)
        for i, bit in enumerate(exp_bits):
            if bit:
                exp_by[i >> 3] |= (1 << (i & 7))
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(exp_bits), bytes(exp_by), ch_index=host,
            ch_seq=self.next_chan_seq(conn, host),
            ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1, bHasPackageMapExports=1)])
        print(f"[match]       *** M4: SoftClass WARM EXPORT "
              f"(host=ch{host} classes={len(uniq)} bits={len(exp_bits)}, "
              f"before early SoftClass OnRep, WW3_WAM_SOFTCLASS_WARM_EXPORT) ***")
        return True

    def maybe_send_wpn_attach_resend(self, s, addr, conn):
        """Re-send WeaponAttachmentManager RepLayout from local weapon opens.

        Capture fact: ch86/87 opens already carry WAM stably-named payloads (9418=505,
        9426=457) — follow-up bunches are ammo/FireType, not more WAM. This resend gives
        OnRep another shot after the opens ACK, under `WW3_WPN_ATTACH=1`. Shares the
        CAM_IM_AFTER_ACK gate when that flag is set.

        `WW3_WAM_STRIP_CATALOG=1` also strips WAM inside open FINALs at send time
        (src 15/17/258/260 → ch4/5/86/87), then follows the ACK gate with BatchID=2
        stripped WAM-only blocks on those channels. Empty AttachmentIds + empty
        skins Parts; MainId omitted (capture-faithful — writing MainId=0 arms
        MainSkinLoadedClass SoftClass). Optional WW3_WAM_SPAWN_ATTACH exports +
        spawns real BP_WP_* UObject attachments (CAM hat/chest pattern) and puts
        those NetGUIDs in ReplicatedAttachments[]. Capture never opens Mag/Rail
        channels (SoftClass-only); weapon-ch stably=0 CLOSES — use
        WW3_WAM_SPAWN_HOST=pawn to put content on ch3. WW3_WAM_KEEP_DYNAMIC is the
        obsolete FireType keep (default off). Drops SoftClass waits on capture
        catalog IDs — including SoftClass id 4606 armed by early ownership Glocks
        when only INV_ATTACH WAMs were stripped.
        """
        if not wpn_attach_enabled():
            return False
        if getattr(conn, "_wpn_attach_resend_done", False):
            return False
        if not getattr(conn, "_ownership_done", False):
            return False
        # Keep generated WAM strip/reinforce bunches behind the same deferred
        # channel barrier as the captured attachment OPENs.
        if (os.environ.get("WW3_SKIP_ATTACHMENTS") == "1"
                and not getattr(conn, "_deferred_attachments_released", False)):
            return False
        ready, why = self._inv_attach_gate_ready(conn)
        if not ready:
            if not getattr(conn, "_wpn_attach_wait_logged", False):
                conn._wpn_attach_wait_logged = True
                print(f"[match]       *** M4: WAM resend held ({why}, WW3_WPN_ATTACH) ***")
            return False
        self.flush_acks(s, addr, conn)
        # Capture WAM SoftClass wait: catalog AttachmentIds, no ReplicatedAttachments.
        # When stripping, skip the capture-faithful resend — re-sending the full
        # catalog re-arms ItemDatabase SoftClass loads that strip cannot cancel.
        # Opens are rewritten empty at send time; post-ACK BatchID=2 strip reinforces.
        try:
            if wam_strip_catalog_enabled():
                # SoftClass offline: package-map export SoftClass BP_WP_* paths BEFORE
                # post-ACK SoftClass AttachmentIds OnRep. Export alone is safe (no CLOSE);
                # stably=0 content is NOT sent here. ItemDatabase SoftClass async can
                # then resolve against already-imported paths.
                if (wam_softclass_catalog_enabled() and wam_softclass_export_enabled()
                        and not wam_spawn_attach_enabled()):
                    # Export only SoftClass ids for active MODE (mag/min/full).
                    uniq = list(collect_wam_softclass_export_specs())
                    if uniq:
                        host = 3  # pawn ch — same host as clothing exports
                        exp_bits = build_wam_attach_export_bits(tuple(uniq))
                        exp_by = bytearray((len(exp_bits) + 7) // 8)
                        for i, bit in enumerate(exp_bits):
                            if bit:
                                exp_by[i >> 3] |= (1 << (i & 7))
                        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                            len(exp_bits), bytes(exp_by), ch_index=host,
                            ch_seq=self.next_chan_seq(conn, host),
                            ch_type=cc.CHTYPE_ACTOR,
                            bOpen=0, bReliable=1, bHasPackageMapExports=1)])
                        print(f"[match]       *** M4: WAM SoftClass EXPORT "
                              f"(host=ch{host} mode={wam_softclass_mode()} "
                              f"classes={len(uniq)} bits={len(exp_bits)}, "
                              f"WW3_WAM_SOFTCLASS_EXPORT) ***")
                # Optional: spawn real BP_WP_* before strip refs them (CAM pattern).
                # Class NetGUIDs are connection-global — export each static class ONCE.
                # host=pawn: all export+content on ch3 (like hat/chest); host=weapon:
                # per-WAM actor ch (known CLOSE).
                if wam_spawn_attach_enabled():
                    payload_mode = wam_spawn_payload_mode()
                    do_export = wam_spawn_export_enabled()
                    do_content = wam_spawn_content_enabled()
                    if wam_spawn_host_is_shared():
                        specs = collect_wam_spawn_specs()
                        host = wam_spawn_host_ch()
                        exp_note = "export=skip"
                        if specs and do_export:
                            exp_bits = build_wam_attach_export_bits(specs)
                            exp_by = bytearray((len(exp_bits) + 7) // 8)
                            for i, bit in enumerate(exp_bits):
                                if bit:
                                    exp_by[i >> 3] |= (1 << (i & 7))
                            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                                len(exp_bits), bytes(exp_by), ch_index=host,
                                ch_seq=self.next_chan_seq(conn, host),
                                ch_type=cc.CHTYPE_ACTOR,
                                bOpen=0, bReliable=1, bHasPackageMapExports=1)])
                            exp_note = f"export={len(exp_bits)}"
                        dyns = tuple(att.dyn_netguid for att in specs)
                        spawn_n = 0
                        if specs and do_content:
                            spawn_bits = build_wam_attach_spawn_bits(specs)
                            spawn_n = len(spawn_bits)
                            sp_by = bytearray((spawn_n + 7) // 8)
                            for i, bit in enumerate(spawn_bits):
                                if bit:
                                    sp_by[i >> 3] |= (1 << (i & 7))
                            self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                                spawn_n, bytes(sp_by), ch_index=host,
                                ch_seq=self.next_chan_seq(conn, host),
                                ch_type=cc.CHTYPE_ACTOR,
                                bOpen=0, bReliable=1)])
                        print(f"[match]       *** M4: WAM SPAWN BP_WP_* "
                              f"(host=ch{host} shared dyn={list(dyns)}, "
                              f"{exp_note} spawn={spawn_n} bits "
                              f"payload={payload_mode} keep="
                              f"{int(wam_spawn_strip_keep_enabled())}, "
                              f"WW3_WAM_SPAWN_ATTACH) ***")
                    else:
                        exported_classes: set[int] = set()
                        for netguid in wam_spawn_target_netguids():
                            specs = wam_spawn_specs_for(netguid)
                            if not specs:
                                continue
                            ch = wam_spawn_host_ch(WAM_CHANNELS[netguid])
                            exp_note = "export=skip"
                            if do_export:
                                new_specs = [
                                    s for s in specs
                                    if s.class_netguid not in exported_classes
                                ]
                                if new_specs:
                                    exp_bits = build_wam_attach_export_bits(new_specs)
                                    exp_by = bytearray((len(exp_bits) + 7) // 8)
                                    for i, bit in enumerate(exp_bits):
                                        if bit:
                                            exp_by[i >> 3] |= (1 << (i & 7))
                                    self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                                        len(exp_bits), bytes(exp_by), ch_index=ch,
                                        ch_seq=self.next_chan_seq(conn, ch),
                                        ch_type=cc.CHTYPE_ACTOR,
                                        bOpen=0, bReliable=1, bHasPackageMapExports=1)])
                                    for att in new_specs:
                                        exported_classes.add(att.class_netguid)
                                    exp_note = f"export={len(exp_bits)}"
                                else:
                                    exp_note = "export=0(reuse)"
                            dyns = tuple(att.dyn_netguid for att in specs)
                            spawn_n = 0
                            if do_content:
                                spawn_bits = build_wam_attach_spawn_bits(specs)
                                spawn_n = len(spawn_bits)
                                sp_by = bytearray((spawn_n + 7) // 8)
                                for i, bit in enumerate(spawn_bits):
                                    if bit:
                                        sp_by[i >> 3] |= (1 << (i & 7))
                                self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                                    spawn_n, bytes(sp_by), ch_index=ch,
                                    ch_seq=self.next_chan_seq(conn, ch),
                                    ch_type=cc.CHTYPE_ACTOR,
                                    bOpen=0, bReliable=1)])
                            print(f"[match]       *** M4: WAM SPAWN BP_WP_* "
                                  f"(wam={netguid} ch{ch} dyn={list(dyns)}, "
                                  f"{exp_note} spawn={spawn_n} bits "
                                  f"payload={payload_mode} keep="
                                  f"{int(wam_spawn_strip_keep_enabled())}, "
                                  f"WW3_WAM_SPAWN_ATTACH) ***")
                strip_batch = []
                strip_sizes = []
                strip_targets = wam_strip_target_netguids()
                for netguid in strip_targets:
                    bits = build_wam_strip_resend_bits(netguid, batch_id=2)
                    by = bytearray((len(bits) + 7) // 8)
                    for i, bit in enumerate(bits):
                        if bit:
                            by[i >> 3] |= (1 << (i & 7))
                    ch = WAM_CHANNELS[netguid]
                    strip_batch.append(cc.make_bunch(
                        len(bits), bytes(by), ch_index=ch,
                        ch_seq=self.next_chan_seq(conn, ch), ch_type=cc.CHTYPE_ACTOR,
                        bOpen=0, bReliable=1))
                    strip_sizes.append(f"{netguid}@{ch}:{len(bits)}")
                self.send_packet(s, addr, conn, bunches=strip_batch)
                open_n = len(getattr(conn, "_wam_open_strip_logged", set()) or ())
                open_total = len(wam_open_strip_srcs())
                skins_note = "skins=[]"
                if wam_spawn_strip_keep_enabled():
                    keep_note = "spawn BP_WP_* ReplicatedAttachments"
                elif wam_spawn_attach_enabled():
                    keep_note = "spawn sent, strip keep off"
                elif wam_keep_clothing_enabled():
                    keep_note = "keep clothing 9404+9406"
                elif wam_keep_dynamic_enabled():
                    keep_note = "keep dynamic att"
                elif wam_softclass_catalog_enabled():
                    if wam_softclass_open_only():
                        keep_note = (
                            f"SoftClass {wam_softclass_mode()} open-only "
                            f"(post-ACK empty)"
                        )
                    elif wam_softclass_keep_skins():
                        keep_note = (
                            f"SoftClass {wam_softclass_mode()} keep-skins "
                            f"(capture skins/MainId)"
                        )
                        skins_note = "skins/MainId kept"
                    else:
                        keep_note = f"SoftClass {wam_softclass_mode()} AttachmentIds"
                else:
                    keep_note = "no keep/MainId"
                print(f"[match]       *** M4: WAM STRIP catalog (BatchID=2, "
                      f"{skins_note}, {keep_note}, "
                      f"{', '.join(strip_sizes)} bits, WW3_WAM_STRIP_CATALOG, "
                      f"open_strip={open_n}/{open_total}, no full resend, gate={why}) ***")
                # hist STRIP_CHANNELS=inv leaves early SoftClass WAMs native with
                # Parts 0xFFFF. SoftClass CreateAttachment completes but Check never
                # re-enters. BatchID=2 SoftClass+empty-Parts reinforce on ch4/5.
                if wam_early_empty_parts_reinforce_enabled():
                    early_batch = []
                    early_sizes = []
                    for netguid in (WAM_EARLY_CH4, WAM_EARLY_CH5):
                        bits = build_wam_early_empty_parts_resend_bits(
                            netguid, batch_id=2)
                        by = bytearray((len(bits) + 7) // 8)
                        for i, bit in enumerate(bits):
                            if bit:
                                by[i >> 3] |= (1 << (i & 7))
                        ch = WAM_CHANNELS[netguid]
                        early_batch.append(cc.make_bunch(
                            len(bits), bytes(by), ch_index=ch,
                            ch_seq=self.next_chan_seq(conn, ch),
                            ch_type=cc.CHTYPE_ACTOR,
                            bOpen=0, bReliable=1))
                        early_sizes.append(f"{netguid}@{ch}:{len(bits)}")
                    self.send_packet(s, addr, conn, bunches=early_batch)
                    print(f"[match]       *** M4: EARLY SoftClass empty-Parts "
                          f"reinforce (BatchID=2, SoftClass ids kept, skins=[], "
                          f"{', '.join(early_sizes)} bits, "
                          f"WW3_WAM_EARLY_EMPTY_PARTS_REINFORCE) ***")
                    # Optional second generation bump.  The client can apply the
                    # BatchID=2 reinforce without re-entering its attachment
                    # synchronization check; a genuinely new replicated value is
                    # the safest wire-level way to test that hypothesis.  Keep this
                    # opt-in because it changes the normal capture-faithful stream.
                    if os.environ.get("WW3_WAM_SYNC_KICK", "0") == "1":
                        kick_batch = []
                        kick_sizes = []
                        for netguid in (WAM_EARLY_CH4, WAM_EARLY_CH5,
                                         WAM_SECONDARY, WAM_PRIMARY):
                            if netguid in (WAM_EARLY_CH4, WAM_EARLY_CH5):
                                kb = build_wam_early_empty_parts_resend_bits(
                                    netguid, batch_id=3)
                            else:
                                kb = build_wam_strip_resend_bits(
                                    netguid, batch_id=3)
                            kby = bytearray((len(kb) + 7) // 8)
                            for i, bit in enumerate(kb):
                                if bit:
                                    kby[i >> 3] |= (1 << (i & 7))
                            kch = WAM_CHANNELS[netguid]
                            kick_batch.append(cc.make_bunch(
                                len(kb), bytes(kby), ch_index=kch,
                                ch_seq=self.next_chan_seq(conn, kch),
                                ch_type=cc.CHTYPE_ACTOR,
                                bOpen=0, bReliable=1))
                            kick_sizes.append(f"{netguid}@{kch}:{len(kb)}")
                        self.send_packet(s, addr, conn, bunches=kick_batch)
                        print(f"[match]       *** M4: WAM SYNC KICK BatchID=3 "
                              f"({', '.join(kick_sizes)}, WW3_WAM_SYNC_KICK) ***")
            else:
                batch = []
                sizes = []
                for netguid in (WAM_SECONDARY, WAM_PRIMARY):
                    bits = build_wam_resend_bits(netguid)
                    by = bytearray((len(bits) + 7) // 8)
                    for i, bit in enumerate(bits):
                        if bit:
                            by[i >> 3] |= (1 << (i & 7))
                    ch = WAM_CHANNELS[netguid]
                    batch.append(cc.make_bunch(
                        len(bits), bytes(by), ch_index=ch,
                        ch_seq=self.next_chan_seq(conn, ch), ch_type=cc.CHTYPE_ACTOR,
                        bOpen=0, bReliable=1))
                    sizes.append(f"{netguid}@{ch}:{len(bits)}")
                self.send_packet(s, addr, conn, bunches=batch)
                print(f"[match]       *** M4: WAM resend ({', '.join(sizes)} bits, gate={why}, "
                      f"WW3_WPN_ATTACH"
                      f"{'+AFTER_ACK' if cam_im_after_ack_enabled() else ''}) ***")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[match]       ! WAM attach/strip failed (will retry): {e}")
            return False
        conn._wpn_attach_resend_done = True
        return True

    def maybe_send_softclass_post_stub_4606(self, s, addr, conn):
        """Mid-flight SoftClass 4606 finish/skip after Mag NewObject (not open stub).

        Open SoftClass keeps 4606 so Mag*_C_0 can arm. After ACK gate + delay
        (and optional wait-file from heap Mag detect), reinforce early native
        SoftClass WAMs with 4606→151 (or empty SoftClass cancel) so Synchronized
        can complete → WeaponsAttachments. No BP_WP_* stably=0 / no CLOSE.
        """
        if not wam_softclass_post_stub_4606_enabled():
            return False
        if getattr(conn, "_softclass_post_stub_4606_done", False):
            return False
        if not getattr(conn, "_ownership_done", False):
            return False
        # Prefer same clothing+INV ACK gate as WPN_ATTACH when AFTER_ACK is on.
        ready, why = self._inv_attach_gate_ready(conn)
        if not ready:
            if not getattr(conn, "_softclass_post_stub_wait_logged", False):
                conn._softclass_post_stub_wait_logged = True
                print(f"[match]       *** M4: SoftClass POST_STUB 4606 held "
                      f"({why}, WW3_WAM_SOFTCLASS_POST_STUB_4606) ***")
            return False
        now = time.time()
        ready_at = getattr(conn, "_softclass_post_stub_ready_at", None)
        if ready_at is None:
            conn._softclass_post_stub_ready_at = now
            ready_at = now
        delay_s = wam_softclass_post_stub_delay_ms() / 1000.0
        if now < ready_at + delay_s:
            if not getattr(conn, "_softclass_post_stub_delay_logged", False):
                conn._softclass_post_stub_delay_logged = True
                print(f"[match]       *** M4: SoftClass POST_STUB 4606 delay "
                      f"{wam_softclass_post_stub_delay_ms():.0f}ms after gate "
                      f"(wait Mag*_C_0, WW3_WAM_SOFTCLASS_POST_STUB_DELAY_MS) ***")
            return False
        wait_file = wam_softclass_post_stub_wait_file()
        if wait_file:
            path = wait_file
            if not os.path.isabs(path):
                path = os.path.join(LOG_DIR, path)
            if not os.path.isfile(path):
                if not getattr(conn, "_softclass_post_stub_file_logged", False):
                    conn._softclass_post_stub_file_logged = True
                    print(f"[match]       *** M4: SoftClass POST_STUB 4606 waiting "
                          f"file {path} (touch after Mag*_C_0) ***")
                return False
        targets = wam_post_stub_4606_target_netguids()
        if not targets:
            conn._softclass_post_stub_4606_done = True
            print("[match]       *** M4: SoftClass POST_STUB 4606 skip "
                  "(no native SoftClass+4606 targets) ***")
            return False
        mode = wam_softclass_post_stub_mode()
        self.flush_acks(s, addr, conn)
        try:
            batch = []
            sizes = []
            for netguid in targets:
                bits = build_wam_post_stub_4606_resend_bits(
                    netguid, batch_id=2, mode=mode)
                by = bytearray((len(bits) + 7) // 8)
                for i, bit in enumerate(bits):
                    if bit:
                        by[i >> 3] |= (1 << (i & 7))
                ch = WAM_CHANNELS[netguid]
                batch.append(cc.make_bunch(
                    len(bits), bytes(by), ch_index=ch,
                    ch_seq=self.next_chan_seq(conn, ch), ch_type=cc.CHTYPE_ACTOR,
                    bOpen=0, bReliable=1))
                sizes.append(f"{netguid}@{ch}:{len(bits)}")
            self.send_packet(s, addr, conn, bunches=batch)
            print(f"[match]       *** M4: SoftClass POST_STUB 4606 "
                      f"(mode={mode}, {', '.join(sizes)} bits, gate={why}, "
                      f"WW3_WAM_SOFTCLASS_POST_STUB_4606) ***")
            # The empty-catalog/BatchID bump is applied after the normal
            # possession restart.  Re-run the native restart gate only after
            # this wire update has arrived; otherwise LoadingMap never
            # revisits the newly-synchronized attachment managers.  This
            # restart only reasserts the already-mapped PC/PS/pawn graph and
            # does not resend weapon attachment objects.
            if mode in ("empty", "full_empty", "skins_only") and os.environ.get(
                    "WW3_POST_STUB_RESTART", "1") == "1":
                self.maybe_send_post_attachment_restart(s, addr, conn)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[match]       ! SoftClass POST_STUB 4606 failed "
                  f"(will retry): {e}")
            return False
        conn._softclass_post_stub_4606_done = True
        return True

    def maybe_send_ps_rebind(self, s, addr, conn):
        """After NotifyLoadedWorld + full ownership drip: re-send PS + PC RepLayout."""
        if os.environ.get("WW3_PS_REBIND", "1") == "0":
            return False
        if getattr(conn, "_ps_rebind_done", False):
            return False
        if not getattr(conn, "_client_loaded_world", False):
            return False
        if not getattr(conn, "ps_opened", False):
            return False
        # Wait until the ownership bootstrap has finished so the rebind is not
        # interleaved with the streaming pause / pawn / GameState drip.
        if not getattr(conn, "_ownership_done", False):
            return False
        conn._ps_rebind_done = True
        here = os.path.dirname(os.path.abspath(__file__))
        stream = json.load(open(os.path.join(here, "real_replay_stream.json")))
        batch = []
        for idx in rebind_src_indices():
            if idx >= len(stream):
                continue
            spec = sanitize_rebind_spec(dict(stream[idx]))
            spec["_src_idx"] = idx
            spec["_ps_rebind"] = 1
            batch.append(self.build_replay_bunch(conn, spec))
        # Fresh PC RepLayout content block (channel already open — no NewActor).
        rep_bits = build_pc_rep_layout_bunch_bits()
        by = bytearray((len(rep_bits) + 7) // 8)
        for i, bit in enumerate(rep_bits):
            if bit:
                by[i >> 3] |= (1 << (i & 7))
        batch.append(cc.make_bunch(
            len(rep_bits), bytes(by), ch_index=2,
            ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1))
        self.flush_acks(s, addr, conn)
        # Send in small packets to stay under MTU.
        for i in range(0, len(batch), 3):
            self.send_packet(s, addr, conn, bunches=batch[i:i + 3])
        print(f"[match]       *** M4: PS rebind after ownership+NotifyLoadedWorld "
              f"({len(batch)} bunches: PS 20–21 + RPC nudges + PC RepLayout) ***")
        # Pawn is definitely mapped by now — Restart again with MustBeMapped + Retry.
        self.maybe_send_client_restart(s, addr, conn, reason="ps-rebind")
        return True

    def maybe_send_late_ps_rebind(self, s, addr, conn):
        """Opt-in A/B: replay PS/PC bind only after clothing FULL is ACKed.

        The normal PS rebind is intentionally one-shot at ownership completion,
        which precedes deferred clothing.  This diagnostic preserves the exact
        captured source order and follows it with one explicit ClientRestart.
        """
        if os.environ.get("WW3_LATE_PS_REBIND_AFTER_CLOTHING", "0") != "1":
            return False
        if getattr(conn, "_late_ps_rebind_done", False):
            return False
        if not getattr(conn, "_late_ps_rebind_pending", False):
            return False
        if not getattr(conn, "_ownership_done", False):
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            stream = json.load(open(os.path.join(here, "real_replay_stream.json"),
                                    encoding="utf-8"))
            allowed = {20, 21, 3, 4, 9}
            raw_sources = os.environ.get(
                "WW3_LATE_PS_REBIND_SOURCES", "20,21,3,4,9")
            try:
                source_list = [int(x.strip()) for x in raw_sources.split(",") if x.strip()]
            except ValueError:
                raise ValueError("WW3_LATE_PS_REBIND_SOURCES must be comma-separated integers")
            if (not source_list or any(idx not in allowed for idx in source_list)
                    or len(set(source_list)) != len(source_list)):
                raise ValueError(
                    "WW3_LATE_PS_REBIND_SOURCES must be unique subset of 20,21,3,4,9")
            batch = []
            for idx in source_list:
                spec = sanitize_rebind_spec(dict(stream[idx]))
                spec["_src_idx"] = idx
                spec["_late_ps_rebind"] = 1
                batch.append(self.build_replay_bunch(conn, spec))
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! late PS rebind unavailable: {exc}")
            return False
        self.flush_acks(s, addr, conn)
        for i in range(0, len(batch), 3):
            self.send_packet(s, addr, conn, bunches=batch[i:i + 3],
                             audit_tag="late PS/PC rebind capture sources")
        conn._late_ps_rebind_done = True
        conn._late_ps_rebind_pending = False
        # Explicitly send one captured ClientRestart even if the normal restart
        # spray was already consumed by AckPossession(Pawn).
        handles = restart_handles()
        if handles and os.environ.get("WW3_CLIENT_RESTART", "1") != "0":
            bits = build_client_restart_bits(
                restart_pawn_guid(), handle=handles[0], must_be_mapped=False)
            by = bytearray((len(bits) + 7) // 8)
            for i, bit in enumerate(bits):
                if bit:
                    by[i >> 3] |= 1 << (i & 7)
            self.flush_acks(s, addr, conn)
            self.send_packet(
                s, addr, conn,
                bunch=cc.make_bunch(
                    len(bits), bytes(by), ch_index=2,
                    ch_seq=self.next_chan_seq(conn, 2), ch_type=cc.CHTYPE_ACTOR,
                    bOpen=0, bReliable=1),
                audit_tag="late PS/PC rebind ClientRestart")
        sources_note = ",".join(str(idx) for idx in source_list)
        print("[match]       *** late PS/PC rebind after clothing FULL ACK "
              f"(src={sources_note} + ClientRestart; "
              "WW3_LATE_PS_REBIND_AFTER_CLOTHING) ***")
        return True

    @staticmethod
    def strict_player_in_game_order_enabled():
        return os.environ.get("WW3_STRICT_PLAYER_IN_GAME_ORDER", "0") == "1"

    def _load_strict_profile_sync_specs(self, conn):
        """Load and validate the complete captured post-h65 sequence atomically."""
        return self._load_validated_capture_specs(conn, STRICT_PROFILE_SYNC_SPECS,
                                                  "strict profile")

    def _load_validated_capture_specs(self, conn, specs, label):
        """Load a captured S->C bunch sequence atomically, or raise.

        Every field of the bunch header plus a SHA-256 of the whole payload bit
        string is checked, so the experiment fails closed if real_replay_stream.json
        is ever regenerated from a different capture.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        stream = json.load(open(os.path.join(here, "real_replay_stream.json"),
                                encoding="utf-8"))
        pc_channel = int(getattr(conn, "pc_channel", 2))
        validated = []
        for source_index, delay_s, expected_bits, expected_sha in specs:
            source = dict(stream[source_index])
            payload = source.get("payload", "")
            if (int(source.get("chIndex", -1)) != 2
                    or int(source.get("bits", -1)) != expected_bits
                    or int(source.get("bOpen", 0)) != 0
                    or int(source.get("bClose", 0)) != 0
                    or int(source.get("bReliable", 0)) != 1
                    or int(source.get("bPartial", 0)) != 0
                    or int(source.get("bPartialInitial", 0)) != 0
                    or int(source.get("bPartialFinal", 0)) != 0
                    or int(source.get("bHasPackageMapExports", 0)) != 0
                    or int(source.get("bHasMustBeMappedGUIDs", 0)) != 0
                    or int(source.get("chType", -1)) != cc.CHTYPE_ACTOR
                    or len(payload) != expected_bits
                    or hashlib.sha256(payload.encode("ascii")).hexdigest() != expected_sha):
                raise ValueError(f"{label} source {source_index} identity mismatch")
            # The capture's PC is ch2.  Keep the payload bit-exact while adapting only
            # the actor channel should a future bootstrap bind the local PC elsewhere.
            source["chIndex"] = pc_channel
            source["_src_idx"] = source_index
            validated.append((delay_s, source))
        return validated

    @staticmethod
    def profile_prologue_enabled():
        return os.environ.get("WW3_PROFILE_PROLOGUE", "0") == "1"

    @staticmethod
    def profile_prologue_specs():
        """`min` (default) opens the profile list; `full` also fills and finishes it.

        `min` is the two-bunch opener whose only confirmed effect is the client's
        C->S h177.  `full` is every ch2 profile bunch the working server sent
        before the client reported h281/h65, re-paced onto a uniform
        WW3_PROFILE_PROLOGUE_STEP_S grid.
        """
        mode = os.environ.get("WW3_PROFILE_PROLOGUE_MODE", "min").strip().lower()
        if mode not in ("full", "all"):
            return STRICT_PROFILE_PROLOGUE_SPECS
        try:
            step = float(os.environ.get("WW3_PROFILE_PROLOGUE_STEP_S", "0.200"))
        except ValueError:
            step = 0.200
        step = max(0.0, step)
        return tuple(
            (source, n * step, bits, digest)
            for n, (source, _delay, bits, digest)
            in enumerate(STRICT_PROFILE_PROLOGUE_FULL_SPECS)
        )

    def maybe_service_profile_prologue(self, s, addr, conn, now=None):
        """Send the captured profile-replication prologue the bootstrap omits.

        Working capture (`24July26/W3_match_full_2.pcapng`, ~0.35 s after the spawn
        burst, ~2.7 s *before* the client reports h281/h65):

            src 204  Client_ForceClearCurrentPlayersProfileReplication
            src 321  Client_ReceiveServerStartDate   -> C->S h177 acks it

        Our ownership bootstrap sends neither, so the client's profile state machine
        is never opened and every later `Client_FinishPlayersProfileData` closes a
        list that was never started.
        """
        if not self.profile_prologue_enabled():
            return False
        if getattr(conn, "_profile_prologue_failed", False):
            return False
        if not getattr(conn, "_ownership_done", False):
            return False
        current = time.time() if now is None else float(now)
        queue = getattr(conn, "_profile_prologue_queue", None)
        if queue is None:
            try:
                arm_delay = float(os.environ.get("WW3_PROFILE_PROLOGUE_DELAY_S", "2.0"))
            except ValueError:
                arm_delay = 2.0
            armed_at = (getattr(conn, "_ownership_done_t", 0) or current) + arm_delay
            if current < armed_at:
                return False
            try:
                specs = self._load_validated_capture_specs(
                    conn, self.profile_prologue_specs(), "profile prologue")
            except (OSError, ValueError, IndexError) as exc:
                print(f"[match]       ! profile prologue unavailable: {exc}")
                conn._profile_prologue_failed = True
                return False
            queue = [(armed_at + delay_s, source) for delay_s, source in specs]
            conn._profile_prologue_queue = queue
            conn._profile_prologue_armed_at = armed_at
            mode = os.environ.get("WW3_PROFILE_PROLOGUE_MODE", "min")
            print(f"[match]       *** profile prologue armed: {len(queue)} captured "
                  f"sources, mode={mode} (WW3_PROFILE_PROLOGUE) ***")
        sent = False
        while queue and queue[0][0] <= current:
            _due, source = queue.pop(0)
            bunch = self.build_replay_bunch(conn, source)
            self.flush_acks(s, addr, conn)
            self.send_packet(
                s, addr, conn, bunch=bunch,
                audit_tag=f"profile prologue src={source['_src_idx']}")
            print(f"[match]       *** profile prologue captured source "
                  f"{source['_src_idx']} sent on ch{source['chIndex']} ***")
            sent = True
        if not queue and not getattr(conn, "_profile_prologue_done", False):
            conn._profile_prologue_done = True
            print("[match]       *** profile prologue complete; watching for C->S "
                  "h177 Server_ClientReceivedServerStartDate ***")
        return sent

    def _load_validated_action_replicator_specs(self, conn):
        """Validate the ch80 partial pair, header field by header field.

        Same fail-closed contract as the profile specs: a regenerated
        `real_replay_stream.json` must stop the experiment, not silently put
        different bits on a channel the client will keep open forever.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        stream = json.load(open(os.path.join(here, "real_replay_stream.json"),
                                encoding="utf-8"))
        validated = []
        for source_index, expected_bits, expected_sha in TEAM_ACTION_REPLICATOR_SPECS:
            source = dict(stream[source_index])
            payload = source.get("payload", "")
            if (int(source.get("chIndex", -1)) != TEAM_ACTION_REPLICATOR_CHANNEL
                    or int(source.get("chType", -1)) != cc.CHTYPE_ACTOR
                    or int(source.get("bits", -1)) != expected_bits
                    or int(source.get("bClose", 0)) != 0
                    or int(source.get("bReliable", 0)) != 1
                    or int(source.get("bPartial", 0)) != 1
                    or len(payload) != expected_bits
                    or hashlib.sha256(payload.encode("ascii")).hexdigest() != expected_sha):
                raise ValueError(f"action replicator source {source_index} identity mismatch")
            source["_src_idx"] = source_index
            validated.append(source)
        if (int(validated[0].get("bOpen", 0)) != 1
                or int(validated[0].get("bPartialInitial", 0)) != 1
                or int(validated[-1].get("bPartialFinal", 0)) != 1):
            raise ValueError("action replicator specs are not a whole partial chain")
        return validated

    @staticmethod
    def team_action_replicator_enabled():
        return os.environ.get("WW3_TEAM_ACTION_REPLICATOR", "0") == "1"

    def maybe_service_team_action_replicator(self, s, addr, conn, now=None):
        """Open the capture's ch80 `AWW3ActionReplicator`, once.

        Both bunches go in a single packet: they are one partial chain, and a
        partial-initial whose final is lost leaves the actor channel half-open
        with nothing ever dispatched.
        """
        if not self.team_action_replicator_enabled():
            return False
        if getattr(conn, "_action_replicator_done", False):
            return False
        if getattr(conn, "_action_replicator_failed", False):
            return False
        if (getattr(conn, "_bootstrap_opens_action_replicator", False)
                and os.environ.get("WW3_ACTION_REPLICATOR_ALLOW_DOUBLE_OPEN", "0") != "1"):
            # The bootstrap (WW3_WORLD_FILL=1) already replays src 174/175 on
            # this channel.  Opening NetGUID 9400 twice is the one thing the
            # capture never does and it costs the client its ActionReplicator.
            # `_action_replicator_done` is armed by `note_replay_bunch_sent` when
            # the drip actually transmits that open -- never here, where the
            # bunch is still sitting in a 266-entry queue.
            if not getattr(conn, "_action_replicator_skip_logged", False):
                conn._action_replicator_skip_logged = True
                print(f"[match]       *** ch{TEAM_ACTION_REPLICATOR_CHANNEL} "
                      "WW3ActionReplicator is opened by the bootstrap "
                      f"(sources {list(TEAM_ACTION_REPLICATOR_SOURCES)}); not opening it "
                      "twice (WW3_TEAM_ACTION_REPLICATOR) ***")
            return False
        if not getattr(conn, "_ownership_done", False):
            return False
        current = time.time() if now is None else float(now)
        try:
            arm_delay = float(os.environ.get("WW3_TEAM_ACTION_REPLICATOR_DELAY_S", "2.0"))
        except ValueError:
            arm_delay = 2.0
        armed_at = (getattr(conn, "_ownership_done_t", 0) or current) + arm_delay
        if current < armed_at:
            return False
        try:
            sources = self._load_validated_action_replicator_specs(conn)
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! action replicator unavailable: {exc}")
            conn._action_replicator_failed = True
            return False
        bunches = [self.build_replay_bunch(conn, source) for source in sources]
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=bunches,
                         audit_tag="action replicator ch80 src=174,175")
        conn._action_replicator_done = True
        conn._action_replicator_done_t = current
        print(f"[match]       *** ch{TEAM_ACTION_REPLICATOR_CHANNEL} WW3ActionReplicator "
              f"opened from captured sources {list(TEAM_ACTION_REPLICATOR_SOURCES)} "
              f"(WW3_TEAM_ACTION_REPLICATOR); watching for PlayerState->CurrentSquad ***")
        return True

    def note_replay_bunch_sent(self, conn, spec, now=None):
        """Arm ch80 state from the drip's own transmission, not from the queue.

        Turn 9b marked the channel open the moment the bootstrap was *queued*
        and fired the probe ~100 log lines later, while ch80 was still one of
        266 bunches waiting in that queue.  The client answered nothing, even
        though `_uobject_live.py` later found the actor alive -- the open simply
        had not gone out yet.  Anchoring on the send makes the probe's own
        arming delay measure from a moment that actually happened.
        """
        if getattr(conn, "_action_replicator_done", False):
            return False
        if (int(spec.get("chIndex", -1)) != TEAM_ACTION_REPLICATOR_CHANNEL
                or not int(spec.get("bOpen", 0))):
            return False
        conn._action_replicator_done = True
        conn._action_replicator_done_t = time.time() if now is None else float(now)
        print(f"[match]       *** ch{TEAM_ACTION_REPLICATOR_CHANNEL} WW3ActionReplicator "
              "open transmitted by the bootstrap drip; probe armed from here ***")
        return True

    @staticmethod
    def action_probe_enabled():
        return os.environ.get("WW3_ACTION_PROBE", "0") == "1"

    def maybe_send_action_probe(self, s, addr, conn, now=None):
        """Send ONE empty `TM_Synchronize` over ch80 `Client_ReceivePacket`.

        This is a transport experiment, not a gameplay change.  The client's
        `Client_ReceivePacket_Implementation` (exe 0x140873980) tail-calls
        `Server_AckActionsReceived` on *both* exit paths, so an ack proves the
        ClassNetCache handle, the `TArray<uint8>` parameter encoding and the
        bunch framing are right — and nothing about the payload.  The payload
        oracle is the ActionReplicator's own `ReceiveBuffer`/`ExpectedTotal`/
        action count, which `_action_live.py` reads out of the running client.

        Rides the channel the capture itself opened, so it cannot fire unless
        `WW3_TEAM_ACTION_REPLICATOR` actually put ch80 up first.
        """
        if not self.action_probe_enabled():
            return False
        if getattr(conn, "_action_probe_done", False):
            return False
        if getattr(conn, "_action_probe_failed", False):
            return False
        if not self.team_action_replicator_enabled():
            return False
        if not getattr(conn, "_action_replicator_done", False):
            return False
        current = time.time() if now is None else float(now)
        try:
            arm_delay = float(os.environ.get("WW3_ACTION_PROBE_DELAY_S", "2.0"))
        except ValueError:
            arm_delay = 2.0
        armed_at = (getattr(conn, "_action_replicator_done_t", 0) or current) + arm_delay
        if current < armed_at:
            return False

        # Liveness. A one-shot experiment is worthless if the client's net thread
        # has stalled -- turn 5's first run spent its only probe 1.1 s after the
        # client stopped sending (it was still streaming the map, 9.8 GB working
        # set) and proved nothing. Require recent inbound bunches so an ack, or
        # its absence, actually means something.
        try:
            liveness_s = float(os.environ.get("WW3_ACTION_PROBE_LIVENESS_S", "2.0"))
        except ValueError:
            liveness_s = 2.0
        last_in = getattr(conn, "_last_client_bunch_t", 0)
        if liveness_s > 0 and (not last_in or current - last_in > liveness_s):
            quiet = "never" if not last_in else f"{current - last_in:.1f}s ago"
            if not getattr(conn, "_action_probe_wait_logged", False):
                conn._action_probe_wait_logged = True
                print(f"[match]       action probe armed but holding: last client "
                      f"bunch {quiet} (need <= {liveness_s:.1f}s, "
                      f"WW3_ACTION_PROBE_LIVENESS_S)")
            return False

        packet = action_replicator.build_empty_tm_synchronize_packet()
        digest = hashlib.sha256(packet).hexdigest()
        if len(packet) != ACTION_PROBE_PACKET_BYTES or digest != ACTION_PROBE_PACKET_SHA256:
            conn._action_probe_failed = True
            print(f"[match]       ! action probe payload identity mismatch "
                  f"({len(packet)} bytes, sha256 {digest[:16]}...) -- not sending")
            return False

        bits = action_replicator.build_client_receive_packet_bits(packet)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._action_probe_done = True
        conn._action_probe_sent_t = current
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=TEAM_ACTION_REPLICATOR_CHANNEL,
            ch_seq=self.next_chan_seq(conn, TEAM_ACTION_REPLICATOR_CHANNEL),
            ch_type=cc.CHTYPE_ACTOR, bOpen=0, bReliable=1)],
            audit_tag="action probe ch80 Client_ReceivePacket(empty TM_Synchronize)")
        print(f"[match]       *** ch{TEAM_ACTION_REPLICATOR_CHANNEL} "
              f"Client_ReceivePacket (handle "
              f"{action_replicator.RPC_CLIENT_RECEIVE_PACKET}) sent: empty "
              f"TM_Synchronize, {len(packet)} bytes / {len(bits)} bits "
              f"(WW3_ACTION_PROBE); oracle = C->S handle "
              f"{action_replicator.RPC_SERVER_ACK_ACTIONS_RECEIVED} "
              f"Server_AckActionsReceived ***")
        return True

    @staticmethod
    def team_sync_bind_enabled():
        return os.environ.get("WW3_TEAM_SYNC_BIND", "0") == "1"

    def maybe_send_team_sync_bind(self, s, addr, conn, now=None):
        """Send ONE non-empty `TM_Synchronize` over ch80 `Client_ReceivePacket`.

        This is the payload the whole squad path exists for.  The handler
        (0x140969db0) integrates the team/squad/slot graph, and for the one slot
        whose `+0x60` is set it calls 0x1409739b0, which requires
        `slot->[0x34] != 0` and then scans live `AWW3PlayerState`s for
        `InternalNetId == slot->[0x30]` and `PlayerStateUniqueID ==
        slot->[0x34]`.  On a match it binds `slot->PlayerState` and -- because
        `TeamManager->LocalPlayerState` is still NULL on this client and its
        `Owner` casts to `AWW3PlayerController` (`_slot_bind_gates.py`) -- calls
        `AWW3PlayerState::SetCurrentSquad`.

        Same gating as the transport probe: opt-in, one-shot, riding a channel it
        did not open itself, refusing a stalled client, and fail-closed on the
        payload identity.  Additionally it holds until the empty probe has gone
        out when that is enabled too, so a live A/B can attribute a change to the
        payload rather than to the transport.
        """
        if not self.team_sync_bind_enabled():
            return False
        if getattr(conn, "_team_sync_bind_done", False):
            return False
        if getattr(conn, "_team_sync_bind_failed", False):
            return False
        if not self.team_action_replicator_enabled():
            return False
        if not getattr(conn, "_action_replicator_done", False):
            return False
        if self.action_probe_enabled() and not getattr(conn, "_action_probe_done", False):
            return False
        if (os.environ.get("WW3_TEAM_SYNC_BIND_REQUIRE_PROBE_ACK", "0") == "1"
                and self.action_probe_enabled()
                and not getattr(conn, "_action_probe_acked", False)):
            # `_action_probe_done` only means "we transmitted it".  The client's
            # `Server_AckActionsReceived` is unconditional on both exit paths of
            # `Client_ReceivePacket`, so its absence proves the RPC was never
            # dispatched -- i.e. there is no `AWW3ActionReplicator` to receive
            # the graph.  Turn 9 spent this one-shot into exactly that client.
            if not getattr(conn, "_team_sync_probe_wait_logged", False):
                conn._team_sync_probe_wait_logged = True
                print("[match]       team sync bind holding: the ch80 probe was sent "
                      "but never answered with Server_AckActionsReceived "
                      "(WW3_TEAM_SYNC_BIND_REQUIRE_PROBE_ACK)")
            return False
        current = time.time() if now is None else float(now)
        try:
            arm_delay = float(os.environ.get("WW3_TEAM_SYNC_BIND_DELAY_S", "3.0"))
        except ValueError:
            arm_delay = 3.0
        armed_at = (getattr(conn, "_action_replicator_done_t", 0) or current) + arm_delay
        if current < armed_at:
            return False

        try:
            liveness_s = float(os.environ.get("WW3_TEAM_SYNC_BIND_LIVENESS_S", "2.0"))
        except ValueError:
            liveness_s = 2.0
        last_in = getattr(conn, "_last_client_bunch_t", 0)
        if liveness_s > 0 and (not last_in or current - last_in > liveness_s):
            quiet = "never" if not last_in else f"{current - last_in:.1f}s ago"
            if not getattr(conn, "_team_sync_bind_wait_logged", False):
                conn._team_sync_bind_wait_logged = True
                print(f"[match]       team sync bind armed but holding: last client "
                      f"bunch {quiet} (need <= {liveness_s:.1f}s, "
                      f"WW3_TEAM_SYNC_BIND_LIVENESS_S)")
            return False

        def _env_int(name, default):
            try:
                return int(os.environ.get(name, str(default)))
            except ValueError:
                return default

        net_id = _env_int("WW3_TEAM_SYNC_BIND_NET_ID", TEAM_SYNC_BIND_DEFAULT_NET_ID)
        unique_id = _env_int("WW3_TEAM_SYNC_BIND_UNIQUE_ID",
                             TEAM_SYNC_BIND_DEFAULT_UNIQUE_ID)
        name = os.environ.get("WW3_TEAM_SYNC_BIND_NAME", "")
        try:
            packet = action_replicator.build_local_bind_packet(net_id, unique_id,
                                                               name=name)
        except ValueError as exc:
            conn._team_sync_bind_failed = True
            print(f"[match]       ! team sync bind identity refused: {exc} "
                  f"(net_id={net_id}, unique_id={unique_id}) -- not sending")
            return False

        digest = hashlib.sha256(packet).hexdigest()
        if (len(packet) != TEAM_SYNC_BIND_PACKET_BYTES
                or digest != TEAM_SYNC_BIND_PACKET_SHA256):
            conn._team_sync_bind_failed = True
            print(f"[match]       ! team sync bind payload identity mismatch "
                  f"({len(packet)} bytes, sha256 {digest[:16]}...) -- not sending")
            return False

        bits = action_replicator.build_client_receive_packet_bits(packet)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._team_sync_bind_done = True
        conn._team_sync_bind_sent_t = current
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=TEAM_ACTION_REPLICATOR_CHANNEL,
            ch_seq=self.next_chan_seq(conn, TEAM_ACTION_REPLICATOR_CHANNEL),
            ch_type=cc.CHTYPE_ACTOR, bOpen=0, bReliable=1)],
            audit_tag="team sync bind ch80 Client_ReceivePacket(TM_Synchronize 1/1/1)")
        print(f"[match]       *** ch{TEAM_ACTION_REPLICATOR_CHANNEL} "
              f"Client_ReceivePacket (handle "
              f"{action_replicator.RPC_CLIENT_RECEIVE_PACKET}) sent: "
              f"TM_Synchronize 1 team / 1 squad / 1 slot bound to "
              f"InternalNetId={net_id} PlayerStateUniqueID={unique_id} "
              f"name={name!r}, {len(packet)} bytes / {len(bits)} bits "
              f"(WW3_TEAM_SYNC_BIND); oracles = C->S handle "
              f"{action_replicator.RPC_SERVER_ACK_ACTIONS_RECEIVED}, then "
              f"_team_graph_live.py CurrentSquad != NULL ***")
        return True

    @staticmethod
    def deploy_release_enabled():
        return os.environ.get("WW3_DEPLOY_RELEASE", "0") == "1"

    def _load_validated_transition_spec(self):
        """Load capture source 1934 and validate it field by field, fail-closed.

        Same contract as `maybe_send_late_transition`'s strict branch: a
        regenerated `real_replay_stream.json` must stop the experiment rather
        than put different bits on a live reliable channel.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        stream = json.load(open(os.path.join(here, "real_replay_stream.json"),
                                encoding="utf-8"))
        spec = dict(stream[STRICT_TRANSITION_SOURCE])
        payload = spec.get("payload", "")
        if (int(spec.get("chIndex", -1)) != 2
                or int(spec.get("bits", -1)) != STRICT_TRANSITION_BITS
                or int(spec.get("bOpen", 0)) != 0
                or int(spec.get("bClose", 0)) != 0
                or int(spec.get("bReliable", 0)) != 1
                or int(spec.get("bPartial", 0)) != 0
                or int(spec.get("bPartialInitial", 0)) != 0
                or int(spec.get("bPartialFinal", 0)) != 0
                or int(spec.get("bHasPackageMapExports", 0)) != 0
                or int(spec.get("bHasMustBeMappedGUIDs", 0)) != 0
                or int(spec.get("chType", -1)) != cc.CHTYPE_ACTOR
                or len(payload) != STRICT_TRANSITION_BITS
                or hashlib.sha256(payload.encode("ascii")).hexdigest()
                != STRICT_TRANSITION_SHA256):
            raise ValueError("source1934 identity mismatch")
        spec["_src_idx"] = STRICT_TRANSITION_SOURCE
        return spec

    @staticmethod
    def deploy_repeat_after_spectator_enabled():
        return os.environ.get("WW3_DEPLOY_REPEAT_AFTER_SPECTATOR", "0") == "1"

    def maybe_replay_capturepoint_exports(self, s, addr, conn):
        """Make Domination's real capture points nameable to the client.

        The deploy screen needs two objects per spawn -- h305 takes the capture
        point actor, h287 takes that point's "First Spawn Zone" child -- and the
        client can name neither unless their NetGUID -> path exports arrived.

        On four independent captures `BP_CapturePoint_*` open no actor channel of
        their own; they reach the client only as exports riding on *other* actors'
        opens.  Gobi is the same: `BP_CapturePoint_A` / `_B`, in the streaming
        sublevel `WW3_Dunhuang_Gameplay_New_DOM`, are exported on two other
        players' PlayerState opens (ch6 pkt 174, ch40 pkt 216), each also
        exporting a `First Spawn Zone`.  Our ownership bootstrap skips both (it
        jumps src 17 -> 20), so the client has never had them.

        Note these are a DIFFERENT pair from the `WW3TdmCapturePoint_1/2` that
        `maybe_replay_capture_points` replays out of the persistent level -- those
        look like TDM leftovers, and replicating them produced a spawn tile that
        rendered but could never be selected.

        Re-extracted complete from the raw pcap by `_extract_cp_exports.py`
        (unlike the capture-point channels' own dangling export, these reassemble
        cleanly: 2 frags -> 4755 / 4650 bits).  Bounded, one-shot, default off.
        """
        if os.environ.get("WW3_CP_EXPORT_REPLAY", "0") != "1":
            return False
        if getattr(conn, "_cp_export_replay_done", False):
            return False
        conn._cp_export_replay_done = True
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "capturepoint_export_stream.json")
        try:
            with open(path, encoding="utf-8") as fh:
                stream = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"[match]       ! capture-point export replay unavailable: {exc}")
            return False
        if not stream:
            print("[match]       ! capture-point export replay: nothing to send")
            return False
        queue = getattr(conn, "replay_queue", None)
        if queue is None:
            conn.replay_queue = queue = []
        for b in stream:
            queue.append(dict(b))
        what = sorted({e for b in stream for e in b.get("_exports", [])})
        chans = sorted({int(b["chIndex"]) for b in stream})
        print(f"[match]       *** M5: queued {len(stream)} capture-point EXPORT bunches "
              f"on ch{chans} (other players' PlayerState opens) carrying {what}. "
              "These are the NetGUID->path exports that let the client NAME "
              "Domination's real capture points and their spawn zones; without them "
              "the deploy screen has nothing selectable. Oracle = C->S h305 "
              "Server_SpectatorAttachToCapturePoint appears (WW3_CP_EXPORT_REPLAY) ***")
        return True

    def maybe_replay_capture_points(self, s, addr, conn):
        """Open the two capture-point actor channels the capture opens at pkt 370.

        Turn 10 measured the deploy screen's real gate.  The client has 3 local
        `AWW3CapturePoint` actors (they are level-placed, so they exist as soon as
        the map loads) and 39 pooled `WW3CapturePointSpectatorButton` widgets, but
        the spawn list renders empty and DEPLOY reads NOT READY.  What it never
        receives is the capture points' *replicated* state -- `CapturePointAsEnum`,
        `bIsEntireCapturePointActive`, `RemainingScore` are all Net properties, and
        without them no point is a valid spawn.

            ch 83  WW3_Gobi_New_P.PersistentLevel.WW3TdmCapturePoint_1
            ch 84  WW3_Gobi_New_P.PersistentLevel.WW3TdmCapturePoint2

        `real_replay_stream.json` kept only a dangling partial-initial for each --
        the same sanitiser damage that removed the ch3 pawn bunches -- so these are
        re-extracted from the raw capture by `_extract_capturepoints.py`, with
        partial runs reassembled into whole bunches.  Replay is bounded and the
        two OPENs (which carry the PackageMap exports) always go first, in the
        capture's own order.
        """
        if os.environ.get("WW3_CAPTUREPOINT_REPLAY", "0") != "1":
            return False
        if getattr(conn, "_capturepoint_replay_done", False):
            return False
        conn._capturepoint_replay_done = True
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "capturepoint_stream.json")
        try:
            with open(path, encoding="utf-8") as fh:
                stream = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"[match]       ! capture-point replay unavailable: {exc}")
            return False
        try:
            limit = int(os.environ.get("WW3_CAPTUREPOINT_LIMIT", "40"))
        except ValueError:
            limit = 40
        # `_actor_seq` 0 is the static capture point; sequence 1 is a *different*
        # actor that reuses the same channel index at pkt 11174 (dynamic, netguid
        # 18056/18060, with a world location, versus the level actors' 113/109 and
        # no location).  Replaying sequence 1's updates would apply one actor's
        # properties to another, so take sequence 0 only.
        stream = [b for b in stream if int(b.get("_actor_seq", 0)) == 0]
        # Send EVERY sequence-0 open, in capture order.  ch84 has two: the
        # dangling identity-export bunch at pkt 280, which carries the NetGUID
        # -> path chain (/Game/Maps/.../WW3_Gobi_New_P -> WW3_Gobi_New_P ->
        # PersistentLevel -> WW3TdmCapturePoint2) and makes the actor
        # RESOLVABLE, and the real open at pkt 370, which exports only
        # WW3CapturePointMarker.  Both are needed: h287
        # Server_RequestRespawnAtCapturePoint targets the capture point's
        # "First Spawn Zone" child, which cannot be named unless its outer
        # chain resolved first.
        opens = [b for b in stream if int(b.get("bOpen", 0)) == 1]
        rest = [b for b in stream if int(b.get("bOpen", 0)) != 1]
        # MEASURED REGRESSION: sending BOTH ch84 opens (the pkt-280 identity
        # export and the pkt-370 complete open) makes the client re-open the
        # channel, which resets the actor and discards the property updates that
        # follow.  With both, the live capture point reads
        # EntireCapturePointTeamOwner=255 / bIsEntireCapturePointActive=0; with
        # only the complete open it reads owner=0 / active=1.  So the identity
        # export is NOT deliverable as a second open, and the theory that it is
        # simply "the missing bunch" is not supported by the live result.
        # Default therefore keeps the better-measured single-open behaviour.
        if os.environ.get("WW3_CAPTUREPOINT_IDENTITY_EXPORT", "0") != "1":
            opens = [b for b in opens if not b.get("_dangling_export")]
            first = {}
            for b in opens:
                first.setdefault(int(b["chIndex"]), b)
            opens = [first[ch] for ch in sorted(first)]
        selected = sorted(opens, key=lambda b: (int(b.get("_pkt", 0)),
                                                int(b["chIndex"])))
        selected += rest[:max(0, limit - len(selected))]
        if not selected:
            print("[match]       ! capture-point replay: nothing selected")
            return False
        queue = getattr(conn, "replay_queue", None)
        if queue is None:
            conn.replay_queue = queue = []
        for b in selected:
            queue.append(dict(b))
        chans = sorted({int(b["chIndex"]) for b in selected})
        n_export = sum(1 for b in selected if b.get("_dangling_export"))
        print(f"[match]       *** M5: queued {len(selected)} capture-point bunches on "
              f"ch{chans} ({len(opens)} OPEN of which {n_export} are NetGUID identity "
              f"exports + {len(selected) - len(opens)} updates, from "
              "capturepoint_stream.json). The identity export carries the outer chain "
              "/Game/Maps/.../WW3_Gobi_New_P -> WW3_Gobi_New_P -> PersistentLevel -> "
              "WW3TdmCapturePoint2, which is what makes the capture point RESOLVABLE; "
              "without it the client cannot name the actor and never offers it as a "
              "spawn. Oracle = C->S h305 Server_SpectatorAttachToCapturePoint appears "
              "(WW3_CAPTUREPOINT_REPLAY) ***")
        return True

    def maybe_mark_deploy_eligible(self, s, addr, conn):
        """Tell the client the local player is not alive, so DEPLOY can arm.

        Turn 12 measured why the button reads NOT READY, and it is not a protocol
        fault.  On the live client `AWW3Character::CurrentHealth` is 100,
        `AWW3PlayerState::PlayingState` is 2 and `bIsSpectator` is 0 -- the client
        believes it is already alive and playing, and WW3 does not let a living
        player deploy.  That is why no spawn tile can be selected (both the "A"
        capture point and the BASE highlight on hover but never latch) and why the
        client never sends h287.

        The cause is that `real_replay_stream.json` was captured from the middle of
        a live match, long after the real player had deployed, so replaying it hands
        our client a full-health pawn before it has ever been through the deploy
        flow.

        Handles and widths come from the build's own RepLayout dump
        (`RepLayout/replication_seed.json`), the size oracle this project requires
        before synthesising any property write -- h60 CurrentHealth is a byte (8
        bits) and h52 PlayingState is an enum with Max=5 (3 bits).  Both encodings
        round-trip through `read_content_blocks` with zero bits left over.

        Off by default; PlayingState is only sent when a value is given explicitly,
        so health is testable as a single variable.
        """
        if os.environ.get("WW3_DEPLOY_MARK_DEAD", "0") != "1":
            return False
        if getattr(conn, "_deploy_mark_dead_done", False):
            return False
        conn._deploy_mark_dead_done = True
        sent = []

        try:
            health = int(os.environ.get("WW3_DEPLOY_DEAD_HEALTH", "0"))
        except ValueError:
            health = 0
        bits = build_char_health_bits(health)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= (1 << (i & 7))
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=3,
            ch_seq=self.next_chan_seq(conn, 3), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="deploy mark-dead ch3 h60")
        sent.append(f"ch3 h60 CurrentHealth={health} ({len(bits)} bits)")

        raw_state = os.environ.get("WW3_DEPLOY_PLAYING_STATE", "").strip()
        ps_channel = getattr(conn, "ps_channel", None)
        if raw_state and ps_channel:
            try:
                state = int(raw_state)
            except ValueError:
                state = None
            if state is not None:
                pbits = build_ps_playing_state_bits(state)
                pby = bytearray((len(pbits) + 7) // 8)
                for i, bit in enumerate(pbits):
                    if bit:
                        pby[i >> 3] |= (1 << (i & 7))
                self.flush_acks(s, addr, conn)
                self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
                    len(pbits), bytes(pby), ch_index=int(ps_channel),
                    ch_seq=self.next_chan_seq(conn, int(ps_channel)),
                    ch_type=cc.CHTYPE_ACTOR, bOpen=0, bReliable=1)],
                    audit_tag="deploy mark-dead PS h52")
                sent.append(f"ch{ps_channel} h52 PlayingState={state} "
                            f"({len(pbits)} bits)")

        print("[match]       *** M4: deploy-eligibility write sent -- "
              + "; ".join(sent)
              + ". The client had CurrentHealth=100 while on the deploy screen "
                "(PlayingState=2 is EWW3PS_OnDeployScreen, which is correct -- an "
                "earlier note here wrongly read it as 'alive'). MEASURED: this write "
                "does land, health goes 100->0 on the live client, which proves the "
                "synthesised RepLayout path -- but h287 still never fires, so health "
                "alone is NOT the deploy gate (WW3_DEPLOY_MARK_DEAD) ***")
        return True

    def maybe_send_deploy_screen_chain(self, s, addr, conn, now=None):
        """Replay the capture's deploy-screen block once the client is spectating.

        Between the strict profile chain (src 1385) and the deploy answer (src
        1934) the real server sent the deploy screen's own conversation:
        `ClientSetViewTarget` for the spectator camera and five
        `Client_UpdateSpectatePoint`.  We skipped all of it and jumped from 1385
        to 1934, which is measurable on the live client -- 39 pooled
        `WW3CapturePointSpectatorButton` widgets exist but the spawn list renders
        empty, `ClObjectResponsibleForRespawn` is NULL and DEPLOY reads NOT READY.

        Same contract as every other replay here: captured bytes only, validated
        field-by-field plus SHA-256, fail-closed, one shot, default off.
        """
        if os.environ.get("WW3_DEPLOY_SCREEN_CHAIN", "0") != "1":
            return False
        if getattr(conn, "_deploy_screen_chain_done", False):
            return False
        if not getattr(conn, "_client_start_spectator", False):
            return False
        current = time.time() if now is None else float(now)
        queue = getattr(conn, "_deploy_screen_chain_queue", None)
        if queue is None:
            try:
                specs = self._load_validated_capture_specs(
                    conn, DEPLOY_SPECTATE_SPECS, "deploy screen")
            except (OSError, ValueError, IndexError) as exc:
                print(f"[match]       ! deploy screen chain refused: {exc}")
                conn._deploy_screen_chain_done = True
                return False
            queue = [(current + delay, src) for delay, src in specs]
            conn._deploy_screen_chain_queue = queue
            print("[match]       *** deploy screen chain armed: captured sources "
                  f"{[i for i, _d, _b, _s in DEPLOY_SPECTATE_SPECS]} "
                  "(ClientSetViewTarget + 5x Client_UpdateSpectatePoint) ***")
        sent = False
        while queue and queue[0][0] <= current:
            _due, source = queue.pop(0)
            bunch = self.build_replay_bunch(conn, source)
            self.flush_acks(s, addr, conn)
            self.send_packet(s, addr, conn, bunch=bunch,
                             audit_tag=f"deploy screen src={source['_src_idx']}")
            print(f"[match]       *** deploy screen captured source "
                  f"{source['_src_idx']} sent on ch{source['chIndex']} ***")
            sent = True
        if not queue:
            conn._deploy_screen_chain_done = True
        return sent

    def maybe_send_deploy_respawn_status(self, s, addr, conn):
        """Send captured src 1856 (h231) -- the capture's own prelude to 1934.

        `Client_OnCapturePointRespawnRequestStatusChanged` lands 78 ms before the
        transition bundle and is the only thing between the client's DEPLOY press
        (C->S h287, src ~1841) and the server's answer.  Sending 1934 without it
        asks `Client_OnStopSpectatorBeforeDeploy` to deploy onto a request the
        client never received, which is consistent with the observed outcome:
        possession is acknowledged, then the client falls straight back into the
        deploy spectator and h73 never stops.
        """
        if os.environ.get("WW3_DEPLOY_STATUS_BEFORE_TRANSITION", "0") != "1" \
                and not getattr(conn, "_deploy_answer_in_progress", False):
            return False
        if getattr(conn, "_deploy_status_sent", False):
            return False
        try:
            specs = self._load_validated_capture_specs(
                conn, DEPLOY_RESPAWN_STATUS_SPECS, "deploy status")
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! deploy status refused: {exc}")
            conn._deploy_status_sent = True
            return False
        conn._deploy_status_sent = True
        _delay, source = specs[0]
        bunch = self.build_replay_bunch(conn, source)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunch=bunch,
                         audit_tag="deploy status src=1856")
        print(f"[match]       *** captured source 1856 sent on ch{source['chIndex']}: "
              f"h{PC_RPC_CAPTURE_POINT_RESPAWN_STATUS} "
              "Client_OnCapturePointRespawnRequestStatusChanged, the capture's own "
              "prelude to source 1934 (WW3_DEPLOY_STATUS_BEFORE_TRANSITION) ***")
        return True

    def maybe_answer_spectate_attach(self, s, addr, conn):
        """Answer C->S h305 with the capture's own Client_UpdateSpectatePoint.

        Four independent clean captures show the real server replying to every
        `Server_SpectatorAttachToCapturePoint` with `ClientSetViewTarget` +
        `Client_UpdateSpectatePoint`, echoing the capture point the client named,
        strictly 1:1 (StrongHold: 12 out, 12 back).  Without that reply the client
        has no confirmation that its spawn selection took, and h287 -- which
        targets the point's "First Spawn Zone" child -- never follows.

        We replay the capture's own 47-bit h273 bunches (sources 1640/1641/1650/
        1651/1657, all byte-identical and already SHA-validated in
        DEPLOY_SPECTATE_SPECS).  They name the *capture's* point rather than
        whichever the client asked for; that is a known limitation of replaying
        bytes and is why this is bounded and default-off.
        """
        if os.environ.get("WW3_SPECTATE_POINT_REPLY", "1") != "1":
            return False
        try:
            budget = int(os.environ.get("WW3_SPECTATE_POINT_REPLY_MAX", "12"))
        except ValueError:
            budget = 12
        sent_n = getattr(conn, "_spectate_reply_n", 0)
        if sent_n >= budget:
            return False
        specs = getattr(conn, "_spectate_reply_specs", None)
        if specs is None:
            try:
                # index 1 onwards are the five 47-bit Client_UpdateSpectatePoint
                # bunches; index 0 is the 113-bit ClientSetViewTarget.
                loaded = self._load_validated_capture_specs(
                    conn, DEPLOY_SPECTATE_SPECS, "spectate reply")
            except (OSError, ValueError, IndexError) as exc:
                print(f"[match]       ! spectate-point reply unavailable: {exc}")
                conn._spectate_reply_specs = []
                return False
            specs = [src for _delay, src in loaded]
            conn._spectate_reply_specs = specs
        if not specs:
            return False
        view_target, points = specs[0], specs[1:]
        bunches = []
        if sent_n == 0:
            bunches.append(self.build_replay_bunch(conn, dict(view_target)))
        bunches.append(self.build_replay_bunch(
            conn, dict(points[sent_n % len(points)])))
        conn._spectate_reply_n = sent_n + 1
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=bunches,
                         audit_tag=f"spectate-point reply {sent_n + 1}/{budget}")
        if sent_n == 0:
            print("[match]       *** client selected a spawn point "
                  f"(C->S h{PC_RPC_SPECTATOR_ATTACH_CAPTURE_POINT} "
                  "Server_SpectatorAttachToCapturePoint) -- answering with the "
                  f"capture's ClientSetViewTarget + h{PC_RPC_CLIENT_UPDATE_SPECTATE_POINT} "
                  "Client_UpdateSpectatePoint, the strict 1:1 reply seen in 4 clean "
                  "captures. Oracle = C->S h287 follows (WW3_SPECTATE_POINT_REPLY) ***")
        return True

    def maybe_answer_deploy_request(self, s, addr, conn):
        """Answer a real C->S h287 DEPLOY press the way the capture does.

        This is the only path in this file where the *client* asks first.  The
        capture's shape is exact: h287 at src ~1841, then
        `Client_OnCapturePointRespawnRequestStatusChanged` (src 1856), then the
        transition bundle (src 1934) 78 ms later.  Everything else we do around
        the deploy screen is us guessing when to push 1934; this is the request/
        response pair, so it takes priority over the one-shots and is allowed to
        re-arm them.

        Captured bytes only, both bunches SHA-pinned, one shot, default off.
        """
        if os.environ.get("WW3_DEPLOY_ANSWER_H287", "1") != "1":
            return False
        if getattr(conn, "_deploy_answer_done", False):
            return False
        conn._deploy_answer_done = True
        try:
            spec = self._load_validated_transition_spec()
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! deploy answer refused: {exc}")
            return False
        spec["chIndex"] = int(getattr(conn, "pc_channel", 2))
        # Re-arm the status one-shot: this is a fresh request, not a repeat.
        conn._deploy_answer_in_progress = True
        conn._deploy_status_sent = False
        self.maybe_send_deploy_respawn_status(s, addr, conn)
        conn._deploy_answer_in_progress = False
        bunch = self.build_replay_bunch(conn, spec)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[bunch],
                         audit_tag="deploy answer source1934 after h287")
        print("[match]       *** ANSWERED the client's own DEPLOY press: captured "
              "source 1856 then source 1934, the capture's exact response to "
              f"h{PC_RPC_REQUEST_RESPAWN_AT_CAPTURE_POINT}. Oracle = h73 stops, "
              "C->S h64, pawn Controller non-NULL ***")
        self.maybe_revive_after_deploy(s, addr, conn)
        return True

    def maybe_revive_after_deploy(self, s, addr, conn):
        """Put the pawn's health back once the client has actually deployed.

        `WW3_DEPLOY_MARK_DEAD` lies to the client to get the DEPLOY button to arm
        -- it has to, because our replay hands it a live pawn before it has ever
        deployed.  Once the client answers with h287 and we send the transition,
        that lie has done its job and has to be undone, or the player arrives in
        first person on a pawn it believes is dead.

        Same grounded encoding as the mark-dead write: h60, byte, 8 bits, from
        `RepLayout/replication_seed.json`.
        """
        if os.environ.get("WW3_DEPLOY_MARK_DEAD", "0") != "1":
            return False
        if os.environ.get("WW3_DEPLOY_REVIVE_ON_ANSWER", "1") != "1":
            return False
        if getattr(conn, "_deploy_revive_done", False):
            return False
        conn._deploy_revive_done = True
        try:
            health = int(os.environ.get("WW3_DEPLOY_REVIVE_HEALTH", "100"))
        except ValueError:
            health = 100
        bits = build_char_health_bits(health)
        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= (1 << (i & 7))
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=3,
            ch_seq=self.next_chan_seq(conn, 3), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)], audit_tag="deploy revive ch3 h60")
        print(f"[match]       *** M4: post-deploy revive -- ch3 h60 CurrentHealth="
              f"{health} ({len(bits)} bits), undoing the mark-dead write now that the "
              "client has deployed (WW3_DEPLOY_REVIVE_ON_ANSWER) ***")
        return True

    def maybe_repeat_deploy_transition(self, s, addr, conn, now=None):
        """Send capture source 1934 once more, after the client starts spectating.

        Turn 9 falsified the obvious reordering.  Holding the bundle until h310
        deadlocks, because h310 is a *consequence* of the bundle, not a
        precondition: on a client at mask 0xff with h281 and a real PS h65 both
        on the wire, h310 never arrived while the bundle was withheld, and every
        run that ever produced h208+h310 had already received it.

        So the capture's ordering is restored by repeating rather than by
        holding.  The first copy (h281 + PS h65) moves the controller out of its
        initial state; the client then opens the deploy screen and enters
        spectator, which is exactly the state the capture's own source 1934
        answers.  This sends the identical SHA-pinned bunch once more, in that
        position -- `Client_OnStopSpectatorBeforeDeploy`, `Client_StopSpectator`,
        `ClientSetViewTarget`, `ClientRestart(9372)`, `ClientSetViewTarget`,
        `ClientSetCameraMode`, `ClientSetRotation`.

        Nothing new is synthesised: same bytes, same channel, one extra copy,
        gated on the client actually spectating and actually transmitting.
        """
        if not self.deploy_repeat_after_spectator_enabled():
            return False
        if getattr(conn, "_deploy_repeat_done", False):
            return False
        if not getattr(conn, "_client_start_spectator", False):
            return False
        if not (getattr(conn, "_deploy_release_done", False)
                or getattr(conn, "_strict_transition_done", False)
                or getattr(conn, "_late_transition_done", False)):
            # Repeating something that was never delivered is not a repeat.
            return False
        if (os.environ.get("WW3_DEPLOY_SCREEN_CHAIN", "0") == "1"
                and not getattr(conn, "_deploy_screen_chain_done", False)):
            # Capture order is 1637..1657 -> 1856 -> 1934; do not overtake it.
            return False
        current = time.time() if now is None else float(now)
        try:
            settle = float(os.environ.get(
                "WW3_DEPLOY_REPEAT_AFTER_SPECTATOR_DELAY_S", "0.0"))
        except ValueError:
            settle = 0.0
        if settle > 0 and current < getattr(
                conn, "_client_start_spectator_t", current) + settle:
            return False
        try:
            liveness_s = float(os.environ.get("WW3_DEPLOY_RELEASE_LIVENESS_S", "2.0"))
        except ValueError:
            liveness_s = 2.0
        last = getattr(conn, "_last_client_bunch_t", 0) or 0
        if liveness_s > 0 and (not last or current - last > liveness_s):
            return False
        try:
            spec = self._load_validated_transition_spec()
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! deploy repeat refused: {exc}")
            conn._deploy_repeat_done = True
            return False
        spec["chIndex"] = int(getattr(conn, "pc_channel", 2))
        # Capture order: src 1856 (h231 request-status) precedes src 1934 by 78 ms.
        self.maybe_send_deploy_respawn_status(s, addr, conn)
        bunch = self.build_replay_bunch(conn, spec)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[bunch],
                         audit_tag="deploy repeat source1934 after h310")
        conn._deploy_repeat_done = True
        conn._deploy_repeat_sent_t = current
        print("[match]       *** captured source 1934 REPEATED after C->S h"
              f"{PC_RPC_START_SPECTATOR} Server_StartSpectator "
              "(WW3_DEPLOY_REPEAT_AFTER_SPECTATOR); this is the capture's own "
              "position for it. Oracle = h73 ServerSetSpectatorLocation stops, "
              "C->S h64 + h280 Server_OnMapClosed ***")
        return True

    @staticmethod
    def deploy_after_spectator_enabled():
        """Hold captured source 1934 until C->S h310 `Server_StartSpectator`.

        This mode both *holds* and *releases*, so it is self-sufficient: it would
        be a footgun for it to block the transition forever when
        `WW3_DEPLOY_RELEASE` happens to be off.
        """
        return os.environ.get("WW3_DEPLOY_AFTER_SPECTATOR", "0") == "1"

    def maybe_replay_pawn_movement(self, s, addr, conn):
        """Replay the CAPTURED pawn (ch3) property stream after the deploy transition.

        Evidence for why this exists (turn 9d, 2026-08-10):
        * The deploy transition now works: h73 stops and C->S h64 arrives, so the
          client leaves spectator with a possessed pawn and the real match HUD.
        * The pawn is nevertheless parked at (0, 0, -10000) -- `_deploy_gates_live.py`
          reads that location while Pawn/PlayerState/mask 0xff are all healthy.  The
          bootstrap spawns ch3 at the capture's (-1787, -10060, -562.5), so the
          spectator cycle parks it and nothing ever places it again.
        * `real_replay_stream.json` cannot supply the fix: the structural sanitiser
          that made the world replay safe dropped ch3 after its OPEN pair, so the
          stream holds only 6 ch3 bunches while the capture has 9,586.

        So the pawn's own movement/property updates are replayed from a SEPARATE,
        index-stable file (`pawn_ch3_stream.json`, extracted straight from
        captures/24July26/W3_match_full_2.pcapng).  Nothing here is synthesised:
        every bunch is capture-grounded, and `real_replay_stream.json` source
        indexes are deliberately left untouched.

        Default OFF.  One-shot, and queued through the existing replay queue so it
        inherits the proven packing (~12 bunches/packet) and reliable/unreliable mix.
        """
        if getattr(conn, "_pawn_movement_replay_done", False):
            return False
        if os.environ.get("WW3_PAWN_MOVEMENT_REPLAY", "0") != "1":
            conn._pawn_movement_replay_done = True
            return False
        # Only after the deploy actually completed, or we would be feeding movement
        # to a pawn the client is still about to park.
        if not getattr(conn, "_deploy_repeat_done", False):
            return False
        conn._pawn_movement_replay_done = True
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "pawn_ch3_stream.json")
        try:
            stream = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"[match]       ! pawn movement replay unavailable: {exc}")
            return False
        try:
            limit = int(os.environ.get("WW3_PAWN_MOVEMENT_LIMIT", "600"))
        except ValueError:
            limit = 600
        queued = [b for b in stream[:max(0, limit)] if int(b.get("chIndex", -1)) == 3]
        if not queued:
            print("[match]       (pawn movement replay: nothing to queue)")
            return False
        conn.replay_queue.extend(queued)
        print(f"[match]       *** M4: PAWN MOVEMENT REPLAY queued {len(queued)} captured ch3 "
              f"bunches ({sum(b['bits'] for b in queued)} bits, WW3_PAWN_MOVEMENT_REPLAY); "
              f"oracle = _deploy_gates_live.py LOCATION leaves (0,0,-10000) ***")
        return True

    def note_client_start_spectator(self, conn, now=None):
        """Record C->S h310 `Server_StartSpectator` -- the client is spectating.

        Capture src~1626 pairs it with h208
        `Server_SetProfileMainEquipmentLoadoutIndex`; our client emits exactly
        that pair and then floods h73 `ServerSetSpectatorLocation`, so h310 may
        be seen once but the surrounding traffic repeats.  First sighting wins.
        """
        if getattr(conn, "_client_start_spectator", False):
            return False
        conn._client_start_spectator = True
        conn._client_start_spectator_t = time.time() if now is None else float(now)
        return True

    def note_client_map_opened(self, conn, now=None):
        """Record C->S h281 `Server_OnMapOpened` -- the deploy screen is up."""
        if getattr(conn, "_client_map_opened", False):
            return False
        conn._client_map_opened = True
        conn._client_map_opened_t = time.time() if now is None else float(now)
        return True

    def note_client_player_in_game(self, conn):
        """Record PS h65 `Server_PlayerInGameNotify`.

        The reference log shows this is emitted *by*
        `SetNewPlayerState(MainMenu -> InGame)`, the same event that fires
        `MapLoadingEnd` -- so it is the client's own statement that its
        synchronization checklist completed and the loading layer is gone.
        """
        if getattr(conn, "_client_player_in_game", False):
            return False
        conn._client_player_in_game = True
        return True

    def note_client_respawn_requested(self, conn):
        """Record C->S h287 `Server_RequestRespawnAtCapturePoint` -- DEPLOY pressed.

        This is the capture's own trigger for source 1934 (src~1841 -> src 1934),
        so when the client can produce it, it takes precedence over the h281/h65
        fallback and fires without an arming delay.
        """
        if getattr(conn, "_client_respawn_requested", False):
            return False
        conn._client_respawn_requested = True
        return True

    def maybe_release_deploy_transition(self, s, addr, conn, now=None):
        """Release captured source 1934 on client evidence instead of on h279.

        `WW3_STRICT_PLAYER_IN_GAME_ORDER=1` models the capture faithfully: run the
        post-h65 profile chain, then wait for a *fresh* h279
        (`Server_OnClientPreloadWeaponsFinished`) before releasing the deploy
        transition.  In the capture that h279 arrives right after the human
        presses DEPLOY.

        Turn 8 measured why that deadlocks here.  Our client emits h279 once,
        early -- before the profile chain completes, so it is correctly ignored --
        and it can never press DEPLOY, because `AWW3GamePlayerController::
        ClRespawnTarget` (+0x15A0) is NULL and the button renders "NOT READY"
        (`_deploy_gates_live.py`, `_live_frame.py`).  Nothing else will ever
        produce another h279.  So both sides wait for each other forever.

        The substitute trigger is the strongest evidence the client can give that
        it has reached the capture's post-deploy-screen state, and it is evidence
        this session has actually produced:

          * C->S h281 `Server_OnMapOpened`     -- the deploy map opened
          * C->S PS h65 `Server_PlayerInGameNotify` -- checklist complete, InGame

        No new bytes reach the wire: this only calls the existing
        `maybe_send_late_transition`, which still validates capture source 1934
        field by field against `STRICT_TRANSITION_SHA256` and refuses on any
        mismatch.  Opt-in, once per connection, and never ahead of the strict
        profile chain it is layered on top of.
        """
        if not (self.deploy_release_enabled() or self.deploy_after_spectator_enabled()):
            return False
        if getattr(conn, "_deploy_release_done", False):
            return False
        if getattr(conn, "_strict_transition_done", False):
            return False
        # Never jump the strict experiment's own ordering when it is running.
        if (self.strict_player_in_game_order_enabled()
                and not getattr(conn, "_strict_profiles_complete", False)):
            return False
        current = time.time() if now is None else float(now)
        # The capture's own trigger wins outright, with no arming delay: this is
        # exactly the src~1841 -> src 1934 exchange.
        faithful = getattr(conn, "_client_respawn_requested", False)
        if self.deploy_after_spectator_enabled():
            # h310 is the trigger in this mode, and it is the only one that can
            # fire: the h281/h65 evidence fallback is not a precondition.  The
            # live run that produced h310 never sent a real PS h65 at all -- its
            # strict sequence started from the synthetic h71 timeout -- so
            # requiring h65 here would deadlock exactly as turn 8's gate did.
            if not getattr(conn, "_client_start_spectator", False):
                return False
            try:
                settle = float(os.environ.get("WW3_DEPLOY_AFTER_SPECTATOR_DELAY_S", "0.0"))
            except ValueError:
                settle = 0.0
            if settle > 0 and current < getattr(
                    conn, "_client_start_spectator_t", current) + settle:
                return False
            faithful = True
        if not faithful:
            if not getattr(conn, "_client_map_opened", False):
                return False
            if not getattr(conn, "_client_player_in_game", False):
                return False
            try:
                arm_delay = float(os.environ.get("WW3_DEPLOY_RELEASE_DELAY_S", "3.0"))
            except ValueError:
                arm_delay = 3.0
            if current < (getattr(conn, "_client_map_opened_t", 0) or current) + arm_delay:
                return False
        try:
            liveness_s = float(os.environ.get("WW3_DEPLOY_RELEASE_LIVENESS_S", "2.0"))
        except ValueError:
            liveness_s = 2.0
        last = getattr(conn, "_last_client_bunch_t", 0) or 0
        if liveness_s > 0 and (not last or current - last > liveness_s):
            if not getattr(conn, "_deploy_release_wait_logged", False):
                conn._deploy_release_wait_logged = True
                print(f"[match]       deploy release armed but holding: last client "
                      f"bunch {'never' if not last else f'{current - last:.1f}s ago'} "
                      f"(need <= {liveness_s}s, WW3_DEPLOY_RELEASE_LIVENESS_S)")
            return False
        # Satisfy the strict gate the same way a fresh h279 would have.
        conn._strict_post_profile_h279_ready = True
        sent = self.maybe_send_late_transition(s, addr, conn, force=True)
        if not sent:
            return False
        conn._deploy_release_done = True
        conn._deploy_release_sent_t = current
        if getattr(conn, "_client_respawn_requested", False):
            why = "C->S h287 Server_RequestRespawnAtCapturePoint (the capture's own trigger)"
        elif self.deploy_after_spectator_enabled():
            why = (f"C->S h{PC_RPC_START_SPECTATOR} Server_StartSpectator "
                   "(WW3_DEPLOY_AFTER_SPECTATOR: the capture only ever answers a "
                   "client that is already spectating)")
        else:
            why = "h281 Server_OnMapOpened + PS h65 Server_PlayerInGameNotify"
        print(f"[match]       *** deploy transition released on {why}; "
              "captured source 1934 = Client_OnStopSpectatorBeforeDeploy + "
              "Client_StopSpectator + ClientSetViewTarget + ClientRestart(9372) + "
              "ClientSetViewTarget + ClientSetCameraMode + ClientSetRotation; "
              "oracle = C->S h64 + h280 Server_OnMapClosed and h73 stops ***")
        return True

    @staticmethod
    def inv_sync_bind_enabled():
        return os.environ.get("WW3_INV_SYNC_BIND", "0") == "1"

    def maybe_send_inv_sync_bind(self, s, addr, conn, now=None):
        """Send ONE ch3 RepLayout block for InventoryManager subobject 9384.

        Carries `CurrentItemRepInfo.CurrentItem` (h3) and `SvReplicatedInventory`
        (h10/h11 + h15..h20).  Those are the three inputs
        `UWW3InventoryManagerBase::IsSynchronized` (0x140c37770) is missing on the
        live client -- `ClientCurrentItem` (+0x290, set by
        `OnRep_CurrentItemRepInfo`), `+0x2B9` (set by
        `OnRep_ReplicatedInventory`) and a struct that passes
        `FWW3ReplicatedInventory::IsValid`.  Either RepNotify then reaches a
        broadcast of the delegate at +0xF0, which is the only way
        `0x1411c0f30` runs and the only producer of the `InventoryManager` bit.

        Framing is the capture's: same channel, same subobject, same
        stably-named content block and the same reliable ch3 bunch shape as the
        existing CAM/IM resend.  Gating matches the other one-shot experiments --
        opt-in, once per connection, held until ownership has settled and the
        client is demonstrably still transmitting, and fail-closed on both the
        payload identity and on any struct that could not satisfy the predicate.
        """
        if not self.inv_sync_bind_enabled():
            return False
        if getattr(conn, "_inv_sync_bind_done", False):
            return False
        if getattr(conn, "_inv_sync_bind_failed", False):
            return False
        if not getattr(conn, "_ownership_done_t", 0):
            return False
        # Never race the capture's own IM block: it owns h22 and the
        # WeaponsPreloadRequest handles, and landing first keeps the A/B clean.
        if inv_attach_enabled() and cam_im_after_ack_enabled() \
                and not getattr(conn, "_cam_im_resend_done", False):
            return False
        current = time.time() if now is None else float(now)
        try:
            arm_delay = float(os.environ.get("WW3_INV_SYNC_BIND_DELAY_S", "6.0"))
        except ValueError:
            arm_delay = 6.0
        if current < (getattr(conn, "_ownership_done_t", 0) or current) + arm_delay:
            return False

        try:
            liveness_s = float(os.environ.get("WW3_INV_SYNC_BIND_LIVENESS_S", "2.0"))
        except ValueError:
            liveness_s = 2.0
        last_in = getattr(conn, "_last_client_bunch_t", 0)
        if liveness_s > 0 and (not last_in or current - last_in > liveness_s):
            quiet = "never" if not last_in else f"{current - last_in:.1f}s ago"
            if not getattr(conn, "_inv_sync_bind_wait_logged", False):
                conn._inv_sync_bind_wait_logged = True
                print(f"[match]       inv sync bind armed but holding: last client "
                      f"bunch {quiet} (need <= {liveness_s:.1f}s, "
                      f"WW3_INV_SYNC_BIND_LIVENESS_S)")
            return False

        def _env_int(name, default):
            try:
                return int(os.environ.get(name, str(default)))
            except ValueError:
                return default

        mode = (os.environ.get("WW3_INV_SYNC_BIND_MODE") or "weapons").strip().lower()
        primary = _env_int("WW3_INV_SYNC_BIND_PRIMARY",
                           inventory_sync.CAPTURE_PRIMARY_WEAPON)
        secondary = _env_int("WW3_INV_SYNC_BIND_SECONDARY",
                             inventory_sync.CAPTURE_SECONDARY_WEAPON)
        raw_force = (os.environ.get("WW3_INV_SYNC_BIND_FORCE_VAR") or "").strip()
        force_var = int(raw_force) if raw_force else None
        try:
            bits = inventory_sync.build_inventory_sync_block_bits(
                mode=mode, primary_weapon=primary, secondary_weapon=secondary,
                force_replication_var=force_var)
        except ValueError as exc:
            conn._inv_sync_bind_failed = True
            print(f"[match]       ! inv sync bind refused: {exc} "
                  f"(mode={mode!r}) -- not sending")
            return False

        digest = inventory_sync.packet_sha256(bits)
        default_shape = (mode == "weapons" and force_var is None
                         and primary == inventory_sync.CAPTURE_PRIMARY_WEAPON
                         and secondary == inventory_sync.CAPTURE_SECONDARY_WEAPON)
        if default_shape and (len(bits) != INV_SYNC_PACKET_BITS
                              or digest != INV_SYNC_PACKET_SHA256):
            conn._inv_sync_bind_failed = True
            print(f"[match]       ! inv sync bind payload identity mismatch "
                  f"({len(bits)} bits, sha256 {digest[:16]}...) -- not sending")
            return False

        by = bytearray((len(bits) + 7) // 8)
        for i, bit in enumerate(bits):
            if bit:
                by[i >> 3] |= 1 << (i & 7)
        conn._inv_sync_bind_done = True
        conn._inv_sync_bind_sent_t = current
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunches=[cc.make_bunch(
            len(bits), bytes(by), ch_index=3,
            ch_seq=self.next_chan_seq(conn, 3), ch_type=cc.CHTYPE_ACTOR,
            bOpen=0, bReliable=1)],
            audit_tag="inv sync bind ch3 SvReplicatedInventory(9384)")
        print(f"[match]       *** ch3 InventoryManager({inventory_sync.IM_NETGUID}) "
              f"SvReplicatedInventory sent: mode={mode} primary={primary} "
              f"secondary={secondary} BatchID=1, {len(bits)} bits "
              f"(WW3_INV_SYNC_BIND); oracle = _inv_sync_gates.py mask 0xeb -> 0xff "
              f"(IsSynchronized -> broadcast +0xF0 -> 0x1411c0f30) ***")
        return True

    def note_action_replicator_bunch(self, conn, bits):
        """Decode client ch80 traffic with AWW3ActionReplicator's own ValueMax.

        Scoped strictly to ch80 and to sessions that actually opened it, so no
        other actor channel's decoding changes.
        """
        try:
            fields = action_replicator.describe_action_replicator_fields(bits)
        except Exception:
            fields = []
        if not fields:
            return
        print("[match]       *** client ch80 ActionReplicator RPCs="
              f"{[(h, name) for h, name, _n in fields]} ***")
        for handle, _name, _nbits in fields:
            if handle != action_replicator.RPC_SERVER_ACK_ACTIONS_RECEIVED:
                continue
            conn._action_ack_count = getattr(conn, "_action_ack_count", 0) + 1
            if not getattr(conn, "_action_probe_acked", False):
                conn._action_probe_acked = True
                sent_t = getattr(conn, "_action_probe_sent_t", 0)
                delta = f" after {(time.time() - sent_t) * 1000:.0f}ms" if sent_t else ""
                print("[match]       *** GREEN: client sent Server_AckActionsReceived"
                      f"{delta} -- Client_ReceivePacket dispatched on ch80 ***")

    def _send_captured_ps_update(self, s, addr, conn, *, source_index, expected_bits,
                                 expected_sha, done_attr, env_flag, label):
        """Replay one captured unreliable ch7 PlayerState property bunch, once.

        Same fail-closed identity gate as source1056: every header field plus a
        SHA-256 of the payload bit string, so a regenerated capture artifact stops
        the experiment instead of silently sending different bits.
        """
        if os.environ.get(env_flag, "0") != "1":
            return False
        if getattr(conn, done_attr, False):
            return False
        ps_channel = getattr(conn, "ps_channel", None)
        if not getattr(conn, "ps_opened", False) or not ps_channel:
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            stream = json.load(open(os.path.join(here, "real_replay_stream.json"),
                                    encoding="utf-8"))
            source = dict(stream[source_index])
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! {label} source unavailable: {exc}")
            return False
        payload = source.get("payload", "")
        if (int(source.get("chIndex", -1)) != 7
                or int(source.get("bits", -1)) != expected_bits
                or int(source.get("bOpen", 0)) != 0
                or int(source.get("bClose", 0)) != 0
                or int(source.get("bReliable", 1)) != 0
                or int(source.get("bPartial", 0)) != 0
                or int(source.get("bPartialInitial", 0)) != 0
                or int(source.get("bPartialFinal", 0)) != 0
                or int(source.get("bHasPackageMapExports", 0)) != 0
                or int(source.get("bHasMustBeMappedGUIDs", 0)) != 0
                or int(source.get("chType", -1)) != cc.CHTYPE_ACTOR
                or len(payload) != expected_bits
                or hashlib.sha256(payload.encode("ascii")).hexdigest() != expected_sha):
            print(f"[match]       ! {label} source{source_index} identity mismatch; refusing")
            return False
        source["chIndex"] = int(ps_channel)
        source["_src_idx"] = source_index
        bunch = self.build_replay_bunch(conn, source)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunch=bunch,
                         audit_tag=f"{label} source{source_index}")
        setattr(conn, done_attr, True)
        print(f"[match]       *** {label}: captured source{source_index} sent on "
              f"ch{ps_channel} ({env_flag}) ***")
        return True

    def maybe_send_ps_master_link(self, s, addr, conn):
        """PS h54 bIsConnectedToMaster=true -- the capture sends it after h279."""
        return self._send_captured_ps_update(
            s, addr, conn,
            source_index=PS_MASTER_LINK_SOURCE,
            expected_bits=PS_MASTER_LINK_BITS,
            expected_sha=PS_MASTER_LINK_SHA256,
            done_attr="_ps_master_link_done",
            env_flag="WW3_PS_MASTER_LINK",
            label="PS master link bIsConnectedToMaster")

    def maybe_send_lock_vehicle_reply(self, s, addr, conn):
        """PS h40 LockVehicleMode -- the capture's answer to C->S PS h71."""
        return self._send_captured_ps_update(
            s, addr, conn,
            source_index=PS_LOCK_VEHICLE_REPLY_SOURCE,
            expected_bits=PS_LOCK_VEHICLE_REPLY_BITS,
            expected_sha=PS_LOCK_VEHICLE_REPLY_SHA256,
            done_attr="_ps_lock_vehicle_reply_done",
            env_flag="WW3_PS_LOCK_VEHICLE_REPLY",
            label="PS LockVehicleMode reply")

    def note_profile_prologue_ack(self, conn):
        """C->S h177 is the client's ACK of Client_ReceiveServerStartDate."""
        if getattr(conn, "_profile_prologue_acked", False):
            return False
        conn._profile_prologue_acked = True
        print("[match]       *** client acked Client_ReceiveServerStartDate "
              "(C->S h177 Server_ClientReceivedServerStartDate) ***")
        return True

    def begin_strict_player_in_game_sequence(self, s, addr, conn, *, synthetic=False,
                                             now=None):
        """Send source1056 and arm its exact, timed profile-sync continuation once."""
        if not self.strict_player_in_game_order_enabled():
            return False
        if getattr(conn, "_strict_player_in_game_started", False):
            return False
        try:
            specs = self._load_strict_profile_sync_specs(conn)
        except (OSError, ValueError, IndexError) as exc:
            print(f"[match]       ! strict player-in-game sequence unavailable: {exc}")
            conn._strict_player_in_game_failed = True
            return False
        if not self.maybe_reply_player_in_game_notify(s, addr, conn):
            print("[match]       ! strict player-in-game h30 failed; profile chain held")
            conn._strict_player_in_game_failed = True
            return False
        started = time.time() if now is None else float(now)
        conn._strict_player_in_game_started = True
        conn._strict_h65_seen = not synthetic
        conn._strict_h65_synthetic = bool(synthetic)
        conn._strict_h65_fallback_at = 0
        conn._strict_profile_started_at = started
        conn._strict_profile_queue = [
            (started + delay_s, source) for delay_s, source in specs
        ]
        conn._strict_profiles_complete = False
        origin = "synthetic readiness after h71 timeout" if synthetic else "real PS h65"
        print("[match]       *** strict player-in-game order started from "
              f"{origin}: h30 now, {len(specs)} captured profile sources timed ***")
        return True

    def note_strict_playerstate_h71(self, conn, now=None):
        """Arm the capture's h71->h65 timeout when native h65 cannot be invoked again."""
        if not self.strict_player_in_game_order_enabled():
            return False
        if (getattr(conn, "_strict_player_in_game_started", False)
                or getattr(conn, "_strict_h65_fallback_at", 0)):
            return False
        observed = time.time() if now is None else float(now)
        conn._strict_h71_seen_at = observed
        conn._strict_h65_fallback_at = observed + STRICT_H71_TO_H65_FALLBACK_S
        print("[match]       *** strict order: PS h71 observed; h65 semantic fallback "
              f"armed for +{STRICT_H71_TO_H65_FALLBACK_S * 1000:.0f}ms ***")
        return True

    def maybe_service_strict_player_in_game(self, s, addr, conn, now=None):
        """Service the h71 fallback and capture-timed profile continuation."""
        if not self.strict_player_in_game_order_enabled():
            return False
        current = time.time() if now is None else float(now)
        sent = False
        fallback_at = getattr(conn, "_strict_h65_fallback_at", 0)
        if (fallback_at and current >= fallback_at
                and not getattr(conn, "_strict_player_in_game_started", False)):
            conn._strict_h65_fallback_at = 0
            sent = self.begin_strict_player_in_game_sequence(
                s, addr, conn, synthetic=True, now=current) or sent
        queue = getattr(conn, "_strict_profile_queue", None)
        while queue and queue[0][0] <= current:
            _due, source = queue.pop(0)
            bunch = self.build_replay_bunch(conn, source)
            self.flush_acks(s, addr, conn)
            self.send_packet(
                s, addr, conn, bunch=bunch,
                audit_tag=f"strict post-h65 profile src={source['_src_idx']}")
            print(f"[match]       *** strict post-h65 captured source "
                  f"{source['_src_idx']} sent on ch{source['chIndex']} ***")
            sent = True
        if (getattr(conn, "_strict_player_in_game_started", False)
                and not queue
                and not getattr(conn, "_strict_profiles_complete", False)):
            conn._strict_profiles_complete = True
            print("[match]       *** strict post-h65 profile chain complete; "
                  "waiting for a fresh h279 ***")
        return sent

    def maybe_reply_player_in_game_notify(self, s, addr, conn):
        """Answer PS::Server_PlayerInGameNotify with its captured one-shot reply.

        In the working flow, C->S PS handle 65 is followed 64.7 ms later by
        real_replay_stream source 1056: a 25-bit reliable PlayerState bunch carrying
        Client_RejoinIsPossible(bool).  Replay that bunch byte-for-byte, changing only
        the actor channel index to the channel on which this connection's local PS opened.
        """
        if getattr(conn, "_player_in_game_reply_done", False):
            return False
        ps_channel = getattr(conn, "ps_channel", None)
        if not getattr(conn, "ps_opened", False) or ps_channel is None:
            return False
        here = os.path.dirname(os.path.abspath(__file__))
        try:
            stream = json.load(open(os.path.join(here, "real_replay_stream.json"),
                                    encoding="utf-8"))
            source = dict(stream[PS_REJOIN_REPLY_SOURCE])
        except (OSError, ValueError, IndexError) as e:
            print(f"[match]       ! PS h65 reply source unavailable: {e}")
            return False
        # Fail closed if the capture artifact changes under this hard evidence anchor.
        if (int(source.get("chIndex", -1)) != 7
                or int(source.get("bits", -1)) != 25
                or int(source.get("bReliable", 0)) != 1
                or int(source.get("bOpen", 0)) != 0
                or int(source.get("bClose", 0)) != 0
                or int(source.get("bPartial", 0)) != 0
                or int(source.get("bPartialInitial", 0)) != 0
                or int(source.get("bPartialFinal", 0)) != 0
                or int(source.get("bHasPackageMapExports", 0)) != 0
                or int(source.get("bHasMustBeMappedGUIDs", 0)) != 0
                or int(source.get("chType", -1)) != cc.CHTYPE_ACTOR
                or source.get("payload") != "0101111000011110010000001"):
            print("[match]       ! PS h65 reply source1056 identity mismatch; refusing")
            return False
        source["chIndex"] = int(ps_channel)
        source["_src_idx"] = PS_REJOIN_REPLY_SOURCE
        bunch = self.build_replay_bunch(conn, source)
        self.flush_acks(s, addr, conn)
        self.send_packet(s, addr, conn, bunch=bunch,
                         audit_tag="PS h65 Client_RejoinIsPossible source1056")
        conn._player_in_game_reply_done = True
        print("[match]       *** PS Server_PlayerInGameNotify h65 -> exact captured "
              f"Client_RejoinIsPossible source1056 on ch{ps_channel} (once) ***")
        return True

    def replay_real_spawn(self, s, addr, conn):
        """Send the captured server's first actor bunches BYTE-FOR-BYTE (partial split:
        exports bunch + payload bunch), then optionally queue the rest of the early world."""
        here = os.path.dirname(os.path.abspath(__file__))
        if os.environ.get("WW3_REPLAY_FULL") == "1":
            stream = os.path.join(here, "real_replay_stream.json")
            self.queue_replay_stream(conn, stream)
            conn.replay_total = len(conn.replay_queue)
            conn.spawned = True
            return                                    # the keepalive loop drip-feeds it
        specs = json.load(open(os.path.join(here, "real_spawn_bunches.json")))
        self.flush_acks(s, addr, conn)
        for spec in specs:
            bits = [int(c) for c in spec["payload"]]
            by = bytearray((len(bits) + 7) // 8)
            for i, b in enumerate(bits):
                if b: by[i >> 3] |= (1 << (i & 7))
            bunch = cc.make_bunch(len(bits), bytes(by), ch_index=spec["chIndex"],
                                  ch_seq=self.next_chan_seq(conn, spec["chIndex"]),
                                  ch_type=spec["chType"] or cc.CHTYPE_ACTOR,
                                  bOpen=spec["bOpen"],
                                  bHasPackageMapExports=spec["bHasPackageMapExports"],
                                  bHasMustBeMappedGUIDs=spec.get("bHasMustBeMappedGUIDs", 0),
                                  bPartial=spec["bPartial"],
                                  bPartialInitial=spec["bPartialInitial"] or 0,
                                  bPartialFinal=spec["bPartialFinal"] or 0)
            self.send_packet(s, addr, conn, bunch=bunch)
            print(f"[match]       -> REPLAY bunch ch{spec['chIndex']} {len(bits)} bits "
                  f"(open={spec['bOpen']} exports={spec['bHasPackageMapExports']} "
                  f"partial i={spec['bPartialInitial']}/f={spec['bPartialFinal']})")
        conn.spawned = True
        self.queue_world_after_pc(conn, here, skip=len(specs))

    def _filter_partial_chain(self, bunches):
        """Drop orphan partial-finals (no matching initial on that channel)."""
        pending = {}
        cleaned = []
        for b in bunches:
            ch = b["chIndex"]
            if b.get("bPartial") and b.get("bPartialFinal") and not pending.get(ch):
                continue
            if b.get("bPartial") and b.get("bPartialInitial"):
                pending[ch] = True
            elif b.get("bPartial") and b.get("bPartialFinal"):
                pending[ch] = False
            cleaned.append(b)
        return cleaned

    def _ambient_channel_filter(self, owned_chs):
        """-> (predicate, description) for WW3_AMBIENT_CHANNELS.

        unset / "all"  : every channel (legacy behaviour)
        "owned"        : only channels the ownership bootstrap already opened. This is the
                         low-risk window: it feeds more of the *local* player's own state
                         (PlayerState ch7, pawn ch3, weapons ch4/ch5, GameState ch53)
                         without introducing actors on channels the client never opened.
        "2,7,53"       : explicit list
        """
        raw = (os.environ.get("WW3_AMBIENT_CHANNELS", "7,53") or "").strip().lower()
        if not raw or raw == "all":
            return (lambda ch: True), "all"
        if raw == "owned":
            allowed = set(owned_chs)
            return (lambda ch: ch in allowed), f"owned={sorted(allowed)}"
        try:
            # PowerShell serializes an environment array as space-separated text
            # (e.g. `7 53`), while shell callers commonly use `7,53` or `7;53`.
            # Accept all three forms so a targeted channel filter cannot silently
            # fall back to the unsafe `all` behavior.
            import re
            allowed = {int(x) for x in re.split(r"[;,\s]+", raw) if x.strip()}
        except ValueError:
            print(f"[match]       ! bad WW3_AMBIENT_CHANNELS={raw!r} — treating as 'all'")
            return (lambda ch: True), "all"
        return (lambda ch: ch in allowed), f"list={sorted(allowed)}"

    def _queue_ambient_after_ownership(self, conn, here, owned_src, owned_chs=()):
        """After the sync-critical ownership slice, drip more capture bunches.

        WW3_AMBIENT_LIMIT=0 disables. Default 120 bunches starting at stream idx 18
        (first foreign PlayerState), skipping indices already in the ownership set.

        WW3_AMBIENT_START moves the window start; WW3_AMBIENT_CHANNELS restricts it to a
        channel set (see _ambient_channel_filter). Everything queued here is a bit-exact
        capture bunch -- nothing is synthesised -- so the only risk is ordering, not framing.
        """
        try:
            ambient_limit = int(os.environ.get("WW3_AMBIENT_LIMIT", "120"))
        except ValueError:
            ambient_limit = 120
        if ambient_limit <= 0:
            print("[match]       (WW3_AMBIENT_LIMIT=0 — no ambient world after ownership)")
            return
        try:
            ambient_start = int(os.environ.get("WW3_AMBIENT_START", "18"))
        except ValueError:
            ambient_start = 18
        # Captured replay records can exceed the live UE channel's negotiated
        # bunch budget (the client rejects these with Bunch data overflowed and
        # closes the connection).  Keep the ambient stream playable by dropping
        # only those oversized artifacts; the ownership bootstrap remains exact.
        try:
            ambient_max_bits = int(os.environ.get("WW3_AMBIENT_MAX_BITS", "5000"))
        except ValueError:
            ambient_max_bits = 5000
        stream_path = os.path.join(here, "real_replay_stream.json")
        if not os.path.isfile(stream_path):
            return
        stream = json.load(open(stream_path))
        keep_ch, ch_desc = self._ambient_channel_filter(owned_chs)
        ambient = []
        # Some narrowly selected post-transition actors use static archetype
        # NetGUIDs that were exported earlier in the real capture.  Replaying
        # the actor without those exports makes UE reject the bunch and close
        # the connection.  Allow the launcher to prepend those exact export
        # chains while keeping the normal ambient window narrow.
        prereq_raw = (os.environ.get("WW3_AMBIENT_PREREQS", "") or "").strip()
        prereqs = []
        if prereq_raw:
            try:
                prereqs = sorted({int(v.strip()) for v in prereq_raw.split(",") if v.strip()})
            except ValueError:
                print(f"[match]       ! bad WW3_AMBIENT_PREREQS={prereq_raw!r} — ignoring")
                prereqs = []
        selected = set()
        for i in prereqs:
            if i < 0 or i >= len(stream) or i in owned_src:
                continue
            bunch = dict(stream[i])
            bunch["_src_idx"] = i
            bunch["_ambient"] = 1
            ambient.append(bunch)
            selected.add(i)
        for i in range(ambient_start, len(stream)):
            if i in owned_src:
                continue
            if i in selected:
                continue
            if len(ambient) >= ambient_limit:
                break
            if not keep_ch(stream[i]["chIndex"]):
                continue
            if ambient_max_bits > 0 and int(stream[i].get("bits", 0)) > ambient_max_bits:
                print(f"[match]       - skipping oversized ambient src={i} "
                      f"ch={stream[i].get('chIndex')} bits={stream[i].get('bits')} "
                      f"(WW3_AMBIENT_MAX_BITS={ambient_max_bits})")
                continue
            bunch = dict(stream[i])
            bunch["_src_idx"] = i
            bunch["_ambient"] = 1
            ambient.append(bunch)
        ambient = self._filter_partial_chain(ambient)
        if not ambient:
            print(f"[match]       (ambient window empty: start={ambient_start} "
                  f"channels={ch_desc})")
            return
        # When attachment replication is deferred, ambient capture can still contain
        # reliable follow-up bunches for those channels.  Keeping them in the main
        # queue lets one arrive before the channel's deferred OPEN, which UE rejects
        # as "reliable bunch before channel was fully open".  Move every blocked
        # ambient bunch behind the same release barrier as the bootstrap chain.
        if os.environ.get("WW3_SKIP_ATTACHMENTS") == "1":
            blocked = {4, 5, 85, 86, 87, 88}
            deferred = [b for b in ambient if int(b.get("chIndex", -1)) in blocked]
            ambient = [b for b in ambient if int(b.get("chIndex", -1)) not in blocked]
            if deferred:
                conn._deferred_attachment_queue = list(
                    getattr(conn, "_deferred_attachment_queue", []) or []
                ) + deferred
                print(f"[match]       *** M4: deferring {len(deferred)} ambient "
                      "attachment bunches until channel OPEN/release ***")
        per_ch = {}
        for b in ambient:
            per_ch[b["chIndex"]] = per_ch.get(b["chIndex"], 0) + 1
        conn.replay_queue.extend(ambient)
        conn.replay_total = len(conn.replay_queue)
        print(f"[match]       + ambient world {len(ambient)} bunches "
              f"(WW3_AMBIENT_LIMIT={ambient_limit} start={ambient_start} "
              f"channels={ch_desc}) per-ch={dict(sorted(per_ch.items()))}")

    def queue_world_after_pc(self, conn, here, skip=2):
        """After the PlayerController open, drip-feed world bunches.

        Default (WW3_BOOTSTRAP=ownership|minimal|default): curated ownership slice
        (HUD, early GameState, streaming, Pawn, local weapons, local PS 9362) — see
        ownership_bootstrap.json — then optional ambient capture window.

        WW3_BOOTSTRAP=full + WW3_WORLD_LIMIT: legacy stream window after PC.
        WW3_NO_WORLD_REPLAY=1: PC open only.
        """
        if os.environ.get("WW3_NO_WORLD_REPLAY") == "1":
            print("[match]       (WW3_NO_WORLD_REPLAY=1 — not queuing world stream)")
            return

        mode = (os.environ.get("WW3_BOOTSTRAP") or "ownership").strip().lower()
        if mode in ("ownership", "minimal", "default", "", "capture", "capture_order",
                    "capture-order", "linear"):
            boot_path = os.path.join(here, "ownership_bootstrap.json")
            # Always regenerate so WW3_BOOTSTRAP=capture_order takes effect.
            try:
                import build_ownership_bootstrap as bob
                # Must NOT call argparse main() — that reads sys.argv and dies on "7871".
                bob.write_bootstrap(mode)
            except Exception as e:
                print(f"[match]       ! bootstrap build failed: {e}")
            if os.path.isfile(boot_path):
                boot = json.load(open(boot_path))
                rest = [b for b in boot if int(b.get("_src_idx", -1)) >= skip]
                cleaned = self._filter_partial_chain(rest)
                # The real server's ch2 src=8 is a MustBeMapped-gated post-spawn
                # transition (ClientRestart + view/camera RPCs).  A raw replay
                # cannot reproduce that gate, so sending it in the pre-pawn
                # ownership drip makes the RPC resolve against a missing pawn.
                # Keep it out of the initial queue; maybe_send_post_pawn_pc_state
                # replays the exact bunch after ch3 opens.
                if (os.environ.get("WW3_POST_PAWN_PC_STATE", "1") == "1"
                        and os.environ.get("WW3_DEFER_POST_PAWN_SRC8", "1") == "1"):
                    before_src8 = len(cleaned)
                    cleaned = [b for b in cleaned if int(b.get("_src_idx", -1)) != 8]
                    if len(cleaned) != before_src8:
                        print("[match]       *** M4: deferring ownership src=8 until pawn open "
                              "(WW3_DEFER_POST_PAWN_SRC8=1) ***")
                if os.environ.get("WW3_SKIP_ATTACHMENTS") == "1":
                    blocked = {4, 5, 85, 86, 87, 88}
                    before = len(cleaned)
                    conn._deferred_attachment_queue = [
                        b for b in cleaned if int(b.get("chIndex", -1)) in blocked
                    ]
                    cleaned = [b for b in cleaned if int(b.get("chIndex", -1)) not in blocked]
                    conn._deferred_attachments_active = False
                    print(f"[match]       *** M4: withholding attachment channels during initial load "
                          f"({before - len(cleaned)} bunches deferred; WW3_SKIP_ATTACHMENTS=1) ***")
                # The local Domination PlayerState's first RepLayout can refer to
                # the static WW3TeamSatelliteObjectReplication class (NetGUID 35).
                # In the capture that class is exported by the first satellite
                # actor (stream index 160), which occurs before later PS updates
                # but is absent from the curated ownership slice.  An unresolved
                # sub-object class makes UE reject ch7 and leaves LoadingMap
                # permanently latched.  Keep this as an opt-in A/B until the
                # client-side transition is verified; the captured bunch is
                # replayed intact and is not synthesized.
                if (os.environ.get("WW3_PRELOAD_SATELLITE_EXPORT", "1") == "1"
                        and not any(int(b.get("_src_idx", -1)) == 160 for b in cleaned)):
                    try:
                        stream_for_preload = json.load(open(
                            os.path.join(here, "real_replay_stream.json"), encoding="utf-8"))
                        preload = dict(stream_for_preload[160])
                        cleaned.insert(0, preload)
                        print("[match]       *** preloading captured satellite export "
                              "(stream 160 / NetGUID 35) before ownership PS ***")
                    except (OSError, ValueError, IndexError) as e:
                        print(f"[match]       ! satellite export preload unavailable: {e}")
                conn.replay_queue = cleaned
                conn.replay_total = len(cleaned)
                conn.replay_sent = 0
                conn.pawn_sent = False
                conn._bootstrap_opens_action_replicator = bootstrap_opens_action_replicator(cleaned)
                if conn._bootstrap_opens_action_replicator:
                    print(f"[match]       bootstrap already opens "
                          f"ch{TEAM_ACTION_REPLICATOR_CHANNEL} WW3ActionReplicator "
                          "(WW3_WORLD_FILL); WW3_TEAM_ACTION_REPLICATOR will not "
                          "open it a second time")
                owned_src = {int(b.get("_src_idx", -1)) for b in boot}
                owned_chs = {int(b["chIndex"]) for b in boot}
                print(f"[match]       queued OWNERSHIP bootstrap {len(cleaned)} bunches "
                      f"mode={mode or 'ownership'} (after PC skip={skip}, "
                      f"~{sum(b['bits'] for b in cleaned)//8} B)")
                self._queue_ambient_after_ownership(conn, here, owned_src, owned_chs)
                return
            print("[match]       ! ownership_bootstrap.json missing — falling back to full window")

        stream_path = os.path.join(here, "real_replay_stream.json")
        if not os.path.isfile(stream_path):
            print("[match]       ! no real_replay_stream.json — PC only")
            return
        stream = json.load(open(stream_path))
        rest = stream[skip:]
        try:
            limit = int(os.environ.get("WW3_WORLD_LIMIT", "160"))
        except ValueError:
            limit = 160
        if limit > 0:
            rest = rest[:limit]
        cleaned = self._filter_partial_chain(rest)
        conn.replay_queue = cleaned
        conn.replay_total = len(cleaned)
        conn.replay_sent = 0
        conn.pawn_sent = False
        lim_note = "full" if limit <= 0 else f"limit={limit}"
        print(f"[match]       queued {len(cleaned)} stream bunches after PC "
              f"(skip={skip}, {lim_note}, mode={mode})")

    # ---- M4: spawn the player's PlayerController (capture-faithful open + world queue) ----
    def send_player_controller(self, s, addr, conn, ch_index=2):
        """On NMT_Join: open the owning PlayerController channel.

        Default = byte-replay the captured PC open (exports + SerializeNewActor with
        rotation + RepLayout + subobject stubs), then queue the rest of the early world.
        Set WW3_GENERATE_SPAWN=1 to build the open from our writers (still uses captured
        RepLayout bits). Set WW3_REPLAY_SPAWN=1 / WW3_REPLAY_FULL=1 for older explicit modes.
        """
        here = os.path.dirname(os.path.abspath(__file__))
        if os.environ.get("WW3_REPLAY_SPAWN") == "1" or os.environ.get("WW3_REPLAY_FULL") == "1":
            return self.replay_real_spawn(s, addr, conn)
        if os.environ.get("WW3_GENERATE_SPAWN") == "1":
            return self.generate_player_controller(s, addr, conn, ch_index=ch_index)

        # Default M4 path: capture-faithful PC open + world drip-feed
        return self.replay_real_spawn(s, addr, conn)

    def generate_player_controller(self, s, addr, conn, ch_index=2):
        """Build PC open with our writers: export block (partial) + new actor w/ rotation
        + captured RepLayout bits + empty subobject stubs (partial final)."""
        here = os.path.dirname(os.path.abspath(__file__))
        claims = conn.claims or {}
        srv = claims.get("server", {})
        mp = os.environ.get("WW3_FORCE_MAP") or srv.get("map", "WW3_Gobi_New_P")
        level_pkg = MAP_PACKAGE_PATH.get(mp, f"/Game/Maps/{mp}")
        pc_pkg, pc_arch = PLAYER_CONTROLLER.get(srv.get("gameMode", 47), PLAYER_CONTROLLER[47])

        # Slice the captured RepLayout payload (819 bits) out of real_spawn_bunches.
        specs = json.load(open(os.path.join(here, "real_spawn_bunches.json")))
        all_bits = []
        for sp in specs:
            all_bits.extend(int(c) for c in sp["payload"])
        # After exports (3257) + new_actor header (122) = 3379, actor content header, then 819
        # Use decoder to extract cleanly
        from actor_channel import Bits, read_new_actor, read_content_blocks
        from netguid import PackageMap, GuidReader
        pm = PackageMap()
        gr = GuidReader(all_bits)
        gr.bit(); n = gr.i32()
        for _ in range(n):
            pm.load_object(gr, exporting=True)
        r = Bits(all_bits, gr.pos)
        info = read_new_actor(r, pm)
        assert not info.get("incomplete"), info
        blocks = read_content_blocks(r)
        assert blocks and blocks[0].get("isActor") and blocks[0].get("payloadBits") == 819
        rep_bits = blocks[0]["payload"]

        actor_ref = {"gid": ACTOR_NETGUID, "path": None, "no_load": True, "checksum": 0}
        w_exp = GuidWriter()
        write_export_block(w_exp, [
            {"gid": 13, "path": pc_arch, "checksum": PC_ARCH_CHECKSUM,
             "outer": {"gid": 15, "path": pc_pkg, "checksum": 0, "outer": None}},
            {"gid": 5, "path": "PersistentLevel", "checksum": 0, "no_load": True,
             "outer": {"gid": 7, "path": mp, "checksum": 0, "no_load": True,
                       "outer": {"gid": 9, "path": level_pkg, "checksum": 0,
                                 "no_load": True, "outer": None}}},
        ] + [
            {"gid": gid, "path": name, "checksum": csum, "no_load": True, "outer": actor_ref}
            for (gid, name, csum) in PC_SUBOBJECTS
        ])

        w_body = GuidWriter()
        write_new_actor(w_body, ACTOR_NETGUID, 13, 5,
                        location=info.get("location") or SPAWN_LOCATION,
                        rotation=info.get("rotation") or SPAWN_ROTATION)
        write_content_block(w_body, rep_bits, has_rep_layout=1)
        for gid, _name, _csum in PC_SUBOBJECTS:
            write_subobject_content_block(w_body, gid, stably_named=1)

        self.flush_acks(s, addr, conn)
        # Partial initial = exports only (matches capture)
        b0 = cc.make_bunch(w_exp.num, w_exp.get_bytes(), ch_index=ch_index,
                           ch_seq=self.next_chan_seq(conn, ch_index),
                           ch_type=cc.CHTYPE_ACTOR, bOpen=1, bHasPackageMapExports=1,
                           bPartial=1, bPartialInitial=1, bPartialFinal=0)
        self.send_packet(s, addr, conn, bunch=b0)
        b1 = cc.make_bunch(w_body.num, w_body.get_bytes(), ch_index=ch_index,
                           ch_seq=self.next_chan_seq(conn, ch_index),
                           ch_type=cc.CHTYPE_ACTOR, bOpen=0, bHasPackageMapExports=0,
                           bPartial=1, bPartialInitial=0, bPartialFinal=1)
        self.send_packet(s, addr, conn, bunch=b1)
        conn.spawned = True
        print(f"[match]       -> GENERATED PC spawn ch{ch_index}: "
              f"export={w_exp.num}b body={w_body.num}b rot={info.get('rotation')}")
        print(f"[match]          map={mp} level={level_pkg} loc={info.get('location')}")
        self.queue_world_after_pc(conn, here, skip=2)

    # ---- main dispatch ----
    def handle(self, s, data, addr):
        key = f"{addr[0]}:{addr[1]}"
        p = self.hs.parse_incoming(data)
        if p.get("is_handshake"):
            self.handle_handshake(s, data, addr, key, p)
        else:
            conn = self.conns.get(key)
            if not conn or conn.state == "HANDSHAKING":
                print(f"[match] <- non-handshake from unconnected {key} ({len(data)}B) -- ignoring")
                return
            self.handle_control(s, data, addr, conn)

    # ---- M1: handshake ----
    def handle_handshake(self, s, data, addr, key, p):
        if p.get("is_ack"):
            return
        if p.get("initial"):
            s.sendto(self.hs.build_challenge(key, self.server_time()), addr)
            self.conns.setdefault(key, Conn())
            print(f"[match] <- InitialConnect {key}  -> sent ConnectChallenge")
        else:
            if self.hs.validate_response(key, p["ts_bytes"], p["cookie"]):
                s.sendto(self.hs.build_ack(p["cookie"]), addr)
                c = self.conns.setdefault(key, Conn()); c.state = "CONNECTED"
                # UE4 InitSequence: BOTH the packet sequence and the reliable-bunch sequence
                # start from values derived from the cookie -- NOT from zero. If we start at 0
                # the client buffers our bunches as out-of-order forever (silent hang).
                srv_seq, cli_seq = sequences_from_cookie(p["cookie"])
                c.out_seq   = srv_seq
                c.out_chseq = srv_seq & (MAX_CHSEQUENCE - 1)
                c.init_reliable = srv_seq & (MAX_CHSEQUENCE - 1)
                c.chan_seq  = {}
                c.in_seq    = cli_seq
                print(f"[match] *** HANDSHAKE COMPLETE {key} -> connection OPEN (awaiting NMT_Hello) ***")
                print(f"[match]     InitSequence from cookie: out packet seq={srv_seq}, "
                      f"out reliable ChSeq starts {c.out_chseq + 1}, expect client seq={cli_seq}")
            else:
                print(f"[match] <- ChallengeResponse {key} INVALID cookie")

    # ---- M2: control channel ----
    def handle_control(self, s, data, addr, conn):
        p = cc.read_packet(data)
        if p.get("is_handshake"):
            return
        conn.pending_acks.append(p["seq"])
        if ACK_AUDIT and conn.pkt_audit:
            self.audit_note_acks(conn, p.get("acks"))
        responded = False
        for b in p["bunches"]:
            try:
                responded = self.handle_bunch(s, addr, conn, b) or responded
            except Exception as e:
                print(f"[match]   ! bunch parse error (ignored, connection kept alive): {e}")
        if not responded:
            self.flush_acks(s, addr, conn)           # ack-only packet

    def handle_bunch(self, s, addr, conn, b):
        """Dispatch one bunch. Returns True if we sent a reply."""
        # Client liveness stamp: experiments gate on this so a one-shot bunch is
        # never spent on a connection whose net thread has stopped ticking.
        conn._last_client_bunch_t = time.time()
        if b["bClose"]:
            print(f"[match]   <- CHANNEL CLOSE from client on ch{b['chIndex']} "
                  f"(reason={b['closeReason']}) -- the client is hanging up")
            conn.state = "CLOSED"
            return False
        if b["chIndex"] != 0:
            # Client actor-channel traffic (moves on ch2, PS updates on ch7, …).
            n = getattr(conn, "_actor_log_n", 0) + 1
            conn._actor_log_n = n
            nb = b.get("payloadBits") or b.get("bunchDataBits")
            if n <= 5 or n % 200 == 0:
                print(f"[match]   <- actor ch{b['chIndex']} bits={nb} "
                      f"open={b.get('bOpen')} rel={b.get('bReliable')} partial={b.get('bPartial')} (n={n})")
            # ServerNotifyLoadedWorld carries streamed /Game/Maps/… paths.
            # PlayerState has its own ClassNetCache (ValueMax=82), so the PC parser's
            # ValueMax=315 cannot decode these fields. Bind this path to the channel on
            # which the local PS open was actually replayed, not to a global ch7 guess.
            # ch80 AWW3ActionReplicator has its own ClassNetCache (ValueMax=14),
            # so neither the PC (315) nor the PS (82) parser can read it. Only
            # look when this session actually opened that channel.
            if (b["chIndex"] == TEAM_ACTION_REPLICATOR_CHANNEL
                    and getattr(conn, "_action_replicator_done", False)
                    and (nb or 0) >= 4):
                self.note_action_replicator_bunch(conn, bunch_payload_bits(b))
            ps_channel = getattr(conn, "ps_channel", None)
            if (getattr(conn, "ps_opened", False)
                    and ps_channel is not None
                    and b["chIndex"] == ps_channel
                    and (nb or 0) >= 16):
                try:
                    ps_fields = parse_actor_rpc_fields(
                        bunch_payload_bits(b), value_max=PS_RPC_HANDLE_VALUE_MAX)
                except Exception:
                    ps_fields = []
                if ps_fields:
                    print("[match]       *** client PS RPC handles="
                          f"{[int(h) for h, _p in ps_fields]} on ch{ps_channel} ***")
                if any(int(h) == 71 for h, _p in ps_fields):
                    # Capture answers h71 with PS src 888 LockVehicleMode.
                    self.maybe_send_lock_vehicle_reply(s, addr, conn)
                    self.note_strict_playerstate_h71(conn)
                if any(int(h) == PS_RPC_PLAYER_IN_GAME_NOTIFY and not param
                       for h, param in ps_fields):
                    self.note_client_player_in_game(conn)
                    self.maybe_release_deploy_transition(s, addr, conn)
                    if self.strict_player_in_game_order_enabled():
                        conn._strict_h65_fallback_at = 0
                        return self.begin_strict_player_in_game_sequence(
                            s, addr, conn, synthetic=False)
                    return self.maybe_reply_player_in_game_notify(s, addr, conn)
            if b["chIndex"] == 2 and (nb or 0) >= 16:
                try:
                    bits = bunch_payload_bits(b)
                    # The pawn belongs to a streamed level.  A timer is not enough:
                    # UE queues/drops actor opens until the client has acknowledged
                    # the matching ServerUpdateLevelVisibility RPC.  Observe that RPC
                    # explicitly and use it as the spawn gate.
                    try:
                        level_fields = parse_actor_rpc_fields(bits)
                    except Exception:
                        level_fields = []
                    # Keep a compact record of client-originated controller RPCs that
                    # are not part of the possession probes.  In particular, the native
                    # deploy path may send ServerSetSpectatorWaiting/other spawn requests
                    # before the server-side transition callbacks are emitted.
                    if level_fields:
                        known_probe = {39, 78, 79, 9, 10}
                        extra_handles = [int(h) for h, _p in level_fields
                                         if int(h) not in known_probe]
                        if extra_handles:
                            print(f"[match]       *** client ch2 RPC handles={extra_handles} ***")
                        # Handle 279 is AWW3GamePlayerController::Server_OnClientPreloadWeaponsFinished.
                        # It is the authoritative client-side readiness signal for
                        # the final spectator -> playable transition.
                        if PC_RPC_CLIENT_RECEIVED_SERVER_START_DATE in extra_handles:
                            self.note_profile_prologue_ack(conn)
                        if 279 in extra_handles:
                            # Capture order: the client's first h279 (src~354) is
                            # immediately followed by PS src 372 bIsConnectedToMaster.
                            self.maybe_send_ps_master_link(s, addr, conn)
                            self.maybe_send_post_preload_deploy(s, addr, conn)
                        if PC_RPC_SPECTATOR_ATTACH_CAPTURE_POINT in extra_handles:
                            self.maybe_answer_spectate_attach(s, addr, conn)
                        if PC_RPC_REQUEST_RESPAWN_AT_CAPTURE_POINT in extra_handles:
                            if self.note_client_respawn_requested(conn):
                                print("[match]       *** client pressed DEPLOY "
                                      "(h287 Server_RequestRespawnAtCapturePoint) ***")
                            self.maybe_release_deploy_transition(s, addr, conn)
                            self.maybe_answer_deploy_request(s, addr, conn)
                        if PC_RPC_ON_MAP_OPENED in extra_handles:
                            if self.note_client_map_opened(conn):
                                print("[match]       *** client reports "
                                      "Server_OnMapOpened (h281): the deploy screen "
                                      "is up ***")
                            self.maybe_release_deploy_transition(s, addr, conn)
                            # h281 is the reliable "deploy screen is up" signal.
                            # h310 is not: it arrived in the turn-11 run but not in
                            # turn 12, so gating the eligibility write on the
                            # spectator state alone can leave it unsent forever.
                            self.maybe_mark_deploy_eligible(s, addr, conn)
                        if PC_RPC_START_SPECTATOR in extra_handles:
                            if self.note_client_start_spectator(conn):
                                print("[match]       *** client started the deploy "
                                      f"spectator (h{PC_RPC_START_SPECTATOR} "
                                      "Server_StartSpectator, capture src~1626) ***")
                            self.maybe_release_deploy_transition(s, addr, conn)
                            self.maybe_send_deploy_screen_chain(s, addr, conn)
                            self.maybe_repeat_deploy_transition(s, addr, conn)
                        # The client floods h73 ServerSetSpectatorLocation while
                        # spectating, so this is a bounded retry driven by the
                        # client's own traffic: if the release was held at the
                        # instant h310 arrived (settle delay or liveness), it
                        # still fires without adding a timer.
                        if getattr(conn, "_client_start_spectator", False):
                            if (self.deploy_after_spectator_enabled()
                                    and not getattr(conn, "_deploy_release_done", False)):
                                self.maybe_release_deploy_transition(s, addr, conn)
                            self.maybe_send_deploy_screen_chain(s, addr, conn)
                            self.maybe_mark_deploy_eligible(s, addr, conn)
                            if not getattr(conn, "_deploy_repeat_done", False):
                                self.maybe_repeat_deploy_transition(s, addr, conn)
                            # Once the deploy repeat has landed the pawn is possessed
                            # but unplaced; feed it the capture's own ch3 movement.
                            self.maybe_replay_pawn_movement(s, addr, conn)
                        # The fixed ClientSetSpectatorWaiting(false) path makes
                        # the native client emit this authoritative completion
                        # callback.  Finish pawn/HUD/camera state only after it.
                        if 299 in extra_handles:
                            self.maybe_accept_character_respawn(s, addr, conn)
                        if 282 in extra_handles:
                            self.maybe_finalize_post_spectator(s, addr, conn)
                    for _h, _param in level_fields:
                        if _h == 79:  # PlayerController::ServerUpdateLevelVisibility
                            names = extract_map_path_strings(_param)
                            print("[match]       *** M4: ServerUpdateLevelVisibility ***"
                                  + (" names=" + ",".join(names[:6]) if names else ""))
                            if payload_has_spawn_level_visibility(_param):
                                conn._spawn_level_visible = True
                                print("[match]           spawn level visible; releasing pawn gate")
                    if (not getattr(conn, "_client_loaded_world", False)
                            and (nb or 0) >= 200
                            and payload_has_loaded_world_marker(bits)):
                        conn._client_loaded_world = True
                        paths = extract_map_path_strings(bits)
                        print("[match]       *** M4: ServerNotifyLoadedWorld (map paths) ***")
                        if paths:
                            print(f"[match]           paths({len(paths)}): "
                                  + ", ".join(os.path.basename(p) for p in paths[:12]))
                        self.maybe_send_ps_rebind(s, addr, conn)
                    if (not getattr(conn, "_gameplay_dom_loaded", False)
                            and payload_has_gameplay_dom(bits)):
                        conn._gameplay_dom_loaded = True
                        print("[match]       *** M4: client reports Gameplay_DOM loaded ***")
                        # The client reports this marker before its pawn/camera
                        # and attachment managers are actually ready.  Do not
                        # let that early report cancel the settle barrier; hold
                        # possession until the configured post-streaming window
                        # has elapsed.
                        try:
                            settle_ms = max(0, int(os.environ.get(
                                "WW3_STREAMING_PAUSE_MS", "0")))
                        except ValueError:
                            settle_ms = 0
                        if settle_ms:
                            conn._streaming_settle_until = max(
                                getattr(conn, "_streaming_settle_until", 0) or 0,
                                time.time() + settle_ms / 1000.0)
                            print(f"[match]       *** M4: extending streaming settle "
                                  f"{settle_ms}ms after Gameplay_DOM report ***")
                    if is_ack_possession_null(bits):
                        self._note_restart_reaction(conn, "AckPossession(null)")
                        if not getattr(conn, "_ack_possess_null", False):
                            conn._ack_possess_null = True
                            print("[match]       *** M4: ServerAcknowledgePossession(null) ***")
                            self.maybe_send_client_restart(s, addr, conn, reason="ack-null")
                    if (not getattr(conn, "_ack_possess_pawn", False)
                            and is_ack_possession_pawn(bits)):
                        conn._ack_possess_pawn = True
                        print(f"[match]       *** M4: ServerAcknowledgePossession"
                              f"(Pawn {PAWN_NETGUID}) — possession OK ***")
                        if (os.environ.get("WW3_POST_ACK_PC_STATE", "1") == "1"
                                and not getattr(conn, "_post_ack_pc_state_done", False)):
                            conn._post_ack_pc_state_done = True
                            self.maybe_send_post_pawn_pc_state(
                                s, addr, conn, force=True, audit_tag="post-ack PC src=8")
                        self.maybe_send_online_session_started(s, addr, conn)
                        # These captured transition RPCs were previously only
                        # emitted when a deferred attachment queue drained.  In
                        # the normal (non-deferred) path that meant the pawn was
                        # possessed but the client never received its final
                        # view-target/camera and gameplay-transition state.
                        self.maybe_send_late_transition(s, addr, conn)
                        self.maybe_send_camera_rebind(s, addr, conn)
                        conn._camera_retry_at = time.time() + 3.0
                        self.maybe_send_post_spawn_finalize_rpcs(s, addr, conn)
                        self.maybe_send_player_respawned(s, addr, conn)
                        self.maybe_send_player_respawned_with_movement_type(s, addr, conn)
                        self.maybe_clear_spectator_waiting(s, addr, conn)
                        self.maybe_send_client_goto_state(s, addr, conn)
                        self.maybe_send_client_stream_status(s, addr, conn)
                        self.maybe_send_game_started(s, addr, conn)
                        self.maybe_send_domination_match_started(s, addr, conn)
                        self.maybe_send_infantry_widget(s, addr, conn)
                        conn._late_transition_settle_retry_at = time.time() + max(
                            1.0, float(os.environ.get("WW3_LATE_TRANSITION_RETRY_S", "12")))
                        deferred = getattr(conn, "_deferred_attachment_queue", None)
                        if (deferred and not getattr(conn, "_deferred_attachments_released", False)):
                            try:
                                hold_ms = max(0, int(os.environ.get(
                                    "WW3_DEFER_ATTACHMENTS_MS", "5000")))
                            except ValueError:
                                hold_ms = 5000
                            if hold_ms:
                                conn._deferred_attachment_release_at = time.time() + hold_ms / 1000.0
                                print(f"[match]       *** M4: holding deferred attachments "
                                      f"{hold_ms}ms after AckPossession(Pawn) ***")
                            else:
                                self._release_deferred_attachments(conn)
                    calib_guid = restart_calibration_pawn_guid()
                    if (calib_guid is not None
                            and not getattr(conn, "_ack_possess_calib", False)
                            and is_ack_possession_pawn(bits, pawn=calib_guid)):
                        conn._ack_possess_calib = True
                        self._note_restart_reaction(
                            conn, f"AckPossession(Pawn {calib_guid}) [calibration GUID cast succeeded!]")
                    if is_check_possession(bits):
                        self._note_restart_reaction(conn, "ServerCheckClientPossession(Reliable)")
                        print("[match]       *** M4: ServerCheckClientPossession ***")
                        self.maybe_send_client_restart(s, addr, conn, reason="check-possess")
                except Exception as e:
                    print(f"[match]       ! actor RPC probe failed: {e}")
            return False
        nmt = b.get("nmt")
        if nmt is None:
            return False                             # partial continuation / no NMT type
        if nmt == cc.NMT_Hello:
            h = cc.parse_hello(b["reader"])
            self.conns_challenge(s, addr, conn, h)
            return True
        if nmt == cc.NMT_Login:
            return self.on_login(s, addr, conn, b)
        if nmt == cc.NMT_Netspeed:
            r = b["reader"]; r.read_bits(8)
            print(f"[match]   <- NMT_Netspeed {r.read_int32()}")
            return False
        if nmt == cc.NMT_Join:
            # M3 trigger: the client finished loading the map and asks to spawn. A real UE4
            # server would SpawnPlayActor -> open the PlayerController actor channel and start
            # replicating (GameState, PlayerController, streaming levels, Pawn).
            print(f"[match]   <- NMT_Join  *** M4 START: client wants to spawn (PC + world) ***")
            conn.state = "JOINING"
            if not conn.spawned:
                try:
                    self.send_player_controller(s, addr, conn)
                    return True
                except Exception as e:
                    import traceback; traceback.print_exc()
                    print(f"[match]       ! spawn failed: {e}")
            return False
        print(f"[match]   <- NMT {cc.NMT_NAMES.get(nmt, nmt)} (chSeq={b.get('chSeq')}) [not handled]")
        return False

    def conns_challenge(self, s, addr, conn, hello):
        conn.state = "CONNECTED"
        conn.challenge = "%08X" % ((int(self.server_time() * 1000) ^ 0x5A5A5A5A) & 0xFFFFFFFF)
        print(f"[match]   <- NMT_Hello (netver=0x{hello['remoteNetworkVersion']:08x}) "
              f"-> NMT_Challenge '{conn.challenge}'")
        self.send_control_msg(s, addr, conn, cc.build_challenge_msg(conn.challenge))

    def on_login(self, s, addr, conn, bunch):
        token = cc.find_lobby_token(bunch)
        if not token:
            print("[match]   <- NMT_Login but NO lobbyToken found"); return False
        claims = validate_token(token)
        if not claims:
            # our secret didn't verify it (e.g. the studio-signed capture) -- decode for visibility
            try: _, claims = decode_token(token)
            except Exception: claims = None
            print(f"[match]   <- NMT_Login: token did NOT validate against our secret "
                  f"(map={claims['server']['map'] if claims else '?'}) -- would REJECT a live client")
            return False
        # Capture live identity from NMT_Login (URL Name= + Steam UniqueId) for PS patching.
        try:
            lg = cc.parse_login(bunch["reader"])
            conn.player_name = name_from_login_url(lg["url"])
            r = lg["_reader"]
            left = r.bits_left()
            rest = [r.read_bit() for _ in range(left)]
            conn.steam_id = steam_from_login_bits(rest)
            print(f"[match]       login identity name={conn.player_name!r} steam={conn.steam_id!r}")
        except Exception as e:
            print(f"[match]       ! login identity parse failed: {e}")
        conn.claims = claims; conn.state = "LOGGED_IN"
        srv = claims["server"]; mp = srv["map"]
        # We only know the REAL package path for Gobi (read off the wire). For a live test,
        # WW3_FORCE_MAP=WW3_Gobi_New_P forces the known-good path regardless of what was picked.
        forced = os.environ.get("WW3_FORCE_MAP")
        if forced and forced != mp:
            print(f"[match]       (WW3_FORCE_MAP: {mp} -> {forced}, known-good package path)")
            mp = forced
        print(f"[match]   <- NMT_Login VALID: player={claims['playerId']} team={claims['team']['id']} "
              f"map={mp} gameMode={srv['gameMode']}  -> NMT_Welcome")
        level = MAP_PACKAGE_PATH.get(mp, f"/Game/Maps/{mp}")
        game, redirect = GAMEMODE_CLASS.get(srv["gameMode"],
            ("/Game/Blueprints/GameModes/BP_DominationNewbie_GameMode_01_01.BP_DominationNewbie_GameMode_01_01_C", "DOM_N"))
        self.send_control_msg(s, addr, conn, cc.build_welcome_msg(level, game, redirect))
        print(f"[match]       sent NMT_Welcome(level={level}, game={game}, redirect={redirect})")
        print(f"[match]       *** M2 LOGIN COMPLETE -> client loads map, then sends NMT_Netspeed + NMT_Join ***")
        print(f"[match]       M4: on NMT_Join, capture-faithful PC spawn + world drip-feed")
        return True

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7871
    try:
        MatchServer(port).run()
    except KeyboardInterrupt:
        print("\n[match] stopped.")
