"""General BOQ parser. Standard library only.

    list_sheets(path)            -> candidate BOQ sheets (a header row with Description and Qty), visible and hidden
    parse_sheet(path, sheet)     -> {'lines': [...], 'outline': [...], 'zero_qty': [...], 'no_qty': [...], 'fractional': [...], ...}

Columns are found by header text, per sheet, in any order. Only Sr, Description, Model, Make, Unit and Qty are read;
price columns are never read, so prices cannot leak into a drawing.

Rows are told apart like this (nothing is dropped silently; every row lands in lines, outline or one of the lists):
  * heading     - text but no quantity, model or make (Kemari puts category names in the Sr column, Murtiba sub-headings and
                  site names likewise); or a numbered group row with a quantity but no model, make or unit (KSU "1 Servers").
  * item        - a description and a numeric quantity above zero.
  * zero_qty    - an item with quantity 0 (kept in a list, not in lines).
  * no_qty      - a description with a model or make but no quantity (listed so it can be asked about).
  * total rows  - "Total", "Sub total": ignored, counted in `ignored`.
  * `content_rows` (rows with anything in them) always equals `accounted_rows` (rows that landed in one of the above).

Heading context: consecutive heading rows form a chain. The last one is the line's `section`; with two or more, the earlier
ones become `parents` and stay in force until the next chain of two or more. A single heading after items is a sibling section
and keeps the current parents. `outline` lists every heading with its row, so context lost by this rule can still be recovered.
"""
import re

import xlsx_reader

HEADER = {
    "description": r"(item )?description",
    "qty": r"qty\.?|quantity",
    "model": r"model( number| no\.?)?|part( number| no\.?)?|mlfb",
    "make": r"make|brand|manufacturer|oem",
    "unit": r"unit|uom",
    "sr": r"sr\.? ?(no\.?)?|s\.? ?no\.?|s/no|item( no\.?)?|#|sr #",
}
TOTAL = re.compile(r"^\s*(sub[- ]?)?total\b", re.I)


class BoqError(ValueError):
    pass


def _clean(v):
    return re.sub(r"\s+", " ", str(v)).strip() if isinstance(v, str) else ""


def _qty(v):
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        try:
            return float(v.strip().replace(",", ""))
        except ValueError:
            return None
    return None


def find_header(cells):
    """(row, {field: column}, other_headers) for the first row that has Description and Qty headers, else (None, None, None)."""
    for r in range(1, 13):
        row = {c: _clean(v).lower() for (rr, c), v in cells.items() if rr == r and isinstance(v, str)}
        cols = {}
        for field, pat in HEADER.items():
            for c, text in sorted(row.items()):
                if re.fullmatch(pat, text) and field not in cols and c not in cols.values():
                    cols[field] = c
        if "description" in cols and "qty" in cols:
            other = [_clean(cells[(r, c)]) for c in sorted(row) if c not in cols.values()]
            return r, cols, other
    return None, None, None


def list_sheets(path):
    """[{'name', 'state', 'header_row', 'columns'}] for every sheet that looks like a BOQ. Reads only the first rows."""
    out = []
    for name, state in xlsx_reader.sheets(path):
        hr, cols, _ = find_header(xlsx_reader.read_sheet(path, name, max_row=12))
        if hr:
            out.append({"name": name, "state": state, "header_row": hr, "columns": sorted(cols)})
    return out


def parse_sheet(path, sheet):
    cells = xlsx_reader.read_sheet(path, sheet)
    hr, col, other = find_header(cells)
    if hr is None:
        raise BoqError("sheet %r has no header row with Description and Qty" % sheet)
    maxr = max(r for r, _ in cells)
    res = {"sheet": sheet, "header_row": hr, "columns": dict(col), "unread_columns": other, "lines": [], "outline": [],
           "zero_qty": [], "no_qty": [], "fractional": [], "ignored": [], "content_rows": 0, "accounted_rows": 0}
    get = lambda r, f: cells.get((r, col[f])) if f in col else None
    chain, parent_items, section, prev_heading = [], [], "", False
    for r in range(hr + 1, maxr + 1):
        desc, qty = _clean(get(r, "description")), _qty(get(r, "qty"))
        sr = get(r, "sr")
        sr = ("%g" % sr) if isinstance(sr, float) else _clean(sr)
        model, make, unit = _clean(get(r, "model")), _clean(get(r, "make")), _clean(get(r, "unit"))
        # a non-numeric entry in the Sr column (a category name); other columns left of Description, such as a 'Filter' tag, are not headings
        left_cols = [col["sr"]] if "sr" in col else range(1, col["description"])
        left = [t for t in (_clean(cells.get((r, c))) for c in left_cols) if t and not re.fullmatch(r"[\d.]+", t)]
        if not (desc or qty is not None or model or make or unit or left or sr):
            continue                                            # blank row: does not end a heading chain
        res["content_rows"] += 1
        if desc and TOTAL.match(desc) and not model and not make:
            res["ignored"].append({"row": r, "text": desc, "why": "total row"})
            res["accounted_rows"] += 1
            continue
        numbered_group = re.fullmatch(r"\d+", sr) is not None and not (model or make or unit)
        desc_only = bool(desc) and not (model or make or unit)
        if not desc and left:
            heading, kind = left[-1], "left"
        elif desc_only and numbered_group:
            heading, kind = desc, "numbered"
        elif desc_only and (qty is None or (qty == 1 and not sr)):
            heading, kind = desc, "desc"
        else:
            heading, kind = "", ""
        if heading:
            if not prev_heading:
                chain = []
            chain.append((heading, kind))
            prev_heading = True
            section = chain[-1][0]
            res["outline"].append({"row": r, "text": heading, "sr": sr, "qty": qty})
            res["accounted_rows"] += 1
            continue
        if prev_heading and len(chain) >= 2:
            parent_items = _parents(parent_items, chain)         # the chain is complete once a non-heading row follows
        parents = [t for t, _ in parent_items]
        prev_heading = False
        if not desc:
            res["ignored"].append({"row": r, "text": sr or ("qty %g" % qty if qty is not None else ""), "why": "row without a description"})
            res["accounted_rows"] += 1
            continue
        if qty is None:
            res["no_qty"].append({"row": r, "description": desc, "model": model, "make": make, "section": section})
            res["accounted_rows"] += 1
            continue
        line = {"sheet": sheet, "row": r, "sr": sr, "section": section, "parents": list(parents), "description": desc,
                "model": model, "make": make, "unit": unit, "qty": qty}
        res["accounted_rows"] += 1
        if qty == 0:
            res["zero_qty"].append(line)
            continue
        if qty < 0:
            raise BoqError("%s row %d: negative quantity %g" % (sheet, r, qty))
        if qty != int(qty):
            res["fractional"].append(line)
        res["lines"].append(line)
    return res


def _parents(old, chain):
    """New parent list [(text, kind)] after a chain of two or more headings.

    The chain's first heading is a sibling of the deepest existing parent of the same kind (so a new numbered building
    replaces the previous building but keeps its zone, "New Buildings"); with no such parent it is a child of all of them."""
    first_kind = chain[0][1]
    for depth in range(len(old) - 1, -1, -1):
        if old[depth][1] == first_kind:
            return old[:depth] + list(chain[:-1])
    return list(old) + list(chain[:-1])
