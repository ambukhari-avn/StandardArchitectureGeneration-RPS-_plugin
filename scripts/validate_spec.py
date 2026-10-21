"""Check a diagram spec before anything is drawn.   Standard library only.

    python scripts/validate_spec.py spec.json [--json]

Exit code 0 = valid, 1 = invalid. The output lists every problem with a code, where it is, and what is wrong, so the spec can be
corrected and checked again. On success it also prints the notes the diagram must carry.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec as specmod

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args()
    report = specmod.validate(specmod.load_json(a.spec))
    if a.json:
        print(json.dumps({"ok": report.ok, "errors": report.errors, "warnings": report.warnings, "notes": report.notes, "stats": report.stats}, indent=1))
    else:
        print(report.text())
        if report.ok:
            print("stats:", report.stats)
    sys.exit(0 if report.ok else 1)
