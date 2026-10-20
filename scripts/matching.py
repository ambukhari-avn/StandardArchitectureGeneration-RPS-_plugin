"""Match a BOQ line (description, model number, make) to a dataset component. Standard library only.

No guessing. A line matches only by
  1. a confirmed alias in data/aliases.json,
  2. an exact order-number token (e.g. BMEH584040) shared with a component's part number, or
  3. an exact title (brackets are part of the title), narrowed by make when several components share it.
Headings (BOQ category rows such as "Flame Detectors") are matched separately, by exact title with plurals folded.
Otherwise the result is 'unmatched' (with look-alike suggestions for a human to confirm) or 'ambiguous'.
"""
import json
import os
import re
from collections import namedtuple

ALIASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aliases.json")
Result = namedtuple("Result", "status ids how suggestions")      # status: matched | ambiguous | unmatched


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def part_tokens(s):
    """Order-number-like tokens: 6+ characters mixing letters and digits (BMEH584040, 6ES7214-1AG40-0XB0),
    split on spaces, slashes, commas and plus signs. Short family names such as 'M580' or 'TP1200' do not count."""
    out = set()
    for t in re.split(r"[\s/()+,;]+", str(s or "")):
        t = re.sub(r"[^A-Za-z0-9]", "", t).lower()
        if len(t) >= 6 and any(ch.isdigit() for ch in t) and any(ch.isalpha() for ch in t):
            out.add(t)
    return out


def norm_singular(s):
    """norm() with a trailing plural 's' folded off each word: 'Flame Detectors' == 'Flame detector'."""
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in norm(s).split())


class Matcher:
    def __init__(self, comps, aliases_path=ALIASES):
        self.comps = comps
        self.parts, self.titles, self.headings = {}, {}, {}
        for c in comps.distinct():
            if c["part_number"] and "box representation" not in c["part_number"].lower():
                for t in part_tokens(c["part_number"].split("(")[0]):          # the order number, not the family name in brackets
                    self.parts.setdefault(t, set()).add(c["id"])
            self.titles.setdefault(norm(c["title"]), set()).add(c["id"])
            self.headings.setdefault(norm_singular(c["title"]), set()).add(c["id"])
        self.aliases = {}
        if aliases_path and os.path.exists(aliases_path):
            with open(aliases_path, encoding="utf-8") as fh:
                for a in json.load(fh).get("aliases", []):
                    if a["component"] not in comps.by_id:
                        raise ValueError("alias %r points at unknown component %r" % (a["text"], a["component"]))
                    self.aliases[norm(a["text"])] = comps.get(a["component"])["id"]

    def match(self, description="", model="", make=""):
        for text in (description, model):
            if norm(text) in self.aliases:
                return Result("matched", [self.aliases[norm(text)]], "alias", [])
        toks = part_tokens(model) | part_tokens(make)        # make is included because some sheets have make and model swapped
        hit = set()
        for t in toks:
            hit |= self.parts.get(t, set())
        if len(hit) == 1:
            return Result("matched", sorted(hit), "part number", [])
        if len(hit) > 1:
            return Result("ambiguous", sorted(hit), "part number", [])
        cands = set(self.titles.get(norm(description), set()))
        if len(cands) == 1:
            return Result("matched", sorted(cands), "title", [])
        if len(cands) > 1:
            narrowed = {i for i in cands if self.comps.by_id[i]["brand"] and norm(make) and
                        (norm(self.comps.by_id[i]["brand"]) in norm(make) or norm(make) in norm(self.comps.by_id[i]["brand"]))}
            if len(narrowed) == 1:
                return Result("matched", sorted(narrowed), "title + make", [])
            return Result("ambiguous", sorted(cands), "title", [])
        return Result("unmatched", [], "", self._suggest(description))

    def match_heading(self, heading):
        """Match a BOQ category heading to a component by alias or exact title (plurals folded)."""
        if norm(heading) in self.aliases:
            return Result("matched", [self.aliases[norm(heading)]], "alias", [])
        c = self.headings.get(norm_singular(heading), set())
        if len(c) == 1:
            return Result("matched", sorted(c), "heading", [])
        if len(c) > 1:
            return Result("ambiguous", sorted(c), "heading", [])
        return Result("unmatched", [], "", self._suggest(heading))

    def _suggest(self, description, top=3):
        words = set(norm(description).split())
        if not words:
            return []
        scored = []
        for c in self.comps.distinct():
            tw = set(norm(c["title"]).split())
            if tw:
                score = len(words & tw) / len(words | tw)
                if score >= 0.34:
                    scored.append((round(score, 2), c["id"]))
        return [(i, s) for s, i in sorted(scored, reverse=True)[:top]]
