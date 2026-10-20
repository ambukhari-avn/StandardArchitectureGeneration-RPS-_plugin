"""Builds tiny .xlsx files for tests (no client data needed)."""
import os
import tempfile
import zipfile
from xml.sax.saxutils import escape


def make_xlsx(sheets):
    """sheets: {name: [[cell, ...], ...]}; cells are str, float/int or None. Returns a path."""
    p = os.path.join(tempfile.mkdtemp(), "t.xlsx")
    letters = "ABCDEFGHIJ"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        names = list(sheets)
        z.writestr("xl/workbook.xml", "<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' "
                   "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'><sheets>%s</sheets></workbook>" %
                   "".join("<sheet name='%s' sheetId='%d' r:id='rId%d'%s/>" % (escape(n), i + 1, i + 1, " state='hidden'" if n.startswith("_") else "")
                           for i, n in enumerate(names)))
        z.writestr("xl/_rels/workbook.xml.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>%s</Relationships>" %
                   "".join("<Relationship Id='rId%d' Type='x' Target='worksheets/sheet%d.xml'/>" % (i + 1, i + 1) for i in range(len(names))))
        for i, n in enumerate(names):
            rows = ""
            for r, row in enumerate(sheets[n], 1):
                cs = ""
                for c, v in enumerate(row):
                    if v is None:
                        continue
                    ref = "%s%d" % (letters[c], r)
                    cs += ("<c r='%s'><v>%s</v></c>" % (ref, v)) if isinstance(v, (int, float)) else \
                          ("<c r='%s' t='inlineStr'><is><t>%s</t></is></c>" % (ref, escape(v)))
                rows += "<row r='%d'>%s</row>" % (r, cs)
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), "<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
                       "<sheetData>%s</sheetData></worksheet>" % rows)
    return p
