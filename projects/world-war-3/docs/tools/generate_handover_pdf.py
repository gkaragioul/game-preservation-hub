#!/usr/bin/env python3
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Preformatted, KeepTogether, HRFlowable
)

OUT = Path('/home/georgek/Desktop/WW3_Private_Server_Handover_Report.pdf')
OUT.parent.mkdir(parents=True, exist_ok=True)

PAGE_W, PAGE_H = A4
NAVY = colors.HexColor('#111827')
BLUE = colors.HexColor('#2563EB')
CYAN = colors.HexColor('#0891B2')
GREEN = colors.HexColor('#15803D')
AMBER = colors.HexColor('#B45309')
RED = colors.HexColor('#B91C1C')
SLATE = colors.HexColor('#475569')
LIGHT = colors.HexColor('#F1F5F9')
LINE = colors.HexColor('#CBD5E1')
WHITE = colors.white

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleBig', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=27, leading=32, textColor=NAVY, alignment=TA_LEFT, spaceAfter=8))
styles.add(ParagraphStyle(name='Subtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=12, leading=17, textColor=SLATE, spaceAfter=8))
styles.add(ParagraphStyle(name='H1x', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=NAVY, spaceBefore=10, spaceAfter=8))
styles.add(ParagraphStyle(name='H2x', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=BLUE, spaceBefore=8, spaceAfter=5))
styles.add(ParagraphStyle(name='Bodyx', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.4, leading=13.6, textColor=NAVY, spaceAfter=5))
styles.add(ParagraphStyle(name='Smallx', parent=styles['BodyText'], fontName='Helvetica', fontSize=7.8, leading=10.5, textColor=SLATE, spaceAfter=3))
styles.add(ParagraphStyle(name='Bulletx', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.2, leading=13.2, leftIndent=13, firstLineIndent=-7, bulletIndent=5, textColor=NAVY, spaceAfter=3))
styles.add(ParagraphStyle(name='Callout', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=9.6, leading=13.5, textColor=NAVY, spaceAfter=0))
styles.add(ParagraphStyle(name='CodeLabel', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=SLATE, spaceAfter=3))
styles.add(ParagraphStyle(name='TOC', parent=styles['BodyText'], fontName='Helvetica', fontSize=10, leading=16, textColor=NAVY, leftIndent=8))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(18*mm, 14*mm, PAGE_W-18*mm, 14*mm)
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(SLATE)
    canvas.drawString(18*mm, 9*mm, 'WW3 Private-Server Revival - AI Handover Report')
    canvas.drawRightString(PAGE_W-18*mm, 9*mm, f'Page {doc.page}')
    canvas.restoreState()


def P(text, style='Bodyx'):
    return Paragraph(text, styles[style])


def H1(text):
    return Paragraph(text, styles['H1x'])


def H2(text):
    return Paragraph(text, styles['H2x'])


def B(text):
    return Paragraph('&bull; ' + text, styles['Bulletx'])


def Code(text, label=None):
    parts = []
    if label:
        parts.append(P(label, 'CodeLabel'))
    parts.append(Preformatted(text.strip(), ParagraphStyle(
        name='CodeBlockTemp', fontName='Courier', fontSize=7.2, leading=9.4,
        leftIndent=7, rightIndent=7, borderColor=LINE, borderWidth=0.5,
        borderPadding=7, backColor=colors.HexColor('#F8FAFC'),
        textColor=colors.HexColor('#0F172A'), spaceBefore=2, spaceAfter=8)))
    return parts


def Callout(title, text, color=BLUE):
    data = [[Paragraph(title, ParagraphStyle(name='ct'+title[:5], parent=styles['Callout'], textColor=color)),
             Paragraph(text, styles['Bodyx'])]]
    t = Table(data, colWidths=[39*mm, 132*mm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,0),colors.HexColor('#EFF6FF')),
        ('BACKGROUND',(1,0),(1,0),colors.HexColor('#F8FAFC')),
        ('BOX',(0,0),(-1,-1),0.7,color),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]))
    return t


def DataTable(rows, widths, header=True):
    conv = []
    for r, row in enumerate(rows):
        conv.append([Paragraph(str(cell), styles['Smallx'] if r else ParagraphStyle(name=f'th{len(conv)}', parent=styles['Smallx'], fontName='Helvetica-Bold', textColor=WHITE)) for cell in row])
    t = Table(conv, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
    cmds = [
        ('GRID',(0,0),(-1,-1),0.45,LINE),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]
    if header:
        cmds += [('BACKGROUND',(0,0),(-1,0),NAVY)]
        for i in range(1, len(rows)):
            if i % 2 == 0:
                cmds.append(('BACKGROUND',(0,i),(-1,i),colors.HexColor('#F8FAFC')))
    t.setStyle(TableStyle(cmds))
    return t


doc = BaseDocTemplate(
    str(OUT), pagesize=A4,
    rightMargin=18*mm, leftMargin=18*mm, topMargin=17*mm, bottomMargin=19*mm,
    title='WW3 Private-Server Revival - AI Handover Report',
    author='Hermes Agent for Repository Owner',
    subject='Technical handover for continued AI implementation of the World War 3 private-server revival'
)
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='main')
doc.addPageTemplates(PageTemplate(id='normal', frames=[frame], onPage=footer))

story = []

# Title page
story += [Spacer(1, 15*mm), P('GAME PRESERVATION / PRIVATE BACKEND', 'Smallx'),
          P('World War 3', 'TitleBig'),
          P('Private-Server Revival', 'TitleBig'),
          Spacer(1, 4*mm),
          HRFlowable(width='100%', thickness=3, color=BLUE, spaceAfter=8),
          P('Technical AI Handover Report', 'Subtitle'),
          P('Prepared 22 July 2026, 19:17 EEST', 'Subtitle'),
          Spacer(1, 11*mm),
          Callout('Current objective', 'Continue autonomously until the installed Steam client reaches the real Main Menu through local REST, WebSocket Hub, and XMPP mocks. Do not revert to the SECRETMS path unless the normal FXID route is conclusively blocked.', GREEN),
          Spacer(1, 7*mm),
          Callout('Current status', 'Linux/Proton viability is proven. The official launcher logs into the user\'s own Steam/FXID account, validates all files, mints a valid FXID token, and launches the protected game. The remaining task is to capture and satisfy the first backend request after EOS initialization.', BLUE),
          Spacer(1, 7*mm),
          Callout('Security', 'A live seven-day FXID bearer token exists locally with mode 600. Its value is NOT contained in this PDF. Never print, paste, commit, upload, or transmit it.', RED),
          Spacer(1, 16*mm),
          P('<b>Owner:</b> georgek / OfflinePlayer[STEAM]', 'Bodyx'),
          P('<b>Workspace:</b> /media/georgek/Work/Dev_Work/GameDev/WW3', 'Bodyx'),
          P('<b>Target platform:</b> Linux using Proton Experimental', 'Bodyx'),
          PageBreak()]

# Contents
story += [H1('Contents')]
for item in [
    '1. Executive summary', '2. Environment and paths', '3. Source material',
    '4. Recovered online architecture', '5. Implemented mock backend',
    '6. Authentication findings and breakthroughs', '7. SECRETMS investigation',
    '8. Current live system state', '9. Exact continuation procedure',
    '10. Verification criteria and diagnostic branches', '11. Cleanup and safety',
    '12. File inventory and final handover checklist']:
    story.append(P(item, 'TOC'))
story.append(PageBreak())

story += [H1('1. Executive summary'),
          P('The goal is to revive the discontinued online game <b>World War 3</b> by replacing its unavailable backend services with local mocks. The user expects implementation-first progress and a playable result, not a request list for the outside preservation team.'),
          P('The installed Windows client and official CEF launcher both run under Proton on Linux. The launcher successfully authenticates the user through the still-live FXID identity service, validates the 58.2 GB installation, generates a correctly signed token, and starts the EAC-protected shipping executable.'),
          P('Four local services have been implemented: HTTP, HTTPS, WebSocket JSON-RPC Hub, and XMPP. The Hub mock has passed a standalone simulated-client test using RPCs recovered from a known-working June 2026 game log.'),
          P('The immediate unresolved point is determining the first backend call made after the real-token launch finishes EOS and asset initialization. The latest exact replay remained alive for at least 43 seconds but the observation was interrupted before the normal 90-120 second startup period completed.'),
          Callout('Chosen strategy', '<b>Option B:</b> use the normal FXID/meta route. Do not launch with <font name="Courier">-Continent=SECRETMS</font>. The SECRETMS flag selects a separate custom master-server protocol on port 8443 and bypasses the REST/Hub/XMPP stack already implemented.', GREEN),
          H2('What is already proven'),
          B('Linux/Proton can run the official launcher, EAC bootstrap, and shipping game executable.'),
          B('EAC tolerates an unavailable CDN and starts in null-client mode.'),
          B('The official launcher can still authenticate the user and mint a valid FXID token.'),
          B('The game locally parses the recovered FXID JWT schema correctly.'),
          B('The menu-driving transport is WebSocket JSON-RPC, not REST alone.'),
          B('The game libcurl path has certificate verification disabled; no pinning patch is required.'),
          PageBreak()]

story += [H1('2. Environment and paths')]
story.append(DataTable([
    ['Item','Value'],
    ['Host','Linux workstation Megatron'],
    ['User','georgek; passwordless sudo available via sudo -n'],
    ['Workspace','/media/georgek/Work/Dev_Work/GameDev/WW3'],
    ['Steam app','World War 3, app ID 674020'],
    ['Game install','/media/georgek/Games/SteamLibrary/steamapps/common/World War 3'],
    ['Proton prefix','/media/georgek/Games/SteamLibrary/steamapps/compatdata/674020'],
    ['Proton','/home/georgek/.local/share/Steam/steamapps/common/Proton - Experimental/proton'],
    ['Shipping binary','WW3/Binaries/Win64/WW3-Win64-Shipping.exe'],
    ['EAC bootstrap','start_protected_game.exe'],
    ['Launcher bootstrap','WW3_Launcher.exe'],
    ['CEF launcher','Launcher/WW3_Launcher.exe'],
], [43*mm, 128*mm]))
story += [Spacer(1,5*mm), H2('Client facts'),
          B('Unreal Engine 4.21.'), B('libcurl 7.82 with OpenSSL 1.1.1.'),
          B('EOS SDK and Easy Anti-Cheat are bundled.'),
          B('The installed depot is approximately 58.2 GB and passed launcher integrity checks.'),
          PageBreak()]

story += [H1('3. Source material')]
story.append(DataTable([
    ['Artifact','Contents / value'],
    ['stub.py','Team XMPP stub; stream, auth, bind, session, presence, ping handling.'],
    ['api_server.py / https_server.py','Original generic HTTP/HTTPS mocks.'],
    ['Launcher-*.zip','Launcher.pcap plus synchronized screen recording.'],
    ['Direct-*.zip','Direct connection pcap plus synchronized recording.'],
    ['Match_tacops_DMZ-*.zip','Still, walk, run, drive, infantry, tank, and capture pcaps/videos.'],
    ['Crashes-*.zip','Hundreds of Unreal WW3.log files, crash contexts, and minidumps.'],
    ['message*.txt','Real XMPP sessions against the team stub.'],
    ['analysis/ and captures/','Extracted pcaps, logs, and crash evidence.'],
], [50*mm,121*mm]))
story += [Spacer(1,5*mm),
          P('The most valuable artifact is a complete June 2026 working-session <font name="Courier">WW3.log</font>. It reveals the real host order, WebSocket URL, RPC messages and responses, XMPP behavior, menu transition, lobby object, and dedicated server handoff.'),
          PageBreak()]

story += [H1('4. Recovered online architecture')]
story.append(DataTable([
    ['Layer','Endpoint','Transport','Purpose'],
    ['FXID identity','id-dev.fx.gl / id.fx.gl','HTTPS','Launcher login and JWT issue.'],
    ['Meta backend','meta.prod.ww3.fxtools.gl:443','HTTPS','Friends, profile/bootstrap data.'],
    ['Public/time API','api.public.dev.ww3.fxtools.gl:443','HTTPS','Date/time and config retries.'],
    ['Hub','historically 213.183.62.234:8705','WebSocket JSON-RPC','Menu and live lobby brain.'],
    ['Presence','xmpp.prod.ww3.fxtools.gl:5222','XMPP','Online status and keepalive.'],
    ['Match','per-match address, 7867/7868','UDP','Actual gameplay replication.'],
    ['Connectivity','api.ipify.org','HTTP','Public IP / reachability check.'],
], [30*mm,52*mm,34*mm,55*mm]))
story += [H2('TLS result'),
          P('The working log explicitly reports: <font name="Courier">bVerifyPeer = false - Libcurl will NOT verify peer certificate</font>. No certificate-pinning evidence was found. A local self-signed certificate is accepted by the game libcurl path.'),
          H2('Menu-driving RPC protocol')]
story += Code('''Request:
{"type":"RpcRequest","id":123,"context":"friends","method":"changeStatus","args":[1]}

Response:
{"type":"RpcResponse","id":123,"result":true}''')
story += [P('Observed opening RPCs include <font name="Courier">onlineParameters.getParameters</font>, <font name="Courier">notifications.getNotifications</font>, <font name="Courier">friends.changeStatus</font>, and <font name="Courier">debug.log</font>. The working log transitions to <font name="Courier">MainMenu</font> immediately after this Hub exchange.'),
          H2('XMPP behavior'),
          B('Port 5222; DIGEST-MD5 requested by client.'),
          B('JID form: prod-&lt;player-id&gt;@xmpp.prod.ww3.fxtools.gl/V2:WW3:::&lt;session&gt;.'),
          B('Client ping cadence is approximately ten seconds.'),
          B('Existing mock successfully completes stream, auth, bind, session, presence and pong.'),
          PageBreak()]

story += [H1('5. Implemented mock backend')]
story.append(DataTable([
    ['File','Status','Function'],
    ['mockserver/hub_server.py','Unit-tested PASS','WebSocket 8705; recovered JSON-RPC responses and generic fallback.'],
    ['mockserver/rest_server.py','Implemented','Path-aware HTTP/HTTPS on 80/443; friends, invitations, time and auth-shaped fallback.'],
    ['mockserver/xmpp_server.py','Implemented','XMPP 5222 handshake, presence and keepalive.'],
    ['mockserver/launch_ww3_mock.sh','Implemented','Hosts, services, raw-IP DNAT and teardown.'],
    ['mockserver/make_fxid_token.py','Parser test only','Creates schema-correct synthetic JWT; not accepted by EOS.'],
    ['mockserver/check_fxid_schema.py','Tested PASS','Validates recovered HS512 FXID claim schema.'],
    ['WW3_ENDPOINT_MAP.md','Current','Protocol notes and endpoint map.'],
], [54*mm,31*mm,86*mm]))
story += [H2('Hub standalone test'),
          P('A simulated client successfully connected to port 8705 and received correctly correlated responses for online parameters, notifications, friend status, debug logging, and an unknown fallback method.'),
          Callout('Important limitation', 'Generic fallback responses are useful for discovery but are not proof of correctness. Once the real client reaches an unimplemented call, capture the exact request and recover the corresponding real response shape rather than adding arbitrary fields.', AMBER),
          PageBreak()]

story += [H1('6. Authentication findings and breakthroughs'),
          H2('Recovered JWT schema'),
          P('A scan of supplied crash archives found 264 unique working FXID tokens. The real schema uses HS512 and eleven required claims. The token itself must never be copied into reports or source control.')]
story.append(DataTable([
    ['Claim','Expected type / meaning'],
    ['sub, id','Integer FXID identity; not the WW3 profile ID.'],
    ['auth_type','String, normally steam.'],
    ['public_tags','String, normally [].'],
    ['soc_ids','Object containing linked Steam and optional My.Games identity.'],
    ['email','String.'],
    ['nbf, exp, iat','Integer timestamps.'],
    ['iss, aud','https://id.fx.gl'],
], [43*mm,128*mm]))
story += [H2('Synthetic-token result'),
          P('The first fake used HS256 and incomplete claims, causing <font name="Courier">Failed to extract user data from token</font>. A corrected HS512 synthetic token made the parser log <font name="Courier">Extracted Email ... ID</font>, proving the schema. Epic EOS then correctly rejected its untrusted signature with HTTP 401 and <font name="Courier">external.invalid_token</font>.'),
          H2('Official launcher result'),
          P('The official CEF launcher runs under Proton, signs in as <b>OfflinePlayer[STEAM]</b>, validates the installation, and starts EAC with a real FXID token. Its application log recorded successful integrity checks and 100 percent torrent state.'),
          P('A fresh user-owned token was extracted securely from the local launcher log and written to:'),
          P('<font name="Courier">/media/georgek/Work/Dev_Work/GameDev/WW3/mockserver/fxid_live_token.txt</font>'),
          Callout('Token handling', 'File mode is 600. The token was valid for approximately seven days when generated. Never expose its value. If expired, rerun the official launcher with id-dev.fx.gl left live and securely re-extract the latest token.', RED),
          PageBreak()]

story += [H1('7. SECRETMS investigation'),
          P('The team-provided batch file uses <font name="Courier">-Continent=SECRETMS</font>. Testing proved that this selects a separate Steam-ticket authentication architecture instead of the normal FXID/meta route.'),
          P('It contacts <font name="Courier">live.master.worldwar3.com:8443</font> and reports missing GAS/authentication responses. Multiple dev, QA, PTE, MENA and seasonal master endpoints are embedded in the binary. This likely uses a custom master protocol and would require separate reverse engineering.'),
          Callout('Decision', 'Do not use SECRETMS for the current implementation. Continue with the normal launcher arguments and FXID token because the REST, Hub and XMPP layers for that route are already recovered and implemented.', GREEN),
          H2('EAC result'),
          P('EAC is not the principal blocker. Its log showed a CDN 403 followed by <font name="Courier">launching with null client</font> and <font name="Courier">Easy Anti-Cheat successfully loaded in-game</font>. Always start the game through <font name="Courier">start_protected_game.exe</font>, not the raw shipping executable.'),
          PageBreak()]

story += [H1('8. Current live system state'),
          Callout('State at report generation', 'The game and official launcher are stopped. All four mock listeners remain active. The hosts redirects and Hub DNAT rule remain installed. The environment is intentionally ready for the next test but is not clean.', AMBER)]
story.append(DataTable([
    ['Component','State'],
    ['Game / launcher','Stopped.'],
    ['HTTP mock','Listening on 0.0.0.0:80.'],
    ['HTTPS mock','Listening on 0.0.0.0:443.'],
    ['XMPP mock','Listening on 127.0.0.1:5222.'],
    ['Hub mock','Listening on 0.0.0.0:8705.'],
    ['Hub DNAT','213.183.62.234:8705 -> 127.0.0.1:8705.'],
    ['id-dev.fx.gl','Not redirected; must remain live for official launcher token generation.'],
    ['Live token','Present locally, mode 600, value not included.'],
], [52*mm,119*mm]))
story += [H2('/etc/hosts redirects currently installed')]
story += Code('''127.0.0.1 meta.prod.ww3.fxtools.gl
127.0.0.1 meta.dev.ww3.fxtools.gl
127.0.0.1 api.public.dev.ww3.fxtools.gl
127.0.0.1 xmpp.prod.ww3.fxtools.gl
127.0.0.1 xmpp.dev.ww3.fxtools.gl
127.0.0.1 ww3.anticheat.my.games
127.0.0.1 api.ipify.org''')
story.append(PageBreak())

story += [H1('9. Exact continuation procedure'),
          H2('Step 1 - Verify mocks and routing')]
story += Code('''cd /media/georgek/Work/Dev_Work/GameDev/WW3/mockserver

ss -tlnp | grep -E ':(80|443|5222|8705)\\s'
getent ahostsv4 meta.prod.ww3.fxtools.gl
sudo -n iptables -t nat -L OUTPUT -n | grep 8705''')
story += [P('Expected: four listeners, meta.prod resolving to 127.0.0.1, and one DNAT rule for 213.183.62.234:8705.'),
          H2('Step 2 - Launch exact normal FXID route with logging')]
story += Code('''cd "/media/georgek/Games/SteamLibrary/steamapps/common/World War 3"

export STEAM_COMPAT_CLIENT_INSTALL_PATH="/home/georgek/.local/share/Steam"
export STEAM_COMPAT_DATA_PATH="/media/georgek/Games/SteamLibrary/steamapps/compatdata/674020"
export SteamAppId=674020
export SteamGameId=674020

TOK="$(cat /media/georgek/Work/Dev_Work/GameDev/WW3/mockserver/fxid_live_token.txt)"
PROTON="/home/georgek/.local/share/Steam/steamapps/common/Proton - Experimental/proton"

"$PROTON" run start_protected_game.exe \\
  -log \\
  -pref_language english \\
  --fxid-login-token="$TOK" \\
  -NoMrac \\
  -Region=meta.prod.ww3.fxtools.gl:443 \\
  -FXGamesInit=1''')
story += [P('Do not add <font name="Courier">-Continent=SECRETMS</font>. Allow 90-120 seconds for EAC, EOS and asset initialization before judging the result.'),
          H2('Step 3 - Observe the real seam')]
story += Code('''gnome-screenshot -f /tmp/ww3_real_token_live.png

ps -eo pid,etimes,args | grep WW3-Win64-Shipping.exe

for f in https http hub xmpp; do
  echo "=== $f ==="
  tail -100 "/tmp/ww3mock/$f.log"
done

ss -tnp | grep -E 'GameThread|WW3-Win64'

find "/media/georgek/Games/SteamLibrary/steamapps/compatdata/674020/pfx/drive_c/users/steamuser/AppData/Local/WW3/Saved" \\
  -name WW3.log -newermt '-5 min' -print''')
story.append(PageBreak())

story += [H1('10. Verification criteria and diagnostic branches'),
          H2('Success criteria'),
          B('HTTPS mock receives the meta/bootstrap request.'),
          B('Hub mock accepts a WebSocket connection on 8705.'),
          B('Client sends onlineParameters, notifications and friends RPC calls.'),
          B('XMPP mock receives a connection and completes session/presence.'),
          B('Client log transitions from InitialMenuState to MainMenu.'),
          B('The visible client reaches the actual main menu.'),
          H2('If the game exits before any mock request'),
          P('Read the newest crash <font name="Courier">WW3.log</font>. Confirm the real token was locally parsed and EOS login succeeded. Isolate the first failed host/path after that point. Do not add more guessed responses.'),
          H2('If the game stays alive but bypasses local meta'),
          P('Capture TLS SNI during a fresh launch with tshark, inspect live sockets, verify Proton sees /etc/hosts through <font name="Courier">/proc/&lt;pid&gt;/root/etc/hosts</font>, and identify whether the bootstrap address is raw IP. Add only a precise routing rule.'),
          H2('If Hub connects but menu still hangs'),
          P('Compare each real RpcRequest against the June working log. Recover the exact expected result shape and add a targeted handler. Keep request IDs correlated. Avoid blanket success objects once the real call is known.'),
          H2('If the token expires'),
          P('Remove only the <font name="Courier">id-dev.fx.gl</font> redirect if present, flush DNS cache, start the official <font name="Courier">WW3_Launcher.exe</font>, allow integrity checking, and securely extract the newest token from the launcher application log. Never include it in AI prompts.'),
          PageBreak()]

story += [H1('11. Cleanup and safety'),
          P('The current environment is dirty by design. When testing is complete or before unrelated network work, run the launcher teardown and verify every side effect is removed.')]
story += Code('''cd /media/georgek/Work/Dev_Work/GameDev/WW3/mockserver
sudo -n bash launch_ww3_mock.sh down

ss -tlnp | grep -E ':(80|443|5222|8705)\\s' || echo "ports free"
grep -E 'fxtools|my.games|ipify' /etc/hosts || echo "hosts clean"
sudo -n iptables -t nat -L OUTPUT -n | grep 8705 || echo "DNAT clean"
ps -eo args | grep WW3-Win64-Shipping.exe | grep -v grep || echo "game stopped"''')
story += [Callout('Do not remove user data', 'Do not delete the Steam game, Proton prefix, crash captures, launcher cache or secure token file while debugging. Never upload the token file or raw launcher app.log.', RED),
          PageBreak()]

story += [H1('12. File inventory and handover checklist')]
story.append(DataTable([
    ['Path','Purpose'],
    ['mockserver/hub_server.py','Menu/lobby WebSocket RPC mock.'],
    ['mockserver/rest_server.py','HTTP/HTTPS route-aware mock.'],
    ['mockserver/xmpp_server.py','XMPP presence server.'],
    ['mockserver/launch_ww3_mock.sh','Setup, redirect and teardown orchestration.'],
    ['mockserver/check_fxid_schema.py','Recovered JWT schema test.'],
    ['mockserver/make_fxid_token.py','Synthetic parser-test token generator.'],
    ['mockserver/fxid_live_token.txt','Sensitive current real token; mode 600; never expose.'],
    ['WW3_ENDPOINT_MAP.md','Endpoint and RPC notes.'],
    ['captures/','Extracted network captures.'],
    ['analysis/crashes/','Recovered working and crash logs.'],
], [69*mm,102*mm]))
story += [Spacer(1,5*mm), H2('Incoming AI checklist'),
          B('Read this report and WW3_ENDPOINT_MAP.md before modifying mocks.'),
          B('Confirm current side effects and service state before launching.'),
          B('Use the normal FXID route; no SECRETMS.'),
          B('Do not reveal the live token.'),
          B('Run the exact EAC command and wait the full startup period.'),
          B('Capture the first real missing seam and implement one targeted response.'),
          B('Verify visible MainMenu before declaring the phase complete.'),
          B('Run teardown and verify the host is clean when done.'),
          Spacer(1,8*mm),
          HRFlowable(width='100%', thickness=1, color=LINE, spaceAfter=7),
          P('<b>End state expected from next AI:</b> a verified client run reaching MainMenu, with logs showing REST bootstrap, Hub RPC and XMPP session against local services—or a sharply isolated next protocol blocker backed by a fresh log/capture.', 'Bodyx')]

doc.build(story)
print(OUT)
