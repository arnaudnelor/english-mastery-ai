"""Free configuration: Gemini (free tier) + the browser's own speech recognition."""
import json

import app.providers.llm as L
import app.providers.speech as S
from app.providers.llm import ChatMessage, GeminiProvider


class FakeResp:
    def __init__(self, payload, status=200):
        self.status_code, self._p = status, payload
        self.text = json.dumps(payload)

    def json(self):
        return self._p


def test_gemini_request_shape(monkeypatch):
    seen = {}

    def fake_post(url, params=None, json=None, timeout=None, **_):
        seen.update(url=url, params=params, body=json)
        return FakeResp({"candidates": [{"content": {"parts": [{"text": '{"ok": '}, {"text": "true}"}]}}]})

    monkeypatch.setattr(L.httpx, "post", fake_post)
    g = GeminiProvider("gemini-2.5-flash", api_key="AIza-test")
    out = g.chat_json([ChatMessage("system", "Be JSON"), ChatMessage("assistant", "Hi!"), ChatMessage("user", "a"), ChatMessage("user", "b")])
    assert out == {"ok": True}
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent") and seen["params"] == {"key": "AIza-test"}
    b = seen["body"]
    assert b["systemInstruction"]["parts"][0]["text"] == "Be JSON"
    assert [c["role"] for c in b["contents"]] == ["user", "model", "user"]  # starts with user, alternates
    assert len(b["contents"][2]["parts"]) == 2  # consecutive user turns merged
    assert b["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_errors(monkeypatch):
    monkeypatch.setattr(L.httpx, "post", lambda *a, **k: FakeResp({"error": {"message": "API key not valid"}}, 400))
    g = GeminiProvider("gemini-2.5-flash", api_key="bad")
    try:
        g.chat([ChatMessage("user", "hi")])
        raise AssertionError("expected ProviderError")
    except L.ProviderError as e:
        assert "400" in str(e)


def test_get_llm_falls_back_to_provider_with_key(monkeypatch):
    monkeypatch.setattr(L.settings, "llm_provider", "openai")
    monkeypatch.setattr(L, "get_secret", lambda n: "AIza-x" if n == "gemini" else None)
    assert L.get_llm().name == "gemini"
    monkeypatch.setattr(L, "get_secret", lambda n: None)
    try:
        L.get_llm()
        raise AssertionError
    except L.MissingAPIKey as e:
        assert "gemini" in str(e)


def test_browser_transcript_path(monkeypatch):
    monkeypatch.setattr(S, "_stt_override", None)
    monkeypatch.setattr(S, "get_secret", lambda n: None)
    t = S.transcribe_any(b"", "x.webm", "I am agree with this", 2.0)
    m = S.fluency_metrics(t)
    assert t.text == "I am agree with this" and m["words_per_minute"] == 150.0 and m["pauses_measured"] is False
    try:
        S.transcribe_any(b"audio", "x.webm", "", 0)
        raise AssertionError
    except L.MissingAPIKey:
        pass


def test_free_voice_turn_and_memory(client, profile, llm, monkeypatch):
    monkeypatch.setattr(S, "_stt_override", None)
    monkeypatch.setattr(S, "get_secret", lambda n: None)
    s = client.post("/api/conversation/start", json={"mode": "free"}).json()
    r = client.post(f"/api/conversation/{s['conversation_id']}/voice-turn", data={"transcript": "I am agree with this decision", "duration": "2.4"},
                    files={"audio": ("a.webm", b"", "audio/webm")})
    assert r.status_code == 200, r.text
    assert r.json()["speech_metrics"]["words_per_minute"] == 150.0
    # second turn: the professor's system prompt now remembers the recurring mistake
    client.post(f"/api/conversation/{s['conversation_id']}/turn", json={"text": "Yes", "speech": {"duration_sec": 0.5}})
    teacher_prompt = llm.calls[-1][0].content
    assert "Recurring mistakes" in teacher_prompt and "be + lexical verb" in teacher_prompt
    conv = client.get(f"/api/conversation/{s['conversation_id']}").json()
    assert conv["messages"][1]["content"].startswith("I am agree") and conv["messages"][1]["feedback"]
    hist = client.get("/api/conversation/history").json()
    assert hist[0]["turns"] == 2


def test_read_aloud_with_browser_transcript(client, profile, monkeypatch):
    monkeypatch.setattr(S, "_stt_override", None)
    monkeypatch.setattr(S, "get_secret", lambda n: None)
    r = client.post("/api/pronunciation/read-aloud", data={"target": "I think so.", "transcript": "I sink so", "duration": "1.2"},
                    files={"audio": ("a.webm", b"", "audio/webm")}).json()
    assert r["words"][1]["status"] == "wrong" and r["heard"] == "I sink so"
