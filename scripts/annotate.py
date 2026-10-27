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

STYLE_VERSION = "4"
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


def stroke(d, pts, w, ink, halo, halo_w):
    """Halo first (paper), then ink on top; round caps."""
    for color, ww in ((halo, w + halo_w), (ink, w)):
        d.line(pts, fill=color, width=int(round(ww)), joint="curve")
        r = ww / 2
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def displace(mask, s, seed, amp=2.0, freq=34):
    """Hand-drawn wobble like an SVG feTurbulence + feDisplacementMap pass: every point of the
    line work is nudged by a smooth noise field, so edges waver a little and line widths vary."""
    import numpy as np
    from scipy.ndimage import gaussian_filter, map_coordinates
    h, w = mask.size[1], mask.size[0]
    g = np.random.default_rng(seed)
    sigma = freq * s
    fields = []
    for _ in range(2):
        f = gaussian_filter(g.standard_normal((h // 4 + 1, w // 4 + 1)), sigma / 4)
        f = f / (np.abs(f).max() + 1e-9)
        fields.append(np.kron(f, np.ones((4, 4)))[:h, :w] * amp * s)
    yy, xx = np.mgrid[0:h, 0:w].astype("float32")
    out = map_coordinates(np.asarray(mask, dtype="float32"), [yy + fields[1], xx + fields[0]], order=1, mode="constant")
    return Image.fromarray(out.clip(0, 255).astype("uint8"), "L")


# ---------- shapes: each returns (points_list, shape_bbox) ----------
def shape_rect(box, rng, s):
    x, y, w, h = box
    pad = 7 * s
    x0, y0, x1, y1 = x - pad, y - pad, x + w + pad, y + h + pad
    start = x0 + min(26 * s, (x1 - x0) * 0.2)
    over = min(30 * s, (x1 - x0) * 0.25)
    path = [(start, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0), (start + over, y0 - 3.5 * s)]
    return [wobble_pts(path, rng, s)], (x0, y0, x1, y1)


def shape_circle(box, rng, s):
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    rx = max(w / 2 * 1.12 + 10 * s, 22 * s)
    ry = max(h / 2 * 1.30 + 9 * s, 19 * s)
    th0 = rng.uniform(-2.6, -1.9)           # start up and to the left, like a quick pen loop
    n = 120
    pts = []
    for i in range(n + 1):
        t = i / n
        th = th0 + TAU * 1.03 * t
        k = 1 + 0.025 * t                     # drifts out a hair, so the end passes the start
        pts.append((cx + rx * k * math.cos(th), cy + ry * k * math.sin(th)))
    return [wobble_pts(pts, rng, s, step=8, amp=1.6)], (cx - rx * 1.03, cy - ry * 1.03, cx + rx * 1.03, cy + ry * 1.03)


def shape_underline(box, rng, s):
    x, y, w, h = box
    yb = y + h + 7 * s
    pts = [(x - 4 * s, yb), (x + w * 0.5, yb + 1.5 * s), (x + w + 5 * s, yb - 1 * s)]
    return [wobble_pts(pts, rng, s, step=8, amp=1.3)], (x - 6 * s, yb - 4 * s, x + w + 8 * s, yb + 6 * s)


def shape_arrow(box, rng, s, size):
    x, y, w, h = box
    W, H = size
    cx, cy = x + w / 2, y + h / 2
    room = {"left": x, "right": W - (x + w), "top": y, "bottom": H - (y + h)}
    side = max(room, key=room.get)
    L, gap = 78 * s, 9 * s
    tip = {"left": (x - gap, cy), "right": (x + w + gap, cy), "top": (cx, y - gap), "bottom": (cx, y + h + gap)}[side]
    off = {"left": (-L, -L * 0.5), "right": (L, -L * 0.5), "top": (-L * 0.5, -L), "bottom": (-L * 0.5, L)}[side]
    tail = (tip[0] + off[0], tip[1] + off[1])
    ctrl = ((tail[0] + tip[0]) / 2 + rng.uniform(-14, 14) * s, (tail[1] + tip[1]) / 2 + rng.uniform(-14, 14) * s)
    shaft = wobble_pts(bezier(tail, ctrl, tip), rng, s, step=6, amp=1.0)
    ang = math.atan2(shaft[-1][1] - shaft[-6][1], shaft[-1][0] - shaft[-6][0])
    hl = 17 * s
    heads = [[(shaft[-1][0] + hl * math.cos(ang + da), shaft[-1][1] + hl * math.sin(ang + da)), shaft[-1]] for da in (2.65, -2.65)]
    allp = shaft + [p for hd in heads for p in hd]
    bb = (min(p[0] for p in allp), min(p[1] for p in allp), max(p[0] for p in allp), max(p[1] for p in allp))
    return [shaft] + heads, bb, tail


# ---------- badge ----------
def place_badge(bb, r, size, taken, others, prefer_point=None):
    W, H = size
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
        if cx - r < 2 or cy - r < 2 or cx + r > W - 2 or cy + r > H - 2:
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
    c = next((c for c in cands if 0 <= c[0] <= W and 0 <= c[1] <= H), cands[-1])
    return (min(max(c[0], r + 2), W - r - 2), min(max(c[1], r + 2), H - r - 2))


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
    w = 3.2 * s
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

    # 2. lines, drawn as two masks (paper halo, ink), wobbled together, then painted on
    halo_mask = Image.new("L", big.size, 0)
    ink_mask = Image.new("L", big.size, 0)
    dh, di = ImageDraw.Draw(halo_mask), ImageDraw.Draw(ink_mask)
    shapes = []   # (mark, bbox, tail)
    for m in marks:
        style = m.get("style", "rect")
        if style == "blur":
            shapes.append((m, None, None))
            continue
        box = scaled(m)
        tail = None
        if style == "circle":
            parts, bb = shape_circle(box, rng, s)
        elif style == "underline":
            parts, bb = shape_underline(box, rng, s)
        elif style == "arrow":
            parts, bb, tail = shape_arrow(box, rng, s, big.size)
        else:
            parts, bb = shape_rect(box, rng, s)
        for pts in parts:
            stroke(dh, pts, w, 255, 255, 5 * s)
            stroke(di, pts, w, 255, 255, 0)
        shapes.append((m, bb, tail))
    if shapes and any(sh[1] for sh in shapes):
        halo_mask = displace(halo_mask, s, seed)
        ink_mask = displace(ink_mask, s, seed)
        big.paste(Image.new("RGB", big.size, paper), (0, 0), halo_mask)
        big.paste(Image.new("RGB", big.size, ink), (0, 0), ink_mask)
        d = ImageDraw.Draw(big)

    # 3. numbered discs, outside the shapes
    taken = []
    all_bb = [bb for _, bb, _ in shapes if bb]
    for m, bb, tail in shapes:
        if "n" not in m:
            continue
        if bb is None:   # blur mark that wants a number: use its box
            x, y, bw, bh = scaled(m)
            bb = (x, y, x + bw, y + bh)
        others = [o for o in all_bb if o is not bb]
        c = place_badge(bb, r_badge, big.size, taken, others, prefer_point=tail)
        taken.append(c)
        draw_badge(d, c, m["n"], r_badge, s, acc, paper)

    out = big.resize(im.size, Image.LANCZOS)
    if crop:
        cx, cy, cw, ch = crop
        out = out.crop((max(0, int(cx * sx)), max(0, int(cy * sy)), min(im.width, int((cx + cw) * sx)), min(im.height, int((cy + ch) * sy))))
    if out.width > max_w:
        out = out.resize((max_w, int(out.height * max_w / out.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    out.save(out_path, "JPEG", quality=90, subsampling=0, optimize=True)


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
