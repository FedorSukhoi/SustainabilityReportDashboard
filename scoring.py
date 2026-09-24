"""Shared index aggregation and exclusive grade boundaries."""

METHODOLOGY_VERSION = "index-2026-09-24"
MAX_CERTIFICATION_BONUS = 10
DIMENSION_WEIGHTS = {"Environmental": 0.7, "Social": 0.2, "Governance": 0.1}


def overall_from_categories(scores, certification_bonus):
    """Use the existing one-decimal category scores; round before grading."""
    weighted = sum(scores[name] * weight for name, weight in DIMENSION_WEIGHTS.items())
    return min(round(weighted + min(certification_bonus, MAX_CERTIFICATION_BONUS), 1), 100)


def grade_from_score(score):
    for grade, threshold in (("A", 80), ("B", 70), ("C", 55), ("D", 25)):
        if score > threshold:
            return grade
    return "F"
