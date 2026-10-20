"""Purdue level of a component, from its dataset layer label via data/purdue_map.json. Standard library only.

The mapping is data, not code (decisions D10). Each layer label maps to
  * a level (a key of "levels"),
  * "inherit": a network/HMI-type device that sits at the level of the group it is placed in, or
  * nothing - the label is then unassigned and asking for it is an error, never a guess.
Every entry carries a status. "proposed" (drafted by us) and unassigned entries are reported by unconfirmed() so they can be
shown in the diagram's Notes; "confirmed" (client) and "from dataset tag" (the label itself says L0/L1/L2) are not.
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "purdue_map.json")
INHERIT = "inherit"


class PurdueError(ValueError):
    pass


class PurdueMap:
    def __init__(self, path=PATH):
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.levels = raw["levels"]                    # {"0": "Process / field", ...}
        self.layers = raw["layers"]                    # {label: {"level": ..., "status": ...}}
        for label, e in self.layers.items():
            lv = e.get("level")
            if lv not in (None, INHERIT) and lv not in self.levels:
                raise PurdueError("layer %r maps to unknown level %r" % (label, lv))

    def level_of(self, layer, group_level=None):
        """Level key (e.g. '1') for a dataset layer label. 'inherit' layers take `group_level`."""
        if layer not in self.layers:
            raise PurdueError("layer %r is not in the Purdue map" % layer)
        lv = self.layers[layer].get("level")
        if lv is None:
            raise PurdueError("layer %r has no Purdue level assigned yet (edit data/purdue_map.json)" % layer)
        if lv == INHERIT:
            if group_level is None:
                raise PurdueError("layer %r takes the level of its group, but no group level was given" % layer)
            if group_level not in self.levels:
                raise PurdueError("unknown group level %r" % group_level)
            return group_level
        return lv

    def unconfirmed(self, layers_in_use=None):
        """[(layer, status)] for entries still awaiting confirmation, optionally only those used in a diagram."""
        return sorted((l, e.get("status", "unknown")) for l, e in self.layers.items()
                      if e.get("status") not in ("confirmed", "from dataset tag") and (layers_in_use is None or l in layers_in_use))

    def unmapped_dataset_layers(self, dataset_layers):
        return sorted(set(dataset_layers) - set(self.layers))
