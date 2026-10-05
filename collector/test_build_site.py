"""Run: python3 -m unittest discover collector"""
import unittest

from build_site import missing_days


class MissingDays(unittest.TestCase):
    def test_gap_in_the_middle(self):
        self.assertEqual(missing_days({"2026-10-02": 1, "2026-10-04": 1, "2026-10-05": 1}), ["2026-10-03"])

    def test_no_gaps(self):
        self.assertEqual(missing_days({"2026-10-02": 1, "2026-10-03": 1}), [])
        self.assertEqual(missing_days({}), [])


if __name__ == "__main__":
    unittest.main()
