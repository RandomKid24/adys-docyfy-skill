#!/usr/bin/env python3
"""One-page A4 cheat sheets, made to be printed and stuck next to the desk.

  build_cheatsheet.py --ws W [--module S]   -> W/final/cheatsheets/<S>.pdf (and all.pdf when run for every module)

Each sheet is a grid of up to 6 cards. A card is one feature: title, a zoomed crop of
the screen around its highlights, and the first steps in short form. Features marked
"cheat": true in the module JSON are used; otherwise the first 6. The three most useful
"Common problems" go in a strip at the bottom.
Optional per feature: "cheat_step": index of the step whose picture is used (default: first with marks).
"""
import argparse, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
import annotate as ann
import build_pdf as bp

W, H = A4
MARG, GAP = 12 * mm, 6 * mm
CARD_W = (W - 2 * MARG - GAP) / 2
THUMB_H = 30 * mm


def short(text, n=80):
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= n else t[:n - 1].rsplit(" ", 1)[0] + "..."


def focus_region(step, viewport, aspect):
    """Region of the screen (viewport pixels) around the step's highlights, at the card's aspect ratio."""
    marks = [m for m in (step.get("marks") or []) if m.get("style") != "blur" and m.get("box")]
    if not marks or not viewport:
        return None
    vw, vh = viewport
    x0 = min(m["box"][0] for m in marks) - 90
    y0 = min(m["box"][1] for m in marks) - 90
    x1 = max(m["box"][0] + m["box"][2] for m in marks) + 90
    y1 = max(m["box"][1] + m["box"][3] for m in marks) + 90
    w, h = x1 - x0, y1 - y0
    if w / h > aspect:
        grow = w / aspect - h
        y0, y1 = y0 - grow / 2, y1 + grow / 2
    else:
        grow = h * aspect - w
        x0, x1 = x0 - grow / 2, x1 + grow / 2
    w, h = x1 - x0, y1 - y0
    if w >= vw or h >= vh:
        return None
    x0 = min(max(0, x0), vw - w)
    y0 = min(max(0, y0), vh - h)
    return [round(x0), round(y0), round(w), round(h)]


def thumb(ws, step, viewport, aspect, accent, style=None):
    """Redraw the highlights on the ORIGINAL screenshot, cropped to the focus region.
    Cropping the finished (already shrunk) picture made blurry thumbnails."""
    src = step.get("image")
    src = src if src and os.path.isabs(src) else (os.path.join(ws, src) if src else None)
    marks = step.get("marks") or []
    region = focus_region(step, viewport, aspect)
    if not src or not os.path.exists(src) or not marks:
        p = bp.step_image(step, ws)
        if not p:
            return None
        im = Image.open(p).convert("RGB")
        h = min(im.height, int(im.width / aspect))
        return im.crop((0, 0, im.width, h))
    import hashlib
    key = hashlib.sha1((open(src, "rb").read().hex()[:2000] + json.dumps([marks, region, viewport, accent, style, ann.STYLE_VERSION])).encode()).hexdigest()[:16]
    out = os.path.join(ws, "build", "thumbs", f"{key}.jpg")
    if not os.path.exists(out):
        ann.annotate(src, marks, out, viewport, crop=region, max_w=1300, accent=accent, style=style)
    return Image.open(out).convert("RGB")


def pick_features(mod):
    feats = mod.get("features", [])
    flagged = [f for f in feats if f.get("cheat")]
    return (flagged or feats)[:6]


def build_one(ws, slug, state, common):
    mod = json.load(open(os.path.join(ws, "modules", f"{slug}.json")))
    feats = pick_features(mod)
    if not feats:
        print(f"{slug}: no features, skipped")
        return None
    out_dir = os.path.join(ws, "final", "cheatsheets")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{slug}.pdf")
    probs = (mod.get("problems") or [])[:3]
    foot_h = (14 + 9 * len(probs)) * mm if probs else 8 * mm
    head_h = 26 * mm
    grid_h = H - 2 * MARG - head_h - foot_h
    rows = 3
    card_h = (grid_h - (rows - 1) * GAP) / rows
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle(f"{mod.get('title', slug)} cheat sheet")
    # header
    c.setFillColor(bp.ACCENT)
    c.rect(0, H - 10 * mm, W, 10 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(bp.FONT_B, 9)
    c.drawString(MARG, H - 6.8 * mm, state["app"])
    c.drawRightString(W - MARG, H - 6.8 * mm, time.strftime("%d %b %Y"))
    c.setFillColor(bp.INK)
    c.setFont(bp.FONT_XB, 22)
    c.drawString(MARG, H - 21 * mm, mod.get("title", slug))
    c.setFillColor(bp.MUTED)
    c.setFont(bp.FONT, 10)
    c.drawString(MARG, H - 27 * mm, "Quick reference. The full guide has every screen and field.")
    top = H - MARG - head_h + 2 * mm
    step_style = ParagraphStyle("cs", fontName=bp.FONT, fontSize=8.6, leading=11, textColor=bp.INK)
    for i, feat in enumerate(feats):
        col, row = i % 2, i // 2
        x = MARG + col * (CARD_W + GAP)
        y = top - (row + 1) * card_h - row * GAP
        c.setStrokeColor(bp.RULE)
        c.setFillColor(colors.white)
        c.rect(x, y, CARD_W, card_h, fill=1, stroke=1)
        c.setFillColor(bp.ACCENT)
        c.circle(x + 6 * mm, y + card_h - 6 * mm, 3.3 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(bp.FONT_B, 9)
        c.drawCentredString(x + 6 * mm, y + card_h - 7.2 * mm, str(i + 1))
        c.setFillColor(bp.INK)
        c.setFont(bp.FONT_B, 10.5)
        c.drawString(x + 11.5 * mm, y + card_h - 7.4 * mm, short(feat["title"], 38))
        steps = [bp.resolve_step(s, common, ws, state) for s in feat.get("steps", [])]
        # thumbnail
        idx = feat.get("cheat_step")
        if idx is None:
            idx = next((j for j, s in enumerate(steps) if s.get("marks") and bp.step_image(s, ws)), None)
        ty = y + card_h - 11 * mm - THUMB_H
        if idx is not None and idx < len(steps) and bp.step_image(steps[idx], ws):  # picture of the screen
            aspect = (CARD_W - 6 * mm) / THUMB_H
            th = thumb(ws, steps[idx], mod.get("viewport"), aspect, (state.get("brand") or {}).get("accent") or None, (state.get("brand") or {}).get("style") or None)
            tw_mm = CARD_W - 6 * mm
            r = min(tw_mm / th.width, THUMB_H / th.height)
            dw, dh = th.width * r, th.height * r
            c.drawImage(ImageReader(th), x + 3 * mm + (tw_mm - dw) / 2, ty + (THUMB_H - dh) / 2, width=dw, height=dh)
            c.setStrokeColor(bp.RULE)
            c.rect(x + 3 * mm, ty, tw_mm, THUMB_H, fill=0, stroke=1)
        # steps
        y_cursor = ty - 3 * mm
        floor = y + 3 * mm
        shown = 0
        for j, s in enumerate(steps, 1):
            p = Paragraph(f"<b>{j}.</b> {bp.md(short(s.get('text', ''), 90))}", step_style)
            w_, h_ = p.wrap(CARD_W - 8 * mm, 100 * mm)
            if y_cursor - h_ < floor + (4 * mm if j < len(steps) else 0):
                break
            p.drawOn(c, x + 4 * mm, y_cursor - h_)
            y_cursor -= h_ + 1.2 * mm
            shown += 1
        if shown < len(steps):
            c.setFillColor(bp.MUTED)
            c.setFont(bp.FONT, 7.5)
            c.drawString(x + 4 * mm, y + 2.2 * mm, f"+ {len(steps) - shown} more steps in the full guide")
    # problems strip
    if probs:
        c.setFillColor(bp.BONE)
        c.rect(MARG, MARG, W - 2 * MARG, foot_h - 3 * mm, fill=1, stroke=0)
        c.setFillColor(bp.INK)
        c.setFont(bp.FONT_B, 9)
        c.drawString(MARG + 4 * mm, MARG + foot_h - 9 * mm, "If something goes wrong")
        yy = MARG + foot_h - 14.5 * mm
        for p_ in probs:
            para = Paragraph(f"<b>{bp.md(short(p_.get('message', ''), 60))}</b> &gt; {bp.md(short(p_.get('fix', ''), 90))}", step_style)
            w_, h_ = para.wrap(W - 2 * MARG - 8 * mm, 20 * mm)
            para.drawOn(c, MARG + 4 * mm, yy - h_ + 3 * mm)
            yy -= 8.5 * mm
    c.showPage()
    c.save()
    print(f"{out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--module")
    a = ap.parse_args()
    state = bp.load_state(a.ws)
    bp.apply_brand(a.ws, state)
    common = bp.load_common(a.ws, state)
    skip = {"quick-start", "workflows"}
    if a.module:
        slugs = [a.module]
    else:
        slugs = [s for s in state["order"] if state["modules"][s]["status"] == "built" and s not in skip]
    made = [p for p in (build_one(a.ws, s, state, common) for s in slugs) if p]
    if len(made) > 1:
        w = PdfWriter()
        for p in made:
            for pg in PdfReader(p).pages:
                w.add_page(pg)
        merged = os.path.join(a.ws, "final", "cheatsheets", "all.pdf")
        with open(merged, "wb") as f:
            w.write(f)
        print(f"{merged} ({len(made)} sheets)")


if __name__ == "__main__":
    main()
