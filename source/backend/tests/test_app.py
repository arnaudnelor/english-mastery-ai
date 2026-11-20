from datetime import datetime, timedelta

from app import content
from app.models import VocabCard
from app.providers.llm import parse_json_block
from app.providers.speech import Transcript, Word, fluency_metrics
from app.services import srs


# ---------- content integrity ----------
def test_curriculum_is_well_formed():
    topics = content.all_lessons()
    assert len(topics) >= 60
    ids = set()
    for t in topics:
        assert t["level"] in {"A1", "A2", "B1", "B2", "C1", "C2"}
        assert t["explanation"] and t["examples"] and len(t["exercises"]) >= 3
        for e in t["exercises"]:
            assert e["id"] not in ids
            ids.add(e["id"])
            if e["type"] == "mcq":
                assert e["answer"] in e["options"]
    words = content.vocabulary()
    assert len(words) >= 40
    assert len({w["id"] for w in words}) == len(words)


def test_answer_normalisation():
    ex = {"answer": ["I've known him since we were at university."]}
    assert content.check_answer(ex, "  i’ve known him since we were at university ")
    assert not content.check_answer(ex, "I know him since we were at university.")


# ---------- spaced repetition ----------
def test_sm2_schedule_and_lapse():
    c = VocabCard(profile_id=1, word_id="x", ease=2.5, interval_days=0, repetitions=0, lapses=0)
    t0 = datetime(2026, 1, 1)
    srs.review(c, 2, t0)
    assert c.interval_days == 1
    srs.review(c, 2, t0)
    assert c.interval_days == 6
    srs.review(c, 2, t0)
    assert c.interval_days == 15
    srs.review(c, 0, t0)
    assert c.repetitions == 0 and c.lapses == 1
    assert c.due_at - t0 == timedelta(minutes=10)
    assert c.ease >= srs.MIN_EASE


# ---------- speech metrics ----------
def test_fluency_metrics():
    t = Transcript("um I think", [Word("um", 0, 0.3), Word("I", 1.5, 1.6), Word("think", 1.6, 2.0)], 2.0)
    m = fluency_metrics(t)
    assert m["filler_words"] == 1
    assert m["long_pauses"] == 1
    assert m["words_per_minute"] == 90.0


def test_parse_json_block_tolerates_fences():
    assert parse_json_block('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}


# ---------- API ----------
def test_profile_and_dashboard(client, profile):
    r = client.get("/api/profile/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert d["estimated_cefr"] == "B2"
    assert sum(x["minutes"] for x in d["daily_plan"]) >= 50
    assert d["daily_plan"][0]["skill"] == "speaking"


def test_requires_profile(client):
    assert client.get("/api/profile/dashboard").status_code == 409


def test_profile_validation(client):
    assert client.put("/api/profile", json={"name": "", "target_level": "Z9"}).status_code == 422


def test_grammar_flow_hides_answers_and_records_mistakes(client, profile):
    topic = client.get("/api/grammar/topics/conditionals-mixed").json()
    assert "answer" not in topic["exercises"][0]
    ok = client.post("/api/grammar/topics/conditionals-mixed/answer", json={"exercise_id": "c1", "answer": "had known"}).json()
    assert ok["correct"]
    bad = client.post("/api/grammar/topics/conditionals-mixed/answer", json={"exercise_id": "c1", "answer": "would know"}).json()
    assert not bad["correct"] and bad["explanation"]
    dash = client.get("/api/profile/dashboard").json()
    assert dash["skills"]["grammar"] == 0.5
    assert dash["weaknesses"][0]["category"] == "grammar"


def test_vocab_deck_and_review(client, profile):
    assert client.post("/api/vocabulary/deck/mitigate").json()["ok"]
    assert client.post("/api/vocabulary/deck/nope").status_code == 404
    due = client.get("/api/vocabulary/review").json()
    assert due[0]["word"]["word"] == "mitigate"
    r = client.post(f"/api/vocabulary/review/{due[0]['card_id']}", json={"grade": 2}).json()
    assert r["interval_days"] == 1
    assert client.get("/api/vocabulary/review").json() == []
    assert client.post("/api/vocabulary/deck-all").json()["added"] == len(content.vocabulary()) - 1


def test_conversation_text_turn_with_correction(client, profile, llm):
    s = client.post("/api/conversation/start", json={"mode": "business"}).json()
    assert s["opener"]
    r = client.post(f"/api/conversation/{s['conversation_id']}/turn", json={"text": "I am agree with this decision."})
    assert r.status_code == 200, r.text
    body = r.json()
    fb = body["feedback"]
    assert fb["corrected_sentence"] == "I agree with this decision."
    assert fb["issues"][0]["category"] == "grammar"
    assert fb["advanced_alternative"] == "I fully support this decision."
    assert body["reply"]
    # teacher prompt includes mode & accent
    teacher_sys = llm.calls[-1][0].content
    assert "Business English" in teacher_sys and "Canadian" in teacher_sys
    # mistake tracked
    w = client.get("/api/profile/dashboard").json()["weaknesses"]
    assert w[0]["pattern"].startswith("be + lexical verb")


def test_end_of_conversation_mode_defers_feedback(client, profile, llm):
    s = client.post("/api/conversation/start", json={"mode": "ielts", "correction_mode": "end_of_conversation"}).json()
    r = client.post(f"/api/conversation/{s['conversation_id']}/turn", json={"text": "I am agree"}).json()
    assert r["feedback"] is None and r["feedback_deferred"]
    summary = client.post(f"/api/conversation/{s['conversation_id']}/end").json()
    assert summary["estimated_cefr"] == "B2"
    assert summary["corrections"] and "disclaimer" in summary


def test_voice_turn_uses_stt_and_metrics(client, profile, llm):
    s = client.post("/api/conversation/start", json={"mode": "free"}).json()
    r = client.post(f"/api/conversation/{s['conversation_id']}/voice-turn",
                    files={"audio": ("a.webm", b"\x1aE\xdf\xa3fake", "audio/webm")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["transcript"].startswith("Um I am agree")
    assert b["speech_metrics"]["filler_words"] == 1
    assert b["speech_metrics"]["long_pauses"] == 1
    assert b["feedback"]["issues"]


def test_missing_key_gives_clear_error(client, profile, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import app.providers.llm as L
    monkeypatch.setattr(L, "get_secret", lambda n: None)
    s = client.post("/api/conversation/start", json={"mode": "free"}).json()
    r = client.post(f"/api/conversation/{s['conversation_id']}/turn", json={"text": "hello"})
    assert r.status_code == 412
    assert "API key" in r.json()["detail"]


def test_tts(client, llm):
    r = client.post("/api/conversation/tts", json={"text": "Hello"}).json()
    assert r["mime"] == "audio/mpeg" and r["audio_base64"]


def test_writing_evaluation(client, profile, llm):
    r = client.post("/api/writing/evaluate", json={"genre": "ielts_task2", "text": "Many peoples think that technology is very very good for society."})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["issues"][0]["corrected"] == "people"
    assert "disclaimer" in b


def test_feature_registry_is_honest(client):
    f = client.get("/api/system/features").json()
    assert all(("needs" in x) or x["status"] == "planned" for x in f)
    assert all(x["status"] in {"available", "planned"} for x in f)


def test_selftest_reports_each_dependency(client, llm):
    r = client.post("/api/system/selftest").json()["results"]
    by = {x["name"]: x for x in r}
    assert by["App & database"]["status"] == "ok"
    assert by["AI professor (conversation, corrections, marking)"]["status"] == "fail"  # fake LLM returns prose for a ping
    assert by["Correction engine"]["status"] == "ok"
    assert by["Natural AI voices (optional, OpenAI)"]["status"] == "skipped"  # optional without an OpenAI key
    assert by["Azure phoneme scoring (optional)"]["status"] == "skipped"
