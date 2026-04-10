from __future__ import annotations

from typing import Any


DEFAULT_RETRIEVAL_EMBEDDINGS_PROVIDER = "ollama"
DEFAULT_RETRIEVAL_EMBEDDINGS_MODEL = "qwen3-embedding:0.6b"
DEFAULT_RETRIEVAL_EMBEDDINGS_PROFILE = "medium"
DEFAULT_RETRIEVAL_OLLAMA_BASE_URL = "http://host.docker.internal:11434"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_retrieval_embeddings_provider(value: Any) -> str:
    normalized = _normalize_text(value).lower()
    return normalized or DEFAULT_RETRIEVAL_EMBEDDINGS_PROVIDER


def normalize_retrieval_embeddings_profile(value: Any) -> str:
    normalized = _normalize_text(value).lower()
    return normalized or DEFAULT_RETRIEVAL_EMBEDDINGS_PROFILE


def resolve_retrieval_embeddings_settings(config: dict[str, Any]) -> dict[str, str]:
    runtime = config.get("runtime", {}) or {}
    retrieval = runtime.get("retrieval", {}) or {}
    embeddings = retrieval.get("embeddings", {}) or {}

    provider = normalize_retrieval_embeddings_provider(embeddings.get("provider"))
    model = _normalize_text(embeddings.get("model")) or DEFAULT_RETRIEVAL_EMBEDDINGS_MODEL
    profile = normalize_retrieval_embeddings_profile(embeddings.get("profile"))
    ollama_base_url = (
        _normalize_text(embeddings.get("ollama_base_url")) or DEFAULT_RETRIEVAL_OLLAMA_BASE_URL
    )

    return {
        "provider": provider,
        "model": model,
        "profile": profile,
        "ollama_base_url": ollama_base_url,
    }
