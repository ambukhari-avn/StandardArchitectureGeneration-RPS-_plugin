"""xlsx reader, BOQ line reader and matcher tests. Run:  python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import boq_lines
import xlsx_reader
from components import Components
from matching import Matcher, norm_singular, part_tokens


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


class ReaderTests(unittest.TestCase):
    def test_sheets_and_cells(self):
        p = make_xlsx({"A": [["x", 2], [None, "y & z"]], "_hid": [["q"]]})
        self.assertEqual(xlsx_reader.sheets(p), [("A", "visible"), ("_hid", "hidden")])
        cells = xlsx_reader.read_sheet(p, "A")
        self.assertEqual(cells, {(1, 1): "x", (1, 2): 2.0, (2, 2): "y & z"})
        with self.assertRaises(KeyError):
            xlsx_reader.read_sheet(p, "nope")


class BoqLineTests(unittest.TestCase):
    def setUp(self):
        self.p = make_xlsx({
            "Foreign": [["Filter", "Sr.", "Description", "Model Number", "Make", "Unit", "Qty", "Unit Price"],
                        ["X", "Flame Detectors"],
                        ["X", 1, "FS24X kit", "FS24XP", "Honeywell", "No", 19, 5370],
                        ["X", 2, "Spare", "SP-1", "Honeywell", "No", 0, 10],
                        ["X", "Sounder"],
                        ["X", 1, "Indoor Sounder", "GYJ", "Crown", "No", 1, 50]],
            "PLC": [[None], ["Sr.No", "Description", "Make", "Model Number", "Unit", "Qty"],
                    ["PLC System"],
                    [1, "Power Supply", "Rockwell", "1756-PA72", "No", 2]],
        })

    def test_columns_found_by_header_in_any_order(self):
        a = boq_lines.read_lines(self.p, "Foreign")
        self.assertEqual([(l["description"], l["model"], l["make"], l["qty"]) for l in a],
                         [("FS24X kit", "FS24XP", "Honeywell", 19.0), ("Indoor Sounder", "GYJ", "Crown", 1.0)])
        b = boq_lines.read_lines(self.p, "PLC")
        self.assertEqual((b[0]["description"], b[0]["make"], b[0]["model"], b[0]["qty"]), ("Power Supply", "Rockwell", "1756-PA72", 2.0))

    def test_headings_become_sections_and_zero_qty_is_skipped(self):
        a = boq_lines.read_lines(self.p, "Foreign")
        self.assertEqual([l["section"] for l in a], ["Flame Detectors", "Sounder"])
        self.assertNotIn("Spare", [l["description"] for l in a])

    def test_price_columns_are_not_read(self):
        a = boq_lines.read_lines(self.p, "Foreign")
        self.assertTrue(all(set(l) == {"sheet", "row", "section", "description", "model", "make", "unit", "qty"} for l in a))
        self.assertNotIn(5370.0, [v for l in a for v in l.values()])

    def test_sheet_without_header_is_an_error(self):
        with self.assertRaises(ValueError):
            boq_lines.read_lines(make_xlsx({"S": [["a", "b"]]}), "S")


def comps(items):
    rows = []
    for i, (cid, title, brand, part, picture) in enumerate(items, 2):
        rows.append({"id": cid, "layer": "L", "title": title, "label": title, "brand": brand, "part_number": part, "confidence": None,
                     "image_file_name": None, "picture": picture, "duplicate_of": None, "source_row": i})
    p = os.path.join(tempfile.mkdtemp(), "components.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"source": {}, "components": rows}, fh)
    return Components(p)


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.c = comps([("hmi_a", "HMI panel", "Siemens", "6AV2124-0MC01-0AX0 (TP1200 Comfort)", None),
                        ("hmi_b", "HMI panel", "Schneider", "HMIST6400 (Magelis ST6)", None),
                        ("flame", "Flame detector", None, "Box Representation only", None),
                        ("lvl", "Level switch (vibrating fork)", None, "Box Representation only", None),
                        ("m580", "Hot standby PLC pair", "Schneider", "BMEH584040 (Modicon M580)", None)])
        self.m = Matcher(self.c, aliases_path=None)

    def test_part_tokens(self):
        self.assertEqual(part_tokens("6AV2124-0MC01-0AX0 (TP1200 Comfort)"), {"6av21240mc010ax0", "tp1200"})   # 6+ characters, letters and digits
        self.assertEqual(part_tokens("Box Representation only"), set())
        self.assertEqual(part_tokens("BMEH584040 / BMEH582040K"), {"bmeh584040", "bmeh582040k"})
        self.assertEqual(part_tokens("M580 kit 12345678"), set())                                       # M580 is too short; digits alone do not count

    def test_exact_part_number_matches(self):
        r = self.m.match("some wording", "BMEH584040", "Schneider")
        self.assertEqual((r.status, r.ids, r.how), ("matched", ["m580"], "part number"))

    def test_near_part_number_does_not_match(self):
        self.assertEqual(self.m.match("M580 kit", "BMEH582040K", "Schneider").status, "unmatched")
        self.assertEqual(self.m.match("M580 kit", "", "Schneider").status, "unmatched")           # a family name alone is not a match

    def test_exact_title_matches_and_make_breaks_ties(self):
        self.assertEqual(self.m.match("Flame detector").ids, ["flame"])
        r = self.m.match("HMI panel")
        self.assertEqual((r.status, r.ids), ("ambiguous", ["hmi_a", "hmi_b"]))
        r = self.m.match("HMI panel", "", "Schneider Electric")
        self.assertEqual((r.status, r.ids, r.how), ("matched", ["hmi_b"], "title + make"))

    def test_brackets_are_part_of_the_title(self):
        r = self.m.match("Capacitive Level Switch")
        self.assertEqual(r.status, "unmatched")
        self.assertEqual(self.m.match("Level switch").status, "unmatched")               # not the vibrating-fork entry
        self.assertEqual(self.m.match("Level switch (vibrating fork)").ids, ["lvl"])

    def test_headings_fold_plurals_only(self):
        self.assertEqual(norm_singular("Flame Detectors"), norm_singular("Flame detector"))
        self.assertEqual(self.m.match_heading("Flame Detectors").ids, ["flame"])
        self.assertEqual(self.m.match_heading("Gas Detectors").status, "unmatched")
        self.assertEqual(self.m.match_heading("HMI").status, "unmatched")

    def test_suggestions_are_given_but_never_used(self):
        r = self.m.match("Level switch capacitive")
        self.assertEqual(r.status, "unmatched")
        self.assertIn("lvl", [i for i, _ in r.suggestions])

    def test_alias_file_is_honoured_and_validated(self):
        p = os.path.join(tempfile.mkdtemp(), "a.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"aliases": [{"text": "Capacitive Level Switch", "component": "lvl"}]}, fh)
        self.assertEqual(Matcher(self.c, p).match("capacitive  level switch").ids, ["lvl"])
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"aliases": [{"text": "x", "component": "nope"}]}, fh)
        with self.assertRaises(ValueError):
            Matcher(self.c, p)

    def test_real_dataset_flame_detectors_heading(self):
        m = Matcher(Components(), aliases_path=None)
        self.assertEqual(m.match_heading("Flame Detectors").ids, ["flame_detector"])


if __name__ == "__main__":
    unittest.main()
