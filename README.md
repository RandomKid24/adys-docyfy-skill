# Docyfy

A Claude skill that writes a click-by-click user guide for any web app. It drives the app in Claude in Chrome, takes screenshots, outlines each click target by hand-drawn ink marks, numbers them, and builds the guide.

You get a PDF. You can also get a Word file, a one-page cheat sheet per module, and a small help site you can host and link to from inside your app.

Highlights, workflow roads, fonts and colours follow the BeForth design system. You can swap the blue accent per project.

## What you need

- Claude Code, or any Claude app that supports skills.
- The Claude in Chrome extension, signed in and running. The skill uses it to open the app and take screenshots.
- Python 3.9 or newer and Node 16 or newer.

## Install

One command. It looks for the AI tools on your machine and copies the skill into each one, then installs the Python packages into their own virtualenv at `~/.docyfy/venv`, so your system Python stays untouched. You need Node 16 or newer.

```bash
npx github:RandomKid24/adys-docyfy-skill
```

It prints what it found and asks once before installing. Restart your AI tool afterwards.

| Tool | Skills folder | Confidence |
| --- | --- | --- |
| Claude Code | `~/.claude/skills` | Documented |
| OpenCode | `~/.config/opencode/skill` | Documented |
| Codex CLI | `~/.codex/skills` | Best effort |
| Gemini CLI | `~/.gemini/skills` | Best effort |
| Cursor | `~/.cursor/skills` | Best effort |

Best effort means the folder is my guess for that tool. If it does not pick the skill up, check the tool's docs for where skills go and use `--target`.

Options:

```bash
npx github:RandomKid24/adys-docyfy-skill --yes          # no question, install everywhere found
npx github:RandomKid24/adys-docyfy-skill --project      # only this project (./.claude/skills)
npx github:RandomKid24/adys-docyfy-skill --tool claude  # one tool only
npx github:RandomKid24/adys-docyfy-skill --target ~/my/skills   # any folder
npx github:RandomKid24/adys-docyfy-skill --list         # show what it found, change nothing
npx github:RandomKid24/adys-docyfy-skill --uninstall
npx github:RandomKid24/adys-docyfy-skill --no-deps      # skip the Python virtualenv
```

To update, run the same command again. It replaces the old copy.

### Install by hand

```bash
git clone https://github.com/RandomKid24/adys-docyfy-skill ~/.claude/skills/docyfy
python3 -m venv ~/.docyfy/venv
~/.docyfy/venv/bin/pip install -r ~/.claude/skills/docyfy/requirements.txt
echo ~/.docyfy/venv/bin/python > ~/.claude/skills/docyfy/.python
```

The folder name must be `docyfy`.

`pytesseract` in the requirements is optional. It powers `check_guide.py --ocr`, which scans finished screenshots for readable personal data. It also needs the `tesseract` program (`apt install tesseract-ocr` or `brew install tesseract`).

## Use it

Open Claude Code in your project (or anywhere) and say what you want:

> Make a user guide for my app at http://localhost:3000

> Write help docs for the Customers and Invoices modules of our staging app, https://staging.example.com

Claude then asks a few things before it starts.

1. The whole app or only some features.
2. Where to capture. Local, a staging or demo link, or production. Production is read-only and real data gets blurred.
3. Brand accent colour and logo, if you have them.
4. Whether you want GIFs, a Word file, cheat sheets and a help site.

Log in to the app in Chrome first if it needs a sign-in. The skill never types your passwords.

## Guides for specific tasks

You can ask for step-by-step guides for particular tasks instead of the whole app:

```
/docyfy make step-by-step guides for these tasks in https://staging.example.com
1. How to punch in and punch out
2. How to apply for leave
3. How to submit a daily work report
```

Each task becomes its own section. It starts at the screen the reader sees first and ends at the confirmation message. Every step has a screenshot with the target highlighted and a number, plus a "Before you start" box and a table of the fields. You can also get a one-page cheat sheet for the tasks you use most.

## Fast capture, sharp pictures and edited recordings

When the app opens from your computer (localhost, staging or a demo link), the skill runs `scripts/capture.py`. It drives the Google Chrome you already have, through Playwright (no extra browser download; if Chrome is missing the installer fetches Chromium), so:

- Screenshots are 2x sharp (a 1440 px window gives a 2880 px picture), not the 800 px the built-in browser tool returns.
- Highlight boxes are measured from the page, so they sit exactly on the target.
- A recording is made as it runs, edited with a spotlight on the target, the step number and a caption bar. You get a GIF and an MP4 per task. Install `ffmpeg` for this (`brew install ffmpeg`).
- A three-step task takes about 10 seconds.

A PDF cannot play a video, so the recordings live in the help site. If you host the site, give the address (`--site-url`) and each task in the PDF gets a link and a QR code to its recording.

You sign in yourself, once, in a window the script opens. The skill never types your password. On production it only looks and never clicks.

## What it writes

Everything goes in a workspace folder, so a stopped run picks up where it left off.

| Path | What is in it |
| --- | --- |
| `state.json` | Progress, brand settings, shared screenshots |
| `modules/<name>.json` | One module's steps, marks, fields and common problems |
| `shots/`, `annotated/` | Raw and marked screenshots |
| `final/user-guide.pdf` | The guide, with contents and page numbers |
| `final/user-guide.docx` | Word version |
| `final/cheatsheets/` | One A4 page per module, plus `all.pdf` |
| `final/site/` | Static help site with search and `help-map.json` |

## Keeping the guide current

When your app changes, ask Claude to update the guide. It compares saved page fingerprints, finds the screens that changed, and redoes only those. Everything else is reused. Help keys stay the same, so links from your app keep working.

## Linking help from your app

The site build writes `help-map.json`. It maps a `help_key` to a page URL. Point your app's "Help" button at the key for the current screen.

## Change the look

All colours and fonts live in `scripts/theme.py`. To use another accent for one project, pass `--accent "#RRGGBB"` to `scripts/progress.py init`. Highlights use a spotlight by default (rest of the screen dimmed slightly, target outlined in the accent colour). Pass `--style clean` for a plain dark outline or `--style sketch` for a hand-drawn pen look. Edit `theme.py` for anything else and rerun the build. The cache sees the change and redraws.

## Layout

```
SKILL.md              what Claude reads and follows
references/capture.md how to capture screens in Chrome
assets/               shared steps (login, search, pagination) and fonts
scripts/              annotate, build_pdf, build_docx, build_site, build_cheatsheet, checks
```

## Known limits

- Tested end to end on sample data. Run it on one real module first and check that the highlight boxes line up with your screens.
- The bundled font lacks the rupee sign in its main set. PDFs handle it. Images show "Rs".
- GIFs download through the browser, so you may have to save them by hand into the workspace.

The fonts are Plus Jakarta Sans under the SIL Open Font License (`assets/fonts/LICENSE-OFL.txt`).

### Narrated recordings

Add `"voice": true` to the capture spec and each step is read aloud, like the Frappe help videos. The caption stays on screen until the sentence ends. The MP4 carries the voice and the GIF stays silent. On a Mac it uses `say` with the Rishi voice (change it with `"voice": {"name": "Samantha", "rate": 180}`). Elsewhere it falls back to espeak-ng. To use another engine, set `DOCYFY_TTS_CMD` to a command with `{text}` and `{out}` in it.

### Highlights in videos

The cursor already shows where to click, so videos skip the dim and the numbered disc on click, fill and select steps. You get the caption and the cursor. Look-only steps ("you see the confirmation") get a soft ring. Set `"highlight": "full"` in the capture spec for the spotlight look, or `"caption"` for captions only. PDFs and screenshots keep the spotlight, since they have no cursor.

### What a finished video has

A title card with the task name and goal, then the recording in a Mac-style window. The view eases in toward each click target and back out, the cursor glides and ripples on the click, and the caption carries a "Step 2 of 4" chip. An end card closes it. The voice track, if on, starts after the title card. Turn pieces off in the spec with `"cards": false`, `"zoom": false` or `"highlight": "caption"`. `"zoom_level": 1.3` sets how close it gets.
