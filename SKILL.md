---
name: docyfy
description: Builds click-by-click user guides for web apps, whole app, modules or single tasks like "how to punch in". Outputs PDF, Word, help site, cheat sheets, and 4K narrated screen recordings. Use for any request for a user guide, manual, help docs, how-to, training or onboarding material, or "where to click" docs for a web app, ERP, CRM or HRMS. Words after the command pick the output (pdf, video, word, site, all).
---

# Docyfy

Make guides that tell a non-technical reader exactly where to click. Scripts do the capture, drawing and building. Read only the reference file for the step you are on.

## Words after /docyfy
`pdf` PDF and cheat sheets (capture with `--no-video`). `video` recordings only (skip `build_pdf.py`). `word` add `build_docx.py`. `site` add `build_site.py`. `all` everything. `draft|1080p|4k|8k` video quality, default 4k. `voice` narrated MP4. Words combine. A task or module name sets the scope. If words cover it, skip those intake questions. State what you will make in one line, then start.

## Step 0. Resume
If a workspace exists (`guide-workspace/*/state.json`), run `progress.py status --ws W` and continue at the first unfinished module. Never re-ask what `state.json` answers. App changed after a release: `references/update.md`.

## Step 1. Intake (one AskUserQuestion call, then never again)
1. Scope: whole app, modules, or tasks. For tasks, build one module `tasks`, one feature per task, plain steps from first screen to the confirmation, each with a `before` box and a `fields` table if it has a form. Do not map the app. If no list was given for "staff" or "new users", propose 5 to 8 daily tasks to confirm.
2. Where to capture, in this order. Local (`localhost`), staging or demo link, production only as last resort and strictly look-only with real data blurred. On local or staging, use test credentials the user typed or the project's seed files, and never repeat them back. On production or unknown sites, the person signs in themselves. Never type real passwords or payment details.
3. Extras, if the words did not say: GIFs, Word, help site.
4. Audience and language, accent colour (hex), logo, blur real data (default yes).

Then `progress.py init --ws W --app NAME --url URL [--accent "#RRGGBB"] [--logo path] [--gifs]`. On local or staging, create, edit and delete test records freely with obvious sample data. On production, stop before the final confirm click.

## Step 2. Map (cheap)
`capture.py explore --url URL` prints clickable items as text. Read menu links from it, no pictures. Add each with `progress.py add-module`, in menu order. Sub-pages are features. For a whole app, show the module list in one line and carry on.

## Step 3. Capture, one module at a time
Default: `references/fast-capture.md` (Playwright on this machine, needs no per-click round trips). If the app is not reachable from here (SSO, captcha, private network, no Playwright): `references/browser-capture.md`, then `references/capture.md`.
Videos: read `references/video.md`. A PDF cannot play video, so never promise one inside it.

## Step 4. Finish
Read `references/finish.md` (quick start, workflows, cheat sheets, check, build, deliver). Send files with SendUserFile and report module count, page count and anything skipped, not a recap.

## Writing steps
Read `references/readers.md` once before writing text. In short: one action per numbered mark, name the label exactly as shown, say where it is ("top right"), whole screen by default, at most one `tip` and one `warning` per step, no "simply" or "just". Module file format: `references/module-json.md`. Look and colours: `references/look.md`.

## Traps
Boxes are CSS pixels and `viewport` in the module JSON must match the window used. Do not resize mid-module. Sticky headers and modals hide targets, so scroll into view first. Empty tables: document the empty state honestly, never invent records.
