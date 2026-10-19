# Architecture diagram generator (Claude plugin)

Generates a one-page A3 Purdue-model architecture diagram as an editable Visio `.vsdx` from a project BOQ.
Claude decides *what* goes in the diagram (a structured spec). Fixed, tested code validates the spec, lays it out
and writes the file. No model draws, positions or spells anything.

**Status: Phase 1 (skeleton).** Built: the footer (title block, notes, legend, logo, fill-in form), the `.vsdx` writer,
and a plugin skeleton whose `/arch:arch` command currently builds a footer-only page. Not built yet: BOQ reading, the
spec, layout, cables. See `docs/decisions.md` and `docs/open-questions.md`.

## Layout
```
.claude-plugin/plugin.json   plugin manifest
skills/arch/SKILL.md         the /arch:arch command
skills/arch/instructions.md  do / don't rules (provisional until the client's file arrives)
hooks/                       hooks (Phase 6)
scripts/                     footer.py, footer_form.py, vsdx_writer.py (Python standard library only)
scripts/spike/               reference-only first spike; hard-coded paths; not part of the runtime
data/                        footer_form.json (and the component dataset, Phase 2)
base/                        avanceon_logo.png, base.vsdx (empty A3 page on a Visio-made package skeleton)
samples/  tests/  docs/
```

## Try it
Run the tests (the file-writer tests need any Visio-made `.vsdx` as a skeleton):

```
set ARCH_BASE_VSDX=base\base.vsdx
python -m unittest discover -s tests -v
```

Make a footer-only page (generated files go to `Downloads\out`):

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
