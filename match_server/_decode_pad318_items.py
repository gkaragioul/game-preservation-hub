"""Read-only dump of live Pad_318 TArray work-item objects."""
from __future__ import annotations
import ctypes, ctypes.wintypes as wt, struct, subprocess
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WAMS = [0x21B3B1260A0, 0x21A4B2A3620]
k = ctypes.WinDLL("kernel32", use_last_error=True)
pid = int(subprocess.check_output(["powershell","-NoProfile","-Command",
    "(Get-Process WW3-Win64-Shipping | Select -First 1).Id"], text=True).strip())
h = k.OpenProcess(0x0410, False, pid)
def rpm(a,n):
    b=(ctypes.c_char*n)(); got=ctypes.c_size_t()
    if not k.ReadProcessMemory(h, ctypes.c_uint64(a), b, n, ctypes.byref(got)): return None
    return bytes(b[:got.value])
def strings(blob):
    out=[]
    for enc in ("ascii","utf-16le"):
        step=1 if enc=="ascii" else 2
        try: s=blob.decode(enc, errors="ignore")
        except Exception: continue
        cur=""
        for ch in s:
            if ch.isprintable() and ch not in "\r\n\t": cur+=ch
            else:
                if len(cur)>=5: out.append((enc,cur))
                cur=""
        if len(cur)>=5: out.append((enc,cur))
    return out[:30]
print(f"pid={pid}")
for wam in WAMS:
    raw=rpm(wam,0x4c0)
    print(f"\nWAM 0x{wam:x} pad={raw[0x318:0x350].hex()}")
    for slot in range(3):
        arr=struct.unpack_from("<Q",raw,0x320+slot*16)[0]
        hdr=rpm(arr,16)
        if not hdr: continue
        data,num,mx=struct.unpack_from("<Qii",hdr,0)
        print(f" slot{slot}: array=0x{arr:x} data=0x{data:x} num={num} max={mx}")
        if not data or not (0<num<=16): continue
        ptrblob=rpm(data,num*8)
        ptrs=struct.unpack("<"+"Q"*num,ptrblob)
        for i,p in enumerate(ptrs):
            b=rpm(p,0x100)
            print(f"  [{i}] 0x{p:x} {b[:32].hex() if b else 'READ_FAIL'}")
            if b:
                q=[struct.unpack_from('<Q',b,o)[0] for o in range(0, min(len(b),64), 8)]
                print("      qwords:", [hex(x) for x in q])
                for qv in q[1:4]:
                    pb=rpm(qv,96) if qv > 0x10000 else None
                    if pb:
                        ps=strings(pb)
                        if ps: print("      pointed:",hex(qv),ps)
                ss=strings(b)
                if ss: print("      strings:",ss)
    for slot in range(3):
        c=struct.unpack_from("<Q",raw,0x328+slot*16)[0]
        b=rpm(c,0x80)
        print(f" ctrl{slot}=0x{c:x} {b[:64].hex() if b else 'READ_FAIL'}")
