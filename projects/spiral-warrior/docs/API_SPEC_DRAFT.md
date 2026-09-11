# API Spec Draft

This file records local backend endpoints for the Chinese-primary, dual-edition offline prototype. Schemas are provisional until verified against runtime logcat/network captures.

## Local backend base

Default development URL:

```text
http://127.0.0.1:18080
```

For Android emulators, `127.0.0.1` inside the emulator points at the emulator itself. Use `10.0.2.2` for Android Studio Emulator host access or configure DNS/proxy/hosts to the host LAN IP.

## Implemented local routes

### `GET /health`

Purpose: backend health check.

Response:

```json
{"ok": true, "service": "spiralwarrior-local-server"}
```

### Manifest routes

Supported paths:

```text
/remote-assets/project.manifest
/remote-assets/version.manifest
/oversea/remote-assets/project.manifest
/oversea/remote-assets/version.manifest
/x3-hd/remote-assets/project.manifest
/x3-hd/remote-assets/version.manifest
/x3-hd-test/remote-assets/project.manifest
/x3-hd-test/remote-assets/version.manifest
```

Purpose: satisfy Cocos hot-update/resource manifest checks.

### Login/server routes

Supported provisional paths:

```text
/DHSDK/Action_UserLogin.aspx
/Wbsrv/Check_Login_DH.aspx
/login/1/
/auth/es
/server/list
```

Purpose: return a local Chinese offline account/session/server list.

### Chinese area/server discovery

Captured runtime request:

```text
GET http://lxys-area.17m3.com/area/listV2?plt=1&ver=1.0.348
```

Current local shim:

```text
tools/serve_lbres_proxy.py
```

Status: endpoint is reached through local DNS + port-80 HTTP service, but the response schema is still [uncertain] and has not yet advanced the client to lobby/login success.

Observed failure-report endpoint after bad/unknown area schema:

```text
GET http://upsapi.17m3.com/GetAllEntryFaild?appid=1280858451&data=-1,-1,0
```

### Profile routes

Supported provisional paths:

```text
/profile
/player/profile
/user/profile
/game/profile
```

Purpose: return local default profile/save data.

## Known original endpoint candidates

See `research/endpoint_inventory.md` for generated source references. Priority hostnames include:

```text
sdk-login-cocooversea.17m3.com
sdk-package-update-config.17m3.com
ups-config.17m3.com
sdk-heartbeat.17m3.com
cdnsgp-x3jl-release.17m3.com
cdn-spinarena.17m3.com
lxys-area.17m3.com
lxys-audit-area.17m3.com
lxys-test-area.17m3.com
lxys1-client.17m3.com
spinarena.firebaseio.com
```

## Unknowns

- Exact success response schema expected by the client for SDK login: [uncertain].
- Whether request bodies are encrypted/signed: [uncertain].
- Whether gameplay battle simulation is client-side or server-authoritative: [uncertain].
