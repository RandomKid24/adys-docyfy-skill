# Recordings

A PDF cannot play a GIF or video, so never promise one inside it. Recordings live in `gifs/` (`<task>.mp4` and a silent `<task>.gif`), the help site and the one-page HTML.

## How they are made
A studio renderer takes sharp stills of each page state, then draws the cursor, zoom, captions and fades itself. Nothing is screen-recorded, so the motion is even and the resolution is real. Set these in the capture spec header:

| Key | Default | Meaning |
|---|---|---|
| `quality` | `4k` | `4k` (3840x2160, 60 fps), `1080p`, `draft` (1080p, 30 fps, seconds to render), `8k` (slow) |
| `voice` | off | `true`, or `{"name": "Rishi", "rate": 170}`. Reads each step aloud. MP4 only, GIF stays silent |
| `zoom`, `zoom_level` | on, 1.3 | Eases toward each click target and back |
| `cards` | on | Title card and end card |
| `highlight` | `auto` | `auto`: caption only on click steps (the cursor shows the target), soft ring on look-only steps. `full`: ring on every mark. `caption`: captions only |
| `engine` | `studio` | `live` screen-records the browser instead (1280 px wide, less smooth) |

Use `draft` while checking a spec and `4k` for the final pass. 4K takes a few minutes per task on a laptop. On a Mac with ffmpeg's VideoToolbox encoder it is much faster. `DOCYFY_PRESET=fast` shrinks files at the cost of render time.

## Languages and voice
`"langs": ["en", "hi", "mr"]` renders one video per language from the same captured stills, so extra languages cost render time only. Files are `<task>.mp4` for the first language and `<task>.hi.mp4`, `<task>.mr.mp4` for the rest. Captions, step chips, title and end cards all switch language.

Claude writes the translations into the spec in plain spoken words, never word for word:

```json
{"slug": "apply-leave", "title": "How to apply for leave",
 "i18n": {"hi": {"title": "छुट्टी के लिए आवेदन कैसे करें", "goal": "..."}, "mr": {"title": "...", "goal": "..."}},
 "steps": [{"text": "Click **Apply**.", "click": "...", "i18n": {"hi": "**आवेदन करें** पर क्लिक करें।", "mr": "**अर्ज करा** वर क्लिक करा."}}]}
```

Voice (with `"voice": true`) picks the first engine that works:
1. `DOCYFY_TTS_CMD='mytts "{text}" {out}'`, with `{lang}` also available.
2. Microsoft neural voices through the `edge-tts` package (optional, not installed by default: `~/.docyfy/venv/bin/pip install edge-tts`). Best for Hindi and Marathi. Needs internet, no key. Defaults `en-IN-NeerjaNeural`, `hi-IN-SwaraNeural`, `mr-IN-AarohiNeural`. Change with `"voice": {"voices": {"hi": "hi-IN-MadhurNeural"}}`.
3. macOS `say` (Rishi for English, Lekha for Hindi and Marathi).
4. espeak-ng (robotic, but works offline).

To hear the voices first: `capture.py voices [--out DIR] [--langs en,hi,mr]` writes one sample per language.

Timing follows the longest narration across languages, so every language fits. Each caption stays up for the whole sentence.

## Dropdowns
A native `<select>` step (`"select": [target, "Sick leave"]`) shows the list open with the chosen option highlighted. The video opens the list, glides to the option and clicks it. The screenshot gets a second mark on the option. Custom dropdowns built from page elements show naturally: click the trigger, then click the option as two steps.

## Watch link in the PDF
Ask where the help site will be hosted. With an address, run `progress.py init ... --site-url https://help.example.com` (or set `brand.site_url` in `state.json`). Each task with a recording then gets a "Watch this as a short video" box in the PDF with the link and a QR code. With no address the PDF shows nothing about the recording.

Prefer the MP4 for chat and email, the GIF for web pages.
