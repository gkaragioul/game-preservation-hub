#!/usr/bin/env python3
r"""
ww3_redirect.py  --  Windows WinDivert (pydivert) DNAT fallback.

This is the Windows equivalent of the Linux `iptables -t nat OUTPUT ... DNAT`
rule the old launcher used. It is a FALLBACK: only needed if the WW3 client
resolves backend hostnames past the Windows hosts file (the c-ares bypass we
saw on Linux), or connects to a raw backend IP directly (e.g. the Hub) that we
cannot catch by hostname.

It transparently redirects outbound TCP going to any (IP, port) in TARGETS to a
local mock listening on 127.0.0.1:<same-port>, and rewrites the loopback reply
back so the client's socket accepts it.

Run from an ELEVATED shell (WinDivert loads a kernel driver):
    python ww3_redirect.py 213.183.62.234:8705 89.167.40.140:443 ...
If no targets are given on the command line, DEFAULT_TARGETS below are used.

Ctrl+C to stop; the driver unloads and networking returns to normal.
"""
import sys
import socket
import logging

try:
    import pydivert
except ImportError:
    sys.exit("pydivert not installed. Run: pip install pydivert")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [REDIR] %(message)s")
log = logging.getLogger("redir")

# Populate these from a baseline capture (the real resolved IPs of meta.prod,
# api.public, xmpp.prod, and the Hub). Left empty by default so nothing is
# redirected until you know the current IPs.
DEFAULT_TARGETS = [
    # ("213.183.62.234", 8705),   # Hub (raw IP) -- usually unnecessary; master mock returns 127.0.0.1
    # ("89.167.40.140", 443),     # meta.prod A-record (verify current value first)
]


def local_ip() -> str:
    """Best-effort primary LAN IP of this machine (the client's source addr)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def parse_targets(argv):
    targets = []
    for a in argv:
        host, _, port = a.partition(":")
        if not port:
            sys.exit(f"bad target '{a}', expected IP:PORT")
        targets.append((host, int(port)))
    return targets


def main():
    targets = parse_targets(sys.argv[1:]) or DEFAULT_TARGETS
    if not targets:
        sys.exit("No targets. Pass IP:PORT args, e.g. python ww3_redirect.py 213.183.62.234:8705")

    my_ip = local_ip()
    ports = sorted({p for _, p in targets})
    ips = sorted({ip for ip, _ in targets})
    log.info(f"local IP = {my_ip}; redirecting {targets} -> 127.0.0.1")

    # One filter that catches both directions:
    #   outbound  -> any target IP:port
    #   inbound   <- 127.0.0.1:port  (the loopback reply from our mock)
    ip_clause = " or ".join(f"ip.DstAddr == {ip}" for ip in ips)
    port_clause = " or ".join(f"tcp.DstPort == {p}" for p in ports)
    src_port_clause = " or ".join(f"tcp.SrcPort == {p}" for p in ports)
    flt = (f"tcp and (((({ip_clause}) and ({port_clause}))) or "
           f"(ip.SrcAddr == 127.0.0.1 and ({src_port_clause})))")
    log.info(f"WinDivert filter: {flt}")

    target_set = set(targets)
    with pydivert.WinDivert(flt) as w:
        log.info("driver up. Ctrl+C to stop.")
        for packet in w:
            if packet.dst_addr != "127.0.0.1" and (packet.dst_addr, packet.dst_port) in target_set:
                # outbound client -> real backend : send to our local mock
                packet.dst_addr = "127.0.0.1"
                packet.src_addr = "127.0.0.1"
            elif packet.src_addr == "127.0.0.1" and packet.dst_addr == "127.0.0.1" \
                    and packet.src_port in ports:
                # loopback reply mock -> client : restore so the client accepts it
                # match it back to whichever real IP used this dst port
                real_ip = next((ip for ip, p in targets if p == packet.src_port), ips[0])
                packet.src_addr = real_ip
                packet.dst_addr = my_ip
            w.send(packet)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("stopped.")
