#!/usr/bin/env python3
"""Pre-delivery review of the whole guide. Run it before `build_pdf.py final`.

  check_guide.py --ws W [--module S] [--ocr]

Errors (exit 1): missing text, missing image files, marks without an annotated image,
stale steps, empty features.
Warnings: unbuilt modules, long steps, features over 12 steps, marks with no bold label in
the text, GIF files missing, personal-looking data in the written text.
--ocr also reads the annotated screenshots with tesseract and flags personal-looking data
that is still readable, which means a blur mark is missing. Needs pytesseract + tesseract;
without them the OCR pass is skipped with a note.
"""
import argparse, json, os, re, sys

EMAIL = re.compile(r"[\w.+-]+@([\w-]+\.)+[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
AADHAAR = re.compile(r"(?<!\d)\d{4}\s\d{4}\s\d{4}(?!\d)")
SAFE_DOMAINS = ("example.com", "example.org", "example.net", "test", "invalid", "localhost", "demo.local")


def pii_hits(text):
    hits = []
    for m in EMAIL.finditer(text):
        dom = m.group(0).split("@", 1)[1].lower()
        if not (dom.endswith(SAFE_DOMAINS) or dom in SAFE_DOMAINS):
            hits.append(("email", m.group(0)))
    for name, rx in (("phone", PHONE), ("PAN", PAN), ("GSTIN", GSTIN), ("Aadhaar-like number", AADHAAR)):
        for m in rx.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if name in ("phone", "Aadhaar-like number") and len(set(digits)) <= 2:
                continue  # 9999999999 style sample data
            hits.append((name, m.group(0)))
    return hits


def mask(s):
    return s[:2] + "*" * max(2, len(s) - 3) + s[-1:]


def texts_of(mod):
    for fi, feat in enumerate(mod.get("features", [])):
        for si, st in enumerate(feat.get("steps", [])):
            for key in ("text", "tip", "warning"):
                if st.get(key):
                    yield f"{fi}.{si} {key}", st[key]
        b_ = feat.get("before") or {}
        for key in ("menu", "role"):
            if b_.get(key):
                yield f"{fi} before {key}", b_[key]
        for item in (b_.get("ready") if isinstance(b_.get("ready"), list) else [b_.get("ready")] if b_.get("ready") else []):
            yield f"{fi} before ready", item
        for f_ in feat.get("fields", []):
            for key in ("help", "example"):
                if f_.get(key):
                    yield f"{fi} field '{f_.get('name','')}' {key}", f_[key]
    for p_ in mod.get("problems", []):
        for key in ("message", "cause", "fix"):
            if p_.get(key):
                yield f"problem {key}", p_[key]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--module")
    ap.add_argument("--ocr", action="store_true")
    a = ap.parse_args()
    state = json.load(open(os.path.join(a.ws, "state.json")))
    slugs = [a.module] if a.module else state["order"]
    errors = warns = 0

    def err(where, msg):
        nonlocal errors
        errors += 1
        print(f"ERROR {where}: {msg}")

    def warn(where, msg):
        nonlocal warns
        warns += 1
        print(f"WARN  {where}: {msg}")

    ocr = None
    if a.ocr:
        try:
            import pytesseract
            from PIL import Image
            pytesseract.get_tesseract_version()
            ocr = (pytesseract, Image)
        except Exception:
            print("note: OCR skipped (pytesseract or tesseract not installed)")
    seen_imgs = set()

    for slug in slugs:
        info = state["modules"].get(slug)
        if not info:
            err(slug, "not in state.json")
            continue
        if info["status"] != "built" and not a.module:
            warn(slug, f"status is {info['status']}, so it will not be in the final PDF")
        mp = os.path.join(a.ws, "modules", f"{slug}.json")
        if not os.path.exists(mp):
            if info["status"] in ("built", "written"):
                err(slug, "module JSON missing")
            continue
        mod = json.load(open(mp))
        if not mod.get("features") and not mod.get("workflows"):
            err(slug, "no features and no workflows")
        for wf in mod.get("workflows", []):
            if len(wf.get("flow", [])) < 2:
                err(f"{slug} / {wf.get('title','workflow')}", "a workflow needs at least 2 steps")
            if len(wf.get("flow", [])) > 9:
                warn(f"{slug} / {wf.get('title','workflow')}", "more than 9 steps; split it into two workflows")
        for fi, feat in enumerate(mod.get("features", [])):
            steps = feat.get("steps", [])
            where = f"{slug} / {feat.get('title', fi)}"
            if not steps:
                err(where, "feature has no steps")
            if len(steps) > 12:
                warn(where, f"{len(steps)} steps; readers lose their place past about 12, so split it")
            if (feat.get("fields") or len(steps) >= 4) and not feat.get("before"):
                warn(where, "no `before` box (where it is in the menu, who can do it, what to have ready); forms and long tasks need one")
            for key in ("video", "gif"):
                if feat.get(key) and not os.path.exists(os.path.join(a.ws, feat[key])):
                    warn(where, f"{key} {feat[key]} not found; the HTML page will skip it")
            for si, st in enumerate(steps):
                w = f"{where} step {si + 1}"
                if "common" in st:
                    continue
                if not st.get("text"):
                    err(w, "no text")
                    continue
                if len(st["text"]) > 220:
                    warn(w, f"{len(st['text'])} characters; shorten or split into two steps")
                if st.get("stale"):
                    err(w, "stale, re-capture it")
                img = st.get("image")
                if img and not os.path.exists(img if os.path.isabs(img) else os.path.join(a.ws, img)):
                    err(w, f"image missing: {img}")
                if (st.get("marks") or st.get("crop")) and not st.get("annotated"):
                    err(w, "has marks but no annotated image; run annotate.py")
                if st.get("marks") and not re.search(r"\*\*.+?\*\*", st["text"]):
                    warn(w, "has marks but the text names no label in bold; say what to click")
                if st.get("annotated"):
                    seen_imgs.add(st["annotated"])
        for where, text in texts_of(mod):
            for kind, val in pii_hits(text):
                warn(f"{slug} {where}", f"looks like a real {kind} ({mask(val)}); use sample data")

    if ocr:
        pt, Image = ocr
        print(f"OCR scan of {len(seen_imgs)} images ...")
        for rel in sorted(seen_imgs):
            path = os.path.join(a.ws, rel)
            if not os.path.exists(path):
                continue
            try:
                txt = pt.image_to_string(Image.open(path))
            except Exception as e:
                warn(rel, f"OCR failed: {e}")
                continue
            for kind, val in pii_hits(txt):
                warn(rel, f"readable {kind} ({mask(val)}) in the screenshot; add a blur mark over it")

    print(f"{len(slugs)} modules reviewed: {errors} errors, {warns} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
