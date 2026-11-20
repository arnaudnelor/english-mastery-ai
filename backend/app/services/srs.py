"""SM-2 spaced repetition (as used by Anki/SuperMemo), adapted.

Grades: 0=forgot, 1=hard, 2=good, 3=easy.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..models import VocabCard

MIN_EASE = 1.3


def review(card: VocabCard, grade: int, now: datetime | None = None) -> VocabCard:
    if grade not in (0, 1, 2, 3):
        raise ValueError("grade must be 0..3")
    now = now or datetime.utcnow()
    # map 0..3 onto SM-2's 0..5 quality scale
    q = {0: 1, 1: 3, 2: 4, 3: 5}[grade]

    if q < 3:
        card.repetitions = 0
        card.interval_days = 0
        card.lapses += 1
        due = now + timedelta(minutes=10)
    else:
        card.repetitions += 1
        if card.repetitions == 1:
            card.interval_days = 1
        elif card.repetitions == 2:
            card.interval_days = 6 if grade >= 2 else 3
        else:
            card.interval_days = max(1, round(card.interval_days * card.ease))
        if grade == 3:
            card.interval_days = max(card.interval_days, round(card.interval_days * 1.3))
        due = now + timedelta(days=card.interval_days)

    card.ease = max(MIN_EASE, card.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    card.due_at = due
    card.last_reviewed_at = now
    return card


def status(card: VocabCard) -> str:
    if card.repetitions == 0 and card.lapses == 0:
        return "new"
    if card.lapses >= 3 and card.interval_days < 7:
        return "often_forgotten"
    if card.interval_days >= 21:
        return "mastered"
    return "learning"
