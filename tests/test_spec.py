"""Spec validator tests. Run:  python -m unittest discover -s tests"""
import copy
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import jsonschema_lite
import spec as S
from cables import Cables
from components import Components
from purdue import PurdueMap

PROMPT = ("F&G system with a DMZ. Level 2: 1 Industrial firewall, Work Stations x2, a virtual server host (VM). "
          "Level 1: 2 Guardlogix 5580 Controller. Level 0: 19 Flame detector, 5 Sounder. "
          "Show the SIEM in the DMZ. SCS WEB SERVERS run on the VM.")


def good_spec():
    return {
        "spec_version": 1, "prompt": PROMPT,
        "project": {"end_user": "SEWA", "contractor": "Avanceon", "project": "Test", "prepared_by": "A", "checked_by": "B", "approved_by": "C"},
        "options": {"quantity_mode": "instances", "dmz": False},
        "groups": [
            {"id": "ops", "title": "Operator layer", "level": "2", "devices": [
                {"id": "ws", "label": "Work Stations", "qty": 2, "quote": "Work Stations x2"},
                {"id": "fw", "component": "industrial_firewall", "qty": 1, "quote": "1 Industrial firewall"},
                {"id": "vmhost", "label": "virtual server host", "qty": 1, "quote": "a virtual server host (VM)",
                 "vm": {"note": 1, "contents": ["SCS WEB SERVERS"]}}]},
            {"id": "ctl", "title": "Controllers", "level": "1", "devices": [
                {"id": "plc", "label": "Guardlogix 5580 Controller", "qty": 2, "quote": "2 Guardlogix 5580 Controller"}]},
            {"id": "field", "title": "Field devices", "level": "0", "devices": [
                {"id": "flame", "component": "flame_detector", "qty": 19, "quantity_mode": "type", "quote": "19 Flame detector"},
                {"id": "sounder", "label": "Sounder", "qty": 5, "quote": "5 Sounder"}]}],
        "connections": [
            {"from": "ws", "to": "fw", "cable": "ethernet", "basis": "assumed"},
            {"from": "fw", "to": "plc", "cable": "ethernet", "basis": "assumed"},
            {"from": "plc", "to": "flame", "cable": "hardwired", "basis": "assumed"},
            {"from": "plc", "to": "sounder", "cable": "hardwired", "basis": "assumed"}],
        "rings": [], "notes": [], "answers": {}}


class SpecTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comps, cls.purdue, cls.cables = Components(), PurdueMap(), Cables()

    def run_spec(self, spec):
        return S.validate(spec, self.comps, self.purdue, self.cables)

    def codes(self, spec, which="errors"):
        return sorted({e["code"] for e in getattr(self.run_spec(spec), which)})

    def mutated(self, fn):
        s = copy.deepcopy(good_spec())
        fn(s)
        return s

    def dev(self, s, gid="field", did="sounder"):
        return next(d for g in s["groups"] if g["id"] == gid for d in g["devices"] if d["id"] == did)


class GoodSpecTests(SpecTestCase):
    def test_a_correct_spec_is_valid_and_carries_the_notes(self):
        r = self.run_spec(good_spec())
        self.assertTrue(r.ok, r.text())
        joined = " ".join(r.notes)
        self.assertIn("Work Stations", joined)                      # boxes drawn with the user's wording
        self.assertIn("4 connection(s) are assumed", joined)
        self.assertIn("Detector", joined)                           # provisional Purdue layer used
        self.assertEqual(r.stats["devices"], 6)

    def test_schema_file_accepts_the_good_spec(self):
        self.assertEqual(jsonschema_lite.check(good_spec(), S.load_json(S.SCHEMA_PATH)), [])

    def test_the_sample_spec_is_valid(self):
        r = self.run_spec(S.load_json(os.path.join(HERE, "..", "samples", "spec_example.json")))
        self.assertTrue(r.ok, r.text())

    def test_render_mode(self):
        spec = good_spec()
        srules = S.load_json(S.RULES_PATH)
        groups = {g["id"]: g for g in spec["groups"]}
        rm = lambda gid, did: S.render_mode(self.dev(spec, gid, did), groups[gid], self.comps, self.purdue, srules)
        self.assertEqual(rm("ops", "ws"), "box")                    # no dataset component
        self.assertEqual(rm("ops", "fw"), "picture")                # the firewall has a dataset symbol, and level 2 may show pictures
        self.assertEqual(rm("field", "flame"), "box")               # level 0 is always a box
        picture = {"id": "x", "component": "hot_standby_plc_pair", "qty": 1}
        self.assertEqual(S.render_mode(picture, {"id": "c", "level": "1"}, self.comps, self.purdue, srules), "picture")
        self.assertEqual(S.render_mode(dict(picture, third_party=True), {"id": "c", "level": "1"}, self.comps, self.purdue, srules), "box")
        self.assertEqual(S.render_mode(picture, {"id": "d", "level": "3.5"}, self.comps, self.purdue, srules), "box")
        estop = {"id": "e", "component": "emergency_stop_push_button", "qty": 1}
        self.assertEqual(S.render_mode(estop, {"id": "f", "level": "0"}, self.comps, self.purdue, srules), "box")   # has a picture, still a box (D23)


class StructureAndProjectTests(SpecTestCase):
    def test_structure_errors_stop_everything_else(self):
        self.assertEqual(self.codes(self.mutated(lambda s: s.pop("groups"))), ["S001"])
        self.assertEqual(self.codes(self.mutated(lambda s: s.pop("prompt"))), ["S001"])
        self.assertEqual(self.codes(self.mutated(lambda s: s["options"].update(quantity_mode="all"))), ["S001"])
        self.assertEqual(self.codes(self.mutated(lambda s: self.dev(s).update(colour="red"))), ["S001"])
        self.assertEqual(self.codes(self.mutated(lambda s: self.dev(s).pop("quote"))), ["S001"])

    def test_missing_footer_field(self):
        self.assertEqual(self.codes(self.mutated(lambda s: s["project"].pop("contractor"))), ["P001"])
        self.assertEqual(self.codes(self.mutated(lambda s: (s["project"].pop("contractor"), s["options"].update(allow_tbc=True)))), [])

    def test_group_errors(self):
        self.assertIn("G001", self.codes(self.mutated(lambda s: s["groups"][1].update(id="ops"))))
        self.assertIn("G002", self.codes(self.mutated(lambda s: s["groups"][1].update(level="9"))))
        self.assertIn("G003", self.codes(self.mutated(lambda s: s["groups"][1].update(level="3.5"))))


class DeviceTests(SpecTestCase):
    def test_ids_components_and_labels(self):
        self.assertIn("D001", self.codes(self.mutated(lambda s: self.dev(s, "ctl", "plc").update(id="ws"))))
        self.assertIn("D002", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(component="not_in_dataset"))))
        self.assertIn("D003", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(label="Firewall"))))
        self.assertIn("D004", self.codes(self.mutated(lambda s: self.dev(s).pop("label"))))
        self.assertIn("D005", self.codes(self.mutated(lambda s: self.dev(s).update(label="Siren"))))

    def test_the_quote_must_be_the_users_words(self):
        self.assertIn("D017", self.codes(self.mutated(lambda s: self.dev(s).update(quote="5 Sirens"))))
        def answered(s):                                           # words from the user's answer to a question count
            s["answers"]["siren"] = "Add 3 Siren to the field"
            self.dev(s).update(label="Siren", quote="3 Siren", qty=3)
        self.assertEqual(self.codes(self.mutated(answered)), [])

    def test_a_component_must_be_named_by_the_quote(self):
        self.assertIn("D018", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(component="gas_detector"))))
        self.assertIn("D018", self.codes(self.mutated(lambda s: (self.dev(s).pop("label"), self.dev(s).update(component="ups")))))

    def test_clashing_titles_make_the_model_ask(self):
        def plc(s, quote):
            s["prompt"] += " " + quote
            self.dev(s, "ctl", "plc").pop("label")
            self.dev(s, "ctl", "plc").update(component="compact_plc_siemens_6es72141ag400xb0", quote=quote, qty=1)
        self.assertIn("D019", self.codes(self.mutated(lambda s: plc(s, "1 Compact PLC"))))
        self.assertNotIn("D019", self.codes(self.mutated(lambda s: plc(s, "1 Siemens Compact PLC"))))
        self.assertNotIn("D018", self.codes(self.mutated(lambda s: plc(s, "1 Compact PLC 6ES7214-1AG40-0XB0"))))

    def test_prompt_only_devices(self):
        def add_dmz(s, label="SIEM", quote="Show the SIEM in the DMZ"):
            s["options"]["dmz"] = True
            s["groups"].append({"id": "dmz", "title": "DMZ", "level": "3.5", "devices": [{"id": "siem", "label": label, "qty": 1, "quote": quote}]})
        self.assertEqual(self.codes(self.mutated(add_dmz)), [])
        self.assertIn("D017", self.codes(self.mutated(lambda s: add_dmz(s, quote="Show the WAF"))))
        self.assertIn("D005", self.codes(self.mutated(lambda s: add_dmz(s, label="WAF"))))

    def test_dmz_and_third_party_items_are_boxes(self):
        def mutate(s):
            s["options"]["dmz"] = True
            s["groups"].append({"id": "dmz", "title": "DMZ", "level": "3.5", "devices": [
                {"id": "dfw", "component": "industrial_firewall", "qty": 1, "quote": "1 Industrial firewall"}]})
            s["groups"][0]["devices"].pop(1)
        self.assertIn("D014", self.codes(self.mutated(mutate)))
        self.assertIn("D014", self.codes(self.mutated(lambda s: self.dev(s, "ops", "fw").update(third_party=True))))

    def test_quantity_plan_errors(self):
        self.assertIn("D009", self.codes(self.mutated(lambda s: (self.dev(s).update(quantity_mode="instances"), s["options"].update(max_instances=3)))))
        self.assertIn("D009", self.codes(self.mutated(lambda s: self.dev(s).update(qty=0))))

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
            s["groups"].append({"id": "dmz", "title": "DMZ", "level": "3.5", "devices": [{"id": "siem", "label": "SIEM", "qty": 1, "quote": "Show the SIEM in the DMZ"}]})
            s["groups"].append({"id": "l3", "title": "Site operations", "level": "3", "devices": [
                {"id": "hist", "label": "SCS WEB SERVERS", "qty": 1, "quote": "SCS WEB SERVERS run on the VM"}]})
        self.assertEqual(self.codes(self.mutated(base)), [])
        def no_fw(s):
            base(s)
            s["connections"].append({"from": "hist", "to": "siem", "cable": "ethernet", "basis": "assumed"})
        self.assertIn("C005", self.codes(self.mutated(no_fw)))
        def with_fw(s):                                   # the firewall sits in the DMZ group as a box and carries role firewall
            base(s)
            s["groups"][-2]["devices"].append({"id": "dfw", "label": "SIEM", "qty": 1, "quote": "Show the SIEM in the DMZ", "role": "firewall"})
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


if __name__ == "__main__":
    unittest.main()
