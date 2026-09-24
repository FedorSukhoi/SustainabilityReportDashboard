import unittest

from dashboard_builder import score_label
from scoring import grade_from_score, overall_from_categories


class IndexScoringTests(unittest.TestCase):
    def test_exclusive_boundaries(self):
        for score, grade in [(0, "F"), (25, "F"), (25.1, "D"), (55, "D"),
                             (55.1, "C"), (70, "C"), (70.1, "B"), (80, "B"),
                             (80.1, "A"), (100, "A"), (78, "B"), (60, "C")]:
            with self.subTest(score=score):
                self.assertEqual(grade_from_score(score), grade)
                self.assertEqual(score_label(score)[0], "Starter" if grade == "F" else grade)

    def test_hm_retains_bonus_and_changes_weights(self):
        self.assertEqual(overall_from_categories(
            {"Environmental": 62.9, "Social": 21.1, "Governance": 33.2}, 7), 58.6)

    def test_pillar_contributions(self):
        for name, expected in [("Environmental", 70), ("Social", 20), ("Governance", 10)]:
            scores = dict.fromkeys(["Environmental", "Social", "Governance"], 0)
            scores[name] = 100
            self.assertEqual(overall_from_categories(scores, 0), expected)

    def test_caps_and_rounding(self):
        self.assertEqual(overall_from_categories(dict.fromkeys(
            ["Environmental", "Social", "Governance"], 100), 10), 100)
        self.assertEqual(overall_from_categories(dict.fromkeys(
            ["Environmental", "Social", "Governance"], 0), 20), 10)
        score = overall_from_categories(
            {"Environmental": 80, "Social": 80, "Governance": 80.1}, 0)
        self.assertEqual(score, 80)
        self.assertEqual(grade_from_score(score), "B")
