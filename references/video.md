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

## Voice
macOS `say` with the Rishi voice (en-IN) by default, else espeak-ng. `DOCYFY_TTS_CMD='mytts "{text}" {out}'` swaps in another engine. Each caption stays up for the whole sentence.

## Watch link in the PDF
Ask where the help site will be hosted. With an address, run `progress.py init ... --site-url https://help.example.com` (or set `brand.site_url` in `state.json`). Each task with a recording then gets a "Watch this as a short video" box in the PDF with the link and a QR code. With no address the PDF shows nothing about the recording.

Prefer the MP4 for chat and email, the GIF for web pages.
