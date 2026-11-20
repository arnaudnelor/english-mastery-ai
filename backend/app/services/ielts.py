"""IELTS band helpers. All outputs are PRACTICE ESTIMATES, not official scores."""
from __future__ import annotations

# Approximate Academic Listening/Reading raw-score (out of 40) to band table.
_TABLE = [(39, 9.0), (37, 8.5), (35, 8.0), (33, 7.5), (30, 7.0), (27, 6.5), (23, 6.0), (19, 5.5),
          (15, 5.0), (13, 4.5), (10, 4.0), (8, 3.5), (6, 3.0), (4, 2.5), (0, 2.0)]


def objective_band(correct: int, total: int) -> float:
    """Scale to a 40-question test, then apply the band table."""
    raw = round(correct / max(1, total) * 40)
    return next(b for threshold, b in _TABLE if raw >= threshold)


def round_band(x: float) -> float:
    """IELTS overall rounding: .25 rounds up to .5, .75 rounds up to the next whole band."""
    whole = int(x)
    frac = x - whole
    if frac < 0.25:
        return float(whole)
    if frac < 0.75:
        return whole + 0.5
    return float(whole + 1)


def half(x: float) -> float:
    return round(x * 2) / 2
