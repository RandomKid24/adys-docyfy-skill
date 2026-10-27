#!/usr/bin/env python3
"""Draw hand-drawn style highlights and numbered discs on screenshots (BeForth doodle style).

Usage
  annotate.py --ws W --module SLUG        annotate every step of modules/SLUG.json
  annotate.py --image in.png --out out.png --marks '[{"n":1,"box":[10,10,100,40]}]' [--viewport 1440 900] [--crop x y w h]

Look (see theme.py): ink line work with a paper halo so it reads on any screen colour,
round caps, a slow wobble (lines bend, they do not jitter), one stroke per shape, and a
numbered disc in the accent colour that sits OUTSIDE the shape so it never covers the line.
Styles: rect (default), circle, underline, arrow, blur.

Output goes to W/annotated/<hash>.jpg. The hash covers the source image bytes, marks, crop,
viewport, accent and STYLE_VERSION, so unchanged steps are skipped and a style change
redraws everything once.
"""
import argparse, hashlib, json, math, os, random, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme

STYLE_VERSION = "6"
SS = 2                    # supersampling for smooth lines
TAU = math.tau


# ---------- helpers ----------
def font(size, weight="extrabold"):
    p = theme.font_path(weight)
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


class Wobble:
    """Slow, smooth offset as a function of distance along a path."""

    def __init__(self, rng, s, amp=1.5):
        self.terms = [(rng.uniform(80, 190) * s, rng.uniform(0, TAU), rng.uniform(0.5, 1.0)) for _ in range(3)]
        self.norm = sum(a for _, _, a in self.terms)
        self.amp = amp * s

    def __call__(self, d):
        return self.amp * sum(a * math.sin(TAU * d / l + ph) for l, ph, a in self.terms) / self.norm


def densify(pts, step):
    """Resample a polyline every ~step pixels; returns [(x, y, dist)]."""
    out, dist = [], 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = math.hypot(bx - ax, by - ay)
        n = max(1, int(seg / step))
        for i in range(n):
            t = i / n
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t, dist + seg * t))
        dist += seg
    out.append((pts[-1][0], pts[-1][1], dist))
    return out


def wobble_pts(pts, rng, s, step=6, amp=1.5):
    wx, wy = Wobble(rng, s, amp), Wobble(rng, s, amp)
    return [(x + wx(d), y + wy(d)) for x, y, d in densify(pts, step * s)]


def bezier(p0, p1, p2, n=40):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]) for t in (i / n for i in range(n + 1))]


def pen(d, pts, w, fill=255, taper=0.12, s=1.0):
    """One pen stroke as a run of round dabs. The width swells in the middle and thins to a point
    at both ends, with a faint pressure wobble, the way a pen line looks when drawn fast."""
    dense = densify(pts, max(1.0, 1.4 * s))
    total = dense[-1][2] or 1.0
    ramp = max(total * taper, 12 * s)
    for i, (x, y, dist) in enumerate(dense):
        f = min(1.0, dist / ramp, (total - dist) / ramp)
        f = max(f, 0.0) ** 0.7
        ww = w * (0.28 + 0.72 * f) * (1 + 0.07 * math.sin(dist / (23 * s)))
        r = ww / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def displace(mask, s, seed, amp=0.9, freq=30):
    """Hand-drawn wobble like an SVG feTurbulence + feDisplacementMap pass: every point of the
    line work is nudged by a smooth noise field, so edges waver a little and line widths vary."""
    import numpy as np
    from scipy.ndimage import gaussian_filter, map_coordinates, zoom
    h, w = mask.size[1], mask.size[0]
    g = np.random.default_rng(seed)
    sigma = freq * s
    fields = []
    for _ in range(2):
        f = gaussian_filter(g.standard_normal((h // 4 + 1, w // 4 + 1)), sigma / 4)
        f = f / (np.abs(f).max() + 1e-9)
        fields.append(zoom(f, 4, order=3)[:h, :w] * amp * s)
    yy, xx = np.mgrid[0:h, 0:w].astype("float32")
    out = map_coordinates(np.asarray(mask, dtype="float32"), [yy + fields[1], xx + fields[0]], order=1, mode="constant")
    return Image.fromarray(out.clip(0, 255).astype("uint8"), "L")


# ---------- shapes: each returns (main_parts, bbox, faint_parts, tail) ----------
def _rrect_loop(x0, y0, x1, y1, r, start_y=0.4, over=16.0, s=1.0):
    """Rounded rectangle as one pen path. It starts on the right edge, goes round, and overshoots
    its own start by a few pixels, drifting outward, like a quick hand-drawn box.
    Starting on a side keeps the stray end away from the label printed above a field."""
    perim = []

    def arc(cx, cy, a0, a1, n=10):
        return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]

    perim += [(x0 + r, y0), (x1 - r, y0)] + arc(x1 - r, y0 + r, -math.pi / 2, 0)
    perim += [(x1, y1 - r)] + arc(x1 - r, y1 - r, 0, math.pi / 2)
    perim += [(x0 + r, y1)] + arc(x0 + r, y1 - r, math.pi / 2, math.pi)
    perim += [(x0, y0 + r)] + arc(x0 + r, y0 + r, math.pi, 1.5 * math.pi)
    perim.append(perim[0])
    dense = densify(perim, 2 * s)
    ty = y0 + (y1 - y0) * start_y
    k = min(range(len(dense)), key=lambda i: abs(dense[i][0] - x1) + abs(dense[i][1] - ty) * (1 if dense[i][0] > x1 - r else 9))
    pts = [(x, y) for x, y, _ in dense]
    pts = pts[k:] + pts[1:k + 1]
    n_over = max(2, int(over * s / (2 * s)))
    tail = pts[1:1 + n_over]
    tail = [(x + 2.2 * s * (i / n_over), y) for i, (x, y) in enumerate(tail)]
    return pts + tail


def shape_rect(box, rng, s, pad=None):
    x, y, w, h = box
    pad = (3 if pad is None else pad) * s
    x0, y0, x1, y1 = x - pad, y - pad, x + w + pad, y + h + pad
    r = min(6 * s, (y1 - y0) / 2.4, (x1 - x0) / 2.4)
    main = wobble_pts(_rrect_loop(x0, y0, x1, y1, r, rng.uniform(0.3, 0.55), s=s), rng, s, step=6, amp=0.7)
    j = 1.4 * s
    faint = wobble_pts(_rrect_loop(x0 - j, y0 - j * 0.6, x1 + j * 0.8, y1 + j, r, rng.uniform(0.6, 0.85), over=8, s=s), rng, s, step=6, amp=0.9)
    return [main], (x0, y0, x1, y1), [faint], None


def shape_circle(box, rng, s, pad=None):
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    extra = 4 if pad is None else pad
    rx = max(w / 2 * 1.08 + extra * s, 16 * s)
    ry = max(h / 2 * 1.18 + extra * s, 14 * s)

    def loop(th0, turns, drift, amp):
        n = 140
        pts = []
        for i in range(n + 1):
            t = i / n
            th = th0 + TAU * turns * t
            k = 1 + drift * t
            pts.append((cx + rx * k * math.cos(th), cy + ry * k * math.sin(th)))
        return wobble_pts(pts, rng, s, step=8, amp=amp)

    th0 = rng.uniform(-0.5, 0.5)       # start on the right side, away from labels above
    main = loop(th0, 1.03, 0.025, 0.7)
    faint = loop(th0 + 0.35, 0.9, -0.02, 0.9)
    return [main], (cx - rx * 1.03, cy - ry * 1.03, cx + rx * 1.03, cy + ry * 1.03), [faint], None


def shape_underline(box, rng, s, pad=None):
    x, y, w, h = box
    yb = y + h + 6 * s
    pts = [(x - 3 * s, yb), (x + w * 0.5, yb + 1.2 * s), (x + w + 4 * s, yb - 0.8 * s)]
    main = wobble_pts(pts, rng, s, step=8, amp=0.7)
    faint = wobble_pts([(px, py + 2.2 * s) for px, py in pts[:-1]] + [(pts[-1][0] - w * 0.15, pts[-1][1] + 2.2 * s)], rng, s, step=8, amp=0.9)
    return [main], (x - 6 * s, yb - 4 * s, x + w + 8 * s, yb + 6 * s), [faint], None


def shape_arrow(box, rng, s, size):
    x, y, w, h = box
    W, H = size
    cx, cy = x + w / 2, y + h / 2
    room = {"left": x, "right": W - (x + w), "top": y, "bottom": H - (y + h)}
    side = max(room, key=room.get)
    L, gap = 70 * s, 8 * s
    tip = {"left": (x - gap, cy), "right": (x + w + gap, cy), "top": (cx, y - gap), "bottom": (cx, y + h + gap)}[side]
    off = {"left": (-L, -L * 0.45), "right": (L, -L * 0.45), "top": (-L * 0.45, -L), "bottom": (-L * 0.45, L)}[side]
    tail = (tip[0] + off[0], tip[1] + off[1])
    ctrl = ((tail[0] + tip[0]) / 2 + rng.uniform(-12, 12) * s, (tail[1] + tip[1]) / 2 + rng.uniform(-12, 12) * s)
    shaft = wobble_pts(bezier(tail, ctrl, tip), rng, s, step=6, amp=0.7)
    ang = math.atan2(shaft[-1][1] - shaft[-6][1], shaft[-1][0] - shaft[-6][0])
    hl = 15 * s
    heads = [[(shaft[-1][0] + hl * math.cos(ang + da), shaft[-1][1] + hl * math.sin(ang + da)), shaft[-1]] for da in (2.7, -2.7)]
    allp = shaft + [p for hd in heads for p in hd]
    bb = (min(p[0] for p in allp), min(p[1] for p in allp), max(p[0] for p in allp), max(p[1] for p in allp))
    return [shaft] + heads, bb, [], tail


# ---------- badge ----------
def place_badge(bb, r, bounds, taken, others, prefer_point=None):
    BX0, BY0, BX1, BY1 = bounds
    x0, y0, x1, y1 = bb
    gap = 5 * r / 13
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    cands = []
    if prefer_point:
        cands.append(prefer_point)
    cands += [(x0 - r - gap, my), (x0 - r * 0.9, y0 - r - gap * 0.4), (mx, y0 - r - gap),
              (x1 + r + gap, my), (mx, y1 + r + gap), (x1 + r * 0.9, y0 - r - gap * 0.4)]

    def ok(c):
        cx, cy = c
        if cx - r < BX0 + 2 or cy - r < BY0 + 2 or cx + r > BX1 - 2 or cy + r > BY1 - 2:
            return False
        if any(math.dist(c, t) < 2 * r + 4 for t in taken):
            return False
        for ox0, oy0, ox1, oy1 in others:
            nx, ny = min(max(cx, ox0), ox1), min(max(cy, oy0), oy1)
            if math.dist((cx, cy), (nx, ny)) < r:
                return False
        return True

    for c in cands:
        if ok(c):
            return c
    c = next((c for c in cands if BX0 <= c[0] <= BX1 and BY0 <= c[1] <= BY1), cands[-1])
    return (min(max(c[0], BX0 + r + 2), BX1 - r - 2), min(max(c[1], BY0 + r + 2), BY1 - r - 2))


def draw_badge(d, c, n, r, s, accent, paper):
    cx, cy = c
    ring = 2.4 * s
    d.ellipse([cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring], fill=paper)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)
    f = font(int(r * 1.25))
    t = str(n)
    bb = d.textbbox((0, 0), t, font=f)
    d.text((cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2), t, font=f, fill=paper)


# ---------- main drawing ----------
def annotate(img_path, marks, out_path, viewport=None, crop=None, max_w=1600, accent=None):
    tk = theme.tokens({"brand": {"accent": accent}} if accent else None)
    ink, paper, acc = theme.hex_rgb(tk["ink"]), theme.hex_rgb(tk["paper"]), theme.hex_rgb(tk["accent"])
    im = Image.open(img_path).convert("RGB")
    sx = im.width / viewport[0] if viewport else 1.0
    sy = im.height / viewport[1] if viewport else 1.0
    big = im.resize((im.width * SS, im.height * SS), Image.LANCZOS)
    d = ImageDraw.Draw(big)
    s = SS * max(1.0, im.width / 1280)     # one unit = 1px on a 1280-wide image
    w = 2.5 * s
    seed = int(hashlib.md5(json.dumps(marks, sort_keys=True).encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    r_badge = 13 * s

    def scaled(m):
        bx, by, bw, bh = m["box"]
        return (bx * sx * SS, by * sy * SS, bw * sx * SS, bh * sy * SS)

    # 1. redact first, so lines and discs stay crisp on top
    for m in marks:
        if m.get("style") == "blur":
            x, y, bw, bh = scaled(m)
            x0, y0 = max(0, int(x)), max(0, int(y))
            x1, y1 = min(big.width, int(x + bw)), min(big.height, int(y + bh))
            if x1 > x0 and y1 > y0:
                reg = big.crop((x0, y0, x1, y1))
                cell = max(6, int(8 * s))
                small = reg.resize((max(1, reg.width // cell), max(1, reg.height // cell)), Image.BILINEAR)
                big.paste(small.resize(reg.size, Image.NEAREST), (x0, y0))

    # 2. lines: paper halo, faint second pass and the main pen stroke are three masks,
    #    wobbled by the same noise, then painted on top of the screenshot
    halo_mask = Image.new("L", big.size, 0)
    faint_mask = Image.new("L", big.size, 0)
    ink_mask = Image.new("L", big.size, 0)
    dh, df, di = ImageDraw.Draw(halo_mask), ImageDraw.Draw(faint_mask), ImageDraw.Draw(ink_mask)
    shapes = []   # (mark, bbox, tail)
    for m in marks:
        style = m.get("style", "rect")
        if style == "blur":
            shapes.append((m, None, None))
            continue
        box = scaled(m)
        if style == "circle":
            parts, bb, faint, tail = shape_circle(box, rng, s)
        elif style == "underline":
            parts, bb, faint, tail = shape_underline(box, rng, s)
        elif style == "arrow":
            parts, bb, faint, tail = shape_arrow(box, rng, s, big.size)
        else:
            parts, bb, faint, tail = shape_rect(box, rng, s)
        for pts in parts:
            pen(dh, pts, w + 4.5 * s, 255, s=s)
            pen(di, pts, w, 255, s=s)
        for pts in faint:
            pen(df, pts, w * 0.5, 255, s=s)
        shapes.append((m, bb, tail))
    if any(sh[1] for sh in shapes):
        halo_mask = displace(halo_mask, s, seed)
        faint_mask = displace(faint_mask, s, seed + 1).point(lambda v: int(v * 0.26))
        ink_mask = displace(ink_mask, s, seed)
        big.paste(Image.new("RGB", big.size, paper), (0, 0), halo_mask)
        big.paste(Image.new("RGB", big.size, ink), (0, 0), faint_mask)
        big.paste(Image.new("RGB", big.size, ink), (0, 0), ink_mask)
        d = ImageDraw.Draw(big)

    # 3. numbered discs, outside the shapes and always inside the visible picture
    if crop:
        bounds = (max(0, crop[0] * sx * SS), max(0, crop[1] * sy * SS),
                  min(big.width, (crop[0] + crop[2]) * sx * SS), min(big.height, (crop[1] + crop[3]) * sy * SS))
    else:
        bounds = (0, 0, big.width, big.height)
    taken = []
    all_bb = [bb for _, bb, _ in shapes if bb]
    for m, bb, tail in shapes:
        if "n" not in m:
            continue
        if bb is None:   # blur mark that wants a number: use its box
            x, y, bw, bh = scaled(m)
            bb = (x, y, x + bw, y + bh)
        others = [o for o in all_bb if o is not bb]
        c = place_badge(bb, r_badge, bounds, taken, others, prefer_point=tail)
        taken.append(c)
        draw_badge(d, c, m["n"], r_badge, s, acc, paper)

    out = big.resize(im.size, Image.LANCZOS)
    if crop:
        cx, cy, cw, ch = crop
        out = out.crop((max(0, int(cx * sx)), max(0, int(cy * sy)), min(im.width, int((cx + cw) * sx)), min(im.height, int((cy + ch) * sy))))
    if out.width > max_w:
        out = out.resize((max_w, int(out.height * max_w / out.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    out.save(out_path, "JPEG", quality=95, subsampling=0, optimize=True)


def key_for(img_path, marks, viewport, crop, accent):
    h = hashlib.sha1()
    with open(img_path, "rb") as f:
        h.update(f.read())
    h.update(json.dumps([marks, viewport, crop, accent, STYLE_VERSION], sort_keys=True).encode())
    return h.hexdigest()[:16]


def run_module(ws, slug):
    mp = os.path.join(ws, "modules", f"{slug}.json")
    with open(mp) as f:
        mod = json.load(f)
    viewport = mod.get("viewport")
    made = reused = 0
    shots, accent = {}, None
    sp = os.path.join(ws, "state.json")
    if os.path.exists(sp):
        st = json.load(open(sp))
        shots = st.get("shots", {})
        accent = (st.get("brand") or {}).get("accent") or None
    for feat in mod.get("features", []):
        for step in feat.get("steps", []):
            step_img = step.get("image")
            if not step_img and "common" in step:
                step_img = shots.get(step["common"])  # shared screenshot, annotated by whoever registered it
                if step_img:
                    step["annotated"] = step_img
                continue
            if not step_img:
                continue
            src = step_img if os.path.isabs(step_img) else os.path.join(ws, step_img)
            if not os.path.exists(src):
                print(f"missing image: {step_img}", file=sys.stderr)
                continue
            try:
                with Image.open(src) as _im:
                    if _im.width < 1100:
                        print(f"WARN {step_img}: only {_im.width}px wide, it will print soft. Retake it with scale 1 in a ~1440px window.", file=sys.stderr)
            except Exception:
                pass
            marks, crop = step.get("marks", []), step.get("crop")
            if not marks and not crop:
                step["annotated"] = os.path.relpath(src, ws)
                continue
            k = key_for(src, marks, viewport, crop, accent)
            out = os.path.join(ws, "annotated", f"{k}.jpg")
            if os.path.exists(out):
                reused += 1
            else:
                annotate(src, marks, out, viewport, crop, accent=accent)
                made += 1
            step["annotated"] = os.path.relpath(out, ws)
    with open(mp, "w") as f:
        json.dump(mod, f, indent=2)
    print(f"{slug}: {made} drawn, {reused} reused")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ws")
    p.add_argument("--module")
    p.add_argument("--image")
    p.add_argument("--out")
    p.add_argument("--marks")
    p.add_argument("--viewport", nargs=2, type=float)
    p.add_argument("--crop", nargs=4, type=float)
    p.add_argument("--accent")
    a = p.parse_args()
    if a.ws and a.module:
        run_module(a.ws, a.module)
    elif a.image and a.out and a.marks:
        annotate(a.image, json.loads(a.marks), a.out, a.viewport, a.crop, accent=a.accent)
        print(a.out)
    else:
        p.error("give --ws and --module, or --image --out --marks")


if __name__ == "__main__":
    main()
