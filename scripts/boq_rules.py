"""Classify BOQ lines with ordered rules from data/boq_rules.json. Standard library only.

Buckets: device (may be drawn), component (part of a device, rack or panel; not drawn on its own), service, software,
cable, material (supports, junction boxes, tools, consumables), documentation, spares.

A rule has an id, a bucket, a reason and one or more conditions - section, parents, description, description_full, model,
make, unit - each a case-insensitive regular expression searched in that field (parents are joined with " / "). `description`
looks only at the headline (the first `headline_chars` characters, 70 by default) because BOQ descriptions often carry pages of
spec text; `description_full` looks at all of it. All conditions of a rule must match; the first matching rule wins. A line that matches no rule falls back to the file's "default" bucket and is
marked `by_default`, so it can be reviewed - nothing is classified silently. Rules are provisional until the client
confirms them (they come from the approved drawings, not from the client's instruction file).
"""
import json
import os
import re

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "boq_rules.json")
FIELDS = ("section", "parents", "description", "description_full", "model", "make", "unit")


class RulesError(ValueError):
    pass


class Rules:
    def __init__(self, path=PATH):
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.status = raw.get("status", "unknown")
        self.buckets = raw["buckets"]
        self.default = raw["default"]
        self.headline = int(raw.get("headline_chars", 70))
        if self.default not in self.buckets:
            raise RulesError("default bucket %r is not a bucket" % self.default)
        self.rules, seen = [], set()
        for r in raw["rules"]:
            if r["id"] in seen:
                raise RulesError("duplicate rule id %r" % r["id"])
            seen.add(r["id"])
            if r["bucket"] not in self.buckets:
                raise RulesError("rule %s: unknown bucket %r" % (r["id"], r["bucket"]))
            conds = {f: re.compile(r[f], re.I) for f in FIELDS if f in r}
            if not conds:
                raise RulesError("rule %s has no condition" % r["id"])
            self.rules.append((r["id"], r["bucket"], r.get("reason", ""), conds))

    def classify(self, line):
        """-> {'bucket', 'rule', 'by_default'} for a line from boq_parser."""
        desc = line.get("description", "")
        fields = {"parents": " / ".join(line.get("parents", [])), "description": desc[:self.headline], "description_full": desc}
        for f in ("section", "model", "make", "unit"):
            fields[f] = line.get(f, "")
        for rid, bucket, _, conds in self.rules:
            if all(c.search(fields[f]) for f, c in conds.items()):
                return {"bucket": bucket, "rule": rid, "by_default": False}
        return {"bucket": self.default, "rule": "default", "by_default": True}

    def classify_all(self, lines):
        return [dict(l, **self.classify(l)) for l in lines]


def account(classified):
    """{'lines', 'by_bucket': {bucket: {'lines', 'qty'}}, 'by_default'} - every line is in exactly one bucket."""
    out = {}
    for l in classified:
        b = out.setdefault(l["bucket"], {"lines": 0, "qty": 0.0})
        b["lines"] += 1
        b["qty"] += l["qty"]
    return {"lines": len(classified), "by_bucket": out, "by_default": sum(1 for l in classified if l["by_default"])}
