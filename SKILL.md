---
name: docyfy
description: Docyfy builds click-by-click user guides for web apps (PDF, Word, hostable help site, one-page cheat sheets, plus edited GIF and MP4 screen recordings). It can cover the whole app, chosen modules, or specific tasks such as how to punch in. It captures sharp 2x screenshots with a spotlight and numbered highlight on every click target, blurs personal data, and saves progress so nothing is redone. Use this whenever the user asks for a user guide, user manual, help documentation, how-to guide, training material, onboarding walkthrough, feature guide, step-by-step task guide, or "where to click" documentation for a web app, ERP, CRM, HRMS, dashboard or admin panel, even if they never say PDF or screenshots.
---

# Docyfy

Produce a PDF that tells a non-technical reader exactly where to click, in order, for every feature of a web app. Each step has a screenshot with a spotlight on the target and a numbered badge that matches the numbered instruction beside it. Tasks can also get an edited screen recording.

## Look
Read `references/look.md` only when asked to change how the guide looks (colours, highlight style, fonts).

## Step 0. Resume or start

If a workspace already exists (the user names one, or `guide-workspace/*/state.json` is present), run `progress.py status --ws <dir>`. If every module is built and the user says the app changed, use Update mode below. Otherwise continue from the first unfinished module. Do not re-ask scope questions that `state.json` already answers.

## Step 1. Intake (ask once, with AskUserQuestion, then stop asking)

Ask these together in one call:

1. **Scope**: whole software, specific modules, or **specific tasks**? Offer all three. If the person names tasks ("how to punch in", "apply for leave", "raise an invoice"), build a task guide: one module called "Tasks" (slug `tasks`), one feature per task in the order they listed, written as a plain step-by-step ("Click **Punch in**") from the first screen the reader sees (login or Home) to the confirmation message. Each task gets its own `before` box and, when the task has a form, a `fields` table. Do not map the rest of the app. If they gave no task list but said "for staff" or "for new users", propose the 5 to 8 most common daily tasks from what the menu shows and ask them to confirm or edit the list, in the same question.
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

With `capture.py`, run `capture.py explore` on the home page and read the menu links from the text (no picture needed). With browser tools, follow `references/capture.md` section "Discover modules". Use `read_page` with `filter: interactive` on the navigation menu, not screenshots. Write modules to state with `progress.py add-module`. Keep the list in menu order. Sub-pages belong to their module as features. For "whole software", show the user the module list in one short message and carry on unless they object.

## Step 3. Capture (one module at a time)
Try `capture.py` first (below). **Browser-tool capture** (when `capture.py` cannot reach the app: SSO, captcha, app only on a private network, or Playwright missing). Read `references/browser-capture.md` for the per-module loop, then `references/capture.md` for tool tips.

### Fast capture with capture.py
`scripts/capture.py` drives the installed Google Chrome through Playwright on the same machine Claude's shell runs on. Pictures come out 2x sharp (2880 px for a 1440 px window), boxes are measured exactly, and an edited recording (spotlight, numbered mark, caption bar) is made while it runs, as a GIF and an MP4 in `gifs/`. It needs no round trip to Claude per click, so a task takes seconds instead of minutes. Use it when the app address opens from this machine (localhost, or a staging or demo link) and Playwright is installed (`<python> -c "import playwright"`). Otherwise use the browser-tool capture in Step 3 and `references/capture.md`.

1. **Sign in once, by the person.** If the app needs a login, ask them to run `<python> <skill-dir>/scripts/capture.py login --url <app url> --out <ws>/.auth/state.json` in their own terminal, sign in in the window that opens, and close it. Never type or ask for their password yourself. The saved state stays in `<ws>/.auth` and is never part of the guide.
2. **Look at pages as text, not pictures.** `capture.py explore --url <page> [--state <ws>/.auth/state.json]` prints every visible button, link and field as `role=button[name="Punch in"]`. Those are the targets for the spec. This costs a few lines per page instead of an image.
3. **Write one spec** (`<ws>/spec.json`, format in the header of `capture.py`): each task has steps with `text`, an optional `goto`, then one action (`click`, `fill`, `select`, `press`, `wait`). Marks and the picture are taken before the action. A click step with no marks highlights the click target. Use `blur` for names, phones and amounts. Add `before`, `fields` and `goal` per task.
4. **Run it**: `capture.py run --ws W --spec spec.json` (add `--only <slug>` for one task, `--no-video` to skip recordings). It writes `shots/`, `gifs/` and the module JSON (default module `tasks`, or set `"module"` in the spec).
5. **Continue as normal**: `check_boxes.py`, `annotate.py`, `build_pdf.py module`, `review_pages.py`, then the front pages and final build. The picture, GIF and PDF all show the same steps.

Rules it enforces: `"env": "production"` is look-only, so click, fill, select and press are refused. It never types into a password field. Use sample data in `fill` values. If a step cannot be found within 8 seconds, it stops and names the step. Fix the target (rerun `explore` on that page) instead of guessing. If the app uses single sign-on, a captcha or a code sent by phone, the login command still works because the person does it by hand.

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

## Recordings and the PDF
A PDF cannot play a GIF or a video, so never promise one inside it. Recordings (`gifs/*.gif`, `gifs/*.mp4`) live in the help site (`build_site.py`) and the one-page HTML. Ask where the help site will be hosted. If the person gives an address, run `progress.py init ... --site-url https://help.example.com` (or set `brand.site_url` in `state.json`). Every task that has a recording then gets a "Watch this as a short video" box in the PDF with that link and a QR code, so a reader with the printout can scan it. With no address the PDF shows nothing about the recording. The recordings are edited as they are made (a cursor that glides to the target, a ripple on each click, caption bar, typing shown letter by letter), so they need no editing afterwards. The cursor points at click targets, so the video shows only a caption there and a soft ring on look-only steps. Videos come from a studio renderer (sharp stills plus a drawn cursor, zoom and captions at 60 fps). Use `"quality": "draft"` in the spec while checking and leave the default `4k` for the final pass; 4K takes a few minutes per task. Videos also get a title card, an end card, a "Step n of N" chip and a smooth zoom toward click targets (switch off with `"cards": false`, `"zoom": false`). Set `"highlight": "full"` in the spec for the dimmed spotlight with numbers. Set `"voice": true` in the capture spec to add a computer voice that reads each step, as Frappe does. The MP4 has the voice, the GIF stays silent. It uses `say` on a Mac and espeak-ng elsewhere. Prefer the MP4 for chat apps and email, the GIF for web pages.

## Update mode (after a release)
**Update mode** (after a release). Read `references/update.md`.

## Module JSON
**Module JSON.** Read `references/module-json.md` before writing or editing a module file by hand. `capture.py` writes it for you when you use a spec.

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
