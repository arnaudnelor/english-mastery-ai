"""Hosted academy: accounts, isolation, admin portal, content management, progress, privacy, expansion foundations."""
import re

import pytest
from conftest import REG, auth, register

from app import content


# ------------------------------------------------------------------ accounts
def test_everything_needs_sign_in(server):
    assert server.get("/api/profile").status_code == 401
    assert server.get("/api/academy/overview").status_code == 401
    assert server.get("/api/admin/overview").status_code == 401
    cfg = server.get("/api/auth/config").json()
    assert cfg["mode"] == "server" and cfg["setup_available"] and cfg["registration_open"]
    assert server.get("/api/system/health").status_code == 200


def test_register_login_logout_and_v1_alias(server):
    r = register(server, "Ana@Example.com")
    assert r["verification_required"] is False  # no email service configured -> immediate access
    tok = r["token"]
    me = server.get("/api/auth/me", headers=auth(tok)).json()
    assert me["email"] == "ana@example.com" and me["role"] == "learner" and not me["is_admin"] and me["level"] is None
    assert server.get("/api/v1/profile", headers=auth(tok)).json()["name"] == "Ana"
    # duplicate email
    assert server.post("/api/auth/register", json=REG | {"email": "ana@example.com", "first_name": "X", "last_name": "Y"}).status_code == 409
    # weak / mismatched passwords
    assert server.post("/api/auth/register", json=REG | {"email": "b@e.com", "first_name": "B", "last_name": "C", "password": "short1", "password_confirm": "short1"}).status_code == 422
    assert server.post("/api/auth/register", json=REG | {"email": "b@e.com", "first_name": "B", "last_name": "C", "password_confirm": "Different-pass1"}).status_code == 422
    # login / logout
    bad = server.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope-nope-1"})
    assert bad.status_code == 401
    tok2 = server.post("/api/auth/login", json={"email": "ANA@example.com", "password": REG["password"]}).json()["token"]
    server.post("/api/auth/logout", headers=auth(tok2))
    assert server.get("/api/auth/me", headers=auth(tok2)).status_code == 401
    assert server.get("/api/auth/me", headers=auth(tok)).status_code == 200  # other session untouched


def test_lockout_after_failed_logins(server):
    register(server, "lock@example.com")
    for _ in range(8):
        server.post("/api/auth/login", json={"email": "lock@example.com", "password": "wrong-pass-1"})
    r = server.post("/api/auth/login", json={"email": "lock@example.com", "password": REG["password"]})
    assert r.status_code in (423, 429)


def test_email_verification_and_password_reset_with_email_service(server, monkeypatch):
    sent = []
    from app.services import mailer

    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send_email", lambda db, to, subj, text, kind: sent.append((to, text)) or True)
    import app.routers.auth as A

    monkeypatch.setattr(A.mailer, "send_email", lambda db, to, subj, text, kind: sent.append((to, text)) or True)
    r = register(server, "verify@example.com")
    assert r["verification_required"] is True and "token" not in r
    assert server.post("/api/auth/login", json={"email": "verify@example.com", "password": REG["password"]}).status_code == 403
    token = re.search(r"token=([\w-]+)", sent[-1][1]).group(1)
    assert "https://academy.example/app/#/verify-email?token=" in sent[-1][1]
    assert server.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert server.post("/api/auth/verify-email", json={"token": token}).status_code == 400  # single use
    assert server.post("/api/auth/login", json={"email": "verify@example.com", "password": REG["password"]}).status_code == 200
    # forgot password: same answer for unknown emails
    assert server.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).json()["ok"]
    server.post("/api/auth/forgot-password", json={"email": "verify@example.com"})
    rt = re.search(r"token=([\w-]+)", sent[-1][1]).group(1)
    new = "An0ther-long-pass"
    assert server.post("/api/auth/reset-password", json={"token": rt, "password": new, "password_confirm": new}).status_code == 200
    assert server.post("/api/auth/login", json={"email": "verify@example.com", "password": new}).status_code == 200


def test_learners_only_see_their_own_records(server, llm):
    a = register(server, "a@example.com", "Ana")["token"]
    b = register(server, "b@example.com", "Ben")["token"]
    cid = server.post("/api/conversation/start", json={"mode": "free"}, headers=auth(a)).json()["conversation_id"]
    assert server.get(f"/api/conversation/{cid}", headers=auth(a)).status_code == 200
    assert server.get(f"/api/conversation/{cid}", headers=auth(b)).status_code == 404
    server.post("/api/grammar/topics/a1-to-be/answer", json={"exercise_id": "a1-to-be-tb1", "answer": "x"}, headers=auth(a))
    da = server.get("/api/profile/dashboard", headers=auth(a)).json()
    db_ = server.get("/api/profile/dashboard", headers=auth(b)).json()
    assert da["weaknesses"] and not db_["weaknesses"]  # A's grammar mistake is invisible to B
    pa = server.get("/api/profile", headers=auth(a)).json()
    pb = server.get("/api/profile", headers=auth(b)).json()
    assert pa["id"] != pb["id"] and pa["name"] == "Ana" and pb["name"] == "Ben"
    # learners can't set their own level, and can't reach the admin portal or secrets
    server.put("/api/profile", json={"name": "Ana", "estimated_level": "C2"}, headers=auth(a))
    assert server.get("/api/profile", headers=auth(a)).json()["estimated_level"] == "A1"
    assert server.get("/api/admin/overview", headers=auth(a)).status_code == 403
    assert server.post("/api/system/keys", json={"provider": "gemini", "api_key": "AIza-0123456789"}, headers=auth(a)).status_code == 403


def test_progress_autosave_continue_and_study_time(server):
    t = register(server, "p@example.com")["token"]
    h = auth(t)
    server.post("/api/academy/choose-level", json={"level": "A1"}, headers=h)
    assert server.get("/api/academy/continue", headers=h).json()["route"] == "/lesson/a1-alphabet"
    server.post("/api/academy/visit", json={"route": "/lesson/a1-greetings", "title": "Greetings"}, headers=h)
    assert server.get("/api/academy/continue", headers=h).json() == {"route": "/lesson/a1-greetings", "title": "Greetings", "reason": "last_unfinished"}
    for e in content.find_topic("a1-greetings")["exercises"]:
        ans = e["answer"] if isinstance(e["answer"], str) else e["answer"][0]
        server.post("/api/grammar/topics/a1-greetings/answer", json={"exercise_id": e["id"], "answer": ans}, headers=h)
    prog = {r["key"]: r for r in server.get("/api/academy/progress", headers=h).json()}
    assert prog["a1-greetings"]["status"] == "completed" and prog["a1-greetings"]["score"] == 1.0
    assert server.get("/api/academy/continue", headers=h).json()["route"] == "/lesson/a1-alphabet"  # last one is finished
    for _ in range(3):
        server.post("/api/academy/heartbeat", json={"seconds": 60}, headers=h)
    assert server.get("/api/profile/dashboard", headers=h).json()["minutes_week"] == 3
    notes = server.get("/api/auth/notifications", headers=h).json()
    assert any(n["kind"] == "milestone" for n in notes["items"]) and any(n["kind"] == "welcome" for n in notes["items"])
    # progress survives a new session (another device)
    t2 = server.post("/api/auth/login", json={"email": "p@example.com", "password": REG["password"]}).json()["token"]
    assert server.get("/api/academy/level/A1", headers=auth(t2)).json()["done"] >= 1


# ------------------------------------------------------------------ admin portal
def test_admin_setup_is_one_time(server, admin_token):
    me = server.get("/api/auth/me", headers=auth(admin_token)).json()
    assert me["role"] == "super_admin" and me["is_admin"]
    r = server.post("/api/auth/setup-admin", json=REG | {"email": "x@e.com", "first_name": "X", "last_name": "Y", "setup_code": "SETUP-CODE-1234"})
    assert r.status_code == 409
    assert server.get("/api/auth/config").json()["setup_available"] is False


def test_admin_monitoring_and_account_actions(server, admin_token):
    A = auth(admin_token)
    t = register(server, "learner@example.com", "Lea", "Martin")["token"]
    register(server, "other@example.com", "Omar", "Diallo")
    server.post("/api/academy/choose-level", json={"level": "B1"}, headers=auth(t))
    ov = server.get("/api/admin/overview", headers=A).json()
    assert ov["learners"]["total"] == 2 and ov["cefr_distribution"]["B1"] == 1 and ov["cefr_distribution"]["Not placed"] == 1
    lst = server.get("/api/admin/learners", params={"q": "lea"}, headers=A).json()
    assert lst["total"] == 1 and lst["items"][0]["email"] == "learner@example.com"
    assert server.get("/api/admin/learners", params={"level": "B1"}, headers=A).json()["total"] == 1
    uid = lst["items"][0]["user_id"]
    d = server.get(f"/api/admin/learners/{uid}", headers=A).json()
    assert d["level"] == "B1" and d["sessions"] == 1 and len(d["weekly"]) == 12
    # suspend -> signed out and can't sign in
    assert server.post(f"/api/admin/learners/{uid}/status", json={"status": "suspended"}, headers=A).status_code == 200
    assert server.get("/api/profile", headers=auth(t)).status_code == 401
    assert server.post("/api/auth/login", json={"email": "learner@example.com", "password": REG["password"]}).status_code == 403
    server.post(f"/api/admin/learners/{uid}/status", json={"status": "active"}, headers=A)
    # admin reset link works once
    link = server.post(f"/api/admin/learners/{uid}/reset-link", headers=A).json()["link"]
    tok = link.split("token=")[1]
    assert server.post("/api/auth/reset-password", json={"token": tok, "password": "Brand-new-pass9", "password_confirm": "Brand-new-pass9"}).status_code == 200
    assert server.post("/api/auth/login", json={"email": "learner@example.com", "password": "Brand-new-pass9"}).status_code == 200
    # admin can't suspend themselves; audit trail exists
    me = server.get("/api/auth/me", headers=A).json()
    assert server.post(f"/api/admin/learners/{me['id']}/status", json={"status": "suspended"}, headers=A).status_code == 400
    actions = [a["action"] for a in server.get("/api/admin/audit", headers=A).json()]
    assert "learner.suspended" in actions and "learner.reset_link" in actions and "admin.setup" in actions


def test_reports_export_in_three_formats(server, admin_token):
    A = auth(admin_token)
    register(server, "r@example.com")
    for kind in ("learners", "usage_weekly", "usage_monthly", "completion", "cefr", "assessments"):
        j = server.get(f"/api/admin/reports/{kind}", headers=A)
        assert j.status_code == 200, (kind, j.text)
    csv = server.get("/api/admin/reports/learners", params={"format": "csv"}, headers=A)
    assert csv.headers["content-type"].startswith("text/csv") and b"r@example.com" in csv.content
    xlsx = server.get("/api/admin/reports/cefr", params={"format": "xlsx"}, headers=A)
    assert xlsx.content[:2] == b"PK"
    pdf = server.get("/api/admin/reports/completion", params={"format": "pdf", "level": "B1"}, headers=A)
    assert pdf.content[:4] == b"%PDF"
    uid = server.get("/api/admin/learners", headers=A).json()["items"][0]["user_id"]
    assert server.get(f"/api/admin/learners/{uid}/report.pdf", headers=A).content[:4] == b"%PDF"


def test_content_management_lessons_and_curriculum(server, admin_token):
    A = auth(admin_token)
    t = register(server, "c@example.com")["token"]
    lesson = {"title": "Ordering Food", "level": "A2", "unit": "Everyday Communication", "summary": "Restaurant phrases.",
              "explanation": "Use 'I'd like…' and 'Could I have…?' to order politely.", "exercises": [
                  {"id": "of1", "type": "mcq", "prompt": "Choose the polite request:", "options": ["Give me soup.", "I'd like the soup, please."],
                   "answer": "I'd like the soup, please.", "explanation": "Polite."}], "collection": "lessons", "published": False}
    assert server.put("/api/admin/content/lessons/a2-ordering-food", json=lesson, headers=A).status_code == 200
    assert server.get("/api/grammar/topics/a2-ordering-food", headers=auth(t)).status_code == 404  # unpublished
    server.post("/api/admin/content/lessons/a2-ordering-food/publish", json={"published": True}, headers=A)
    assert server.get("/api/grammar/topics/a2-ordering-food", headers=auth(t)).json()["title"] == "Ordering Food"
    # add it to the A2 curriculum; mixing levels is refused
    cur = server.get("/api/admin/content/curriculum", headers=A).json()["curriculum"]
    a2 = next(lv for lv in cur["levels"] if lv["code"] == "A2")
    a2["units"].append({"title": "Unit 5 · At the Restaurant", "items": [{"kind": "lesson", "ref": "a2-ordering-food"}]})
    assert server.put("/api/admin/content/curriculum", json=cur, headers=A).status_code == 200
    server.post("/api/academy/choose-level", json={"level": "A2"}, headers=auth(t))
    units = server.get("/api/academy/level/A2", headers=auth(t)).json()["units"]
    assert units[-1]["title"] == "Unit 5 · At the Restaurant"
    a1 = next(lv for lv in cur["levels"] if lv["code"] == "A1")
    for un in a1["units"]:
        un["items"] = [i for i in un["items"] if i["ref"] != "a1-to-be"]
    b1 = next(lv for lv in cur["levels"] if lv["code"] == "B1")
    b1["units"][0]["items"].append({"kind": "lesson", "ref": "a1-to-be"})
    r = server.put("/api/admin/content/curriculum", json=cur, headers=A)
    assert r.status_code == 422 and "never mixed" in r.json()["detail"]
    # unpublish a built-in lesson, then restore it
    server.post("/api/admin/content/lessons/a1-to-be/publish", json={"published": False}, headers=A)
    assert server.get("/api/grammar/topics/a1-to-be", headers=auth(t)).status_code == 404
    server.post("/api/admin/content/lessons/a1-to-be/restore", headers=A)
    assert server.get("/api/grammar/topics/a1-to-be", headers=auth(t)).status_code == 200
    # learners can't manage content
    assert server.put("/api/admin/content/lessons/x-hack", json=lesson, headers=auth(t)).status_code == 403


def test_placement_configuration(server, admin_token):
    A = auth(admin_token)
    cfg = server.get("/api/admin/placement", headers=A).json()
    doc = cfg["document"]
    doc["grammar_vocab"].append({"id": "custom1", "level": "B2", "skill": "vocabulary", "prompt": "A 'deadline' is…",
                                 "options": ["a limit date", "a dead phone"], "answer": "a limit date"})
    body = doc | {"placement_level_threshold": 0.65, "level_test_pass_mark": 0.75}
    assert server.put("/api/admin/placement", json=body, headers=A).status_code == 200
    t = register(server, "pl@example.com")["token"]
    pl = server.get("/api/assess/placement", headers=auth(t)).json()
    assert any(q["id"] == "custom1" for q in pl["grammar_vocab"]) and "answer" not in pl["grammar_vocab"][0]
    r = server.post("/api/assess/placement/submit", json={"answers": {}}, headers=auth(t)).json()
    assert r["overall"] == "A1" and r["weaknesses"] is not None and r["pathway"]
    assert server.get("/api/academy/level/A1", headers=auth(t)).json()["pass_mark"] == 0.75
    bad = body | {"grammar_vocab": [q for q in doc["grammar_vocab"] if q["level"] != "C2"]}
    assert server.put("/api/admin/placement", json=bad, headers=A).status_code == 422


def test_media_upload_and_learner_playback(server, admin_token):
    A = auth(admin_token)
    t = register(server, "m@example.com")["token"]
    fake_mp3 = b"ID3" + b"\x00" * 2048
    r = server.post("/api/admin/media", headers=A, data={"title": "Café dialogue", "kind": "audio", "level": "A1",
                                                         "transcript": "1\n00:00:00,000 --> 00:00:02,000\nHello!\n",
                                                         "questions": '[{"prompt":"What does she say?","options":["Hello","Bye"],"answer":"Hello"}]'},
                    files={"file": ("cafe.mp3", fake_mp3, "audio/mpeg")})
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    m = server.get(f"/api/media/{mid}", headers=auth(t)).json()
    assert m["cues"][0]["text"] == "Hello!" and "answer" not in m["questions"][0]
    f = server.get(f"/api/media/{mid}/file", headers=auth(t) | {"Range": "bytes=0-9"})
    assert f.status_code == 206 and f.content[:3] == b"ID3"
    assert server.post(f"/api/media/{mid}/complete", json={"answers": {"q1": "Hello"}}, headers=auth(t)).json()["score"] == 1.0
    # wrong file type rejected
    assert server.post("/api/admin/media", headers=A, data={"title": "x1", "kind": "document"}, files={"file": ("a.exe", b"MZ", "application/octet-stream")}).status_code == 415


def test_settings_secrets_roles_and_backup(server, admin_token):
    A = auth(admin_token)
    s = server.get("/api/admin/settings", headers=A).json()
    s["registration_open"] = False
    assert server.put("/api/admin/settings", json=s, headers=A).status_code == 200
    assert server.post("/api/auth/register", json=REG | {"email": "late@e.com", "first_name": "L", "last_name": "T"}).status_code == 403
    # secrets are stored encrypted and never returned
    assert server.post("/api/system/keys", json={"provider": "gemini", "api_key": "AIza-SECRET-VALUE-123"}, headers=A).status_code == 200
    st = server.get("/api/admin/status", headers=A).json()
    assert st["ai"]["keys"]["gemini"] is True and "AIza-SECRET" not in str(st)
    from app.config import get_secret
    assert get_secret("gemini") == "AIza-SECRET-VALUE-123"
    from app.db import get_db
    from app.models_platform import PlatformSecret
    db = next(get_db())
    assert "AIza" not in db.get(PlatformSecret, "gemini").ciphertext
    # roles & permissions
    roles = server.get("/api/admin/roles", headers=A).json()
    assert {r["name"] for r in roles["roles"]} >= {"super_admin", "admin", "teacher", "learner"}
    assert server.put("/api/admin/roles/admin", json={"permissions": ["learners.view"]}, headers=A).status_code == 200
    inv = server.post("/api/admin/staff", json={"email": "helper@academy.example", "first_name": "Help", "last_name": "Er", "role": "admin"}, headers=A).json()
    tok = inv["link"].split("token=")[1]
    server.post("/api/auth/reset-password", json={"token": tok, "password": "Assist-pass-123", "password_confirm": "Assist-pass-123"})
    H = auth(server.post("/api/auth/login", json={"email": "helper@academy.example", "password": "Assist-pass-123"}).json()["token"])
    assert server.get("/api/admin/learners", headers=H).status_code == 200
    assert server.get("/api/admin/settings", headers=H).status_code == 403  # permission removed
    b = server.get("/api/admin/backup", headers=A)
    assert b.status_code == 200 and b"password_hash" not in b.content and b"users" in b.content
    assert server.get("/api/admin/backup", headers=H).status_code == 403


def test_privacy_export_and_account_deletion(server, admin_token):
    t = register(server, "gone@example.com")["token"]
    h = auth(t)
    server.post("/api/academy/heartbeat", json={"seconds": 30}, headers=h)
    assert server.get("/api/auth/me/export.json", headers=h).json()["account"]["email"] == "gone@example.com"
    assert server.get("/api/auth/me/report.pdf", headers=h).content[:4] == b"%PDF"
    assert server.post("/api/auth/me/delete", json={"password": "wrong-one-1"}, headers=h).status_code == 400
    assert server.post("/api/auth/me/delete", json={"password": REG["password"]}, headers=h).json()["deleted"]
    assert server.post("/api/auth/login", json={"email": "gone@example.com", "password": REG["password"]}).status_code == 401
    assert server.get("/api/admin/learners", params={"q": "gone"}, headers=auth(admin_token)).json()["total"] == 0


def test_expansion_foundations_relationships(server, admin_token):
    """Teachers, classes, groups, organisations, subscriptions and payments exist in the schema and relate correctly,
    while staying inactive in the product."""
    from datetime import datetime, timedelta

    from app.db import get_db
    from app.models_platform import (Attendance, ClassSession, Classroom, Course, Enrolment, GroupCourse, Invoice, LearnerGroup,
                                     Organization, Payment, Subscription, SubscriptionPlan, TeacherAssignment, TeacherProfile, User)

    register(server, "corp1@bank.example", "Corp", "One")
    db = next(get_db())
    learner = db.query(User).filter_by(email="corp1@bank.example").one()
    org = Organization(name="Banque Exemple", kind="bank", seat_limit=50)
    db.add(org)
    db.flush()
    learner.organization_id = org.id
    teacher_user = User(email="teach@bank.example", password_hash="x", first_name="T", last_name="Ch", role="teacher", organization_id=org.id)
    db.add(teacher_user)
    db.flush()
    tp = TeacherProfile(user_id=teacher_user.id, organization_id=org.id, status="approved")
    course = Course(code="biz-b2", title="Business English B2", track="business", curriculum_ref="business:meetings", organization_id=org.id)
    db.add_all([tp, course])
    db.flush()
    cls = Classroom(organization_id=org.id, name="Finance team B2", level="B2", capacity=12, course_id=course.id)
    db.add(cls)
    db.flush()
    grp = LearnerGroup(organization_id=org.id, name="Corporate group", kind="corporate", class_id=cls.id, supervisor_teacher_id=tp.id)
    db.add(grp)
    db.flush()
    sess = ClassSession(class_id=cls.id, starts_at=datetime.utcnow() + timedelta(days=1))
    db.add_all([TeacherAssignment(teacher_id=tp.id, class_id=cls.id), GroupCourse(group_id=grp.id, course_id=course.id),
                Enrolment(user_id=learner.id, class_id=cls.id), Enrolment(user_id=learner.id, group_id=grp.id), sess])
    db.flush()
    db.add(Attendance(session_id=sess.id, user_id=learner.id, status="present"))
    plan = db.query(SubscriptionPlan).filter_by(code="institutional").one()
    sub = Subscription(plan_id=plan.id, organization_id=org.id, interval="year", status="trialing")
    db.add(sub)
    db.flush()
    pay = Payment(subscription_id=sub.id, organization_id=org.id, amount_cents=150000, status="pending", provider="stripe")
    db.add(pay)
    db.flush()
    db.add(Invoice(number="INV-0001", payment_id=pay.id, subscription_id=sub.id, organization_id=org.id, amount_cents=150000))
    db.commit()
    ex = server.get("/api/admin/expansion", headers=auth(admin_token)).json()
    assert ex["records"] == {"organizations": 1, "teachers": 1, "classes": 1, "groups": 1, "subscriptions": 1, "payments": 1}
    assert ex["features"]["payments"] == "configured_inactive" and ex["features"]["teacher_portal"] == "future"
    com = server.get("/api/admin/commerce", headers=auth(admin_token)).json()
    assert com["payments_active"] is False and com["pending_payments"] == 1 and com["total_revenue_cents"] == 0
    plans = server.get("/api/admin/plans", headers=auth(admin_token)).json()["plans"]
    assert [p["code"] for p in plans] == ["free", "basic", "premium", "business", "institutional"]
    # a teacher account can't sign in to the admin portal by default
    assert server.get("/api/admin/overview").status_code == 401
