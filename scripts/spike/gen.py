"""Spike: BOQ -> one-page A3 .vsdx.  Stdlib only (+ PIL only for the optional preview).
Model decides nothing visual: positions come from the fixed layout below."""
import json, math, re, sys, zipfile
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import boq

BOQ_PATH = r"C:\Users\ambhukari\Downloads\BMS-SF02 - 201125 1.xlsx"
BASE_PATH = r"C:\Users\ambhukari\Downloads\BOQ n architectures\kemari\F&G_kemari 1.vsdx"
OUT_DIR = r"C:\Users\ambhukari\Downloads\dataset 1\arch-spike\out"
PW, PH = 16.5354, 11.6929            # A3 landscape, inches
WARNINGS = []
FONT_FLOOR = 6.0                      # pt, configurable legibility floor

# cable types: colour/dash come from here, never from the spec (defaults = Maaden/KSU convention; TO BE CONFIRMED)
CABLES = {"ethernet": ("Ethernet Cable", "#0070C0", 1), "fiber": ("Fiber Optical Cable", "#00B050", 1)}

# proto-dataset: key -> (label, placeholder tag, fill).  Real dataset = labelled icons from the client.
ICONS = {
    "server_rack": ("Server Rack", "RACK", "#D9D9D9"), "server": ("Server", "SRV", "#D9D9D9"),
    "historian": ("Historian Server", "SRV", "#D9D9D9"), "gps_ntp": ("GPS NTP Server", "NTP", "#D9D9D9"),
    "gps_clock": ("GPS Clock", "CLK", "#EDEDED"), "laptop": ("Maintenance Laptop", "PC", "#BDD7EE"),
    "eng_ws": ("Engineering Workstation", "WS", "#BDD7EE"), "op_ws": ("Operator Workstation", "WS", "#BDD7EE"),
    "screen65": ('65" Screen at Manager Room', "LED", "#D9E1F2"), "videowall": ("Video Wall", "VW", "#D9E1F2"),
    "vw_ctrl": ("Video Wall Controller", "CTL", "#EDEDED"), "printer_alarm": ("Alarm Printer", "PRN", "#EDEDED"),
    "printer_report": ("Report Printer", "PRN", "#EDEDED"), "eth_switch": ("Ethernet Switch", "SW", "#C6E0B4"),
    "managed_switch": ("Managed Switch", "SW", "#C6E0B4"), "fo_panel": ("FO Patch Panel", "FO", "#A9D18E"),
    "hsby": ("M580 HSBY Controller", "PLC", "#F8CBAD"), "asp": ("SpaceLogic AS-P Controller", "PLC", "#F8CBAD"),
    "old_panel": ("Control Panel", "CP", "#FFE699"), "rio": ("RIO", "RIO", "#FFE699"),
}


# ------------------------------------------------------------------ model
class Page:
    def __init__(self):
        self.shapes = []

    def add(self, kind, role, x, y, w, h, parent=None, **kw):
        s = dict(id=len(self.shapes) + 1, kind=kind, role=role, x=x, y=y, w=w, h=h, parent=parent,
                 fill=None, line="#000000", lw=0.75, pattern=1, text="", size=6.5, bold=False, halign=1,
                 valign=1, key=None, pts=None, color="#000000", rounding=0)
        s.update(kw)
        self.shapes.append(s)
        return s["id"]

    def rect(self, role, x, y, w, h, parent=None, **kw):
        return self.add("rect", role, x, y, w, h, parent, **kw)

    def text(self, x, y, w, h, text, parent=None, **kw):
        return self.add("rect", "text", x, y, w, h, parent, fill=None, line=None, text=text, **kw)

    def line(self, pts, cable, parent=None, **kw):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        _, color, _ = CABLES[cable]
        return self.add("line", "line", min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), parent,
                        pts=pts, line=color, lw=1.0, key=cable, **kw)


def icon(pg, key, cx, ytop, w, h, label, parent, qty=1, label_below=True, lw_=0.9, label_h=0.3):
    lab, tag, fill = ICONS[key]
    pg.rect("icon", cx - w / 2, ytop - h, w, h, parent, fill=fill, text=tag, size=6, bold=True,
            key="%s|qty=%d" % (key, qty), lw=0.5)
    if label_below is None:
        return
    if label_below:
        pg.text(cx - lw_ / 2, ytop - h - label_h - 0.02, lw_, label_h, label, parent, size=6, valign=0)
    else:
        pg.text(cx - lw_ / 2, ytop + 0.02, lw_, label_h, label, parent, size=6, valign=2)


# ------------------------------------------------------------------ data from BOQ
def gather(sections, items):
    ctl, old, bld, other = {}, {}, [], []
    for it in items:
        b, k = boq.classify(it)
        it["bucket"], it["key"] = b, k
    for s in sections:
        z = s["zone"]
        if z == "control":
            for it in s["items"]:
                if it["bucket"] == "drawn":
                    ctl[it["key"]] = ctl.get(it["key"], 0) + it["qty"]
        elif z == "old":
            for it in s["items"]:
                if it["bucket"] == "drawn":
                    old[it["key"]] = old.get(it["key"], 0) + it["qty"]
        elif z == "new":
            b = dict(title=s["title"], master=None, rio=0, io={}, rio_hdr=s["rio_hdr"],
                     master_title=s.get("master_title"))
            m = {}
            for it in s["items"]:
                if it["bucket"] == "drawn" and it["key"] == "rio":
                    b["rio"] += int(it["qty"])
                elif it["bucket"] == "drawn" and it["sub"] == "master":
                    m[it["key"]] = m.get(it["key"], 0) + it["qty"]
                elif it["bucket"] == "io":
                    b["io"][it["key"]] = b["io"].get(it["key"], 0) + int(it["qty"])
            b["master"] = m or None
            bld.append(b)
    return ctl, old, bld


# ------------------------------------------------------------------ layout
def build(title, ctl, old, bld):
    pg = Page()
    cx_page = lambda: PW / 2
    # page frame
    frame = pg.rect("frame", 0.20, 0.20, PW - 0.40, PH - 0.40, fill=None, lw=1.25)
    # ---- control room
    CRx0, CRx1, CRy0, CRy1 = 0.40, 16.135, 8.15, 11.40
    cr = pg.rect("block", CRx0, CRy0, CRx1 - CRx0, CRy1 - CRy0, frame, fill="#F2F2F2", lw=1.0)
    pg.text(CRx0 + 4.0, CRy1 - 0.30, CRx1 - CRx0 - 8.0, 0.26, "CONTROL ROOM - K20A", cr, size=11, bold=True)
    bus_y = 10.22
    r1 = [("laptop", None)] + [("screen65", None)] * int(ctl["screen65"]) + [("eng_ws", None)] \
        + [("op_ws", i) for i in range(1, int(ctl["op_ws"]) + 1)] + [("printer_alarm", None), ("printer_report", None)] \
        + [("videowall", i) for i in range(1, int(ctl["videowall"]) + 1)] \
        + [("vw_ctrl", i) for i in range(1, int(ctl["vw_ctrl"]) + 1)]
    assert len(r1) == 16, len(r1)
    xs1 = []
    for i, (k, n) in enumerate(r1):
        cx = 1.0 + i * 0.95
        lab = ICONS[k][0] + ("-%02d" % n if n and k == "op_ws" else "-%d" % n if n else "")
        if k == "videowall":
            lab += '\n(75"x4)'
        icon(pg, k, cx, 10.76, 0.6, 0.38, lab, cr, label_below=False, label_h=0.32)
        pg.line([(cx, 10.38), (cx, bus_y)], "ethernet", cr)
        xs1.append(cx)
    r2 = [("server_rack", None)] + [("server", i) for i in range(1, int(ctl["server"]) + 1)] \
        + [("historian", None), ("gps_ntp", None), ("gps_clock", None)]
    xs2 = []
    for i, (k, n) in enumerate(r2):
        cx = 1.0 + i * 0.95
        icon(pg, k, cx, 10.16, 0.6, 0.38, ICONS[k][0] + ("-%d" % n if n else ""), cr, label_h=0.32)
        pg.line([(cx, bus_y), (cx, 10.16)], "ethernet", cr)
        xs2.append(cx)
    sw_x = [10.975, 13.825]
    assert int(ctl["eth_switch"]) == 2 and int(ctl["fo_panel"]) == 2
    pg.line([(xs1[0], bus_y), (max(xs1[-1], sw_x[-1]), bus_y)], "ethernet", cr)
    ring_cy, ring_b, ring_cx, ring_a = 7.70, 0.25, (0.30 + 16.235) / 2, (16.235 - 0.30) / 2
    ring_pt = lambda x, up: (x, ring_cy + (1 if up else -1) * ring_b * math.sqrt(max(0, 1 - ((x - ring_cx) / ring_a) ** 2)))
    for i, sx in enumerate(sw_x):
        pg.line([(sx, bus_y), (sx, 9.25)], "ethernet", cr)
        icon(pg, "eth_switch", sx, 9.25, 1.0, 0.30, "", cr, label_below=None)
        pg.text(sx - 0.55 - 1.05, 8.95, 1.05, 0.30, "Ethernet Switch", cr, size=6, halign=2)
        icon(pg, "fo_panel", sx, 8.72, 1.0, 0.22, "", cr, label_below=None)
        pg.text(sx - 0.55 - 1.05, 8.50, 1.05, 0.22, "FO Patch Panel", cr, size=6, halign=2)
        pg.line([(sx, 8.95), (sx, 8.72)], "fiber", cr)
        pg.line([(sx, 8.50), ring_pt(sx, True)], "fiber", frame)
    # ---- ring
    ring = pg.add("ellipse", "ring", 0.30, ring_cy - ring_b, 2 * ring_a, 2 * ring_b, frame, fill=None,
                  line=CABLES["fiber"][1], lw=1.0, pattern=2, text="Fiber Optic Ring", size=8, bold=True)
    # ---- grid
    gx0, gp, gw, bh = 0.45, 15.7 / 12, 15.7 / 12 - 0.14, 1.70
    rows_y = {1: 5.40, 2: 3.50, 3: 1.60}
    trunk_end = {}
    blocks = []                      # (col, span, row, kind, data)
    # wide master/old blocks sit in the bottom row so they never sit above another block's trunk
    blocks += [(0, 3, 3, "master", bld[0]), (3, 3, 3, "old", old), (6, 3, 3, "master", bld[10])]
    assert len(bld) == 19
    slots = [(c, 1) for c in range(12)] + [(c, 2) for c in range(7)]
    for (c, r), b in zip(slots, bld):
        blocks.append((c, 1, r, "bld", b))
    stub_pts = []
    for c, span, r, kind, d in blocks:
        x0, y0 = gx0 + c * gp, rows_y[r]
        w = span * gp - 0.14
        top = y0 + bh
        blk = pg.rect("block", x0, y0, w, bh, frame, fill="#FFFFFF", lw=0.75)
        trunk_x = x0 - 0.07
        pg.line([(trunk_x, y0 + bh / 2), (x0, y0 + bh / 2)], "fiber", frame)
        trunk_end[c] = min(trunk_end.get(c, 99), y0 + bh / 2)
        if kind == "bld":
            ttl = d["title"]
            pg.text(x0 + 0.03, top - 0.45, w - 0.06, 0.43, ttl, blk, size=6.5, bold=True, valign=0)
            n = d["rio"]
            hdr = re.search(r"\((?:1-)?(\d+)\)", d["rio_hdr"])
            if not hdr or int(hdr.group(1)) != n:      # BOQ header disagrees with its own priced lines: draw the lines, warn
                WARNINGS.append("%s: BOQ header says '%s' but %d RIO panels are listed - %d drawn." % (
                    ttl.split(" ")[0] + (" " + ttl.split(" ")[1] if len(ttl.split(" ")[1]) == 1 else ""), d["rio_hdr"], n, n))
            for i in range(n):
                rr, cc = divmod(i, 3)
                cx = x0 + w * (0.2, 0.5, 0.8)[cc]
                icon(pg, "rio", cx, top - 0.52 - rr * 0.44, 0.34, 0.22, "RIO-%d" % (i + 1), blk, label_h=0.12, lw_=0.33)
            io = d["io"]
            cap = "DI %d DO %d AI %d AO %d" % (io.get("NTSDDI1602XHK", 0), io.get("NTSDDO0802K", 0),
                                                  io.get("NTSACI0802XK", 0), io.get("NTSAMO0400K", 0))
            pg.text(x0 + 0.03, y0 + 0.03, w - 0.06, 0.26, cap + "\nGateway x%d" % io.get("gateway", 0), blk, size=6, valign=2)
        else:
            if kind == "master":
                m = d["master"]
                pg.text(x0 + 0.05, top - 0.48, w - 0.10, 0.44, d["master_title"] + "\n" + d["title"].split(" ")[0], blk,
                        size=7.5, bold=True, valign=0)
                seq = [("hsby", m["hsby"]), ("managed_switch", m["managed_switch"]), ("eth_switch", m["eth_switch"]),
                       ("fo_panel", m["fo_panel"])]
                links = ["ethernet", "ethernet", "fiber"]
            else:
                pg.text(x0 + 0.05, top - 0.48, w - 0.10, 0.44, "Old-Buildings\nList of buildings attached in Appendix", blk,
                        size=7.5, bold=True, valign=0)
                seq = [("old_panel", d["old_panel"]), ("asp", d["asp"]), ("eth_switch", d["eth_switch"]),
                       ("fo_panel", d["fo_panel"])]
                links = [None, "ethernet", "fiber"]
            cxs = [x0 + w * (2 * i + 1) / 8 for i in range(4)]
            for (k, q), cx in zip(seq, cxs):
                q = int(q)
                lab = ICONS[k][0] + (" x%d" % q if q > 1 else "")
                icon(pg, k, cx, top - 0.75, 0.8, 0.42, lab, blk, qty=q, label_h=0.3, lw_=0.9)
            ymid = top - 0.75 - 0.21
            for i, lk in enumerate(links):
                if lk:
                    pg.line([(cxs[i] + 0.4, ymid), (cxs[i + 1] - 0.4, ymid)], lk, blk)
    # trunks from ring down through column gaps
    for c, yend in trunk_end.items():
        tx = gx0 + c * gp - 0.07
        pg.line([ring_pt(tx, False), (tx, yend)], "fiber", frame)
    # ---- footer
    fx0, fx1, fy0, fy1 = 0.30, 16.235, 0.30, 1.40
    foot = pg.rect("block", fx0, fy0, fx1 - fx0, fy1 - fy0, frame, fill=None, lw=1.0)
    cells = [
        (0.30, 1.0333, 3.10, 0.3667, "End User:  TBC", 8, 0), (3.40, 1.0333, 3.10, 0.3667, "Contractor:  TBC", 8, 0),
        (0.30, 0.6667, 6.20, 0.3666, "Project:  " + title.lstrip("'"), 8, 0),
        (0.30, 0.30, 1.50, 0.3667, "AVANCEON", 12, 1),
        (1.80, 0.4833, 4.70, 0.1834, "Documentation Name:  Architecture", 7, 0),
        (1.80, 0.30, 1.00, 0.1833, "Prepared by:  TBC", 6, 0), (2.80, 0.30, 1.00, 0.1833, "Checked by:  TBC", 6, 0),
        (3.80, 0.30, 1.00, 0.1833, "Approved by:  TBC", 6, 0), (4.80, 0.30, 0.80, 0.1833, "Size:  A3", 6, 0),
        (5.60, 0.30, 0.90, 0.1833, "Rev/Sheet:  R0", 6, 0)]
    for x, y, w, h, t, sz, ha in cells:
        pg.rect("block", x, y, w, h, foot, fill=None, lw=0.5, text=t, size=sz, bold=(t == "AVANCEON"), halign=ha, valign=1)
    notes = ("Notes:\n1. Drawn from the BOQ sheet '3. BOQ' (KSU Utilities and Facilities Relocation Project).\n"
             "2. x N = BOQ total quantity for that item.   3. Connections between devices are assumed - not stated in the BOQ.\n"
             "4. Not drawn: software licences, services, cables, field instruments (BOQ section 30) and panel components."
             + "".join("\n5. " + w for w in WARNINGS))
    pg.rect("block", 6.50, 0.30, 4.70, 1.10, foot, fill=None, lw=0.5, text=notes, size=6, halign=0, valign=0)
    leg = pg.rect("block", 11.20, 0.30, fx1 - 11.20, 1.10, foot, fill=None, lw=0.5)
    pg.text(11.20, 1.12, fx1 - 11.20, 0.22, "Legend", leg, size=8, bold=True)
    for i, ck in enumerate(("ethernet", "fiber")):
        y = 0.85 - i * 0.30
        pg.line([(11.5, y), (12.9, y)], ck, leg)
        pg.text(13.05, y - 0.11, 2.9, 0.22, CABLES[ck][0], leg, size=7, halign=0)
    return pg


# ------------------------------------------------------------------ vsdx writer
def f(v):
    return repr(round(v, 6))


def shape_xml(s):
    x, y, w, h = s["x"], s["y"], s["w"], s["h"]
    c = ["<Cell N='PinX' V='%s'/>" % f(x + w / 2), "<Cell N='PinY' V='%s'/>" % f(y + h / 2),
         "<Cell N='Width' V='%s'/>" % f(w), "<Cell N='Height' V='%s'/>" % f(h),
         "<Cell N='LocPinX' V='%s' F='Width*0.5'/>" % f(w / 2), "<Cell N='LocPinY' V='%s' F='Height*0.5'/>" % f(h / 2)]
    line = s["line"]
    c += ["<Cell N='LinePattern' V='%d'/>" % (0 if line is None else s["pattern"] if s["kind"] != "line" else 1),
          "<Cell N='LineColor' V='%s'/>" % (line or "#000000"), "<Cell N='LineWeight' V='%s'/>" % f(s["lw"] / 72)]
    filled = s["fill"] is not None and s["kind"] != "line"
    c += ["<Cell N='FillPattern' V='%d'/>" % (1 if filled else 0), "<Cell N='FillForegnd' V='%s'/>" % (s["fill"] or "#FFFFFF")]
    c += ["<Cell N='%s' V='0.02'/>" % n for n in ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin")]
    c.append("<Cell N='VerticalAlign' V='%d'/>" % {0: 0, 1: 1, 2: 2}[s["valign"]])
    sec = ""
    if s["text"]:
        sec += ("<Section N='Character'><Row IX='0'><Cell N='Color' V='#000000'/><Cell N='Style' V='%d'/>"
                "<Cell N='Size' V='%s'/></Row></Section>" % (1 if s["bold"] else 0, f(s["size"] / 72)))
        sec += "<Section N='Paragraph'><Row IX='0'><Cell N='HorzAlign' V='%d'/></Row></Section>" % s["halign"]
    if s["key"]:
        k, _, q = s["key"].partition("|qty=")
        rows = "<Row N='BoqKey'><Cell N='Value' V='%s' U='STR'/></Row>" % escape(k, {"'": "&apos;"})
        if q:
            rows += "<Row N='BoqQty'><Cell N='Value' V='%s'/></Row>" % q
        sec += "<Section N='User'>%s</Section>" % rows
    g = "<Section N='Geometry' IX='0'><Cell N='NoFill' V='%d'/><Cell N='NoLine' V='%d'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>" % (0 if filled else 1, 1 if line is None else 0)
    if s["kind"] == "rect":
        rows = [("MoveTo", 0, 0, "", ""), ("LineTo", 1, 0, "Width*1", ""), ("LineTo", 1, 1, "Width*1", "Height*1"),
                ("LineTo", 0, 1, "", "Height*1"), ("LineTo", 0, 0, "", "")]
        for i, (t, ax, ay, fx, fy) in enumerate(rows, 1):
            g += "<Row T='%s' IX='%d'><Cell N='X' V='%s'%s/><Cell N='Y' V='%s'%s/></Row>" % (
                t, i, f(ax * w), " F='%s'" % fx if fx else "", f(ay * h), " F='%s'" % fy if fy else "")
    elif s["kind"] == "ellipse":
        g += ("<Row T='Ellipse' IX='1'><Cell N='X' V='%s' F='Width*0.5'/><Cell N='Y' V='%s' F='Height*0.5'/>"
              "<Cell N='A' V='%s' F='Width*1'/><Cell N='B' V='%s' F='Height*0.5'/>"
              "<Cell N='C' V='%s' F='Width*0.5'/><Cell N='D' V='%s' F='Height*1'/></Row>") % (
            f(w / 2), f(h / 2), f(w), f(h / 2), f(w / 2), f(h))
    else:
        for i, (px, py) in enumerate(s["pts"], 1):
            g += "<Row T='%s' IX='%d'><Cell N='X' V='%s'/><Cell N='Y' V='%s'/></Row>" % (
                "MoveTo" if i == 1 else "LineTo", i, f(px - x), f(py - y))
    g += "</Section>"
    txt = ""
    if s["text"]:
        txt = "<Text><pp IX='0'/><cp IX='0'/>%s</Text>" % escape(s["text"])
    return "<Shape ID='%d' Type='Shape' LineStyle='0' FillStyle='0' TextStyle='0'>%s%s%s%s</Shape>" % (
        s["id"], "".join(c), sec, g, txt)


def write_vsdx(pg, out):
    zin = zipfile.ZipFile(BASE_PATH)
    page = ("<?xml version='1.0' encoding='utf-8' ?>\n<PageContents xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
            "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' xml:space='preserve'><Shapes>"
            + "".join(shape_xml(s) for s in pg.shapes) + "</Shapes></PageContents>")
    ET.fromstring(page.encode("utf-8"))      # well-formedness
    empty_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/'
                  'package/2006/relationships"></Relationships>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
            'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>KSU Utilities and Facilities Relocation - Architecture</dc:title>'
            '</cp:coreProperties>')
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for i in zin.infolist():
            n = i.filename
            if n.startswith(("visio/media/", "visio/embeddings/")) or n == "docProps/thumbnail.emf":
                continue
            data = zin.read(n)
            if n == "visio/pages/page1.xml":
                data = page.encode("utf-8")
            elif n == "visio/pages/_rels/page1.xml.rels":
                data = empty_rels.encode()
            elif n == "docProps/core.xml":
                data = core.encode()
            elif n == "_rels/.rels":
                t = data.decode()
                data = re.sub(r"<Relationship [^>]*thumbnail[^>]*/>", "", t).encode()
            elif n == "visio/pages/pages.xml":
                t = data.decode()
                t = re.sub(r"(N='PageWidth' V=')[^']*", r"\g<1>%s" % PW, t)
                t = re.sub(r"(N='PageHeight' V=')[^']*", r"\g<1>%s" % PH, t)
                t = re.sub(r"ViewCenterX='[^']*'", "ViewCenterX='%s'" % (PW / 2), t)
                t = re.sub(r"ViewCenterY='[^']*'", "ViewCenterY='%s'" % (PH / 2), t)
                data = t.encode()
            elif n == "visio/windows.xml":
                t = data.decode()
                t = re.sub(r"ViewCenterX='[^']*'", "ViewCenterX='%s'" % (PW / 2), t)
                t = re.sub(r"ViewCenterY='[^']*'", "ViewCenterY='%s'" % (PH / 2), t)
                data = t.encode()
            zo.writestr(n, data)


if __name__ == "__main__":
    title, sections, items = boq.parse(BOQ_PATH)
    ctl, old, bld = gather(sections, items)
    pg = build(title, ctl, old, bld)
    out = OUT_DIR + r"\KSU_BMS_Architecture.vsdx"
    write_vsdx(pg, out)
    json.dump(pg.shapes, open(OUT_DIR + r"\model.json", "w"), default=str)
    print("wrote", out, len(pg.shapes), "shapes")
