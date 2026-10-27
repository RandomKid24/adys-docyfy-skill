#!/usr/bin/env python3
"""Self-check: turn a built module PDF into ONE contact-sheet image to look at.

  review_pages.py --ws W --module S [--cols 3] [--page N]

Writes W/build/review/<module>.png with every page side by side at low resolution, and prints
what to look for. Look at the sheet once (one image costs far less than opening every page).
Then open a single page at full size with --page N only for something that looks wrong.
Needs pdftoppm (poppler). Without it the script says so and exits cleanly.
"""
import argparse, os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme

CHECKLIST = """Look for:
  1. Does each outline sit on the thing the step names? (wrong element is the most common mistake)
  2. Is any number badge cut off, or sitting on a line or on text?
  3. Is any text on the screenshot readable that should be blurred (names, phones, emails, amounts)?
  4. Is a picture blurry or tiny? Retake it at full size.
  5. Does any step picture land on a different page from its instruction line?
  6. Are the "Before you start" box and the fields table present where the feature has a form?
Fix the module JSON or retake the shot, rerun annotate.py and build_pdf.py module, then look again."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--page", type=int, help="render this one page at full size instead")
    a = ap.parse_args()
    pdf = os.path.join(a.ws, "build", f"{a.module}.pdf")
    if not os.path.exists(pdf):
        print(f"missing {pdf}; run build_pdf.py module --slug {a.module}")
        return 1
    if not shutil.which("pdftoppm"):
        print("pdftoppm not found (install poppler: apt install poppler-utils, or brew install poppler). Skipping the visual check.")
        return 0
    out_dir = os.path.join(a.ws, "build", "review")
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp()
    if a.page:
        subprocess.run(["pdftoppm", "-r", "110", "-f", str(a.page), "-l", str(a.page), "-png", pdf, os.path.join(tmp, "p")], check=True)
        f = sorted(os.listdir(tmp))[0]
        dst = os.path.join(out_dir, f"{a.module}-p{a.page}.png")
        shutil.copy(os.path.join(tmp, f), dst)
        print(dst)
        return 0
    subprocess.run(["pdftoppm", "-r", "50", "-png", pdf, os.path.join(tmp, "p")], check=True)
    pages = [Image.open(os.path.join(tmp, f)).convert("RGB") for f in sorted(os.listdir(tmp))]
    tw, th = pages[0].size
    cols = min(a.cols, len(pages))
    rows = -(-len(pages) // cols)
    gap = 14
    paper = theme.hex_rgb(theme.PALETTE["bone"])
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * (th + 22) + gap), paper)
    d = ImageDraw.Draw(sheet)
    for i, pg in enumerate(pages):
        x, y = gap + (i % cols) * (tw + gap), gap + (i // cols) * (th + 22)
        sheet.paste(pg, (x, y + 18))
        d.text((x, y + 2), f"page {i + 1}", fill=theme.hex_rgb(theme.PALETTE["ink"]))
    dst = os.path.join(out_dir, f"{a.module}.png")
    sheet.save(dst)
    print(dst)
    print(f"{len(pages)} pages. Open the sheet once.\n")
    print(CHECKLIST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
