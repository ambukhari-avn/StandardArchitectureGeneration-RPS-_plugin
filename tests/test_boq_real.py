"""Checks on the client's real BOQs. Skipped unless the files are available:
    set ARCH_BOQ_DIR=<folder with the Kemari, Korangi, FADI and Murtiba workbooks>
    set ARCH_KSU_BOQ=<path of BMS-SF02 - 201125 1.xlsx>
Numbers are regression values recorded when the parser was written."""
import glob
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import boq_parser as P
import boq_rules as R

DIR = os.environ.get("ARCH_BOQ_DIR")
KSU = os.environ.get("ARCH_KSU_BOQ")


def find(pattern):
    hits = glob.glob(os.path.join(DIR, pattern)) if DIR else []
    return hits[0] if hits else None


@unittest.skipUnless(DIR and os.path.isdir(DIR), "set ARCH_BOQ_DIR to the folder with the client's BOQ workbooks")
class RealBoqTests(unittest.TestCase):
    CASES = [("*Kemari*.xlsx", "BOQ Foreign", 31, 12), ("*Kemari*.xlsx", "PLC F&G", 21, 5), ("*Kemari*.xlsx", "Work Stations", 5, 2),
             ("*Korangi*.xlsx", "BOQ Foreign", 39, 17), ("*Korangi*.xlsx", "PLC F&G", 22, 5),
             ("*FADI*.xlsx", "BOQ", 31, 6),
             ("*AROOBA BOQ*.xlsx", "BOQ Rockwell SIL2", 500, 131), ("*AROOBA BOQ*.xlsx", "BOQ HONEYWELL SIL2", 519, 36),
             ("*AROOBA BOQ*.xlsx", "BOQ HONEYWELL SIL3", 680, 49)]

    def test_line_and_heading_counts_and_nothing_dropped(self):
        for pattern, sheet, lines, headings in self.CASES:
            path = find(pattern)
            self.assertTrue(path, pattern)
            r = P.parse_sheet(path, sheet)
            self.assertEqual((len(r["lines"]), len(r["outline"])), (lines, headings), "%s / %s" % (pattern, sheet))
            self.assertEqual(r["content_rows"], r["accounted_rows"], "%s / %s" % (pattern, sheet))

    def test_murtiba_has_fourteen_sites_and_fractional_quantities(self):
        r = P.parse_sheet(find("*AROOBA BOQ*.xlsx"), "BOQ Rockwell SIL2")
        sites = {p for l in r["lines"] for p in l["parents"] if "RTU" in p}
        self.assertEqual(len(sites), 14)
        self.assertEqual(len(r["fractional"]), 18)

    def test_kemari_sections_and_prices_not_read(self):
        r = P.parse_sheet(find("*Kemari*.xlsx"), "BOQ Foreign")
        self.assertIn("Flame Detectors", {l["section"] for l in r["lines"]})
        self.assertNotIn("MDCPF", {l["section"] for l in r["lines"]})
        self.assertIn("Unit LP (USD)", r["unread_columns"])

    def test_classification_of_a_real_sheet(self):
        r = P.parse_sheet(find("*Korangi*.xlsx"), "BOQ Foreign")
        a = R.account(R.Rules().classify_all(r["lines"]))
        self.assertEqual(a["lines"], 39)
        self.assertEqual(a["by_bucket"]["device"]["lines"], 10)
        self.assertEqual(a["by_bucket"]["component"]["lines"], 16)


@unittest.skipUnless(KSU and os.path.exists(KSU), "set ARCH_KSU_BOQ to the KSU BMS workbook")
class RealKsuTests(unittest.TestCase):
    def test_ksu_structure(self):
        r = P.parse_sheet(KSU, "3. BOQ")
        self.assertEqual((len(r["lines"]), len(r["zero_qty"]), len(r["outline"])), (485, 12, 63))
        self.assertEqual(r["content_rows"], r["accounted_rows"])
        k23a = next(l for l in r["lines"] if "RIO-1" in l["description"] and "K23A" in " ".join(l["parents"]))
        self.assertEqual(k23a["parents"], ["New Buildings", "K23A Central Warehouse"])


if __name__ == "__main__":
    unittest.main()
