# Browser-tool capture (moved out of SKILL.md to save tokens)

## Step 3. Per-module loop

Repeat for each pending module. Do not hold more than one module in working memory.

1. `progress.py next --ws W` prints the module slug and its feature list. Mark it `capturing`.
2. **Capture** (references/capture.md): for each step, navigate, then take ONE screenshot at full size (`scale: 1`) and save it into `shots/`. Check the size the tool reports against the page width (`innerWidth`). The picture should be about 1:1 with the page, or text prints soft. The built-in browser caps pictures at 800 px wide, so set its window to about 800 px wide first (see capture.md). Never save a downscaled screenshot for the guide. If you only want to glance at a page, use a low `scale` without saving. Record each click target's box. Prefer boxes from `find`/`read_page` plus one `javascript_tool` call that returns `getBoundingClientRect()` for several elements at once; it is cheaper and more exact than eyeballing.
3. **Reuse check before every capture**: `progress.py shot-get --ws W --key <key>`. Shared keys: `login`, `sidebar`, `search-box`, `filters`, `pagination`, `export-menu`, `delete-confirm`, `profile-menu`. If it exists, point the step at it, and do not capture again. After a new capture of a repeatable UI part, `shot-register` it.
4. **Check, then annotate**: write the module JSON (see "Module JSON"), run `check_boxes.py --ws W --module S`, fix any ERROR and look at each WARN, then run `annotate.py`. The box check is cheap and catches wrong coordinates before they cost an image review. It skips images already annotated with the same marks. Spot-check at most one annotated image per module, at low scale.
5. **Fingerprints and problems.** Right after each screenshot, run the snippet from `check_changes.py snippet` with `javascript_tool` and keep the short result. When the module is captured, store them all at once with `check_changes.py set-fp --ws W --module S --fps '{"0.0":"..","0.1":".."}'` (keys are featureIndex.stepIndex). On every form screen also run the form-fields snippet from capture.md and turn the result into the feature's `fields` table. While capturing, note exact error and validation messages you see (see capture.md) for the module's `problems` list.
6. **GIF** (only if the user wanted them): references/capture.md section "GIFs". One GIF per feature, 3 to 6 actions.
7. **Write text**: short, imperative, one action per step, naming the exact label on screen ("Click **Save**"). Use `common` entries from `assets/common.json` for generic steps instead of rewriting them.
8. `build_pdf.py module --ws W --slug S` writes `build/S.pdf` and caches by content hash.
9. **Self-check by eye.** Run `review_pages.py --ws W --module S`. It writes one contact-sheet image of every page. Open that one image (not each page) and go through the checklist it prints: outline on the right element, badges not cut off, nothing readable that should be blurred, no blurry pictures. If a page looks wrong, run `review_pages.py ... --page N` to see just that page at full size, fix the JSON or retake the shot, rebuild and look again. Only then run `progress.py set --ws W --module S --status built`.
10. Move on. Do not re-read earlier modules.


### Fast mode
The biggest win is `capture.py` (see Fast capture above), which removes the browser round trips. When it cannot reach the app and the browser tools are the only way, most of the time goes into driving the browser. Ways to cut it, in order of payoff:
1. **Never drop steps for speed.** Every field, every Next and the final Save get their own step and picture. Speed comes from measuring and batching, not from skipping.
2. **Measure in one call.** For each screen, run one `javascript_tool` call that returns the boxes of every target at once. Do not hunt for elements with several `find` calls.
3. **Batch the clicks.** When the steps for a screen are known, use `browser_batch` to click and screenshot in one round trip.
4. **Reuse.** Login, sidebar, search, pagination and delete-confirm come from `assets/common.json`. Do not capture them again.
5. **One module per helper.** When there are four or more modules and the person is happy to wait less, start one subagent per module. Each follows this file for its own module and writes only to `modules/<slug>.json` and `shots/`. Never let two helpers write `state.json` at the same time. Run the final build yourself.
6. **Build last.** Capture and write all module JSON first, then run `annotate.py`, `build_pdf.py module` and `final` once. They cache, so a rerun only redraws what changed.

