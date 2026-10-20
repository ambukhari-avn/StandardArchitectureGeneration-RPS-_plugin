"""Read a BOQ and say what is in it.   Standard library only.

    python scripts/boq_report.py <boq.xlsx> --list                        which sheets look like a BOQ
    python scripts/boq_report.py <boq.xlsx> --sheet "BOQ Foreign" ...     write a Markdown report

The report shows, per sheet, that every row with content is accounted for; each line's bucket (device, component, service,
software, cable, material, documentation, spares); the device lines grouped by section with their dataset match; and every
line that needs a person: classified by default, zero or missing quantity, fractional quantity, ignored rows.
Price columns are never read. Default output: <Downloads>/out/boq_report_<boq name>.md
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boq_parser
import boq_rules
from components import Components
from matching import Matcher


def build_report(path, sheets, rules=None, comps=None, matcher=None):
    rules = rules or boq_rules.Rules()
    comps = comps or Components()
    matcher = matcher or Matcher(comps)
    parsed = [boq_parser.parse_sheet(path, s) for s in sheets]
    lines = []
    for p in parsed:
        lines += rules.classify_all(p["lines"])
    acct = boq_rules.account(lines)
    L = ["# BOQ report", "", "BOQ: `%s`" % os.path.basename(path), "",
         "Classification rules: `data/boq_rules.json` (status: **%s**)." % rules.status, "", "## Sheets", "",
         "| Sheet | Header row | Rows with content | Rows accounted for | Lines | Headings | Zero qty | No qty | Fractional | Ignored |", "|---|---|---|---|---|---|---|---|---|---|"]
    for p in parsed:
        L.append("| %s | %d | %d | %d%s | %d | %d | %d | %d | %d | %d |" % (
            p["sheet"], p["header_row"], p["content_rows"], p["accounted_rows"], "" if p["content_rows"] == p["accounted_rows"] else " **MISMATCH**",
            len(p["lines"]), len(p["outline"]), len(p["zero_qty"]), len(p["no_qty"]), len(p["fractional"]), len(p["ignored"])))
    L += ["", "Columns read: Sr, Description, Model, Make, Unit, Qty. Columns present but never read: %s." % (
        "; ".join(sorted({c for p in parsed for c in p["unread_columns"]})) or "none"), "",
        "## Where every line went", "", "| Bucket | Lines | Total quantity |", "|---|---|---|"]
    for b in rules.buckets:
        v = acct["by_bucket"].get(b)
        if v:
            L.append("| %s | %d | %g |" % (b, v["lines"], v["qty"]))
    L += ["| **all** | **%d** | |" % acct["lines"], "", "Lines classified by default (no rule matched; treated as devices): **%d**." % acct["by_default"], "",
          "## Device lines by section", ""]
    groups = {}
    for l in lines:
        if l["bucket"] == "device":
            groups.setdefault((l["sheet"], " / ".join(l["parents"]), l["section"]), []).append(l)
    for (sheet, parents, section), ls in groups.items():
        hm = matcher.match_heading(section)
        head = "%s%s" % ((parents + " / ") if parents else "", section or "(no heading)")
        L += ["### %s  (`%s`)" % (head, sheet),
              "Dataset: " + (("`%s` (heading)" % hm.ids[0]) if hm.status == "matched" else ("ambiguous: " + ", ".join(hm.ids)) if hm.status == "ambiguous" else "no match for the heading"), "",
              "| Row | Description | Model | Make | Qty | Unit | Rule | Dataset match |", "|---|---|---|---|---|---|---|---|"]
        for l in ls:
            m = matcher.match(l["description"], l["model"], l["make"])
            L.append("| %d | %s | %s | %s | %g | %s | %s | %s |" % (
                l["row"], l["description"][:60].replace("|", "/"), l["model"][:24].replace("|", "/"), l["make"][:16].replace("|", "/"), l["qty"], l["unit"],
                "default" if l["by_default"] else l["rule"], ("`%s` (%s)" % (m.ids[0], m.how)) if m.status == "matched" else m.status))
        L.append("")
    L += ["## Needs a person", ""]
    for title, key in (("Quantity 0 (not drawn)", "zero_qty"), ("Fractional quantity (rounded up when drawn)", "fractional")):
        items = [x for p in parsed for x in p[key]]
        L.append("**%s: %d**" % (title, len(items)))
        L += ["- %s row %d: %s - %g %s" % (x["sheet"], x["row"], x["description"][:60], x["qty"], x["unit"]) for x in items[:25]]
        L.append("")
    nq = [(p["sheet"], x) for p in parsed for x in p["no_qty"]]
    L.append("**Description with a model or make but no quantity: %d**" % len(nq))
    L += ["- %s row %d: %s" % (s, x["row"], x["description"][:60]) for s, x in nq[:25]]
    ig = [(p["sheet"], x) for p in parsed for x in p["ignored"]]
    L += ["", "**Ignored rows: %d**" % len(ig)] + ["- %s row %d: %s (%s)" % (s, x["row"], x["text"][:50], x["why"]) for s, x in ig[:25]]
    L += ["", "**Devices by default: %d**" % acct["by_default"]]
    seen = set()
    for l in lines:
        if l["by_default"] and l["description"][:50].lower() not in seen:
            seen.add(l["description"][:50].lower())
            L.append("- %s: %s" % (l["section"][:30], l["description"][:70]))
    return "\n".join(L) + "\n", {"lines": acct, "parsed": parsed}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("boq")
    ap.add_argument("--list", action="store_true", help="list the sheets that look like a BOQ and exit")
    ap.add_argument("--sheet", action="append")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.list:
        for s in boq_parser.list_sheets(a.boq):
            print("%-36s %-8s header row %d" % (s["name"], s["state"], s["header_row"]))
        sys.exit(0)
    if not a.sheet:
        ap.error("give --sheet NAME (repeatable); --list shows the candidates")
    text, _ = build_report(a.boq, a.sheet)
    out = a.out or os.path.join(os.path.expanduser("~"), "Downloads", "out", "boq_report_%s.md" % os.path.splitext(os.path.basename(a.boq))[0].replace(" ", "_"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", out)
