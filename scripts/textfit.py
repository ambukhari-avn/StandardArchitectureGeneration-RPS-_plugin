"""Text fitting: the largest font size at which text fits a box, never below the floor. Standard library only.

Widths are estimated (average glyph width 0.52 em, 8% wider for bold), deliberately on the safe side.
If nothing at or above the floor fits, TextFitError is raised - the caller must not shrink further or drop the text.
"""
import math

from vsdx_writer import FONT_FLOOR


class TextFitError(ValueError):
    pass


def lines_needed(text, width, size, bold=False):
    cw = 0.52 * size / 72 * (1.08 if bold else 1.0)
    per_line = max(1, int((width - 0.04) / cw))
    return sum(max(1, math.ceil(len(seg) / per_line)) for seg in text.split("\n"))


def fit_size(text, w, h, sizes, bold=False, floor=None):
    """First size in `sizes` (descending) at which `text` fits w x h inches; raises TextFitError if none does."""
    floor = FONT_FLOOR if floor is None else floor
    for size in sizes:
        if size < floor:
            break
        if lines_needed(text, w, size, bold) * size * 1.2 / 72 <= h + 0.01:
            return size
    raise TextFitError("text does not fit at or above %.1f pt: %r" % (floor, text[:60]))
