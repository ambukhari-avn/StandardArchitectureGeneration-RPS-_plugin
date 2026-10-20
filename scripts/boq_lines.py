"""Read item lines from a BOQ sheet (description, model, make, unit, qty), whatever the column order. Standard library only.

Columns are found by header text, per sheet (Kemari's 'BOQ Foreign' and 'PLC F&G' sheets order them differently).
Price columns are never read. This is the minimal reader the matching report needs; the full parser (Phase 3) builds on it.
"""
import re

import xlsx_reader


def _find_header(cells):
    for r in range(1, 9):
        row = {c: str(v).strip().lower() for (rr, c), v in cells.items() if rr == r and isinstance(v, str)}
        if "description" in row.values() and "qty" in row.values():
            return r, row
    return None, None


def read_lines(path, sheet):
    cells = xlsx_reader.read_sheet(path, sheet)
    hr, hdr = _find_header(cells)
    if hr is None:
        raise ValueError("sheet %r has no header row with 'Description' and 'Qty'" % sheet)
    col = {}
    for c, h in hdr.items():
        if h == "description": col["description"] = c
        elif h.startswith("model"): col["model"] = c
        elif h == "make": col["make"] = c
        elif h == "unit": col["unit"] = c
        elif h == "qty": col["qty"] = c
    clean = lambda v: re.sub(r"\s+", " ", str(v)).strip() if isinstance(v, str) else ""
    lines, section = [], ""
    for r in range(hr + 1, max(rr for rr, _ in cells) + 1):
        desc = clean(cells.get((r, col["description"])))
        qty = cells.get((r, col["qty"]))
        if not desc:
            # a heading sits in a column left of the description (e.g. the serial-number column)
            left = [clean(cells.get((r, c))) for c in range(1, col["description"]) if clean(cells.get((r, c)))]
            if left and not isinstance(qty, float):
                section = left[-1]
            continue
        if isinstance(qty, float) and qty > 0:
            lines.append({"sheet": sheet, "row": r, "section": section, "description": desc,
                          "model": clean(cells.get((r, col.get("model", 0)))), "make": clean(cells.get((r, col.get("make", 0)))),
                          "unit": clean(cells.get((r, col.get("unit", 0)))), "qty": qty})
    return lines
