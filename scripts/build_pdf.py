#!/usr/bin/env python3
"""Build per-module PDFs (cached) and merge them into the final guide.

  build_pdf.py module --ws W --slug S      build W/build/S.pdf unless unchanged
  build_pdf.py final  --ws W               merge cover + contents + modules -> W/final/user-guide.pdf
                                           and W/final/guide.html (GIFs inline)

A module is rebuilt only if its JSON, the images it uses, common.json or this
script changed. Hash is stored beside the PDF in build/S.hash.
"""
import argparse, hashlib, html, io, json, os, re, sys, tempfile, time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram import flow_png
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (CondPageBreak, Image as RLImage, KeepTogether, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

import theme as _theme
_T = _theme.tokens()
ACCENT = colors.HexColor(_T["signal"])
INK = colors.HexColor(_T["ink"])
MUTED = colors.HexColor(_T["ash"])
BONE = colors.HexColor(_T["bone"])
PAPER = colors.HexColor(_T["paper"])
RULE = colors.HexColor("#D9D9DA")     # ink at about 12% on white
TIP_BG = BONE
MARGIN = 18 * mm
FRAME_W = A4[0] - 2 * MARGIN
MAX_IMG_H = 105 * mm

FONT, FONT_B, FONT_XB, FONT_EXT = "Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Helvetica"
try:
    for name, weight in (("PJS", "regular"), ("PJS-SemiBold", "semibold"), ("PJS-Bold", "bold"),
                         ("PJS-ExtraBold", "extrabold"), ("PJS-Ext", "ext-regular")):
        p = _theme.font_path(weight)
        if p and "PlusJakarta" in p:
            pdfmetrics.registerFont(TTFont(name, p))
    pdfmetrics.registerFontFamily("PJS", normal="PJS", bold="PJS-Bold", italic="PJS", boldItalic="PJS-Bold")
    FONT, FONT_B, FONT_XB, FONT_EXT = "PJS", "PJS-Bold", "PJS-ExtraBold", "PJS-Ext"
except Exception:
    for reg, bold in [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]:
        if os.path.exists(reg) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("GuideSans", reg))
            pdfmetrics.registerFont(TTFont("GuideSans-Bold", bold))
            pdfmetrics.registerFontFamily("GuideSans", normal="GuideSans", bold="GuideSans-Bold")
            FONT, FONT_B, FONT_XB, FONT_EXT = "GuideSans", "GuideSans-Bold", "GuideSans-Bold", "GuideSans"

S = {
    "h1": ParagraphStyle("h1", fontName=FONT_XB, fontSize=22, leading=27, textColor=INK, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName=FONT_B, fontSize=14, leading=18, textColor=INK, spaceBefore=12, spaceAfter=3),
    "body": ParagraphStyle("body", fontName=FONT, fontSize=10, leading=14.5, textColor=INK, alignment=TA_LEFT),
    "muted": ParagraphStyle("muted", fontName=FONT, fontSize=9.5, leading=13, textColor=MUTED),
    "step": ParagraphStyle("step", fontName=FONT, fontSize=10.5, leading=15, textColor=INK),
    "h3": ParagraphStyle("h3", fontName=FONT_B, fontSize=11, leading=15, textColor=INK, spaceBefore=8, spaceAfter=3),
    "tip": ParagraphStyle("tip", fontName=FONT, fontSize=9.5, leading=13, textColor=INK),
}


def md(text):
    """Escape, then turn **bold** into <b>."""
    t = html.escape(text or "")
    t = t.replace("\u20b9", f'<font name="{FONT_EXT}">\u20b9</font>').replace("\u2192", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def sha_files(h, paths):
    for p in paths:
        if p and os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())


def apply_brand(ws, state):
    """Palette is fixed; only the accent can be replaced per project."""
    global ACCENT
    tk = _theme.tokens(state)
    ACCENT = colors.HexColor(tk["accent"])


def load_common(ws, state):
    with open(os.path.join(ws, "common.json")) as f:
        return json.load(f)


def resolve_step(step, common, ws, state):
    """Merge a `common` reference into the step. Own fields win."""
    if "common" not in step:
        return step
    base = dict(common.get(step["common"], {}))
    shot = state.get("shots", {}).get(step["common"])
    if shot and "image" not in base:
        base["image"] = shot
    base.update({k: v for k, v in step.items() if k != "common"})
    if "text" not in base:
        base["text"] = f"(missing common step '{step['common']}')"
    return base


def load_state(ws):
    with open(os.path.join(ws, "state.json")) as f:
        return json.load(f)


def step_image(step, ws):
    p = step.get("annotated") or step.get("image")
    if not p:
        return None
    p = p if os.path.isabs(p) else os.path.join(ws, p)
    return p if os.path.exists(p) else None


def fit_image(path, max_w, max_h):
    with Image.open(path) as im:
        w, h = im.size
    r = min(max_w / w, max_h / h)
    return RLImage(path, width=w * r, height=h * r)


def step_block(n, step, ws):
    badge = Paragraph(f'<font color="#FFFFFF"><b>{n}</b></font>',
                      ParagraphStyle("b", fontName=FONT_B, fontSize=10, alignment=1, leading=12))
    row = Table([[badge, Paragraph(md(step["text"]), S["step"])]], colWidths=[7 * mm, FRAME_W - 7 * mm])
    row.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), ACCENT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                             ("LEFTPADDING", (1, 0), (1, 0), 8), ("TOPPADDING", (0, 0), (-1, -1), 3),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    parts = [row, Spacer(1, 2 * mm)]
    img = step_image(step, ws)
    if img:
        parts.append(fit_image(img, FRAME_W, MAX_IMG_H))
        parts.append(Spacer(1, 1.5 * mm))
    if step.get("warning"):
        wbox = Table([[Paragraph("<b>Careful.</b> " + md(step["warning"]), S["tip"])]], colWidths=[FRAME_W])
        wbox.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDECEA")),
                                  ("LINEBEFORE", (0, 0), (0, 0), 3, colors.HexColor("#C0392B")),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        parts += [wbox, Spacer(1, 1.5 * mm)]
    if step.get("tip"):
        t = Table([[Paragraph("<b>Tip.</b> " + md(step["tip"]), S["tip"])]], colWidths=[FRAME_W])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TIP_BG), ("LINEBEFORE", (0, 0), (0, 0), 3, ACCENT), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        parts += [t, Spacer(1, 1.5 * mm)]
    parts.append(Spacer(1, 4 * mm))
    return KeepTogether(parts)


def accent_hex():
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in (ACCENT.red, ACCENT.green, ACCENT.blue))


def workflow_table(flow):
    cell = S["tip"]
    rows = [[Paragraph("<b>#</b>", cell), Paragraph("<b>What to do</b>", cell),
             Paragraph("<b>Where</b>", cell), Paragraph("<b>Note</b>", cell)]]
    for i, f_ in enumerate(flow, 1):
        rows.append([Paragraph(str(i), cell), Paragraph(md(f_.get("label", "")), cell),
                     Paragraph(md(f_.get("where", "")), cell), Paragraph(md(f_.get("note", "")), cell)])
    t = Table(rows, colWidths=[FRAME_W * 0.07, FRAME_W * 0.30, FRAME_W * 0.30, FRAME_W * 0.33], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BONE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def fields_table(fields):
    cell = S["tip"]
    head = [Paragraph("<b>Field</b>", cell), Paragraph("<b>Required?</b>", cell),
            Paragraph("<b>What to enter</b>", cell), Paragraph("<b>Example</b>", cell)]
    rows = [head]
    for f_ in fields:
        req = bool(f_.get("required"))
        tag = (f'<font color="{ACCENT.hexval().replace("0x", "#")}"><b>Required</b></font>' if req
               else '<font color="#6B7280">Optional</font>')
        rows.append([Paragraph(md(f_.get("name", "")), cell), Paragraph(tag, cell),
                     Paragraph(md(f_.get("help", "")), cell), Paragraph(md(f_.get("example", "")), cell)])
    t = Table(rows, colWidths=[FRAME_W * 0.24, FRAME_W * 0.14, FRAME_W * 0.38, FRAME_W * 0.24], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BONE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def _slug(t):
    s = re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")
    return s or "section"


def watch_box(feat, mod_slug, state):
    """A PDF cannot play a GIF. When the help site has a public address, show a link and a QR code
    to the recording there. Without an address, show nothing (a local file path helps nobody)."""
    base = ((state.get("brand") or {}).get("site_url") or "").rstrip("/")
    if not feat.get("gif") or not base:
        return []
    url = f"{base}/{mod_slug}.html#{_slug(feat.get('help_key') or feat['title'])}"
    text = Paragraph(f'<b>Watch this as a short video</b><br/><font color="{accent_hex()}"><u><a href="{html.escape(url)}">{html.escape(url)}</a></u></font>', S["tip"])
    cell = ""
    try:
        import qrcode
        q = qrcode.QRCode(box_size=6, border=1)
        q.add_data(url)
        q.make(fit=True)
        img = q.make_image(fill_color="#231F20", back_color="#FFFFFF").convert("RGB")
        qp = os.path.join(tempfile.gettempdir(), f"dy-qr-{hashlib.sha1(url.encode()).hexdigest()[:10]}.png")
        img.save(qp)
        cell = RLImage(qp, width=20 * mm, height=20 * mm)
    except Exception:
        pass
    t = Table([[text, cell]], colWidths=[FRAME_W - 24 * mm, 24 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TIP_BG), ("LINEBEFORE", (0, 0), (0, 0), 3, ACCENT),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [t, Spacer(1, 3 * mm)]


def before_lines(feat):
    """Rows for the 'Before you start' box: [(label, text)]. Empty when the feature has none."""
    b = feat.get("before") or {}
    rows = []
    if b.get("menu"):
        rows.append(("Where", b["menu"]))
    if b.get("role"):
        rows.append(("Who can do this", b["role"]))
    if b.get("ready"):
        rows.append(("Have ready", ", ".join(b["ready"]) if isinstance(b["ready"], list) else b["ready"]))
    return rows


def before_box(feat):
    rows = before_lines(feat)
    if not rows:
        return []
    data = [[Paragraph("<b>Before you start</b>", S["tip"]), ""]] + [
        [Paragraph(f"<b>{html.escape(a)}</b>", S["tip"]), Paragraph(md(b), S["tip"])] for a, b in rows]
    t = Table(data, colWidths=[34 * mm, FRAME_W - 34 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TIP_BG), ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                           ("SPAN", (0, 0), (1, 0)), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return [t, Spacer(1, 3 * mm)]


def feature_fields(feat):
    if not feat.get("fields"):
        return []
    return [Paragraph("Fields on this screen", S["h3"]), fields_table(feat["fields"]), Spacer(1, 4 * mm)]


def cheatsheet_table(rows_in):
    cell = S["tip"]
    rows = [[Paragraph("<b>I want to&hellip;</b>", cell), Paragraph("<b>Go to</b>", cell)]]
    for r_ in rows_in:
        rows.append([Paragraph(md(r_.get("want", "")), cell), Paragraph(md(r_.get("go", "")), cell)])
    t = Table(rows, colWidths=[FRAME_W * 0.5, FRAME_W * 0.5], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BONE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def problems_table(probs):
    cell = S["tip"]
    rows = [[Paragraph("<b>You see</b>", cell), Paragraph("<b>Why it happens</b>", cell), Paragraph("<b>What to do</b>", cell)]]
    for p_ in probs:
        rows.append([Paragraph(md(p_.get("message", "")), cell), Paragraph(md(p_.get("cause", "")), cell),
                     Paragraph(md(p_.get("fix", "")), cell)])
    t = Table(rows, colWidths=[FRAME_W * 0.34, FRAME_W * 0.30, FRAME_W * 0.36], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), TIP_BG), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def module_hash(ws, mod, common, state):
    h = hashlib.sha1()
    h.update(json.dumps(mod, sort_keys=True).encode())
    h.update(json.dumps(common, sort_keys=True).encode())
    h.update(json.dumps(state.get("shots", {}), sort_keys=True).encode())
    h.update(str((state.get("brand") or {}).get("site_url")).encode())
    h.update(open(__file__, "rb").read())
    imgs = []
    for feat in mod.get("features", []):
        for st in feat.get("steps", []):
            st = resolve_step(st, common, ws, state)
            p = step_image(st, ws)
            imgs.append(p)
    sha_files(h, sorted(set(x for x in imgs if x)))
    return h.hexdigest()


def build_module(ws, slug, force=False):
    state = load_state(ws)
    apply_brand(ws, state)
    common = load_common(ws, state)
    mp = os.path.join(ws, "modules", f"{slug}.json")
    with open(mp) as f:
        mod = json.load(f)
    for feat in mod.get("features", []):
        for st in feat.get("steps", []):
            if st.get("stale"):
                sys.exit(f"{slug}: step '{st.get('text','')[:40]}' is stale (UI changed). Re-capture it, then run check_changes.py set-fp to clear the flag")
            if (st.get("marks") or st.get("crop")) and not st.get("annotated"):
                sys.exit(f"{slug}: step '{st.get('text','')[:40]}' has marks but no annotated image; run annotate.py first")
    out = os.path.join(ws, "build", f"{slug}.pdf")
    hp =os.path.join(ws, "build", f"{slug}.hash")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    hv = module_hash(ws, mod, common, state)
    tp = os.path.join(ws, "build", f"{slug}.toc.json")
    if not force and os.path.exists(out) and os.path.exists(tp) and os.path.exists(hp) and open(hp).read() == hv:
        print(f"{slug}: unchanged, cached")
        return out
    story = [Paragraph(md(mod.get("title", slug)), S["h1"])]
    if mod.get("intro"):
        story += [Paragraph(md(mod["intro"]), S["muted"]), Spacer(1, 3 * mm)]
    if mod.get("cheatsheet"):
        story += [cheatsheet_table(mod["cheatsheet"]), Spacer(1, 4 * mm)]
    for feat in mod.get("features", []):
        hp_ = Paragraph(md(feat["title"]), S["h2"])
        hp_._feat = feat["title"]  # afterFlowable sees this once KeepTogether is unpacked
        head = [hp_]
        if feat.get("goal"):
            head.append(Paragraph(md(feat["goal"]), S["muted"]))
        head.append(Spacer(1, 2 * mm))
        head += watch_box(feat, slug, state)
        head += before_box(feat)
        steps = [resolve_step(s, common, ws, state) for s in feat.get("steps", [])]
        if not steps:
            story += head + feature_fields(feat)
            continue
        first = step_block(1, steps[0], ws)
        story.append(KeepTogether(head + first._content))
        for i, st in enumerate(steps[1:], 2):
            story.append(step_block(i, st, ws))
        story += feature_fields(feat)
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN + 4 * mm, title=mod.get("title", slug))
    for wf in mod.get("workflows") or []:
        wh = Paragraph(md(wf["title"]), S["h2"])
        wh._feat = wf["title"]
        story += [CondPageBreak(95 * mm), wh]
        if wf.get("goal"):
            story.append(Paragraph(md(wf["goal"]), S["muted"]))
        story += [Spacer(1, 2 * mm), fit_image(flow_png(ws, wf, accent_hex()), FRAME_W, 90 * mm), Spacer(1, 3 * mm),
                  workflow_table(wf.get("flow", [])), Spacer(1, 5 * mm)]
    probs = mod.get("problems") or []
    if probs:
        ph = Paragraph("Common problems", S["h2"])
        ph._feat = "Common problems"
        story += [CondPageBreak(50 * mm), ph, Spacer(1, 2 * mm)]
        story.append(problems_table(probs))
    feats = []

    def after(fl):
        if getattr(fl, "_feat", None):
            feats.append({"title": fl._feat, "page": doc.page})
    doc.afterFlowable = after
    doc.build(story)
    with open(tp, "w") as f:
        json.dump(feats, f)
    with open(hp, "w") as f:
        f.write(hv)
    print(f"{slug}: built ({len(PdfReader(out).pages)} pages)")
    return out


def cover_pdf(state):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    c.setFillColor(ACCENT)
    c.rect(0, H - 14 * mm, W, 14 * mm, fill=1, stroke=0)
    logo = (state.get("brand") or {}).get("logo")
    if logo and os.path.exists(logo):
        with Image.open(logo) as li:
            lw, lh = li.size
        r = min(60 * mm / lw, 22 * mm / lh)
        c.drawImage(logo, MARGIN, H * 0.58 + 22 * mm, width=lw * r, height=lh * r, mask="auto")
    c.setFillColor(INK)
    c.setFont(FONT_XB, 34)
    c.drawString(MARGIN, H * 0.58, f"{state['app']}")
    c.setFont(FONT, 20)
    c.drawString(MARGIN, H * 0.58 - 14 * mm, "User guide")
    c.setFillColor(MUTED)
    c.setFont(FONT, 11)
    c.drawString(MARGIN, H * 0.58 - 28 * mm, time.strftime("%d %B %Y"))
    if state.get("url"):
        c.drawString(MARGIN, H * 0.58 - 35 * mm, state["url"])
    c.setFillColor(ACCENT)
    c.circle(W - MARGIN - 12 * mm, 40 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(FONT_B, 14)
    c.drawCentredString(W - MARGIN - 12 * mm, 40 * mm - 5, "1")
    c.setFillColor(MUTED)
    c.setFont(FONT, 9.5)
    c.drawRightString(W - MARGIN - 24 * mm, 39 * mm, "Numbered marks show where to click.")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


PER_TOC_PAGE = 38


def toc_pdf(entries):
    """entries: [(title, page_number, level)] -> PDF bytes with possibly several pages."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    chunks = [entries[i:i + PER_TOC_PAGE] for i in range(0, len(entries), PER_TOC_PAGE)] or [[]]
    for ci, chunk in enumerate(chunks):
        c.setFillColor(INK)
        c.setFont(FONT_B, 20)
        c.drawString(MARGIN, H - MARGIN - 8 * mm, "Contents" if ci == 0 else "Contents (continued)")
        y = H - MARGIN - 22 * mm
        for title, pg, lvl in chunk:
            fnt, sz, ind = (FONT_B, 11, 0) if lvl == 0 else (FONT, 10, 7 * mm)
            c.setFont(fnt, sz)
            c.setFillColor(INK if lvl == 0 else MUTED)
            c.drawString(MARGIN + ind, y, title)
            c.drawRightString(W - MARGIN, y, str(pg))
            tw = pdfmetrics.stringWidth(title, fnt, sz)
            c.setStrokeColor(RULE)
            c.setDash(1, 3)
            c.line(MARGIN + ind + tw + 6, y + 2, W - MARGIN - 20, y + 2)
            c.setDash()
            y -= 6.4 * mm
        c.showPage()
    c.save()
    buf.seek(0)
    return buf, len(chunks)


def footer_overlay(n_pages, first_numbered):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(n_pages):
        if i >= first_numbered:
            c.setFont(FONT, 8.5)
            c.setFillColor(MUTED)
            c.drawCentredString(A4[0] / 2, 9 * mm, f"Page {i + 1}")
        c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def build_final(ws):
    state = load_state(ws)
    apply_brand(ws, state)
    ready = [s for s in state["order"] if state["modules"][s]["status"] == "built"]
    ready.sort(key=lambda s: {"quick-start": 0, "workflows": 1}.get(s, 2))  # "Start here" and workflows come first
    if not ready:
        sys.exit("no built modules yet")
    mod_pdfs = []
    for s in ready:
        p = os.path.join(ws, "build", f"{s}.pdf")
        if not os.path.exists(p):
            sys.exit(f"missing {p}; run build_pdf.py module --slug {s}")
        mod_pdfs.append((s, p))
    counts = [len(PdfReader(p).pages) for _, p in mod_pdfs]
    ftoc = {}
    for s, _ in mod_pdfs:
        tp = os.path.join(ws, "build", f"{s}.toc.json")
        ftoc[s] = json.load(open(tp)) if os.path.exists(tp) else []
    n_entries = len(ready) + sum(len(v) for v in ftoc.values())
    _, toc_pages = toc_pdf([("x", 1, 0)] * n_entries)
    start = 1 + toc_pages + 1
    entries, outline, page = [], [], start
    for (s, _), n in zip(mod_pdfs, counts):
        title = state["modules"][s]["title"]
        entries.append((title, page, 0))
        outline.append((title, page, 0, None))
        for ft in ftoc[s]:
            entries.append((ft["title"], page + ft["page"] - 1, 1))
        page += n
    toc_buf, _ = toc_pdf(entries)
    w = PdfWriter()
    for r in (PdfReader(cover_pdf(state)), PdfReader(toc_buf)):
        for pg in r.pages:
            w.add_page(pg)
    for (s, p) in mod_pdfs:
        before = len(w.pages)
        for pg_obj in PdfReader(p).pages:
            w.add_page(pg_obj)
        parent = w.add_outline_item(state["modules"][s]["title"], before)
        for ft in ftoc[s]:
            w.add_outline_item(ft["title"], before + ft["page"] - 1, parent=parent)
    overlay = footer_overlay(len(w.pages), 1)
    for i, pg in enumerate(w.pages):
        pg.merge_page(overlay.pages[i])
    os.makedirs(os.path.join(ws, "final"), exist_ok=True)
    out = os.path.join(ws, "final", "user-guide.pdf")
    with open(out, "wb") as f:
        w.write(f)
    print(f"{out}: {len(w.pages)} pages, {len(ready)} modules")
    build_html(ws, state, ready)
    return out


def build_html(ws, state, ready):
    """Companion page that shows GIFs inline (PDF cannot animate)."""
    common = load_common(ws, state)
    parts = [f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             f"<title>{html.escape(state['app'])} user guide</title>"
             "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:24px 16px;color:#231F20;background:#F2F7F9}"
             "h1{font-size:28px}h2{margin-top:40px;border-bottom:1px solid #d9d9da;padding-bottom:4px}h3{margin-top:28px}"
             "img{max-width:100%;border:1px solid #d9d9da}.n{display:inline-block;background:#1C75BC;color:#fff;"
             "border-radius:50%;width:1.6em;height:1.6em;text-align:center;line-height:1.6em;margin-right:8px;font-weight:700}"
             ".tip{background:#D6E7F1;padding:8px 12px}.warn{background:#fdecea;border-left:4px solid #c0392b;padding:8px 12px}table.t{border-collapse:collapse;width:100%;margin:12px 0}table.t th{background:#D6E7F1;text-align:left}table.t td,table.t th{padding:6px 8px;border-bottom:1px solid #d9d9da;vertical-align:top}li{margin:18px 0;list-style:none}ol{padding:0}</style>",
             f"<h1>{html.escape(state['app'])} user guide</h1>"]
    for s in ready:
        with open(os.path.join(ws, "modules", f"{s}.json")) as f:
            mod = json.load(f)
        parts.append(f"<h2>{html.escape(mod.get('title', s))}</h2>")
        if mod.get("intro"):
            parts.append(f"<p>{html.escape(mod['intro'])}</p>")
        if mod.get("cheatsheet"):
            parts.append("<table class=t><tr><th>I want to&hellip;<th>Go to</tr>" + "".join(
                f"<tr><td>{md(r_.get('want',''))}<td>{md(r_.get('go',''))}</tr>" for r_ in mod["cheatsheet"]) + "</table>")
        for feat in mod.get("features", []):
            parts.append(f"<h3>{html.escape(feat['title'])}</h3>")
            if feat.get("goal"):
                parts.append(f"<p>{html.escape(feat['goal'])}</p>")
            if feat.get("gif") and os.path.exists(os.path.join(ws, feat["gif"])):
                parts.append(f"<p><img src='../{html.escape(feat['gif'])}' alt='animated walkthrough'></p>")
            bl = before_lines(feat)
            if bl:
                parts.append("<div class=tip><b>Before you start</b><br>" + "<br>".join(f"<b>{html.escape(a)}:</b> {md(b)}" for a, b in bl) + "</div>")
            parts.append("<ol>")
            for i, st in enumerate(feat.get("steps", []), 1):
                st = resolve_step(st, common, ws, state)
                parts.append(f"<li><span class=n>{i}</span>{md(st['text'])}")
                img = step_image(st, ws)
                if img:
                    parts.append(f"<br><img src='../{html.escape(os.path.relpath(img, ws))}'>")
                if st.get("warning"):
                    parts.append(f"<p class=warn><b>Careful.</b> {md(st['warning'])}</p>")
                if st.get("tip"):
                    parts.append(f"<p class=tip><b>Tip.</b> {md(st['tip'])}</p>")
                parts.append("</li>")
            parts.append("</ol>")
            if feat.get("fields"):
                parts.append("<h4>Fields on this screen</h4><table class=t><tr><th>Field<th>Required?<th>What to enter<th>Example</tr>" + "".join(
                    f"<tr><td>{md(f_.get('name',''))}<td>{'<b>Required</b>' if f_.get('required') else 'Optional'}"
                    f"<td>{md(f_.get('help',''))}<td>{md(f_.get('example',''))}</tr>" for f_ in feat["fields"]) + "</table>")
        for wf in mod.get("workflows") or []:
            png = flow_png(ws, wf, accent_hex())
            parts.append(f"<h3>{html.escape(wf['title'])}</h3>")
            if wf.get("goal"):
                parts.append(f"<p>{html.escape(wf['goal'])}</p>")
            parts.append(f"<p><img src='../{html.escape(os.path.relpath(png, ws))}' alt='workflow diagram'></p>"
                         "<table class=t><tr><th>#<th>What to do<th>Where<th>Note</tr>" + "".join(
                f"<tr><td>{i}<td>{md(f_.get('label',''))}<td>{md(f_.get('where',''))}<td>{md(f_.get('note',''))}</tr>"
                for i, f_ in enumerate(wf.get("flow", []), 1)) + "</table>")
        if mod.get("problems"):
            parts.append("<h3>Common problems</h3><table border=0 cellpadding=6 style='border-collapse:collapse'>"
                         "<tr style='background:#fff6e5;text-align:left'><th>You see<th>Why it happens<th>What to do</tr>")
            for p_ in mod["problems"]:
                parts.append("<tr style='border-bottom:1px solid #d1d5db;vertical-align:top'>"
                             f"<td>{md(p_.get('message',''))}<td>{md(p_.get('cause',''))}<td>{md(p_.get('fix',''))}</tr>")
            parts.append("</table>")
    out = os.path.join(ws, "final", "guide.html")
    text = "".join(parts)
    text = re.sub(r"<b>(.+?)</b>", r"<b>\1</b>", text)
    with open(out, "w") as f:
        f.write(text)
    print(out)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("module")
    m.add_argument("--ws", required=True)
    m.add_argument("--slug", required=True)
    m.add_argument("--force", action="store_true")
    f = sub.add_parser("final")
    f.add_argument("--ws", required=True)
    a = p.parse_args()
    if a.cmd == "module":
        build_module(a.ws, a.slug, a.force)
    else:
        build_final(a.ws)


if __name__ == "__main__":
    main()
