"""Boots the real English Mastery AI engine inside the browser (Pyodide, in a Web Worker).

Three browser adaptations; everything else is the unmodified desktop engine:
1. No threads: anyio's thread offloading (used by FastAPI for sync endpoints) runs inline.
2. No sockets: `httpx.post` is routed through the browser's XMLHttpRequest (synchronous, which is
   allowed in a worker), so the OpenAI / Anthropic / Azure providers work unchanged.
3. No Windows Credential Manager: API keys are stored in this browser's private storage (IndexedDB),
   on this device only, and are sent only to the provider they belong to.
"""
import json
import os
from urllib.parse import urlencode

os.environ.setdefault("EMA_DATA_DIR", "/data/EnglishMasteryAI")

# ---- 1. threads ---------------------------------------------------------------------------
import anyio.to_thread  # noqa: E402


async def _run_inline(func, *args, abandon_on_cancel=False, cancellable=None, limiter=None):
    return func(*args)


anyio.to_thread.run_sync = _run_inline

# ---- 2. HTTP through the browser ----------------------------------------------------------
import httpx  # noqa: E402
from js import Uint8Array, XMLHttpRequest  # noqa: E402
from pyodide.ffi import to_js  # noqa: E402


class _BrowserResponse:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.content)


def _multipart(data: dict, files: dict) -> tuple[bytes, str]:
    boundary = "----EMABoundary7MA4YWxkTrZu0gW"
    out = bytearray()
    for k, v in (data or {}).items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (filename, blob) in (files or {}).items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        out += blob + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _browser_post(url, *, headers=None, json=None, data=None, files=None, content=None, params=None, timeout=None, **_):
    import json as _json

    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    hdrs = dict(headers or {})
    body = None
    if json is not None:
        body = _json.dumps(json).encode()
        hdrs.setdefault("Content-Type", "application/json")
    elif files:
        body, hdrs["Content-Type"] = _multipart(data, files)
    elif content is not None:
        body = content if isinstance(content, bytes) else str(content).encode()
    elif data:
        body = urlencode(data).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    if "api.anthropic.com" in url:
        hdrs["anthropic-dangerous-direct-browser-access"] = "true"  # Anthropic's opt-in for browser requests
    xhr = XMLHttpRequest.new()
    xhr.open("POST", url, False)
    xhr.responseType = "arraybuffer"
    for k, v in hdrs.items():
        xhr.setRequestHeader(k, v)
    try:
        xhr.send(to_js(body) if body is not None else None)
    except Exception as exc:  # network / CORS failure
        raise httpx.ConnectError(f"Browser request to {url.split('/')[2]} failed: {exc}") from exc
    if xhr.status == 0:
        raise httpx.ConnectError(f"Browser request to {url.split('/')[2]} was blocked (network or CORS).")
    raw = bytes(Uint8Array.new(xhr.response).to_py()) if xhr.response else b""
    return _BrowserResponse(int(xhr.status), raw)


httpx.post = _browser_post

# ---- 3. keys stored in this browser ---------------------------------------------------------
import app.config as _cfg  # noqa: E402


def _keyfile():
    _cfg.settings.data_dir.mkdir(parents=True, exist_ok=True)
    return _cfg.settings.data_dir / "browser_keys.json"


def _load_keys() -> dict:
    try:
        return json.loads(_keyfile().read_text())
    except Exception:
        return {}


def _get_secret(name):
    return _load_keys().get(name) or os.environ.get(f"{name.upper()}_API_KEY")


def _set_secret(name, value):
    keys = _load_keys()
    keys[name] = value
    _keyfile().write_text(json.dumps(keys))
    return True


def _delete_secret(name):
    keys = _load_keys()
    keys.pop(name, None)
    _keyfile().write_text(json.dumps(keys))


_cfg.get_secret, _cfg.set_secret, _cfg.delete_secret = _get_secret, _set_secret, _delete_secret

# ---- start the unmodified app ---------------------------------------------------------------
from app.db import init_engine  # noqa: E402
from app.main import create_app, setup_logging  # noqa: E402

setup_logging()
init_engine()
app = create_app()


async def handle(method, path, query, headers_json, body):
    headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in json.loads(headers_json)]
    body_bytes = bytes(body.to_py()) if hasattr(body, "to_py") else b""  # JS null arrives as JsNull
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "https",
             "path": path, "raw_path": path.encode(), "query_string": query.encode(), "root_path": "",
             "headers": headers, "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 443)}
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        return {"type": "http.disconnect"}

    status, out_headers, chunks = 500, [], []

    async def send(msg):
        nonlocal status, out_headers
        if msg["type"] == "http.response.start":
            status = msg["status"]
            out_headers = [(k.decode("latin-1"), v.decode("latin-1")) for k, v in msg.get("headers", [])]
        elif msg["type"] == "http.response.body":
            chunks.append(msg.get("body", b""))

    await app(scope, receive, send)
    return [status, json.dumps(out_headers), b"".join(chunks)]
