from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Oni-Modern-Windows-11-Report.pdf"
VERIFY = ROOT / ".runtime" / "verification"

W, H = 960, 540
BLACK = HexColor("#090909")
PANEL = HexColor("#20242A")
PANEL_2 = HexColor("#272C34")
GOLD = HexColor("#F49A0A")
YELLOW = HexColor("#F6D74F")
CREAM = HexColor("#F7EBCF")
MUTED = HexColor("#CAC5BA")
RULE = HexColor("#D08316")


def register_fonts():
    pdfmetrics.registerFont(TTFont("Georgia", r"C:\Windows\Fonts\georgia.ttf"))
    pdfmetrics.registerFont(TTFont("GeorgiaBold", r"C:\Windows\Fonts\georgiab.ttf"))
    pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
    pdfmetrics.registerFont(TTFont("ArialBold", r"C:\Windows\Fonts\arialbd.ttf"))


def wrap(c, text, font, size, max_width):
    words = text.split()
    lines, line = [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if c.stringWidth(candidate, font, size) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def text_block(c, text, x, y, width, font="Arial", size=15, leading=20, color=CREAM):
    c.setFillColor(color)
    c.setFont(font, size)
    cursor = y
    for paragraph in text.split("\n"):
        for line in wrap(c, paragraph, font, size, width) if paragraph else [""]:
            c.drawString(x, cursor, line)
            cursor -= leading
        cursor -= leading * 0.25
    return cursor


def new_page(c, number, source="OniModern source and local verification, 19 July 2026"):
    c.setFillColor(BLACK)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(YELLOW)
    c.setLineWidth(1.5)
    c.line(32, 478, W - 32, 478)
    c.setFillColor(MUTED)
    c.setFont("Arial", 6.5)
    c.drawString(38, 17, f"Source: {source}")
    c.setFillColor(GOLD)
    c.setFont("ArialBold", 9)
    c.drawRightString(W - 36, 17, f"{number:02d}")


def title(c, value, y=500):
    c.setFillColor(GOLD)
    c.setFont("GeorgiaBold", 28)
    c.drawString(38, y, value)


def image_crop(c, path, crop, x, y, width, height, border=True):
    image = Image.open(path).convert("RGB")
    image = image.crop(crop)
    iw, ih = image.size
    scale = max(width / iw, height / ih)
    render_w, render_h = iw * scale, ih * scale
    left = x + (width - render_w) / 2
    bottom = y + (height - render_h) / 2
    c.saveState()
    clip = c.beginPath()
    clip.rect(x, y, width, height)
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(ImageReader(image), left, bottom, render_w, render_h, mask="auto")
    c.restoreState()
    if border:
        c.setStrokeColor(RULE)
        c.setLineWidth(1.5)
        c.rect(x, y, width, height, fill=0, stroke=1)


def image_contain(c, path, crop, x, y, width, height, border=True):
    image = Image.open(path).convert("RGB").crop(crop)
    iw, ih = image.size
    scale = min(width / iw, height / ih)
    render_w, render_h = iw * scale, ih * scale
    left = x + (width - render_w) / 2
    bottom = y + (height - render_h) / 2
    c.drawImage(ImageReader(image), left, bottom, render_w, render_h, mask="auto")
    if border:
        c.setStrokeColor(RULE)
        c.setLineWidth(1.5)
        c.rect(x, y, width, height, fill=0, stroke=1)


def info_box(c, heading, body, x, y, width, height, stripe=GOLD):
    c.setFillColor(PANEL)
    c.rect(x, y, width, height, fill=1, stroke=0)
    c.setFillColor(stripe)
    c.rect(x, y, 5, height, fill=1, stroke=0)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.rect(x, y, width, height, fill=0, stroke=1)
    c.setFillColor(GOLD)
    c.setFont("GeorgiaBold", 16)
    c.drawString(x + 22, y + height - 28, heading)
    text_block(c, body, x + 22, y + height - 55, width - 42, "Arial", 12, 16, CREAM)


def cover(c):
    c.setFillColor(BLACK)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(YELLOW)
    c.rect(518, 0, 8, H, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("GeorgiaBold", 15)
    c.drawString(48, 485, "ONI MODERN")
    c.setFillColor(CREAM)
    c.setFont("GeorgiaBold", 35)
    for i, line in enumerate(["A MODERN", "WINDOWS", "EDITION FOR A", "2001 CLASSIC"]):
        c.drawString(48, 388 - i * 49, line)
    text_block(
        c,
        "A ready-to-play path for your local retail installation. The launcher handles the profile, controls, display and backup work so you spend less time fiddling and more time playing.",
        50,
        164,
        402,
        "Arial",
        15,
        21,
        MUTED,
    )
    c.setFillColor(YELLOW)
    c.setFont("ArialBold", 8)
    c.drawString(50, 50, "VERSION 1.0  /  PRIVATE LOCAL BUILD AND VERIFICATION REPORT")
    image_contain(c, VERIFY / "oni-main-menu.png", (960, 480, 1600, 960), 528, 108, 432, 324, border=False)


def problem(c):
    new_page(c, 2)
    title(c, "THE GOAL: PLAY, NOT TUNE")
    c.setFillColor(GOLD)
    c.setFont("GeorgiaBold", 17)
    c.drawString(44, 428, "A ONE-TIME SETUP, THEN A DIRECT LAUNCH")
    info_box(c, "SELECT", "Point the launcher at an existing Oni folder. It validates Oni.exe and GameDataFolder before making any change.", 48, 270, 390, 120, YELLOW)
    info_box(c, "PREPARE", "Install the compatible runtime and one managed profile: controls, physical native resolution, borderless mode and a backup in a single flow.", 48, 115, 390, 120, GOLD)
    c.setFillColor(PANEL)
    c.rect(500, 115, 390, 275, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("GeorgiaBold", 19)
    c.drawString(530, 345, "LAUNCH AND PLAY")
    text_block(c, "One button starts the prepared game. No manual DLL copying, configuration hunting or first-run resolution tuning on the normal play path.", 530, 300, 320, "Arial", 14, 20, CREAM)
    c.setFillColor(YELLOW)
    c.setFont("ArialBold", 12)
    c.drawString(530, 180, "ONE PREP. DIRECT LAUNCH.")


def comparison(c):
    new_page(c, 3)
    title(c, "THE PROJECT ADDS A WINDOWS 11 PRODUCT LAYER")
    text_block(c, "The original game remains yours. This project focuses on launch behaviour, modern defaults, reversibility and verification.", 40, 452, 850, "Arial", 12, 17, MUTED)
    rows = [
        ("Retail Oni installation", "Oni Modern local setup"),
        ("Manual folders and settings", "Validate selected game folder before changes"),
        ("Classic input configuration", "WASD, mouse aim, Shift sprint and common FPS binds"),
        ("Legacy display preferences", "Physical native primary-display resolution in persist.dat"),
        ("Window mode can be fragile", "Borderless profile with Alt+Tab enabled"),
        ("Edits are hard to undo", "Timestamped backup of every managed file"),
        ("Manual runtime file copying", "Filtered runtime deployment with archive-path safety checks"),
        ("No project verification", "Automated tests, clean build and live launch check"),
    ]
    x, y, width, row_h = 40, 76, 880, 39
    c.setFillColor(HexColor("#C76408"))
    c.rect(x, y + row_h * 8, width, row_h, fill=1, stroke=0)
    c.setFillColor(CREAM)
    c.setFont("GeorgiaBold", 13)
    c.drawCentredString(x + width * 0.25, y + row_h * 8 + 13, "RETAIL BASELINE")
    c.drawCentredString(x + width * 0.75, y + row_h * 8 + 13, "ONI MODERN")
    for index, (left, right) in enumerate(rows):
        yy = y + row_h * (7 - index)
        c.setFillColor(PANEL_2 if index % 2 == 0 else PANEL)
        c.rect(x, yy, width, row_h, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#7B541D"))
        c.setLineWidth(0.5)
        c.rect(x, yy, width, row_h, fill=0, stroke=1)
        c.line(x + width / 2, yy, x + width / 2, yy + row_h)
        c.setFillColor(CREAM)
        c.setFont("Arial", 11)
        c.drawString(x + 16, yy + 13, left)
        c.drawString(x + width / 2 + 16, yy + 13, right)


def controls(c):
    new_page(c, 4)
    title(c, "MODERN FPS CONTROLS ARE THE DEFAULT")
    c.setFillColor(GOLD)
    c.setFont("GeorgiaBold", 17)
    c.drawString(44, 422, "MODERN BY DEFAULT")
    entries = [
        ("MOVE / LOOK", "WASD / mouse"),
        ("PRIMARY / SECONDARY", "Left mouse / right mouse"),
        ("JUMP / CROUCH", "Space / Ctrl"),
        ("RUN / USE", "Shift / E"),
        ("WEAPONS / HYPO", "Q, R, G / Tab"),
        ("MELEE / VIEW", "F, C / V"),
    ]
    x, y = 48, 374
    for label, value in entries:
        c.setFillColor(GOLD)
        c.setFont("ArialBold", 11)
        c.drawString(x, y, label)
        c.setFillColor(CREAM)
        c.setFont("Arial", 14)
        c.drawString(x + 190, y, value)
        y -= 42
    info_box(c, "PRESERVED", "The launcher writes a clear key_config.txt profile. The original game remains playable with the profile files backed up before changes.", 500, 270, 370, 126, YELLOW)
    image_contain(c, VERIFY / "oni-main-menu.png", (960, 480, 1600, 960), 505, 85, 360, 155)


def native_display(c):
    new_page(c, 5)
    title(c, "NATIVE BORDERLESS FULLSCREEN BY DEFAULT")
    info_box(c, "DEFAULT", "Primary monitor, physical desktop pixel count and borderless fullscreen.", 40, 335, 330, 110, YELLOW)
    info_box(c, "DPI AWARE", "Windows scaling is accounted for. A logical 1920x1080 desktop correctly resolved to a physical 2560x1440 panel.", 40, 195, 330, 110, GOLD)
    info_box(c, "RECOVERY", "Alt+Tab is enabled and the managed profile is backed up before it is replaced.", 40, 55, 330, 110, YELLOW)
    image_crop(c, VERIFY / "gameplay-running.png", (960, 480, 1600, 960), 408, 62, 512, 383)
    c.setFillColor(MUTED)
    c.setFont("Arial", 8)
    c.drawString(410, 45, "Verification capture: Oni running from the managed native-borderless configuration.")


def safety(c):
    new_page(c, 6)
    title(c, "REVERSIBLE CHANGES, SAFER LOCAL SETUP")
    cards = [
        ("VALIDATE", "Require Oni.exe and GameDataFolder before a profile or runtime action can proceed."),
        ("BACK UP", "Create a timestamped profile backup containing executable, runtime, configuration, controls and preferences."),
        ("DEPLOY", "Install only filtered runtime entries and reject archive paths that escape the selected game folder."),
        ("LAUNCH", "Start Oni only after the selected path passes installation validation."),
    ]
    positions = [(48, 292), (503, 292), (48, 108), (503, 108)]
    for (heading, body), (x, y) in zip(cards, positions):
        info_box(c, heading, body, x, y, 405, 135, YELLOW if x == 48 else GOLD)


def verification(c):
    new_page(c, 7)
    title(c, "SOURCES, PROVENANCE AND LICENSING")
    text_block(c, "This is a private local modernization report, not legal advice. The project does not redistribute Oni game files, extracted assets, a patched game folder or the upstream runtime archive.", 40, 450, 860, "Arial", 11, 15, MUTED)
    rows = [
        ("ONI MODERN", "Original local launcher and profile code for this private project. No game assets are included."),
        ("DAODAN DLL / FPSDAODAN", "Used privately as the modern runtime. Sources: wiki.oni2.net/Daodan_DLL and mods.oni2.net/system/files/DaodanDLL.zip. The archive carries a BSD-style ODE notice at fps/ode_license.txt only; no archive-wide redistribution license was found."),
        ("ORIGINAL ONI", "Your local retail game installation. Proprietary game executable, media and assets remain private and are not bundled or redistributed."),
        ("ONISPLIT - RESEARCH ONLY", "Reviewed for provenance only; no source or binary is used by this build. Source: websvn.illy.bz/browse/Oni2/OniSplit/. The 2026-07-19 snapshot showed Copyright (c) 2007-2014 Neo and no explicit reuse license; treat as all-rights-reserved pending permission."),
    ]
    y = 335
    for index, (heading, body) in enumerate(rows):
        height = 68 if index != 1 else 88
        c.setFillColor(PANEL_2 if index % 2 == 0 else PANEL)
        c.rect(40, y, 880, height, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#7B541D"))
        c.setLineWidth(0.6)
        c.rect(40, y, 880, height, fill=0, stroke=1)
        c.setFillColor(GOLD)
        c.setFont("ArialBold", 9)
        c.drawString(58, y + height - 19, heading)
        text_block(c, body, 220, y + height - 18, 675, "Arial", 8.5, 11, CREAM)
        y -= height + 8


def outcome(c):
    c.setFillColor(BLACK)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(YELLOW)
    c.rect(580, 0, 8, H, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("GeorgiaBold", 15)
    c.drawString(48, 485, "OUTCOME")
    c.setFillColor(CREAM)
    c.setFont("GeorgiaBold", 34)
    for i, line in enumerate(["READY TO LAUNCH -", "NOT JUST READY TO", "COMPILE."]):
        c.drawString(48, 385 - i * 48, line)
    text_block(c, "Modern controls, native borderless display and a reversible local setup - ready to play on your Windows 11 desktop.", 50, 170, 435, "Arial", 15, 21, MUTED)
    c.setFillColor(PANEL)
    c.rect(40, 27, 490, 80, fill=1, stroke=0)
    c.setStrokeColor(RULE)
    c.setLineWidth(1)
    c.rect(40, 27, 490, 80, fill=0, stroke=1)
    c.setFillColor(YELLOW)
    c.setFont("ArialBold", 10)
    c.drawString(64, 79, "ONI MODERN")
    c.setFillColor(CREAM)
    c.setFont("Arial", 10)
    c.drawString(64, 55, "Local Windows 11 compatibility launcher and profile")
    image_crop(c, VERIFY / "gameplay-running.png", (900, 420, 1660, 1010), 588, 0, 372, H, border=False)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    register_fonts()
    c = canvas.Canvas(str(OUTPUT), pagesize=(W, H), pageCompression=1)
    c.setTitle("Oni Modern - Windows 11 Report")
    c.setAuthor("Oni Modern")
    for page in (cover, problem, comparison, controls, native_display, safety, verification, outcome):
        page(c)
        c.showPage()
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
