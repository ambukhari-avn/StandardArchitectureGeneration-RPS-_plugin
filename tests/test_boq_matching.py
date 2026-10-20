"""xlsx reader, BOQ line reader and matcher tests. Run:  python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))
import xlsx_reader
from components import Components
from xlsx_helper import make_xlsx
from matching import Matcher, norm_singular, part_tokens


class ReaderTests(unittest.TestCase):
    def test_sheets_and_cells(self):
        p = make_xlsx({"A": [["x", 2], [None, "y & z"]], "_hid": [["q"]]})
        self.assertEqual(xlsx_reader.sheets(p), [("A", "visible"), ("_hid", "hidden")])
        cells = xlsx_reader.read_sheet(p, "A")
        self.assertEqual(cells, {(1, 1): "x", (1, 2): 2.0, (2, 2): "y & z"})
        with self.assertRaises(KeyError):
            xlsx_reader.read_sheet(p, "nope")


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
