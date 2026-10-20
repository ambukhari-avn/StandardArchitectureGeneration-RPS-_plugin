"""BOQ parser tests on small synthetic workbooks. Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))
import boq_parser as P
import xlsx_reader
from xlsx_helper import make_xlsx

HDR = ["Sr.", "Description", "Model Number", "Make", "Unit", "Qty"]


def parse(rows, header=HDR, extra=None):
    p = make_xlsx({"S": [header] + rows})
    return P.parse_sheet(p, "S")


class HeaderTests(unittest.TestCase):
    def test_columns_found_in_any_order_with_header_variants(self):
        a = parse([[1.0, "Item", "M1", "Mk", "No", 3.0, 99.0]], HDR + ["Unit Price"])
        self.assertEqual((a["lines"][0]["description"], a["lines"][0]["model"], a["lines"][0]["make"], a["lines"][0]["qty"]), ("Item", "M1", "Mk", 3.0))
        b = parse([["x", 1.0, "Thing", "Mk", "M2", "No", 2.0]], ["Filter", "Sr.No", "Item Description", "Make", "Model No.", "Unit", "Quantity"])
        self.assertEqual((b["columns"]["sr"], b["lines"][0]["model"], b["lines"][0]["make"], b["lines"][0]["qty"]), (2, "M2", "Mk", 2.0))

    def test_price_columns_are_never_read(self):
        a = parse([[1.0, "Item", "M1", "Mk", "No", 3.0, 5370.0]], HDR + ["Unit Price"])
        self.assertEqual(a["unread_columns"], ["Unit Price"])
        self.assertNotIn(5370.0, a["lines"][0].values())

    def test_sheet_without_header_is_an_error(self):
        with self.assertRaises(P.BoqError):
            P.parse_sheet(make_xlsx({"S": [["a", "b"]]}), "S")

    def test_list_sheets_marks_hidden_and_skips_non_boq(self):
        p = make_xlsx({"BOQ": [HDR, [1.0, "x", "", "", "No", 1.0]], "_old": [HDR], "Notes": [["hello"]]})
        self.assertEqual([(s["name"], s["state"], s["header_row"]) for s in P.list_sheets(p)], [("BOQ", "visible", 1), ("_old", "hidden", 1)])

    def test_reading_can_stop_early(self):
        p = make_xlsx({"S": [HDR] + [[float(i), "d%d" % i, "", "", "No", 1.0] for i in range(1, 50)]})
        cells = xlsx_reader.read_sheet(p, "S", max_row=5)
        self.assertLessEqual(max(r for r, _ in cells), 6)


class RowTypeTests(unittest.TestCase):
    def test_every_row_is_accounted_for(self):
        r = parse([["Group"],
                   [1.0, "Item", "M", "Mk", "No", 2.0],
                   [2.0, "Zero", "M", "Mk", "No", 0.0],
                   [3.0, "Fraction", "M", "Mk", "No", 8.5],
                   [4.0, "No qty", "M", "Mk", "No", None],
                   [None, "Total", None, None, None, 12.0],
                   [5.0],
                   [None, None, None, None, None, 7.0]])
        self.assertEqual(r["content_rows"], r["accounted_rows"])
        self.assertEqual([l["description"] for l in r["lines"]], ["Item", "Fraction"])
        self.assertEqual([l["description"] for l in r["zero_qty"]], ["Zero"])
        self.assertEqual([l["description"] for l in r["fractional"]], ["Fraction"])
        self.assertEqual([x["description"] for x in r["no_qty"]], ["No qty"])
        self.assertEqual(sorted(x["why"] for x in r["ignored"]), ["row without a description", "row without a description", "total row"])
        self.assertEqual([o["text"] for o in r["outline"]], ["Group"])

    def test_numeric_strings_count_and_negative_quantity_is_an_error(self):
        self.assertEqual(parse([[1.0, "Item", "M", "Mk", "No", "5"]])["lines"][0]["qty"], 5.0)
        with self.assertRaises(P.BoqError):
            parse([[1.0, "Item", "M", "Mk", "No", -2.0]])

    def test_a_numbered_group_row_with_quantity_is_a_heading_but_a_fractional_number_is_an_item(self):
        r = parse([[1.0, "Servers", None, None, None, 1.0], [1.01, "Server", "R760", "Dell", "pcs", 4.0], [1.5, "Design Services", None, None, None, 1.0]])
        self.assertEqual([o["text"] for o in r["outline"]], ["Servers"])
        self.assertEqual([l["description"] for l in r["lines"]], ["Server", "Design Services"])

    def test_filter_column_text_is_not_a_heading(self):
        r = P.parse_sheet(make_xlsx({"S": [["Filter", "Sr.", "Description", "Make", "Unit", "Qty"],
                                           ["MDCPF", "Flame Detectors"], ["MDCPF", 1.0, "Kit", "Hw", "No", 19.0], ["MDCPF", None, None, None, None, None]]}), "S")
        self.assertEqual(r["lines"][0]["section"], "Flame Detectors")
        self.assertEqual([o["text"] for o in r["outline"]], ["Flame Detectors"])


class HeadingContextTests(unittest.TestCase):
    def test_ksu_style_zones_buildings_and_subsections(self):
        r = parse([["CONTROL ROOM"],
                   [1.0, "Servers", None, None, None, 1.0],
                   ["1.01", "Server", "R760", "Dell", "pcs", 4.0],
                   [2.0, "Workstations", None, None, None, 1.0],
                   ["2.01", "Workstation", "P7960", "Dell", "pcs", 2.0],
                   ["NEW BUILDINGS"],
                   [11.0, "K-20A Directorate", None, None, None, 1.0],
                   [None, "Master Control Panel (North)", None, None, None, None],
                   ["11.01", "HSBY kit", "BMEH", "Schneider", "pcs", 1.0],
                   [None, "Field RIO panels (1-2)", None, None, None, 1.0],
                   ["11.02", "RIO-1", None, "Hoffman", "pcs", 1.0],
                   [12.0, "K23A Warehouse", None, None, None, 1.0],
                   [None, "Field RIO panels (1)", None, None, None, 1.0],
                   ["12.01", "RIO-1", None, "Hoffman", "pcs", 1.0]])
        by = {l["description"]: (l["section"], l["parents"]) for l in r["lines"]}
        self.assertEqual(by["Server"], ("Servers", ["CONTROL ROOM"]))
        self.assertEqual(by["Workstation"], ("Workstations", ["CONTROL ROOM"]))
        self.assertEqual(by["HSBY kit"], ("Master Control Panel (North)", ["NEW BUILDINGS", "K-20A Directorate"]))
        self.assertEqual([l["parents"] for l in r["lines"] if l["description"] == "RIO-1"],
                         [["NEW BUILDINGS", "K-20A Directorate"], ["NEW BUILDINGS", "K23A Warehouse"]])   # a new building replaces the old, keeps its zone

    def test_murtiba_style_sites_and_blocks(self):
        r = parse([["SCADA"], ["Laptop"], [1.0, "Laptop 18 inch", None, None, "No.", 1.0],
                   ["Programming License"], [None, "FT View Studio", None, "Rockwell", "No", 1.0],
                   ["MIPM-RTU-101"], ["Common Controller"], [1.0, "Chassis", "1756-A4", "Rockwell", "No.", 2.0],
                   ["Simplex IO Rack"], [2.0, "Module", "5094-IB32", "Rockwell", "No.", 5.0],
                   [None], ["MIPM-RTU-201"], ["Common Controller"], [1.0, "Chassis", "1756-A4", "Rockwell", "No.", 2.0]])
        got = [(l["description"], l["section"], l["parents"]) for l in r["lines"]]
        self.assertEqual(got, [("Laptop 18 inch", "Laptop", ["SCADA"]), ("FT View Studio", "Programming License", ["SCADA"]),
                               ("Chassis", "Common Controller", ["MIPM-RTU-101"]), ("Module", "Simplex IO Rack", ["MIPM-RTU-101"]),
                               ("Chassis", "Common Controller", ["MIPM-RTU-201"])])


if __name__ == "__main__":
    unittest.main()
