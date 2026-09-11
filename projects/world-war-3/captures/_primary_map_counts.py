from pathlib import Path
from collections import Counter
import re

PRIMARY = {
    'WW3_Shibuya_P', 'WW3_Berlin_Backyards_02_P', 'WW3_Warsaw_Shopping_Mall_P', 'WW3_Moscow_Senate_P',
    'WW3_Landmark_P', 'WW3_Berlin_P', 'WW3_Moscow_P', 'WW3_Warsaw_P', 'WW3_Polarnyj_P', 'WW3_Smolensk_P',
    'WW3_DMZ_P', 'WW3_Tokio_P', 'WW3_Gobi_New_P',
}

files = list(Path(r'F:\Dev_Work\GameDev\WW3\captures').rglob('*.pcapng'))
files += list(Path(r'F:\Dev_Work\GameDev\WW3\captures').rglob('*.pcap'))
want = []
for f in files:
    if f.stat().st_size < 5_000_000:
        continue
    n = f.name.lower()
    if any(x in n for x in ['shibuya', 'berlin', 'warsaw', 'warszawa', 'moskow', 'moscow', 'tdm', 'strong', 'stolong', 'smolensk', 'smolenck']):
        want.append(f)

root = Path(r'F:\Dev_Work\GameDev\WW3\captures')
for f in sorted(want, key=lambda x: x.name.lower()):
    data = f.read_bytes()
    c = Counter(m.decode() for m in re.findall(rb'WW3_[A-Za-z0-9_]+_P', data))
    primary = {k: v for k, v in c.items() if k in PRIMARY}
    print(f'{f.relative_to(root)} ({f.stat().st_size/1e6:.0f}MB)')
    print(f'  primary={primary if primary else "-"}')
    print(f'  top={c.most_common(4)}')
