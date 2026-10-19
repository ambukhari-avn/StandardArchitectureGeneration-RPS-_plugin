"""Repair a hand-written (ChatGPT) .vsdx: keep its drawing, rebuild the package around it.
usage: python fix_vsdx.py <broken.vsdx> <fixed.vsdx>   (stdlib only)"""
import re, sys, zipfile
import xml.etree.ElementTree as ET

SKELETON = r"C:\Users\ambhukari\Downloads\dataset 1\arch-spike\out\KSU_BMS_Architecture.vsdx"   # Visio-derived, no drawing content
NS = "http://schemas.microsoft.com/office/visio/2012/main"
Q = lambda t: "{%s}%s" % (NS, t)
ET.register_namespace("", NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")


def hexcol(v):
    v = (v or "").strip().lstrip("#")
    return "#" + v.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", v) else None


def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def fix_page(xml, log):
    root = ET.fromstring(xml)
    ps = root.find(Q("PageSheet"))
    if ps is not None:
        root.remove(ps); log.append("removed <PageSheet> from page contents (belongs in pages.xml)")
    n_col = n_txt = n_para = n_order = 0
    for sh in root.iter(Q("Shape")):
        cells = {c.get("N"): c for c in sh.findall(Q("Cell"))}
        for n in ("LineColor", "FillForegnd"):
            c = cells.get(n)
            fixed = hexcol(c.get("V")) if c is not None else None
            if c is not None and fixed != c.get("V"):
                c.set("V", fixed or "#000000"); n_col += 1
        fill = cells["FillForegnd"].get("V") if "FillForegnd" in cells else "#FFFFFF"
        for n, v in (("LinePattern", "1"), ("VerticalAlign", "1")):
            if n not in cells:
                e = ET.Element(Q("Cell"), N=n, V=v)
                last = [c for c in sh if c.tag == Q("Cell")][-1]
                sh.insert(list(sh).index(last) + 1, e)
        sh.set("LineStyle", "0"); sh.set("FillStyle", "0"); sh.set("TextStyle", "0")
        for sec in sh.findall(Q("Section")):
            if sec.get("N") == "Character":
                for row in sec.findall(Q("Row")):
                    for c in list(row):
                        if c.get("N") == "Font":
                            row.remove(c)                       # index 0 needs a FaceNames table; use document default
                        if c.get("N") == "Color":
                            c.set("V", "#FFFFFF" if lum(fill) < 0.40 else "#000000"); n_txt += 1
            if sec.get("N") == "Paragraph":
                for row in sec.findall(Q("Row")):
                    for c in list(row):
                        if c.get("N") == "VertAlign":
                            row.remove(c); n_para += 1
        # Text must follow all Cells/Sections
        t = sh.find(Q("Text"))
        if t is not None:
            sh.remove(t)
            if (t.text or "").strip():
                t2 = ET.SubElement(sh, Q("Text"))
                ET.SubElement(t2, Q("pp"), IX="0"); ET.SubElement(t2, Q("cp"), IX="0")
                t2[-1].tail = t.text
                n_order += 1
            else:                                               # empty text: drop text and its formatting sections
                for sec in sh.findall(Q("Section")):
                    if sec.get("N") in ("Character", "Paragraph"):
                        sh.remove(sec)
    # a shape whose text is repeated verbatim by a later (higher z-order) shape shows only clipped fragments: drop the hidden copy
    shapes = list(root.iter(Q("Shape")))
    txt = lambda sh: "".join(sh.find(Q("Text")).itertext()).strip() if sh.find(Q("Text")) is not None else ""
    dup = 0
    for i, sh in enumerate(shapes):
        t = txt(sh)
        if t and any(txt(o) == t for o in shapes[i + 1:]):
            sh.remove(sh.find(Q("Text")))
            for sec in sh.findall(Q("Section")):
                if sec.get("N") in ("Character", "Paragraph"):
                    sh.remove(sec)
            dup += 1
    log.append("removed %d duplicated, partly hidden band labels (same text exists on a separate label shape)" % dup)
    log.append("fixed %d colour values (added '#'); set text colours by fill contrast (%d)" % (n_col, n_txt))
    log.append("removed invalid Paragraph/VertAlign (%d), moved <Text> after Sections (%d)" % (n_para, n_order))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main(src, dst):
    log = []
    zin = zipfile.ZipFile(src)
    page = fix_page(zin.read("visio/pages/page1.xml"), log)
    ps = zin.read("visio/pages/pages.xml").decode("utf-8")
    W = re.search(r'N="PageWidth" V="([\d.]+)"', ps).group(1)
    H = re.search(r'N="PageHeight" V="([\d.]+)"', ps).group(1)
    name = re.search(r'<Page [^>]*?\sName="([^"]*)"', ps).group(1)
    sk = zipfile.ZipFile(SKELETON)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for i in sk.infolist():
            n, d = i.filename, sk.read(i.filename)
            if n == "visio/pages/page1.xml":
                d = page
            elif n == "visio/pages/pages.xml":
                t = d.decode()
                t = re.sub(r"(N='PageWidth' V=')[^']*", r"\g<1>" + W, t)
                t = re.sub(r"(N='PageHeight' V=')[^']*", r"\g<1>" + H, t)
                t = t.replace("NameU='Page-1' Name='Page-1'", "NameU='%s' Name='%s' IsCustomName='1' IsCustomNameU='1'" % (name, name))
                d = t.encode()
            if n in ("visio/pages/pages.xml", "visio/windows.xml"):
                t = d.decode()
                t = re.sub(r"ViewCenterX='[^']*'", "ViewCenterX='%s'" % (float(W) / 2), t)
                t = re.sub(r"ViewCenterY='[^']*'", "ViewCenterY='%s'" % (float(H) / 2), t)
                d = t.encode()
            if n == "docProps/app.xml":
                d = d.decode().replace("<vt:lpstr>Page-1</vt:lpstr>", "<vt:lpstr>%s</vt:lpstr>" % name).encode()
            zo.writestr(n, d)
    log.insert(0, "dropped stray root part '_rels.rels'; rebuilt package on a Visio-derived skeleton (styles, theme, windows, content types)")
    log.append("page size kept as in the original: %s x %s in; page name %r" % (W, H, name))
    return log


if __name__ == "__main__":
    for l in main(sys.argv[1], sys.argv[2]): print("-", l)
