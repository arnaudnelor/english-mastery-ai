from app import content
from app.services.alignment import align
import app.providers.speech as S


def test_new_content_integrity():
    texts = content.reading_texts()
    assert len(texts) >= 8 and {t["level"] for t in texts} == {"A1", "A2", "B1", "B2", "C1", "C2"}
    for t in texts:
        assert len(t["body"].split()) > (120 if t["level"] in ("A1", "A2") else 200)
        for q in t["questions"]:
            assert q["answer"] in q["options"]
        for g in t["glossary"]:
            assert g.lower() in t["body"].lower(), (t["id"], g)
    items = content.listening_items()
    assert len(items) >= 6
    for it in items:
        for ln in it["lines"]:
            assert ln["s"] in it["speakers"]
        for q in it["questions"]:
            assert q["answer"] in q["options"]
        for d in it["dictation"]:
            assert 0 <= d < len(it["lines"])
        for g in it["gaps"]:
            line = it["lines"][g["line"]]["t"]
            for w in g["words"]:
                assert w in line, (it["id"], w)
    pr = content.pronunciation()
    assert len(pr["sounds"]) >= 20 and len(pr["minimal_pairs"]) >= 8
    assert len(content.grammar_topics()) >= 20
    assert any(t["level"] == "C2" for t in content.grammar_topics())


def test_alignment():
    r = align("I think the third quarter was strong.", "I sink the third quarter was strong")
    assert r["words"][1] == {"word": "think", "status": "wrong", "heard": "sink"}
    assert r["correct_words"] == 6
    assert align("Ten per cent", "10%")["score"] == 1.0
    assert align("Hello there", "")["words"][0]["status"] == "missed"


def test_reading_flow(client, profile, llm):
    lst = client.get("/api/reading/texts").json()
    assert next(x for x in lst if x["id"] == "four-day-week")["word_count"] > 200
    t = client.get("/api/reading/texts/four-day-week").json()
    assert "answer" not in t["questions"][0]
    r = client.post("/api/reading/texts/four-day-week/answer", json={"question_id": "q2", "answer": "It fell from 18% to 4%."}).json()
    assert r["correct"]
    f = client.post("/api/reading/texts/four-day-week/finish", json={"seconds": 120}).json()
    assert f["wpm"] == round(f["words"] / 2)
    d = client.post("/api/reading/define", json={"word": "seductive", "sentence": "The promise is seductive."}).json()
    assert d["french"] == "séduisant"
    s = client.post("/api/reading/texts/four-day-week/summary", json={"summary": "The article says peoples like shorter weeks but it is unclear."})
    assert s.status_code == 200 and s.json()["captured_main_idea"]
    assert client.get("/api/profile/dashboard").json()["skills"]["reading"] is not None


def test_listening_flow(client, profile, llm):
    it = client.get("/api/listening/items/budget-meeting").json()
    assert "answer" not in it["questions"][0] and it["gaps"][0]["count"] == 1
    a = client.get("/api/listening/items/budget-meeting/audio/0")
    assert a.status_code == 200 and a.content.startswith(b"ID3")
    assert client.get("/api/listening/items/budget-meeting").json()["audio_cached"] is False  # only line 0 cached
    d = client.post("/api/listening/items/budget-meeting/dictation", json={"line": 2, "text": "Can I just come in there?"}).json()
    assert d["score"] > 0.15 and d["target"].startswith("Can I just")
    assert client.post("/api/listening/items/budget-meeting/dictation", json={"line": 1, "text": "x"}).status_code == 400
    g = client.post("/api/listening/items/budget-meeting/gaps", json={"line": 0, "answers": ["kick things off"]}).json()
    assert g["results"] == [True]
    q = client.post("/api/listening/items/budget-meeting/answer", json={"question_id": "q2", "answer": "The increase is large given flat sales."}).json()
    assert q["correct"]


def test_listening_audio_without_key(client, profile, monkeypatch):
    import app.providers.speech as S
    monkeypatch.setattr(S, "get_secret", lambda n: None)
    r = client.get("/api/listening/items/news-housing/audio/3")
    assert r.status_code == 412


def test_read_aloud(client, profile, llm):
    S._stt_override.next_text = "I sink the third quarter was worth more than three thousand dollars"
    r = client.post("/api/pronunciation/read-aloud", data={"target": "I think the third quarter was worth more than three thousand dollars.", "item_id": "sh2"},
                    files={"audio": ("a.webm", b"xx", "audio/webm")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["words"][1]["status"] == "wrong" and 0.85 < b["score"] < 1
    w = client.get("/api/profile/dashboard").json()["weaknesses"]
    assert any(x["pattern"] == "unclear: think" for x in w)
    assert client.post("/api/pronunciation/minimal-pairs/result", json={"set_id": "th-s", "correct": 8, "total": 10}).json()["score"] == 0.8


def test_azure_parse_and_missing_key(client, profile):
    from app.providers.pronunciation import parse_assessment
    body = {"RecognitionStatus": "Success", "NBest": [{"Display": "Think.", "PronunciationAssessment": {"PronScore": 72.5, "AccuracyScore": 70, "FluencyScore": 90, "CompletenessScore": 100},
            "Words": [{"Word": "think", "PronunciationAssessment": {"AccuracyScore": 45, "ErrorType": "Mispronunciation"},
                       "Phonemes": [{"Phoneme": "θ", "PronunciationAssessment": {"AccuracyScore": 10}}, {"Phoneme": "ɪ", "PronunciationAssessment": {"AccuracyScore": 90}}]}]}]}
    r = parse_assessment(body)
    assert r["pronunciation_score"] == 72.5 and r["words"][0]["phonemes"][0] == {"phoneme": "θ", "accuracy": 10}
    old = {"RecognitionStatus": "Success", "NBest": [{"PronScore": 50, "AccuracyScore": 40, "Words": []}]}
    assert parse_assessment(old)["accuracy"] == 40
    wav = b"RIFF" + b"\x00" * 100
    resp = client.post("/api/pronunciation/assess", data={"target": "think"}, files={"audio": ("a.wav", wav, "audio/wav")})
    assert resp.status_code == 412
    assert client.post("/api/pronunciation/assess", data={"target": "x"}, files={"audio": ("a.webm", b"xx", "audio/webm")}).status_code == 400


def test_line_audio(client, profile, llm):
    r = client.get("/api/listening/line", params={"text": "Hello there.", "voice": "nova"})
    assert r.status_code == 200 and r.content.startswith(b"ID3")
    assert client.get("/api/listening/line", params={"text": "x", "voice": "robot"}).status_code == 400
