"""Quantity rules: how a stated quantity becomes drawn items. Standard library only.

Three modes (collapsing is off by default, decisions D11):
  instances - one item per unit, numbered "-01", "-02", ... ; refused above `max_instances` (never collapsed silently);
  count     - one item labelled " x N" (an explicit, configured collapse);
  type      - one item, no count shown (the type-level style of the F&G drawings).

A fractional quantity is rounded up and noted; zero or negative is refused.
"""
import math

MODES = ("instances", "count", "type")
DEFAULT_MODE = "instances"
DEFAULT_MAX_INSTANCES = 12


class QuantityError(ValueError):
    pass


def whole(qty):
    """(n, note): n a whole number >= 1. Fractions are rounded up with a note; zero or negative raises."""
    if not isinstance(qty, (int, float)) or isinstance(qty, bool) or qty <= 0 or qty != qty:
        raise QuantityError("quantity must be a positive number, got %r" % (qty,))
    if abs(qty - round(qty)) < 1e-9:
        return max(1, int(round(qty))), None
    n = math.ceil(qty)
    return n, "quantity %g is not a whole number; rounded up to %d" % (qty, n)


def plan(qty, mode=DEFAULT_MODE, max_instances=DEFAULT_MAX_INSTANCES):
    """-> {'n', 'mode', 'suffixes', 'shown', 'notes'}.

    suffixes: one label suffix per drawn item (pass each to draw.draw_component(suffix=...)).
    shown: True if the quantity can be read from the drawing (item count or " x N" label)."""
    if mode not in MODES:
        raise QuantityError("unknown quantity mode %r (use one of %s)" % (mode, ", ".join(MODES)))
    n, note = whole(qty)
    notes = [note] if note else []
    if mode == "type":
        return {"n": n, "mode": mode, "suffixes": [""], "shown": False, "notes": notes + (["quantity %d not shown (type mode)" % n] if n > 1 else [])}
    if mode == "count":
        return {"n": n, "mode": mode, "suffixes": [" x%d" % n if n > 1 else ""], "shown": True, "notes": notes}
    if n > max_instances:
        raise QuantityError("%d items would be drawn one by one; the limit is %d. Use mode 'count' or 'type', or raise the limit "
                            "(collapsing is never done silently)" % (n, max_instances))
    width = max(2, len(str(n)))
    return {"n": n, "mode": mode, "suffixes": [""] if n == 1 else ["-%0*d" % (width, i) for i in range(1, n + 1)], "shown": True, "notes": notes}
