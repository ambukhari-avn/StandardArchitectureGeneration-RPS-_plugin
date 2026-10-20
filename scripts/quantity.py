"""Quantity rules: how a BOQ quantity becomes drawn items. Standard library only.

Three modes (collapsing is off by default, decisions D11):
  instances - one item per unit, numbered "-01", "-02", ... ; refused above `max_instances` (never collapsed silently);
  count     - one item labelled " x N" (an explicit, configured collapse);
  type      - one item, no count shown (the type-level style of the F&G drawings).

Units decide whether a quantity is a count at all: metres and hours are not items and are refused; 'lot' and 'job' are
packages. Fractional quantities (Murtiba has 8.66667) are rounded up and noted, because a BOQ can't mean 0.67 of a rack.
"""
import math
import re

MODES = ("instances", "count", "type")
DEFAULT_MODE = "instances"
DEFAULT_MAX_INSTANCES = 12


class QuantityError(ValueError):
    pass


def unit_kind(unit):
    """'count' | 'lot' | 'length' | 'time' | 'other' for a BOQ unit string."""
    u = re.sub(r"\s+", " ", str(unit or "")).strip().lower().rstrip(".")
    if u in ("", "no", "nos", "pc", "pcs", "each", "ea", "set", "sets", "unit", "units"):
        return "count"
    if u in ("lot", "lump sum", "lumpsum", "ls", "job"):
        return "lot"
    if re.fullmatch(r"m|mtr|mtrs|metr|meter|meters|metre|metres|km|mm", u):
        return "length"
    if re.fullmatch(r"(man[- ]?)?days?|hours?( ?/ ?lot)?|hrs?|man[- ]?hours?", u):
        return "time"
    return "other"


def whole(qty):
    """(n, note): n a whole number >= 1. Fractions are rounded up with a note; zero or negative raises."""
    if not isinstance(qty, (int, float)) or isinstance(qty, bool) or qty <= 0 or qty != qty:
        raise QuantityError("quantity must be a positive number, got %r" % (qty,))
    n = math.ceil(qty - 1e-9)
    note = None if abs(qty - round(qty)) < 1e-9 else "quantity %g is not a whole number; rounded up to %d" % (qty, n)
    return max(1, int(round(qty)) if note is None else n), note


def plan(qty, unit="", mode=DEFAULT_MODE, max_instances=DEFAULT_MAX_INSTANCES):
    """-> {'n', 'mode', 'suffixes', 'shown', 'notes'}.

    suffixes: one label suffix per drawn item (pass each to draw.draw_component(suffix=...)).
    shown: True if the quantity can be read from the drawing (item count or " x N" label)."""
    if mode not in MODES:
        raise QuantityError("unknown quantity mode %r (use one of %s)" % (mode, ", ".join(MODES)))
    kind = unit_kind(unit)
    if kind in ("length", "time"):
        raise QuantityError("a quantity of %g %s cannot be drawn as items" % (qty, unit))
    n, note = whole(qty)
    notes = [note] if note else []
    if kind == "lot" and n > 1:
        notes.append("unit %r with quantity %d: treated as %d items" % (unit, n, n))
    if kind == "other":
        notes.append("unit %r not recognised: quantity treated as a count" % unit)
    if mode == "type":
        return {"n": n, "mode": mode, "suffixes": [""], "shown": False, "notes": notes + (["quantity %d not shown (type mode)" % n] if n > 1 else [])}
    if mode == "count":
        return {"n": n, "mode": mode, "suffixes": [" x%d" % n if n > 1 else ""], "shown": True, "notes": notes}
    if n > max_instances:
        raise QuantityError("%d items would be drawn one by one; the limit is %d. Use mode 'count' or 'type', or raise the limit "
                            "(collapsing is never done silently)" % (n, max_instances))
    width = max(2, len(str(n)))
    return {"n": n, "mode": mode, "suffixes": [""] if n == 1 else ["-%0*d" % (width, i) for i in range(1, n + 1)], "shown": True, "notes": notes}
