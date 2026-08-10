import struct, glob, os
from datetime import datetime, timezone

def scan_pcap(path):
    """Return (first_ts, last_ts, packet_count, udp_count) for pcap/pcapng."""
    with open(path, 'rb') as f:
        magic = f.read(4)
        f.seek(0)
        data = f.read()
    first_ts = last_ts = None
    count = 0
    udp = 0
    if magic in (b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4'):  # classic pcap
        le = magic == b'\xd4\xc3\xb2\xa1'
        fmt_hdr = '<IIII' if le else '>IIII'
        off = 24
        while off + 16 <= len(data):
            ts_sec, ts_usec, caplen, origlen = struct.unpack(fmt_hdr, data[off:off+16])
            off += 16
            if first_ts is None: first_ts = ts_sec
            last_ts = ts_sec
            count += 1
            pkt = data[off:off+caplen]
            if len(pkt) > 34 and pkt[23] == 17: udp += 1  # rough IPv4 UDP check assuming Ethernet
            off += caplen
    elif magic == b'\x0a\x0d\x0d\x0a':  # pcapng
        off = 0
        ts_resol = 1_000_000
        iface_ts_resol = {}
        cur_if = 0
        while off + 12 <= len(data):
            block_type, block_len = struct.unpack('<II', data[off:off+8])
            if block_len < 12 or off + block_len > len(data): break
            block = data[off:off+block_len]
            if block_type == 0x00000001:  # IDB
                pass
            elif block_type == 0x00000006:  # EPB
                if len(block) >= 32:
                    iface_id, ts_high, ts_low = struct.unpack('<III', block[8:20])
                    ts = (ts_high << 32) | ts_low
                    sec = ts / 1_000_000.0
                    if first_ts is None: first_ts = sec
                    last_ts = sec
                    count += 1
            off += block_len
    return first_ts, last_ts, count, udp

root = r'F:\Dev_Work\GameDev\WW3\captures'
files = sorted(glob.glob(os.path.join(root, '**', '*.pcap*'), recursive=True))
print(f'{"file":65s} {"dur(s)":>8s} {"dur(min)":>9s} {"pkts":>8s}')
for f in files:
    try:
        first, last, cnt, udp = scan_pcap(f)
        dur = (last - first) if (first and last) else 0
        rel = os.path.relpath(f, root)
        print(f'{rel[:65]:65s} {dur:8.1f} {dur/60:9.2f} {cnt:8d}')
    except Exception as e:
        print(f'{os.path.relpath(f, root)[:65]:65s}  ERROR {e}')
