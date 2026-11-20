"""Practice score scales for TOEFL iBT (2026) and Cambridge exams. Estimates only."""
from __future__ import annotations


def toefl_band(pct: float) -> float:
    """Map a proportion correct/achieved to the 1–6 TOEFL band scale (0.5 steps)."""
    table = [(0.95, 6.0), (0.85, 5.5), (0.75, 5.0), (0.65, 4.5), (0.55, 4.0), (0.45, 3.5), (0.35, 3.0), (0.25, 2.5), (0.15, 2.0), (0.05, 1.5)]
    return next((b for t, b in table if pct >= t), 1.0)


def toefl_overall(bands: list[float]) -> float:
    """ETS: average of section bands, rounded to the nearest half band."""
    avg = sum(bands) / len(bands)
    return round(avg * 2) / 2


def cambridge_scale(pct: float, kind: str) -> int:
    """Cambridge English Scale estimate. 60% ≈ the pass mark (grade C)."""
    lo, passmark, hi = (160, 180, 210) if kind == "cambridge_c1" else (180, 200, 230)
    if pct <= 0.6:
        return round(lo + pct / 0.6 * (passmark - lo))
    return round(passmark + (pct - 0.6) / 0.4 * (hi - passmark))


def cambridge_result(score: int, kind: str) -> str:
    if kind == "cambridge_c1":
        return "Grade A (C2 level)" if score >= 200 else "Grade B" if score >= 193 else "Grade C" if score >= 180 else "Level B2 (C1 not yet achieved)" if score >= 160 else "Below B2"
    return "Grade A" if score >= 220 else "Grade B" if score >= 213 else "Grade C" if score >= 200 else "Level C1 (C2 not yet achieved)" if score >= 180 else "Below C1"


def section_score(pct: float, kind: str):
    return toefl_band(pct) if kind == "toefl2026" else cambridge_scale(pct, kind)


def overall(scores: list, kind: str) -> dict:
    if kind == "toefl2026":
        o = toefl_overall(scores)
        return {"overall": o, "scale": "TOEFL 1–6 bands", "result": f"Band {o}"}
    o = round(sum(scores) / len(scores))
    return {"overall": o, "scale": "Cambridge English Scale", "result": cambridge_result(o, kind)}
