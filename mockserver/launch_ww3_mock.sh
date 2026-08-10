#!/usr/bin/env bash
# WW3 private-server mock launcher
# Brings up the full mock backend + redirects + (optionally) launches WW3, with clean teardown.
#
#   sudo ./launch_ww3_mock.sh up      # start mocks + redirects
#   sudo ./launch_ww3_mock.sh game    # start mocks + redirects + launch WW3
#   sudo ./launch_ww3_mock.sh down    # stop everything, restore system
#
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
LOGDIR=/tmp/ww3mock
mkdir -p "$LOGDIR"

# --- config ---
HUB_IP="213.183.62.234"; HUB_PORT=8705
STEAM="/home/georgek/.local/share/Steam"
GAMEDIR="/media/georgek/Games/SteamLibrary/steamapps/common/World War 3"
COMPAT="/media/georgek/Games/SteamLibrary/steamapps/compatdata/674020"
PROTON="$STEAM/steamapps/common/Proton - Experimental/proton"
REAL_USER="${SUDO_USER:-georgek}"

HOSTS_MARK_A="# === WW3 mock redirects (auto) ==="
HOSTS_MARK_B="# === end WW3 mock redirects ==="
HOSTS_ENTRIES=(
  meta.prod.ww3.fxtools.gl
  meta.dev.ww3.fxtools.gl
  api.public.dev.ww3.fxtools.gl
  xmpp.prod.ww3.fxtools.gl
  xmpp.dev.ww3.fxtools.gl
  ww3.anticheat.my.games
  id-dev.fx.gl
  api.ipify.org
)

hosts_add() {
  hosts_del
  { echo "$HOSTS_MARK_A"
    for h in "${HOSTS_ENTRIES[@]}"; do echo "127.0.0.1 $h"; done
    echo "$HOSTS_MARK_B"; } >> /etc/hosts
}
hosts_del() { sed -i "/$HOSTS_MARK_A/,/$HOSTS_MARK_B/d" /etc/hosts; }

dnat_add() {
  # Redirect the raw-IP hub connection to our local hub mock.
  iptables -t nat -C OUTPUT -p tcp -d "$HUB_IP" --dport "$HUB_PORT" -j DNAT --to-destination 127.0.0.1:"$HUB_PORT" 2>/dev/null \
    || iptables -t nat -A OUTPUT -p tcp -d "$HUB_IP" --dport "$HUB_PORT" -j DNAT --to-destination 127.0.0.1:"$HUB_PORT"
  # needed so DNAT to loopback works for locally-generated packets
  sysctl -q -w net.ipv4.conf.all.route_localnet=1
}
dnat_del() {
  iptables -t nat -D OUTPUT -p tcp -d "$HUB_IP" --dport "$HUB_PORT" -j DNAT --to-destination 127.0.0.1:"$HUB_PORT" 2>/dev/null || true
}

start_mocks() {
  echo "[*] starting mock servers..."
  python3 "$HERE/xmpp_server.py"            > "$LOGDIR/xmpp.log" 2>&1 &  echo $! > "$LOGDIR/xmpp.pid"
  python3 "$HERE/hub_server.py" "$HUB_PORT"  > "$LOGDIR/hub.log"  2>&1 &  echo $! > "$LOGDIR/hub.pid"
  python3 "$HERE/rest_server.py" 443 1       > "$LOGDIR/https.log" 2>&1 & echo $! > "$LOGDIR/https.pid"
  python3 "$HERE/rest_server.py" 80  0       > "$LOGDIR/http.log"  2>&1 & echo $! > "$LOGDIR/http.pid"
  sleep 2
  echo "[*] listening ports:"; ss -tlnp 2>/dev/null | grep -E ':(80|443|5222|8705)\s' || echo "  (none up — check logs in $LOGDIR)"
}
stop_mocks() {
  for s in xmpp hub https http; do
    [ -f "$LOGDIR/$s.pid" ] && kill -9 "$(cat "$LOGDIR/$s.pid")" 2>/dev/null
  done
  pkill -9 -f "hub_server.py"  2>/dev/null
  pkill -9 -f "rest_server.py" 2>/dev/null
  pkill -9 -f "xmpp_server.py" 2>/dev/null
  fuser -k 80/tcp 443/tcp 5222/tcp 8705/tcp 2>/dev/null
}

launch_game() {
  echo "[*] launching WW3 (as $REAL_USER)..."
  sudo -u "$REAL_USER" env \
    STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM" \
    STEAM_COMPAT_DATA_PATH="$COMPAT" \
    bash -c "cd '$GAMEDIR' && '$PROTON' run WW3-Win64-Shipping.exe -log -Continent=SECRETMS" \
    > "$LOGDIR/game.log" 2>&1 &
  echo $! > "$LOGDIR/game.pid"
  echo "[*] game launching; watch $LOGDIR/game.log and the WW3.log in the prefix"
}

case "${1:-}" in
  up)   hosts_add; dnat_add; start_mocks; echo "[✓] mocks + redirects up. Run the game, then: sudo $0 down" ;;
  game) hosts_add; dnat_add; start_mocks; launch_game ;;
  down) echo "[*] tearing down..."; pkill -9 -f "WW3-Win64-Shipping" 2>/dev/null; pkill -9 -f "Continent=SECRETMS" 2>/dev/null
        stop_mocks; dnat_del; hosts_del
        echo "[✓] stopped mocks, removed DNAT, restored /etc/hosts" ;;
  *) echo "usage: sudo $0 {up|game|down}"; exit 1 ;;
esac
