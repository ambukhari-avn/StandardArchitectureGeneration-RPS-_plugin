---
name: arch
description: Generate a one-page A3 Purdue-model architecture diagram (.vsdx) from a BOQ. Skeleton stage - currently builds the footer only.
argument-hint: "[optional prompt]"
disable-model-invocation: true
allowed-tools: Bash Read Write
---

# /arch - skeleton stage

**Status:** only the footer is built. BOQ reading, the spec, layout and cables come in later phases. Say so to the user at the start and again at the end. Do not draw or position anything yourself; all drawing is done by the scripts.

Rules for this run are in `${CLAUDE_PLUGIN_ROOT}/skills/arch/instructions.md`. Read it first.

## Steps

1. **Show the footer form.** Run:

   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/footer.py" --print-form
   ```

   Show the printed form to the user as-is and ask them to fill it in and reply. Do not add, remove or reword questions; the questions live in `data/footer_form.json`.

2. **Save their answers.** Write the user's reply, unchanged, one `Label: value` per line with their notes under `Notes:`, to `arch_form.txt` in an `out` folder inside the user's Downloads folder (create the folder if needed).

3. **Build the footer page.** Run:

   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/footer.py" --form "<path of arch_form.txt>" --base "${CLAUDE_PLUGIN_ROOT}/base/base.vsdx"
   ```

   The file is written to the same `out` folder as `footer_demo.vsdx`.
   - If the script prints an error (a missing field, text that does not fit, an unrecognised line), show the message to the user, name the field, and ask for a corrected value. Do not fill the gap yourself and do not retry with `--tbc` unless the user asks for it.

4. **Report.** Give the output path. Say clearly that this is a footer-only A3 page and that it has not been checked in Visio unless the user says they opened it.
