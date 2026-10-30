#!/usr/bin/env python3
"""Rank the guides worth writing first.

  plan.py --ws W --url APP [--state S] [--usage usage.csv] [--max-pages 25] [--register]

It reads the app's menu, visits each page, and turns the main buttons into candidate tasks.
Each task gets a score from 0 to 100 and a tier: first, next or later.

The score is an estimate from menu order, button names and form size, unless you give real
numbers. usage.csv has two columns, task and count (support tickets, analytics, help requests).
Tasks whose name matches a usage row use the count instead of the guess.

Writes <ws>/plan.md and <ws>/plan.json. plan.json also groups the tasks by menu page into modules.
--register adds each menu page to the workspace as a module, in menu order (needs progress.py init first).
"""
import argparse, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

VERBS = [  # (pattern, weight, why)
    (r"punch|clock|check.?in|check.?out", 32, "daily action"),
    (r"apply|request|raise|submit|claim", 26, "staff do this often"),
    (r"add|create|new|register|onboard", 20, "common setup task"),
    (r"approve|reject|review", 18, "managers do this daily"),
    (r"search|find|filter", 10, "frequent lookup"),
    (r"upload|import", 12, "needs care"),
    (r"export|download|print|report", 10, "regular need"),
    (r"edit|update|change", 8, "occasional"),
    (r"delete|archive|deactivate", 6, "rare and risky"),
]
HOT = r"dashboard|home|attendance|leave|timesheet|expense|payslip|salary|profile|task|ticket|order|invoice|customer|employee|candidate"
COLD = r"admin|setting|config|master|audit|log|role|permission|integration|backup|template"

NAV_JS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 2 && r.height > 2 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const roots = [...document.querySelectorAll('nav,aside,[role=navigation],[class*=sidebar i],[class*=menu i]')];
  const seen = new Set(), out = [];
  (roots.length ? roots : [document.body]).forEach(r => r.querySelectorAll('a[href]').forEach(a => {
    const href = a.href.split('#')[0];
    const name = (a.innerText || a.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
    if (!name || name.length > 40 || !vis(a) || seen.has(href) || !href.startsWith(location.origin) || /logout|sign.?out/i.test(name + href)) return;
    seen.add(href); out.push({name, href});
  }));
  return out;
}"""

PAGE_JS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 2 && r.height > 2 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const t = e => (e.innerText || e.value || e.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
  const buttons = [...document.querySelectorAll('button,a[role=button],[type=submit],a.btn,a[class*=button i]')].filter(vis).map(t).filter(x => x && x.length < 40);
  const fields = [...document.querySelectorAll('input,select,textarea')].filter(e => vis(e) && !['hidden','submit','button'].includes(e.type)).length;
  const h = document.querySelector('h1,h2');
  return {title: h ? t(h) : document.title, buttons: [...new Set(buttons)].slice(0, 20), fields, rows: document.querySelectorAll('tbody tr').length};
}"""


def score_task(task, page, position, total):
    """Return (score, reasons). Pure function so it can be tested without a browser."""
    name = f"{task} {page}".lower()
    s, why = 0, []
    pos = max(0, 22 - position * (22 / max(total, 1)))
    s += pos
    if position < 3:
        why.append("near the top of the menu")
    for pat, w, reason in VERBS:
        if re.search(pat, task.lower()):
            s += w
            why.append(reason)
            break
    if re.search(HOT, name):
        s += 14
        why.append("core area")
    if re.search(COLD, name):
        s -= 14
        why.append("admin or setup area, used rarely")
    return s, why


def tier(score, counted=False):
    hi, mid = (30, 10) if counted else (55, 35)
    return "first" if score >= hi else "next" if score >= mid else "later"


def build(items, usage=None):
    """items: [{task, page, position, total, fields, rows}]. usage: {name: count}. Returns ranked list."""
    out = []
    for it in items:
        s, why = score_task(it["task"], it["page"], it["position"], it["total"])
        s += min(14, it.get("fields", 0) * 1.4)
        if it.get("fields", 0) >= 6:
            why.append(f"{it['fields']} fields, easy to get wrong")
        row = dict(it, score=0, why=why, source="estimate")
        if usage:
            key = next((k for k in usage if k.lower() in f"{it['task']} {it['page']}".lower() or it["task"].lower() in k.lower()), None)
            if key:
                row["usage"] = usage[key]
                row["source"] = "usage file"
        row["raw"] = s
        out.append(row)
    if usage:
        mx = max([r["usage"] for r in out if "usage" in r] or [0])
        est = max([r["raw"] for r in out if "usage" not in r] or [1])
        for r in out:
            if "usage" in r and mx:
                r["raw"] = 100 * r["usage"] / mx
                r["why"].append(f"{r['usage']:g} requests in your usage file")
            else:
                r["raw"] = 30 * r["raw"] / est      # no count for this one: keep the guess, but below anything counted
    top = max([r["raw"] for r in out] or [1])
    for r in out:
        r["score"] = max(0, min(100, round(100 * r["raw"] / top)))
        r["tier"] = tier(r["score"], bool(usage))
        r.pop("raw")
    return sorted(out, key=lambda r: -r["score"])


def crawl(url, state, max_pages):
    from capture import pw, launch, cdp_state
    items = []
    with pw()() as p:
        br = launch(p)
        st = (cdp_state(br) if os.environ.get("DOCYFY_CDP") else None) or (state if state and os.path.exists(state) else None)
        page = br.new_context(storage_state=st, viewport={"width": 1440, "height": 900}).new_page()
        page.goto(url, wait_until="networkidle")
        nav = page.evaluate(NAV_JS)[:max_pages]
        if not nav:
            nav = [{"name": "Home", "href": page.url}]
        for pos, n in enumerate(nav):
            try:
                page.goto(n["href"], wait_until="networkidle", timeout=15000)
                d = page.evaluate(PAGE_JS)
            except Exception:
                continue
            name = n["name"]
            found = False
            for b in d["buttons"]:
                if any(re.search(pat, b.lower()) for pat, _, _ in VERBS):
                    items.append({"task": f"{b} ({name})", "page": name, "position": pos, "total": len(nav), "fields": d["fields"], "rows": d["rows"], "url": n["href"]})
                    found = True
            if d["rows"] and not found:
                items.append({"task": f"Find a record in {name}", "page": name, "position": pos, "total": len(nav), "fields": 0, "rows": d["rows"], "url": n["href"]})
            elif not found:
                items.append({"task": f"Use {name}", "page": name, "position": pos, "total": len(nav), "fields": d["fields"], "rows": 0, "url": n["href"]})
        br.close()
    return items


def slugify(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "page"


def modules_of(ranked):
    """Group tasks by menu page. Pages keep menu order; each page's score is its best task."""
    mods = {}
    for r in ranked:
        m = mods.setdefault(r["page"], {"slug": slugify(r["page"]), "title": r["page"], "position": r["position"], "url": r.get("url", ""), "tasks": []})
        m["tasks"].append({"task": r["task"], "score": r["score"], "tier": r["tier"]})
    out = sorted(mods.values(), key=lambda m: m["position"])
    for m in out:
        m["best"] = max(t["score"] for t in m["tasks"])
    return out


def write(ws, ranked, note):
    os.makedirs(ws, exist_ok=True)
    json.dump({"tasks": ranked, "modules": modules_of(ranked)}, open(os.path.join(ws, "plan.json"), "w"), indent=1)
    L = ["# Guide plan", "", note, "", "| Rank | Task | Score | Tier | Why |", "| --- | --- | --- | --- | --- |"]
    for i, r in enumerate(ranked, 1):
        L.append(f"| {i} | {r['task']} | {r['score']} | {r['tier']} | {', '.join(dict.fromkeys(r['why'])) or 'menu position'} |")
    L += ["", "## Modules in menu order", ""] + [f"{i}. {m['title']}: {len(m['tasks'])} tasks, best score {m['best']}" for i, m in enumerate(modules_of(ranked), 1)]
    L += ["", "Build the `first` tier, check the guides, then do `next`.", ""]
    open(os.path.join(ws, "plan.md"), "w").write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--state")
    ap.add_argument("--usage")
    ap.add_argument("--max-pages", type=int, default=25)
    ap.add_argument("--register", action="store_true")
    a = ap.parse_args()
    usage = None
    if a.usage:
        usage = {r[0].strip(): float(r[1]) for r in csv.reader(open(a.usage)) if len(r) > 1 and re.match(r"^[\d.]+$", r[1].strip())}
    ranked = build(crawl(a.url, a.state, a.max_pages), usage)
    note = ("Ranked with real counts from your usage file where a task matched." if usage else
            "This is an estimate from menu order, button names and form size. It is not real usage. "
            "Give a usage.csv (task,count) from support tickets or analytics for a better ranking.")
    write(a.ws, ranked, note)
    try:
        import journal
        journal.event(a.ws, f"Planned {len(ranked)} tasks: {sum(r['tier'] == 'first' for r in ranked)} in the first tier")
    except Exception:
        pass
    if a.register:
        import subprocess
        if not os.path.exists(os.path.join(a.ws, "state.json")):
            sys.exit("Run progress.py init first, then plan.py --register.")
        have = json.load(open(os.path.join(a.ws, "state.json"))).get("modules", {})
        for m in modules_of(ranked):
            if m["slug"] not in have:
                subprocess.run([sys.executable, os.path.join(HERE, "progress.py"), "add-module", "--ws", a.ws, "--slug", m["slug"], "--title", m["title"],
                                "--features", ",".join(t["task"] for t in m["tasks"])], check=False)
    print(f"{len(ranked)} candidate tasks. Top of the list:")
    for r in ranked[:10]:
        print(f"  {r['score']:>3}  {r['tier']:<5}  {r['task']}")
    print(f"Full list: {os.path.join(a.ws, 'plan.md')}")


if __name__ == "__main__":
    main()
