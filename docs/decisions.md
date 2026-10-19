# Decisions

Choices made so far, with the reason. Change one only by editing this file and saying why.

| # | Decision | Reason |
|---|---|---|
| D1 | Scripts the plugin runs use only the Python standard library. Dev and test tooling may use more. | The plugin may run where `pip install` and network access are unavailable. |
| D2 | A `.vsdx` is written directly as an OPC zip of XML. The package skeleton (styles, theme, windows, content types) is copied from an existing Visio-made file; only page contents, page size and core properties are replaced. | A hand-written package from ChatGPT would not open in Visio: stray root part, no styles or theme, colours without `#`, `<Text>` before `<Geometry>`, a page sheet in the wrong place. A skeleton from a real Visio file avoids that class of fault. **Not yet confirmed in real Visio.** |
| D3 | Claude only produces a structured spec (what goes in the diagram). Fixed code validates it, lays it out and writes the file. | Models are unreliable at spelling and positioning; that is what went wrong in the ChatGPT images. |
| D4 | Output is always A3 landscape (16.5354 x 11.6929 in) and always one page. The writer refuses any other size. | Project requirement. |
| D5 | The footer is fixed: title block, notes, legend, logo. Its field values come from a form the user fills in. Size is always printed as A3. Missing fields stop the run (or print `TBC` if explicitly allowed). | Every diagram carries the same footer; nothing is guessed. |
| D6 | Cable colour, dash and label come from a cable type table, never from the spec. Placeholder values (Ethernet blue, fibre green, as on the Maaden and KSU drawings) are used until the client's standard arrives. | The legend and the drawn lines must always agree. |
| D7 | Legibility floor is 6 pt (configurable). Content that cannot fit above it fails with a report; it is never shrunk further or dropped. | Silent shrinking or dropping produces drawings that look right and are wrong. |
| D8 | A component is drawn as a picture only if the dataset has a picture for it. Everything else is a rectangle with its name inside. | Client decision. |
| D9 | The dataset workbook is used as the client supplied it. The client states it is verified. | Client decision. Anything odd found while using it goes in `open-questions.md`, not into silent edits. |
| D10 | Every diagram follows the Purdue model. Vertical bands come from a Purdue level, and the mapping from dataset layer names to levels is a table, not hard-coded. | Client decision. The mapping itself is still to be confirmed (see open question Q3). |
| D11 | Collapsing identical items into one icon with a count is off by default and configurable. | The client has not approved it. |
| D12 | The ChatGPT images are negative examples only ("how AI diagrams look"). Corrected versions are not needed. | Client decision. |
| D13 | Generated files go to `Downloads\out`. | User decision. |
| D14 | Hooks enforce the checks (validate before writing, check after writing, protect the dataset), so they cannot be skipped by forgetting an instruction. | A rule in a text file can be missed; a hook cannot. |
| D15 | Whether each picture is stored once in the file or pasted per use is decided with file-size evidence in Phase 5. | The 87 MB Murtiba `.vsdx` (154 media files, 284 embedded objects) shows what per-use pasting costs. |
| D16 | The spike code (`scripts/spike/`) is reference only. It hard-codes local paths and one project's layout and is not part of the runtime. | It proved the BOQ-to-file path; the real modules replace it phase by phase. |
