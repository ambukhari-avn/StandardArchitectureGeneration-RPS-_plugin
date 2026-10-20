"""Sample specs and the model input pack. Run:  python -m unittest discover -s tests
The real-BOQ checks are skipped unless ARCH_BOQ_DIR points at the folder with the client's workbooks."""
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import jsonschema_lite
import spec as S
import spec_input
from xlsx_helper import make_xlsx

SAMPLES = os.path.join(HERE, "..", "samples")
DIR = os.environ.get("ARCH_BOQ_DIR")


def sample(name):
    return S.load_json(os.path.join(SAMPLES, name))


class SampleSpecTests(unittest.TestCase):
    def test_samples_follow_the_schema_and_refer_only_to_their_own_devices(self):
        schema = S.load_json(S.SCHEMA_PATH)
        for name in ("spec_kemari.json", "spec_korangi.json"):
            s = sample(name)
            self.assertEqual(jsonschema_lite.check(s, schema), [], name)
            ids = [d["id"] for g in s["groups"] for d in g["devices"]]
            self.assertEqual(len(ids), len(set(ids)), name)
            for c in s["connections"]:
                self.assertIn(c["from"], ids)
                self.assertIn(c["to"], ids)
            self.assertEqual({g["level"] for g in s["groups"]}, {"0", "1", "2"})
            self.assertFalse(s["options"]["dmz"])

    def test_samples_use_no_image_and_no_invented_component(self):
        from components import Components
        comps = Components()
        for name in ("spec_kemari.json", "spec_korangi.json"):
            for g in sample(name)["groups"]:
                for d in g["devices"]:
                    if d.get("component"):
                        self.assertIn(d["component"], comps.by_id)


class InputPackTests(unittest.TestCase):
    ROWS = [["Sr.", "Description", "Model Number", "Make", "Unit", "Qty"],
            ["Flame Detectors"],
            [1.0, "FS24X PLUS kit", "FS24XP-SMGXX", "Honeywell", "No", 19.0],
            [2.0, "Name plates / Labels", "X4S", "Honeywell", "No", 19.0],
            [1.0, "Industrial firewall", "6GK5615-0AA00-2AA2", "Siemens", "No", 1.0],
            [1.0, "Engineering Services", "", "Avanceon", "Job", 1.0]]

    def test_pack_lists_everything_the_model_may_use(self):
        path = make_xlsx({"BOQ": self.ROWS})
        text = spec_input.build_pack(path, ["BOQ"], "Show the SIEM in the DMZ.")
        self.assertIn("Show the SIEM in the DMZ.", text)
        for cable in ("ethernet", "fibre", "modbus", "bacnet", "hardwired"):
            self.assertIn("| %s |" % cable, text)
        self.assertIn("| 3.5 | Industrial DMZ |", text)
        self.assertIn("| industrial_firewall |", text)
        self.assertRegex(text, r"\| 3 \|[^\n]*FS24X PLUS kit[^\n]*heading: `flame_detector`")        # heading match shown
        self.assertRegex(text, r"\| 5 \|[^\n]*Industrial firewall[^\n]*line: `industrial_firewall`")  # part-number match shown
        self.assertNotIn("| 4 | Flame Detectors | Name plates", text)                                  # components are not device lines
        self.assertIn("component 1", text)
        self.assertIn("service 1", text)
        self.assertIn("all accounted for: yes", text)


@unittest.skipUnless(DIR and os.path.isdir(DIR), "set ARCH_BOQ_DIR to the folder with the client's BOQ workbooks")
class RealSampleTests(unittest.TestCase):
    def test_both_samples_validate_against_their_real_boq(self):
        for name, pattern in (("spec_kemari.json", "*Kemari*.xlsx"), ("spec_korangi.json", "*Korangi*.xlsx")):
            path = glob.glob(os.path.join(DIR, pattern))[0]
            r = S.validate(sample(name), [path])
            self.assertTrue(r.ok, r.text())
            self.assertEqual(r.stats["drawn_rows"], r.stats["boq_device_lines"])             # every device line drawn
            self.assertTrue(any("assumed" in n for n in r.notes))

    def test_a_sample_checked_against_the_wrong_boq_fails(self):
        wrong = glob.glob(os.path.join(DIR, "*Korangi*.xlsx"))[0]
        s = sample("spec_kemari.json")
        s["sources"][0]["file"] = os.path.basename(wrong)
        r = S.validate(s, [wrong])
        self.assertFalse(r.ok)
        self.assertTrue({"D006", "B001"} & {e["code"] for e in r.errors})


if __name__ == "__main__":
    unittest.main()
