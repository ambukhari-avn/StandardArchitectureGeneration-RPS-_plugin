"""Build the A3 Visio file from a spec that passes the validator.   Standard library only.

    python scripts/build_diagram.py spec.json [--out diagram.vsdx] [--preview]

Steps: validate -> one band per Purdue level (highest at the top) -> items placed in rows (picture or box, one per unit or one
"x N" item, as the spec's quantity mode says) -> connections routed square through the gaps between bands, in the cable's colour
-> geometric checks -> footer (title block, short notes, legend) -> .vsdx. Nothing is placed by the language model; nothing that is
not in the spec is drawn. Connections drawn here are exactly those of the spec; ones marked 'assumed' are counted in the notes.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import footer
import quantity
import spec as S
from cables import Cables
from components import Components
from draw import BOX_FILL, BOX_LINE, BOX_SIZES, LABEL_SIZES, LABEL_ZONE, draw_component
from purdue import PurdueMap
from textfit import TextFitError, fit_size
from vsdx_writer import A3_H, A3_W, Page, write_vsdx

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MARGIN, STRIP = footer.X0, 1.05                  # page margin; width of the level-name strip left of each band
PAD, GAP, ROW_GAP, TOP_LANE = 0.12, 0.12, 0.14, 0.30
MIN_CHANNEL, MAX_CHANNEL = 0.40, 1.50           # space between bands for the connection lanes
SCALES = (1.3, 1.15, 1.0, 0.85, 0.70)           # item size ladder: the first that fits the page wins (never below the font floor)
PIC, BOX = (1.00, 0.95), (1.35, 0.55)
PANEL_W = 2.10                                  # side panel for VM contents
BAND_FILL, BAND_LINE = "#F7F9FC", "#9AA5B1"


class BuildError(ValueError):
    pass


# ---- items ----------------------------------------------------------------------------------------------------------------
def make_items(spec, comps, purdue, srules):
    """One entry per drawn item, in spec order: dict(dev, level, label, comp, mode, key, vm, qty, suffix)."""
    items = []
    opts = spec["options"]
    for g in spec["groups"]:
        for d in g["devices"]:
            label = comps.get(d["component"])["label"] if d.get("component") else d["label"]
            plan = quantity.plan(d["qty"], d.get("quantity_mode") or opts["quantity_mode"], opts.get("max_instances", quantity.DEFAULT_MAX_INSTANCES))
            for suffix in plan["suffixes"]:
                items.append(dict(dev=d["id"], level=g["level"], label=label + suffix, comp=d.get("component"),
                                  mode=S.render_mode(d, g, comps, purdue, srules), key="prompt:" + d["quote"], vm=d.get("vm"),
                                  qty=d["qty"], suffix=suffix))
    return items


def item_size(it, scale):
    """(w, h) of the cell: widened step by step until the label fits at or above the font floor."""
    base, sizes, zone = (PIC, LABEL_SIZES, LABEL_ZONE) if it["mode"] == "picture" else (BOX, BOX_SIZES, None)
    for k in (1.0, 1.25, 1.5, 2.0, 2.6):
        w, h = base[0] * scale * k, base[1] * scale
        try:
            fit_size(it["label"], w, zone or h, sizes)
            return w, h
        except TextFitError:
            continue
    raise BuildError("the label %r is too long to fit an item at 6 pt" % it["label"])


def flow_rows(sizes, inner_w):
    """Split items (by width) into rows no wider than inner_w; returns lists of indexes."""
    rows, cur, used = [], [], 0.0
    for i, (w, _) in enumerate(sizes):
        if cur and used + GAP + w > inner_w:
            rows.append(cur)
            cur, used = [], 0.0
        used += (GAP if cur else 0) + w
        cur.append(i)
    return rows + ([cur] if cur else [])


def band_height(sizes, rows):
    return TOP_LANE + sum(max(sizes[i][1] for i in r) for r in rows) + ROW_GAP * (len(rows) - 1) + PAD


# ---- geometry helpers -----------------------------------------------------------------------------------------------------
def rect_of(it):
    return it["x"], it["y"], it["w"], it["h"]


def seg_hits(p, q, r, inset=0.01):
    x, y, w, h = r
    x0, x1, y0, y1 = x + inset, x + w - inset, y + inset, y + h - inset
    sx0, sx1, sy0, sy1 = min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1])
    return sx1 > x0 and sx0 < x1 and sy1 > y0 and sy0 < y1


def overlap(a, b):
    return a["x"] < b["x"] + b["w"] - 1e-6 and b["x"] < a["x"] + a["w"] - 1e-6 and a["y"] < b["y"] + b["h"] - 1e-6 and b["y"] < a["y"] + a["h"] - 1e-6


def hits(pts, items, skip):
    return sum(1 for p, q in zip(pts, pts[1:]) for it in items if it["id"] not in skip and seg_hits(p, q, rect_of(it)))


def dedupe(pts):
    out = []
    for p in pts:
        if not out or abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6:
            out.append(p)
    return out


def route_between(a, b, lane, items):
    """Square route from item a (upper) to item b (lower) through the lane y; first candidate that touches no other item wins.
    Returns (points, crossings)."""
    def exits(it, from_bottom):
        cx, edge_y, cy = it["x"] + it["w"] / 2, (it["y"] if from_bottom else it["y"] + it["h"]), it["y"] + it["h"] / 2
        out = [(cx, [(cx, edge_y)])]
        for edge, gx in ((it["x"] + it["w"], it["x"] + it["w"] + 0.06), (it["x"], it["x"] - 0.06)):
            out.append((gx, [(edge, cy), (gx, cy)]))
        return out
    best = None
    for ax, a_pre in exits(a, True):
        for bx, b_pre in exits(b, False):
            pts = dedupe(a_pre + [(ax, lane), (bx, lane)] + b_pre[::-1])
            c = hits(pts, items, {a["id"], b["id"]})
            if best is None or c < best[1] or (c == best[1] and len(pts) < len(best[0])):
                best = (pts, c)
            if c == 0 and len(pts) <= 4:
                return pts, 0
    return best


def route_same(a, b, top_y, items):
    """Route between two items of one band: straight along a row, else over the top of the band."""
    if a["x"] > b["x"]:
        a, b = b, a
    acy, bcy = a["y"] + a["h"] / 2, b["y"] + b["h"] / 2
    cands = []
    if abs(acy - bcy) < 0.05:
        cands.append([(a["x"] + a["w"], acy), (b["x"], bcy)])
    cands.append(dedupe([(a["x"] + a["w"] / 2, a["y"] + a["h"]), (a["x"] + a["w"] / 2, top_y), (b["x"] + b["w"] / 2, top_y), (b["x"] + b["w"] / 2, b["y"] + b["h"])]))
    best = None
    for pts in cands:
        c = hits(pts, items, {a["id"], b["id"]})
        if best is None or c < best[1]:
            best = (pts, c)
        if c == 0:
            break
    return best


# ---- drawing --------------------------------------------------------------------------------------------------------------
def draw_item(page, comps, it):
    x, y, w, h = rect_of(it)
    if it["mode"] == "picture":
        ids = draw_component(page, comps, it["comp"], x, y, w, h, suffix=it["suffix"], qty=int(it["qty"]))
        for i in ids:
            page.shapes[i - 1]["key"] = (page.shapes[i - 1]["key"] or "") + "|" + it["key"]
        return ids
    size = fit_size(it["label"], w, h, BOX_SIZES)
    return [page.rect("icon", x, y, w, h, fill=BOX_FILL, line=BOX_LINE, lw=1.0 if it["vm"] else 0.75, pattern=2 if it["vm"] else 1,
                      text=it["label"], size=size, key=it["key"])]


def draw_line(page, cables, c, pts):
    color, pattern = cables.line_style(c["cable"])
    key = c["from"] + "->" + c["to"]
    page.line(pts, color, pattern, lw=1.25, key=key)
    if c.get("redundant"):
        page.line([(x + 0.04, y - 0.04) for x, y in pts], color, pattern, lw=1.25, key=key + "|redundant")


def footer_notes(spec, items, has_vm):
    notes = ["Pictures are used only for components named in the dataset; every other item is a box with the wording of the prompt."]
    assumed = sum(1 for c in spec.get("connections", []) if c["basis"] == "assumed")
    if assumed:
        notes.append("%d of %d connections are assumed (not stated by the user)." % (assumed, len(spec["connections"])))
    if any(" x" in it["suffix"] for it in items):
        notes.append("x N = quantity.")
    if has_vm:
        notes.append("Dashed box = virtual machine; contents are listed at the right.")
    return notes


# ---- layout ---------------------------------------------------------------------------------------------------------------
def fit_to_page(items, levels, inner_w, avail):
    """Largest size step at which every band fits the page. Sets item sizes; returns (scale, band heights)."""
    for scale in SCALES:
        for it in items:
            it["w"], it["h"] = item_size(it, scale)
        heights = {}
        for lv in levels:
            sizes = [(it["w"], it["h"]) for it in items if it["level"] == lv]
            heights[lv] = band_height(sizes, flow_rows(sizes, inner_w))
        if sum(heights.values()) + (len(levels) - 1) * MIN_CHANNEL <= avail:
            return scale, heights
    raise BuildError("the items do not fit on one A3 page at the smallest size; use quantity_mode 'count' or 'type' "
                     "(collapsing is never done silently)")


def place_items(spec, items, levels, heights, band_y, band_x, inner_w):
    """Order devices inside each band by where their neighbours in the band above sit, then place the rows centred."""
    placed_x = {}
    for lv in levels:
        mine = [it for it in items if it["level"] == lv]
        devs = list(dict.fromkeys(it["dev"] for it in mine))
        def centre(dv):
            xs = [placed_x[o] for c in spec.get("connections", []) for o in ((c["to"],) if c["from"] == dv else (c["from"],) if c["to"] == dv else ())
                  if o in placed_x]
            return sum(xs) / len(xs) if xs else None
        centres = {dv: centre(dv) for dv in devs}
        if all(v is not None for v in centres.values()):
            devs.sort(key=lambda dv: centres[dv])
        order = [it for dv in devs for it in mine if it["dev"] == dv]
        sizes = [(it["w"], it["h"]) for it in order]
        y = band_y[lv] + heights[lv] - TOP_LANE
        for r in flow_rows(sizes, inner_w):
            rh = max(sizes[i][1] for i in r)
            x = band_x + PAD + (inner_w - sum(sizes[i][0] for i in r) - GAP * (len(r) - 1)) / 2
            for i in r:
                order[i]["x"], order[i]["y"] = x, y - rh + (rh - order[i]["h"]) / 2
                x += order[i]["w"] + GAP
            y -= rh + ROW_GAP
        for dv in devs:
            xs = [it["x"] + it["w"] / 2 for it in mine if it["dev"] == dv]
            placed_x[dv] = sum(xs) / len(xs)


def draw_bands(page, spec, levels, heights, band_y, band_x, band_w):
    titles = {}
    for g in spec["groups"]:
        titles.setdefault(g["level"], []).append(g["title"])
    for lv in levels:
        page.rect("band", band_x, band_y[lv], band_w, heights[lv], fill=BAND_FILL, line=BAND_LINE, lw=0.75)
        label = "Level %s\n%s" % (lv, " / ".join(titles[lv]))
        page.text(MARGIN, band_y[lv], STRIP, heights[lv], label, size=fit_size(label, STRIP - 0.06, heights[lv], (8, 7, 6.5, 6), bold=True), bold=True)


def draw_connections(page, cables, spec, items, by_dev, band_y, heights):
    """Draw every connection of the spec. Links leaving one item in one cable share a lane (a bus). Returns warnings."""
    level_of = {it["dev"]: it["level"] for it in items}
    jobs = []                                                    # (connection, upper item, lower item, shared end)
    for c in spec.get("connections", []):
        A, B = by_dev[c["from"]], by_dev[c["to"]]
        small, big = (A, B) if len(A) <= len(B) else (B, A)
        for x in big:
            near = min(small, key=lambda s: abs(s["x"] + s["w"] / 2 - x["x"] - x["w"] / 2))
            a, b = (near, x) if big is B else (x, near)
            if float(level_of[a["dev"]]) < float(level_of[b["dev"]]):
                a, b = b, a
            jobs.append((c, a, b, near))
    by_channel = {}
    for job in jobs:
        by_channel.setdefault((job[1]["level"], job[2]["level"]), []).append(job)
    warnings = []
    for (la, lb), js in by_channel.items():
        js.sort(key=lambda j: (j[3]["x"], j[0]["cable"], j[1]["x"] + j[2]["x"]))
        if la == lb:
            step = min(0.05, (TOP_LANE - 0.1) / len(js))
            for k, (c, a, b, _) in enumerate(js):
                pts, crossed = route_same(a, b, band_y[la] + heights[la] - 0.06 - k * step, items)
                if crossed:
                    warnings.append("connection %s -> %s passes through %d other item(s)" % (c["from"], c["to"], crossed))
                draw_line(page, cables, c, pts)
            continue
        top, bottom = band_y[la], band_y[lb] + heights[lb]
        bus = lambda j: ((j[1] if j[1]["dev"] == j[0]["from"] else j[2])["id"], j[0]["cable"])
        lanes = list(dict.fromkeys(bus(j) for j in js))
        for job in js:
            c, a, b, _ = job
            pts, crossed = route_between(a, b, top - (lanes.index(bus(job)) + 1) * (top - bottom) / (len(lanes) + 1), items)
            if crossed:
                warnings.append("connection %s -> %s passes through %d other item(s)" % (c["from"], c["to"], crossed))
            draw_line(page, cables, c, pts)
    return warnings, len(jobs)


def draw_rings(page, cables, spec, by_dev):
    for r in spec.get("rings", []):
        members = [it for dv in r["members"] for it in by_dev[dv]]
        x0, y0 = min(m["x"] for m in members) - 0.08, min(m["y"] for m in members) - 0.08
        x1, y1 = max(m["x"] + m["w"] for m in members) + 0.08, max(m["y"] + m["h"] for m in members) + 0.08
        color, pattern = cables.line_style(r["cable"])
        page.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], color, pattern, lw=1.5, key="ring:" + r["id"])


def draw_vm_panel(page, vms, y_top):
    """Side panel listing what runs inside each VM. Returns the y of its lowest edge."""
    px, py = A3_W - MARGIN - PANEL_W, y_top
    for it in vms:
        box_h = 0.30 + 0.38 * len(it["vm"]["contents"]) + 0.10
        py -= box_h
        page.rect("band", px, py, PANEL_W, box_h, fill=BAND_FILL, line=BAND_LINE, lw=0.75)
        title = "%s: contents" % it["label"]
        page.text(px, py + box_h - 0.30, PANEL_W, 0.28, title, size=fit_size(title, PANEL_W - 0.06, 0.28, (7, 6.5, 6), bold=True), bold=True)
        for n, text in enumerate(it["vm"]["contents"]):
            page.rect("icon", px + 0.10, py + box_h - 0.30 - 0.38 * (n + 1), PANEL_W - 0.20, 0.32, fill=BOX_FILL, line=BOX_LINE,
                      text=text, size=fit_size(text, PANEL_W - 0.20, 0.32, BOX_SIZES), key="vm:" + it["dev"])
        py -= 0.15
    return py


def geometric_problems(items, y_bottom, y_top):
    problems = []
    for it in items:
        x, y, w, h = rect_of(it)
        if x < MARGIN - 1e-6 or x + w > A3_W - MARGIN + 1e-6 or y < y_bottom - 0.12 or y + h > y_top + 1e-6:
            problems.append("%s is outside the drawing area" % it["label"])
    problems += ["%s overlaps %s" % (a["label"], b["label"]) for i, a in enumerate(items) for b in items[i + 1:] if overlap(a, b)]
    return problems


# ---- build ----------------------------------------------------------------------------------------------------------------
def build(spec, base, out, comps=None):
    """Validate `spec`, draw it and write `out` (.vsdx). Returns a summary dict (with the Page under 'page')."""
    comps, purdue, cables = comps or Components(), PurdueMap(), Cables()
    srules = S.load_json(S.RULES_PATH)
    report = S.validate(spec, comps=comps, purdue=purdue, cables=cables, srules=srules)
    if not report.ok:
        raise BuildError("the spec does not pass the validator:\n" + report.text())
    items = make_items(spec, comps, purdue, srules)
    for n, it in enumerate(items, 1):
        it["id"] = n
    by_dev = {}
    for it in items:
        by_dev.setdefault(it["dev"], []).append(it)
    levels = sorted({it["level"] for it in items}, key=float, reverse=True)       # top band first
    vms = [it for it in items if it["vm"]]

    page = Page()
    used_cables = sorted({c["cable"] for c in spec.get("connections", [])} | {r["cable"] for r in spec.get("rings", [])})
    notes = footer_notes(spec, items, bool(vms))
    info = footer.build_footer(page, spec["project"], cables.legend(used_cables), notes, spec["options"].get("allow_tbc", False))
    y_top, y_bottom = A3_H - MARGIN, info["top"] + 0.12
    band_x = MARGIN + STRIP + 0.05
    band_w = A3_W - MARGIN - band_x - (PANEL_W + 0.10 if vms else 0.0)
    inner_w = band_w - 2 * PAD

    scale, heights = fit_to_page(items, levels, inner_w, y_top - y_bottom)
    spare = y_top - y_bottom - sum(heights.values())
    gap = min(MAX_CHANNEL, spare / (len(levels) - 1)) if len(levels) > 1 else 0
    cursor = y_top - max(0.0, (spare - gap * (len(levels) - 1)) / 2)                # centre the stack of bands
    band_y = {}
    for lv in levels:
        cursor -= heights[lv]
        band_y[lv] = cursor
        cursor -= gap

    place_items(spec, items, levels, heights, band_y, band_x, inner_w)
    draw_bands(page, spec, levels, heights, band_y, band_x, band_w)
    warnings, n_lines = draw_connections(page, cables, spec, items, by_dev, band_y, heights)      # lines first, items on top
    draw_rings(page, cables, spec, by_dev)
    for it in items:
        draw_item(page, comps, it)
    problems = geometric_problems(items, y_bottom, y_top)
    if vms and draw_vm_panel(page, vms, y_top) < y_bottom:
        problems.append("the VM contents panel does not fit above the footer")
    if problems:
        raise BuildError("geometric check failed:\n  " + "\n  ".join(problems))
    write_vsdx(page, out, base, title=spec["project"].get("project", "Architecture"))
    return {"out": out, "items": len(items), "devices": len(by_dev), "bands": len(levels), "scale": scale, "connections": n_lines,
            "warnings": warnings, "notes": notes, "validator_notes": report.notes, "validator_warnings": report.warnings, "page": page}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--base", default=os.path.join(ROOT, "base", "base.vsdx"))
    ap.add_argument("--out", help="output .vsdx (default: Downloads\\out\\<spec name>.vsdx)")
    ap.add_argument("--preview", action="store_true", help="also write a PNG preview next to the file (needs Pillow; development aid)")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.expanduser("~"), "Downloads", "out", os.path.splitext(os.path.basename(a.spec))[0] + ".vsdx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        r = build(S.load_json(a.spec), a.base, out)
    except BuildError as e:
        print("NOT BUILT: %s" % e)
        sys.exit(1)
    print("built %s: %d items from %d devices in %d bands (size step %.2f), %d connection lines" % (
        r["out"], r["items"], r["devices"], r["bands"], r["scale"], r["connections"]))
    for w in r["warnings"] + ["validator: %s [%s] %s" % (w["code"], w["where"], w["message"][:140]) for w in r["validator_warnings"]]:
        print("  warning:", w)
    for n in r["notes"]:
        print("  footer note:", n)
    if a.preview:
        import dev_preview
        png = os.path.splitext(out)[0] + "_preview.png"
        dev_preview.render(r["page"], png)
        print("preview:", png)
