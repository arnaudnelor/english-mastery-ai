from app.services.subtitles import parse

SRT = """1
00:00:01,000 --> 00:00:03,500
Welcome to the <i>lesson</i>.

2
00:00:03,600 --> 00:00:06,000
Today we talk about
interest rates.
"""

VTT = """WEBVTT

00:01.000 --> 00:02.000 align:start
<c.yellow>Hello</c> there

00:02.000 --> 00:03.000
Hello there
"""


def test_parse_srt_vtt_plain():
    c = parse(SRT)
    assert c == [{"start": 1.0, "end": 3.5, "text": "Welcome to the lesson."},
                 {"start": 3.6, "end": 6.0, "text": "Today we talk about interest rates."}]
    v = parse(VTT)
    assert v == [{"start": 1.0, "end": 3.0, "text": "Hello there"}]
    plain = parse("First sentence. Second one? Third!")
    assert [x["text"] for x in plain] == ["First sentence.", "Second one?", "Third!"] and plain[0]["start"] is None


def test_video_library_flow(client, profile, llm):
    r = client.post("/api/video/items", data={"title": "Rates explained", "level": "C1"},
                    files={"video": ("clip.mp4", b"\x00" * 5000, "video/mp4"), "subtitles_file": ("clip.srt", SRT.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    assert r.json()["timed"] and len(r.json()["cues"]) == 2
    f = client.get(f"/api/video/items/{vid}/file", headers={"Range": "bytes=0-99"})
    assert f.status_code == 206 and len(f.content) == 100
    s = client.post(f"/api/video/items/{vid}/study").json()
    assert s["vocabulary"][0]["word"] == "pivot" and len(s["questions"]) == 1  # invalid question dropped
    assert client.get(f"/api/video/items/{vid}").json()["has_study"]
    assert client.post(f"/api/video/items/{vid}/progress", json={"seconds": 120, "score": 0.8}).json()["ok"]
    assert client.delete(f"/api/video/items/{vid}").json()["deleted"]


def test_youtube_and_validation(client, profile):
    r = client.post("/api/video/items", data={"title": "Talk", "youtube_url": "https://www.youtube.com/watch?v=abcdefghijk&t=3", "transcript": "One. Two."})
    assert r.json()["youtube_id"] == "abcdefghijk" and not r.json()["timed"]
    assert client.post("/api/video/items", data={"title": "x", "youtube_url": "https://vimeo.com/1"}).status_code == 422
    assert client.post("/api/video/items", data={"title": "x"}, files={"video": ("a.avi", b"x", "video/avi")}).status_code == 415
    s = client.post("/api/video/items", data={"title": "y", "youtube_url": "youtu.be/abcdefghijk"}).json()
    assert client.post(f"/api/video/items/{s['id']}/study").status_code == 409
