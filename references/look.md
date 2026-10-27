# Look (moved out of SKILL.md to save tokens)

## Look
Every output (PDF, Word, site, cheat sheets, workflow roads) uses the BeForth design system through `scripts/theme.py`: paper background, ink line work, bone fills, one signal blue accent, Plus Jakarta Sans (bundled in `assets/fonts`), square corners, 1px rules, no shadows or gradients. Highlights use a spotlight. The rest of the screen is dimmed about 10% so the target stays bright, the target gets a slim outline in the accent colour with a thin paper ring, and a numbered disc sits beside it, never on the line. Other styles through `--style` on `progress.py init`: `clean` (dark outline, no dimming) and `sketch` (hand-drawn pen). Workflows are drawn as a road with numbered stops and a flag. Pass `--accent "#RRGGBB"` to `progress.py init` when a client wants their own colour in place of the signal blue. Do not restyle by hand. Change `theme.py` and rerun.

The job is large (dozens of screens), so the whole design aims at spending few tokens and never redoing work:

- One module per pass. After a module is built, its details leave your head and live on disk.
- Everything is saved to a workspace folder. `progress.py` is the memory. Read its short `status` output, not the files.
- Screenshots and wording that repeat (login, search box, pagination, delete confirm) are captured or written once and reused.


