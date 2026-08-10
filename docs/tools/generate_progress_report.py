#!/usr/bin/env python3
"""Generate WW3_Project_Progress_Report.pdf in the workspace.
Explains the concept, goal, architecture and full progress of the WW3
private-server revival, including this session's root-cause findings.
The live FXID token value is never included."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Preformatted, HRFlowable
)

OUT = Path('/media/georgek/Work/Dev_Work/GameDev/WW3/WW3_Project_Progress_Report.pdf')

PAGE_W, PAGE_H = A4
NAVY = colors.HexColor('#111827')
BLUE = colors.HexColor('#2563EB')
CYAN = colors.HexColor('#0891B2')
GREEN = colors.HexColor('#15803D')
AMBER = colors.HexColor('#B45309')
RED = colors.HexColor('#B91C1C')
SLATE = colors.HexColor('#475569')
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
    canvas.setStrokeColor(LINE); canvas.setLineWidth(0.4)
    canvas.line(18*mm, 14*mm, PAGE_W-18*mm, 14*mm)
    canvas.setFont('Helvetica', 7.5); canvas.setFillColor(SLATE)
    canvas.drawString(18*mm, 9*mm, 'WW3 Private-Server Revival - Project Progress & Concept')
    canvas.drawRightString(PAGE_W-18*mm, 9*mm, f'Page {doc.page}')
    canvas.restoreState()


def P(text, style='Bodyx'): return Paragraph(text, styles[style])
def H1(text): return Paragraph(text, styles['H1x'])
def H2(text): return Paragraph(text, styles['H2x'])
def B(text): return Paragraph('&bull; ' + text, styles['Bulletx'])


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
    data = [[Paragraph(title, ParagraphStyle(name='ct'+title[:6], parent=styles['Callout'], textColor=color)),
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
    title='WW3 Private-Server Revival - Project Progress & Concept',
    author='Claude Code for Repository Owner',
    subject='Concept, goal and full progress of the World War 3 private-server revival'
)
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='main')
doc.addPageTemplates(PageTemplate(id='normal', frames=[frame], onPage=footer))

story = []

# ---- Title page ----
story += [Spacer(1, 15*mm), P('GAME PRESERVATION / PRIVATE BACKEND', 'Smallx'),
          P('World War 3', 'TitleBig'),
          P('Private-Server Revival', 'TitleBig'),
          Spacer(1, 4*mm),
          HRFlowable(width='100%', thickness=3, color=BLUE, spaceAfter=8),
          P('Project Progress &amp; Concept', 'Subtitle'),
          P('Updated 22 July 2026', 'Subtitle'),
          Spacer(1, 10*mm),
          Callout('The concept', 'World War 3 is an online-only shooter whose live backend is no longer usable. This project makes the user\'s own, legally-installed copy playable again by standing up local replacements for the game\'s backend services and steering the client to them - the same idea as a community private server for a retired MMO.', GREEN),
          Spacer(1, 6*mm),
          Callout('The goal', 'Drive the installed Steam client - through the real Easy Anti-Cheat bootstrap and the user\'s own account - all the way to a working Main Menu against local REST, WebSocket Hub and XMPP mocks, with no live game servers involved.', BLUE),
          Spacer(1, 6*mm),
          Callout('Scope &amp; ownership', 'Everything runs on the owner\'s own machine, with the owner\'s own game licence and identity. No anti-cheat is defeated (EAC runs normally in offline mode); nothing is redistributed. This is interoperability / preservation work, and the associated Terms-of-Service and legal considerations are the owner\'s to weigh.', SLATE),
          Spacer(1, 12*mm),
          P('<b>Owner:</b> georgek / OfflinePlayer[STEAM]', 'Bodyx'),
          P('<b>Workspace:</b> /media/georgek/Work/Dev_Work/GameDev/WW3', 'Bodyx'),
          P('<b>Platform:</b> Linux (workstation "Megatron") + Proton Experimental', 'Bodyx'),
          PageBreak()]

# ---- Contents ----
story += [H1('Contents')]
for item in [
    '1. What this project is (concept &amp; goal)',
    '2. How the game gets online (recovered architecture)',
    '3. The emulation strategy',
    '4. What was built before this session',
    '5. This session - root-cause breakthroughs',
    '6. The DNS / c-ares discovery (why redirects failed)',
    '7. Launch mechanics &amp; Easy Anti-Cheat',
    '8. Current system state',
    '9. Remaining work to reach Main Menu',
    '10. Glossary']:
    story.append(P(item, 'TOC'))
story.append(PageBreak())

# ---- 1 ----
story += [H1('1. What this project is (concept &amp; goal)'),
          P('World War 3 (Steam app 674020) is a multiplayer-only first-person shooter. Like most online games, the client is only half of the product: on startup it must reach a chain of backend services to authenticate the player, load their profile, and connect them to the lobby "Hub". When those services are unavailable, the client boots but stalls before the menu - there is no offline mode.'),
          P('This project revives the game for a single owned copy by <b>re-creating those backend services locally</b> and making the client talk to them instead of the (now unusable) real servers. The end result we are driving toward is simple and concrete: the game window reaches its real <b>Main Menu</b>, powered entirely by mock servers on this machine.'),
          Callout('Why it is legitimate', 'The client is launched through its normal Easy Anti-Cheat bootstrap and runs unmodified - EAC simply starts in offline / null-client mode when its CDN is unreachable. Nothing is patched, cracked, or redistributed, and there are no other players to cheat against. It is the owner\'s copy, account and hardware throughout.', GREEN),
          H2('Definition of done'),
          B('The client, launched via the official launcher + EAC, authenticates with the owner\'s FXID token.'),
          B('Its backend traffic (meta, Hub, XMPP) is served by local mocks, not live servers.'),
          B('The client transitions from <font name="Courier">InitialMenuState</font> to <font name="Courier">MainMenu</font> and the menu is visible and interactive.'),
          PageBreak()]

# ---- 2 ----
story += [H1('2. How the game gets online (recovered architecture)'),
          P('The connection order below was reverse-engineered from a complete <b>known-working session log dated 12 June 2026</b> (captured while the real servers were still up), from packet captures, and from hundreds of recovered crash logs. Each layer must succeed for the client to reach the menu.')]
story.append(DataTable([
    ['#','Layer','Real endpoint','Transport','Purpose'],
    ['1','FXID identity','id.fx.gl / id-dev.fx.gl','HTTPS','Account login; mints the signed FXID JWT.'],
    ['2','EOS + EAC','epicgames.dev, ww3.anticheat.my.games','HTTPS','Epic Online Services + anti-cheat handshake.'],
    ['3','Meta / master','meta.prod.ww3.fxtools.gl:443','HTTPS','Authorises the session, returns the WW3 profile id and the Hub token.'],
    ['4','Hub','213.183.62.234:8705','WebSocket JSON-RPC','THE menu / lobby brain - all live menu data.'],
    ['5','Presence','xmpp.prod.ww3.fxtools.gl:5222','XMPP','Friends presence and keepalive.'],
    ['6','Match','per-match IP, 7867/7868','UDP','Actual in-match gameplay replication.'],
], [7*mm,26*mm,55*mm,34*mm,49*mm]))
story += [Spacer(1,4*mm),
          H2('The authorisation handshake (the crux)'),
          P('In the working log the client sends its FXID token to the <b>meta / master server</b>, which validates it and replies with the player\'s real WW3 profile id and a second, short-lived <b>Hub session token</b>. Only then does the client open the Hub WebSocket, carrying that token in the URL path, and drive the menu over JSON-RPC:')]
story += Code('''# master server authorises -> gives profile id + hub token
[UWW3PlatformManager::SetIsConnectedToMasterServer] InternalPlayerId: [100001]

# client then opens the Hub WebSocket with a second (HS256) token in the path
ws://213.183.62.234:8705/client/<hub-session-JWT>

# menu-driving JSON-RPC over that socket
-> {"type":"RpcRequest","id":123,"context":"onlineParameters","method":"getParameters","args":[]}
<- {"type":"RpcResponse","id":123,"result":{"type":"OnlineParameters","pingPongInterval":4000,...}}
-> friends.changeStatus / notifications.getNotifications / debug.log ...
# ... immediately followed by the transition to MainMenu''')
story += [P('<b>Key implication:</b> because the meta server is the thing that hands out the profile id and Hub token, once <i>we</i> control the meta response we control the whole chain - the client will accept a locally-issued identity and Hub token.'),
          Callout('TLS is wide open', 'The client\'s libcurl runs with bVerifyPeer = false - it does not verify server certificates and there is no pinning. A local self-signed certificate is accepted with zero binary patching.', BLUE),
          PageBreak()]

# ---- 3 ----
story += [H1('3. The emulation strategy'),
          P('Rather than reverse-engineer and reimplement the entire backend, we implement just enough of each service to satisfy the client\'s startup path, and reroute the client\'s network traffic to those local services.'),
          H2('Local mock services (all on this machine)')]
story.append(DataTable([
    ['Mock','Port','Replaces','Role'],
    ['rest_server.py','443 / 80','meta.prod + public API','Friends, invitations, profile bootstrap, time; self-signed TLS.'],
    ['hub_server.py','8705','Hub WebSocket','JSON-RPC menu brain: onlineParameters, notifications, friends, debug, generic fallback.'],
    ['xmpp_server.py','5222','xmpp.prod','Stream, auth, bind, session, presence, keepalive.'],
], [40*mm,20*mm,42*mm,69*mm]))
story += [Spacer(1,4*mm),
          H2('Two ways to reroute traffic - only one works'),
          P('The original approach used <font name="Courier">/etc/hosts</font> entries pointing each backend hostname at 127.0.0.1, plus a single iptables DNAT rule for the raw-IP Hub. Section 6 explains why the hosts entries never actually took effect and why <b>iptables DNAT is the only reliable mechanism</b> for this client.'),
          Callout('The corrected principle', 'Redirect by destination IP at the firewall (iptables nat OUTPUT -> DNAT to 127.0.0.1), not by hostname in /etc/hosts. The game\'s resolver bypasses /etc/hosts entirely.', GREEN),
          PageBreak()]

# ---- 4 ----
story += [H1('4. What was built before this session'),
          B('A full mock backend: path-aware HTTP/HTTPS server, a WebSocket JSON-RPC Hub, and an XMPP presence server, plus an orchestration script (hosts + DNAT + teardown).'),
          B('A self-signed certificate accepted by the client\'s non-verifying libcurl.'),
          B('The FXID JWT schema, recovered from 264 real tokens found in crash archives: HS512, eleven required claims (sub/id, auth_type, soc_ids, email, nbf/exp/iat, iss/aud).'),
          B('A validated understanding of the menu-driving JSON-RPC protocol and the XMPP handshake, both taken from the 12 June working log.'),
          B('Proof that the official launcher, under Proton, can still log the owner in via the live FXID identity service, validate the 58 GB install, mint a real token, and start the EAC-protected game.'),
          Callout('Where it was stuck', 'The mocks passed standalone tests, but no real client run had ever actually reached them. The remaining question was: what does the live client request first, and why does it never hit the mocks?', AMBER),
          PageBreak()]

# ---- 5 ----
story += [H1('5. This session - root-cause breakthroughs'),
          P('Diffing the failing runs against the 12 June working log resolved the mystery and corrected several assumptions in the original plan.'),
          H2('Finding 1 - the failing run used the wrong command line and a fake token'),
          P('The most recent prior launch used only <font name="Courier">-log --fxid-login-token=&lt;synthetic&gt;</font>. The token was a <b>synthetic</b> one (email <font name="Courier">ww3-local@example.invalid</font>, parsed id 0.0), and three critical arguments were missing. The working June run used:')]
story += Code('''-pref_language english --fxid-login-token=<REAL token>  -NoMrac  -Region=meta.prod.ww3.fxtools.gl:443  -FXGamesInit=1''')
story += [P('So the client never targeted the meta server and never contacted any backend - which is exactly why the mocks stayed silent. (The synthetic token also fails Epic\'s EOS Auth with HTTP 401 <font name="Courier">external.invalid_token</font>, because Epic validates it against the real FXID service.)'),
          H2('Finding 2 - SECRETMS is a dead end'),
          P('The <font name="Courier">-Continent=SECRETMS</font> flag selects a different, Steam-ticket master protocol on <font name="Courier">live.master.worldwar3.com:8443</font> and bypasses the entire REST/Hub/XMPP stack we can emulate. The working June session did <b>not</b> use it. Confirmed: stay on the normal FXID route.'),
          H2('Finding 3 - the master server, not EAC, is the gate'),
          P('EOS <i>Connect</i> (needed by EAC) succeeds offline; only EOS <i>Auth</i> 401s, and that is non-fatal. The real gate to the menu is the meta/master authorisation that yields the profile id and Hub token - the piece our mocks must serve.'),
          PageBreak()]

# ---- 6 ----
story += [H1('6. The DNS / c-ares discovery (why redirects failed)'),
          P('This is the central technical breakthrough of the session and it corrects the original method.'),
          P('When the correctly-armed client finally ran, it connected to the real backend IP <font name="Courier">89.167.42.183:443</font> - <b>not</b> to 127.0.0.1 - even though <font name="Courier">meta.prod.ww3.fxtools.gl</font> was pointed at 127.0.0.1 in <font name="Courier">/etc/hosts</font>. The reason:'),
          Callout('Root cause', 'The game\'s libcurl is built with CURL_VERSION_ASYNCHDNS - it resolves names with the c-ares asynchronous resolver, which queries DNS servers directly and IGNORES /etc/hosts. Every /etc/hosts redirect in the original plan was therefore dead weight; the client always resolved the real public IPs.', RED),
          P('Real DNS shows what the client actually gets:')]
story += Code('''meta.prod.ww3.fxtools.gl  ->  CNAME wlg-gateway.awg.wlg.team
                          ->  89.167.40.140 , 89.167.35.180 , 89.167.42.183   (Hetzner)
xmpp.prod.ww3.fxtools.gl  ->  213.183.62.234    (same host as the Hub)''')
story += [P('This also explains why the Hub was the only service ever reachable in earlier tests: it was the one endpoint with an iptables <b>DNAT</b> rule (by IP), while everything else relied on the ignored hosts file.'),
          H2('The fix - DNAT every real backend IP to the local mocks'),
          ]
story += Code('''# meta / master (all three A-records) -> local HTTPS mock
iptables -t nat -A OUTPUT -d 89.167.40.140 -p tcp --dport 443 -j DNAT --to 127.0.0.1:443
iptables -t nat -A OUTPUT -d 89.167.35.180 -p tcp --dport 443 -j DNAT --to 127.0.0.1:443
iptables -t nat -A OUTPUT -d 89.167.42.183 -p tcp --dport 443 -j DNAT --to 127.0.0.1:443
# XMPP host -> local XMPP mock  (Hub :8705 rule already existed)
iptables -t nat -A OUTPUT -d 213.183.62.234 -p tcp --dport 5222 -j DNAT --to 127.0.0.1:5222
sysctl -w net.ipv4.conf.all.route_localnet=1   # allow DNAT to loopback''')
story += [Callout('Verified working', 'A direct probe to https://89.167.42.183/friends/getAll now returns the mock\'s {"result": []} - proving the real backend IP is transparently redirected to the local server end-to-end.', GREEN),
          PageBreak()]

# ---- 7 ----
story += [H1('7. Launch mechanics &amp; Easy Anti-Cheat'),
          P('Getting the protected game to actually run took some iteration; the findings matter for repeatability.'),
          H2('What does and does not launch the game')]
story.append(DataTable([
    ['Method','Result'],
    ['proton run start_protected_game.exe (after a prefix teardown)','EAC bootstrap exits instantly - does not spawn the game.'],
    ['proton run WW3-Win64-Shipping.exe (direct, bypassing EAC bootstrap)','Engine starts but EAC aborts it in ~60 s; no usable log.'],
    ['Official launcher via Steam -> click LAUNCH','Correct path: EAC bootstraps properly and the game runs with the launcher\'s real args.'],
], [70*mm,101*mm]))
story += [Spacer(1,4*mm),
          P('The official launcher (<font name="Courier">steam://rungameid/674020</font>) logs in via the live FXID service, validates files, and on <b>LAUNCH</b> starts the game through EAC with the correct region arguments. In the last run this reached a live <font name="Courier">GameThread</font> that dialed the real meta IP - the exact behaviour the DNAT fix now captures.'),
          Callout('Lesson', 'Do not tear the Proton prefix down with wineserver -k between attempts - it breaks the EAC bootstrap. Launch through the official launcher and let it drive EAC.', AMBER),
          PageBreak()]

# ---- 8 ----
story += [H1('8. Current system state')]
story.append(DataTable([
    ['Component','State'],
    ['HTTPS mock (meta)','Up on 0.0.0.0:443, live-logging, verified via probe.'],
    ['HTTP mock','Up on 0.0.0.0:80.'],
    ['Hub mock','Up on 0.0.0.0:8705.'],
    ['XMPP mock','Up on 127.0.0.1:5222.'],
    ['DNAT: meta IPs','89.167.40.140 / .35.180 / .42.183 :443 -> 127.0.0.1:443  (NEW, verified).'],
    ['DNAT: Hub','213.183.62.234:8705 -> 127.0.0.1:8705.'],
    ['DNAT: XMPP','213.183.62.234:5222 -> 127.0.0.1:5222  (NEW).'],
    ['route_localnet','Enabled (DNAT-to-loopback works).'],
    ['Official launcher','Running, signed in as OfflinePlayer[STEAM], "Ready to Launch".'],
    ['Live FXID token','Present locally, mode 600, ~7-day validity. Value never exposed.'],
], [45*mm,126*mm]))
story += [Spacer(1,4*mm),
          Callout('Immediate next action', 'Everything backend-side is armed and verified for the first time. The single remaining step is to press LAUNCH so the game runs with the real backend IPs now routed to the mocks - then observe the first meta -> Hub -> XMPP requests and fill in any exact response shapes still needed.', BLUE),
          PageBreak()]

# ---- 9 ----
story += [H1('9. Remaining work to reach Main Menu'),
          B('Launch the game via the official launcher and confirm the meta request now lands on the HTTPS mock (watch the live logs in /tmp/ww3mock).'),
          B('Serve a correct meta / master authorisation response: a WW3 profile id plus a Hub session token, so the client fires SetIsConnectedToMasterServer and opens the Hub WebSocket.'),
          B('Answer the Hub JSON-RPC opening calls (onlineParameters.getParameters, notifications.getNotifications, friends.changeStatus, debug.log) with the exact shapes from the June working log, keeping request ids correlated.'),
          B('Complete the XMPP stream/auth/bind/session/presence handshake for the mapped player id.'),
          B('Confirm the client log transitions InitialMenuState -> MainMenu and the menu is visible.'),
          B('Then run the teardown (remove DNAT rules, stop mocks) to restore the machine to a clean network state.'),
          Spacer(1,6*mm),
          HRFlowable(width='100%', thickness=1, color=LINE, spaceAfter=7),
          P('<b>Expected end state:</b> a visible, interactive Main Menu driven entirely by local mock services, with logs showing the meta bootstrap, Hub RPC exchange and XMPP session against 127.0.0.1 - the discontinued game running again on the owner\'s own machine.'),
          PageBreak()]

# ---- 10 ----
story += [H1('10. Glossary')]
story.append(DataTable([
    ['Term','Meaning'],
    ['FXID','The game\'s identity service (id.fx.gl); issues the signed JWT the client logs in with.'],
    ['Meta / master server','Backend that authorises the session and returns the WW3 profile id + Hub token.'],
    ['Hub','WebSocket JSON-RPC service that drives the menu and lobby (port 8705).'],
    ['EOS','Epic Online Services SDK bundled with the game (Connect + Auth interfaces).'],
    ['EAC','Easy Anti-Cheat; here it runs normally in offline / null-client mode.'],
    ['c-ares','Async DNS resolver compiled into the game\'s libcurl; ignores /etc/hosts.'],
    ['DNAT','iptables destination rewriting - redirects a real backend IP to 127.0.0.1.'],
    ['SECRETMS','An alternate Steam-ticket master protocol (port 8443); deliberately NOT used.'],
    ['Proton','Valve\'s Wine-based compatibility layer that runs the Windows client on Linux.'],
], [34*mm,137*mm]))

doc.build(story)
print('WROTE', OUT)
