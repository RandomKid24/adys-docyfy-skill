#!/usr/bin/env python3
"""Hostable help site: searchable, one page per module, stable deep links.

  build_site.py --ws W         -> W/final/site/ (open index.html, or upload the folder anywhere)

Writes
  index.html, <module>.html      pages with a search box and a side menu
  assets/                        copies of the images, GIFs and diagrams the pages use
  search-index.js                data for the search box (works from file:// too)
  help-map.json                  "module/feature-key" -> "module.html#feature-key"
  cheatsheets/                   copied from W/final/cheatsheets if present

Use help-map.json for "?" buttons inside the app, so Add Customer opens exactly its section:
  window.open(HELP_BASE + helpMap["customers/add-a-customer"])
Feature keys come from the feature's `help_key` if set (keep these stable across releases),
otherwise from its title.
"""
import argparse, hashlib, html, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import theme
from build_pdf import accent_hex, apply_brand, before_lines, load_common, load_state, md, resolve_step, step_image
from diagram import flow_png

CSS = """
@font-face{font-family:'Plus Jakarta Sans';font-weight:400;src:url(assets/fonts/PlusJakartaSans-Regular.ttf)}@font-face{font-family:'Plus Jakarta Sans';font-weight:600;src:url(assets/fonts/PlusJakartaSans-SemiBold.ttf)}@font-face{font-family:'Plus Jakarta Sans';font-weight:700;src:url(assets/fonts/PlusJakartaSans-Bold.ttf)}@font-face{font-family:'Plus Jakarta Sans';font-weight:800;src:url(assets/fonts/PlusJakartaSans-ExtraBold.ttf)}:root{--a:%(accent)s;--ink:#231F20;--mut:#5F6571;--line:#d9d9da;--bg:#F2F7F9;--soft:#fff;--bone:#D6E7F1}
*{box-sizing:border-box}body{margin:0;font:16px/1.7 'Plus Jakarta Sans',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--line);display:flex;gap:16px;align-items:center;padding:10px 20px}
header a.brand{font-weight:700;color:var(--ink);text-decoration:none;white-space:nowrap}
.sw{position:relative;flex:1;max-width:520px}.sw input{width:100%%;padding:9px 12px;border:1px solid var(--line);border-radius:0;font:inherit;background:#fff}
#res{display:none;position:absolute;left:0;right:0;top:44px;background:#fff;border:1px solid var(--line);max-height:60vh;overflow:auto}
#res a{display:block;padding:8px 12px;color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}#res a:hover{background:var(--soft)}#res small{color:var(--mut)}
.wrap{display:flex;max-width:1200px;margin:0 auto}nav{width:260px;flex:none;padding:20px;position:sticky;top:62px;align-self:flex-start;max-height:calc(100vh - 62px);overflow:auto;font-size:14px}
nav a{display:block;color:var(--ink);text-decoration:none;padding:3px 0}nav a.m{font-weight:600;margin-top:10px}nav a.f{padding-left:12px;color:var(--mut)}nav a:hover{color:var(--a)}
main{flex:1;min-width:0;padding:24px 28px 80px}h1{font-size:32px;font-weight:800;letter-spacing:-.025em;margin:0 0 6px}h2{margin-top:44px;border-bottom:1px solid var(--line);padding-bottom:6px;font-weight:700}h2 a.anc{color:var(--line);text-decoration:none;margin-left:6px}
h3{margin-top:28px}.mut{color:var(--mut)}ol.steps{padding:0;list-style:none}ol.steps li{margin:22px 0}.n{display:inline-block;background:var(--a);color:#fff;border-radius:50%%;width:1.7em;height:1.7em;text-align:center;line-height:1.7em;margin-right:8px;font-weight:700;font-size:.9em}
img{max-width:100%%;border:1px solid var(--line);margin-top:8px}.tip{background:var(--bone);border-left:3px solid var(--a);padding:8px 12px}.warn{background:#fdecea;border-left:4px solid #c0392b;padding:8px 12px}
table.t{border-collapse:collapse;width:100%%;margin:12px 0}table.t th{background:var(--bone);text-align:left}table.t td,table.t th{padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
main table a,h3 a{color:var(--a)}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-top:20px}.card{border:1px solid var(--line);padding:16px 18px;text-decoration:none;color:var(--ink);background:var(--soft)}
.card:hover{border-color:var(--a)}.card b{display:block;font-size:17px}.card span{color:var(--mut);font-size:14px}.pdf{display:inline-block;margin:6px 0;padding:5px 12px;border:1px solid var(--a);border-radius:20px;color:var(--a);text-decoration:none;font-size:14px}
@media(max-width:900px){nav{display:none}main{padding:18px 16px 60px}}
@media print{header,nav{display:none}main{padding:0}}
"""

JS = """
(function(){var i=document.getElementById('q'),b=document.getElementById('res');if(!i)return;
i.addEventListener('input',function(){var q=i.value.toLowerCase().split(/\\s+/).filter(Boolean);b.innerHTML='';
if(!q.length){b.style.display='none';return}
var hits=(window.IDX||[]).map(function(e){var t=e.t.toLowerCase(),h=t+' '+e.x.toLowerCase();
if(!q.every(function(w){return h.indexOf(w)>-1}))return null;return{e:e,s:q.reduce(function(a,w){return a+(t.indexOf(w)>-1?3:1)},0)}})
.filter(Boolean).sort(function(a,b){return b.s-a.s}).slice(0,10);
if(!hits.length){var d=document.createElement('div');d.style.padding='10px 12px';d.textContent='No match. Try fewer or different words.';b.appendChild(d)}
hits.forEach(function(h){var a=document.createElement('a');a.href=h.e.u;var s=document.createElement('b');s.textContent=h.e.t;a.appendChild(s);
var sm=document.createElement('small');sm.textContent='  '+h.e.m;a.appendChild(sm);b.appendChild(a)});b.style.display='block'});
document.addEventListener('click',function(e){if(!b.contains(e.target)&&e.target!==i)b.style.display='none'})})();
"""


def slugify(t):
    s = re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")
    return s or "section"


def plain(t):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", t or "")


class Site:
    def __init__(self, ws):
        self.ws = ws
        self.state = load_state(ws)
        apply_brand(ws, self.state)
        self.common = load_common(ws, self.state)
        self.out = os.path.join(ws, "final", "site")
        self.assets = os.path.join(self.out, "assets")
        self.copied = {}
        self.helpmap = {}
        self.index = []
        ready = [s for s in self.state["order"] if self.state["modules"][s]["status"] == "built"]
        ready.sort(key=lambda s: {"quick-start": 0, "workflows": 1}.get(s, 2))
        if not ready:
            sys.exit("no built modules yet")
        self.ready = ready
        self.mods = {s: json.load(open(os.path.join(ws, "modules", f"{s}.json"))) for s in ready}
        self.keys = {}
        for s in ready:
            used, m = set(), {}
            for fi, feat in enumerate(self.mods[s].get("features", [])):
                m[("f", fi)] = self.unique(slugify(feat.get("help_key") or feat["title"]), used)
            for wi, wf in enumerate(self.mods[s].get("workflows", [])):
                m[("w", wi)] = self.unique(slugify(wf.get("help_key") or wf["title"]), used)
            if self.mods[s].get("problems"):
                m[("p", 0)] = self.unique("common-problems", used)
            self.keys[s] = m

    @staticmethod
    def unique(k, used):
        base, i = k, 2
        while k in used:
            k = f"{base}-{i}"
            i += 1
        used.add(k)
        return k

    def asset(self, path):
        if not path:
            return None
        src = path
        if not os.path.isabs(path):
            under_ws = os.path.join(self.ws, path)
            src = under_ws if os.path.exists(under_ws) else path  # callers pass either form
        if not os.path.exists(src):
            return None
        src = os.path.abspath(src)
        if src not in self.copied:
            os.makedirs(self.assets, exist_ok=True)
            name = hashlib.sha1(src.encode()).hexdigest()[:8] + "-" + os.path.basename(src)
            shutil.copy(src, os.path.join(self.assets, name))
            self.copied[src] = "assets/" + name
        return self.copied[src]

    def title(self, s):
        return self.mods[s].get("title") or self.state["modules"][s]["title"]

    def nav(self):
        out = ["<a class=m href='index.html'>All topics</a>"]
        for s in self.ready:
            out.append(f"<a class=m href='{s}.html'>{html.escape(self.title(s))}</a>")
            for fi, feat in enumerate(self.mods[s].get("features", [])):
                out.append(f"<a class=f href='{s}.html#{self.keys[s][('f', fi)]}'>{html.escape(feat['title'])}</a>")
            for wi, wf in enumerate(self.mods[s].get("workflows", [])):
                out.append(f"<a class=f href='{s}.html#{self.keys[s][('w', wi)]}'>{html.escape(wf['title'])}</a>")
        return "".join(out)

    def page(self, title, body, nav):
        app = html.escape(self.state["app"])
        return (f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                f"<title>{html.escape(title)} | {app} help</title><style>{CSS % {'accent': accent_hex()}}</style>"
                f"<header><a class=brand href='index.html'>{app} help</a><div class=sw>"
                "<input id=q type=search placeholder='Search the guide, for example: add customer' autocomplete=off><div id=res></div></div></header>"
                f"<div class=wrap><nav>{nav}</nav><main>{body}</main></div>"
                f"<script src='search-index.js'></script><script>{JS}</script></html>")

    def steps_html(self, feat):
        parts = ["<ol class=steps>"]
        texts = []
        for i, st in enumerate((resolve_step(x, self.common, self.ws, self.state) for x in feat.get("steps", [])), 1):
            parts.append(f"<li><span class=n>{i}</span>{md(st['text'])}")
            texts.append(plain(st["text"]))
            img = self.asset(step_image(st, self.ws))
            if img:
                parts.append(f"<br><img loading=lazy src='{img}' alt='Screenshot for step {i}: {html.escape(plain(st['text']))[:120]}'>")
            if st.get("warning"):
                parts.append(f"<p class=warn><b>Careful.</b> {md(st['warning'])}</p>")
            if st.get("tip"):
                parts.append(f"<p class=tip><b>Tip.</b> {md(st['tip'])}</p>")
            parts.append("</li>")
        parts.append("</ol>")
        return "".join(parts), " ".join(texts)

    def build_module(self, s):
        mod = self.mods[s]
        keys = self.keys[s]
        body = [f"<h1 id='{s}'>{html.escape(self.title(s))}</h1>"]
        if mod.get("intro"):
            body.append(f"<p class=mut>{html.escape(mod['intro'])}</p>")
        cs = os.path.join(self.ws, "final", "cheatsheets", f"{s}.pdf")
        if os.path.exists(cs):
            os.makedirs(os.path.join(self.out, "cheatsheets"), exist_ok=True)
            shutil.copy(cs, os.path.join(self.out, "cheatsheets", f"{s}.pdf"))
            body.append(f"<a class=pdf href='cheatsheets/{s}.pdf'>One-page cheat sheet (PDF, for printing)</a>")
        if mod.get("cheatsheet"):
            body.append("<table class=t><tr><th>I want to&hellip;<th>Go to</tr>" + "".join(
                f"<tr><td>{md(r.get('want',''))}<td>{md(r.get('go',''))}</tr>" for r in mod["cheatsheet"]) + "</table>")
            self.index.append({"t": f"{self.title(s)}: I want to...", "m": self.title(s), "u": f"{s}.html",
                               "x": " ".join(plain(r.get("want", "")) + " " + plain(r.get("go", "")) for r in mod["cheatsheet"])})
        self.helpmap[s] = f"{s}.html"
        self.index.append({"t": self.title(s), "m": "Module", "u": f"{s}.html", "x": mod.get("intro", "")})
        for fi, feat in enumerate(mod.get("features", [])):
            k = keys[("f", fi)]
            steps_html, texts = self.steps_html(feat)
            body.append(f"<section id='{k}'><h2>{html.escape(feat['title'])}<a class=anc href='#{k}' aria-label='Link to this section'>#</a></h2>")
            if feat.get("goal"):
                body.append(f"<p class=mut>{html.escape(feat['goal'])}</p>")
            if feat.get("gif"):
                g = self.asset(feat["gif"])
                if g:
                    body.append(f"<p><img loading=lazy src='{g}' alt='Animated walkthrough of {html.escape(feat['title'])}'></p>")
            elif feat.get("video"):
                g = self.asset(feat["video"])
                if g:
                    body.append(f"<p><video controls muted playsinline preload=metadata src='{g}' aria-label='Video walkthrough of {html.escape(feat['title'])}' style='max-width:100%'></video></p>")
            bl = before_lines(feat)
            if bl:
                body.append("<div class=tip><b>Before you start</b><br>" + "<br>".join(f"<b>{html.escape(a)}:</b> {md(b)}" for a, b in bl) + "</div>")
                texts += " " + " ".join(plain(b) for _, b in bl)
            body.append(steps_html)
            if feat.get("fields"):
                body.append("<h3>Fields on this screen</h3><table class=t><tr><th>Field<th>Required?<th>What to enter<th>Example</tr>" + "".join(
                    f"<tr><td>{md(f.get('name',''))}<td>{'<b>Required</b>' if f.get('required') else 'Optional'}<td>{md(f.get('help',''))}<td>{md(f.get('example',''))}</tr>"
                    for f in feat["fields"]) + "</table>")
                texts += " " + " ".join(plain(f.get("name", "")) + " " + plain(f.get("help", "")) for f in feat["fields"])
            body.append("</section>")
            self.helpmap[f"{s}/{k}"] = f"{s}.html#{k}"
            self.index.append({"t": feat["title"], "m": self.title(s), "u": f"{s}.html#{k}",
                               "x": plain(feat.get("goal", "")) + " " + texts})
        for wi, wf in enumerate(mod.get("workflows", [])):
            k = keys[("w", wi)]
            png = self.asset(os.path.relpath(flow_png(self.ws, wf, accent_hex()), self.ws))
            rows = []
            for i, f in enumerate(wf.get("flow", []), 1):
                label = md(f.get("label", ""))
                if f.get("link") and f["link"] in self.helpmap_future():
                    label = f"<a href='{self.helpmap_future()[f['link']]}'>{label}</a>"
                rows.append(f"<tr><td>{i}<td>{label}<td>{md(f.get('where',''))}<td>{md(f.get('note',''))}</tr>")
            body.append(f"<section id='{k}'><h2>{html.escape(wf['title'])}<a class=anc href='#{k}'>#</a></h2>"
                        + (f"<p class=mut>{html.escape(wf['goal'])}</p>" if wf.get("goal") else "")
                        + (f"<p><img loading=lazy src='{png}' alt='Workflow diagram: {html.escape(wf['title'])}'></p>" if png else "")
                        + "<table class=t><tr><th>#<th>What to do<th>Where<th>Note</tr>" + "".join(rows) + "</table></section>")
            self.helpmap[f"{s}/{k}"] = f"{s}.html#{k}"
            self.index.append({"t": wf["title"], "m": "Workflow", "u": f"{s}.html#{k}",
                               "x": plain(wf.get("goal", "")) + " " + " ".join(plain(f.get("label", "")) for f in wf.get("flow", []))})
        if mod.get("problems"):
            k = keys[("p", 0)]
            body.append(f"<section id='{k}'><h2>Common problems</h2><table class=t><tr><th>You see<th>Why it happens<th>What to do</tr>" + "".join(
                f"<tr><td>{md(p.get('message',''))}<td>{md(p.get('cause',''))}<td>{md(p.get('fix',''))}</tr>" for p in mod["problems"])
                + "</table></section>")
            self.helpmap[f"{s}/{k}"] = f"{s}.html#{k}"
            self.index.append({"t": f"{self.title(s)}: common problems", "m": "Problems", "u": f"{s}.html#{k}",
                               "x": " ".join(plain(p.get("message", "")) + " " + plain(p.get("fix", "")) for p in mod["problems"])})
        return "".join(body)

    def helpmap_future(self):
        """Predicted keys for links between workflow steps and sections (module/feature-key)."""
        if not hasattr(self, "_future"):
            self._future = {}
            for s in self.ready:
                for (kind, i), k in self.keys[s].items():
                    self._future[f"{s}/{k}"] = f"{s}.html#{k}"
        return self._future

    def build(self):
        os.makedirs(self.out, exist_ok=True)
        fdir = os.path.join(self.assets, "fonts")
        os.makedirs(fdir, exist_ok=True)
        for w in ("regular", "semibold", "bold", "extrabold"):
            fp = theme.font_path(w)
            if fp and "PlusJakarta" in fp:
                shutil.copy(fp, os.path.join(fdir, os.path.basename(fp)))
        nav = self.nav()
        for s in self.ready:
            body = self.build_module(s)
            open(os.path.join(self.out, f"{s}.html"), "w").write(self.page(self.title(s), body, nav))
        cards = []
        for s in self.ready:
            m = self.mods[s]
            n = len(m.get("features", [])) + len(m.get("workflows", []))
            sub = html.escape(m.get("intro", "") or f"{n} topics")
            cards.append(f"<a class=card href='{s}.html'><b>{html.escape(self.title(s))}</b><span>{sub}</span></a>")
        body = (f"<h1>{html.escape(self.state['app'])} help</h1><p class=mut>Search above, or pick a topic. "
                "Numbered marks on the screenshots show where to click.</p>"
                f"<div class=cards>{''.join(cards)}</div>")
        open(os.path.join(self.out, "index.html"), "w").write(self.page("Help", body, nav))
        open(os.path.join(self.out, "search-index.js"), "w").write("window.IDX=" + json.dumps(self.index, ensure_ascii=False) + ";")
        json.dump(self.helpmap, open(os.path.join(self.out, "help-map.json"), "w"), indent=2)
        print(f"{self.out}: {len(self.ready)} module pages, {len(self.helpmap)} help links, {len(self.copied)} assets")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    Site(ap.parse_args().ws).build()
