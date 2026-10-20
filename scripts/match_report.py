"""How well do a BOQ's lines match the dataset?   Standard library only.

    python scripts/match_report.py <boq.xlsx> --sheet "BOQ Foreign" --sheet "PLC F&G" [--out report.md]

Writes a Markdown report (default: <Downloads>/out/match_report_<boq name>.md): totals, then every distinct
unmatched or ambiguous item with look-alike suggestions. Nothing is added to data/aliases.json by this tool.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boq_lines
from components import Components
from matching import Matcher


def build_report(path, sheets, comps=None, matcher=None):
    comps = comps or Components()
    matcher = matcher or Matcher(comps)
    seen, headings = {}, {}
    for sh in sheets:
        for ln in boq_lines.read_lines(path, sh):
            if ln["section"]:
                headings.setdefault(ln["section"], 0)
                headings[ln["section"]] += 1
            k = (ln["description"], ln["model"], ln["make"])
            e = seen.setdefault(k, {"lines": 0, "qty": 0.0, "where": []})
            e["lines"] += 1
            e["qty"] += ln["qty"]
            e["where"].append("%s r%d" % (sh, ln["row"]))
    res = {k: matcher.match(*k) for k in seen}
    counts = {s: sum(1 for r in res.values() if r.status == s) for s in ("matched", "ambiguous", "unmatched")}
    hres = {h: matcher.match_heading(h) for h in headings}
    hc = {s: sum(1 for r in hres.values() if r.status == s) for s in ("matched", "ambiguous", "unmatched")}
    L = ["# BOQ to dataset match report", "", "BOQ: `%s`; sheets: %s" % (os.path.basename(path), ", ".join("`%s`" % s for s in sheets)), "",
         "Distinct items: **%d** - matched **%d**, ambiguous **%d**, unmatched **%d**" % (len(res), counts["matched"], counts["ambiguous"], counts["unmatched"]), "",
         "Category headings: **%d** - matched **%d**, ambiguous **%d**, unmatched **%d**" % (len(hres), hc["matched"], hc["ambiguous"], hc["unmatched"]), "",
         "Matching is exact only (confirmed alias, part-number token, or title; headings fold plurals). Suggestions are look-alikes for a person to confirm; none are used automatically.", "",
         "## By category heading", "", "| Heading | Lines under it | Result |", "|---|---|---|"]
    for h, r in hres.items():
        out = ("`%s` (%s)" % (r.ids[0], r.how)) if r.status == "matched" else ("could be: " + ", ".join("`%s`" % i for i in r.ids)) if r.status == "ambiguous" else "no match; suggest: " + (", ".join("`%s` (%s)" % x for x in r.suggestions) or "none")
        L.append("| %s | %d | %s |" % (h[:60].replace("|", "/"), headings[h], out))
    L.append("")
    for status, head in (("matched", "Matched"), ("ambiguous", "Ambiguous (needs a decision)"), ("unmatched", "Unmatched (no dataset entry, or wording not yet confirmed)")):
        rows = [(k, r) for k, r in res.items() if r.status == status]
        L += ["## %s (%d)" % (head, len(rows)), "", "| Description | Model | Make | Qty | Result |", "|---|---|---|---|---|"]
        for (d, m, mk), r in rows:
            if status == "matched":
                out = "`%s` (%s)" % (r.ids[0], r.how)
            elif status == "ambiguous":
                out = "could be: " + ", ".join("`%s`" % i for i in r.ids)
            else:
                out = "suggest: " + (", ".join("`%s` (%s)" % s for s in r.suggestions) or "none")
            L.append("| %s | %s | %s | %g | %s |" % (d[:70].replace("|", "/"), m[:30].replace("|", "/"), mk[:20].replace("|", "/"), seen[(d, m, mk)]["qty"], out))
        L.append("")
    return "\n".join(L), counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("boq")
    ap.add_argument("--sheet", action="append", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    text, counts = build_report(a.boq, a.sheet)
    out = a.out or os.path.join(os.path.expanduser("~"), "Downloads", "out", "match_report_%s.md" % os.path.splitext(os.path.basename(a.boq))[0].replace(" ", "_"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("%s -> %s" % (counts, out))
