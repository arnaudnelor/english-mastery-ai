from __future__ import annotations

from typing import Any, Callable

MultipartCallbacks = dict
QuerystringCallbacks = dict


def parse_options_header(value: str | bytes | None) -> tuple[bytes, dict[bytes, bytes]]:
    """'form-data; name="a"; filename="b.txt"' -> (b'form-data', {b'name': b'a', b'filename': b'b.txt'})"""
    if not value:
        return b"", {}
    if isinstance(value, str):
        value = value.encode("latin-1")
    parts = _split_params(value)
    ctype = parts[0].strip().lower()
    options: dict[bytes, bytes] = {}
    for p in parts[1:]:
        if b"=" not in p:
            continue
        k, v = p.split(b"=", 1)
        v = v.strip()
        if len(v) >= 2 and v[:1] == v[-1:] == b'"':
            v = v[1:-1].replace(b'\\"', b'"').replace(b"\\\\", b"\\")
        options[k.strip().lower()] = v
    return ctype, options


def _split_params(value: bytes) -> list[bytes]:
    """Split on ';' outside double quotes."""
    out, cur, quoted, i = [], bytearray(), False, 0
    while i < len(value):
        c = value[i:i + 1]
        if c == b"\\" and quoted and i + 1 < len(value):
            cur += value[i:i + 2]
            i += 2
            continue
        if c == b'"':
            quoted = not quoted
        if c == b";" and not quoted:
            out.append(bytes(cur))
            cur = bytearray()
        else:
            cur += c
        i += 1
    out.append(bytes(cur))
    return out


class MultipartParser:
    def __init__(self, boundary: bytes | str, callbacks: dict[str, Callable[..., Any]] | None = None, max_size: float = float("inf")):
        if isinstance(boundary, str):
            boundary = boundary.encode("latin-1")
        self.boundary = boundary
        self.callbacks = callbacks or {}
        self.buffer = bytearray()
        self.done = False

    def _cb(self, name: str, *args) -> None:
        fn = self.callbacks.get(name)
        if fn:
            fn(*args)

    def write(self, data: bytes) -> int:
        if self.done:
            return len(data)
        self.buffer += data
        if b"--" + self.boundary + b"--" in self.buffer:
            self._parse()
        return len(data)

    def finalize(self) -> None:
        if not self.done and self.buffer:
            self._parse()

    def _parse(self) -> None:
        self.done = True
        delim = b"--" + self.boundary
        body = bytes(self.buffer)
        start = body.find(delim)
        if start < 0:
            self._cb("on_end")
            return
        pos = start + len(delim)
        while True:
            if body[pos:pos + 2] == b"--":  # closing delimiter
                break
            if body[pos:pos + 2] == b"\r\n":
                pos += 2
            nxt = body.find(b"\r\n" + delim, pos)
            if nxt < 0:
                break
            part = body[pos:nxt]
            head_end = part.find(b"\r\n\r\n")
            raw_headers, content = (part[:head_end], part[head_end + 4:]) if head_end >= 0 else (b"", part)
            self._cb("on_part_begin")
            for line in raw_headers.split(b"\r\n"):
                if b":" not in line:
                    continue
                name, val = line.split(b":", 1)
                name, val = name.strip(), val.strip()
                self._cb("on_header_field", name, 0, len(name))
                self._cb("on_header_value", val, 0, len(val))
                self._cb("on_header_end")
            self._cb("on_headers_finished")
            if content:
                self._cb("on_part_data", content, 0, len(content))
            self._cb("on_part_end")
            pos = nxt + 2 + len(delim)
        self._cb("on_end")


class QuerystringParser:
    def __init__(self, callbacks: dict[str, Callable[..., Any]] | None = None, max_size: float = float("inf")):
        self.callbacks = callbacks or {}
        self.buffer = bytearray()

    def _cb(self, name: str, *args) -> None:
        fn = self.callbacks.get(name)
        if fn:
            fn(*args)

    def write(self, data: bytes) -> int:
        self.buffer += data
        return len(data)

    def finalize(self) -> None:
        for pair in bytes(self.buffer).replace(b";", b"&").split(b"&"):
            if not pair:
                continue
            name, _, value = pair.partition(b"=")
            self._cb("on_field_start")
            self._cb("on_field_name", name, 0, len(name))
            if value:
                self._cb("on_field_data", value, 0, len(value))
            self._cb("on_field_end")
        self._cb("on_end")
