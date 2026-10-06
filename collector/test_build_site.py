"""Run: python3 -m unittest discover collector"""
import unittest

from build_site import missing_days, trusted


class MissingDays(unittest.TestCase):
    def test_gap_in_the_middle(self):
        self.assertEqual(missing_days({"2026-10-02": 1, "2026-10-04": 1, "2026-10-05": 1}), ["2026-10-03"])

    def test_no_gaps(self):
        self.assertEqual(missing_days({"2026-10-02": 1, "2026-10-03": 1}), [])
        self.assertEqual(missing_days({}), [])


class Trusted(unittest.TestCase):
    def test_imerco_rows_with_a_before_price_before_the_fix_are_left_out(self):
        # D-024: those may be member prices recorded as offers.
        self.assertFalse(trusted("imerco", "2026-10-06", {"s": "100452261", "p": 187.46, "lp": 249.95}))
        self.assertTrue(trusted("imerco", "2026-10-06", {"s": "100452261", "p": 249.95}))
        self.assertTrue(trusted("imerco", "2026-10-07", {"s": "100452261", "p": 199.95, "lp": 249.95}))
        self.assertTrue(trusted("power", "2026-10-06", {"s": "1", "p": 187.46, "lp": 249.95}))


if __name__ == "__main__":
    unittest.main()
