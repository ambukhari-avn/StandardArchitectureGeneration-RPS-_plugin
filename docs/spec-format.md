# Spec format

The language model produces one JSON file, the **spec**, from the user's prompt and the user's answers to its questions. Fixed code
(`scripts/spec.py`) checks it against the dataset, the cable table and the Purdue rules before anything is drawn. The machine-readable
structure is `data/spec_schema.json`; a complete example is `samples/spec_example.json`.

## Shape

```json
{
  "spec_version": 1,
  "prompt": "the user's prompt, word for word",
  "project": {"end_user": "", "contractor": "", "project": "", "doc_name": "Architecture", "prepared_by": "", "checked_by": "", "approved_by": "", "rev": "R0/1"},
  "options": {"quantity_mode": "instances | count | type", "max_instances": 12, "dmz": false, "allow_tbc": false},
  "groups": [{"id": "ops", "title": "Operator layer", "level": "2", "devices": [ ... ]}],
  "connections": [{"from": "device id", "to": "device id", "cable": "ethernet", "redundant": false, "basis": "prompt", "quote": "..."}],
  "rings": [{"id": "ring1", "cable": "fibre", "members": ["device id", "device id"]}],
  "notes": ["extra notes for the diagram"],
  "answers": {"question": "the user's answer, word for word"}
}
```

A **device** is one icon or box on the diagram:

| Field | Meaning |
|---|---|
| `id` | unique, lower-case (`ws`, `plc-1`) |
| `quote` | the user's words that ask for it (from the prompt or an answer), copied exactly |
| `component` | a dataset component id; only when the quote names it (title or order number, plus brand if the title is shared) |
| `label` | only when there is no component: words that appear in the quote |
| `qty` | quantity; a whole number (a fraction is rounded up and noted) |
| `quantity_mode` | optional override of `options.quantity_mode` for this device |
| `third_party`, `role` | third-party items are boxes; `role: firewall` marks a firewall |
| `vm` | `{"note": 1, "contents": ["..."]}` when the server is a VM; contents are boxes in a side panel |

## What the validator guarantees

| Code | Meaning |
|---|---|
| S001 | structure wrong: a missing or unknown field, a wrong type |
| P001 | a footer field is missing (unless `allow_tbc`) |
| G001-G003 | duplicate group id; level not a Purdue level; a Level 3.5 group when the user did not ask for a DMZ |
| D001 | duplicate device id |
| D002, D003, D004 | component not in the dataset; label given with a component; neither given |
| D005 | label does not appear in the quote |
| D009 | quantity cannot be drawn (zero, or too many items to number: use `count` or `type`) |
| D010 | the component's Purdue level differs from its group's level |
| D011-D013 | VM claimed but the quote does not say so; a VM content not said by the user; (warning) the quote says VM but no `vm` block |
| D014 | a DMZ or third-party item names a dataset component; it must be a box |
| D017 | the quote is not in the prompt or the user's answers |
| D018 | the component is not named by the quote |
| D019 | the quote fits several dataset components (shared title): ask the user for the brand or part number |
| C001-C002, C007 | connection ends or cable type unknown; a device connected to itself |
| C003 | the two levels are not adjacent |
| C004 | a level 0 to level 1 link is not `hardwired` (client rule) |
| C005 | traffic into or out of the DMZ without a firewall at one end |
| C006 | a `prompt` connection without a real quote, or an `assumed` one with a quote |
| C008, C009 | (warnings) duplicate connection; hardwired link between level 2 devices |
| R001 | a ring member or cable is unknown |

The validator also builds the **notes the diagram must carry**: items drawn as boxes because the dataset has no component, how many
connections are assumed, Purdue levels assigned provisionally, quantities rounded or not shown.
