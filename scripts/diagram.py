#!/usr/bin/env python3
"""Workflow drawing: a hand-drawn road with numbered stops and a flag at the end.

Same idea as the "How we work" road on the BeForth site: one stop per stage, the road
bends back on itself when it runs out of width, the last stop gets a flag.

Look: ink edges on the road, bone fill, a dashed signal line down the middle (the
connected route), signal discs for stops, paper background, Plus Jakarta Sans, a slow
wobble, no shadows or gradients, no rounded boxes. Cached by content hash in
W/build/flow-<hash>.png.
"""
import hashlib, json, math, os, random, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme

TAU = math.tau
STYLE_VERSION = "2"


def _font(weight, size):
    p = theme.font_path(weight)
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


def _wrap(d, text, font, max_w, max_lines):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,") + "..."
    return lines


def _dense(pts, step):
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


class _Wob:
    def __init__(self, rng, s, amp):
        self.t = [(rng.uniform(140, 320) * s, rng.uniform(0, TAU), rng.uniform(.5, 1)) for _ in range(3)]
        self.n = sum(a for _, _, a in self.t)
        self.amp = amp * s

    def __call__(self, d):
        return self.amp * sum(a * math.sin(TAU * d / l + p) for l, p, a in self.t) / self.n


def _ellipse_arc(cx, cy, rx, ry, a0, a1, n=48):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def render(flow, accent="#1C75BC", out_path="flow.png", state=None):
    tk = theme.tokens({"brand": {"accent": accent}})
    ink, bone, paper, ash, sig = (theme.hex_rgb(tk[k]) for k in ("ink", "bone", "paper", "ash", "signal"))
    S = 2
    n = len(flow)
    rows = 1 if n <= 4 else math.ceil(n / 4)
    per_row = math.ceil(n / rows)
    W = 1400 * S
    margin = 70 * S
    col_w = (W - 2 * margin) / per_row
    row_h = 340 * S
    top = 175 * S
    H = int(top * 2 + (rows - 1) * row_h)
    road_w, edge = 58 * S, 3.4 * S

    # stops
    stops = []
    for i in range(n):
        r, c = divmod(i, per_row)
        cc = c if r % 2 == 0 else per_row - 1 - c
        stops.append((margin + col_w * (cc + 0.5), top + r * row_h))
    rx_turn = col_w * 0.30
    # road: row by row, in travel order, with a U-turn between rows
    path = []
    for r in range(rows):
        idx = [i for i in range(n) if i // per_row == r]
        xs = [stops[i][0] for i in idx]
        y = top + r * row_h
        right = r % 2 == 0
        a = xs[0] - (col_w * 0.45 if r == 0 else col_w * 0.12 * (-1 if right else 1) * -1)
        if r == 0:
            a = xs[0] - col_w * 0.45
        else:
            a = (xs[0] + col_w * 0.12) if not right else (xs[0] - col_w * 0.12)
        b = xs[-1] + (col_w * 0.38 if (r == rows - 1 and right) else (-col_w * 0.38 if r == rows - 1 else 0))
        if r < rows - 1:
            b = xs[-1] + (col_w * 0.12 if right else -col_w * 0.12)
        path += [(a, y), (b, y)]
        if r < rows - 1:
            sign = 1 if right else -1
            cx = b
            arc = _ellipse_arc(0, 0, rx_turn, row_h / 2, -math.pi / 2, math.pi / 2)
            path += [(cx + sign * (px), y + row_h / 2 + py) for px, py in arc]

    rng = random.Random(int(hashlib.md5(json.dumps(flow, sort_keys=True).encode()).hexdigest()[:8], 16))
    wx, wy = _Wob(rng, S, 3.0), _Wob(rng, S, 3.0)
    dense = _dense(path, 6 * S)
    pts = [(x + wx(d), y + wy(d), d) for x, y, d in dense]
    xy = [(x, y) for x, y, _ in pts]

    im = Image.new("RGB", (W, H), paper)
    d = ImageDraw.Draw(im)

    def thick(points, width, color):
        d.line(points, fill=color, width=int(width), joint="curve")
        r = width / 2
        for i in range(0, len(points), 3):
            x, y = points[i]
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)
        for x, y in (points[0], points[-1]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    thick(xy, road_w + 2 * edge, ink)       # road edge
    thick(xy, road_w, bone)                  # road surface
    # dashed centre line = the connected route
    on, off, acc_d, drawing, seg = 30 * S, 22 * S, 0.0, True, []
    for (x, y, dist), (x2, y2, dist2) in zip(pts, pts[1:]):
        step = dist2 - dist
        seg.append((x, y))
        acc_d += step
        if drawing and acc_d >= on:
            seg.append((x2, y2))
            d.line(seg, fill=sig, width=int(4.2 * S), joint="curve")
            seg, acc_d, drawing = [], 0.0, False
        elif not drawing and acc_d >= off:
            seg, acc_d, drawing = [], 0.0, True
    if drawing and len(seg) > 1:
        d.line(seg, fill=sig, width=int(4.2 * S))

    f_num = _font("extrabold", 26 * S)
    f_label = _font("bold", 25 * S)
    f_where = _font("regular", 19 * S)
    r_stop = 27 * S

    def nearest(px, py):
        return min(xy, key=lambda q: (q[0] - px) ** 2 + (q[1] - py) ** 2)

    for i, step in enumerate(flow):
        sx, sy = nearest(*stops[i])
        # stop disc: signal fill, paper ring, ink outline
        d.ellipse([sx - r_stop - 5 * S, sy - r_stop - 5 * S, sx + r_stop + 5 * S, sy + r_stop + 5 * S], fill=ink)
        d.ellipse([sx - r_stop - 1.6 * S, sy - r_stop - 1.6 * S, sx + r_stop + 1.6 * S, sy + r_stop + 1.6 * S], fill=paper)
        d.ellipse([sx - r_stop + 2 * S, sy - r_stop + 2 * S, sx + r_stop - 2 * S, sy + r_stop - 2 * S], fill=sig)
        t = str(i + 1)
        bb = d.textbbox((0, 0), t, font=f_num)
        d.text((sx - (bb[0] + bb[2]) / 2, sy - (bb[1] + bb[3]) / 2), t, font=f_num, fill=paper)
        last = i == n - 1
        if last:   # flag planted on the last stop
            px, py0, py1 = sx, sy - r_stop - 6 * S, sy - r_stop - 100 * S
            d.line([(px, py0), (px, py1)], fill=ink, width=int(3.4 * S))
            d.polygon([(px, py1), (px + 62 * S, py1 + 19 * S), (px, py1 + 40 * S)], fill=sig, outline=ink)
            d.line([(px, py1), (px + 62 * S, py1 + 19 * S), (px, py1 + 40 * S), (px, py1)], fill=ink, width=int(3 * S), joint="curve")
        # label: alternate above and below, the last one always below because of the flag
        r_i, c_i = divmod(i, per_row)
        below = (i % 2 == 0)
        if rows > 1 and r_i < rows - 1 and c_i == len([j for j in range(n) if j // per_row == r_i]) - 1:
            below = False        # last stop before a bend: the road curves away underneath, so write above
        if rows > 1 and r_i > 0 and c_i == 0:
            below = True         # first stop after a bend: the road comes in from above, so write below
        if last:
            below = True         # the flag takes the space above
        label = _wrap(d, theme.pil_text(step.get("label", "")), f_label, col_w * 0.90, 2)
        where = _wrap(d, theme.pil_text(step.get("where", "")), f_where, col_w * 0.90, 2)
        block_h = len(label) * 32 * S + (8 * S if where else 0) + len(where) * 25 * S
        ty = sy + r_stop + 20 * S if below else sy - r_stop - 20 * S - block_h
        for ln in label:
            w_ = d.textlength(ln, font=f_label)
            d.text((sx - w_ / 2, ty), ln, font=f_label, fill=ink)
            ty += 32 * S
        ty += 8 * S if where else 0
        for ln in where:
            w_ = d.textlength(ln, font=f_where)
            d.text((sx - w_ / 2, ty), ln, font=f_where, fill=ash)
            ty += 25 * S

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    im = im.resize((W // 2, H // 2), Image.LANCZOS)
    im.save(out_path, "PNG", optimize=True)
    return out_path


def flow_png(ws, wf, accent="#1C75BC"):
    key = hashlib.sha1((json.dumps(wf.get("flow", []), sort_keys=True) + accent + STYLE_VERSION
                        + open(__file__).read()).encode()).hexdigest()[:12]
    out = os.path.join(ws, "build", f"flow-{key}.png")
    if not os.path.exists(out):
        render(wf.get("flow", []), accent, out)
    return out


if __name__ == "__main__":
    demo = [{"label": "Add the item", "where": "Items > Add item"},
            {"label": "Receive stock", "where": "Stock > Receive"},
            {"label": "Create the quotation", "where": "Quotations > Add quotation"},
            {"label": "Convert to order", "where": "Orders > From quotation"},
            {"label": "Raise the invoice", "where": "Invoices > Add invoice"}]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(render(demo[:n], "#1C75BC", sys.argv[1] if len(sys.argv) > 1 else "flow-demo.png"))
