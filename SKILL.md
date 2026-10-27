---
name: docyfy
description: Docyfy builds a click-by-click user guide (PDF, plus optional GIFs) for any web application by driving it in Claude in Chrome, taking screenshots, and marking each click target with a hand-drawn outline and a numbered badge in the BeForth look. Asks whether the person wants the whole software or only specific features, works one module at a time, saves progress to disk so work is never repeated, and reuses screenshots and common steps like login, search and pagination. Use this whenever the user asks for a user guide, user manual, help documentation, how-to guide, training material, onboarding walkthrough, feature guide, or "where to click" documentation for a web app, ERP, CRM, dashboard or admin panel, even if they never say "PDF" or "screenshots".
---

# User guide builder

Produce a PDF that tells a non-technical reader exactly where to click, in order, for every feature of a web app. Each step has a screenshot with a hand-drawn highlight and a numbered badge that matches the numbered instruction beside it.

## Look
Every output (PDF, Word, site, cheat sheets, workflow roads) uses the BeForth design system through `scripts/theme.py`: paper background, ink line work, bone fills, one signal blue accent, Plus Jakarta Sans (bundled in `assets/fonts`), square corners, 1px rules, no shadows or gradients. Highlights use a spotlight. The rest of the screen is dimmed about 10% so the target stays bright, the target gets a slim outline in the accent colour with a thin paper ring, and a numbered disc sits beside it, never on the line. Other styles through `--style` on `progress.py init`: `clean` (dark outline, no dimming) and `sketch` (hand-drawn pen). Workflows are drawn as a road with numbered stops and a flag. Pass `--accent "#RRGGBB"` to `progress.py init` when a client wants their own colour in place of the signal blue. Do not restyle by hand. Change `theme.py` and rerun.

The job is large (dozens of screens), so the whole design aims at spending few tokens and never redoing work:

- One module per pass. After a module is built, its details leave your head and live on disk.
- Everything is saved to a workspace folder. `progress.py` is the memory. Read its short `status` output, not the files.
- Screenshots and wording that repeat (login, search box, pagination, delete confirm) are captured or written once and reused.

Scripts live in `scripts/` next to this file. Python: if the file `.python` exists next to this SKILL.md, its single line is the interpreter to use (the installer made a virtualenv with every package). Otherwise use `python3`. Run scripts as `<python> <skill-dir>/scripts/<name>.py`. Needs numpy, scipy, Pillow, reportlab, pypdf and python-docx. If one is missing and there is no `.python` file, create a virtualenv (`python3 -m venv ~/.docyfy/venv`), run `~/.docyfy/venv/bin/pip install -r <skill-dir>/requirements.txt`, and write that interpreter path into `.python`. Do not use `--break-system-packages`. The image privacy scan also uses pytesseract and the tesseract program when they exist, and is skipped when they do not.

## Step 0. Resume or start

If a workspace already exists (the user names one, or `guide-workspace/*/state.json` is present), run `progress.py status --ws <dir>`. If every module is built and the user says the app changed, use Update mode below. Otherwise continue from the first unfinished module. Do not re-ask scope questions that `state.json` already answers.

## Step 1. Intake (ask once, with AskUserQuestion, then stop asking)

Ask these together in one call:

1. **Scope**: whole software, or specific features/modules? If specific, ask which (free text via Other).
2. **Environment**: where should the guide be captured? Offer, in this order:
   - **Run it locally.** The user starts the project and gives a `localhost` address. Best option: nothing real can be harmed and no client data is on screen.
   - **Staging or demo link.** A non-production copy with dummy data, for example `staging.example.com`.
   - **Production.** Only if nothing else exists, and then strictly read-only (look, never change) with real data blurred. Say plainly that a staging or demo copy would give a better guide, and ask once if they can set one up.

   Sign-in: on a local or staging copy, use the test username and password the user types in chat for that app, or ones from the project's seed or example-config files. Do not repeat them back in replies. On production, or on any site the user has not said is a test copy, ask the user to sign in themselves in the Chrome tab and continue from there. Never type real passwords or payment details.
3. **Extras**: GIFs for features, or screenshots only? (GIFs make a companion folder and an HTML page, since PDF cannot play animation.) Also an editable Word version (useful when the client wants to change wording), and a help website (searchable, can be hosted, gives the app's "?" buttons links straight to the right section)?
4. **Audience and language**: for example "shop staff, plain English". It sets the tone of the step text.
5. **Branding and privacy**: accent colour (hex) and logo file for the cover, if they have them. Confirm that real customer data on screen should be blurred (default yes).
6. **Safe to click?** On a local or staging copy, creating, editing and deleting test records is fine, so document full flows end to end (fill the form, click Save, show the success message), using obvious sample data like "Sample Customer". On production, look at everything and change nothing. On production, create and delete steps are documented by stopping before the final confirm click.

Then `progress.py init --ws W --app NAME --url URL [--accent "#RRGGBB"] [--logo path] [--gifs]`. If the user chose specific features, only those modules are added.

## Step 2. Map the app once (cheap)

Follow `references/capture.md` section "Discover modules". Use `read_page` with `filter: interactive` on the navigation menu, not screenshots. Write modules to state with `progress.py add-module`. Keep the list in menu order. Sub-pages belong to their module as features. For "whole software", show the user the module list in one short message and carry on unless they object.

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

## Step 4. Front pages, check, assemble, deliver

1. **Quick start.** Once all modules are built, write a short `quick-start` module so a new user is not facing 40 pages cold. `progress.py add-module --ws W --slug quick-start --title "Start here"`, write `modules/quick-start.json`, build it like any module. It has an `intro` of two sentences, a `cheatsheet` ("I want to..." and where to go, 6 to 10 rows covering the most common jobs), and one feature, "Your first five minutes": sign in (`common: login`), find your way around (`common: sidebar`), then the two or three tasks people do daily. Reuse existing annotated images by setting `"annotated": "annotated/<file>.jpg"` on a step instead of capturing again. Keep it to one or two pages.
2. **Workflows.** People think in jobs that cross modules ("quote, order, invoice, payment"), not in menu items. Write a `workflows` module (`progress.py add-module --slug workflows --title "Workflows"`) with 2 to 5 of the most important end-to-end jobs. If the app's modules make the jobs obvious, infer them; if not, ask the user once which jobs matter most. Each workflow is a `flow` of 2 to 9 steps with a short `label`, a `where` ("Orders > From quotation") and an optional `note` and `link` (`module/feature-key`, which makes the step a link on the help website). The flow diagram is drawn for you. No new capturing is needed.
3. **Cheat sheets.** While writing each module, set `"cheat": true` on the 4 to 6 features people do every day. `build_cheatsheet.py --ws W` makes a one-page A4 sheet per module (`final/cheatsheets/<module>.pdf`, plus `all.pdf`) with a zoomed picture and the first steps of each, and the top three common problems. Skim one sheet at low resolution to confirm the crops show the right button.
4. **Check the guide**: `check_guide.py --ws W --ocr`. Fix every ERROR. For each WARN, either fix it or be able to say why it is fine. A readable email, phone, PAN, GSTIN or Aadhaar-like number in a screenshot means a `blur` mark is missing; add it, rerun `annotate.py` and the module build, and check again.
5. `build_pdf.py final --ws W` merges cover (with logo if given), a contents page listing modules and their features with real page numbers, and every built module into `final/user-guide.pdf` with bookmarks. "Start here" comes first, then workflows. If GIFs exist, it also writes `final/guide.html` with the animations inline.
6. If the user wanted Word: `build_docx.py --ws W` writes `final/user-guide.docx`. Tell them Word asks to update fields on opening (click Yes) to fill the contents list.
7. If the user wanted the help website: `build_site.py --ws W` writes `final/site/` (open `index.html`, or upload the folder to any web host). It has search, a side menu, one page per module, workflow diagrams, and `help-map.json`. Run it after the cheat sheets so their PDFs are linked. Give the developer the one-line usage: `window.open(HELP_BASE + helpMap["customers/add-a-customer"])`. Set `help_key` on features whose links must survive a rename (see Module JSON).
8. Send the PDF with SendUserFile, plus whichever of the cheat sheets, Word file, site folder and GIFs were made. Report the module count, page count and anything skipped (for example screens that needed data the account did not have). Finish with that, not a recap of steps.

## Making it easy for readers

The reader is a shop clerk or accountant, not a developer. Every choice below serves one question: can they find the right button in five seconds?

- One screen, one idea per image. Show the WHOLE screen by default, so the reader sees where the target sits on the page, in the menu or in the form. Crops confuse people who do not know the app. Use `crop` only when the target is tiny (an icon in a dense toolbar, one cell in a big table). A cropped image automatically gets a small map of the full screen in a corner with the zoomed area boxed, so the reader never wonders where it is.
- Use `rect` for fields, `circle` for icons and small buttons, `arrow` when the target is hard to spot, `underline` for text links. Four numbered marks per image at most.
- Say where it is in words as well ("top right", "left menu"), and name the button exactly as it is labelled.
- Use the user's words, not the database's. "Customer" not "party master", unless that is the label on screen.
- `tip` for a shortcut or hint, `warning` for anything that deletes, sends, pays or cannot be undone. Use at most one of each per step.
- Forms get a `fields` table so readers can see which boxes are required before they start.
- Real client data is blurred. Sample data is obviously sample ("Sample Traders", 9999999999).

## Fast mode
Most of the time goes into driving the browser, not into the scripts. Ways to cut it, in order of payoff:
1. **Ask for scope.** Offer "main screens only": one screenshot per feature (the screen with its target marked) instead of one per click. Steps like "type your name" or "scroll down" need no picture. This alone halves the capture time.
2. **Measure in one call.** For each screen, run one `javascript_tool` call that returns the boxes of every target at once. Do not hunt for elements with several `find` calls.
3. **Batch the clicks.** When the steps for a screen are known, use `browser_batch` to click and screenshot in one round trip.
4. **Reuse.** Login, sidebar, search, pagination and delete-confirm come from `assets/common.json`. Do not capture them again.
5. **One module per helper.** When there are four or more modules and the person is happy to wait less, start one subagent per module. Each follows this file for its own module and writes only to `modules/<slug>.json` and `shots/`. Never let two helpers write `state.json` at the same time. Run the final build yourself.
6. **Build last.** Capture and write all module JSON first, then run `annotate.py`, `build_pdf.py module` and `final` once. They cache, so a rerun only redraws what changed.

## Update mode (after a release)

Use this when a guide already exists and the app has changed. Do not rebuild everything.

1. `progress.py status` to see the built modules. Ask the user which modules changed, or check all.
2. For each module: `check_changes.py list --ws W --module S` shows the step keys. Revisit each screen in the browser (same viewport size as the original capture), run the fingerprint snippet, collect results into one JSON object, then run `check_changes.py compare --ws W --module S --fps '{...}' --apply`. No screenshots are taken at this stage, so it is cheap.
3. Changed steps are flagged stale and the module reopens (`progress.py next` returns it). Re-capture only those steps, re-measure boxes, update the step, then `check_changes.py set-fp` for them, which clears the flag.
4. `annotate.py` redraws only changed images, `build_pdf.py module` rebuilds only reopened modules (and refuses to build while a step is stale), and `build_pdf.py final` merges again. Rerun `build_cheatsheet.py`, `build_docx.py` and `build_site.py` for any outputs the user has. Because `help_key`s stay the same, links from the app keep working.

A changed fingerprint can be a false alarm (a heading with a record count, say). Re-capturing one extra step is cheap, so prefer a false alarm over a missed change. If a screen cannot be reached any more, set the module note and tell the user.

## Module JSON

`modules/<slug>.json`, written by you, read by `annotate.py` and `build_pdf.py`:

```json
{
  "title": "Customers",
  "intro": "Add, find and edit customer records.",
  "viewport": [1440, 900],
  "features": [
    {
      "title": "Add a customer",
      "goal": "Create a new customer record.",
      "gif": "gifs/customers-add.gif",
      "steps": [
        {"text": "Click **Customers** in the left menu.",
         "image": "shots/customers-list.png",
         "marks": [{"n": 1, "box": [24, 210, 180, 36], "style": "rect"}]},
        {"common": "search-box"},
        {"text": "Click **Add customer**, top right.",
         "image": "shots/customers-list.png",
         "marks": [{"n": 1, "box": [1210, 96, 150, 40], "style": "circle"}]},
        {"text": "Fill the name and phone, then click **Save**.",
         "image": "shots/customer-form.png",
         "marks": [{"n": 1, "box": [420, 200, 520, 44]},
                   {"n": 2, "box": [420, 260, 520, 44]},
                   {"n": 3, "box": [860, 640, 110, 42], "style": "circle"}],
         "tip": "Phone numbers need 10 digits."}
      ]
    }
  ]
}
```

- `box` is `[x, y, w, h]` in **viewport CSS pixels**, as the browser reports them. `annotate.py` scales to the image using `viewport`, so full-size and scaled screenshots both work.
- `style`: `rect` (default, wobbly box), `circle` (loop around small buttons and icons), `underline`, `arrow`, `blur`.
- `blur` pixelates a region and draws nothing else (leave out `n`). Use it on names, phone numbers, emails, addresses, amounts, GST/PAN numbers and anything else that looks like real client data. Real data in a guide that gets shared is a leak, so measure those boxes in the same JS call as the click targets and add a blur mark whenever such fields are visible.
- Several marks on one image get badges 1, 2, 3, and the step text lists them in the same order. Keep to 4 marks per image; split the step otherwise.
- `crop`: optional `[x, y, w, h]` per step, rarely needed. Leave it out so the guide shows the full screen. When set, the picture gets a locator map in a corner (see "Making it easy for readers"). Cheat sheet thumbnails are always zoomed this way because the cards are small.
- `warning` (step): red caution box for destructive or irreversible actions. `tip` is the bone-coloured hint box.
- `before` (feature): `{"menu": "Sales > Customers", "role": "Sales staff or an admin", "ready": ["Customer name", "10 digit phone number"]}`. Shown as a "Before you start" box above the steps (where it is in the menu, who is allowed, what to have ready). Write one for every form and for any task of 4 or more steps. Most failures come from missing access or missing information, not from not finding the button. Take the role from what you saw (menu items that were missing for a limited user) or the person's answer, never guess it.
- `fields` (feature): `[{"name": "Customer name", "required": true, "help": "Full legal name as on the invoice.", "example": "Sample Traders"}]`. Rendered as a "Fields on this screen" table after the steps.
- `cheatsheet` (module): `[{"want": "Add a new customer", "go": "Customers > **Add customer**"}]`. A two-column "I want to..." table at the top of the module; the main use is in `quick-start`.
- `workflows` (module level, used in the `workflows` module): `[{"title": "Quote to payment", "goal": "...", "flow": [{"label": "Create quotation", "where": "Quotations > Add quotation", "note": "...", "link": "quotes/add-quotation"}]}]`. Drawn as a numbered flow diagram with a table below it.
- `help_key` (feature or workflow): a stable name for the help link, for example `"customer-add"`. Without it the link comes from the title, so renaming the title would change the link. The app's "?" buttons use these, so tell the developer which keys exist (they are all in `help-map.json`).
- `cheat` (feature): true for the features that go on the cheat sheet. `cheat_step` picks which step's picture is shown (default: the first with marks).
- `fp`: page fingerprint stored by `check_changes.py set-fp`. Do not write it by hand.
- `problems` (module level, optional): `[{"message": "Phone number must be 10 digits", "cause": "...", "fix": "..."}]`. Becomes a "Common problems" table at the end of the module, listed in the contents. Use only messages you actually saw on screen; never invent them.
- `common`: pulls a step from the project's `common.json` (seeded from `assets/common.json`), including its shared screenshot if one is registered.

## Style rules for the text

- One action per numbered mark. Name the label exactly as shown.
- Say where it is ("top right", "left menu") because the reader cannot see your mind.
- Put cautions in `tip`, at most one per step.
- No marketing words, no "simply" or "just". The reader is following along with a mouse.

## Things that go wrong

- Screenshot coordinates are the full-resolution frame even when `scale` is below 1. Boxes from `getBoundingClientRect` are CSS pixels. Both are right as long as `viewport` in the module JSON matches the window size you used. Do not resize the window mid-module.
- Sticky headers and modals hide targets. Scroll the target into view with `scroll_to` before measuring it.
- GIF export is a browser download, so the file lands in the user's Downloads folder, not in the workspace. See capture.md for how to bring it in; if that is not possible, say where the files are and carry on with a PDF.
- If a page needs data the account lacks (an empty table), document the empty state honestly and note it; do not invent records.
