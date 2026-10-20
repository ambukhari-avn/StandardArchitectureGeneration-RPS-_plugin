# ChatGPT trial of the spec step (manual, no packaging)

Purpose: find out whether ChatGPT can turn a BOQ and a prompt into a spec that passes the validator, **before** the plugin is
packaged for ChatGPT. Nothing needs installing in ChatGPT. You do the ChatGPT side; the validator runs on your PC.

This is the acceptance test for Phase 4.3. Packaging the whole thing for ChatGPT is Phase 6 (and depends on open question Q40).

## 1. Make the input pack (Korangi, the one that is not the example)

```powershell
cd "C:\Users\ambhukari\StandardArchitectureGeneration(RPS)"
python scripts\spec_input.py "C:\Users\ambhukari\Downloads\system_architecture\BOQ 'S and visio\260402P60-PRL-Korangi-South-HB-AA-00.xlsx" --sheet "BOQ Foreign" --sheet "PLC F&G" --sheet "Work Stations" --prompt "F&G system architecture for PRL Korangi. Show the ESD push button."
```

This writes `Downloads\out\spec_input_260402P60-PRL-Korangi-South-HB-AA-00.md`.

## 2. In ChatGPT

Open a new chat. Paste the **Short form** from `docs/spec-instructions.md`. Attach these files:
- `Downloads\out\spec_input_260402P60-PRL-Korangi-South-HB-AA-00.md` (the pack)
- `data\spec_schema.json`
- `docs\connection-conventions.md`
- `samples\spec_kemari.json` (the worked example; do **not** attach the Korangi one)

Then send:

> Using the instructions, the pack and the example, write the spec JSON for this project. Output only the JSON.

## 3. Check it

Save ChatGPT's JSON as `Downloads\out\spec_korangi_chatgpt.json`, then:

```powershell
python scripts\validate_spec.py "$HOME\Downloads\out\spec_korangi_chatgpt.json" --boq "C:\Users\ambhukari\Downloads\system_architecture\BOQ 'S and visio\260402P60-PRL-Korangi-South-HB-AA-00.xlsx"
```

If it says INVALID, paste the whole output back into the chat and ask ChatGPT to correct the JSON. Repeat.

## 4. What to bring back

- Valid on the first try? (yes / no)
- How many rounds until VALID?
- The error codes it got wrong (for example D018, B001).
- Anything ChatGPT invented (a label, a component, a connection stated as fact).
- The final JSON.

**Passing** means VALID within two rounds and nothing invented. Failures tell us which instruction to tighten or which check to add.

## If you want to try more

- Repeat with Kemari as the target and the Korangi sample as the example.
- Try a prompt with a deliberate trap ("add a Rockwell flame detector"); the validator should refuse it.
- Try a prompt that asks for a DMZ with two boxes in it.
