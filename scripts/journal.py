#!/usr/bin/env python3
"""Workspace memory for docyfy. Writes <ws>/docyfy.md.

docyfy.md lists the app, what was built, every task with its steps, and a dated
change log. A later agent reads the top of it instead of rescanning the workspace.
Other scripts call event() after they finish. Nothing here can break a build.

  python3 journal.py note --ws W --text "Client wants Hindi on all videos"
  python3 journal.py refresh --ws W
"""
import argparse, glob, hashlib, json, os, re, sys, time

MAX_LOG = 200
SHOW_LOG = 10


def now():
    return time.strftime("%Y-%m-%d %H:%M %Z").strip()


def _jp(ws):
    return os.path.join(ws, "journal.json")


def _load(ws):
    try:
        return json.load(open(_jp(ws)))
    except Exception:
        return {"created": now(), "log": [], "notes": [], "meta": {}, "tasks": {}}


def _save(ws, j):
    j["log"] = j["log"][-MAX_LOG:]
    json.dump(j, open(_jp(ws), "w"), indent=1, ensure_ascii=False)


def _json(path):
    try:
        return json.load(open(path))
    except Exception:
        return {}


def _plain(t):
    return re.sub(r"\s+", " ", str(t or "").replace("**", "")).strip()


def _sig(feat):
    keep = [[_plain(s.get("text")) for s in feat.get("steps", [])], feat.get("before"), feat.get("goal")]
    return hashlib.sha1(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:10]


def _track(ws, j):
    """Compare each task with the last refresh. Log new and changed ones."""
    stamp = now()
    for mp in sorted(glob.glob(os.path.join(ws, "modules", "*.json"))):
        slug = os.path.basename(mp)[:-5]
        for f in _json(mp).get("features", []):
            key = f"{slug}/{f.get('title')}"
            sig = _sig(f)
            t = j["tasks"].get(key)
            if t is None:
                j["tasks"][key] = {"v": 1, "sig": sig, "added": stamp, "updated": stamp}
                j["log"].append({"at": stamp, "text": f"Added task \"{f.get('title')}\" ({len(f.get('steps', []))} steps) in {slug}"})
            elif t["sig"] != sig:
                t.update(v=t["v"] + 1, sig=sig, updated=stamp)
                j["log"].append({"at": stamp, "text": f"Changed task \"{f.get('title')}\" to v{t['v']} ({len(f.get('steps', []))} steps) in {slug}"})


def _outputs(ws):
    rows = []
    def one(label, pattern):
        fs = glob.glob(os.path.join(ws, pattern), recursive=True)
        if fs:
            m = max(os.path.getmtime(x) for x in fs)
            rows.append((label, len(fs), time.strftime("%Y-%m-%d %H:%M", time.localtime(m)), pattern.split("*")[0].rstrip("/") or pattern))
    one("PDF guide", "final/user-guide.pdf")
    one("Word guide", "final/user-guide.docx")
    one("Help site", "final/site/index.html")
    one("Cheat sheets", "final/cheatsheets/*.pdf")
    one("Videos (mp4)", "gifs/*.mp4")
    one("GIFs", "gifs/*.gif")
    return rows


def refresh(ws):
    j = _load(ws)
    _track(ws, j)
    _save(ws, j)
    st = _json(os.path.join(ws, "state.json"))
    meta = j.get("meta", {})
    L = [f"# {st.get('app') or 'App'} guide memory", "",
         "Written by docyfy. Do not edit the tables by hand. Add decisions with `progress.py note`.", ""]
    L += ["## Summary", ""]
    for k, v in (("App", st.get("app")), ("URL", meta.get("base") or st.get("url")), ("Environment", meta.get("env")),
                 ("Scope", st.get("scope")), ("Languages", meta.get("langs")), ("Video quality", meta.get("quality")),
                 ("Window", meta.get("viewport")), ("Created", j.get("created")), ("Last updated", now())):
        if v:
            L.append(f"- {k}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
    L.append("")
    out = _outputs(ws)
    if out:
        L += ["## Outputs", "", "| Output | Files | Last built | Path |", "| --- | --- | --- | --- |"]
        L += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in out]
        L.append("")
    L += ["## Notes for the next agent", ""]
    L += [f"- {n['at']}: {n['text']}" for n in j["notes"][-15:]] or ["- None yet."]
    L += ["", "## Change log (newest first)", ""]
    log = j["log"][::-1]
    L += [f"- {e['at']}: {e['text']}" for e in log[:SHOW_LOG]] or ["- Nothing yet."]
    if len(log) > SHOW_LOG:
        L.append(f"- {len(log) - SHOW_LOG} older entries are in journal.json.")
    L += ["", "## Modules", ""]
    for slug in st.get("order", []):
        m = st.get("modules", {}).get(slug, {})
        L.append(f"- {m.get('title', slug)} (`{slug}`): {m.get('status', 'pending')}" + (f". {m['note']}" if m.get("note") else ""))
    L += ["", "## Tasks and steps", ""]
    for mp in sorted(glob.glob(os.path.join(ws, "modules", "*.json"))):
        slug = os.path.basename(mp)[:-5]
        for f in _json(mp).get("features", []):
            t = j["tasks"].get(f"{slug}/{f.get('title')}", {})
            L += [f"### {f.get('title')}", "",
                  f"Module `{slug}`. Version {t.get('v', 1)}. Added {t.get('added', '?')}. Updated {t.get('updated', '?')}."]
            if f.get("goal"):
                L.append(f"Goal: {_plain(f['goal'])}")
            if f.get("help_key"):
                L.append(f"Help key: `{f['help_key']}`")
            L.append("")
            for n, s in enumerate(f.get("steps", []), 1):
                L.append(f"{n}. {_plain(s.get('text'))}")
            L.append("")
    tmp = os.path.join(ws, "docyfy.md.tmp")
    open(tmp, "w").write("\n".join(L).rstrip() + "\n")
    os.replace(tmp, os.path.join(ws, "docyfy.md"))


def event(ws, text, **meta):
    """Log what a script just did, then rewrite docyfy.md. Never raises."""
    try:
        if not ws or not os.path.isdir(ws):
            return
        j = _load(ws)
        j["log"].append({"at": now(), "text": text})
        for k, v in meta.items():
            if v not in (None, "", []):
                j["meta"][k] = v
        _save(ws, j)
        refresh(ws)
    except Exception as e:
        print(f"(journal skipped: {e})", file=sys.stderr)


def note(ws, text):
    j = _load(ws)
    j["notes"].append({"at": now(), "text": text.strip()})
    _save(ws, j)
    refresh(ws)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["note", "refresh"])
    p.add_argument("--ws", required=True)
    p.add_argument("--text", default="")
    a = p.parse_args()
    if a.cmd == "note":
        if not a.text.strip():
            sys.exit("--text is required")
        note(a.ws, a.text)
    else:
        refresh(a.ws)
    print(os.path.join(a.ws, "docyfy.md"))


if __name__ == "__main__":
    main()
