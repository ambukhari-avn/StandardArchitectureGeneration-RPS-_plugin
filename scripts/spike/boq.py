"""Stdlib-only reader for the KSU BMS BOQ ('3. BOQ' sheet) + classifier.
Every BOQ line is mapped to one bucket; unmapped lines raise (no silent drops)."""
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
TAG = "{%s}" % NS["m"]


def read_sheet(path, name):
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = next(s.get(RNS) for s in wb.find("m:sheets", NS) if s.get("name") == name)
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels if r.get("Id") == rid).lstrip("/")
    target = target if target.startswith("xl/") else "xl/" + target
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            sst.append("".join(t.text or "" for t in si.iter(TAG + "t")))
    cells = {}
    for c in ET.fromstring(z.read(target)).iter(TAG + "c"):
        v = c.find("m:v", NS)
        t = c.get("t")
        if t == "inlineStr":
            val = "".join(x.text or "" for x in c.iter(TAG + "t"))
        elif v is None or v.text is None:
            continue
        elif t == "s":
            val = sst[int(v.text)]
        elif t in ("str", "e", "b"):
            val = v.text
        else:
            val = float(v.text)
        m = re.match(r"([A-Z]+)(\d+)", c.get("r"))
        col = 0
        for ch in m.group(1):
            col = col * 26 + ord(ch) - 64
        cells[(int(m.group(2)), col)] = val
    return cells


def clean(s):
    return re.sub(r"\s+", " ", str(s).replace(" ", " ")).strip()


def parse(path):
    cells = read_sheet(path, "3. BOQ")
    get = lambda r, c: cells.get((r, c))
    maxr = max(r for r, _ in cells)
    title = clean(get(1, 1))
    zone = None            # control | old | new | other
    sect = None
    sub = None             # 'master' | 'rio' (new buildings)
    sections, items = [], []
    for r in range(3, maxr + 1):
        a, b, c, d, e, f = (get(r, i) for i in range(1, 7))
        if a is None and b is None:
            continue
        if isinstance(a, str) and not b:                 # zone marker in col A
            t = clean(a).lower()
            zone = "control" if t.startswith("control room") else "old" if t.startswith("old") \
                else "new" if t.startswith("new") else zone
            if zone == "control":
                sect = {"num": 0, "title": clean(a), "zone": zone, "items": [], "rio_hdr": None}
                sections.append(sect)
            continue
        is_header = isinstance(a, float) and a == int(a) and b and not c and f == 1
        if is_header:
            sect = {"num": int(a), "title": clean(b), "zone": zone, "items": [], "rio_hdr": None}
            if sect["num"] >= 30:
                sect["zone"] = "other"
            sections.append(sect)
            sub = None
            continue
        if a is None and b:                                # sub-group marker
            tb = clean(b)
            if tb.lower().startswith("master control panel"):
                sub = "master"
                sect["master_title"] = tb
            elif tb.lower().startswith("field rio"):
                sub = "rio"
                sect["rio_hdr"] = tb
            continue
        if isinstance(a, float) and sect is not None and b:
            it = {"row": r, "sr": a, "desc": clean(b), "model": clean(c or ""), "make": clean(d or ""),
                  "unit": clean(e or ""), "qty": f if isinstance(f, float) else 0.0,
                  "sect": sect, "sub": sub}
            sect["items"].append(it)
            items.append(it)
    return title, sections, items


SERVICE = re.compile(r"engineering|services|testing and commissioning|functional design|plc programming|scada development", re.I)


def classify(it):
    """-> (bucket, key). bucket in drawn|io|component|service|software|cable|instrument"""
    z, d, m = it["sect"]["zone"], it["desc"].lower(), it["model"]
    sn = it["sect"]["num"]
    if z == "other":
        return ("cable", "fo_cable") if sn == 31 else ("instrument", "instrument")
    if SERVICE.search(it["desc"]) and it["unit"].lower() in ("job", "man-days", ""):
        return "service", "service"
    if d.startswith(("aveva", "customer first")):
        return "software", "software"
    if z == "control":
        if d == "server rack": return "drawn", "server_rack"
        if d == "server": return "drawn", "server"
        if d == "historian server": return "drawn", "historian"
        if d.startswith("ethernet switch"): return "drawn", "eth_switch"
        if d.startswith("ethernet cable"): return "cable", "eth_cable"
        if d.startswith("fo patch panel"): return "drawn", "fo_panel"
        if d == "workstation": return "drawn", "eng_ws" if sn == 2 else "op_ws"
        if d.startswith('65"'): return "drawn", "screen65"
        if d.startswith("video-wall"): return "drawn", "videowall"
        if d == "controller": return "drawn", "vw_ctrl"
        if d == "gps ntp server": return "drawn", "gps_ntp"
        if d == "gps clock": return "drawn", "gps_clock"
        if d == "alarm": return "drawn", "printer_alarm"
        if d == "report": return "drawn", "printer_report"
        if d == "engineering laptop": return "drawn", "laptop"
    if z == "old":
        if d.startswith("control panel"): return "drawn", "old_panel"
        if d.startswith("spacelogic as-p-s"): return "drawn", "asp"
        if d.startswith("ethernet switch"): return "drawn", "eth_switch"
        if d.startswith("fo patch panel"): return "drawn", "fo_panel"
        if d.startswith(("ps-24v", "tb-ps", "terminal base", "as-p complete")): return "component", m
    if z == "new":
        if d.startswith("control panel and marshalling"):
            return ("drawn", "rio") if "(rio-" in d else ("component", "master_enclosure")
        if "m580 level 3 hsby" in d: return "drawn", "hsby"
        if d.startswith("network switch"): return "drawn", "managed_switch"
        if d.startswith("ethernet switch"): return "drawn", "eth_switch"
        if d.startswith("fo patch panel"): return "drawn", "fo_panel"
        if m in ("NTSDDI1602XHK", "NTSDDO0802K", "NTSACI0802XK", "NTSAMO0400K"): return "io", m
        if m == "PS-QS-1010-0757": return "io", "gateway"
        if m in ("NTSNEC1200HK", "NTSPFB1002HK", "NTSXTB02230H", "NTSXTB18200H", "NTSXTB12200H", "ABL8RPS24100",
                 "BMEXBP0400", "BMXCPS3020", "BMENOC0321", "ABL8RED24400"):
            return "component", m
    raise ValueError("unclassified BOQ line row %d: %r (zone %s)" % (it["row"], it["desc"], z))
