"""Pluggable local LLM provider.

The only provider for v1 is Ollama (gemma4), talked to over its HTTP API using
the stdlib (no extra dependency). The interface is deliberately small —
`complete(prompt, json_mode=...)` returns the model's text — so a different
local model or backend can be swapped in later by adding a provider class and
selecting it via CLIPFORGE_LLM_PROVIDER, without touching the highlight or
edit-parsing logic.

The LLM only ever sees text. It never touches audio or video.
"""
from __future__ import annotations

import json
import os
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("CLIPFORGE_LLM_MODEL", "gemma4:latest")
DEFAULT_PROVIDER = os.environ.get("CLIPFORGE_LLM_PROVIDER", "ollama")


class OllamaProvider:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = OLLAMA_HOST):
        self.model = model
        self.host = host.rstrip("/")

    def name(self) -> str:
        return f"ollama:{self.model}"

    def complete(
        self, prompt: str, *, json_mode: bool = False, temperature: float = 0.2,
        timeout: float = 300.0,
    ) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            body["format"] = "json"  # Ollama constrains output to valid JSON
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data.get("response", "")


def get_provider():
    if DEFAULT_PROVIDER == "ollama":
        return OllamaProvider()
    raise ValueError(f"unknown LLM provider: {DEFAULT_PROVIDER!r}")
