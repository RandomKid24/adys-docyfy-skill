# Scout with Claude in Chrome, capture with capture.py

Use this when the flow is unclear, long, behind several tabs or a wizard, or the app needs a sign-in that capture.py cannot do. Claude in Chrome acts in the person's real signed-in Chrome, so Claude can scroll, open tabs and try the task like a user. capture.py then takes the sharp screenshots and videos from the spec Claude wrote.

Skip it for simple tasks on a page capture.py can already open. `fields` and `explore` are cheaper.

## Steps
1. Load the `chrome-browser` skill and its tools in one ToolSearch call. Open the app in a new tab. Never type a password. If a sign-in shows, ask the person to do it.
2. Walk the whole task like a user. Scroll to the bottom of every page, open every tab or wizard section, and note each field. Read pages with `get_page_text` or `read_page`, not screenshots. On staging or local, fill with sample data and finish the task, ending on the final Save or Submit and the confirmation. On production, look only. Click nothing that saves.
3. For each target, get a stable selector with `javascript_tool`. Prefer `role=button[name="Submit Application"]`, `text=`, `#id` or `[name=...]` over long chains. A quick check that returns a unique match:
   `(s) => document.querySelectorAll(s).length` should give 1.
4. Write `<ws>/spec.json` from what you saw. One step per action. List every field in `fields` with `required` true or false. Add `before`. Put a `scroll`-worthy target below the fold as its own step.
5. Run `capture.py run`. If it cannot reach the app (SSO, captcha, private network), stay in Chrome and use `references/browser-capture.md` instead.
6. Look at the contact sheet from `review_pages.py`. Fix any ring that sits on the wrong thing and rerun that task with `--only`.

## Rules
- Chrome stays look-and-learn. The final pictures and videos come from capture.py, which is sharper and steadier.
- Test data only. Never real customer data on a guide that gets shared. Blur anything real that shows.
- Keep the tab list tidy. Close the tabs you opened when done.
