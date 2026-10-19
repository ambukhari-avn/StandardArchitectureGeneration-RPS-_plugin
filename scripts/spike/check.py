"""Reads the written .vsdx back and checks it. Also renders a preview PNG from the XML (NOT a Visio render)."""
import math, re, sys, zipfile, collections
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")
import boq, gen

NS = "{http://schemas.microsoft.com/office/visio/2012/main}"
VSDX = gen.OUT_DIR + r"\KSU_BMS_Architecture.vsdx"
EPS = 0.005


def load(path):
    z = zipfile.ZipFile(path)
    pgx = z.read("visio/pages/pages.xml").decode()
    W = float(re.search(r"N='PageWidth' V='([\d.]+)'", pgx).group(1))
    H = float(re.search(r"N='PageHeight' V='([\d.]+)'", pgx).group(1))
    root = ET.fromstring(z.read("visio/pages/page1.xml"))
    shapes = []
    for sh in root.iter(NS + "Shape"):
        cell = {c.get("N"): c.get("V") for c in sh.findall(NS + "Cell")}
        g = sh.find(NS + "Section[@N='Geometry']")
        rows = [(r.get("T"), float(next(c.get("V") for c in r if c.get("N") == "X")),
                 float(next(c.get("V") for c in r if c.get("N") == "Y"))) for r in g.findall(NS + "Row") if r.get("T") != "Ellipse"] if g is not None else []
        ell = g is not None and g.find(NS + "Row[@T='Ellipse']") is not None
        t = sh.find(NS + "Text")
        text = "".join(t.itertext()) if t is not None else ""
        ch = sh.find(NS + "Section[@N='Character']")
        size = float(next(c.get("V") for c in ch.iter(NS + "Cell") if c.get("N") == "Size")) * 72 if ch is not None else None
        w, h = float(cell["Width"]), float(cell["Height"])
        x, y = float(cell["PinX"]) - w / 2, float(cell["PinY"]) - h / 2
        u = {r.get("N"): next(cc.get("V") for cc in r if cc.get("N") == "Value") for r in sh.findall(NS + "Section[@N='User']/" + NS + "Row")}
        name = (u["BoqKey"] + ("|qty=" + u["BoqQty"] if "BoqQty" in u else "")) if "BoqKey" in u else None
        para = sh.find(NS + "Section[@N='Paragraph']")
        ha = int(next(cc.get("V") for cc in para.iter(NS + "Cell") if cc.get("N") == "HorzAlign")) if para is not None else 1
        shapes.append(dict(id=int(sh.get("ID")), name=name, halign=ha, x=x, y=y, w=w, h=h, cell=cell, rows=rows,
                           ellipse=ell, text=text, size=size, bold=(ch is not None and any(c.get("N") == "Style" and c.get("V") == "1" for c in ch.iter(NS + "Cell")))))
    return W, H, shapes


def inter(a, b, shrink=0.0):
    return (a["x"] + shrink < b["x"] + b["w"] - shrink and b["x"] + shrink < a["x"] + a["w"] - shrink and
            a["y"] + shrink < b["y"] + b["h"] - shrink and b["y"] + shrink < a["y"] + a["h"] - shrink)


def seg_hits(p, q, box, sh=0.02):
    x0, x1 = sorted((p[0], q[0])); y0, y1 = sorted((p[1], q[1]))
    return x0 < box["x"] + box["w"] - sh and x1 > box["x"] + sh and y0 < box["y"] + box["h"] - sh and y1 > box["y"] + sh


def run():
    title, sections, items = boq.parse(gen.BOQ_PATH)
    ctl, old, bld = gen.gather(sections, items)
    gen.WARNINGS.clear()
    pg = gen.build(title, ctl, old, bld)           # model (roles/parents) - same code that wrote the file
    W, H, xs = load(VSDX)
    problems, notes = [], []
    # 1. XML <-> model round trip
    if len(xs) != len(pg.shapes):
        problems.append("shape count: xml %d vs model %d" % (len(xs), len(pg.shapes)))
    by = {s["id"]: s for s in xs}
    for m in pg.shapes:
        x = by[m["id"]]
        if any(abs(x[k] - m[k]) > 1e-4 for k in ("x", "y", "w", "h")) or x["text"] != m["text"]:
            problems.append("round-trip mismatch shape %d" % m["id"])
            break
    # 2. page size A3
    if abs(W - 16.5354) > 0.01 or abs(H - 11.6929) > 0.01:
        problems.append("page size %sx%s is not A3 landscape" % (W, H))
    # 3. bounds
    for m in pg.shapes:
        if m["x"] < 0.2 - EPS or m["y"] < 0.2 - EPS or m["x"] + m["w"] > W - 0.2 + EPS or m["y"] + m["h"] > H - 0.2 + EPS:
            problems.append("outside page margin: shape %d %r" % (m["id"], m["text"][:30]))
    # 4. containment in parent
    P = {m["id"]: m for m in pg.shapes}
    for m in pg.shapes:
        p = P.get(m["parent"])
        if p and m["role"] != "line" and (m["x"] < p["x"] - EPS or m["y"] < p["y"] - EPS or m["x"] + m["w"] > p["x"] + p["w"] + EPS or m["y"] + m["h"] > p["y"] + p["h"] + EPS):
            problems.append("child outside parent: %d %r in %d" % (m["id"], m["text"][:30] or m["key"], p["id"]))
    # 5. overlaps: blocks with same parent; icons/text among themselves
    blocks = [m for m in pg.shapes if m["role"] == "block"]
    for i, a in enumerate(blocks):
        for b in blocks[i + 1:]:
            if a["parent"] == b["parent"] and inter(a, b, EPS) and not (a["w"] > 20):
                problems.append("blocks overlap: %d %r / %d %r" % (a["id"], a["text"][:20], b["id"], b["text"][:20]))
    ico = [m for m in pg.shapes if m["role"] in ("icon", "text")]
    for i, a in enumerate(ico):
        for b in ico[i + 1:]:
            if inter(a, b, 0.01):
                problems.append("overlap: %s %r / %s %r" % (a["role"], a["text"][:20] or a["key"], b["role"], b["text"][:20] or b["key"]))
    # 6. lines through icons/text
    for l in (m for m in pg.shapes if m["role"] == "line"):
        for p, q in zip(l["pts"], l["pts"][1:]):
            for b in ico:
                if b["text"] == "" and b["role"] == "text":
                    continue
                if seg_hits(p, q, b):
                    problems.append("line %d crosses %s %r" % (l["id"], b["role"], b["text"][:20] or b["key"]))
    # 7. font floor + text fit (estimate)
    for m in pg.shapes:
        if m["text"]:
            if m["size"] < gen.FONT_FLOOR:
                problems.append("font %.1fpt below floor: %r" % (m["size"], m["text"][:30]))
            cw = 0.52 * m["size"] / 72 * (1.08 if m["bold"] else 1)
            usable = max(m["w"] - 0.04, 0.05)
            lines = sum(max(1, math.ceil(len(seg) * cw / usable)) for seg in m["text"].split("\n"))
            if m["kind"] == "ellipse":
                continue
            if lines * m["size"] * 1.2 / 72 > m["h"] + 0.02:
                problems.append("text may overflow (%d lines, h=%.2f): %r" % (lines, m["h"], m["text"][:40]))
    # 8. BOQ reconciliation, from the XML: every drawn key's qty == BOQ qty
    drawn = collections.Counter()
    for x in xs:
        if x["name"] and "|qty=" in x["name"]:
            k, q = x["name"].split("|qty=")
            drawn[k] += int(q)
    exp = collections.Counter()
    for it in items:
        if it["bucket"] == "drawn":
            exp[it["key"]] += int(it["qty"])
    # rio drawn once per RIO icon (qty=1); eth_switch/fo_panel summed across control room + masters + old
    for k in sorted(set(exp) | set(drawn)):
        if exp[k] != drawn[k]:
            problems.append("BOQ qty mismatch %s: BOQ %d vs drawn %d" % (k, exp[k], drawn[k]))
    notes.append("drawn-vs-BOQ quantities per device type: %s" % dict(sorted(exp.items())))
    buckets = collections.Counter(it["bucket"] for it in items)
    notes.append("BOQ lines by bucket (none unclassified): %s" % dict(buckets))
    return W, H, xs, pg, problems, notes


def preview(xs, W, H, out, scale=140):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (int(W * scale), int(H * scale)), "white")
    d = ImageDraw.Draw(im)
    Y = lambda y: (H - y) * scale
    X = lambda x: x * scale
    font = lambda pt, b=False: ImageFont.truetype(r"C:\Windows\Fonts\%s.ttf" % ("arialbd" if b else "arial"), max(7, int(pt / 72 * scale)))
    for s in xs:
        c = s["cell"]
        fill = c.get("FillForegnd") if c.get("FillPattern") == "1" else None
        line = c.get("LineColor") if c.get("LinePattern") != "0" else None
        lw = max(1, int(float(c.get("LineWeight", 0.01)) * scale))
        x0, y0, x1, y1 = X(s["x"]), Y(s["y"] + s["h"]), X(s["x"] + s["w"]), Y(s["y"])
        if s["ellipse"]:
            d.ellipse([x0, y0, x1, y1], outline=line, width=lw)
        elif len(s["rows"]) >= 2 and s["rows"][0][0] == "MoveTo" and not (len(s["rows"]) == 5 and s["rows"][2][1] == s["w"] and s["rows"][2][2] == s["h"] and s["rows"][1][2] == 0):
            pts = [(X(s["x"] + px), Y(s["y"] + py)) for _, px, py in s["rows"]]
            pat = c.get("LinePattern")
            d.line(pts, fill=line, width=lw)
        else:
            d.rectangle([x0, y0, x1, y1], fill=fill, outline=line, width=lw if line else 0)
        if s["text"] and s["size"]:
            f = font(s["size"], s["bold"])
            words, lines_ = [], []
            for para in s["text"].split("\n"):
                cur = ""
                for wd in para.split(" "):
                    t = (cur + " " + wd).strip()
                    if d.textlength(t, font=f) <= (x1 - x0) - 3 or not cur:
                        cur = t
                    else:
                        lines_.append(cur); cur = wd
                lines_.append(cur)
            lh = f.size * 1.15
            va = int(c.get("VerticalAlign", 1))
            ha = 0
            for p in s["text"] and [0]:
                pass
            y = y0 + 2 if va == 0 else (y1 - lh * len(lines_) - 2 if va == 2 else (y0 + y1) / 2 - lh * len(lines_) / 2)
            for ln in lines_:
                tw = d.textlength(ln, font=f)
                hz = s.get("halign", 1)
                tx = x0 + 2 if hz == 0 else x1 - tw - 2 if hz == 2 else (x0 + x1) / 2 - tw / 2
                d.text((tx, y), ln, fill="black", font=f)
                y += lh
    im.save(out)


if __name__ == "__main__":
    W, H, xs, pg, problems, notes = run()
    print("page %.4f x %.4f in, %d shapes read back from the .vsdx" % (W, H, len(xs)))
    for n in notes: print(" -", n)
    print("warnings from BOQ:", gen.WARNINGS)
    print("PROBLEMS: %d" % len(problems))
    for p in problems[:60]: print("  *", p)
    preview(xs, W, H, gen.OUT_DIR + r"\preview.png")
