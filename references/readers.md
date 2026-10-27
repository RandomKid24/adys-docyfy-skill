# Writing for readers

The reader is a shop clerk or accountant, not a developer. Every choice below serves one question: can they find the right button in five seconds?

- One screen, one idea per image. Show the WHOLE screen by default, so the reader sees where the target sits on the page, in the menu or in the form. Crops confuse people who do not know the app. Use `crop` only when the target is tiny (an icon in a dense toolbar, one cell in a big table). A cropped image automatically gets a small map of the full screen in a corner with the zoomed area boxed, so the reader never wonders where it is.
- Use `rect` for fields, `circle` for icons and small buttons, `arrow` when the target is hard to spot, `underline` for text links. Four numbered marks per image at most.
- Say where it is in words as well ("top right", "left menu"), and name the button exactly as it is labelled.
- Use the user's words, not the database's. "Customer" not "party master", unless that is the label on screen.
- `tip` for a shortcut or hint, `warning` for anything that deletes, sends, pays or cannot be undone. Use at most one of each per step.
- Forms get a `fields` table so readers can see which boxes are required before they start.
- Real client data is blurred. Sample data is obviously sample ("Sample Traders", 9999999999).
