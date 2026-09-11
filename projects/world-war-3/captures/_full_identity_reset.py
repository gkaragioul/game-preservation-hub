import os, shutil, time, glob, sqlite3, tempfile

BASE = r'C:\Users\georg\AppData\Local\World War 3 Launcher\Default'
stamp = time.strftime('%Y%m%d_%H%M%S')
BK = os.path.join(r'C:\Users\georg\AppData\Local\World War 3 Launcher', f'Default_fullauthbak_{stamp}')

def copytree(src, dst):
    if os.path.exists(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return True
    return False

print('=== BACKUP ===')
os.makedirs(BK, exist_ok=True)
for rel in ['Local Storage', 'Session Storage', 'Network']:
    ok = copytree(os.path.join(BASE, rel), os.path.join(BK, rel))
    print(f'  backed up {rel}: {ok}')
# also back up Preferences / Secure Preferences (may hold auth state)
for f in ['Preferences', 'Secure Preferences', 'Login Data', 'Login Data For Account']:
    s = os.path.join(BASE, f)
    if os.path.isfile(s):
        shutil.copy2(s, os.path.join(BK, f)); print(f'  backed up {f}')
print('  backup dir:', BK)

print('\n=== WIPE ===')
# 1) delete the persistent id.wishlistgames.net auth cookie (whole Cookies db -> Chromium recreates)
for f in ['Cookies', 'Cookies-journal']:
    p = os.path.join(BASE, 'Network', f)
    try:
        if os.path.exists(p): os.remove(p); print(f'  removed Network/{f}')
    except Exception as e:
        print(f'  ! could not remove {f}: {e}')

# 2) wipe Local Storage leveldb contents
ls = os.path.join(BASE, 'Local Storage', 'leveldb')
if os.path.isdir(ls):
    n = 0
    for x in glob.glob(os.path.join(ls, '*')):
        try: os.remove(x); n += 1
        except Exception as e: print('   ! ', x, e)
    print(f'  wiped Local Storage/leveldb ({n} files)')

# 3) wipe Session Storage
ss = os.path.join(BASE, 'Session Storage')
if os.path.isdir(ss):
    n = 0
    for x in glob.glob(os.path.join(ss, '*')):
        try: os.remove(x); n += 1
        except Exception as e: print('   ! ', x, e)
    print(f'  wiped Session Storage ({n} files)')

print('\n=== VERIFY ===')
# confirm no JWTs remain in Local Storage
import re
remain = 0
for x in glob.glob(os.path.join(ls, '*')):
    try: remain += len(re.findall(rb'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.', open(x,'rb').read()))
    except: pass
print('  JWTs remaining in Local Storage:', remain)
ck = os.path.join(BASE, 'Network', 'Cookies')
print('  Cookies db present:', os.path.exists(ck))
print('\nDONE. Restore command if needed:')
print(f'  robocopy "{BK}" "{BASE}" /E')
