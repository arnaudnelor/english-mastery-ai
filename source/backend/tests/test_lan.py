from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def remote_client(tmp_path):
    from app.db import init_engine
    init_engine(f"sqlite:///{tmp_path / 'lan.db'}")
    return TestClient(create_app(), client=("192.168.1.50", 50000))


def test_lan_requires_pin_and_blocks_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "lan_pin", "4821")
    c = remote_client(tmp_path)
    assert c.get("/api/system/health").status_code == 200
    assert c.get("/api/grammar/topics").status_code == 401
    assert c.post("/api/system/unlock", json={"pin": "0000"}).status_code == 401
    assert c.post("/api/system/unlock", json={"pin": "4821"}).status_code == 200
    assert c.get("/api/grammar/topics").status_code == 200  # cookie set
    assert c.post("/api/system/keys", json={"provider": "openai", "api_key": "sk-xxxxxxxxxxxx"}).status_code == 403
    assert c.get("/api/system/whoami").json() == {"local": False, "lan_mode": True}


def test_remote_blocked_without_lan_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "lan_pin", "")
    c = remote_client(tmp_path)
    assert c.get("/api/grammar/topics").status_code == 401
