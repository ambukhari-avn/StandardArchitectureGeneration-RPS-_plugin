"""Building the diagram from a spec. Run:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_diagram as B
import spec as S

BASE = os.environ.get("ARCH_BASE_VSDX") or os.path.join(HERE, "..", "base", "base.vsdx")
PROMPT = ("Video wall at level 2, 2 Rack PLC at level 1, 3 Gas thing at level 0. The video wall connects to the Rack PLC over Ethernet "
          "and the Rack PLC is hardwired to the Gas thing.")


def spec():
    return {"spec_version": 1, "prompt": PROMPT, "project": {"project": "T"},
            "options": {"quantity_mode": "instances", "dmz": False, "allow_tbc": True},
            "groups": [
                {"id": "l2", "title": "Supervisory", "level": "2", "devices": [
                    {"id": "wall", "qty": 1, "quote": "Video wall", "component": "video_wall"}]},
                {"id": "l1", "title": "Control", "level": "1", "devices": [
                    {"id": "plc", "qty": 2, "quote": "2 Rack PLC", "component": "rack_plc"}]},
                {"id": "l0", "title": "Field", "level": "0", "devices": [
                    {"id": "gas", "qty": 3, "quote": "3 Gas thing", "label": "Gas thing"}]}],
            "connections": [
                {"from": "wall", "to": "plc", "cable": "ethernet", "basis": "prompt", "quote": "The video wall connects to the Rack PLC over Ethernet"},
                {"from": "plc", "to": "gas", "cable": "hardwired", "basis": "prompt", "quote": "the Rack PLC is hardwired to the Gas thing"}]}


def build(s):
    out = os.path.join(tempfile.mkdtemp(), "o.vsdx")
    return B.build(s, BASE, out), out


def images(r):
    return [s for s in r["page"].shapes if s["kind"] == "image"]


class BuildTests(unittest.TestCase):
    def test_builds_an_a3_file_with_pictures_boxes_and_lines(self):
        r, out = build(spec())
        self.assertEqual(r["items"], 1 + 2 + 3)                                  # one per unit in instances mode
        self.assertEqual(len(images(r)) - 1, 3)                                  # video wall + 2 PLCs (+ the footer logo)
        self.assertTrue(any((s["key"] or "").startswith("prompt:3 Gas thing") for s in r["page"].shapes))    # a box carries its quote
        with zipfile.ZipFile(out) as z:
            ET.fromstring(z.read("visio/pages/page1.xml"))
            self.assertIn("16.5354", z.read("visio/pages/pages.xml").decode())

    def test_connections_are_in_the_cable_colour_and_touch_no_other_item(self):
        r, _ = build(spec())
        lines = [s for s in r["page"].shapes if s["kind"] == "line" and "->" in (s["key"] or "")]
        self.assertEqual(len(lines), 2 + 3)                                       # each unit of the larger side meets the nearest unit of the smaller
        self.assertEqual({s["line"] for s in lines}, {"#0000FF", "#000000"})
        self.assertEqual(r["warnings"], [])

    def test_count_mode_gives_one_item_with_the_quantity(self):
        s = spec()
        s["options"]["quantity_mode"] = "count"
        r, _ = build(s)
        self.assertEqual(r["items"], 3)
        self.assertTrue(any(sh["text"] == "Gas thing x3" for sh in r["page"].shapes))

    def test_an_invalid_spec_is_not_drawn(self):
        s = spec()
        s["groups"][2]["devices"][0]["label"] = "Invented sensor"
        with self.assertRaises(B.BuildError) as e:
            build(s)
        self.assertIn("D005", str(e.exception))

    def test_too_many_items_for_the_page_stop_the_build(self):
        s = spec()
        s["groups"][2]["devices"][0].update(qty=12, quote="3 Gas thing")
        s["options"]["max_instances"] = 100
        s["groups"][2]["devices"] += [{"id": "d%d" % i, "qty": 12, "quote": "3 Gas thing", "label": "Gas thing"} for i in range(40)]
        with self.assertRaises(B.BuildError) as e:
            build(s)
        self.assertIn("one A3 page", str(e.exception))

    def test_everything_stays_above_the_footer(self):
        r, _ = build(spec())
        foot = next(s for s in r["page"].shapes if s["role"] == "block")
        for s in r["page"].shapes:
            if (s["key"] or "").startswith("prompt:") or s["role"] == "band":
                self.assertGreaterEqual(s["y"], foot["y"] + foot["h"] - 1e-6)

    def test_the_dataset_workstation_symbol_is_drawn_when_the_quote_names_it(self):
        s = spec()
        s["prompt"] += " 2 Client / operator workstation."
        s["groups"][0]["devices"].append({"id": "ows", "qty": 2, "quote": "2 Client / operator workstation", "component": "client_operator_workstation"})
        r, _ = build(s)
        self.assertEqual(len(images(r)) - 1, 5)


class VmAndDmzTests(unittest.TestCase):
    def test_vm_contents_go_in_a_side_panel_and_dmz_is_boxes(self):
        s = {"spec_version": 1, "prompt": "Add a DMZ with a Jump host box. The Historian server VM runs Historian and Backup.", "project": {"project": "T"},
             "options": {"quantity_mode": "instances", "dmz": True, "allow_tbc": True},
             "groups": [{"id": "dmz", "title": "DMZ", "level": "3.5", "devices": [{"id": "jump", "qty": 1, "label": "Jump host", "quote": "Jump host"}]},
                        {"id": "l2", "title": "Supervisory", "level": "2", "devices": [
                            {"id": "hist", "qty": 1, "label": "Historian server VM", "quote": "The Historian server VM",
                             "vm": {"note": 1, "contents": ["Historian", "Backup"]}}]}]}
        r, _ = build(s)
        texts = [sh["text"] for sh in r["page"].shapes]
        self.assertIn("Historian", texts)
        self.assertIn("Backup", texts)
        self.assertEqual([sh["pattern"] for sh in r["page"].shapes if sh["text"] == "Historian server VM"], [2])   # dashed
        self.assertEqual(r["bands"], 2)


class SampleTests(unittest.TestCase):
    def test_the_sample_spec_builds_without_warnings(self):
        r, _ = build(S.load_json(os.path.join(HERE, "..", "samples", "spec_example.json")))
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["bands"], 3)
        self.assertEqual(len(images(r)) - 1, 2)                                   # the two workstation symbols


if __name__ == "__main__":
    unittest.main()
