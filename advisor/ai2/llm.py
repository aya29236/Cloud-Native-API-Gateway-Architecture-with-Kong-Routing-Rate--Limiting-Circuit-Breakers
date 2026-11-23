"""Small Ollama and scripted LLM clients for AI2."""

import json
import math
import os
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class LLMClient(Protocol):
    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Return an assistant message with optional tool_calls."""


class OllamaClient:
    """Standard-library Ollama /api/chat client."""

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("ADVISOR_MODEL")
        timeout_value = timeout
        if timeout_value is None:
            raw_timeout = os.getenv("OLLAMA_TIMEOUT", "180")
            try:
                timeout_value = float(raw_timeout)
            except ValueError as exc:
                raise RuntimeError(
                    "OLLAMA_TIMEOUT must be a positive number of seconds."
                ) from exc
        if not math.isfinite(timeout_value) or timeout_value <= 0:
            raise RuntimeError("OLLAMA_TIMEOUT must be a positive number of seconds.")
        self.timeout = timeout_value
        if not self.model:
            raise RuntimeError(
                "ADVISOR_MODEL is not set. Set ADVISOR_MODEL to an Ollama model name."
            )

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        payload = {
            "model": self.model,
            "messages": list(messages),
            "tools": list(tools),
            "stream": False,
            "options": {"temperature": 0},
        }
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise RuntimeError(
                    f"Ollama request timed out after {self.timeout:g} seconds "
                    f"at {self.host}/api/chat"
                ) from exc
            raise RuntimeError(
                f"Cannot reach Ollama at {self.host}/api/chat: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout:g} seconds "
                f"at {self.host}/api/chat"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON") from exc

        message = body.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama response did not contain a valid assistant message")
        return message


class ScriptedClient:
    """Replay predefined assistant messages for deterministic tests and demos."""

    def __init__(self, messages: Sequence[Mapping[str, Any]]) -> None:
        self.messages = list(messages)
        self.calls = 0

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        del messages, tools
        if self.calls >= len(self.messages):
            return {"role": "assistant", "content": "No verified data"}
        message = dict(self.messages[self.calls])
        self.calls += 1
        return message
