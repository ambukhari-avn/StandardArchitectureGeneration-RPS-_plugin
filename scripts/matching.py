"""Does the user's wording name a dataset component?  Standard library only.

No guessing. A component is supported by a piece of text only when
  1. one of its order numbers (6+ characters mixing letters and digits, e.g. 6GK5615-0AA00-2AA2) appears in the text, or
  2. its title appears in the text as whole words (plurals folded; a bracketed note in the title is optional), and, when several
     components share that title, the text also names the brand of exactly one of them.
The longest title found wins ("Compact PLC (larger)" beats "Compact PLC"). Anything else is 'no' or 'ambiguous', and the
model must ask the user which component is meant rather than choose.
"""
import re


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def part_tokens(s):
    """Order-number-like tokens: 6+ characters mixing letters and digits, split on spaces, slashes, commas and plus signs.
    Short family names such as 'M580' or 'TM221' do not count."""
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
    def __init__(self, comps):
        self.comps = comps
        self.parts, self.phrases = {}, {}
        for c in comps.distinct():
            if c["part_number"] and "box representation" not in c["part_number"].lower():
                for t in part_tokens(c["part_number"].split("(")[0]):          # the order number, not the family name in brackets
                    self.parts.setdefault(t, set()).add(c["id"])
            for title in (c["title"], re.sub(r"\(.*?\)", " ", c["title"])):
                if norm_singular(title):
                    self.phrases.setdefault(norm_singular(title), set()).add(c["id"])

    def check(self, text, cid):
        """('ok' | 'no' | 'ambiguous', candidate ids) for the claim that `text` names component `cid`."""
        if any(cid in self.parts.get(t, ()) for t in part_tokens(text)):
            return "ok", [cid]
        hay = " %s " % norm_singular(text)
        hits = [p for p in self.phrases if " %s " % p in hay]
        if not hits:
            return "no", []
        longest = max(len(p) for p in hits)
        cands = set().union(*(self.phrases[p] for p in hits if len(p) == longest))
        if cid not in cands:
            return "no", sorted(cands)
        if len(cands) == 1:
            return "ok", [cid]
        words = " %s " % norm(text)
        named = {i for i in cands if self.comps.by_id[i]["brand"] and " %s " % norm(self.comps.by_id[i]["brand"]) in words}
        return ("ok", [cid]) if named == {cid} else ("ambiguous", sorted(cands))
