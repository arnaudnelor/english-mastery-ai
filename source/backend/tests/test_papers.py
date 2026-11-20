import re

import app.providers.speech as S
from app import content
from app.services import scales


def test_scales():
    assert scales.toefl_band(1.0) == 6.0 and scales.toefl_band(0.7) == 4.5 and scales.toefl_band(0.0) == 1.0
    assert scales.toefl_overall([4.5, 5, 4, 5]) == 4.5  # 4.625 -> nearest half = 4.5
    assert scales.cambridge_scale(0.6, "cambridge_c1") == 180 and scales.cambridge_scale(1.0, "cambridge_c1") == 210
    assert scales.cambridge_scale(0.6, "cambridge_c2") == 200 and scales.cambridge_result(214, "cambridge_c2") == "Grade B"
    assert scales.cambridge_result(170, "cambridge_c1").startswith("Level B2")


def test_paper_content_integrity():
    for p in content.papers():
        for s in p["sections"]:
            for part in s["parts"]:
                if part["type"] == "gapfill":
                    nums = re.findall(r"\{(\d+)\}", part["text"])
                    assert sorted(nums, key=int) == sorted(part["gaps"], key=int), (p["id"], part["id"])
                    for g in part["gaps"].values():
                        if "options" in g:
                            assert g["answer"] in g["options"]
                if part["type"] == "mcq":
                    for q in part["questions"]:
                        assert q["answer"] in q["options"], (p["id"], q["prompt"])
                if part["type"] == "build_sentence":
                    for it in part["items"]:
                        assert sorted(it["chunks"]) == sorted(it["answer"].split())


def answers_for(section):
    a = {}
    for part in section["parts"]:
        if part["type"] == "gapfill":
            for gid, g in part["gaps"].items():
                ans = g["answer"] if isinstance(g["answer"], str) else g["answer"][0]
                a[f"{part['id']}:{gid}"] = ans
        elif part["type"] == "mcq":
            for q in part["questions"]:
                a[f"{part['id']}:{q['id']}"] = q["answer"]
        elif part["type"] in ("transform", "build_sentence"):
            for it in part["items"]:
                a[f"{part['id']}:{it['id']}"] = it["answer"] if isinstance(it["answer"], str) else it["answer"][0]
    return a


def test_toefl_flow(client, profile, llm):
    paper = client.get("/api/papers/toefl-2026-1").json()
    assert "answer" not in paper["sections"][0]["parts"][0]["gaps"]["1"]
    raw = content.by_id(content.papers(), "toefl-2026-1")
    aid = client.post("/api/papers/toefl-2026-1/attempts").json()["attempt_id"]
    r = client.post(f"/api/papers/toefl-2026-1/attempts/{aid}/sections/reading/objective", json={"answers": answers_for(raw["sections"][0])}).json()
    assert r["pct"] == 1.0 and r["score"] == 6.0
    # complete-the-words accepts the full word too
    r2 = client.post(f"/api/papers/toefl-2026-1/attempts/{aid}/sections/listening/objective", json={"answers": {}}).json()
    assert r2["score"] == 1.0
    w = client.post(f"/api/papers/toefl-2026-1/attempts/{aid}/sections/writing/writing",
                    json={"texts": {"email": "x " * 90, "discussion": "y " * 110}, "answers": answers_for(raw["sections"][2])}).json()
    assert round(w["pct"], 3) == round((0.8 + 0.6 + 1.0) / 3, 3)
    S._stt_override.next_text = "Welcome to the science building"
    files = {f"repeat:r{i}": (f"r{i}.webm", b"x", "audio/webm") for i in range(1, 8)}
    files["interview:i1"] = ("i1.webm", b"x", "audio/webm")
    sp = client.post(f"/api/papers/toefl-2026-1/attempts/{aid}/sections/speaking/speaking", files=files)
    assert sp.status_code == 200, sp.text
    assert sp.json()["repeat"][0]["score"] == 1.0
    f = client.post(f"/api/papers/toefl-2026-1/attempts/{aid}/finish").json()
    assert f["scale"] == "TOEFL 1–6 bands" and f["complete"] and f["weakest"] == "listening"


def test_cambridge_full_word_and_transform(client, profile):
    aid = client.post("/api/papers/cambridge-c1-1/attempts").json()["attempt_id"]
    r = client.post(f"/api/papers/cambridge-c1-1/attempts/{aid}/sections/reading/objective",
                    json={"answers": {"p4:t4": "wish I'd studied", "p2:1": "AS", "p3:4": "Unfortunately"}}).json()
    assert r["correct"] == 3 and 160 <= r["score"] < 180
    f = client.post(f"/api/papers/cambridge-c1-1/attempts/{aid}/finish").json()
    assert f["result"].startswith("Level B2") or f["result"] == "Below B2"
