# Module JSON (moved out of SKILL.md to save tokens)

## Module JSON

`modules/<slug>.json`, written by you, read by `annotate.py` and `build_pdf.py`:

```json
{
  "title": "Customers",
  "intro": "Add, find and edit customer records.",
  "viewport": [1440, 900],
  "features": [
    {
      "title": "Add a customer",
      "goal": "Create a new customer record.",
      "gif": "gifs/customers-add.gif",
      "steps": [
        {"text": "Click **Customers** in the left menu.",
         "image": "shots/customers-list.png",
         "marks": [{"n": 1, "box": [24, 210, 180, 36], "style": "rect"}]},
        {"common": "search-box"},
        {"text": "Click **Add customer**, top right.",
         "image": "shots/customers-list.png",
         "marks": [{"n": 1, "box": [1210, 96, 150, 40], "style": "circle"}]},
        {"text": "Fill the name and phone, then click **Save**.",
         "image": "shots/customer-form.png",
         "marks": [{"n": 1, "box": [420, 200, 520, 44]},
                   {"n": 2, "box": [420, 260, 520, 44]},
                   {"n": 3, "box": [860, 640, 110, 42], "style": "circle"}],
         "tip": "Phone numbers need 10 digits."}
      ]
    }
  ]
}
```

- `box` is `[x, y, w, h]` in **viewport CSS pixels**, as the browser reports them. `annotate.py` scales to the image using `viewport`, so full-size and scaled screenshots both work.
- `style`: `rect` (default, wobbly box), `circle` (loop around small buttons and icons), `underline`, `arrow`, `blur`.
- `blur` pixelates a region and draws nothing else (leave out `n`). Use it on names, phone numbers, emails, addresses, amounts, GST/PAN numbers and anything else that looks like real client data. Real data in a guide that gets shared is a leak, so measure those boxes in the same JS call as the click targets and add a blur mark whenever such fields are visible.
- Several marks on one image get badges 1, 2, 3, and the step text lists them in the same order. Keep to 4 marks per image; split the step otherwise.
- `crop`: optional `[x, y, w, h]` per step, rarely needed. Leave it out so the guide shows the full screen. When set, the picture gets a locator map in a corner (see "Making it easy for readers"). Cheat sheet thumbnails are always zoomed this way because the cards are small.
- `warning` (step): red caution box for destructive or irreversible actions. `tip` is the bone-coloured hint box.
- `before` (feature): `{"menu": "Sales > Customers", "role": "Sales staff or an admin", "ready": ["Customer name", "10 digit phone number"]}`. Shown as a "Before you start" box above the steps (where it is in the menu, who is allowed, what to have ready). Write one for every form and for any task of 4 or more steps. Most failures come from missing access or missing information, not from not finding the button. Take the role from what you saw (menu items that were missing for a limited user) or the person's answer, never guess it.
- `fields` (feature): `[{"name": "Customer name", "required": true, "help": "Full legal name as on the invoice.", "example": "Sample Traders"}]`. Rendered as a "Fields on this screen" table after the steps.
- `cheatsheet` (module): `[{"want": "Add a new customer", "go": "Customers > **Add customer**"}]`. A two-column "I want to..." table at the top of the module; the main use is in `quick-start`.
- `workflows` (module level, used in the `workflows` module): `[{"title": "Quote to payment", "goal": "...", "flow": [{"label": "Create quotation", "where": "Quotations > Add quotation", "note": "...", "link": "quotes/add-quotation"}]}]`. Drawn as a numbered flow diagram with a table below it.
- `help_key` (feature or workflow): a stable name for the help link, for example `"customer-add"`. Without it the link comes from the title, so renaming the title would change the link. The app's "?" buttons use these, so tell the developer which keys exist (they are all in `help-map.json`).
- `cheat` (feature): true for the features that go on the cheat sheet. `cheat_step` picks which step's picture is shown (default: the first with marks).
- `fp`: page fingerprint stored by `check_changes.py set-fp`. Do not write it by hand.
- `problems` (module level, optional): `[{"message": "Phone number must be 10 digits", "cause": "...", "fix": "..."}]`. Becomes a "Common problems" table at the end of the module, listed in the contents. Use only messages you actually saw on screen; never invent them.
- `common`: pulls a step from the project's `common.json` (seeded from `assets/common.json`), including its shared screenshot if one is registered.

