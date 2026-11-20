"""The CEFR academy, Business English Academy, placement routing and level tests."""
from app import content
from app.routers.academy import LEVELS


def _refs(items):
    return [(it["kind"], it["ref"]) for it in items if it["kind"] != "soon"]


def test_curriculum_refs_resolve_and_never_repeat():
    cur = content.curriculum()
    assert [lv["code"] for lv in cur["levels"]] == LEVELS
    seen = set()
    for lv in cur["levels"]:
        for u in lv["units"]:
            for kind, ref in _refs(u["items"]):
                if kind == "lesson":
                    t = content.find_topic(ref)
                    assert t, ref
                    assert t["level"] == lv["code"], (ref, t["level"], lv["code"])
                if kind == "reading":
                    assert content.by_id(content.reading_texts(), ref)["level"] == lv["code"], ref
                if kind == "listening":
                    assert content.by_id(content.listening_items(), ref)["level"] == lv["code"], ref
                if kind in ("lesson", "reading", "listening", "writing"):
                    assert (kind, ref) not in seen, f"{ref} appears twice"
                    seen.add((kind, ref))
    assert len(cur["business"]) == 18
    for c in cur["business"]:
        kinds = {it["kind"] for it in c["items"]}
        assert "lesson" in kinds and "conversation" in kinds, c["id"]
        for kind, ref in _refs(c["items"]):
            if kind in ("lesson", "reading", "listening", "writing"):
                assert (kind, ref) not in seen, f"{ref} reused"
                seen.add((kind, ref))
                if kind == "lesson":
                    assert content.find_topic(ref)["unit"] == "Business English"
    # every lesson and every business lesson is placed exactly once
    placed = {r for k, r in seen if k == "lesson"}
    assert placed == {t["id"] for t in content.all_lessons()}


def test_conversation_modes_exist_for_every_curriculum_item(client, profile):
    modes = {m["id"] for m in client.get("/api/conversation/modes").json()["modes"]}
    cur = content.curriculum()
    used = {it["ref"] for lv in cur["levels"] for u in lv["units"] for it in u["items"] if it["kind"] == "conversation"}
    used |= {it["ref"] for c in cur["business"] for it in c["items"] if it["kind"] == "conversation"}
    assert used <= modes, used - modes


def test_unplaced_learner_sees_a1_only_then_chooses(client, profile):
    client.put("/api/profile", json={"name": "Test"})
    o = client.get("/api/academy/overview").json()
    assert o["level_confirmed"] is False
    assert [lv["status"] for lv in o["levels"]] == ["available"] + ["locked"] * 5
    assert client.get("/api/academy/level/B2/test").status_code == 403
    client.post("/api/academy/choose-level", json={"level": "B1"})
    o = client.get("/api/academy/overview").json()
    assert [lv["status"] for lv in o["levels"]] == ["completed", "completed", "current", "locked", "locked", "locked"]
    assert o["current_level_name"] == "Intermediate"
    assert all(lv["lesson_count"] > 0 for lv in o["levels"])
    assert o["business"]["categories"] == 18


def test_lesson_progress_and_level_test_promotion(client, profile):
    client.post("/api/academy/choose-level", json={"level": "A1"})
    t = content.find_topic("a1-to-be")
    for e in t["exercises"]:
        ans = e["answer"] if isinstance(e["answer"], str) else e["answer"][0]
        assert client.post("/api/grammar/topics/a1-to-be/answer", json={"exercise_id": e["id"], "answer": ans}).json()["correct"]
    lv = client.get("/api/academy/level/A1").json()
    item = next(i for u in lv["units"] for i in u["items"] if i["ref"] == "a1-to-be")
    assert item["done"] and item["score"] == 1.0 and item["route"] == "/lesson/a1-to-be"
    assert lv["percent"] > 0

    test = client.get("/api/academy/level/A1/test").json()
    assert len(test["items"]) == 20
    # wrong answers: no promotion
    r = client.post("/api/academy/level/A1/test", json={"answers": {i["key"]: "zzz" for i in test["items"]}}).json()
    assert not r["passed"] and r["promoted_to"] is None and r["weak_topics"]
    # correct answers: promoted to A2
    answers = {}
    for i in test["items"]:
        kind, *rest = i["key"].split(":")
        if kind == "g":
            e = next(x for x in content.find_topic(rest[0])["exercises"] if x["id"] == rest[1])
            answers[i["key"]] = e["answer"] if isinstance(e["answer"], str) else e["answer"][0]
        else:
            answers[i["key"]] = content.find_word(rest[0])["word"]
    r = client.post("/api/academy/level/A1/test", json={"answers": answers}).json()
    assert r["passed"] and r["promoted_to"] == "A2"
    assert client.get("/api/profile").json()["estimated_level"] == "A2"
    hist = client.get("/api/academy/assessments").json()
    assert [h["passed"] for h in hist] == [True, False]


def test_business_lessons_and_test(client, profile):
    b = client.get("/api/academy/business").json()
    assert len(b["categories"]) == 18
    first = b["categories"][0]["items"][0]
    assert first["route"].startswith("/lesson/biz-")
    assert client.get(first["route"].replace("/lesson/", "/api/grammar/topics/")).status_code == 200
    t = client.get("/api/academy/business/test").json()
    assert len(t["items"]) == 24
    r = client.post("/api/academy/business/test", json={"answers": {i["key"]: "x" for i in t["items"]}}).json()
    assert r["passed"] is False


def test_placement_can_place_a_beginner(client, profile):
    pl = client.get("/api/assess/placement").json()
    assert any(q.get("skill") == "construction" for q in pl["grammar_vocab"])
    answers = {q["id"]: "" for q in pl["grammar_vocab"]}
    for q in content.placement()["grammar_vocab"]:
        if q["level"] == "A1":
            answers[q["id"]] = q["answer"]
    r = client.post("/api/assess/placement/submit", json={"answers": answers}).json()
    assert r["overall"] in ("A1", "A2") and r["overall_name"]
    o = client.get("/api/academy/overview").json()
    assert o["level_confirmed"] and o["current_level"] == r["overall"]
    assert o["placement"]["last"]["level"] == r["overall"]


def test_writing_lesson_completion(client, profile, llm):
    r = client.post("/api/writing/evaluate", json={"genre": "short_text", "text": "My name is Paul and I live in Lyon with my family.", "lesson_id": "a1-about-me"})
    assert r.status_code == 200
    client.post("/api/academy/choose-level", json={"level": "A1"})
    lv = client.get("/api/academy/level/A1").json()
    w = next(i for u in lv["units"] for i in u["items"] if i["kind"] == "writing")
    assert w["done"] and "lesson=a1-about-me" in w["route"]
