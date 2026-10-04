"""LLM access for the writing agents.

Two providers:

* ``static``  - no network. Uses the artefacts authored in story/ and episodes/.
  This is what runs by default, and it is why the pilot costs nothing.
* ``openai``  - any OpenAI-compatible endpoint, which covers OmniRoute on
  localhost:20128. Read the key from the env var named in config, never from
  disk, and never log it.

Writing agents fail closed. A weak story is the most expensive defect in this
pipeline because it is the one thing a downstream stage cannot repair, so an
unreachable LLM raises instead of emitting a fallback script.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from lib import config


class LLMUnavailable(RuntimeError):
    pass


class OpenAICompatClient:
    def __init__(self, cfg: dict):
        self.cfg = cfg["llm"]
        self.base = self.cfg["base_url"].rstrip("/")
        self.model = self.cfg.get("model") or ""
        env = self.cfg.get("api_key_env", "OMNIROUTE_API_KEY")
        self.key = os.environ.get(env, "")
        self.timeout = int(self.cfg.get("timeout_s", 180))
        self.temperature = float(self.cfg.get("temperature", 0.85))

    def models(self) -> list[str]:
        if not self.key:
            raise LLMUnavailable("no API key in env for the configured endpoint")
        req = urllib.request.Request(f"{self.base}/models", headers=self._headers())
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("id", "") for m in data.get("data", [])]

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def complete(self, system: str, user: str, *, max_tokens: int = 2600,
                 json_mode: bool = False) -> str:
        if not self.model:
            raise LLMUnavailable("llm.model is empty - set a model id in config/pipeline.json")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            f"{self.base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMUnavailable(f"endpoint HTTP {exc.code}: {exc.read()[:400]!r}") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise LLMUnavailable(f"endpoint unreachable: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMUnavailable(f"unexpected response shape: {str(data)[:300]}") from exc

    def complete_json(self, system: str, user: str, **kw) -> Any:
        raw = self.complete(system, user, json_mode=True, **kw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"model did not return valid JSON: {raw[:300]}") from exc


def client(cfg: dict) -> OpenAICompatClient | None:
    """Return an LLM client, or None when the pipeline is in static mode."""
    if cfg["llm"].get("provider", "static") == "static":
        return None
    return OpenAICompatClient(cfg)


def describe(cfg: dict) -> str:
    l = cfg["llm"]
    if l.get("provider", "static") == "static":
        return "static (no network calls, artefacts authored in story/ and episodes/)"
    key_present = bool(os.environ.get(l.get("api_key_env", "OMNIROUTE_API_KEY"), ""))
    return f"{l['base_url']} model={l.get('model') or '<unset>'} key={'present' if key_present else 'MISSING'}"