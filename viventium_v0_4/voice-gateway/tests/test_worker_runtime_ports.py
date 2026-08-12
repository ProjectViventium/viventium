"""VIVENTIUM START
Feature: side-by-side voice-worker port isolation.
Purpose: protect local prod and dev runtimes from competing for LiveKit Agents' implicit 8081
HTTP listener while preserving an explicit operator override for deployments that need one.
VIVENTIUM END"""

from __future__ import annotations

import pytest

import worker


def test_voice_worker_http_port_defaults_to_ephemeral(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIVENTIUM_VOICE_WORKER_HTTP_PORT", raising=False)

    assert worker._resolve_voice_worker_http_port() == 0


def test_voice_worker_http_port_accepts_an_explicit_operator_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIVENTIUM_VOICE_WORKER_HTTP_PORT", "18081")

    assert worker._resolve_voice_worker_http_port() == 18081


@pytest.mark.parametrize("value", ["invalid", "-1", "65536"])
def test_voice_worker_http_port_rejects_invalid_operator_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("VIVENTIUM_VOICE_WORKER_HTTP_PORT", value)

    with pytest.raises(ValueError, match="VIVENTIUM_VOICE_WORKER_HTTP_PORT"):
        worker._resolve_voice_worker_http_port()
