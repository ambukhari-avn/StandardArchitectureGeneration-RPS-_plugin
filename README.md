# Architecture diagram generator (ChatGPT plugin, in progress)

Generates a one-page A3 Purdue-model architecture diagram as an editable Visio `.vsdx` from a project BOQ.
The model decides *what* goes in the diagram (a structured spec). Fixed, tested code validates the spec, lays it out
and writes the file. No model draws, positions or spells anything.

**Platform:** the plugin is now to be built for **ChatGPT**, not Claude (decision D26). The Python core below is unaffected;
the Claude packaging (`.claude-plugin/`, `skills/`) is superseded and will be replaced once the ChatGPT form is chosen (open question Q40).

**Status: Phase 4 (spec and validator) done.** Built: footer, `.vsdx` writer, dataset import, Purdue map, cable table, picture/box
drawing, exact matching, BOQ parser, classification rules, quantity rules, the **spec format and validator**, and the **model
input pack**. The spec step can be tried by hand in ChatGPT today (`docs/chatgpt-trial.md`). Not built yet: layout and cable
routing (Phase 5), the ChatGPT packaging (Phase 6), evaluation (Phase 7). See `docs/`.

## Layout
```
.claude-plugin/plugin.json   plugin manifest
skills/arch/SKILL.md         the /arch:arch command
skills/arch/instructions.md  do / don't rules (provisional until the client's file arrives)
hooks/                       hooks (Phase 6)
scripts/                     Python standard library only:
                             vsdx_writer, footer, footer_form, textfit, draw        writing the page
                             xlsx_reader, import_dataset, components, purdue, cables   data layer
                             boq_parser, boq_rules, quantity, boq_report                 reading and classifying a BOQ
                             matching, match_report                                 BOQ wording to dataset components
                             spec, validate_spec, spec_input, jsonschema_lite       the spec, its validator, the model input pack
                             catalogue (dev check), make_base (one-off)
scripts/spike/               reference-only first spike; hard-coded paths; not part of the runtime
data/                        components.json + icons/ (imported dataset), purdue_map.json, cable_types.json,
                             aliases.json (confirmed BOQ wording; empty), boq_rules.json (classification), spec_schema.json, spec_rules.json,
                             footer_form.json
base/                        avanceon_logo.png, base.vsdx (empty A3 page on a Visio-made package skeleton)
samples/                     spec_kemari.json, spec_korangi.json (worked examples of a correct spec)
tests/  docs/
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
python scripts\boq_report.py <boq.xlsx> --list
python scripts\boq_report.py <boq.xlsx> --sheet "BOQ Foreign" --sheet "PLC F&G"
python scripts\spec_input.py <boq.xlsx> --sheet "BOQ Foreign" --prompt "..."
python scripts\validate_spec.py samples\spec_korangi.json --boq <Korangi BOQ.xlsx>
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
