import struct
from pathlib import Path
from collections import Counter

def analyze(path):
    data = Path(path).read_bytes()
    print('===', Path(path).name, f'{len(data)/1e6:.2f} MB ===')
    off = 0
    linktypes = {}
    ts_resol = {}
    pkts = []
    iface_count = 0
    while off + 12 <= len(data):
        bt, bl = struct.unpack('<II', data[off:off+8])
        if bl < 12 or off + bl > len(data):
            break
        block = data[off:off+bl]
        if bt == 1:
            lt = struct.unpack('<H', block[8:10])[0]
            iid = iface_count
            iface_count += 1
            linktypes[iid] = lt
            resol = 1_000_000
            opts = block[16:-4]
            i = 0
            while i + 4 <= len(opts):
                oc, ol = struct.unpack('<HH', opts[i:i+4])
                if oc == 0 and ol == 0:
                    break
                if oc == 9 and ol >= 1:
                    v = opts[i+4]
                    resol = (2 ** (v & 0x7f)) if (v & 0x80) else (10 ** (v & 0x7f))
                i += 4 + ol + ((4 - ol % 4) % 4)
            ts_resol[iid] = resol
        elif bt == 6 and len(block) >= 32:
            iid, th, tl, caplen = struct.unpack('<IIII', block[8:24])
            resol = ts_resol.get(iid, 1_000_000)
            ts = ((th << 32) | tl) / float(resol)
            pkt = block[28:28+caplen]
            pkts.append((ts, pkt, linktypes.get(iid, 1)))
        off += bl

    print('  interfaces/linktypes:', linktypes)
    print('  packets:', len(pkts))
    if not pkts:
        return
    times = [t for t, _, _ in pkts]
    print(f'  duration: {(max(times)-min(times))/60:.2f} min')
    # show first 3 packet headers
    for i, (ts, pkt, lt) in enumerate(pkts[:3]):
        print(f'  pkt[{i}] lt={lt} len={len(pkt)} head={pkt[:32].hex()}')

    # try multiple decode strategies
    def try_udp(pkt, lt):
        # ethernet
        cands = []
        if len(pkt) >= 34 and struct.unpack('>H', pkt[12:14])[0] == 0x0800:
            cands.append(14)
        if len(pkt) >= 20 and (pkt[0] >> 4) == 4:
            cands.append(0)
        if len(pkt) >= 16 and struct.unpack('>H', pkt[14:16])[0] == 0x0800:
            cands.append(16)
        # NULL/loopback linktype 0: 4-byte family then IP
        if lt == 0 and len(pkt) >= 24:
            cands.append(4)
        for off in cands:
            if len(pkt) < off + 20:
                continue
            if (pkt[off] >> 4) != 4:
                continue
            ihl = (pkt[off] & 0x0F) * 4
            proto = pkt[off + 9]
            l4 = off + ihl
            if proto == 17 and len(pkt) >= l4 + 4:
                sp, dp = struct.unpack('>HH', pkt[l4:l4+4])
                return ('UDP', sp, dp, off)
            if proto == 6 and len(pkt) >= l4 + 4:
                sp, dp = struct.unpack('>HH', pkt[l4:l4+4])
                return ('TCP', sp, dp, off)
        return None

    proto = Counter()
    ports = Counter()
    for ts, pkt, lt in pkts:
        r = try_udp(pkt, lt)
        if r:
            proto[r[0]] += 1
            ports[r[1]] += 1
            ports[r[2]] += 1
        else:
            proto['OTHER'] += 1
    print('  decoded:', dict(proto))
    print('  top ports:', ports.most_common(8))

for p in [
    r'F:\Dev_Work\GameDev\WW3\captures\31July26\TDM_MoscowSenate.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\31July26\moskow TDM.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\31July26\TDM_BerlinBackyards.pcapng',
    r'F:\Dev_Work\GameDev\WW3\captures\31July26\Berlin.pcapng',
]:
    analyze(p)
    print()
