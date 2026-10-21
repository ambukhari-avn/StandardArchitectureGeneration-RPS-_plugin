"""Does a piece of the user's wording name a dataset component? Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import matching as M
from components import Components


class HelperTests(unittest.TestCase):
    def test_normalising(self):
        self.assertEqual(M.norm("  Flame-Detector!! "), "flame detector")
        self.assertEqual(M.norm_singular("Flame Detectors"), M.norm_singular("flame detector"))
        self.assertEqual(M.norm_singular("Glass"), "glass")                   # 'ss' is not a plural

    def test_part_tokens_need_letters_digits_and_length(self):
        self.assertEqual(M.part_tokens("6GK5615-0AA00-2AA2 / BMEH584040"), {"6gk56150aa002aa2", "bmeh584040"})
        self.assertEqual(M.part_tokens("M580 TM221 kit"), set())              # short family names do not count


class MatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = M.Matcher(Components())

    def status(self, text, cid):
        return self.m.check(text, cid)[0]

    def test_a_title_in_the_text_names_the_component(self):
        self.assertEqual(self.status("2 Client / operator workstation", "client_operator_workstation"), "ok")
        self.assertEqual(self.status("5 Client operator workstations", "client_operator_workstation"), "ok")     # plural, no slash
        self.assertEqual(self.status("1 Industrial firewall", "industrial_firewall"), "ok")

    def test_no_title_no_match(self):
        self.assertEqual(self.status("2 Work Stations", "client_operator_workstation"), "no")
        self.assertEqual(self.status("1 ESD push button", "emergency_stop_push_button"), "no")

    def test_an_order_number_names_the_component(self):
        self.assertEqual(self.status("one SCALANCE 6GK5615-0AA00-2AA2", "industrial_firewall"), "ok")

    def test_the_longest_title_wins(self):
        self.assertEqual(self.status("1 Compact PLC (larger)", "compact_plc_schneider_tm241ce24t"), "ok")
        self.assertEqual(self.status("1 Compact PLC (larger)", "compact_plc_siemens_6es72141ag400xb0"), "no")

    def test_shared_titles_need_a_brand_or_an_order_number(self):
        self.assertEqual(self.status("1 Safety PLC", "safety_plc_abb"), "ambiguous")
        self.assertEqual(self.status("1 ABB Safety PLC", "safety_plc_abb"), "ok")
        self.assertNotEqual(self.status("1 ABB Safety PLC", "safety_plc_siemens"), "ok")          # the brand named is not Siemens
        self.assertEqual(self.status("1 HMI panel", "hmi_panel_siemens"), "ambiguous")

    def test_candidates_are_reported_for_the_question_to_the_user(self):
        status, cands = self.m.check("1 Safety PLC", "safety_plc_abb")
        self.assertEqual(status, "ambiguous")
        self.assertEqual(set(cands), {"safety_plc_abb", "safety_plc_schneider", "safety_plc_siemens"})


if __name__ == "__main__":
    unittest.main()
