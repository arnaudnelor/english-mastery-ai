"""Word-level alignment between a target text and what was heard/typed.

Used for dictation scoring (typed) and read-aloud checks (Whisper transcript).
This measures *intelligibility to a speech recogniser*, which is a useful but
partial proxy for pronunciation; it is not phoneme-level assessment.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def tokens(text: str) -> list[str]:
    text = text.lower().replace("’", "'").replace("per cent", "percent").replace("%", " percent")
    toks = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)
    return [_NUM.get(t, t) for t in toks]


def align(target: str, heard: str) -> dict:
    t_disp = re.findall(r"\S+", target)
    t, h = tokens(target), tokens(heard)
    # Map normalised tokens back to display words (1:1 when punctuation-only differences)
    display = t_disp if len(t_disp) == len(t) else t
    sm = SequenceMatcher(a=t, b=h, autojunk=False)
    words: list[dict] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            words += [{"word": display[i], "status": "ok"} for i in range(i1, i2)]
        elif op == "replace":
            heard_seg = " ".join(h[j1:j2])
            for k, i in enumerate(range(i1, i2)):
                words.append({"word": display[i], "status": "wrong", "heard": heard_seg if k == 0 else None})
        elif op == "delete":
            words += [{"word": display[i], "status": "missed"} for i in range(i1, i2)]
        elif op == "insert":
            words.append({"word": None, "status": "extra", "heard": " ".join(h[j1:j2])})
    correct = sum(1 for w in words if w["status"] == "ok")
    extras = sum(1 for w in words if w["status"] == "extra")
    score = correct / max(1, len(t) + extras * 0.5)
    return {"score": round(min(1.0, score), 3), "words": words, "target_words": len(t), "correct_words": correct}
