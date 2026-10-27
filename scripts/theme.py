#!/usr/bin/env python3
"""Shared look for every output: the BeForth palette, Plus Jakarta Sans, doodle rules.

Palette tokens match the BeForth design system (src/index.css). Per project, state.json
brand.accent can replace `signal` (the one accent) when a client wants their own colour;
everything else stays as is so the guides look like one family.

Doodle rules (from the design system):
  - line work in ink, round caps and joins, about 3px on a 1280px-wide image
  - signal only for the working or connected part (badges, the route)
  - bone for flat fills, no gradients, no shadows
  - a slow wobble so lines bend instead of jitter
  - square corners; only pills, avatars and numbered discs are round
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "..", "assets", "fonts")

PALETTE = {
    "paper": "#F2F7F9",
    "bone": "#D6E7F1",
    "ink": "#231F20",
    "ash": "#5F6571",
    "signal": "#1C75BC",
    "wave": "#75BAE6",
    "signal_deep": "#165B93",
}

FONT_FILES = {
    "regular": "PlusJakartaSans-Regular.ttf",
    "semibold": "PlusJakartaSans-SemiBold.ttf",
    "bold": "PlusJakartaSans-Bold.ttf",
    "extrabold": "PlusJakartaSans-ExtraBold.ttf",
    "ext-regular": "PlusJakartaSans-Ext-Regular.ttf",
    "ext-bold": "PlusJakartaSans-Ext-Bold.ttf",
}
FALLBACKS = {
    "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"],
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"],
}


def font_path(weight="regular"):
    """Path to a TrueType file. Plus Jakarta Sans if bundled, else a system font."""
    p = os.path.join(FONT_DIR, FONT_FILES.get(weight, FONT_FILES["regular"]))
    if os.path.exists(p):
        return p
    for q in FALLBACKS["bold" if weight in ("bold", "extrabold", "semibold", "ext-bold") else "regular"]:
        if os.path.exists(q):
            return q
    return None


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def tokens(state=None):
    """Palette with the project's accent applied. Returns {name: '#RRGGBB'} plus 'accent'."""
    t = dict(PALETTE)
    acc = ((state or {}).get("brand") or {}).get("accent")
    try:
        if acc:
            hex_rgb(acc)
            t["signal"] = acc if acc.startswith("#") else "#" + acc
    except Exception:
        pass
    t["accent"] = t["signal"]
    return t


def pil_text(text):
    """The bundled font has no rupee sign in its main set; PIL callers swap it for 'Rs'."""
    return (text or "").replace("\u20b9", "Rs ").replace("\u2192", ">")
