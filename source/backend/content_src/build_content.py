"""Regenerates the academy content files from content_src/. Idempotent: run `python3 content_src/build_content.py`."""
import json, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
OUT = HERE.parent / "app" / "content"
from grammar_lower import TOPICS
from lessons_general import LESSONS as GEN
from lessons_business import LESSONS as BIZ
from vocab_lower import WORDS
from texts_lower import READINGS, LISTENING
from curriculum import CURRICULUM
from placement_extra import EXTRA_ITEMS, LISTENING_FIRST

def load(n): return json.loads((OUT / n).read_text(encoding="utf-8"))
def save(n, d): (OUT / n).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

def prefixed(topics):
    for t in topics:
        for e in t["exercises"]:
            if not e["id"].startswith(t["id"] + "-"):
                e["id"] = f"{t['id']}-{e['id']}"
    return topics

g = load("grammar.json")
new_ids = {t["id"] for t in TOPICS}
topics = [t for t in g["topics"] if t["id"] not in new_ids]
for t in topics:
    if t["id"] in ("present-perfect-vs-past-simple", "conditionals-mixed", "future-forms"):
        t["level"] = "B1"
g["topics"] = prefixed(TOPICS) + topics
save("grammar.json", g)
save("lessons.json", {"lessons": prefixed(GEN), "business": prefixed(BIZ)})

v = load("vocabulary.json")
ids = {w["id"] for w in WORDS}
v["words"] = WORDS + [w for w in v["words"] if w["id"] not in ids]
save("vocabulary.json", v)

r = load("reading.json")
ids = {x["id"] for x in READINGS}
r["texts"] = READINGS + [x for x in r["texts"] if x["id"] not in ids]
for x in r["texts"]:
    if x["id"] == "online-learning-lessons": x["level"] = "B1"
save("reading.json", r)

l = load("listening.json")
ids = {x["id"] for x in LISTENING}
l["items"] = LISTENING + [x for x in l["items"] if x["id"] not in ids]
for x in l["items"]:
    if x["id"] in ("coffee-shop-catchup", "bank-account"): x["level"] = "B1"
save("listening.json", l)

p = load("placement.json")
ids = {q["id"] for q in EXTRA_ITEMS}
p["grammar_vocab"] = EXTRA_ITEMS + [q for q in p["grammar_vocab"] if q["id"] not in ids]
p["listening_items"] = [LISTENING_FIRST] + [i for i in p["listening_items"] if i != LISTENING_FIRST]
save("placement.json", p)
save("curriculum.json", CURRICULUM)
print("ok", len(g["topics"]), len(GEN), len(BIZ), len(v["words"]), len(r["texts"]), len(l["items"]), len(p["grammar_vocab"]))
