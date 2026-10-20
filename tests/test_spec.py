"""Spec validator tests on a small synthetic BOQ. Run:  python -m unittest discover -s tests"""
import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import jsonschema_lite
import spec as S
from components import Components
from cables import Cables
from purdue import PurdueMap
from xlsx_helper import make_xlsx

HDR = ["Sr.", "Description", "Model Number", "Make", "Unit", "Qty"]
BOQ_ROWS = [HDR,
            ["Flame Detectors"],                                               # row 2
            [1.0, "FS24X PLUS kit", "FS24XP-SMGXX", "Honeywell", "No", 19.0],   # row 3  device (default)
            [2.0, "Name plates / Labels", "X4S", "Honeywell", "No", 19.0],      # row 4  component
            ["Sounder"],                                                       # row 5
            [1.0, "Indoor Type Sounder", "GYJ", "Crown", "No", 1.0],            # row 6  device
            [2.0, "Outdoor Type Sounder", "D1x", "E2S", "No", 4.0],             # row 7  device
            ["Work Stations"],                                                 # row 8
            [1.0, "PC DELL OPTI", "Dell", "PC", "No", 2.0],                     # row 9  device
            [2.0, "LED DELL 32", "Dell", "Dell", "No", 2.0],                    # row 10 device
            [1.0, "Industrial firewall", "6GK5615-0AA00-2AA2", "Siemens", "No", 1.0],   # row 11 device
            [1.0, "Guardlogix 5580 Controller", "1756-L81ES", "Rockwell", "No", 2.0],   # row 12 device
            [1.0, "Virtual server host (VM)", "", "Dell", "No", 1.0],           # row 13 device, says VM
            [1.0, "Engineering Services", "", "Avanceon", "Job", 1.0]]          # row 14 service
PROMPT = "F&G system with a DMZ. Show the SIEM in the DMZ. SCS WEB SERVERS run on the VM."


def boq_path():
    return make_xlsx({"BOQ": BOQ_ROWS})


def good_spec():
    return {
        "spec_version": 1, "prompt": PROMPT,
        "project": {"end_user": "SEWA", "contractor": "Avanceon", "project": "Test", "prepared_by": "A", "checked_by": "B", "approved_by": "C"},
        "options": {"quantity_mode": "instances", "dmz": False},
        "sources": [{"file": "t.xlsx", "sheets": ["BOQ"]}],
        "groups": [
            {"id": "ops", "title": "Operator layer", "level": "2", "devices": [
                {"id": "ws", "basis": "boq", "label": "Work Stations", "qty": 2, "boq": [{"sheet": "BOQ", "row": 9}], "parts": [{"sheet": "BOQ", "row": 10}]},
                {"id": "fw", "basis": "boq", "component": "industrial_firewall", "qty": 1, "boq": [{"sheet": "BOQ", "row": 11}]},
                {"id": "vmhost", "basis": "boq", "label": "Virtual server host (VM)", "qty": 1, "boq": [{"sheet": "BOQ", "row": 13}],
                 "vm": {"note": 1, "contents": ["SCS WEB SERVERS"]}}]},
            {"id": "ctl", "title": "Controllers", "level": "1", "devices": [
                {"id": "plc", "basis": "boq", "label": "Guardlogix 5580 Controller", "qty": 2, "boq": [{"sheet": "BOQ", "row": 12}]}]},
            {"id": "field", "title": "Field devices", "level": "0", "devices": [
                {"id": "flame", "basis": "boq", "component": "flame_detector", "qty": 19, "quantity_mode": "type", "boq": [{"sheet": "BOQ", "row": 3}], "parts": [{"sheet": "BOQ", "row": 4}]},
                {"id": "sounder", "basis": "boq", "label": "Sounder", "qty": 5, "boq": [{"sheet": "BOQ", "row": 6}, {"sheet": "BOQ", "row": 7}]}]}],
        "connections": [
            {"from": "ws", "to": "fw", "cable": "ethernet", "basis": "assumed"},
            {"from": "fw", "to": "plc", "cable": "ethernet", "basis": "assumed"},
            {"from": "plc", "to": "flame", "cable": "hardwired", "basis": "assumed"},
            {"from": "plc", "to": "sounder", "cable": "hardwired", "basis": "assumed"}],
        "rings": [], "omitted": [], "notes": [], "answers": {"redundancy": "none"}}


class SpecTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comps, cls.purdue, cls.cables = Components(), PurdueMap(), Cables()
        cls.path = boq_path()

    def run_spec(self, spec):
        return S.validate(spec, {"t.xlsx": self.path}, self.comps, self.purdue, self.cables)

    def codes(self, spec, which="errors"):
        return sorted({e["code"] for e in getattr(self.run_spec(spec), which)})

    def mutated(self, fn):
        s = copy.deepcopy(good_spec())
        fn(s)
        return s


class GoodSpecTests(SpecTestCase):
    def test_a_correct_spec_is_valid_and_carries_the_notes(self):
        r = self.run_spec(good_spec())
        self.assertTrue(r.ok, r.text())
        joined = " ".join(r.notes)
        self.assertIn("Work Stations", joined)                      # boxes drawn with BOQ wording
        self.assertIn("4 connection(s) are assumed", joined)
        self.assertIn("Detector", joined)                           # provisional Purdue layer used
        self.assertEqual(r.stats["devices"], 6)

    def test_schema_file_accepts_the_good_spec(self):
        self.assertEqual(jsonschema_lite.check(good_spec(), S.load_json(S.SCHEMA_PATH)), [])

    def test_render_mode(self):
        spec = good_spec()
        srules = S.load_json(S.RULES_PATH)
        groups = {g["id"]: g for g in spec["groups"]}
        dev = lambda gid, did: next(d for d in groups[gid]["devices"] if d["id"] == did)
        rm = lambda gid, did: S.render_mode(dev(gid, did), groups[gid], self.comps, self.purdue, srules)
        self.assertEqual(rm("ops", "ws"), "box")                    # no dataset component
        self.assertEqual(rm("ops", "fw"), "box")                    # component has no picture
        self.assertEqual(rm("field", "flame"), "box")               # level 0 is always a box
        picture = {"id": "x", "basis": "boq", "component": "hot_standby_plc_pair", "qty": 1}
        self.assertEqual(S.render_mode(picture, {"id": "c", "level": "1"}, self.comps, self.purdue, srules), "picture")
        self.assertEqual(S.render_mode(dict(picture, third_party=True), {"id": "c", "level": "1"}, self.comps, self.purdue, srules), "box")
        self.assertEqual(S.render_mode(picture, {"id": "d", "level": "3.5"}, self.comps, self.purdue, srules), "box")
        estop = {"id": "e", "basis": "prompt", "component": "emergency_stop_push_button", "qty": 1}
        self.assertEqual(S.render_mode(estop, {"id": "f", "level": "0"}, self.comps, self.purdue, srules), "box")   # has a picture, still a box (D23)


class StructureAndProjectTests(SpecTestCase):
    def test_structure_errors_stop_everything_else(self):
        self.assertEqual(self.codes(self.mutated(lambda s: s.pop("groups"))), ["S001"])
        self.assertEqual(self.codes(self.mutated(lambda s: s["options"].update(quantity_mode="all"))), ["S001"])
        self.assertEqual(self.codes(self.mutated(lambda s: s["groups"][0]["devices"][0].update(colour="red"))), ["S001"])

    def test_missing_footer_field(self):
        self.assertEqual(self.codes(self.mutated(lambda s: s["project"].pop("contractor"))), ["P001"])
        self.assertEqual(self.codes(self.mutated(lambda s: (s["project"].pop("contractor"), s["options"].update(allow_tbc=True)))), [])

    def test_group_errors(self):
        self.assertIn("G001", self.codes(self.mutated(lambda s: s["groups"][1].update(id="ops"))))
        self.assertIn("G002", self.codes(self.mutated(lambda s: s["groups"][1].update(level="9"))))
        self.assertIn("G003", self.codes(self.mutated(lambda s: s["groups"][1].update(level="3.5"))))


class DeviceTests(SpecTestCase):
    def dev(self, s, gid="field", did="sounder"):
        return next(d for g in s["groups"] if g["id"] == gid for d in g["devices"] if d["id"] == did)

    def test_ids_components_and_labels(self):
        self.assertIn("D001", self.codes(self.mutated(lambda s: self.dev(s, "ctl", "plc").update(id="ws"))))
        self.assertIn("D002", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(component="not_in_dataset"))))
        self.assertIn("D003", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(label="Firewall"))))
        self.assertIn("D004", self.codes(self.mutated(lambda s: self.dev(s).pop("label"))))
        self.assertIn("D005", self.codes(self.mutated(lambda s: self.dev(s).update(label="Siren"))))

    def test_a_component_needs_an_exact_match_of_the_cited_text(self):
        # the firewall row matches by part number; a made-up choice of component does not
        self.assertIn("D018", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(component="gas_detector"))))
        self.assertIn("D018", self.codes(self.mutated(lambda s: (self.dev(s).pop("label"), self.dev(s).update(component="ups")))))

    def test_quantities_must_equal_the_boq(self):
        self.assertIn("D006", self.codes(self.mutated(lambda s: self.dev(s).update(qty=6))))
        self.assertIn("D006", self.codes(self.mutated(lambda s: self.dev(s, "field", "flame").update(qty=20))))

    def test_cited_rows(self):
        self.assertIn("D007", self.codes(self.mutated(lambda s: self.dev(s).update(boq=[{"sheet": "BOQ", "row": 99}]))))
        self.assertIn("D007", self.codes(self.mutated(lambda s: self.dev(s).update(boq=[{"sheet": "Nope", "row": 6}]))))
        self.assertIn("D008", self.codes(self.mutated(lambda s: self.dev(s, "ctl", "plc").update(boq=[{"sheet": "BOQ", "row": 14}], qty=1))))
        r = self.run_spec(self.mutated(lambda s: self.dev(s, "ctl", "plc").update(boq=[{"sheet": "BOQ", "row": 14}], qty=1, boq_override="needed for the demo")))
        self.assertNotIn("D008", {e["code"] for e in r.errors})
        self.assertTrue(any("classed as service" in n for n in r.notes))

    def test_basis_rules(self):
        self.assertIn("D015", self.codes(self.mutated(lambda s: self.dev(s).update(boq=[]))))
        self.assertIn("D016", self.codes(self.mutated(lambda s: self.dev(s).update(quote="SIEM in the DMZ"))))
        prompt_dev = {"id": "siem", "basis": "prompt", "label": "SIEM", "qty": 1, "quote": "Show the SIEM in the DMZ"}
        def add_dmz(s):
            s["options"]["dmz"] = True
            s["groups"].append({"id": "dmz", "title": "DMZ", "level": "3.5", "devices": [copy.deepcopy(prompt_dev)]})
        self.assertEqual(self.codes(self.mutated(add_dmz)), [])
        for bad in ({"quote": "Show the WAF"}, {"quote": None}, {"label": "WAF"}):
            def mutate(s, bad=bad):
                add_dmz(s)
                d = s["groups"][-1]["devices"][0]
                d.update(bad)
                if d.get("quote") is None:
                    d.pop("quote")
            self.assertTrue({"D017", "D005"} & set(self.codes(self.mutated(mutate))), bad)

    def test_dmz_and_third_party_items_are_boxes(self):
        def mutate(s):
            s["options"]["dmz"] = True
            s["groups"].append({"id": "dmz", "title": "DMZ", "level": "3.5", "devices": [
                {"id": "dfw", "basis": "boq", "component": "industrial_firewall", "qty": 1, "boq": [{"sheet": "BOQ", "row": 11}]}]})
            s["groups"][0]["devices"].pop(1)
        self.assertIn("D014", self.codes(self.mutated(mutate)))
        self.assertIn("D014", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(third_party=True))))

    def test_quantity_plan_errors(self):
        self.assertIn("D009", self.codes(self.mutated(lambda s: (self.dev(s).update(quantity_mode="instances"), s["options"].update(max_instances=3)))))
        self.assertIn("D009", self.codes(self.mutated(lambda s: self.dev(s).update(unit="Meter"))))

    def test_level_of_a_dataset_component_must_match_its_group(self):
        def mutate(s):
            fw = s["groups"][0]["devices"].pop(1)
            s["groups"][2]["devices"].append(fw)             # a level-2 firewall placed among level-0 field devices
        self.assertIn("D010", self.codes(self.mutated(mutate)))

    def test_vm_must_be_stated_and_its_contents_found(self):
        self.assertIn("D011", self.codes(self.mutated(lambda s: self.dev(s, "ctl", "plc").update(vm={"note": 1, "contents": ["SCS WEB SERVERS"]}))))
        self.assertIn("D012", self.codes(self.mutated(lambda s: self.dev(s, "ops", "vmhost").update(vm={"note": 1, "contents": ["MADE UP SERVER"]}))))
        self.assertIn("D013", self.codes(self.mutated(lambda s: self.dev(s, "ops", "vmhost").pop("vm")), "warnings"))


class ConnectionTests(SpecTestCase):
    def conn(self, s, i=0):
        return s["connections"][i]

    def test_references_and_cables(self):
        self.assertIn("C001", self.codes(self.mutated(lambda s: self.conn(s).update(to="nope"))))
        self.assertIn("C002", self.codes(self.mutated(lambda s: self.conn(s).update(cable="coax"))))
        self.assertIn("C007", self.codes(self.mutated(lambda s: self.conn(s).update(to="ws"))))

    def test_purdue_adjacency_and_field_hardwiring(self):
        self.assertIn("C003", self.codes(self.mutated(lambda s: s["connections"].append({"from": "ws", "to": "flame", "cable": "hardwired", "basis": "assumed"}))))
        self.assertIn("C004", self.codes(self.mutated(lambda s: self.conn(s, 2).update(cable="ethernet"))))
        self.assertIn("C009", self.codes(self.mutated(lambda s: self.conn(s, 0).update(cable="hardwired")), "warnings"))

    def test_the_dmz_needs_a_firewall_between(self):
        def base(s):
            s["options"]["dmz"] = True
            s["groups"].append({"id": "dmz", "title": "DMZ", "level": "3.5", "devices": [
                {"id": "siem", "basis": "prompt", "label": "SIEM", "qty": 1, "quote": "Show the SIEM in the DMZ"}]})
            s["groups"].append({"id": "l3", "title": "Site operations", "level": "3", "devices": [
                {"id": "hist", "basis": "prompt", "label": "SCS WEB SERVERS", "qty": 1, "quote": "SCS WEB SERVERS run on the VM"}]})
        self.assertEqual(self.codes(self.mutated(base)), [])
        def no_fw(s):
            base(s)
            s["connections"].append({"from": "hist", "to": "siem", "cable": "ethernet", "basis": "assumed"})
        self.assertIn("C005", self.codes(self.mutated(no_fw)))
        def with_fw(s):                                   # the firewall sits in the DMZ group as a box and carries role firewall
            base(s)
            s["groups"][-2]["devices"].append({"id": "dfw", "basis": "prompt", "label": "SIEM", "qty": 1, "quote": "Show the SIEM in the DMZ", "role": "firewall"})
            s["connections"].append({"from": "hist", "to": "dfw", "cable": "ethernet", "basis": "assumed"})
        self.assertNotIn("C005", self.codes(self.mutated(with_fw)))

    def test_prompt_basis_needs_a_quote_and_assumed_must_not_have_one(self):
        self.assertIn("C006", self.codes(self.mutated(lambda s: self.conn(s).update(basis="prompt"))))
        self.assertIn("C006", self.codes(self.mutated(lambda s: self.conn(s).update(basis="prompt", quote="not in the prompt"))))
        self.assertNotIn("C006", self.codes(self.mutated(lambda s: self.conn(s).update(basis="prompt", quote="Show the SIEM in the DMZ"))))
        self.assertIn("C006", self.codes(self.mutated(lambda s: self.conn(s).update(quote="Show the SIEM in the DMZ"))))

    def test_duplicates_and_rings(self):
        self.assertIn("C008", self.codes(self.mutated(lambda s: s["connections"].append(dict(s["connections"][0]))), "warnings"))
        self.assertIn("R001", self.codes(self.mutated(lambda s: s["rings"].append({"id": "r", "cable": "fibre", "members": ["fw", "ghost"]}))))
        self.assertIn("R001", self.codes(self.mutated(lambda s: s["rings"].append({"id": "r", "cable": "coax", "members": ["fw", "ws"]}))))


class AccountingTests(SpecTestCase):
    def test_a_device_line_must_be_drawn_or_omitted(self):
        def mutate(s):
            s["groups"][2]["devices"][1]["boq"] = [{"sheet": "BOQ", "row": 6}]
            s["groups"][2]["devices"][1]["qty"] = 1
        r = self.run_spec(self.mutated(mutate))
        self.assertIn("B001", {e["code"] for e in r.errors})
        self.assertIn("row 7", " ".join(e["message"] for e in r.errors))

    def test_omitting_with_a_reason_accounts_for_it(self):
        def mutate(s):
            s["groups"][2]["devices"][1]["boq"] = [{"sheet": "BOQ", "row": 6}]
            s["groups"][2]["devices"][1]["qty"] = 1
            s["omitted"].append({"sheet": "BOQ", "row": 7, "reason": "outdoor sounders shown by the indoor one"})
        r = self.run_spec(self.mutated(mutate))
        self.assertTrue(r.ok, r.text())
        self.assertTrue(any("not drawn" in n for n in r.notes))

    def test_omit_errors(self):
        self.assertIn("B002", self.codes(self.mutated(lambda s: s["omitted"].append({"sheet": "BOQ", "row": 99, "reason": "does not exist"}))))
        self.assertIn("B003", self.codes(self.mutated(lambda s: s["omitted"].append({"sheet": "BOQ", "row": 6, "reason": "also drawn above"}))))

    def test_missing_boq_file_and_sheet(self):
        r = S.validate(good_spec(), {}, self.comps, self.purdue, self.cables)
        self.assertIn("B000", {e["code"] for e in r.errors})
        self.assertIn("B001", self.codes(self.mutated(lambda s: s["sources"][0].update(sheets=["Nope"]))))

    def test_default_classified_device_is_a_warning(self):
        self.assertIn("B004", self.codes(good_spec(), "warnings"))


if __name__ == "__main__":
    unittest.main()
