#!/usr/bin/env python3
"""Check click-target boxes before drawing, so wrong coordinates are caught early.

  check_boxes.py --ws W --module S

Looks at every step that has marks and an image. Errors stop the run (exit 1),
warnings mean "look at this one". Checks:
  - viewport missing, or screenshot aspect ratio does not match it (wrong window size or browser zoom)
  - box outside the screen, or partly outside
  - box tiny (under 8 px) or covering more than half the screen
  - box sits on flat, empty-looking pixels (usually a coordinate slip)
  - mark numbers not 1..n, more than 4 numbered marks, two marks on nearly the same spot
  - crop outside the image
"""
import argparse, json, os, sys
from PIL import Image, ImageStat


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ws", required=True)
    p.add_argument("--module", required=True)
    a = p.parse_args()
    mod = json.load(open(os.path.join(a.ws, "modules", f"{a.module}.json")))
    vp = mod.get("viewport")
    errors = warns = checked = 0

    def err(k, msg):
        nonlocal errors
        errors += 1
        print(f"ERROR {k}: {msg}")

    def warn(k, msg):
        nonlocal warns
        warns += 1
        print(f"WARN  {k}: {msg}")

    for fi, feat in enumerate(mod.get("features", [])):
        for si, st in enumerate(feat.get("steps", [])):
            k = f"{fi}.{si}"
            marks = st.get("marks") or []
            if not marks or not st.get("image"):
                continue
            checked += 1
            path = st["image"] if os.path.isabs(st["image"]) else os.path.join(a.ws, st["image"])
            if not os.path.exists(path):
                err(k, f"image not found: {st['image']}")
                continue
            if not vp:
                err(k, "module JSON has no viewport [w, h]")
                continue
            im = Image.open(path).convert("L")
            sx, sy = im.width / vp[0], im.height / vp[1]
            if abs(sx - sy) / max(sx, sy) > 0.03:
                warn(k, f"screenshot {im.width}x{im.height} does not match viewport {vp[0]}x{vp[1]} aspect; "
                        "window size or browser zoom changed, boxes will be off")
            if st.get("crop"):
                cx, cy, cw, ch = st["crop"]
                if cx < 0 or cy < 0 or cx + cw > vp[0] + 2 or cy + ch > vp[1] + 2 or cw <= 0 or ch <= 0:
                    err(k, f"crop {st['crop']} is outside the viewport")
            numbered = [m for m in marks if "n" in m]
            ns = sorted(m["n"] for m in numbered)
            if ns and ns != list(range(1, len(ns) + 1)):
                warn(k, f"mark numbers {ns} should be 1..{len(ns)} with no gaps or repeats")
            if len(numbered) > 4:
                warn(k, f"{len(numbered)} numbered marks; split the step so each image has at most 4")
            for i, m in enumerate(marks):
                box = m.get("box")
                if not box or len(box) != 4 or box[2] <= 0 or box[3] <= 0:
                    err(k, f"mark {i + 1} has a bad box {box}")
                    continue
                x, y, w, h = box
                if x + w <= 0 or y + h <= 0 or x >= vp[0] or y >= vp[1]:
                    err(k, f"mark {m.get('n', i + 1)} is completely outside the screen {box}")
                    continue
                if x < -2 or y < -2 or x + w > vp[0] + 2 or y + h > vp[1] + 2:
                    warn(k, f"mark {m.get('n', i + 1)} is partly outside the screen {box}")
                if w < 8 or h < 8:
                    warn(k, f"mark {m.get('n', i + 1)} is tiny ({w}x{h}); did the measurement catch the right element?")
                if w * h > 0.5 * vp[0] * vp[1]:
                    warn(k, f"mark {m.get('n', i + 1)} covers over half the screen; a highlight this big points at nothing")
                if w > 0.45 * vp[0] and h < 0.2 * w and m.get("style") != "blur":
                    warn(k, f"mark {m.get('n', i + 1)} is a wide strip ({w}x{h}); it may ring a whole row. Point the target at the clickable child (the avatar, the button)")
                if m.get("style") != "blur":
                    x0, y0 = max(0, int(x * sx)), max(0, int(y * sy))
                    x1, y1 = min(im.width, int((x + w) * sx)), min(im.height, int((y + h) * sy))
                    if x1 - x0 >= 4 and y1 - y0 >= 4:
                        sd = ImageStat.Stat(im.crop((x0, y0, x1, y1))).stddev[0]
                        if sd < 1.5:
                            warn(k, f"mark {m.get('n', i + 1)} sits on flat, empty-looking pixels (std {sd:.1f}); "
                                    "a button with text normally has some variation, so check the coordinates")
            for i in range(len(marks)):
                for j in range(i + 1, len(marks)):
                    if marks[i].get("box") and marks[j].get("box") and iou(marks[i]["box"], marks[j]["box"]) > 0.6 \
                            and "blur" not in (marks[i].get("style"), marks[j].get("style")):
                        warn(k, f"marks {i + 1} and {j + 1} are on nearly the same spot")
    print(f"{a.module}: {checked} steps checked, {errors} errors, {warns} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
