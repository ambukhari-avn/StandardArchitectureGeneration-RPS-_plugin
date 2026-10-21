# ChatGPT plugin

Home of what is assembled for ChatGPT (Phase 6, form not yet chosen: open question Q40).

- `instructions.md` - the instruction text for the model (short form for the GPT's instruction field, reference below it).
- Knowledge/code files the model needs at run time: `scripts/` (Python standard library only), `data/` (components, icons, Purdue map,
  cable types, schema, rules, footer form), `base/`, and `samples/spec_example.json`.

The user gives only a prompt. The model asks questions until it is clear, writes the spec, runs `scripts/validate_spec.py` and
`scripts/build_diagram.py`, and returns the `.vsdx`.
