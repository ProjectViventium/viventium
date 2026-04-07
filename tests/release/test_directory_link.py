from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DIRECTORY_LINK_PATH = REPO_ROOT / "scripts/viventium/directory_link.py"


def load_directory_link_module():
    spec = importlib.util.spec_from_file_location("viventium_directory_link_test", DIRECTORY_LINK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_directory_base_url_allows_https_and_localhost_http() -> None:
    module = load_directory_link_module()

    assert module.normalize_directory_base_url("https://viventium.ai") == "https://viventium.ai"
    assert module.normalize_directory_base_url("http://localhost:3001") == "http://localhost:3001"
    assert module.normalize_directory_base_url("http://127.0.0.1:3001") == "http://127.0.0.1:3001"


def test_normalize_directory_base_url_rejects_insecure_remote_hosts() -> None:
    module = load_directory_link_module()

    with pytest.raises(RuntimeError, match="directory_base_url may only use http:// for localhost testing"):
        module.normalize_directory_base_url("http://example.com")


def test_normalize_username_enforces_public_directory_contract() -> None:
    module = load_directory_link_module()

    assert module.normalize_username("  Qa-User-9  ") == "qa-user-9"

    with pytest.raises(RuntimeError, match="username may only contain lowercase letters, numbers, and hyphens"):
        module.normalize_username("qa_user")

    with pytest.raises(RuntimeError, match="username cannot start or end with a hyphen"):
        module.normalize_username("-qa-user")


def test_canonical_payload_stays_stable() -> None:
    module = load_directory_link_module()

    payload = {
        "username": "qa-user",
        "targetOrigin": "https://app.example.com",
        "instanceId": "instance-123",
        "publicKeyFingerprint": "sha256:abc",
        "issuedAt": "2026-04-05T03:00:00Z",
    }

    assert module.canonical_payload(payload) == "\n".join(
        [
            "username=qa-user",
            "targetOrigin=https://app.example.com",
            "instanceId=instance-123",
            "publicKeyFingerprint=sha256:abc",
            "issuedAt=2026-04-05T03:00:00Z",
        ]
    )


def test_parse_args_accepts_positional_username(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_directory_link_module()

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "directory_link.py",
            "--state-file",
            "/tmp/public-network.json",
            "qa-user",
        ],
    )

    args = module.parse_args()

    assert args.state_file == "/tmp/public-network.json"
    assert args.username == "qa-user"


def test_parse_args_accepts_explicit_username_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_directory_link_module()

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "directory_link.py",
            "--state-file",
            "/tmp/public-network.json",
            "--username",
            "qa-user",
        ],
    )

    args = module.parse_args()

    assert args.username == "qa-user"
