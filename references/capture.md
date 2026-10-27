# Capturing with Claude in Chrome

Read `anthropic-skills:chrome-browser` first if you have not this session. Load all tools in one ToolSearch call:
`select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__find,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__gif_creator`

Open the app in a fresh tab. Keep the same tab and window size for the whole project.

## Token rules

- Any screenshot that goes into the guide (`save_to_disk: true`) is taken at `scale: 1` with the window about 1440 px wide, so text stays sharp when printed. Only throwaway looks, which you do not save, may use `scale: 0.4` to 0.6. Crops are made later from the full-size file, so never pre-crop or shrink it.
- Add `save_to_disk: true` only on the shot you will actually keep. Rename or move the saved file into `<ws>/shots/<name>.png` (the tool result gives the path).
- Find targets with `find` or `read_page` (`filter: interactive`, `ref_id` to narrow). Do not scan whole pages in `all` mode.
- Measure many targets in one call:

```js
const q = s => { const e=[...document.querySelectorAll('a,button,input,select,textarea,[role=button],[role=menuitem]')]
  .find(x=>x.innerText?.trim()===s || x.placeholder===s || x.getAttribute('aria-label')===s);
  if(!e) return null; const r=e.getBoundingClientRect(); return [Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)]; };
JSON.stringify({vw:innerWidth,vh:innerHeight,boxes:Object.fromEntries(['Customers','Add customer','Save'].map(s=>[s,q(s)]))})
```

  Boxes come back in CSS pixels. Put `vw,vh` into the module JSON `viewport`.
- Do not view annotated output after every step. One spot-check per module.

## Discover modules

1. `read_page` with `filter: interactive` and a small `depth`, or `find` "main navigation menu". Read only the nav region.
2. List top-level items as modules. Expand collapsible groups with one click each and note children as features.
3. `progress.py add-module --ws W --slug customers --title "Customers" --features "List,Add,Edit,Delete,Export"`.
4. Do not open every page now. Opening happens in the module pass, so nothing is visited twice.

## Capturing one step

1. Navigate or click to reach the state.
2. `scroll_to` the target so no sticky bar covers it.
3. Screenshot (`save_to_disk` for keepers). Several steps often share one screenshot (for example the list page for "open menu" and "click Add"). Use one image with different marks per step.
4. Measure boxes via the JS snippet above.
5. Write the step into the module JSON at once. Do not keep a mental backlog.

Reuse: before capturing a repeatable part, run `progress.py shot-get`. A login screen, sidebar, search box, pagination bar and delete confirmation look the same everywhere, so capture each once and register it.

## Fingerprints

After each screenshot run the JavaScript printed by `python3 scripts/check_changes.py snippet` and keep the returned short string. It hashes the visible buttons, links, labels and headings with rough positions, ignoring table rows. If a button is renamed or moves, the string changes. Scroll to the same position as the screenshot first, because the hash only covers what is on screen.

## Form fields

On any screen with a form, run this once and use the output to fill the feature's `fields` table (do not paste it raw; write plain-language `help` and an obviously-sample `example`):

```js
JSON.stringify([...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(e=>e.getBoundingClientRect().width>0).map(e=>{
 const lab=(e.id&&document.querySelector(`label[for="${e.id}"]`))?.innerText||e.closest('label')?.innerText||e.getAttribute('aria-label')||e.placeholder||e.name||'';
 return {name:lab.replace('*','').trim(),required:e.required||e.getAttribute('aria-required')==='true'||/\*/.test(lab),type:e.type||e.tagName.toLowerCase(),
  placeholder:e.placeholder||'',maxlength:e.maxLength>0?e.maxLength:undefined,options:e.tagName==='SELECT'?[...e.options].slice(0,8).map(o=>o.text):undefined}}))
```

Fields hidden behind tabs or "Show more" need that control opened first. If the app marks required fields with a red star that is not in the label text, check `required` against what you see on screen.

## Recording problems for the "Common problems" table

- Local or staging copy: you may trigger the app's own validation on purpose. Submit a form with a required field empty, or enter a clearly invalid value, and copy the exact message shown. Then fix or cancel so you leave no bad data.
- Production: do not trigger errors. Only record messages that appear while you look around.
- Write each as `message` (exact text), `cause` (one short sentence), `fix` (what the user should do). If you do not know the cause, leave it out rather than guess.

## Forms and destructive actions

- Local or staging copy: fill forms with obvious sample data ("Sample Customer", 9999999999) and submit, so the guide can show the success message and the new row. Delete only records you created for the guide.
- Production: fill nothing. Capture the empty form and describe each field. Stop before final Save, Submit, Delete, Send and Pay, document that click with a badge, and say in `tip` what happens next.
- Never type real passwords or payment details. Test credentials on a local or staging copy are fine when the user gave them for that app.
- Dummy data still can look like real data. Blur anything that could be personal if the staging copy was cloned from production.

## GIFs

1. `gif_creator start_recording`, then immediately take a screenshot (first frame).
2. Do the 3 to 6 actions of the feature, with `wait` of about 1 second after each so the frames settle.
3. Screenshot (last frame), `stop_recording`.
4. `export` with `download: true`, `filename: "<module>-<feature>.gif"`, `options: {showWatermark: false, showActionLabels: true, showClickIndicators: true, quality: 15}`. Keep GIFs short and at moderate quality; they are for the HTML companion, not the PDF.
5. The file downloads into the user's browser Downloads folder. If the desktop bridge is connected, stage it from there into `<ws>/gifs/`. If not, tell the user the filenames and where to drop them, and the HTML will pick them up from `gifs/`.
6. `gif_creator clear` before the next recording.

In the PDF, a feature with a GIF shows its first step image and the line "Animated version: gifs/<name>.gif (open final/guide.html)". That is intentional. PDF cannot play GIFs.

## When capturing fails

- Element not found: try `find` with the visible label, then `read_page` on its container. If it is behind a hover, use `hover` first.
- Page changed the layout after login or window resize: re-measure that module's boxes; do not trust older ones.
- Blocked or permission prompt from the extension: stop and tell the user which site needs permission. Do not work around it.
