import json
import os
import tempfile

import pytest

os.environ["EMA_DATA_DIR"] = tempfile.mkdtemp(prefix="ema-test-")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.llm import LLMProvider, set_llm_override  # noqa: E402
from app.providers.speech import (  # noqa: E402
    STTProvider,
    Transcript,
    TTSProvider,
    Word,
    set_speech_overrides,
)


class FakeLLM(LLMProvider):
    """Test double. Records prompts; returns JSON for analysis calls, text otherwise.

    Used ONLY in automated tests — the application itself always calls a real provider.
    """

    name = "fake"

    def __init__(self):
        self.calls = []

    def chat(self, messages, *, temperature=0.7, max_tokens=800):
        self.calls.append(messages)
        sys = messages[0].content
        if "Return strict JSON" in sys and "Learner utterance" in messages[-1].content:
            utt = messages[-1].content
            if "am agree" in utt:
                return "```json\n" + json.dumps({
                    "corrected_sentence": "I agree with this decision.",
                    "is_correct": False,
                    "issues": [{"category": "grammar", "original": "I am agree", "corrected": "I agree",
                                "explanation": "'Agree' is a verb, so it does not need 'am'.",
                                "pattern": "be + lexical verb (*am agree)"}],
                    "advanced_alternative": "I fully support this decision.",
                    "repeat_prompt": "Say: 'I agree with this decision.'",
                    "fluency_note": None, "score": 0.6}) + "\n```"
            return json.dumps({"corrected_sentence": "ok", "is_correct": True, "issues": [], "score": 0.95})
        if "examiner" in sys and "estimated_cefr" in sys:
            return json.dumps({"strengths": ["clear ideas"], "recurring_issues": ["be + verb"],
                               "vocabulary_to_learn": [], "estimated_cefr": "B2",
                               "practice_band_estimate": None, "next_steps": ["practise verb patterns"]})
        if "writing tutor" in sys:
            return json.dumps({"improved_text": "Improved.", "issues": [{"category": "grammar", "original": "peoples",
                               "corrected": "people", "explanation": "Plural already.", "pattern": "*peoples"}],
                               "repeated_words": ["very"], "scores": {"task_achievement": 0.7, "coherence_cohesion": 0.7,
                               "lexical_resource": 0.6, "grammar_accuracy": 0.6}, "overall": 0.65,
                               "practice_band_estimate": 6.5, "advanced_expressions": [], "next_exercise": "x"})
        if "writing rater" in sys or "writing examiner. Score each task" in sys:
            return json.dumps({"tasks": {"email": {"score": 4}, "discussion": {"score": 3}, "essay": {"score": 3.5}}, "improvements": []})
        if "speaking rater" in sys or "speaking examiner (criteria" in sys:
            return json.dumps({"score": 4, "criteria": {}, "feedback": "f", "strengths": [], "improvements": []})
        if "CEFR-certified assessor" in sys:
            return json.dumps({"level": "C1", "justification": "j", "strengths": [], "priorities": []})
        if "IELTS Academic writing examiner" in sys:
            return json.dumps({"task1": {"band": 6.0, "key_errors": [{"original": "a", "corrected": "b", "explanation": "c"}]},
                               "task2": {"band": 7.0, "key_errors": []}, "improvements": ["x"]})
        if "IELTS speaking examiner" in sys:
            return json.dumps({"fluency_coherence": 6.5, "lexical_resource": 6, "grammatical_range_accuracy": 6,
                               "pronunciation": 6.5, "band": 6.4, "feedback": "f", "strengths": [], "improvements": [], "better_answers": []})
        if "study pack from a video transcript" in sys:
            return json.dumps({"summary": "s", "vocabulary": [{"word": "pivot", "meaning": "m", "example": "e", "french": None}],
                               "idioms": [], "grammar": [], "questions": [{"prompt": "p", "options": ["a", "b", "c", "d"], "answer": "a", "explanation": "x"},
                               {"prompt": "bad", "options": ["a", "b"], "answer": "z", "explanation": "x"}], "pronunciation_focus": [], "summary_task": "t"})
        if "lexicographer" in sys:
            return json.dumps({"word": "seductive", "ipa": "/sɪˈdʌktɪv/", "part_of_speech": "adjective",
                               "meaning_in_context": "attractive but possibly misleading", "other_common_meaning": None,
                               "example": "A seductive offer.", "french": "séduisant"})
        if "assess a learner's summary" in sys:
            return json.dumps({"content_score": 0.8, "language_score": 0.6, "captured_main_idea": True, "missing_points": [],
                               "inaccuracies": [], "copied_phrases": [], "corrections": [{"original": "peoples",
                               "corrected": "people", "explanation": "x", "category": "grammar"}], "model_summary": "m", "comment": "c"})
        return "That's a really interesting point. Why do you feel that way?"


class FakeSTT(STTProvider):
    next_text = None

    def transcribe(self, audio, filename, language="en"):
        if self.next_text:
            txt, self.next_text = self.next_text, None
            return Transcript(txt, [Word(w, i * 0.4, i * 0.4 + 0.3) for i, w in enumerate(txt.split())], len(txt.split()) * 0.4)
        return Transcript(
            text="Um I am agree with this decision",
            words=[Word("Um", 0.0, 0.3), Word("I", 1.4, 1.5), Word("am", 1.5, 1.7), Word("agree", 1.7, 2.1),
                   Word("with", 2.1, 2.3), Word("this", 2.3, 2.5), Word("decision", 2.5, 3.0)],
            duration=3.0,
        )


class FakeTTS(TTSProvider):
    def synthesize(self, text, voice=None):
        return b"ID3fake", "audio/mpeg"


@pytest.fixture()
def llm():
    f = FakeLLM()
    set_llm_override(f)
    set_speech_overrides(FakeSTT(), FakeTTS())
    yield f
    set_llm_override(None)
    set_speech_overrides(None, None)


@pytest.fixture()
def client(tmp_path):
    init_engine(f"sqlite:///{tmp_path / 't.db'}")
    app = create_app()
    with TestClient(app) as c:
        init_engine(f"sqlite:///{tmp_path / 't.db'}")
        yield c


@pytest.fixture()
def profile(client):
    r = client.put("/api/profile", json={"name": "Amélie", "target_level": "C1"})
    assert r.status_code == 200
    return r.json()


@pytest.fixture()
def server(tmp_path, monkeypatch):
    """The hosted academy (accounts, admin portal). Uses Postgres when EMA_TEST_PG is set, else SQLite."""
    from app.config import settings
    from app.services.security import limiter

    monkeypatch.setattr(settings, "mode", "server")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-0123456789")
    monkeypatch.setattr(settings, "admin_setup_code", "SETUP-CODE-1234")
    monkeypatch.setattr(settings, "public_app_url", "https://academy.example/app/")
    limiter.reset()
    url = os.environ.get("EMA_TEST_PG")
    from app import db as _db

    if _db._engine is not None:
        _db._engine.dispose()
    if url:
        import sqlalchemy as sa

        eng = sa.create_engine(url.replace("postgresql://", "postgresql+psycopg://"))
        with eng.begin() as c:
            c.execute(sa.text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()"))
            c.execute(sa.text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        eng.dispose()
    else:
        url = f"sqlite:///{tmp_path / 's.db'}"
    init_engine(url)
    from app import content

    app = create_app()
    with TestClient(app) as c:
        init_engine(url)
        yield c
    content.set_overlay({}, {})
    from app import config

    config._server_secret_lookup = None


REG = {"password": "Str0ng-passw0rd!", "password_confirm": "Str0ng-passw0rd!", "country": "Canada",
       "preferred_language": "fr", "objectives": ["Business English"], "accept_privacy": True}


def register(c, email, first="Ana", last="Roy"):
    r = c.post("/api/auth/register", json=REG | {"email": email, "first_name": first, "last_name": last})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(server):
    r = server.post("/api/auth/setup-admin", json=REG | {"email": "boss@academy.example", "first_name": "Arnaud", "last_name": "Admin",
                                                          "setup_code": "SETUP-CODE-1234"})
    assert r.status_code == 200, r.text
    return r.json()["token"]
