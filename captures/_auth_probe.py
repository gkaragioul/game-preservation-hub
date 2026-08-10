import re, json, ssl, socket
from pathlib import Path

host = 'meta.prod.ww3.fxtools.gl'
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
log = Path(r'C:\Users\georg\AppData\Local\World War 3 Launcher\Logs\app.log').read_text(encoding='utf-8', errors='replace')
tok = re.findall(r'--fxid-login-token=(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)', log)[-1]

def raw(ip, reqbytes):
    s = ctx.wrap_socket(socket.create_connection((ip,443),timeout=12), server_hostname=host)
    s.sendall(reqbytes); d=b''
    while True:
        try: c=s.recv(65536)
        except: break
        if not c: break
        d+=c
    s.close(); return d.decode('utf-8','replace')

def outcome(r):
    line0 = r.split('\r\n',1)[0]
    if 'PlayerToken' in r or '"result"' in r: tag='*** SUCCESS ***'
    else:
        m=re.search(r'"message"\s*:\s*"([^"]+)"', r); tag = m.group(1) if m else r[-60:]
    return f'{line0} :: {tag}'

body = json.dumps({'fxToken': tok}, separators=(',',':')).encode()

variants = {
  'body fxToken':      b'POST /authenticate/fxgames HTTP/1.1\r\nhost: %b\r\ncontent-type: application/json\r\ncontent-length: %d\r\nconnection: close\r\n\r\n%b',
}

ips = ['89.167.35.180','89.167.42.183','89.167.40.140']
for ip in ips:
    print('==== IP', ip, '====')
    # 1 body
    req = b'POST /authenticate/fxgames HTTP/1.1\r\nhost: '+host.encode()+b'\r\ncontent-type: application/json\r\ncontent-length: '+str(len(body)).encode()+b'\r\nconnection: close\r\n\r\n'+body
    try: print('  body fxToken       ->', outcome(raw(ip, req)))
    except Exception as e: print('  body fxToken       ERR', e)
    # 2 Authorization Bearer + empty body
    req = b'POST /authenticate/fxgames HTTP/1.1\r\nhost: '+host.encode()+b'\r\nauthorization: Bearer '+tok.encode()+b'\r\ncontent-type: application/json\r\ncontent-length: 2\r\nconnection: close\r\n\r\n{}'
    try: print('  Authorization Bear ->', outcome(raw(ip, req)))
    except Exception as e: print('  Authorization Bear ERR', e)
    # 3 x-fxid-token header
    req = b'POST /authenticate/fxgames HTTP/1.1\r\nhost: '+host.encode()+b'\r\nx-fxid-token: '+tok.encode()+b'\r\ncontent-type: application/json\r\ncontent-length: 2\r\nconnection: close\r\n\r\n{}'
    try: print('  x-fxid-token       ->', outcome(raw(ip, req)))
    except Exception as e: print('  x-fxid-token       ERR', e)
    # 4 body key "token"
    b2 = json.dumps({'token': tok}, separators=(',',':')).encode()
    req = b'POST /authenticate/fxgames HTTP/1.1\r\nhost: '+host.encode()+b'\r\ncontent-type: application/json\r\ncontent-length: '+str(len(b2)).encode()+b'\r\nconnection: close\r\n\r\n'+b2
    try: print('  body token         ->', outcome(raw(ip, req)))
    except Exception as e: print('  body token         ERR', e)
