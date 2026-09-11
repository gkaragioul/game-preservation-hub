import struct

path = r'F:\Dev_Work\GameDev\WW3\captures\31July26\TDM_MoscowSenate.pcapng'
with open(path, 'rb') as f:
    data = f.read()

off = 0
n = 0
while off + 12 <= len(data) and n < 6:
    block_type, block_len = struct.unpack('<II', data[off:off+8])
    print(f'block_type=0x{block_type:08X} len={block_len}')
    if block_type == 0x00000001:
        linktype, reserved, snaplen = struct.unpack('<HHI', data[off+8:off+16])
        print('  IDB linktype:', linktype)
    if block_type == 0x00000006 and n < 6:
        iface_id, ts_high, ts_low, caplen, origlen = struct.unpack('<IIIII', data[off+8:off+28])
        pkt = data[off+28:off+28+caplen]
        print('  EPB caplen', caplen, 'first 20 bytes:', pkt[:20].hex())
    off += block_len
    n += 1
