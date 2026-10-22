"""Explicit local-only Ollama clients for embedding and chat (separate capabilities)."""
from __future__ import annotations

import json
import math
import os
from http.client import HTTPConnection
from urllib.parse import urlsplit

from .errors import DocumentProviderError

DEFAULT_LOCAL_ENDPOINT = "http://127.0.0.1:11434"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def _local_endpoint(endpoint: str | None = None) -> tuple[str, int]:
    value = endpoint or os.environ.get("OLLAMA_HOST") or DEFAULT_LOCAL_ENDPOINT
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "http" or host not in {"127.0.0.1", "::1", "localhost"}:
        raise DocumentProviderError("Only a loopback Ollama endpoint is allowed; remote access is disabled.")
    return host, parsed.port or 11434


def _post(path: str, payload: dict, endpoint: str | None = None, timeout: int = 120) -> dict:
    host, port = _local_endpoint(endpoint)
    connection = HTTPConnection(host, port, timeout=timeout)
    try:
        connection.request("POST", path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            message = response.read(2048).decode("utf-8", "replace")
            raise DocumentProviderError(f"Local Ollama request failed ({response.status}): {message}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise DocumentProviderError("Local model response exceeded the configured size limit.")
        return json.loads(raw)
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise DocumentProviderError(f"Local Ollama is unavailable: {exc}") from exc
    finally:
        connection.close()


def _get(path: str, endpoint: str | None = None) -> dict:
    host, port = _local_endpoint(endpoint)
    connection = HTTPConnection(host, port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if response.status != 200 or len(raw) > MAX_RESPONSE_BYTES:
            raise DocumentProviderError(f"Local Ollama inventory request failed ({response.status}).")
        return json.loads(raw)
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise DocumentProviderError(f"Local Ollama is unavailable: {exc}") from exc
    finally:
        connection.close()


def _require_installed(model: str, endpoint: str | None) -> None:
    result = _get("/api/tags", endpoint)
    installed = {item.get("name", "") for item in result.get("models", [])}
    aliases = {model, model if ":" in model else f"{model}:latest"}
    if not installed.intersection(aliases):
        raise DocumentProviderError(f"{model!r} is not installed in the local Ollama runtime. Models are never downloaded automatically.")


class OllamaEmbeddingProvider:
    """Uses Ollama's embedding endpoint only; it never infers support from a chat model."""

    def __init__(self, model: str, endpoint: str | None = None) -> None:
        if not model.strip():
            raise DocumentProviderError("Select an installed local embedding model first.")
        self.model, self.endpoint = model.strip(), endpoint
        self._dimensions: int | None = None

    @property
    def dimensions(self) -> int | None:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        result = _post("/api/embed", {"model": self.model, "input": texts}, self.endpoint)
        vectors = result.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise DocumentProviderError("Embedding runtime returned an invalid batch.")
        checked = []
        for vector in vectors:
            if not isinstance(vector, list) or not vector:
                raise DocumentProviderError("Embedding runtime returned an empty vector.")
            values = tuple(float(item) for item in vector)
            if not all(math.isfinite(item) for item in values):
                raise DocumentProviderError("Embedding runtime returned non-finite values.")
            if self._dimensions is not None and len(values) != self._dimensions:
                raise DocumentProviderError("Embedding dimensions changed within the configured model.")
            self._dimensions = len(values)
            checked.append(values)
        return checked

    def verify_model(self) -> None:
        _require_installed(self.model, self.endpoint)
        result = _post("/api/show", {"model": self.model}, self.endpoint)
        capabilities = result.get("capabilities", [])
        if "embedding" not in capabilities:
            raise DocumentProviderError(
                f"{self.model!r} does not advertise embedding capability; configure a separate embedding model."
            )


class OllamaChatProvider:
    """Invokes a configured local Ollama chat model with tools and streaming disabled."""

    def __init__(self, model: str, endpoint: str | None = None) -> None:
        if not model.strip():
            raise DocumentProviderError("Select an installed local chat model first.")
        self.model, self.endpoint = model.strip(), endpoint

    def verify_model(self) -> None:
        _require_installed(self.model, self.endpoint)
        result = _post("/api/show", {"model": self.model}, self.endpoint)
        if "completion" not in result.get("capabilities", []):
            raise DocumentProviderError(f"{self.model!r} does not advertise local chat completion capability.")

    def answer(self, system_prompt: str, user_prompt: str,
               *, response_format: str | dict | None = None) -> str:
        self.verify_model()
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.1},
        }
        if response_format is not None:
            payload["format"] = response_format
        result = _post("/api/chat", payload, self.endpoint, timeout=300)
        content = result.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise DocumentProviderError("Local chat model returned no answer.")
        return content.strip()
