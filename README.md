# Architecture diagram generator (ChatGPT plugin, in progress)

Generates a one-page A3 Purdue-model architecture diagram as an editable Visio `.vsdx` from the user's prompt.
The user writes only a prompt. The model asks questions until nothing is unclear, then writes a structured spec; fixed, tested
code validates the spec, lays it out and writes the file. No model draws, positions or spells anything, and nothing is drawn that
the user did not say.

**Inputs:** the user's prompt (the only project input; no BOQ), `system_architecture_dataset.xlsx` (the component library and the
only source of pictures), and the client's drawing instructions. **Platform:** ChatGPT (decision D26).

**Status:** the drawing core is built and tested: footer, `.vsdx` writer, dataset import (including the vector symbols), Purdue map,
cable table, picture/box drawing, exact component matching, quantity rules, the spec format and validator, and the diagram builder.
Not built yet: the ChatGPT packaging (Phase 6) and the evaluation on real prompts (Phase 7). Nothing has been confirmed to open in
real Visio beyond a first check (open question Q17). See `docs/`.

## Layout
```
chatgpt-plugin/              what is assembled for ChatGPT: instructions.md (the model's instructions) and a README
scripts/                     Python standard library only (dev_preview needs Pillow and is a development aid):
                             vsdx_writer, footer, footer_form, textfit, draw        writing the page
                             xlsx_reader, import_dataset, components, purdue, cables   the dataset and the rule tables
                             matching, quantity                                     naming a component; quantities to items
                             spec, validate_spec, jsonschema_lite                   the spec and its validator
                             build_diagram (dev_preview)                            spec -> .vsdx
data/                        components.json + icons/ (imported dataset), purdue_map.json, cable_types.json,
                             spec_schema.json, spec_rules.json, footer_form.json
base/                        avanceon_logo.png, base.vsdx (empty A3 page on a Visio-made package skeleton)
samples/                     spec_example.json (a correct spec, with its prompt)
tests/  docs/
```

## Try it
Run the tests:

```
python -m unittest discover -s tests -v
```

Check and draw the example (files go to `Downloads\out`):

```
python scripts\validate_spec.py samples\spec_example.json
python scripts\build_diagram.py samples\spec_example.json --preview
```

Import the dataset again, or make a footer-only page:

```
python scripts\import_dataset.py <system_architecture_dataset.xlsx>
python scripts\footer.py --print-form
python scripts\footer.py --form filled_form.txt --base base\base.vsdx
```
