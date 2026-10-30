---
name: docyfy
description: Builds click-by-click user guides for web apps, whole app, modules or single tasks like "how to punch in". Outputs PDF, Word, help site, cheat sheets, and silent 4K screen recordings. Use for any request for a user guide, manual, help docs, how-to, training or onboarding material, or "where to click" docs for a web app, ERP, CRM or HRMS. Words after the command pick the output (pdf, video, word, site, all).
---

# Docyfy

Make guides that tell a non-technical reader exactly where to click. Scripts do the capture, drawing and building. Read only the reference file for the step you are on.

## Running scripts
Scripts are in `scripts/` next to this file. Python is the single line in the `.python` file here if it exists, else `python3`. Run `<python> <skill-dir>/scripts/<name>.py`. If a package is missing and there is no `.python`, run `python3 -m venv ~/.docyfy/venv`, `~/.docyfy/venv/bin/pip install -r <skill-dir>/requirements.txt`, and write that interpreter path into `.python`. Never use `--break-system-packages`.

## Words after /docyfy
No words at all? Your first action is one AskUserQuestion call, before anything else, with two questions. What to make (multi-select): PDF guide, Videos, Word file, Help site, Cheat sheets. What to do: Guide the whole app, Guide chosen tasks, Plan what to guide first, Update an existing guide. Then continue from the answers.
`pdf` PDF and cheat sheets (capture with `--no-video`). `video` MP4 recordings only (skip `build_pdf.py`). `gif` also makes a GIF per task, which is never made otherwise. `word` add `build_docx.py`. `site` add `build_site.py`. `all` everything. `plan` rank the tasks worth guiding first: run `plan.py --ws W --url APP [--usage usage.csv]`, show the top 8 in one line, ask which to build, then build the first tier. Ask once if they have support tickets or analytics counts for a usage file. `update` redo only what changed: run `capture.py update --ws W`, then rebuild the outputs (`references/update.md`). `chrome` capture with the person's own Chrome: run `capture.py chrome --url APP`, they sign in once, then set `DOCYFY_CDP=1` on every capture command. `draft|1080p|4k|8k` video quality, default 4k. `hi`, `mr`, `en` set the languages (Hindi, Marathi, English), one video each. Words combine. A task or module name sets the scope. If words cover it, skip those intake questions. State what you will make in one line, then start.

## Step 0. Resume
If a workspace exists (`guide-workspace/*/state.json`), run `progress.py status --ws W` and continue at the first unfinished module. Read the top of `W/docyfy.md` first (summary, outputs, notes, change log). Read its Tasks section only for the module you are on. Never re-ask what `state.json` answers. App changed after a release: `references/update.md`.

## Step 1. Intake (one AskUserQuestion call, then never again)
1. Scope: whole app, modules, or tasks. For tasks, build one module `tasks`, one feature per task, plain steps from first screen to the confirmation, each with a `before` box and a `fields` table if it has a form. Do not map the app. If no list was given for "staff" or "new users", propose 5 to 8 daily tasks to confirm.
2. Where to capture, in this order. Local (`localhost`), staging or demo link, production only as last resort and strictly look-only with real data blurred. On local or staging, use test credentials the user typed or the project's seed files, and never repeat them back. On production or unknown sites, the person signs in themselves. Never type real passwords or payment details.
3. Extras, if the words did not say: Word, help site. Videos are MP4 only. Offer a GIF only if they ask.
4. Audience and language, accent colour (hex), logo, blur real data (default yes).

Then `progress.py init --ws W --app NAME --url URL [--accent "#RRGGBB"] [--logo path] [--gifs]`. On local or staging, create, edit and delete test records freely with obvious sample data. On production, stop before the final confirm click.

## Step 2. Plan (whole app: always, never skip)
Run `plan.py --ws W --url URL --register`. It reads the menu, ranks the tasks, and adds each menu page as a module. For a whole app, show the plan in a few lines (modules in order, the top tasks, anything it could not open) and ask with AskUserQuestion: build in this order, start with the top tasks first, drop some modules, or add tasks it missed. Offer a `usage.csv` of support tickets or analytics once. Save the answer with `progress.py note`. Pages behind a click (tabs, sub-pages) are tasks inside a module. For chosen tasks only, skip the plan and go to Step 3.

## Go one module at a time
Do the first module fully (capture, check, build). Show what came out in two lines and ask once: keep this style for the rest, or change something. After that, continue module by module without stopping, with one short line per module. Say `next module` only if the person asked to approve each one. Sort out each module before the next, never half-do many.

## When you are unsure, ask
Use AskUserQuestion (one call, up to 4 questions, with a default marked) instead of guessing when: a sign-in or role decides what is visible; a form's required data is unclear (an ID that must exist, a value that must be unique); `draft` prints a `check:` line, or any script prints a line starting `ASK:` (put every ASK: line to the person); a button could be Save or Cancel; a step would delete, send or pay; a page is empty and you would need real records; two modules overlap; or a task ran in a different order than expected. If nobody can answer (a scheduled run), take the safest reading, say what you chose at the top of the work, and record it with `progress.py note`.

## Step 3. Capture, one module at a time
Default: `references/fast-capture.md` (Playwright on this machine, needs no per-click round trips). If the app is not reachable from here (SSO, captcha, private network, no Playwright): `references/browser-capture.md`, then `references/capture.md`.
Flow unclear, long, or many tabs and wizard sections: scout it first in the person's signed-in Chrome with Claude in Chrome (`references/scout.md`), then capture from the spec you wrote.
Render videos with `--preview` first (seconds, not minutes). Only after the steps are right, run the 4K pass once.
Videos and languages: read `references/video.md`. Native dropdowns (`select` steps) are drawn open automatically in both screenshots and videos. A PDF cannot play video, so never promise one inside it.

## Step 4. Finish
Read `references/finish.md` (quick start, workflows, cheat sheets, check, build, deliver). `docyfy.md` updates itself after every script. Record a decision or client request with `progress.py note --ws W --text "..."`. Send files with SendUserFile and report module count, page count and anything skipped, not a recap.

## Writing steps
Read `references/readers.md` once before writing text. In short: one action per numbered mark, name the label exactly as shown, say where it is ("top right"), whole screen by default, at most one `tip` and one `warning` per step, no "simply" or "just". Module file format: `references/module-json.md`. Look and colours: `references/look.md`.

## Do every step, in order
A guide is the task done for real, one step at a time. Boxes on a finished screen are not a guide. For a form or wizard, run `capture.py draft` (it makes one step per field, each Next, and the final Save), keep every step, and rewrite only the words. Fill, select and click for real on local or staging, ending on the final Save or Submit and the confirmation. `run` refuses steps that only show boxes.
Never skip. Run `capture.py fields --url PAGE` first. It lists every field on the page, including ones below the fold, each marked REQUIRED or optional, plus the tabs or sections. For a multi-section form or a wizard, rerun with `--click` on each tab. Then:
- Walk every section in order and end on the final Save or Submit and the confirmation the reader sees. A task that ends on "Next" is unfinished.
- Put every field in the `fields` table with `required` true or false, and say in the step text which boxes can be left empty.
- Long pages get several steps that scroll down. Do not drop fields to keep it short.
- Ring the clickable thing itself (the avatar, the button), not the row around it.

## Traps
Boxes are CSS pixels and `viewport` in the module JSON must match the window used. Do not resize mid-module. Sticky headers and modals hide targets, so scroll into view first. Empty tables: document the empty state honestly, never invent records.
