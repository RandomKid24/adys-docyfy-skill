#!/usr/bin/env python3
"""Fast, sharp capture. Runs Chrome on YOUR computer through Playwright, so pictures are 2x sharp,
boxes are measured exactly, and the video is edited as it records. No per-click round trips to Claude.

  capture.py login   --url URL --out ws/.auth/state.json     you sign in yourself, in a real window
  capture.py explore --url URL [--state S] [--wait CSS]       list clickable things as text (no images)
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
Safety: production is look-only (no click, fill, select, press). Password fields are never filled: sign in with
the login command instead. Use sample data in fill values.
"""
import argparse, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
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


OVERLAY_JS = """([boxes, caption, accent]) => {
  document.getElementById('__dy')?.remove();
  const root = document.createElement('div'); root.id = '__dy';
  root.style.cssText = 'position:fixed;inset:0;z-index:2147483647;pointer-events:none;font-family:system-ui,sans-serif';
  boxes.forEach((b, i) => {
    const hole = document.createElement('div');
    hole.style.cssText = `position:absolute;left:${b[0]-8}px;top:${b[1]-8}px;width:${b[2]+16}px;height:${b[3]+16}px;border-radius:9px;` +
      `box-shadow:0 0 0 9999px rgba(35,31,32,.12);outline:2.5px solid ${accent};outline-offset:-2px;background:transparent`;
    root.appendChild(hole);
    const n = document.createElement('div');
    n.textContent = i + 1;
    n.style.cssText = `position:absolute;left:${Math.max(4, b[0]-8-34)}px;top:${b[1]+b[3]/2-15}px;width:30px;height:30px;border-radius:50%;` +
      `background:${accent};color:#fff;font:800 16px/30px system-ui;text-align:center;box-shadow:0 0 0 3px #F2F7F9`;
    root.appendChild(n);
  });
  if (caption) {
    const c = document.createElement('div');
    c.textContent = caption;
    c.style.cssText = 'position:absolute;left:50%;bottom:28px;transform:translateX(-50%);max-width:70%;background:#231F20;color:#F2F7F9;' +
      'padding:12px 20px;font:600 18px/1.35 system-ui;border-left:5px solid ' + accent;
    root.appendChild(c);
  }
  document.body.appendChild(root);
}"""


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


def launch_ctx(p, spec, task_dir, video):
    br = launch(p)
    vw, vh = spec.get("viewport", [1440, 900])
    state = spec.get("state")
    kw = dict(viewport={"width": vw, "height": vh}, device_scale_factor=2,
              storage_state=state if state and os.path.exists(state) else None)
    if video:
        kw.update(record_video_dir=task_dir, record_video_size={"width": min(vw, 1280), "height": int(min(vw, 1280) * vh / vw)})
    return br, br.new_context(**kw)


def to_gif(webm, out_gif, out_mp4):
    if not shutil.which("ffmpeg"):
        return None
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_mp4], check=False)
    pal = out_gif + ".png"
    vf = "fps=10,scale=900:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-vf", vf + ",palettegen=stats_mode=diff", pal], check=False)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-i", pal, "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4", out_gif], check=False)
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
    br, ctx = launch_ctx(p, spec, tmp, video)
    page = ctx.new_page()
    vw, vh = spec.get("viewport", [1440, 900])
    steps_out = []
    for i, st in enumerate(task["steps"], 1):
        if "goto" in st:
            url = st["goto"] if st["goto"].startswith("http") else base + st["goto"]
            page.goto(url, wait_until="networkidle")
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
            page.screenshot(path=png)
            out["image"] = os.path.relpath(png, ws)
            marks = [{"n": n + 1, "box": b, "style": m.get("style", "rect")} for n, (m, b) in enumerate(zip(marks_in, boxes))]
            marks += [{"box": b, "style": "blur"} for b in blur_boxes]
            out["marks"] = marks
        for k in ("tip", "warning"):
            if st.get(k):
                out[k] = st[k]
        if video and boxes:        # the edited look in the recording: spotlight, numbers, caption
            page.evaluate(OVERLAY_JS, [boxes, plain(st["text"]), accent])
            page.wait_for_timeout(1100)
        if action == "click":
            page.locator(st["click"]).first.click(timeout=8000)
        elif action == "fill":
            page.locator(st["fill"][0]).first.fill(st["fill"][1])
        elif action == "select":
            page.locator(st["select"][0]).first.select_option(st["select"][1])
        elif action == "press":
            page.keyboard.press(st["press"])
        if "wait" in st:
            w = st["wait"]
            page.wait_for_timeout(w) if isinstance(w, int) else page.wait_for_selector(w, timeout=10000)
        if action:
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
        if video:
            page.evaluate("document.getElementById('__dy')?.remove()")
            page.wait_for_timeout(500)
        steps_out.append(out)
    feat = {"title": task["title"], "goal": task.get("goal", ""), "steps": steps_out}
    if task.get("before"):
        feat["before"] = task["before"]
    if task.get("fields"):
        feat["fields"] = task["fields"]
    if task.get("cheat", True):
        feat["cheat"] = True
    vpath = page.video.path() if video else None
    ctx.close()
    br.close()
    if video and vpath and os.path.exists(vpath):
        g = to_gif(vpath, os.path.join(gifs, f"{slug}.gif"), os.path.join(gifs, f"{slug}.mp4"))
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("login"); s.add_argument("--url", required=True); s.add_argument("--out", required=True); s.set_defaults(f=cmd_login)
    s = sub.add_parser("explore"); s.add_argument("--url", required=True); s.add_argument("--state"); s.add_argument("--wait"); s.set_defaults(f=cmd_explore)
    s = sub.add_parser("run"); s.add_argument("--ws", required=True); s.add_argument("--spec", required=True)
    s.add_argument("--no-video", action="store_true"); s.add_argument("--only"); s.set_defaults(f=cmd_run)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
