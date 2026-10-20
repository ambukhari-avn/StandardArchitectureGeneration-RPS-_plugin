"""Dev check: one A3 page showing every distinct dataset component as it will be drawn, grouped by Purdue level.

    python scripts/catalogue.py [--out <file.vsdx>]      (default: <Downloads>/out/dataset_catalogue.vsdx)

Exercises the dataset, the Purdue map, picture/box drawing and the footer together. Not part of the /arch flow.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import footer
from components import Components
from draw import draw_component
from purdue import INHERIT, PurdueMap
from vsdx_writer import A3_H, A3_W, Page, write_vsdx

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "base", "base.vsdx")
PIC_W, PIC_H, BOX_W, BOX_H, GAP = 1.00, 0.92, 1.28, 0.40, 0.06


def build():
    comps, pm = Components(), PurdueMap()
    pg = Page()
    frame = pg.rect("frame", 0.20, 0.20, A3_W - 0.40, A3_H - 0.40, fill=None, lw=1.25)
    info = footer.build_footer(pg, {"end_user": "Catalogue", "contractor": "check", "project": "Dataset catalogue (dev check)",
                                    "prepared_by": "-", "checked_by": "-", "approved_by": "-"}, [], ["Every distinct dataset component, grouped by Purdue level."], parent=frame)
    groups = {}
    for c in comps.distinct():
        lv = pm.layers[c["layer"]]["level"]
        groups.setdefault(lv, []).append(c)
    order = [l for l in pm.levels if l in groups] + ([INHERIT] if INHERIT in groups else [])
    names = dict(pm.levels, **{INHERIT: "Takes the level of the group it is placed in (Network, HMI)"})
    x0, x1, y = 0.40, A3_W - 0.40, A3_H - 0.30
    for lv in order:
        items = groups[lv]
        pg.text(x0, y - 0.22, x1 - x0, 0.22, ("Level %s - %s" % (lv, names[lv])) if lv != INHERIT else names[lv], frame, size=9, bold=True, halign=0)
        y -= 0.28
        for want_pic in (True, False):
            sel = [c for c in items if bool(comps.picture_path(c["id"])) == want_pic]
            w, h = (PIC_W, PIC_H) if want_pic else (BOX_W, BOX_H)
            cols = int((x1 - x0 + GAP) // (w + GAP))
            for i, c in enumerate(sel):
                r, k = divmod(i, cols)
                draw_component(pg, comps, c["id"], x0 + k * (w + GAP), y - (r + 1) * (h + GAP) + GAP, w, h, parent=frame)
            if sel:
                y -= ((len(sel) + cols - 1) // cols) * (h + GAP)
        y -= 0.10
    if y < info["top"] + 0.05:
        raise ValueError("catalogue does not fit above the footer (needs %.2f in more)" % (info["top"] + 0.05 - y))
    return pg


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.expanduser("~"), "Downloads", "out", "dataset_catalogue.vsdx"))
    a = ap.parse_args()
    pg = build()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    write_vsdx(pg, a.out, BASE, "Dataset catalogue")
    print("wrote %s (%d shapes)" % (a.out, len(pg.shapes)))
