"""Interchangeable LLM providers.

All application code talks to `LLMProvider`. Switching from OpenAI to
Anthropic (or adding a local model) is a settings change, not a rebuild.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from ..config import get_secret, settings


class ProviderError(RuntimeError):
    pass


class MissingAPIKey(ProviderError):
    def __init__(self, provider: str):
        super().__init__(
            f"No API key configured for '{provider}'. Open Settings > AI Providers to add one."
        )
        self.provider = provider


@dataclass
class ChatMessage:
    role: str  # system|user|assistant
    content: str


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def chat(self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 800) -> str:
        ...

    def chat_json(self, messages: list[ChatMessage], *, max_tokens: int = 1200) -> dict:
        raw = self.chat(messages, temperature=0.2, max_tokens=max_tokens)
        return parse_json_block(raw)


def parse_json_block(text: str) -> dict:
    """Extract the first JSON object from a model reply (tolerates ```json fences)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end == -1:
        raise ProviderError("Model did not return JSON")
    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Invalid JSON from model: {exc}") from exc


class OpenAIProvider(LLMProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"

    def __init__(self, model: str, api_key: str | None = None, timeout: float = 60):
        self.model = model
        self.api_key = api_key or get_secret("openai")
        if not self.api_key:
            raise MissingAPIKey("openai")
        self.timeout = timeout

    def chat(self, messages, *, temperature=0.7, max_tokens=800) -> str:
        payload = {
            "model": self.model,
            "messages": [m.__dict__ for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            r = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Network error contacting OpenAI: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"OpenAI error {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    base_url = "https://api.anthropic.com/v1"

    def __init__(self, model: str, api_key: str | None = None, timeout: float = 60):
        self.model = model
        self.api_key = api_key or get_secret("anthropic")
        if not self.api_key:
            raise MissingAPIKey("anthropic")
        self.timeout = timeout

    def chat(self, messages, *, temperature=0.7, max_tokens=800) -> str:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        convo = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        try:
            r = httpx.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "system": system,
                    "messages": convo,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Network error contacting Anthropic: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"Anthropic error {r.status_code}: {r.text[:300]}")
        return "".join(b.get("text", "") for b in r.json()["content"])


class GeminiProvider(LLMProvider):
    """Google Gemini via the generateContent REST API (free tier available for gemini-2.5-flash)."""

    name = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, model: str, api_key: str | None = None, timeout: float = 60):
        self.model = model
        self.api_key = api_key or get_secret("gemini")
        if not self.api_key:
            raise MissingAPIKey("gemini")
        self.timeout = timeout

    def _contents(self, messages):
        contents = []
        for m in messages:
            if m.role == "system":
                continue
            role = "model" if m.role == "assistant" else "user"
            if contents and contents[-1]["role"] == role:  # Gemini expects alternating turns
                contents[-1]["parts"].append({"text": m.content})
            else:
                contents.append({"role": role, "parts": [{"text": m.content}]})
        if not contents or contents[0]["role"] != "user":
            contents.insert(0, {"role": "user", "parts": [{"text": "(Start of the practice session.)"}]})
        return contents

    def _call(self, messages, temperature, max_tokens, json_mode=False) -> str:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if json_mode:
            cfg["responseMimeType"] = "application/json"
        body = {"contents": self._contents(messages), "generationConfig": cfg}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            r = httpx.post(f"{self.base_url}/models/{self.model}:generateContent", params={"key": self.api_key},
                           json=body, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Network error contacting Google Gemini: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"Gemini error {r.status_code}: {r.text[:300]}")
        data = r.json()
        cands = data.get("candidates") or []
        if not cands:
            raise ProviderError(f"Gemini returned no answer: {str(data.get('promptFeedback', data))[:200]}")
        return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))

    def chat(self, messages, *, temperature=0.7, max_tokens=800) -> str:
        # Thinking models spend part of the budget on reasoning; leave headroom
        return self._call(messages, temperature, max_tokens + 1500)

    def chat_json(self, messages, *, max_tokens=1200) -> dict:
        return parse_json_block(self._call(messages, 0.2, max_tokens + 1500, json_mode=True))


_REGISTRY = {"gemini": GeminiProvider, "openai": OpenAIProvider, "anthropic": AnthropicProvider}
DEFAULT_MODELS = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini", "anthropic": "claude-sonnet-5-5"}

# Test hook / plug-in point: set to an LLMProvider instance to override.
_override: LLMProvider | None = None


def set_llm_override(provider: LLMProvider | None) -> None:
    global _override
    _override = provider


def get_llm() -> LLMProvider:
    """The configured provider; if it has no key, the first provider that does (zero-configuration)."""
    if _override is not None:
        return _override
    cls = _REGISTRY.get(settings.llm_provider)
    if cls is None:
        raise ProviderError(f"Unknown LLM provider '{settings.llm_provider}'")
    try:
        return cls(settings.llm_model)
    except MissingAPIKey:
        for name, other in _REGISTRY.items():
            if name != settings.llm_provider and get_secret(name):
                return other(DEFAULT_MODELS[name])
        raise MissingAPIKey("gemini (free) or openai")
