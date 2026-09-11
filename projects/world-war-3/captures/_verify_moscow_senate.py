import struct, os
from collections import Counter

def parse_pcapng(path):
    with open(path, 'rb') as f:
        data = f.read()
    off = 0
    packets = []
    ts_resol = 1_000_000  # default microsecond
    while off + 12 <= len(data):
        block_type, block_len = struct.unpack('<II', data[off:off+8])
        if block_len < 12 or off + block_len > len(data): break
        block = data[off:off+block_len]
        if block_type == 0x0A0D0D0A:
            pass
        elif block_type == 0x00000001:  # IDB - look for if_tsresol option (code 9)
            opts = block[8+8:-4]
            i = 0
            while i + 4 <= len(opts):
                ocode, olen = struct.unpack('<HH', opts[i:i+4])
                if ocode == 0 and olen == 0: break
                oval = opts[i+4:i+4+olen]
                if ocode == 9 and oval:
                    val = oval[0]
                    ts_resol = (10**(val & 0x7f)) if not (val & 0x80) else (2**(val & 0x7f))
                pad = (4 - olen % 4) % 4
                i += 4 + olen + pad
        elif block_type == 0x00000006:  # EPB
            if len(block) >= 32:
                iface_id, ts_high, ts_low, caplen = struct.unpack('<IIII', block[8:24])
                ts = ((ts_high << 32) | ts_low) / ts_resol
                pkt = block[28:28+caplen]
                packets.append((ts, pkt))
        off += block_len
    return packets

def classify(pkt):
    # Ethernet(14) + IPv4
    if len(pkt) < 34: return None
    ethertype = struct.unpack('>H', pkt[12:14])[0]
    if ethertype != 0x0800: return None
    ihl = (pkt[14] & 0x0F) * 4
    proto = pkt[23]
    ip_off = 14
    l4_off = ip_off + ihl
    if proto == 17 and len(pkt) >= l4_off + 4:  # UDP
        sport, dport = struct.unpack('>HH', pkt[l4_off:l4_off+4])
        return ('UDP', sport, dport)
    if proto == 6 and len(pkt) >= l4_off + 4:  # TCP
        sport, dport = struct.unpack('>HH', pkt[l4_off:l4_off+4])
        return ('TCP', sport, dport)
    return None

path = r'F:\Dev_Work\GameDev\WW3\captures\31July26\TDM_MoscowSenate.pcapng'
pkts = parse_pcapng(path)
print('total packets:', len(pkts))
if pkts:
    t0, t1 = pkts[0][0], pkts[-1][0]
    print(f'duration: {t1-t0:.1f} sec ({(t1-t0)/60:.2f} min)')
proto_counter = Counter()
udp_ports = Counter()
tcp_ports = Counter()
for ts, pkt in pkts:
    c = classify(pkt)
    if not c: continue
    proto_counter[c[0]] += 1
    if c[0] == 'UDP':
        udp_ports[c[1]] += 1; udp_ports[c[2]] += 1
    else:
        tcp_ports[c[1]] += 1; tcp_ports[c[2]] += 1
print('protocol counts:', dict(proto_counter))
print('top UDP ports:', udp_ports.most_common(10))
print('top TCP ports:', tcp_ports.most_common(10))
# known WW3 match server UDP port range clue: 213.183.62.18:786x from docs
game_udp = sum(c for p,c in udp_ports.items() if 7860 <= p <= 7900 or p == 27015)
print('packets on likely game-server UDP ports (786x range):', game_udp)
