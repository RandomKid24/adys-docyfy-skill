#!/usr/bin/env python3
"""Fast, sharp capture. Runs Chrome on YOUR computer through Playwright, so pictures are 2x sharp,
boxes are measured exactly, and the video is edited as it records. No per-click round trips to Claude.

  capture.py login   --url URL --out ws/.auth/state.json     you sign in yourself, in a real window
  capture.py explore --url URL [--state S] [--wait CSS]       list clickable things as text (no images)
  capture.py voices  [--out DIR] [--langs en,hi,mr]          hear the narration voices before you render
  capture.py run     --ws W --spec spec.json [--no-video]     do the tasks, write shots, boxes, GIFs

Spec (spec.json):
{ "env": "staging",                      # local | staging | production (production is look-only)
  "base": "https://staging.example.com", "viewport": [1440, 900], "state": ".auth/state.json",
  "tasks": [ { "slug": "punch-in", "title": "How to punch in", "goal": "...",
      "before": {"menu": "Home", "role": "Any employee", "ready": []},
      "steps": [
        {"text": "Open the app and sign in.", "goto": "/", "marks": [{"target": "role=textbox[name=\\"Username\\"]"}]},
        {"text": "Click **Punch in**.", "click": "role=button[name=\\"Punch in\\"]"},
        {"text": "You see the confirmation.", "shot": true, "marks": [{"target": "text=Punched in", "style": "rect"}]} ] } ] }

A step: optional "goto"; its marks (targets to highlight) and picture are taken BEFORE the action; then one
action: click | fill [target, value] | select [target, value] | press key | wait (ms or selector). A step with
a click and no marks highlights the click target. "shot": true forces a picture. "blur": [targets] pixelates
(names, phones, amounts). Marks are numbered 1, 2, 3 in order.
Highlight in the video: "highlight": "auto" (default) shows only the caption when the cursor points at a click, fill
or select target, and a soft ring (no dim) on look-only steps. "full" always spotlights with a number, "caption" never.
Studio engine (default): captures sharp stills of each page state, then draws the cursor, zoom, captions, ripples
and fades itself at 60 fps. "quality": "4k" (default, 3840x2160 at 60 fps) | "1080p" | "draft" (1080p at 30 fps, fast,
use while checking) | "8k". "engine": "live" goes back to screen-recording the browser. On a Mac the hardware
encoder is used when ffmpeg has it. DOCYFY_PRESET=fast|medium trades render time for smaller files.
Look of the video: a title card and an end card ("cards": false removes them), a "Step 2 of 4" chip in the
caption, and a smooth zoom toward each click target ("zoom": false removes it, "zoom_level": 1.3 sets how much).
Voice: add "voice": true (or {"name": "Rishi", "rate": 170}) to the spec header and each step's text is read
aloud, Frappe style. The MP4 carries the voice, the GIF stays silent. Uses macOS `say` (default voice Rishi),
else espeak-ng. Set DOCYFY_TTS_CMD='mytts "{text}" {out}' to use another engine.
Safety: production is look-only (no click, fill, select, press). Password fields are never filled: sign in with
the login command instead. Use sample data in fill values.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
WRITE_ACTIONS = ("click", "fill", "select", "press")


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def pw():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        die("Playwright is missing. Run the installer again (npx github:RandomKid24/adys-docyfy-skill) or: "
            "pip install playwright && python -m playwright install chromium")


def launch(p, headless=True):
    """Use the Chrome already installed on this computer. Fall back to Playwright's own Chromium."""
    try:
        return p.chromium.launch(channel="chrome", headless=headless)
    except Exception:
        try:
            return p.chromium.launch(headless=headless)
        except Exception as e:
            die("No browser found. Install Google Chrome, or run: python -m playwright install chromium\n" + str(e)[:200])


def box_of(page, target):
    loc = page.locator(target).first
    loc.wait_for(state="visible", timeout=8000)
    loc.scroll_into_view_if_needed(timeout=3000)
    b = loc.bounding_box()
    if not b:
        raise RuntimeError(f"no box for {target}")
    return [round(b["x"]), round(b["y"]), round(b["width"]), round(b["height"])]


OVERLAY_JS = """([boxes, caption, accent, mode, label]) => {
  document.getElementById('__dy')?.remove();
  const root = document.createElement('div'); root.id = '__dy';
  root.style.cssText = 'position:fixed;inset:0;z-index:2147483646;pointer-events:none;font-family:system-ui,sans-serif;opacity:0;transition:opacity .28s ease';
  (mode === 'caption' ? [] : boxes).forEach((b, i) => {
    const full = mode === 'full';
    const hole = document.createElement('div');
    hole.style.cssText = `position:absolute;left:${b[0]-8}px;top:${b[1]-8}px;width:${b[2]+16}px;height:${b[3]+16}px;border-radius:9px;` +
      `box-shadow:${full ? '0 0 0 9999px rgba(35,31,32,.12)' : 'none'};outline:2.5px solid ${accent};outline-offset:-2px;background:transparent`;
    root.appendChild(hole);
    if (!full) return;
    const n = document.createElement('div');
    n.textContent = i + 1;
    n.style.cssText = `position:absolute;left:${Math.max(4, b[0]-8-34)}px;top:${b[1]+b[3]/2-15}px;width:30px;height:30px;border-radius:50%;` +
      `background:${accent};color:#fff;font:800 16px/30px system-ui;text-align:center;box-shadow:0 0 0 3px #F2F7F9`;
    root.appendChild(n);
  });
  if (caption) {
    const c = document.createElement('div');
    if (label) {
      const chip = document.createElement('span');
      chip.textContent = label;
      chip.style.cssText = 'display:inline-block;margin-right:12px;padding:2px 9px;background:' + accent + ';color:#fff;font:800 13px/1.5 system-ui;letter-spacing:.04em;text-transform:uppercase;vertical-align:2px';
      c.appendChild(chip);
    }
    c.appendChild(document.createTextNode(caption));
    c.style.cssText = 'position:absolute;left:50%;bottom:28px;transform:translateX(-50%);max-width:70%;background:#231F20;color:#F2F7F9;' +
      'padding:12px 20px;font:600 18px/1.35 system-ui;border-left:5px solid ' + accent;
    root.appendChild(c);
  }
  document.body.appendChild(root);
  requestAnimationFrame(() => requestAnimationFrame(() => { root.style.opacity = 1; }));
}"""


CURSOR_JS = """([x, y, accent]) => {
  let c = document.getElementById('__dyc');
  if (!c) {
    c = document.createElement('div'); c.id = '__dyc';
    c.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;width:26px;height:26px;margin:-3px 0 0 -3px;' +
      'transition:left .6s cubic-bezier(.45,.05,.2,1),top .6s cubic-bezier(.45,.05,.2,1);left:' + x + 'px;top:' + y + 'px';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 20 L8 15.5 L11.5 23 L14.5 21.6 L11.2 14.3 L18 14 Z" fill="#231F20" stroke="#F2F7F9" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
  }
}"""

MOVE_JS = """([x, y]) => { const c = document.getElementById('__dyc'); if (c) { c.style.left = x + 'px'; c.style.top = y + 'px'; } }"""

RIPPLE_JS = """([x, y, accent]) => {
  const r = document.createElement('div');
  r.style.cssText = `position:fixed;z-index:2147483647;pointer-events:none;left:${x-6}px;top:${y-6}px;width:12px;height:12px;border-radius:50%;` +
    `border:3px solid ${accent};opacity:.9;transform:scale(1);transition:transform .45s ease-out,opacity .45s ease-out`;
  document.body.appendChild(r);
  requestAnimationFrame(() => { r.style.transform = 'scale(4)'; r.style.opacity = 0; });
  setTimeout(() => r.remove(), 600);
}"""


EDGE_VOICES = {"en": "en-IN-NeerjaNeural", "hi": "hi-IN-SwaraNeural", "mr": "mr-IN-AarohiNeural"}
SAY_VOICES = {"en": "Rishi", "hi": "Lekha", "mr": "Lekha"}      # macOS has no Marathi voice; Lekha reads Devanagari
ESPEAK_LANG = {"en": "en-in", "hi": "hi", "mr": "mr"}
_edge_broken = []


def speak(text, out_base, voice=None, rate=170, lang="en"):
    """Turn a sentence into a sound file. Order: DOCYFY_TTS_CMD, then Microsoft neural voices through the
    edge-tts package (best for Hindi and Marathi, needs internet), then macOS `say`, then espeak-ng.
    Returns the file path, or None when no voice is available."""
    custom = os.environ.get("DOCYFY_TTS_CMD")
    out = out_base + ".wav"
    try:
        if custom:
            subprocess.run(custom.format(text=text.replace('"', ""), out=out, lang=lang), shell=True, check=True, capture_output=True)
        else:
            out = None
            if not _edge_broken:
                try:
                    import asyncio, edge_tts
                    name = voice if isinstance(voice, str) and "Neural" in voice else EDGE_VOICES.get(lang, EDGE_VOICES["en"])
                    mp3 = out_base + ".mp3"
                    asyncio.run(asyncio.wait_for(edge_tts.Communicate(text, name).save(mp3), 25))
                    if os.path.exists(mp3) and os.path.getsize(mp3) > 500:
                        out = mp3
                except Exception:
                    if os.path.exists(out_base + ".mp3"):
                        os.remove(out_base + ".mp3")
                    _edge_broken.append(1)             # offline or not installed, do not retry every step
            if out is None and shutil.which("say"):
                out = out_base + ".aiff"
                names = [voice] if voice and "Neural" not in str(voice) else [SAY_VOICES.get(lang, "Rishi"), None]
                for v in names:
                    cmd = ["say", "-r", str(rate), "-o", out] + (["-v", v] if v else []) + [text]
                    if subprocess.run(cmd, capture_output=True).returncode == 0:
                        break
            elif out is None and (shutil.which("espeak-ng") or shutil.which("espeak")):
                out = out_base + ".wav"
                subprocess.run([shutil.which("espeak-ng") or shutil.which("espeak"), "-v", ESPEAK_LANG.get(lang, "en-in"), "-s", str(rate), "-w", out, text],
                               check=True, capture_output=True)
            if out is None:
                return None
    except Exception:
        return None
    return out if os.path.exists(out) and os.path.getsize(out) > 500 else None


def audio_len(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def plain(text):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")


def cmd_login(a):
    sp = pw()()
    with sp as p:
        br = launch(p, headless=False)
        ctx = br.new_context()
        page = ctx.new_page()
        page.goto(a.url)
        print("Sign in in the window that opened. Close the window when you are done. Nothing is typed for you.")
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        try:
            while True:
                if page.is_closed():
                    break
                ctx.storage_state(path=a.out)
                time.sleep(1.5)
        except Exception:
            pass
        try:
            br.close()
        except Exception:
            pass
    os.chmod(a.out, 0o600)
    print(f"Saved sign-in to {a.out}. Keep it private. It is never copied into the guide.")


def cmd_explore(a):
    sp = pw()()
    with sp as p:
        br = launch(p)
        ctx = br.new_context(storage_state=a.state if a.state and os.path.exists(a.state) else None,
                             viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(a.url, wait_until="networkidle")
        if a.wait:
            page.wait_for_selector(a.wait, timeout=10000)
        items = page.evaluate("""() => {
          const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
            return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'; };
          const out = [];
          document.querySelectorAll('a[href],button,input,select,textarea,[role=button],[role=tab],[role=menuitem],[role=link]').forEach(e => {
            if (!vis(e)) return;
            const lab = (e.id && document.querySelector(`label[for="${e.id}"]`)?.innerText) || '';
            const name = (e.getAttribute('aria-label') || lab || e.innerText || e.placeholder || e.value || e.title || e.name || '').trim().replace(/\\s+/g, ' ').slice(0, 60);
            const role = e.getAttribute('role') || ({A: 'link', BUTTON: 'button', SELECT: 'combobox', TEXTAREA: 'textbox'}[e.tagName]) ||
              (e.tagName === 'INPUT' ? ({checkbox: 'checkbox', radio: 'radio', submit: 'button', button: 'button'}[e.type] || 'textbox') : e.tagName.toLowerCase());
            out.push({role, name, type: e.type || undefined, required: e.required || undefined, href: e.getAttribute('href') || undefined});
          });
          return out.slice(0, 120);
        }""")
        print(f"# {page.title()}  {page.url}")
        for i in items:
            if not i["name"]:
                continue
            extra = (" required" if i.get("required") else "") + (f" -> {i['href']}" if i.get("href") else "")
            print(f'role={i["role"]}[name="{i["name"]}"]{extra}')
        br.close()


def launch_ctx(p, spec, task_dir, video, dpr=2):
    br = launch(p)
    vw, vh = spec.get("viewport", [1440, 900])
    state = spec.get("state")
    kw = dict(viewport={"width": vw, "height": vh}, device_scale_factor=dpr,
              storage_state=state if state and os.path.exists(state) else None)
    if video:
        kw.update(record_video_dir=task_dir, record_video_size={"width": min(vw, 1280), "height": int(min(vw, 1280) * vh / vw)})
    return br, br.new_context(**kw)


def make_frame(out_dir, vid_w, vid_h, title, dark=False):
    """Window-style frame: soft backdrop, rounded window with a title bar and three dots, drop shadow.
    Returns (background_png, mask_png, (x, y), (canvas_w, canvas_h)). The video is laid over the hole."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import theme
    pad, bar, rad = 70, 44, 16
    W, H = vid_w + 2 * pad, vid_h + bar + 2 * pad
    W, H = W - W % 2, H - H % 2
    bg = Image.new("RGB", (W, H), theme.hex_rgb(theme.PALETTE["bone"]))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 14, pad + vid_w, pad + bar + vid_h + 14], rad, fill=(35, 31, 32, 85))
    bg.paste(sh.filter(ImageFilter.GaussianBlur(26)), (0, 0), sh.filter(ImageFilter.GaussianBlur(26)))
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([pad, pad, pad + vid_w, pad + bar + vid_h], rad, fill=(246, 247, 249))
    d.rounded_rectangle([pad, pad, pad + vid_w, pad + bar + rad], rad, fill=(236, 238, 241))
    d.rectangle([pad, pad + bar - 1, pad + vid_w, pad + bar], fill=(214, 217, 222))
    for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        cx = pad + 24 + i * 24
        d.ellipse([cx - 7, pad + bar / 2 - 7, cx + 7, pad + bar / 2 + 7], fill=c)
    try:
        f = ImageFont.truetype(theme.font_path("semibold"), 15)
        tw = d.textlength(title, font=f)
        d.text((pad + vid_w / 2 - tw / 2, pad + bar / 2 - 9), title, font=f, fill=(95, 101, 113))
    except Exception:
        pass
    mask = Image.new("L", (vid_w, vid_h), 255)
    m = Image.new("L", (vid_w * 2, vid_h * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, -rad * 4, vid_w * 2 - 1, vid_h * 2 - 1], rad * 2, fill=255)
    mask = m.resize((vid_w, vid_h), Image.LANCZOS)
    bgp, mp = os.path.join(out_dir, "frame-bg.png"), os.path.join(out_dir, "frame-mask.png")
    bg.save(bgp)
    mask.save(mp)
    return bgp, mp, (pad, pad + bar), (W, H)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)



def sm(a):
    c = f"clip({a},0,1)"
    return f"({c}*{c}*(3-2*{c}))"


def zoom_expr(zooms, w, h, zmax, ramp=0.55, fps=25):
    """zoompan expressions: ease in toward each target, hold, ease out. zooms = [(t_in, t_out, cx, cy)] in seconds and video px."""
    T = f"(on/{fps})"
    bumps = [f"({sm(f'(({T}-{a})/{ramp})')}-{sm(f'(({T}-{b})/{ramp})')})" for a, b, _, _ in zooms]
    z = "1+" + f"({zmax}-1)*min(1," + "+".join(bumps) + ")" if bumps else "1"
    cx = f"{w}/2+" + "+".join(f"{bp}*({c[2]}-{w}/2)" for bp, c in zip(bumps, zooms)) if bumps else f"{w}/2"
    cy = f"{h}/2+" + "+".join(f"{bp}*({c[3]}-{h}/2)" for bp, c in zip(bumps, zooms)) if bumps else f"{h}/2"
    return z, f"clip({cx}-iw/zoom/2,0,iw-iw/zoom)", f"clip({cy}-ih/zoom/2,0,ih-ih/zoom)"


def make_card(out_dir, name, size, headline, sub, accent, kicker):
    """Title or end card in the BeForth look: paper background, ink headline, accent bar."""
    from PIL import Image, ImageDraw
    import theme
    W, H = size
    img = Image.new("RGB", (W, H), theme.hex_rgb(theme.PALETTE["paper"]))
    d = ImageDraw.Draw(img)
    big = theme.font_for(headline, int(H * 0.075), "bold")
    mid = theme.font_for(sub, int(H * 0.034), "regular")
    small = theme.font_for(kicker, int(H * 0.026), "semibold")
    x = int(W * 0.1)
    words, lines, cur = headline.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=big) > W * 0.8 and cur:
            lines.append(cur); cur = wd
        else:
            cur = t
    lines.append(cur)
    lh = int(H * 0.095)
    y = int(H * 0.5 - (len(lines) * lh) / 2 - H * 0.03)
    d.rectangle([x, y - int(H * 0.09), x + int(W * 0.06), y - int(H * 0.09) + 8], fill=theme.hex_rgb(accent))
    d.text((x, y - int(H * 0.075)), kicker.upper(), font=small, fill=theme.hex_rgb(accent))
    for ln in lines:
        d.text((x, y), ln, font=big, fill=theme.hex_rgb(theme.PALETTE["ink"]))
        y += lh
    d.text((x, y + int(H * 0.02)), sub, font=mid, fill=theme.hex_rgb(theme.PALETTE["ash"]))
    path = os.path.join(out_dir, name)
    img.save(path)
    return path


def add_cards(mp4, cards, size, has_audio):
    """Second pass: title card, then the recording, then an end card. Measures the real length of the
    recording so nothing is cut."""
    (ip, idur), (op, odur) = cards
    mdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                                capture_output=True, text=True).stdout.strip() or 0)
    tmp = mp4 + ".tmp.mp4"
    W, H = size
    g = (f"[0:v]scale={W}:{H},setsar=1,fps=25,format=yuv420p[ci];[1:v]scale={W}:{H},setsar=1,fps=25,format=yuv420p[cm];"
         f"[2:v]scale={W}:{H},setsar=1,fps=25,format=yuv420p[co];[ci][cm][co]concat=n=3:v=1:a=0[v]")
    args = ["-map", "[v]"]
    if has_audio:
        ms = int(idur * 1000)
        g += f";[1:a]adelay={ms}|{ms},apad[a]"
        args += ["-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "25", "-t", str(idur), "-i", ip, "-i", mp4,
           "-loop", "1", "-framerate", "25", "-t", str(odur), "-i", op, "-filter_complex", g, *args,
           "-t", f"{idur + mdur + odur:.2f}", "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", tmp]
    if subprocess.run(cmd, check=False).returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, mp4)


def to_gif(webm, out_gif, out_mp4, title="", framed=True, clips=None, zooms=None, zmax=1.3, cards=None):
    """MP4 and GIF from the raw recording. Framed puts it in a window (title bar, rounded corners,
    shadow) on a soft backdrop, so it looks like a polished screen recording."""
    if not shutil.which("ffmpeg"):
        return None
    work = os.path.dirname(webm)
    if framed:
        w, h = probe(webm)
        w, h = w - w % 2, h - h % 2
        bgp, mp, (x, y), (cw, ch) = make_frame(work, w, h, title)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", webm],
                             capture_output=True, text=True).stdout.strip() or "30"
        zf = f"scale={w}:{h}"
        if zooms:
            z, zx, zy = zoom_expr(zooms, w * 2, h * 2, zmax)
            zf = f"scale={w * 2}:{h * 2}:flags=lanczos,zoompan=z='{z}':x='{zx}':y='{zy}':d=1:s={w}x{h}:fps=25"
        graph = (f"[0:v]{zf},format=rgba[v];[2:v]format=gray[m];[v][m]alphamerge[vm];"
                 f"[1:v][vm]overlay={x}:{y}:format=auto:shortest=1,format=yuv420p[out]")
        final_size = (cw, ch)
        inputs = ["-i", webm, "-loop", "1", "-framerate", "25", "-i", bgp, "-loop", "1", "-framerate", "25", "-i", mp]
        first_audio = 3
    else:
        graph = "[0:v]format=yuv420p[out]"
        final_size = probe(webm)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", webm],
                             capture_output=True, text=True).stdout.strip() or "30"
        inputs = ["-i", webm]
        first_audio = 1
    audio_args = []
    if clips:
        parts = []
        for k, (path, ms) in enumerate(clips):
            inputs += ["-i", path]
            parts.append(f"[{first_audio + k}:a]adelay={ms}|{ms}[a{k}]")
        mix = "".join(f"[a{k}]" for k in range(len(clips))) + (f"amix=inputs={len(clips)}:normalize=0:duration=longest[aout]" if len(clips) > 1 else "anull[aout]")
        graph += ";" + ";".join(parts) + ";" + mix
        audio_args = ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k"]
    mapping = ["-filter_complex", graph, "-map", "[out]", *audio_args, "-t", str(dur)]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, *mapping, "-c:v", "libx264", "-crf", "20",
                    "-movflags", "+faststart", out_mp4], check=False)
    if cards and os.path.exists(out_mp4):
        add_cards(out_mp4, cards, final_size, bool(clips))
    pal = out_gif + ".png"
    vf = "fps=15,scale=900:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out_mp4, "-vf", vf + ",palettegen=stats_mode=diff", pal], check=False)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out_mp4, "-i", pal, "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5", out_gif], check=False)
    try:
        os.remove(pal)
    except OSError:
        pass
    return out_gif if os.path.exists(out_gif) else None


DD_JS = """(el, [value, hi, accent]) => {
  document.getElementById('__dd')?.remove();
  if (el.tagName !== 'SELECT') return null;
  const opts = [...el.options];
  let idx = opts.findIndex(o => o.value === value || o.text.trim() === value);
  if (idx < 0) idx = Math.max(0, el.selectedIndex);
  const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
  const fs = Math.max(14, parseFloat(cs.fontSize) || 14), rh = Math.round(fs * 2.3), maxRows = 7;
  const start = Math.max(0, Math.min(idx - 2, opts.length - maxRows)), end = Math.min(opts.length, start + maxRows);
  const h = (end - start) * rh + 12, below = innerHeight - r.bottom;
  const top = below > h + 8 ? r.bottom + 4 : Math.max(4, r.top - h - 4);
  const box = document.createElement('div'); box.id = '__dd';
  box.style.cssText = `position:fixed;z-index:2147483645;pointer-events:none;left:${r.left}px;top:${top}px;min-width:${Math.max(r.width, 160)}px;` +
    `padding:6px;background:#fff;border:1px solid rgba(0,0,0,.14);border-radius:10px;box-sizing:border-box;` +
    `box-shadow:0 10px 30px rgba(0,0,0,.18),0 2px 6px rgba(0,0,0,.08);font:${cs.fontWeight} ${fs}px ${cs.fontFamily};color:#1d1d1f`;
  const rows = [];
  for (let i = start; i < end; i++) {
    const d = document.createElement('div');
    d.textContent = opts[i].text.trim() || ' ';
    const on = hi && i === idx;
    d.style.cssText = `height:${rh}px;line-height:${rh}px;padding:0 12px;border-radius:6px;white-space:nowrap;` + (on ? `background:${accent};color:#fff` : '');
    box.appendChild(d); rows.push(d);
  }
  document.body.appendChild(box);
  const rects = rows.map(d => { const q = d.getBoundingClientRect(); return [q.left, q.top, q.width, q.height]; });
  return {rows: rects, row: idx - start, label: opts[idx] ? opts[idx].text.trim() : ''};
}"""


def dd_open(page, target, value, accent, hi):
    """Draw an open dropdown under a native <select>, which the browser would not show in a screenshot.
    Returns the row boxes, or None for anything that is not a native select."""
    try:
        return page.locator(target).first.evaluate(DD_JS, [value, hi, accent])
    except Exception:
        return None


def dd_close(page):
    page.evaluate("document.getElementById('__dd')?.remove()")


CHIP = {"en": "Step {i} of {n}", "hi": "चरण {i} / {n}", "mr": "पायरी {i} / {n}"}
OUTRO = {"en": ("That is it. You are done.", "More tasks are in the full guide."),
         "hi": ("बस, हो गया।", "और काम पूरी गाइड में देखें।"),
         "mr": ("झालं, काम पूर्ण।", "आणखी कामे पूर्ण मार्गदर्शकात पाहा।")}


def studio_step(S, page, st, i, n, action, tgt_box, boxes, texts, audios, dsec, spec, look_only):
    """One step in studio mode: advance the virtual clock, lay out caption, cursor, zoom and ring, and run the action."""
    vw = S.vw
    chips = {l: CHIP.get(l, CHIP["en"]).format(i=i, n=n) if n > 1 else "" for l in texts}
    read = max(min(2.6, 0.7 + 0.024 * max(len(t) for t in texts.values())), dsec + 0.35)
    t_cap = S.t
    cap_end = None
    for lg, a in audios.items():
        S.audio.append((a, S.t + 0.15, lg))
    if boxes and (look_only or spec.get("highlight") == "full"):
        for b in boxes:
            S.rings.append((S.t + 0.25, S.t + read + 0.5, b))
    S.t += read
    if tgt_box is not None and action:
        tx, ty = tgt_box[0] + tgt_box[2] / 2, tgt_box[1] + tgt_box[3] / 2
        dist = math.hypot(tx - S.pos[0], ty - S.pos[1])
        dur = 0.6 + min(0.7, dist / (vw * 1.3))
        z_in = S.t
        cap_end = z_in + 0.3          # the sentence is done once the cursor moves; keeps the caption off open lists
        S.cursor.append((round(S.t, 3), round(S.t + dur, 3), S.pos[0], S.pos[1], tx, ty))
        S.t += dur
        S.pos = [tx, ty]
        t_click = S.t
        if action in ("click", "fill", "select"):
            S.clicks.append(round(t_click, 3))
        page.mouse.move(tx, ty)
        hold_after = 0.6
        dd = dd_open(page, st["select"][0], st["select"][1], S.accent, False) if action == "select" and isinstance(st["select"], list) else None
        if dd:
            # native dropdown: show the list opening, glide to the option, highlight it, click it
            S.snap(page, t_click + 0.05, fade=0.15)
            row = dd["rows"][dd["row"]]
            rx, ry = row[0] + min(row[2] * 0.4, 90), row[1] + row[3] / 2
            S.t = t_click + 0.45
            S.cursor.append((round(S.t, 3), round(S.t + 0.55, 3), tx, ty, rx, ry))
            S.t += 0.55
            S.pos = [rx, ry]
            dd_open(page, st["select"][0], st["select"][1], S.accent, True)
            S.snap(page, S.t, fade=0.1)
            S.t += 0.3
            S.clicks.append(round(S.t, 3))
            page.locator(st["select"][0]).first.select_option(st["select"][1])
            dd_close(page)
            t_click = S.t
            ty = (ty + ry) / 2
        elif action == "click":
            page.locator(st["click"]).first.click(timeout=8000)
        elif action == "fill":
            loc = page.locator(st["fill"][0]).first
            loc.click()
            loc.fill("")
            val = st["fill"][1]
            S.t = t_click + 0.25
            step = max(1, math.ceil(len(val) / 28))
            for k in range(0, len(val), step):
                chunk = val[k:k + step]
                page.keyboard.type(chunk)
                S.t += 0.07 * len(chunk)
                S.snap(page, S.t, fade=0.0)
            t_click = S.t - 0.06
        elif action == "select":
            page.locator(st["select"][0]).first.select_option(st["select"][1])
        elif action == "press":
            page.keyboard.press(st["press"])
        if "wait" in st:
            w = st["wait"]
            page.wait_for_timeout(w) if isinstance(w, int) else page.wait_for_selector(w, timeout=10000)
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        page.wait_for_timeout(250)
        if action != "fill":
            S.snap(page, t_click + 0.05, fade=0.18)
        S.t = max(S.t, t_click + 0.05) + hold_after
        if spec.get("zoom", True):
            S.zooms.append((round(z_in, 3), round(S.t, 3), tx, ty))
    elif action:
        if action == "press":
            page.keyboard.press(st["press"])
        if "wait" in st:
            w = st["wait"]
            page.wait_for_timeout(w) if isinstance(w, int) else page.wait_for_selector(w, timeout=10000)
        page.wait_for_timeout(250)
        S.snap(page, S.t + 0.05, fade=0.18)
        S.t += 0.6
    else:
        S.t += 0.3
    S.captions.append((round(t_cap, 3), round(cap_end if cap_end else S.t + 0.15, 3), texts, chips))


def make_gif(mp4, out_gif):
    pal = out_gif + ".png"
    vf = "fps=15,scale=900:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", vf + ",palettegen=stats_mode=diff", pal], check=False)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-i", pal, "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5", out_gif], check=False)
    try:
        os.remove(pal)
    except OSError:
        pass
    return out_gif if os.path.exists(out_gif) else None


def run_task(p, spec, ws, task, video, accent):
    env = spec.get("env", "staging")
    base = spec.get("base", "").rstrip("/")
    slug = task["slug"]
    shots = os.path.join(ws, "shots")
    gifs = os.path.join(ws, "gifs")
    tmp = os.path.join(ws, "build", f"video-{slug}")
    for d in (shots, gifs, tmp):
        os.makedirs(d, exist_ok=True)
    studio = bool(video and spec.get("engine", "studio") != "live" and shutil.which("ffmpeg"))
    vw, vh = spec.get("viewport", [1440, 900])
    S = None
    if studio:
        import studio as studio_mod
        S = studio_mod.Timeline(tmp, vw, vh, accent, spec.get("app") or task["title"], spec.get("quality", "4k"),
                                float(spec.get("zoom_level", 1.3)) if spec.get("zoom", True) else 1.0)
        br, ctx = launch_ctx(p, spec, tmp, False, dpr=S.dpr())
    else:
        br, ctx = launch_ctx(p, spec, tmp, video)
    page = ctx.new_page()
    steps_out = []
    cur = [vw * 0.5, vh * 0.62]     # where the on-screen cursor is
    voice = spec.get("voice")
    vname = voice.get("name") if isinstance(voice, dict) else None
    vrate = int(voice.get("rate", 170)) if isinstance(voice, dict) else 170
    vnames = {"en": vname, **((voice.get("voices") or {}) if isinstance(voice, dict) else {})}
    langs = [l for l in (spec.get("langs") or ["en"])]
    zooms, zin = [], None
    vid_sc = min(vw, 1280) / vw
    clips, t0 = [], time.time()     # narration clips with their start time in the recording
    for i, st in enumerate(task["steps"], 1):
        if "goto" in st:
            url = st["goto"] if st["goto"].startswith("http") else base + st["goto"]
            page.goto(url, wait_until="networkidle")
            if S:
                page.wait_for_timeout(300)
                S.snap(page, S.t, fade=0.3)
        action = next((k for k in WRITE_ACTIONS if k in st), None)
        if env == "production" and action:
            die(f"{slug} step {i}: production is look-only, so '{action}' is not allowed. Use a staging or local copy.")
        if "fill" in st:
            t = page.locator(st["fill"][0]).first
            if (t.get_attribute("type") or "").lower() == "password":
                die(f"{slug} step {i}: will not type into a password field. Sign in with the login command instead.")
        marks_in = list(st.get("marks") or [])
        if not marks_in and action in ("click", "fill", "select"):
            tgt = st[action][0] if isinstance(st[action], list) else st[action]
            marks_in = [{"target": tgt}]
        out = {"text": st["text"]}
        boxes = []
        want_shot = bool(marks_in) or st.get("shot") or st.get("blur")
        if want_shot:
            for m in marks_in:
                boxes.append(box_of(page, m["target"]))
            blur_boxes = [box_of(page, t) for t in st.get("blur", [])]
            png = os.path.join(shots, f"{slug}-{i}.png")
            dd = dd_open(page, st["select"][0], st["select"][1], accent, True) if action == "select" and isinstance(st["select"], list) else None
            page.screenshot(path=png)      # a native select list is drawn by us, the browser would not show it
            if dd:
                dd_close(page)
                if len(marks_in) < 2:
                    marks_in.append({"target": "(option)", "style": "rect", "pad": 1.5})
                    boxes.append(dd["rows"][dd["row"]])
            out["image"] = os.path.relpath(png, ws)
            marks = [{"n": n + 1, "box": b, "style": m.get("style", "rect"), **({"pad": m["pad"]} if "pad" in m else {})} for n, (m, b) in enumerate(zip(marks_in, boxes))]
            marks += [{"box": b, "style": "blur"} for b in blur_boxes]
            out["marks"] = marks
        for k in ("tip", "warning"):
            if st.get(k):
                out[k] = st[k]
        tx = ty = None
        if S:
            if not S.stills:
                S.snap(page, 0.0)
            tgt = None
            if action in ("click", "fill", "select"):
                tgt = st[action][0] if isinstance(st[action], list) else st[action]
            tb = None
            if tgt:
                tb = boxes[[m["target"] for m in marks_in].index(tgt)] if tgt in [m["target"] for m in marks_in] else box_of(page, tgt)
            texts = {"en": plain(st["text"])}
            for lg in langs:
                texts[lg] = plain((st.get("i18n") or {}).get(lg) or st["text"])
            audios, dsec = {}, 0.0
            if voice:
                for lg, tx_ in texts.items():
                    if lg != "en" and lg not in langs:
                        continue
                    a = speak(tx_, os.path.join(tmp, f"voice{i}-{lg}"), vnames.get(lg), vrate, lg)
                    if a:
                        audios[lg] = a
                        dsec = max(dsec, audio_len(a))
            studio_step(S, page, st, i, len(task["steps"]), action, tb, boxes, texts, audios, dsec, spec, bool(boxes) and not tgt)
        elif video:
            tgt = None
            if action in ("click", "fill", "select"):
                tgt = st[action][0] if isinstance(st[action], list) else st[action]
            if boxes:
                b = boxes[0] if tgt is None else (box_of(page, tgt) if tgt not in [m["target"] for m in marks_in] else boxes[[m["target"] for m in marks_in].index(tgt)])
                tx, ty = b[0] + b[2] / 2, b[1] + b[3] / 2
            page.evaluate(CURSOR_JS, [cur[0], cur[1], accent])
            audio, dsec = None, 0.0
            if voice:
                audio = speak(plain(st["text"]), os.path.join(tmp, f"voice{i}"), vname, vrate)
                dsec = audio_len(audio) if audio else 0.0
            read_ms = max(min(2600, 700 + 24 * len(plain(st["text"]))), int(dsec * 1000 + 350))
            if boxes:
                hl = spec.get("highlight", "auto")
                mode = hl if hl in ("full", "caption") else ("caption" if tgt else "ring")
                page.evaluate(OVERLAY_JS, [boxes, plain(st["text"]), accent, mode, f"Step {i} of {len(task['steps'])}" if len(task['steps']) > 1 else ""])
            if audio:
                clips.append((audio, int((time.time() - t0) * 1000) + 150))
            if boxes or audio:
                page.wait_for_timeout(read_ms)   # time to read the caption, or to hear it
            if tx is not None and action:
                if spec.get("zoom", True) and boxes:
                    page.evaluate("(() => { const o = document.getElementById('__dy'); if (o) o.style.opacity = 0; })()")
                    page.wait_for_timeout(300)
                    zin = (time.time() - t0) + 0.15
                page.evaluate(MOVE_JS, [tx, ty])
                page.wait_for_timeout(750)                                  # cursor glides to the target
                page.evaluate(RIPPLE_JS, [tx, ty, accent]) if action == "click" else None
                page.wait_for_timeout(250)
                cur[0], cur[1] = tx, ty
        if S:
            pass
        elif action == "click":
            page.locator(st["click"]).first.click(timeout=8000)
        elif action == "fill":
            if video:
                loc = page.locator(st["fill"][0]).first
                loc.click()
                loc.fill("")
                page.keyboard.type(st["fill"][1], delay=70)
            else:
                page.locator(st["fill"][0]).first.fill(st["fill"][1])
        elif action == "select":
            page.locator(st["select"][0]).first.select_option(st["select"][1])
        elif action == "press":
            page.keyboard.press(st["press"])
        if S:
            steps_out.append(out)
            continue
        if "wait" in st:
            w = st["wait"]
            page.wait_for_timeout(w) if isinstance(w, int) else page.wait_for_selector(w, timeout=10000)
        if action:
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
        if video and zin is not None:
            zooms.append((round(zin, 2), round((time.time() - t0) + 0.15 + 0.35, 2), round(tx * vid_sc, 1), round(ty * vid_sc, 1)))
            zin = None
        if video:
            page.evaluate("(() => { const o = document.getElementById('__dy'); if (o) o.style.opacity = 0; })()")
            page.wait_for_timeout(600 if not boxes else 450)
            page.evaluate("document.getElementById('__dy')?.remove()")
        steps_out.append(out)
    feat = {"title": task["title"], "goal": task.get("goal", ""), "steps": steps_out}
    if task.get("before"):
        feat["before"] = task["before"]
    if task.get("fields"):
        feat["fields"] = task["fields"]
    if task.get("cheat", True):
        feat["cheat"] = True
    vpath = page.video.path() if (video and not S) else None
    ctx.close()
    br.close()
    if S:
        W_, H_, _ = studio_mod.QUALITY[S.quality]
        app = spec.get("app") or "User guide"
        for n_, lg in enumerate(langs):
            intro = outro = None
            if spec.get("cards", True):
                ti = (task.get("i18n") or {}).get(lg) or {}
                o1, o2 = OUTRO.get(lg, OUTRO["en"])
                intro = (make_card(tmp, f"intro-{lg}.png", (W_, H_), ti.get("title") or task["title"], ti.get("goal") or task.get("goal") or "", accent, app), 2.2)
                outro = (make_card(tmp, f"outro-{lg}.png", (W_, H_), o1, o2, accent, app), 1.8)
            name = slug if n_ == 0 else f"{slug}.{lg}"
            mp4 = os.path.join(gifs, f"{name}.mp4")
            print(f"rendering {name} ({lg}) at {S.quality} ...", file=sys.stderr)
            if S.render(mp4, intro, outro, voice_tail=0.2, lang=lg):
                g = make_gif(mp4, os.path.join(gifs, f"{name}.gif"))
                if g and n_ == 0:
                    feat["gif"] = os.path.relpath(g, ws)
    elif video and vpath and os.path.exists(vpath):
        cards = None
        if spec.get("cards", True) and shutil.which("ffmpeg"):
            vwid = min(vw, 1280)
            cw_, ch_ = vwid + 140, int(vwid * vh / vw) + 44 + 140
            cw_, ch_ = (cw_ - cw_ % 2, ch_ - ch_ % 2) if spec.get("frame", True) else (vwid, int(vwid * vh / vw))
            app = spec.get("app") or "User guide"
            cards = ((make_card(tmp, "intro.png", (cw_, ch_), task["title"], task.get("goal") or "", accent, app), 2.2),
                     (make_card(tmp, "outro.png", (cw_, ch_), "That is it. You are done.", "More tasks are in the full guide.", accent, app), 1.8))
        g = to_gif(vpath, os.path.join(gifs, f"{slug}.gif"), os.path.join(gifs, f"{slug}.mp4"),
                   title=spec.get("app") or task["title"], framed=spec.get("frame", True), clips=clips,
                   zooms=zooms if spec.get("zoom", True) else None, zmax=float(spec.get("zoom_level", 1.3)), cards=cards)
        if g:
            feat["gif"] = os.path.relpath(g, ws)
    shutil.rmtree(tmp, ignore_errors=True)
    return feat


def cmd_run(a):
    spec = json.load(open(a.spec))
    ws = a.ws
    state_json = os.path.join(ws, "state.json")
    accent = "#1C75BC"
    if os.path.exists(state_json):
        accent = ((json.load(open(state_json)).get("brand") or {}).get("accent")) or accent
    if os.path.exists(state_json) and not spec.get("app"):
        spec["app"] = json.load(open(state_json)).get("app") or ""
    if spec.get("state") and not os.path.isabs(spec["state"]):
        spec["state"] = os.path.join(ws, spec["state"])
    sp = pw()()
    feats = []
    t0 = time.time()
    with sp as p:
        for task in spec["tasks"]:
            if a.only and task["slug"] != a.only:
                continue
            feats.append(run_task(p, spec, ws, task, not a.no_video, accent))
            print(f"captured {task['slug']}: {len(feats[-1]['steps'])} steps")
    slug = spec.get("module", "tasks")
    mp = os.path.join(ws, "modules", f"{slug}.json")
    mod = json.load(open(mp)) if os.path.exists(mp) else {"title": spec.get("module_title", "Tasks"), "intro": "Step-by-step guides for everyday tasks."}
    mod["viewport"] = spec.get("viewport", [1440, 900])
    have = {f["title"]: f for f in mod.get("features", [])}
    for f in feats:
        have[f["title"]] = f
    order = [t["title"] for t in spec["tasks"]]
    mod["features"] = [have[t] for t in order if t in have] + [f for t, f in have.items() if t not in order]
    os.makedirs(os.path.dirname(mp), exist_ok=True)
    json.dump(mod, open(mp, "w"), indent=1)
    sj = os.path.join(ws, "state.json")
    if os.path.exists(sj) and slug not in json.load(open(sj)).get("modules", {}):
        subprocess.run([sys.executable, os.path.join(HERE, "progress.py"), "add-module", "--ws", ws, "--slug", slug, "--title", mod["title"]], check=False)
    print(f"wrote {mp} in {time.time() - t0:.1f}s. Next: check_boxes.py, annotate.py, build_pdf.py module --slug {slug}")


SAMPLES = {"en": "Open Leave type and choose Sick leave. The box now shows your choice.",
           "hi": "छुट्टी का प्रकार खोलें और बीमारी की छुट्टी चुनें। अब बॉक्स में आपकी पसंद दिखती है।",
           "mr": "रजेचा प्रकार उघडा आणि आजारपणाची रजा निवडा. आता बॉक्समध्ये तुमची निवड दिसते."}


def cmd_voices(a):
    """Make one audio sample per language with the same voice chain the videos use, so you can hear it first."""
    os.makedirs(a.out, exist_ok=True)
    for lg in a.langs.split(","):
        f = speak(SAMPLES.get(lg, SAMPLES["en"]), os.path.join(a.out, f"voice-{lg}"), None, 170, lg)
        print(f"{lg}: {f}" if f else f"{lg}: no voice engine worked (install edge-tts, or use a Mac, or set DOCYFY_TTS_CMD)")
    if _edge_broken:
        print("edge-tts did not work (not installed or no internet), so a fallback voice was used where one existed.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("login"); s.add_argument("--url", required=True); s.add_argument("--out", required=True); s.set_defaults(f=cmd_login)
    s = sub.add_parser("explore"); s.add_argument("--url", required=True); s.add_argument("--state"); s.add_argument("--wait"); s.set_defaults(f=cmd_explore)
    s = sub.add_parser("voices"); s.add_argument("--out", default="voice-samples"); s.add_argument("--langs", default="en,hi,mr"); s.set_defaults(f=cmd_voices)
    s = sub.add_parser("run"); s.add_argument("--ws", required=True); s.add_argument("--spec", required=True)
    s.add_argument("--no-video", action="store_true"); s.add_argument("--only"); s.set_defaults(f=cmd_run)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
