"""Classification rule and quantity tests. Run:  python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import boq_rules as R
import quantity as Q

RULES_PATH = os.path.join(HERE, "..", "data", "boq_rules.json")


def line(desc, model="", make="", unit="No", section="", parents=()):
    return {"description": desc, "model": model, "make": make, "unit": unit, "section": section, "parents": list(parents), "qty": 1.0}


# (description, model, make, unit, section, expected bucket) - each taken from the real BOQs
EVIDENCE = [
    ("Engineering Services", "", "AVANCEON", "Job", "SCADA Development", "service"),
    ("Engineering Laptop", "Dell Latitude 5540", "Dell/Eq", "pcs", "Maintenance Laptop", "device"),
    ("FO patch panel & patch cords", "", "AVALON/Equiv", "pcs", "Servers", "device"),
    ("Ethernet Switch & cable", "C1000-Unmanaged", "Cisco", "pcs", "List of buildings", "device"),
    ("Cable,ControlLogix,Fiber Optic,1 m,For use with 1756-RM, 1756-RM2", "1756-RMC1", "Rockwell/Equiv.", "No.", "Common Controller", "cable"),
    ("Power Supply", "1756-PA72", "Rockwell", "No", "PLC System", "component"),
    ("Guardlogix 5580 Controller", "1756-L81ES", "Rockwell", "No", "PLC System", "device"),
    ("Studio 5000 Professional Edition (Logic Development)", "Rockwell", "9324M-RLDT31", "No", "Licenses", "software"),
    ("Name plates / Labels POOLE SIGNS & ENGRAVERS", "X4S-2006662", "Honeywell", "No", "Flame Detectors", "component"),
    ("Certificate of Conformity", "COCX1", "Honeywell", "No", "Documentation", "documentation"),
    ("Installation of Flame Detectors", "", "", "No", "Installation", "service"),
    ("6mm Steel Plate", "", "", "nos", "Supply of Poles", "material"),
    ("1 PAIR CU/MICA/XLPE/OS/LSZH/SWA/LSZH 1.5 mm2", "", "", "Meter", "Cables", "cable"),
    ("M20 Explosion Proof", "DCGXX-20-X M20", "Ortac", "No", "Cable Glands", "cable"),
    ("SPARES FOR SOLAR SYSTEM", "", "", "No", "", "spares"),
    ("Training", "Services", "Avanceon", "Days", "SERVICES", "service"),
    ("Capacitive Level Switch", "", "", "No", "Level Switch", "device"),
    ("SC SWITCH MODULE PROGRAM/FORCE/RESET", "FC-SSWM01", "", "No.", "Common Controller", "component"),
    ("Stratix 5200 6 Port Switch", "1783-CMS6P", "", "No", "Main PLC ESD", "device"),
    ("EXPERION HS PANEL BASE SOFWARE", "EP-PNBASE", "", "No.", "18 inch HMI", "software"),
    ("Antivirus", "", "Symantec", "No", "SCADA Hardware", "software"),
    ("FLEX 5000 Digital 32 Input 24 VDC", "5094-IB32", "Rockwell", "No.", "Simplex PCS IO Rack", "component"),
    ("Terminal Bases with 36 pin connections (DI+DO+AI)", "5069-RTB64-SCREW", "Rockwell", "No", "IO Modules", "component"),
    ("Control Panel and Marshalling Assembly (RIO-1)", "", "Hoffman/Eq", "pcs", "Field RIO panels (1-4)", "device"),
    ("Operating System (A separate PC with the following minimum configurations, along with Led monitor", "", "", "No", "Supply of Poles", "device"),
    ("Pavian 1200, stainless steel electronics box, IP66 (L600xH650xW300)", "", "", "No", "Sirens", "device"),
]


class RuleFileTests(unittest.TestCase):
    def test_no_control_characters_in_the_rules_file(self):
        with open(RULES_PATH, encoding="utf-8") as fh:
            raw = fh.read()
        bad = [c for c in raw if ord(c) < 32 and c not in "\n\r\t"]
        self.assertEqual(bad, [], "a single-backslash escape such as \\b became a control character")

    def test_every_pattern_compiles_and_every_rule_is_well_formed(self):
        rules = R.Rules()
        ids = [r[0] for r in rules.rules]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(rules.status, "provisional")
        self.assertEqual(rules.default, "device")

    def test_bad_rule_files_are_rejected(self):
        def load(obj):
            p = os.path.join(tempfile.mkdtemp(), "r.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(obj, fh)
            return R.Rules(p)
        base = {"buckets": ["device", "service"], "default": "device"}
        for rules in ([{"id": "a", "bucket": "nope", "description": "x"}], [{"id": "a", "bucket": "service"}],
                      [{"id": "a", "bucket": "service", "description": "x"}, {"id": "a", "bucket": "service", "description": "y"}]):
            with self.assertRaises(R.RulesError):
                load(dict(base, rules=rules))
        with self.assertRaises(R.RulesError):
            load({"buckets": ["device"], "default": "other", "rules": []})


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.r = R.Rules()

    def test_evidence_from_the_real_boqs(self):
        for desc, model, make, unit, section, want in EVIDENCE:
            got = self.r.classify(line(desc, model, make, unit, section))["bucket"]
            self.assertEqual(got, want, "%s -> %s (wanted %s)" % (desc[:50], got, want))

    def test_description_rules_look_at_the_headline_only(self):
        pc = "PC DELL OPTI 7020 TWR PLUS i7 14700/16GB/1TB-SSD/GT710 2GB-DDR3 (ZT-71302-20L) RW - 1YR + Microsoft Windows Professional OS 64 Bit, 3 year warranty, commissioning"
        self.assertEqual(self.r.classify(line(pc, "Dell", "PC DELL", "No", "Work Stations"))["bucket"], "device")
        spec = "LTE DEVICE 18 W PSU 2x Mobile antennas (swivel, SMA male) 2x Wi-Fi antennas 1x GNSS antenna (SMA male, 3 m cable) 1x Bluetooth antenna (1.5 m cable)"
        self.assertEqual(self.r.classify(line(spec, "", "", "No.", "Laptop"))["bucket"], "device")
        self.assertEqual(self.r.classify(line("Installation of Cables " + "x" * 200, "", "", "Mtr"))["bucket"], "service")

    def test_unmatched_lines_default_to_device_and_say_so(self):
        c = self.r.classify(line("Some unknown gadget", "ZX-1", "Acme"))
        self.assertEqual((c["bucket"], c["rule"], c["by_default"]), ("device", "default", True))
        c = self.r.classify(line("Training", "", "", "Days"))
        self.assertFalse(c["by_default"])

    def test_every_line_lands_in_exactly_one_bucket(self):
        lines = [dict(line(d, m, k, u, s), qty=2.0) for d, m, k, u, s, _ in EVIDENCE]
        out = self.r.classify_all(lines)
        a = R.account(out)
        self.assertEqual(a["lines"], len(lines))
        self.assertEqual(sum(v["lines"] for v in a["by_bucket"].values()), len(lines))
        self.assertEqual(sum(v["qty"] for v in a["by_bucket"].values()), 2.0 * len(lines))
        self.assertEqual(a["by_default"], sum(1 for o in out if o["by_default"]))


class QuantityTests(unittest.TestCase):
    def test_unit_kinds(self):
        for u, k in (("No", "count"), ("pcs", "count"), ("", "count"), ("Nos.", "count"), ("Lot", "lot"), ("Lump Sum", "lot"), ("Job", "lot"),
                     ("Meter", "length"), ("Mtr", "length"), ("metr", "length"), ("Man-days", "time"), ("Hours/ Lot", "time"), ("Days", "time"), ("kg", "other")):
            self.assertEqual(Q.unit_kind(u), k, u)

    def test_whole_numbers_and_fractions(self):
        self.assertEqual(Q.whole(4.0), (4, None))
        n, note = Q.whole(8.66667)
        self.assertEqual(n, 9)
        self.assertIn("rounded up", note)
        for bad in (0, -1, float("nan"), "3", True):
            with self.assertRaises(Q.QuantityError):
                Q.whole(bad)

    def test_instances_are_numbered_and_never_collapsed_silently(self):
        p = Q.plan(3, "No")
        self.assertEqual((p["suffixes"], p["shown"]), (["-01", "-02", "-03"], True))
        self.assertEqual(Q.plan(1, "pcs")["suffixes"], [""])
        self.assertEqual(Q.plan(100, "No", max_instances=200)["suffixes"][:2], ["-001", "-002"])
        with self.assertRaisesRegex(Q.QuantityError, "never done silently"):
            Q.plan(88, "No")

    def test_count_and_type_modes_are_explicit_collapses(self):
        self.assertEqual(Q.plan(88, "No", "count")["suffixes"], [" x88"])
        self.assertEqual(Q.plan(1, "No", "count")["suffixes"], [""])
        t = Q.plan(88, "No", "type")
        self.assertEqual((t["suffixes"], t["shown"]), ([""], False))
        self.assertTrue(any("not shown" in n for n in t["notes"]))

    def test_lengths_and_hours_are_not_items(self):
        for unit in ("Meter", "Man-days", "Hours"):
            with self.assertRaises(Q.QuantityError):
                Q.plan(5, unit)

    def test_notes_for_fractions_lots_and_odd_units(self):
        self.assertTrue(any("rounded up" in n for n in Q.plan(8.5, "No", "count")["notes"]))
        self.assertTrue(any("treated as 3 items" in n for n in Q.plan(3, "Lot")["notes"]))
        self.assertTrue(any("not recognised" in n for n in Q.plan(2, "kg")["notes"]))
        with self.assertRaises(Q.QuantityError):
            Q.plan(2, "No", "everything")

    def test_plan_feeds_the_drawing(self):
        from components import Components
        from draw import draw_component
        from vsdx_writer import Page
        pg = Page()
        comps = Components()
        for i, suffix in enumerate(Q.plan(3, "No")["suffixes"]):
            draw_component(pg, comps, "ps_pressure_switch", 1 + i * 1.6, 5, 1.5, 0.5, suffix=suffix)
        self.assertEqual([s["text"] for s in pg.shapes], ["PS - Pressure switch-01", "PS - Pressure switch-02", "PS - Pressure switch-03"])


if __name__ == "__main__":
    unittest.main()
