import sqlite3

from app import content
from app.routers.assess import grammar_level, median_level


def test_level_helpers():
    assert grammar_level({"B1": (6, 6), "B2": (5, 6), "C1": (3, 6), "C2": (6, 6)}) == "B2"
    assert grammar_level({"B1": (2, 6), "B2": (0, 6), "C1": (0, 6), "C2": (0, 6)}) == "A2"
    assert median_level(["C1", "B2", "C2", "B2"]) == "B2"


def test_placement_flow(client, profile, llm):
    t = client.get("/api/assess/placement").json()
    assert len(t["grammar_vocab"]) == 24 and "answer" not in t["grammar_vocab"][0]
    pl = content.placement()
    answers = {q["id"]: q["answer"] for q in pl["grammar_vocab"] if q["level"] in ("B1", "B2", "C1")}
    for q in content.by_id(content.reading_texts(), "four-day-week")["questions"]:
        answers[f"four-day-week:{q['id']}"] = q["answer"]
    r = client.post("/api/assess/placement/submit", json={"answers": answers, "writing": "word " * 60, "speaking_level": "C1"}).json()
    assert r["skills"]["grammar_vocabulary"] == "C1" and r["skills"]["reading"] == "C2" and r["skills"]["listening"] == "B1"
    assert r["skills"]["writing"] == "C1" and r["overall"] == "C1"
    prof = client.get("/api/profile").json()
    assert prof["estimated_level"] == "C1" and prof["placement_done"]
    sp = client.post("/api/assess/placement/speaking", files={"audio": ("a.webm", b"x", "audio/webm")}).json()
    assert sp["level"] == "C1" and sp["transcript"]


def test_weekly_check(client, profile):
    w = client.get("/api/assess/weekly").json()["items"]
    assert len(w) == 12  # 8 grammar + 4 vocabulary (level-based words before a deck exists)
    assert client.post("/api/vocabulary/deck/mitigate").status_code == 200
    w = client.get("/api/assess/weekly").json()["items"]
    v = [x for x in w if x["kind"] == "vocabulary"]
    assert v and "mitigate" in v[0]["options"]
    r = client.post("/api/assess/weekly/submit", json={"answers": {v[0]["key"]: "mitigate", w[0]["key"]: "nonsense"}}).json()
    assert r["score"] == 0.5


def test_path_analytics_search_bookmarks(client, profile):
    client.post("/api/grammar/topics/articles/answer", json={"exercise_id": "ar1", "answer": "(no article)"})
    path = client.get("/api/path").json()
    assert path["total"] > 10 and path["weeks"][0]["units"][-1]["kind"] == "speaking"
    assert any(u["id"] == "articles" and u["done"] for w in path["weeks"] for u in w["units"])
    a = client.get("/api/analytics").json()
    assert len(a["minutes_per_week"]) == 12 and a["totals"]["activities"] >= 1 and a["history"][0]["skill"] == "grammar"
    hits = client.get("/api/search", params={"q": "inversion"}).json()
    assert any(h["kind"] == "Grammar" for h in hits)
    assert any(h["kind"] == "Vocabulary" for h in client.get("/api/search", params={"q": "atténuer"}).json())
    b = client.post("/api/bookmarks", json={"kind": "grammar", "item_id": "articles", "title": "Articles", "route": "/grammar/articles"}).json()
    assert client.post("/api/bookmarks", json={"kind": "grammar", "item_id": "articles", "title": "Articles", "route": "/grammar/articles"}).json()["id"] == b["id"]
    assert client.get("/api/bookmarks").json()[0]["route"] == "/grammar/articles"
    assert client.post("/api/bookmarks", json={"kind": "x", "item_id": "y", "title": "t", "route": "javascript:alert(1)"}).status_code == 422
    assert client.delete(f"/api/bookmarks/{b['id']}").json()["deleted"]


def test_migration_adds_columns(tmp_path):
    """A v0.2 database (without the new columns) is upgraded in place."""
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE profiles (id INTEGER PRIMARY KEY, name VARCHAR(80), native_language VARCHAR(10), target_level VARCHAR(4), "
                "estimated_level VARCHAR(4), daily_minutes INTEGER, accent_preference VARCHAR(10), correction_mode VARCHAR(20), "
                "french_explanations INTEGER, created_at DATETIME)")
    con.execute("INSERT INTO profiles (name, target_level, estimated_level, daily_minutes, accent_preference, correction_mode, french_explanations) "
                "VALUES ('Old', 'C1', 'B2', 60, 'en-CA', 'after_response', 1)")
    con.execute("CREATE TABLE bookmarks (id INTEGER PRIMARY KEY, profile_id INTEGER, kind VARCHAR(20), item_id VARCHAR(80), created_at DATETIME)")
    con.commit()
    con.close()
    from app.db import init_engine
    init_engine(f"sqlite:///{db}")
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(profiles)")}
    assert {"reminder_time", "placement_done_at"} <= cols
    assert "route" in {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(bookmarks)")}


def test_mistakes_review(client, profile):
    client.post("/api/grammar/topics/articles/answer", json={"exercise_id": "ar1", "answer": "The"})
    m = client.get("/api/mistakes").json()
    assert m[0]["category"] == "grammar" and m[0]["source"] == "grammar_exercise" and m[0]["corrected"]
