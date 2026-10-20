# Architecture diagram generator (Claude plugin)

Generates a one-page A3 Purdue-model architecture diagram as an editable Visio `.vsdx` from a project BOQ.
Claude decides *what* goes in the diagram (a structured spec). Fixed, tested code validates the spec, lays it out
and writes the file. No model draws, positions or spells anything.

**Status: Phase 2 (data layer) done.** Built: the footer, the `.vsdx` writer, a plugin skeleton whose `/arch:arch` command
currently builds a footer-only page, the component dataset (85 rows imported, 23 with pictures), the Purdue map, the cable
table, picture/box drawing, and exact BOQ-to-component matching with a report. Not built yet: the full BOQ parser, the spec,
layout, cable routing. See `docs/decisions.md`, `docs/open-questions.md` and `docs/dataset-import-report.md`.

## Layout
```
.claude-plugin/plugin.json   plugin manifest
skills/arch/SKILL.md         the /arch:arch command
skills/arch/instructions.md  do / don't rules (provisional until the client's file arrives)
hooks/                       hooks (Phase 6)
scripts/                     Python standard library only:
                             vsdx_writer, footer, footer_form, textfit, draw        writing the page
                             xlsx_reader, import_dataset, components, purdue, cables   data layer
                             boq_lines, matching, match_report                      BOQ matching
                             catalogue (dev check), make_base (one-off)
scripts/spike/               reference-only first spike; hard-coded paths; not part of the runtime
data/                        components.json + icons/ (imported dataset), purdue_map.json, cable_types.json,
                             aliases.json (confirmed BOQ wording; empty), footer_form.json
base/                        avanceon_logo.png, base.vsdx (empty A3 page on a Visio-made package skeleton)
samples/  tests/  docs/
```

## Try it
Run the tests (the file-writer tests need any Visio-made `.vsdx` as a skeleton):

```
set ARCH_BASE_VSDX=base\base.vsdx
python -m unittest discover -s tests -v
```

Import the dataset again, check a BOQ against it, or draw the one-page catalogue (files go to `Downloads\out`):

```
python scripts\import_dataset.py <system_architecture_dataset.xlsx>
python scripts\match_report.py <boq.xlsx> --sheet "BOQ Foreign" --sheet "PLC F&G"
python scripts\catalogue.py
```

Make a footer-only page:

```
python scripts\footer.py --print-form
python scripts\footer.py --form filled_form.txt --base base\base.vsdx
```

Load the plugin in Claude Code for testing, then run `/arch:arch`:

```
claude --plugin-dir "<path to this folder>"
claude plugin validate "<path to this folder>"
```

Nothing produced here has been confirmed to open in real Visio yet (open question Q17).
