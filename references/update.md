# Update mode (moved out of SKILL.md to save tokens)

## Update mode (after a release)

Use this when a guide already exists and the app has changed. Do not rebuild everything.

1. `progress.py status` to see the built modules. Ask the user which modules changed, or check all.
2. For each module: `check_changes.py list --ws W --module S` shows the step keys. Revisit each screen in the browser (same viewport size as the original capture), run the fingerprint snippet, collect results into one JSON object, then run `check_changes.py compare --ws W --module S --fps '{...}' --apply`. No screenshots are taken at this stage, so it is cheap.
3. Changed steps are flagged stale and the module reopens (`progress.py next` returns it). Re-capture only those steps, re-measure boxes, update the step, then `check_changes.py set-fp` for them, which clears the flag.
4. `annotate.py` redraws only changed images, `build_pdf.py module` rebuilds only reopened modules (and refuses to build while a step is stale), and `build_pdf.py final` merges again. Rerun `build_cheatsheet.py`, `build_docx.py` and `build_site.py` for any outputs the user has. Because `help_key`s stay the same, links from the app keep working.

A changed fingerprint can be a false alarm (a heading with a record count, say). Re-capturing one extra step is cheap, so prefer a false alarm over a missed change. If a screen cannot be reached any more, set the module note and tell the user.

