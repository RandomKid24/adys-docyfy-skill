#!/usr/bin/env python3
"""Update mode: find which guide steps are out of date without re-taking screenshots.

At capture time each step stores "fp", a short fingerprint of the visible
interactive elements (labels and rough positions) from `snippet`. After a release,
the agent revisits each screen, runs the snippet once (tiny output, no image),
and feeds the results here. Only steps whose fingerprint changed are marked stale.

  check_changes.py snippet
        print the JavaScript to run in the page (javascript_tool) at capture and recheck time
  check_changes.py list --ws W --module S
        print step keys ("featureIdx.stepIdx"), step text and stored fp, so the agent knows what to revisit
  check_changes.py compare --ws W --module S --fps '{"0.1":"a3f","0.2":"77b"}' [--apply]
        compare live fingerprints with stored ones. --apply marks changed steps "stale": true
        and sets the module status to capturing, so `progress.py next` returns it again.
  check_changes.py set-fp --ws W --module S --fps '{"0.1":"a3f"}'
        store fingerprints (at first capture) or refresh them (after re-capturing a stale step);
        this also clears "stale" on those steps.

Steps that use `common` are skipped, because shared screens are re-checked once through their own key.
"""
import argparse, json, os, sys

try:
    import journal as _journal
except Exception:
    _journal = None

def _jlog(ws, text, **m):
    if _journal:
        _journal.event(ws, text, **m)


SNIPPET = r"""(()=>{const sel='a,button,input,select,textarea,th,label,h1,h2,h3,[role=button],[role=tab],[role=menuitem]';
const els=[...document.querySelectorAll(sel)].filter(e=>{const r=e.getBoundingClientRect();
 return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&!e.closest('tbody')});
const sig=els.map(e=>{const r=e.getBoundingClientRect();
 return (e.innerText||e.placeholder||e.getAttribute('aria-label')||e.name||'').trim().slice(0,40)+'@'+Math.round(r.x/16)+','+Math.round(r.y/16)}).join('|');
let h=5381;for(const c of sig)h=((h*33)^c.charCodeAt(0))>>>0;return h.toString(16)})()"""


def mod_path(ws, slug):
    return os.path.join(ws, "modules", f"{slug}.json")


def iter_steps(mod):
    for fi, feat in enumerate(mod.get("features", [])):
        for si, st in enumerate(feat.get("steps", [])):
            yield f"{fi}.{si}", st


def parse_fps(a):
    if a.fps_file:
        with open(a.fps_file) as f:
            return json.load(f)
    if not a.fps:
        sys.exit("give --fps JSON or --fps-file")
    return json.loads(a.fps)


def cmd_list(a):
    mod = json.load(open(mod_path(a.ws, a.module)))
    for k, st in iter_steps(mod):
        if "common" in st:
            continue
        flag = " STALE" if st.get("stale") else ""
        print(f"{k}\t{st.get('fp','-')}\t{st.get('text','')[:70]}{flag}")


def cmd_set(a):
    p = mod_path(a.ws, a.module)
    mod = json.load(open(p))
    fps = parse_fps(a)
    n = 0
    for k, st in iter_steps(mod):
        if k in fps:
            st["fp"] = fps[k]
            st.pop("stale", None)
            n += 1
    json.dump(mod, open(p, "w"), indent=2)
    print(f"{a.module}: fingerprints stored for {n} steps")


def cmd_compare(a):
    p = mod_path(a.ws, a.module)
    mod = json.load(open(p))
    live = parse_fps(a)
    changed, unknown, same = [], [], 0
    for k, st in iter_steps(mod):
        if k not in live or "common" in st:
            continue
        old = st.get("fp")
        if old is None:
            unknown.append(k)
        elif old != live[k]:
            changed.append((k, st))
        else:
            same += 1
    for k, st in changed:
        print(f"CHANGED {k}: {st.get('text','')[:70]}")
    if unknown:
        print(f"no stored fingerprint for: {', '.join(unknown)} (use set-fp to store them)")
    print(f"{a.module}: {same} unchanged, {len(changed)} changed")
    _jlog(a.ws, f"Update check on {a.module}: {same} unchanged, {len(changed)} changed")
    if a.apply and changed:
        for _, st in changed:
            st["stale"] = True
        json.dump(mod, open(p, "w"), indent=2)
        sp = os.path.join(a.ws, "state.json")
        state = json.load(open(sp))
        state["modules"][a.module]["status"] = "capturing"
        state["modules"][a.module]["note"] = f"update: {len(changed)} stale steps"
        json.dump(state, open(sp, "w"), indent=2)
        print("marked stale and reopened module")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snippet")
    for name in ("list", "compare", "set-fp"):
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--module", required=True)
        if name != "list":
            sp.add_argument("--fps")
            sp.add_argument("--fps-file")
        if name == "compare":
            sp.add_argument("--apply", action="store_true")
    a = p.parse_args()
    if a.cmd == "snippet":
        print(SNIPPET)
    elif a.cmd == "list":
        cmd_list(a)
    elif a.cmd == "set-fp":
        cmd_set(a)
    else:
        cmd_compare(a)


if __name__ == "__main__":
    main()
