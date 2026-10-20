"""Load the component dataset (data/components.json, produced by import_dataset.py). Standard library only."""
import json
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA = os.path.join(ROOT, "data")


class Components:
    def __init__(self, path=os.path.join(DATA, "components.json")):
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.source = raw["source"]
        self._dir = os.path.dirname(os.path.abspath(path))
        self.all = raw["components"]
        self.by_id = {c["id"]: c for c in self.all}
        if len(self.by_id) != len(self.all):
            raise ValueError("duplicate component ids in %s" % path)
        for c in self.all:
            if c["duplicate_of"] and c["duplicate_of"] not in self.by_id:
                raise ValueError("%s: duplicate_of %r is not a component" % (c["id"], c["duplicate_of"]))

    def get(self, cid):
        """Component by id; an exact repeat resolves to the component it repeats."""
        c = self.by_id[cid]
        return self.by_id[c["duplicate_of"]] if c["duplicate_of"] else c

    def distinct(self):
        return [c for c in self.all if not c["duplicate_of"]]

    def picture_path(self, cid):
        """Absolute path of the component's PNG, or None if it is drawn as a box."""
        p = self.get(cid)["picture"]
        if not p:
            return None
        full = os.path.join(self._dir, p)
        if not os.path.exists(full):
            raise FileNotFoundError("picture for %s is listed but missing: %s" % (cid, full))
        return full

    def layers(self):
        return sorted({c["layer"] for c in self.all})
