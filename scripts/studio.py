#!/usr/bin/env python3
"""Studio renderer. Instead of screen-recording a live page (low resolution, uneven frames), capture sharp stills of
each page state, then draw the cursor, zoom, captions, ripples and transitions ourselves, frame by frame.
Result: true 4K at 60 fps (or 1080p for quick drafts), perfectly even motion, and no per-frame waiting.

capture.py builds a Timeline while it drives the page, then calls Timeline.render().
"""
import json, math, os, subprocess, sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

QUALITY = {"draft": (1920, 1080, 30), "1080p": (1920, 1080, 60), "4k": (3840, 2160, 60), "8k": (7680, 4320, 60)}


def sm(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def sm5(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


def layout(W, H, vw, vh):
    pad, bar = int(H * 0.06), int(H * 0.042)
    s = min((H - 2 * pad - bar) / vh, (W - 2 * pad) / vw)
    Wp, Hp = int(round(vw * s)) // 2 * 2, int(round(vh * s)) // 2 * 2
    x0, y0 = (W - Wp) // 2, pad + bar
    return dict(pad=pad, bar=bar, s=s, Wp=Wp, Hp=Hp, x0=x0, y0=y0, rad=int(H * 0.012))


def needed_dpr(W, H, vw, vh, zmax):
    s = layout(W, H, vw, vh)["s"]
    return int(min(4, max(2, math.ceil(s * zmax))))


class Timeline:
    def __init__(self, tmp, vw, vh, accent, app, quality="4k", zmax=1.3):
        self.tmp, self.vw, self.vh, self.accent, self.app = tmp, vw, vh, accent, app
        self.quality, self.zmax = quality, zmax
        self.t = 0.0
        self.stills, self.cursor, self.clicks = [], [], []
        self.captions, self.rings, self.zooms, self.audio = [], [], [], []
        self.pos = [vw * 0.5, vh * 0.62]
        self.start_pos = list(self.pos)
        self.n = 0

    def dpr(self):
        W, H, _ = QUALITY[self.quality]
        return needed_dpr(W, H, self.vw, self.vh, self.zmax)

    def snap(self, page, t, fade=0.2):
        self.n += 1
        path = os.path.join(self.tmp, f"still{self.n}.png")
        page.screenshot(path=path)
        self.stills.append([round(t, 3), path, fade if self.stills else 0.0])

    # ---- rendering -------------------------------------------------------------------------------------------
    def save(self, path, lang="en"):
        d = {k: getattr(self, k) for k in ("tmp", "vw", "vh", "accent", "app", "quality", "zmax", "stills", "cursor", "clicks",
                                           "rings", "zooms", "start_pos")}
        d["captions"] = [(a, b, texts.get(lang) or texts["en"], chips.get(lang) or chips.get("en", ""))
                         for a, b, texts, chips in self.captions]
        d["audio"] = [(p, t) for p, t, lg in self.audio if lg == lang]
        d["end"] = self.t
        json.dump(d, open(path, "w"))

    def render(self, out_mp4, intro=None, outro=None, voice_tail=0.0, lang="en"):
        W, H, fps = QUALITY[self.quality]
        tj = os.path.join(self.tmp, f"timeline-{lang}.json")
        audio = [(p, t) for p, t, lg in self.audio if lg == lang]
        self.save(tj, lang)
        i_len = intro[1] if intro else 0.0
        o_len = outro[1] if outro else 0.0
        body = self.t + voice_tail
        total = i_len + body + o_len
        n = int(math.ceil(total * fps))
        extra = dict(intro=intro, outro=outro, total=total, fps=fps, W=W, H=H, i_len=i_len, o_len=o_len, body=body)
        json.dump(extra, open(tj + ".x", "w"))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
        graph = []
        for k, (path, t) in enumerate(audio):
            cmd += ["-i", path]
            ms = int((t + i_len) * 1000)
            graph.append(f"[{k + 1}:a]adelay={ms}|{ms}[a{k}]")
        if audio:
            mix = "".join(f"[a{k}]" for k in range(len(audio)))
            graph.append(f"{mix}amix=inputs={len(audio)}:normalize=0:duration=longest,apad[aout]" if len(audio) > 1 else "[a0]apad[aout]")
            cmd += ["-filter_complex", ";".join(graph), "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "160k"]
        enc = os.environ.get("DOCYFY_ENCODER", "")
        if not enc:
            has_vt = "h264_videotoolbox" in subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
            enc = "vt" if has_vt and sys.platform == "darwin" else "x264"
        if enc == "vt":
            cmd += ["-c:v", "h264_videotoolbox", "-b:v", f"{int(W * H * fps / 1e6 * 0.25)}M", "-allow_sw", "1"]
        else:
            cmd += ["-c:v", "libx264", "-preset", os.environ.get("DOCYFY_PRESET", "veryfast"), "-crf", "17"]
        cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", f"{total:.3f}", out_mp4]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        import multiprocessing as mp
        with mp.Pool(max(1, min(os.cpu_count() or 1, 6)), initializer=_init, initargs=(tj,)) as pool:
            try:
                for k, raw in enumerate(pool.imap(_frame, range(n), chunksize=3)):
                    ff.stdin.write(raw)
                    if k % (fps * 2) == 0:
                        print(f"  rendering {k}/{n} frames", file=sys.stderr, flush=True)
            except BrokenPipeError:
                pass
        ff.stdin.close()
        ff.wait()
        return out_mp4 if os.path.exists(out_mp4) else None


# ---- worker side ------------------------------------------------------------------------------------------------
G = {}


def _init(tj):
    d = json.load(open(tj))
    d.update(json.load(open(tj + ".x")))
    G["d"] = d
    from PIL import ImageFont
    import theme
    G["font"] = lambda size, w="semibold": ImageFont.truetype(theme.font_path(w), size)
    W, H = d["W"], d["H"]
    L = layout(W, H, d["vw"], d["vh"])
    G["L"] = L
    G["bg"], G["pm"] = _background(d, L)
    G["cur"] = {}
    G["caps"] = [None] * len(d["captions"])
    G["cards"] = {}


def _background(d, L):
    from PIL import Image, ImageDraw, ImageFilter
    import theme
    W, H = d["W"], d["H"]
    bg = Image.new("RGB", (W, H), theme.hex_rgb(theme.PALETTE["bone"]))
    sh = Image.new("L", (W, H), 0)
    x0, y0, Wp, Hp, bar, r = L["x0"], L["y0"], L["Wp"], L["Hp"], L["bar"], L["rad"]
    ImageDraw.Draw(sh).rounded_rectangle([x0, y0 - bar + int(H * 0.012), x0 + Wp, y0 + Hp + int(H * 0.012)], r, fill=95)
    sh = sh.filter(ImageFilter.GaussianBlur(H * 0.014))
    bg.paste(Image.new("RGB", (W, H), (35, 31, 32)), (0, 0), sh)
    dr = ImageDraw.Draw(bg)
    dr.rounded_rectangle([x0, y0 - bar, x0 + Wp, y0 + Hp], r, fill=(246, 247, 249))
    dr.rounded_rectangle([x0, y0 - bar, x0 + Wp, y0 - bar + 2 * r + 4], r, fill=(236, 238, 241))
    dr.rectangle([x0, y0 - bar + r + 2, x0 + Wp, y0 - 1], fill=(236, 238, 241))
    dr.rectangle([x0, y0 - 2, x0 + Wp, y0], fill=(214, 217, 222))
    dot = bar * 0.17
    for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        cx = x0 + bar * 0.62 + i * bar * 0.52
        dr.ellipse([cx - dot, y0 - bar / 2 - dot, cx + dot, y0 - bar / 2 + dot], fill=c)
    try:
        f = G["font"](int(bar * 0.36))
        title = d.get("app") or ""
        tw = dr.textlength(title, font=f)
        dr.text((x0 + Wp / 2 - tw / 2, y0 - bar / 2 - bar * 0.22), title, font=f, fill=(95, 101, 113))
    except Exception:
        pass
    # page mask: square top, rounded bottom corners
    ss = 2
    m = Image.new("L", (Wp * ss, Hp * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, -r * ss * 2, Wp * ss - 1, Hp * ss - 1], r * ss, fill=255)
    return bg, m.resize((Wp, Hp), Image.LANCZOS)


@lru_cache(maxsize=5)
def _scaled(path):
    from PIL import Image
    d, L = G["d"], G["L"]
    ps = L["s"] * d["zmax"]
    im = Image.open(path).convert("RGB")
    return im.resize((int(round(d["vw"] * ps)), int(round(d["vh"] * ps))), Image.LANCZOS)


def _page_view(path, z, sx, sy):
    from PIL import Image
    d, L = G["d"], G["L"]
    ps = L["s"] * d["zmax"]
    im = _scaled(path)
    vw, vh = d["vw"], d["vh"]
    box = (sx * ps, sy * ps, (sx + vw / z) * ps, (sy + vh / z) * ps)
    return im.transform((L["Wp"], L["Hp"]), Image.EXTENT, box, Image.BICUBIC)


def _zoom_state(t):
    d = G["d"]
    vw, vh = d["vw"], d["vh"]
    ramp = 0.7
    bumps = [sm5((t - a) / ramp) - sm5((t - b) / ramp) for a, b, _, _ in d["zooms"]]
    tot = min(1.0, max([0.0] + [max(0.0, x) for x in bumps]))
    z = 1 + (d["zmax"] - 1) * tot
    if tot <= 0:
        return 1.0, 0.0, 0.0
    wsum = sum(max(0.0, x) for x in bumps) or 1.0
    cx = vw / 2 + sum(max(0.0, bp) * (c[2] - vw / 2) for bp, c in zip(bumps, d["zooms"])) / wsum
    cy = vh / 2 + sum(max(0.0, bp) * (c[3] - vh / 2) for bp, c in zip(bumps, d["zooms"])) / wsum
    sx = min(max(cx - vw / (2 * z), 0), vw - vw / z)
    sy = min(max(cy - vh / (2 * z), 0), vh - vh / z)
    return z, sx, sy


def _cursor_pos(t):
    d = G["d"]
    segs = d["cursor"]
    pos = d["start_pos"]
    for (t0, t1, x0, y0, x1, y1) in segs:
        if t < t0:
            break
        if t >= t1:
            pos = [x1, y1]
            continue
        u = sm5((t - t0) / (t1 - t0))
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy) or 1.0
        bend = 0.14 * dist
        nx, ny = -dy / dist, dx / dist                      # arc: control point off the straight line
        cx, cy = (x0 + x1) / 2 + nx * bend, (y0 + y1) / 2 + ny * bend
        px = (1 - u) ** 2 * x0 + 2 * (1 - u) * u * cx + u ** 2 * x1
        py = (1 - u) ** 2 * y0 + 2 * (1 - u) * u * cy + u ** 2 * y1
        return px, py
    return pos[0], pos[1]


def _cursor_sprite(scale):
    from PIL import Image, ImageDraw, ImageFilter
    key = round(scale, 2)
    if key in G["cur"]:
        return G["cur"][key]
    H = G["d"]["H"]
    size = int(H * 0.042 * key)
    K = 8
    big = size * K
    pts = [(3, 2), (3, 20), (8, 15.5), (11.5, 23), (14.5, 21.6), (11.2, 14.3), (18, 14)]
    u = big / 26.0
    poly = [(x * u, y * u) for x, y in pts]
    m = int(big * 0.25)
    shadow = Image.new("RGBA", (big + 2 * m, big + 2 * m), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + m + u * 0.7, y + m + u * 1.5) for x, y in poly], fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(u * 1.1))
    arrow = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(arrow)
    pm = [(x + m, y + m) for x, y in poly]
    dr.polygon(pm, fill=(255, 255, 255, 255))
    tip = pm[0]
    ink = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    ImageDraw.Draw(ink).polygon([(tip[0] + (x - tip[0]) * 0.80 + u * 0.9, tip[1] + (y - tip[1]) * 0.80 + u * 1.5) for x, y in pm], fill=(20, 18, 19, 255))
    sprite = Image.alpha_composite(Image.alpha_composite(shadow, arrow), ink)
    final = sprite.resize((sprite.width // K, sprite.height // K), Image.LANCZOS)
    hot = (m + pts[0][0] * u) / K, (m + pts[0][1] * u) / K
    G["cur"][key] = (final, hot)
    return G["cur"][key]


def _caption(idx):
    from PIL import Image, ImageDraw
    if G["caps"][idx]:
        return G["caps"][idx]
    d, L = G["d"], G["L"]
    H = d["H"]
    t_in, t_out, text, chip = d["captions"][idx]
    fs = int(H * 0.028)
    import theme
    f, fb = theme.font_for(text, fs, "semibold"), theme.font_for(chip, int(fs * 0.62), "bold")
    maxw = int(L["Wp"] * 0.66)
    probe = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    cw = probe.textlength(chip.upper(), font=fb) + fs * 0.95 if chip else 0
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if probe.textlength(trial, font=f) + (cw if not lines else 0) > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    lines.append(cur)
    lh = int(fs * 1.35)
    pad_x, pad_y = int(fs * 0.9), int(fs * 0.55)
    tw = max(probe.textlength(l, font=f) + (cw if i == 0 else 0) for i, l in enumerate(lines))
    w, h = int(tw + pad_x * 2 + fs * 0.3), int(len(lines) * lh + pad_y * 2)
    K = 2
    im = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w * K - 1, h * K - 1], int(fs * 0.45) * K, fill=(30, 27, 28, 238))
    acc = tuple(int(d["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    dr.rounded_rectangle([0, 0, int(fs * 0.3) * K, h * K - 1], int(fs * 0.15) * K, fill=acc + (255,))
    x = pad_x + int(fs * 0.3)
    for i, l in enumerate(lines):
        xx = x
        yy = pad_y + i * lh
        if i == 0 and chip:
            cwid = probe.textlength(chip.upper(), font=fb) + fs * 0.1
            dr.rounded_rectangle([xx * K, (yy + lh * 0.13) * K, (xx + cwid + fs * 0.5) * K, (yy + lh * 0.87) * K], int(fs * 0.2) * K, fill=acc + (255,))
            dr.text(((xx + fs * 0.25) * K, (yy + lh * 0.2) * K), chip.upper(), font=theme.font_for(chip, int(fs * 0.62 * K), "bold"), fill=(255, 255, 255, 255))
            xx += cw
        dr.text((xx * K, yy * K), l, font=theme.font_for(text, fs * K, "semibold"), fill=(246, 247, 249, 255))
    im = im.resize((w, h), Image.LANCZOS)
    G["caps"][idx] = im
    return im


def _card(path):
    from PIL import Image
    if path not in G["cards"]:
        G["cards"] = {path: Image.open(path).convert("RGB").resize((G["d"]["W"], G["d"]["H"]), Image.LANCZOS)}
    return G["cards"][path]


def _body(t):
    """The framed recording at body time t."""
    from PIL import Image, ImageDraw
    d, L = G["d"], G["L"]
    z, sx, sy = _zoom_state(t)
    stills = d["stills"]
    i = 0
    for k, s in enumerate(stills):
        if s[0] <= t:
            i = k
    cur = _page_view(stills[i][1], z, sx, sy)
    if i > 0 and stills[i][2] > 0:
        f = sm((t - stills[i][0]) / stills[i][2])
        if f < 1:
            prev = _page_view(stills[i - 1][1], z, sx, sy)
            cur = Image.blend(prev, cur, f)
    base = G["bg"].copy()
    base.paste(cur, (L["x0"], L["y0"]), G["pm"])
    s = L["s"] * z

    def to_screen(px, py):
        return L["x0"] + (px - sx) * s, L["y0"] + (py - sy) * s

    acc = tuple(int(d["accent"].lstrip("#")[j:j + 2], 16) for j in (0, 2, 4))
    # rings on look-only steps
    for (a, b, bx) in d["rings"]:
        f = sm((t - a) / 0.3) * (1 - sm((t - (b - 0.3)) / 0.3))
        if f > 0:
            x1, y1 = to_screen(bx[0] - 8, bx[1] - 8)
            x2, y2 = to_screen(bx[0] + bx[2] + 8, bx[1] + bx[3] + 8)
            ov = Image.new("RGBA", (int(x2 - x1) + 20, int(y2 - y1) + 20), (0, 0, 0, 0))
            ImageDraw.Draw(ov).rounded_rectangle([10, 10, 10 + x2 - x1, 10 + y2 - y1], int(s * 7), outline=acc + (int(255 * f),), width=max(3, int(s * 2.2)))
            base.paste(ov, (int(x1) - 10, int(y1) - 10), ov)
    # click ripples
    for tc in d["clicks"]:
        dt = t - tc
        if 0 <= dt <= 0.7:
            u = sm5(dt / 0.7)
            px, py = to_screen(*_cursor_pos(tc + 0.0001))
            r = d["H"] * (0.012 + 0.05 * u)
            ov = Image.new("RGBA", (int(r * 2) + 8, int(r * 2) + 8), (0, 0, 0, 0))
            ImageDraw.Draw(ov).ellipse([4, 4, 4 + r * 2, 4 + r * 2], outline=acc + (int(220 * (1 - u)),), width=max(3, int(d["H"] * 0.004)))
            base.paste(ov, (int(px - r - 4), int(py - r - 4)), ov)
    # cursor
    cx, cy = _cursor_pos(t)
    squish = 1.0
    for tc in d["clicks"]:
        dt = t - tc
        if 0 <= dt < 0.3:
            squish = 1 - 0.16 * (sm(dt / 0.09) if dt < 0.09 else 1 - sm((dt - 0.09) / 0.21))
    sprite, hot = _cursor_sprite(squish)
    px, py = to_screen(cx, cy)
    base.paste(sprite, (int(round(px - hot[0])), int(round(py - hot[1]))), sprite)
    # captions
    for k, (a, b, text, chip) in enumerate(d["captions"]):
        f = sm((t - a) / 0.3) * (1 - sm((t - (b - 0.3)) / 0.3))
        if f > 0.01:
            cap = _caption(k)
            if f < 1:
                cap = cap.copy()
                cap.putalpha(cap.getchannel("A").point(lambda v, f=f: int(v * f)))
            cx0 = L["x0"] + (L["Wp"] - cap.width) // 2
            cy0 = L["y0"] + L["Hp"] - cap.height - int(d["H"] * 0.04) + int((1 - f) * d["H"] * 0.012)
            base.paste(cap, (cx0, cy0), cap)
    return base


def _frame(k):
    from PIL import Image
    d = G["d"]
    fps = d["fps"]
    t = k / fps
    il, body = d["i_len"], d["body"]
    X = 0.45                                           # cross-dissolve between a card and the recording
    if d["intro"] and t < il:
        card = _card(d["intro"][0])
        if t > il - X:
            card = Image.blend(card, _body(0.0), sm((t - (il - X)) / X))
        return card.tobytes()
    tb = t - il
    if d["outro"] and tb > body:
        card = _card(d["outro"][0])
        f = sm((tb - body) / X)
        return (Image.blend(_body(body - 0.001), card, f) if f < 1 else card).tobytes()
    return _body(min(tb, body - 0.001)).tobytes()
