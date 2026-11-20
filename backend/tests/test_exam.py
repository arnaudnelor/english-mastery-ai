from app import content
from app.services.ielts import objective_band, round_band


def test_band_maths():
    assert objective_band(40, 40) == 9.0
    assert objective_band(30, 40) == 7.0
    assert objective_band(12, 16) == 7.0  # 75% -> raw 30
    assert round_band(6.25) == 6.5 and round_band(6.75) == 7.0 and round_band(6.1) == 6.0 and round_band(6.6) == 6.5


def test_exam_content_references_exist():
    for e in content.exams():
        for iid in e["sections"]["listening"]["items"]:
            assert content.exam_listening(iid)
            assert not content.by_id(content.listening_items(), iid)  # exam-only content
        for tid in e["sections"]["reading"]["texts"]:
            assert content.exam_reading(tid)
            assert not content.by_id(content.reading_texts(), tid)
    for it in content.exam_ielts()["listening"] + content.exam_ielts()["reading"]:
        for q in it["questions"]:
            assert q["answer"] in q["options"]


def test_full_mock_flow(client, profile, llm):
    exam = client.get("/api/exam/exams/ielts-academic-1").json()
    assert "answer" not in exam["listening"]["parts"][0]["questions"][0]
    aid = client.post("/api/exam/attempts", json={"exam_id": "ielts-academic-1"}).json()["attempt_id"]
    # answer all listening questions correctly
    answers = {}
    for part in exam["listening"]["parts"]:
        it = content.exam_listening(part["id"])
        for q in it["questions"]:
            answers[f"{part['id']}:{q['id']}"] = q["answer"]
    L = client.post(f"/api/exam/attempts/{aid}/objective", json={"section": "listening", "answers": answers}).json()
    assert L["band"] == 9.0 and L["correct"] == L["total"]
    R = client.post(f"/api/exam/attempts/{aid}/objective", json={"section": "reading", "answers": {}}).json()
    assert R["band"] == 2.0
    W = client.post(f"/api/exam/attempts/{aid}/writing", json={"task1": "x " * 160, "task2": "y " * 260}).json()
    assert W["band"] == 6.5  # (6 + 2*7)/3 = 6.67 -> 6.5
    S = client.post(f"/api/exam/attempts/{aid}/speaking", files={k: (f"{k}.webm", b"x", "audio/webm") for k in ("part1", "part2", "part3")})
    assert S.status_code == 200, S.text
    assert S.json()["band"] == 6.5 and S.json()["parts"][0]["transcript"]
    f = client.post(f"/api/exam/attempts/{aid}/finish").json()
    assert f["overall"] == round_band((9 + 2 + 6.5 + 6.5) / 4) and f["weakest"] == "reading" and f["complete"]
    assert client.post(f"/api/exam/attempts/{aid}/finish").status_code == 409
    assert client.get("/api/exam/attempts").json()[0]["overall_band"] == f["overall"]
