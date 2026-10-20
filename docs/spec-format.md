# Spec format

The language model produces one JSON file, the **spec**. Fixed code (`scripts/spec.py`) checks it against the BOQ, the dataset,
the cable table and the Purdue rules before anything is drawn. The machine-readable structure is `data/spec_schema.json`;
two complete examples are `samples/spec_kemari.json` and `samples/spec_korangi.json`.

## Shape

```json
{
  "spec_version": 1,
  "prompt": "the user's prompt, word for word",
  "project": {"end_user": "", "contractor": "", "project": "", "doc_name": "Architecture", "prepared_by": "", "checked_by": "", "approved_by": "", "rev": "R0/1"},
  "options": {"quantity_mode": "instances | count | type", "max_instances": 12, "dmz": false, "allow_tbc": false},
  "sources": [{"file": "the BOQ workbook name", "sheets": ["sheet", "sheet"]}],
  "groups": [{"id": "ops", "title": "Operator layer", "level": "2", "devices": [ ... ]}],
  "connections": [{"from": "device id", "to": "device id", "cable": "ethernet", "redundant": false, "basis": "assumed"}],
  "rings": [{"id": "ring1", "cable": "fibre", "members": ["device id", "device id"]}],
  "omitted": [{"sheet": "sheet", "row": 12, "reason": "why this BOQ device line is not drawn"}],
  "notes": ["extra notes for the diagram"],
  "answers": {"redundancy": "...", "topology": "..."}
}
```

A **device** is one icon or box on the diagram:

| Field | Meaning |
|---|---|
| `id` | unique, lower-case (`ws`, `plc-1`) |
| `basis` | `boq` (comes from BOQ rows) or `prompt` (the prompt asked for it) |
| `component` | a dataset component id; only when the cited text matches it by the exact rules |
| `label` | only when there is no component: the BOQ section heading or description of the cited rows, or the prompt's words |
| `qty`, `unit` | quantity; must equal the sum of the cited rows |
| `quantity_mode` | optional override of `options.quantity_mode` for this device |
| `boq` | the rows this device comes from: `[{"sheet": "...", "row": 7}]` |
| `parts` | rows that belong to it (accessories, a monitor, a partner module); no quantity check |
| `quote` | for `basis: prompt`: the words of the prompt that ask for it |
| `third_party`, `role` | third-party items are boxes; `role: firewall` marks a firewall |
| `vm` | `{"note": 1, "contents": ["..."]}` when the server is a VM; contents are boxes in a side note |
| `boq_override` | a reason, to draw a row the rules classed as not a device |

## What the validator guarantees

| Code | Meaning |
|---|---|
| S001 | structure wrong: a missing or unknown field, a wrong type |
| P001 | a footer field is missing (unless `allow_tbc`) |
| B000, B001 | BOQ file or sheet not readable; **or** BOQ device lines that are neither drawn nor listed in `omitted` |
| B002, B003 | an omitted or part row is not an item line; a row is both drawn and omitted |
| G001-G003 | duplicate group id; level not a Purdue level; a Level 3.5 group when the prompt did not ask for a DMZ |
| D001 | duplicate device id |
| D002, D003, D004 | component not in the dataset; label given with a component; neither given |
| D005 | label is not the section heading or description of the cited rows, or not in the prompt |
| D006 | quantity does not equal the cited BOQ rows |
| D007, D008 | a cited row does not exist or has quantity 0; a cited row is not a device (use `boq_override` with a reason) |
| D009 | quantity cannot be drawn (metres, hours, too many items to number) |
| D010 | the component's Purdue level differs from its group's level |
| D011-D013 | VM claimed but not stated in the BOQ text; a VM content label found nowhere; (warning) BOQ says VM but no `vm` block |
| D014 | a DMZ or third-party item names a dataset component; it must be a box |
| D015-D017 | basis and evidence do not agree (rows or quote missing, or a quote not in the prompt) |
| D018 | the component is not supported by an exact match (alias, part number, title or heading) of the cited text |
| C001-C002, C007 | connection ends or cable type unknown; a device connected to itself |
| C003 | the two levels are not adjacent |
| C004 | a level 0 to level 1 link is not `hardwired` (client rule) |
| C005 | traffic into or out of the DMZ without a firewall at one end |
| C006 | a `prompt` connection without a real quote, or an `assumed` one with a quote |
| C008, C009 | (warnings) duplicate connection; hardwired link between level 2 devices |
| R001 | a ring member or cable is unknown |
| B004 | (warning) cited BOQ rows were classed as devices only by default |

The validator also builds the **notes the diagram must carry**: items drawn as boxes because the dataset has no component,
how many connections are assumed, Purdue levels assigned provisionally, BOQ lines not drawn and why, quantities rounded or not shown.
