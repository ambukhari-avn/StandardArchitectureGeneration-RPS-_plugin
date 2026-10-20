"""Build the input pack the language model reads before it writes a spec.   Standard library only.

    python scripts/spec_input.py <boq.xlsx> --sheet "BOQ Foreign" --sheet "PLC F&G" [--prompt "text"] [--out pack.md]

The pack is everything the model is allowed to use, in one Markdown file: the cable types, the Purdue levels, the dataset
components (with their level and whether they have a picture), and the BOQ device lines with their row numbers, their
classification and the dataset component each matches by the exact rules. The model must not use anything that is not in the
pack or the prompt. Default output: <Downloads>/out/spec_input_<boq name>.md
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boq_parser
import boq_rules
from cables import Cables
from components import Components
from matching import Matcher
from purdue import PurdueError, PurdueMap


def build_pack(path, sheets, prompt="", comps=None, purdue=None, cables=None, rules=None, matcher=None):
    comps, purdue, cables = comps or Components(), purdue or PurdueMap(), cables or Cables()
    rules, matcher = rules or boq_rules.Rules(), matcher or Matcher(comps)
    fname = os.path.basename(path)
    L = ["# Spec input pack", "",
         "BOQ file: `%s`   |   sheets: %s" % (fname, ", ".join("`%s`" % s for s in sheets)), "",
         "Use only what is in this pack and the prompt. Every device must cite BOQ rows (sheet + row) or quote the prompt.", "",
         "## Prompt", "", prompt.strip() or "(no prompt text)", "", "## Cable types (use the id)", "", "| id | label | colour |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % (c["id"], c["label"], c["color"]) for c in cables.by_id.values()]
    L += ["", "## Purdue levels (use the key as the group level)", "", "| level | name |", "|---|---|"]
    L += ["| %s | %s |" % kv for kv in purdue.levels.items()]
    L += ["", "## Dataset components (use the id as `component` only when the BOQ text matches it, see the match column below)", "",
          "| id | label | layer | level | picture |", "|---|---|---|---|---|"]
    for c in comps.distinct():
        try:
            lv = purdue.level_of(c["layer"], None)
        except PurdueError as e:
            lv = "inherits" if "takes the level" in str(e) else "?"
        L.append("| %s | %s | %s | %s | %s |" % (c["id"], c["label"].replace("|", "/"), c["layer"], lv, "yes" if comps.picture_path(c["id"]) else "box"))
    L += ["", "Level 0 items and the DMZ are always drawn as boxes, and so is anything third-party, even when a picture exists.", ""]
    for sh in sheets:
        p = boq_parser.parse_sheet(path, sh)
        lines = rules.classify_all(p["lines"])
        acct = boq_rules.account(lines)
        L += ["## Sheet `%s`" % sh, "",
              "%d lines: %s. Rows with content %d, all accounted for: %s." % (
                  acct["lines"], ", ".join("%s %d" % (b, v["lines"]) for b, v in sorted(acct["by_bucket"].items())), p["content_rows"],
                  "yes" if p["content_rows"] == p["accounted_rows"] else "NO"), "",
              "### Device lines (every one must be drawn in a device or listed in `omitted` with a reason)", "",
              "| row | section | description | model | make | qty | unit | exact dataset match | by default |", "|---|---|---|---|---|---|---|---|---|"]
        for l in lines:
            if l["bucket"] != "device":
                continue
            m = matcher.match(l["description"], l["model"], l["make"])
            h = matcher.match_heading(l["section"])
            match = ("line: " + ", ".join("`%s`" % i for i in m.ids)) if m.status == "matched" else ("line ambiguous: " + ", ".join(m.ids)) if m.status == "ambiguous" else ""
            if h.status == "matched":
                match += (" " if match else "") + "heading: " + ", ".join("`%s`" % i for i in h.ids)
            L.append("| %d | %s | %s | %s | %s | %g | %s | %s | %s |" % (
                l["row"], " / ".join(l["parents"] + [l["section"]]).replace("|", "/")[:60], l["description"][:80].replace("|", "/"),
                l["model"][:24].replace("|", "/"), l["make"][:18].replace("|", "/"), l["qty"], l["unit"], match or "none", "yes" if l["by_default"] else ""))
        L.append("")
        others = {}
        for l in lines:
            if l["bucket"] != "device":
                others.setdefault(l["bucket"], 0)
                others[l["bucket"]] += 1
        L += ["Lines that are not devices (never drawn on their own): " + (", ".join("%s %d" % kv for kv in sorted(others.items())) or "none") + ".",
              "A component line may be cited under `parts` of the device it belongs to; a quantity of zero is never drawn.", ""]
        if p["fractional"] or p["zero_qty"] or p["no_qty"]:
            L += ["Needs a person: %d fractional quantities, %d zero quantities, %d lines without a quantity." % (len(p["fractional"]), len(p["zero_qty"]), len(p["no_qty"])), ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("boq")
    ap.add_argument("--sheet", action="append", required=True)
    ap.add_argument("--prompt", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    text = build_pack(a.boq, a.sheet, a.prompt)
    out = a.out or os.path.join(os.path.expanduser("~"), "Downloads", "out", "spec_input_%s.md" % os.path.splitext(os.path.basename(a.boq))[0].replace(" ", "_"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", out, "(%d lines)" % text.count("\n"))
