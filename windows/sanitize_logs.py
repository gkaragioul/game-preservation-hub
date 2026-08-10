#!/usr/bin/env python3
r"""
sanitize_logs.py -- make WW3 capture logs safe to share publicly.

Redacts the things that identify YOUR account or leak secrets, while leaving the
protocol structure (RPC methods, paths, message shapes) intact so the capture is
still useful/interesting to a community.

Redacts:
  * Steam ID64            (17-digit 7656119xxxxxxxxxx)  -> STEAMID
  * JWTs                  (eyJ....eyJ....sig)           -> JWT
  * Bearer / auth tokens                                -> REDACTED
  * "token"/"accessToken"/"refreshToken"/... JSON fields -> "REDACTED"
  * Email addresses                                     -> email@redacted
  * XMPP session tokens   (V2:WW3:::<32 hex>)           -> V2:WW3:::REDACTED
  * mygamesid / soc id long numbers in token payloads   -> ID

Usage:
  # sanitize specific files:
  python sanitize_logs.py "C:\Users\Player\Desktop\WW3_rec_meta.prod...log"
  # or sanitize every WW3_rec_*.log on the Desktop:
  python sanitize_logs.py

Outputs a sibling file "<name>.SHAREABLE.log" for each input. Never overwrites originals.
"""
import re, sys, os, glob

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")

RULES = [
    # JWTs first (before generic long-number rules)
    (re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"), "JWT_REDACTED"),
    # Steam ID64
    (re.compile(r"\b7656119\d{10}\b"), "STEAMID_REDACTED"),
    # token-ish JSON fields: "accessToken":"..." etc.
    (re.compile(r'("(?:access|refresh|session|auth|id)?[Tt]oken|jwt|secret|apiKey)"\s*:\s*"[^"]*"'),
     r'\1":"REDACTED"'),
    # Authorization: Bearer xxxxx  /  bearer xxxxx
    (re.compile(r"([Bb]earer)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 REDACTED"),
    # emails
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "email@redacted"),
    # XMPP resource session token
    (re.compile(r"V2:WW3:::[0-9A-Fa-f]{16,}"), "V2:WW3:::REDACTED"),
    # mygamesid / soc ids inside token payloads
    (re.compile(r'("mygamesid"\s*:\s*")\d+(")'), r"\1REDACTED\2"),
    # in-game identity: player display name + xmpp username (prod-<id>)
    (re.compile(r'("playerName"\s*:\s*")[^"]*(")'), r"\1PLAYER\2"),
    (re.compile(r'("(?:playerName|displayName|nickname|userName)"\s*:\s*")[^"]*(")'), r"\1PLAYER\2"),
    (re.compile(r"\bprod-\d{4,}\b"), "prod-PLAYER"),
]

def sanitize_text(text):
    counts = {}
    for rx, repl in RULES:
        text, n = rx.subn(repl, text)
        if n:
            counts[repl if isinstance(repl, str) else "field"] = counts.get(repl if isinstance(repl, str) else "field", 0) + n
    return text, counts

def main():
    targets = sys.argv[1:] or glob.glob(os.path.join(DESKTOP, "WW3_rec_*.log"))
    targets = [t for t in targets if not t.endswith(".SHAREABLE.log")]
    if not targets:
        print("No logs found. Pass file paths, or put WW3_rec_*.log on your Desktop.")
        return
    for path in targets:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            print(f"! skip {path}: {e}")
            continue
        clean, counts = sanitize_text(text)
        out = os.path.splitext(path)[0] + ".SHAREABLE.log"
        with open(out, "w", encoding="utf-8") as f:
            f.write(clean)
        summary = ", ".join(f"{k}:{v}" for k, v in counts.items()) or "nothing matched"
        print(f"[OK] {os.path.basename(out)}   (redacted: {summary})")
    print("\nShare the .SHAREABLE.log files. Keep the originals private.")

if __name__ == "__main__":
    main()
