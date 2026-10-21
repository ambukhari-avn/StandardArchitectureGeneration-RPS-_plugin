"""Quantity rules. Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import quantity as Q


class QuantityTests(unittest.TestCase):
    def test_whole_numbers_and_fractions(self):
        self.assertEqual(Q.whole(3), (3, None))
        self.assertEqual(Q.whole(3.0), (3, None))
        n, note = Q.whole(8.66667)
        self.assertEqual(n, 9)
        self.assertIn("rounded up", note)
        for bad in (0, -1, "2", None, True, float("nan")):
            with self.assertRaises(Q.QuantityError):
                Q.whole(bad)

    def test_instances_are_numbered_and_never_collapsed_silently(self):
        self.assertEqual(Q.plan(1)["suffixes"], [""])
        self.assertEqual(Q.plan(3)["suffixes"], ["-01", "-02", "-03"])
        self.assertEqual(len(Q.plan(12)["suffixes"]), 12)
        with self.assertRaises(Q.QuantityError) as e:
            Q.plan(13)
        self.assertIn("never done silently", str(e.exception))
        self.assertEqual(len(Q.plan(13, max_instances=20)["suffixes"]), 13)

    def test_count_and_type_modes_are_explicit_collapses(self):
        self.assertEqual(Q.plan(88, "count"), {"n": 88, "mode": "count", "suffixes": [" x88"], "shown": True, "notes": []})
        self.assertEqual(Q.plan(1, "count")["suffixes"], [""])
        t = Q.plan(88, "type")
        self.assertEqual((t["suffixes"], t["shown"]), ([""], False))
        self.assertTrue(any("not shown" in n for n in t["notes"]))

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(Q.QuantityError):
            Q.plan(2, "all")


if __name__ == "__main__":
    unittest.main()
