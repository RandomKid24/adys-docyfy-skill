#!/usr/bin/env python3
"""Resumable progress tracking for docyfy.

The workspace holds state.json. Agents run `status` (a few lines) instead of
re-reading files, which keeps token use low and prevents repeated work.

Commands
  init        --ws W --app NAME --url URL [--scope all|specific] [--gifs] [--audience TXT]
  add-module  --ws W --slug S --title T [--features "A,B,C"]
  status      --ws W
  next        --ws W            print first module not yet built
  set         --ws W --module S --status pending|capturing|annotated|written|built|skipped [--note TXT]
  shot-register --ws W --key K --path P
  shot-get    --ws W --key K    exit 0 and print path if registered and present, else exit 1
"""
import argparse, json, os, shutil, sys, time

STATUSES = ["pending", "capturing", "annotated", "written", "built", "skipped"]
HERE = os.path.dirname(os.path.abspath(__file__))
COMMON_SRC = os.path.join(HERE, "..", "assets", "common.json")


def paths(ws):
    return os.path.join(ws, "state.json")


def load(ws):
    p = paths(ws)
    if not os.path.exists(p):
        sys.exit(f"no state.json in {ws}; run init first")
    with open(p) as f:
        return json.load(f)


def save(ws, st):
    st["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = paths(ws) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2)
    os.replace(tmp, paths(ws))


def cmd_init(a):
    for d in ["shots", "annotated", "modules", "build", "final", "gifs"]:
        os.makedirs(os.path.join(a.ws, d), exist_ok=True)
    if os.path.exists(paths(a.ws)):
        print("state.json exists, keeping it (resume).")
        return cmd_status(a)
    common_dst = os.path.join(a.ws, "common.json")
    if not os.path.exists(common_dst):
        shutil.copy(COMMON_SRC, common_dst)
    st = {"app": a.app, "url": a.url, "scope": a.scope, "gifs": a.gifs,
          "audience": a.audience, "modules": {}, "order": [], "shots": {},
          "brand": {"accent": a.accent, "logo": a.logo}}
    save(a.ws, st)
    print(f"initialised {a.ws}")


def cmd_add(a):
    st = load(a.ws)
    if a.slug not in st["modules"]:
        st["order"].append(a.slug)
        st["modules"][a.slug] = {"title": a.title, "status": "pending", "features": [], "note": ""}
    m = st["modules"][a.slug]
    m["title"] = a.title
    if a.features:
        m["features"] = [x.strip() for x in a.features.split(",") if x.strip()]
    save(a.ws, st)
    print(f"module {a.slug}: {len(m['features'])} features")


def cmd_status(a):
    st = load(a.ws)
    done = sum(1 for s in st["order"] if st["modules"][s]["status"] in ("built", "skipped"))
    print(f"{st['app']} | scope={st['scope']} gifs={st['gifs']} | {done}/{len(st['order'])} modules done | shots registered: {len(st['shots'])}")
    for s in st["order"]:
        m = st["modules"][s]
        extra = f" ({m['note']})" if m.get("note") else ""
        print(f"  [{m['status']:<9}] {s}: {m['title']} ({len(m['features'])} features){extra}")


def cmd_next(a):
    st = load(a.ws)
    for s in st["order"]:
        m = st["modules"][s]
        if m["status"] not in ("built", "skipped"):
            print(json.dumps({"slug": s, "title": m["title"], "status": m["status"], "features": m["features"]}))
            return
    print("ALL DONE")


def cmd_set(a):
    if a.status not in STATUSES:
        sys.exit(f"status must be one of {STATUSES}")
    st = load(a.ws)
    if a.module not in st["modules"]:
        sys.exit(f"unknown module {a.module}")
    st["modules"][a.module]["status"] = a.status
    if a.note is not None:
        st["modules"][a.module]["note"] = a.note
    save(a.ws, st)
    print(f"{a.module} -> {a.status}")


def cmd_shot_register(a):
    st = load(a.ws)
    if not os.path.exists(a.path):
        sys.exit(f"file not found: {a.path}")
    st["shots"][a.key] = os.path.relpath(a.path, a.ws) if os.path.isabs(a.path) else a.path
    save(a.ws, st)
    print(f"registered {a.key}")


def cmd_shot_get(a):
    st = load(a.ws)
    rel = st["shots"].get(a.key)
    if rel and os.path.exists(os.path.join(a.ws, rel)):
        print(rel)
        return
    sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *args):
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        for ar, kw in args:
            sp.add_argument(ar, **kw)
        sp.set_defaults(fn=fn)

    add("init", cmd_init, ("--app", {"required": True}), ("--url", {"default": ""}),
        ("--scope", {"default": "all"}), ("--gifs", {"action": "store_true"}),
        ("--audience", {"default": ""}), ("--accent", {"default": ""}), ("--logo", {"default": ""}))
    add("add-module", cmd_add, ("--slug", {"required": True}), ("--title", {"required": True}),
        ("--features", {"default": ""}))
    add("status", cmd_status)
    add("next", cmd_next)
    add("set", cmd_set, ("--module", {"required": True}), ("--status", {"required": True}),
        ("--note", {"default": None}))
    add("shot-register", cmd_shot_register, ("--key", {"required": True}), ("--path", {"required": True}))
    add("shot-get", cmd_shot_get, ("--key", {"required": True}))
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
