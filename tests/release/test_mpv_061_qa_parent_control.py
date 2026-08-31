from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "mpv_061_qa_parent_control.py"


def load_module():
    spec = importlib.util.spec_from_file_location("mpv_061_qa_parent_control", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


TOKEN = base64.urlsafe_b64encode(b"q" * 32).decode().rstrip("=")
SCOPE = {
    "schemaVersion": 1,
    "caseId": "MPV-061",
    "candidateDigest": _hash("candidate"),
    "installedArtifactDigest": _hash("installed"),
    "runtimeOwnerBindingHash": _hash("runtime"),
    "ownerId": "64a000000000000000000001",
    "ownerEmail": "viventium-voice-qa-mpv-061-exact@example.com",
    "callSessionId": "call-synthetic-1",
    "primary": {"provider": "xai", "model": "grok-4.5"},
    "fallback": {"provider": "openAI", "model": "gpt-5.6-terra"},
}
SESSION = {
    "caseId": "MPV-061",
    "mode": "mpv_061",
    "modeVariable": "VIVENTIUM_LOCAL_QA_MODE",
    "sessionRef": "qa_0123456789abcdef01234567",
    "caseToken": TOKEN,
    "artifactIdentityDigest": SCOPE["candidateDigest"],
    "componentArtifactDigest": _hash("component"),
}


def challenge_fixture() -> dict[str, object]:
    session_ref_hash = _hash("session\0" + SESSION["sessionRef"])
    arm_identity = {
        "schemaVersion": 1,
        "caseId": "MPV-061",
        "sessionRefHash": session_ref_hash,
        "sessionCandidateDigest": SCOPE["candidateDigest"],
        "caseTokenHash": _hash("case-token\0" + TOKEN),
        "candidateDigest": SCOPE["candidateDigest"],
        "componentArtifactDigest": SESSION["componentArtifactDigest"],
        "installedArtifactDigest": SCOPE["installedArtifactDigest"],
        "runtimeOwnerBindingHash": SCOPE["runtimeOwnerBindingHash"],
        "ownerScopeHash": _hash("owner\0" + SCOPE["ownerId"]),
        "callScopeHash": _hash("call\0" + SCOPE["callSessionId"]),
        "primaryProvider": SCOPE["primary"]["provider"],
        "primaryModel": SCOPE["primary"]["model"],
        "fallbackProvider": SCOPE["fallback"]["provider"],
        "fallbackModel": SCOPE["fallback"]["model"],
    }
    arm_binding_hash = _hash(_canonical(arm_identity))
    now = datetime.now(timezone.utc)
    segments = [{"segmentId": "segment-a", "revision": 2}]
    turn = {
        "armBindingHash": arm_binding_hash,
        "turnScopeHash": _hash("turn\0turn-a"),
        "segmentSetHash": _hash(_canonical(segments)),
        "utteranceHash": _hash("utterance"),
    }
    challenge = {
        "schemaVersion": 1,
        "controlId": "mpv061_" + "a" * 24,
        "caseId": "MPV-061",
        "state": "challenged",
        **{key: value for key, value in arm_identity.items() if key != "caseTokenHash"},
        "armBindingHash": arm_binding_hash,
        "challengeId": "mpv061_ch_" + "b" * 24,
        "challengeIssuedAt": now.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "challengeExpiresAt": (now + timedelta(seconds=5))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "replayExpiresAt": (now + timedelta(seconds=60))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "turnId": "turn-a",
        "segments": segments,
        **turn,
        "turnBindingHash": _hash(_canonical(turn)),
        "coreProof": "c" * 43,
    }
    unsigned_keys = (
        "schemaVersion",
        "caseId",
        "controlId",
        "challengeId",
        "challengeIssuedAt",
        "challengeExpiresAt",
        "replayExpiresAt",
        "sessionRefHash",
        "sessionCandidateDigest",
        "candidateDigest",
        "componentArtifactDigest",
        "installedArtifactDigest",
        "runtimeOwnerBindingHash",
        "ownerScopeHash",
        "callScopeHash",
        "turnId",
        "segments",
        "turnScopeHash",
        "segmentSetHash",
        "utteranceHash",
        "primaryProvider",
        "primaryModel",
        "fallbackProvider",
        "fallbackModel",
    )
    challenge["approvalPayload"] = _canonical(
        {
            **{key: challenge[key] for key in unsigned_keys},
            "coreProof": challenge["coreProof"],
        }
    )
    return challenge


def test_parent_arms_watches_verifies_approves_and_returns_one_consumed_receipt():
    module = load_module()
    calls = []
    emitted = []
    challenge = challenge_fixture()

    def invoke(command, payload, timeout_seconds):
        calls.append((command, payload, timeout_seconds))
        if command == "arm":
            return {"controlId": "mpv061_" + "a" * 24, "state": "armed"}
        if command == "watch":
            return challenge
        if command == "approve":
            expected = hmac.new(
                base64.urlsafe_b64decode(TOKEN + "="),
                challenge["approvalPayload"].encode(),
                hashlib.sha256,
            ).digest()
            assert payload["approvalProof"] == base64.urlsafe_b64encode(
                expected
            ).decode().rstrip("=")
            return {"approved": True}
        if command == "receipt":
            return {
                "state": "consumed",
                "controlId": "mpv061_" + "a" * 24,
                "receiptDigest": _hash("receipt"),
                "receiptExpiresAt": "2026-08-26T12:15:00.000Z",
            }
        raise AssertionError(command)

    result = module.run_parent_control(
        scope=SCOPE,
        session=SESSION,
        invoke_cli=invoke,
        emit=emitted.append,
        monotonic=lambda: 10.0,
    )

    assert [entry[0] for entry in calls] == ["arm", "watch", "approve", "receipt"]
    assert emitted[0]["event"] == "armed"
    assert result == emitted[1]
    assert result["event"] == "receipt"
    assert TOKEN not in json.dumps(calls)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidateDigest", _hash("wrong")),
        ("componentArtifactDigest", _hash("wrong")),
        ("installedArtifactDigest", _hash("wrong")),
        ("runtimeOwnerBindingHash", _hash("wrong")),
        ("ownerScopeHash", _hash("wrong")),
        ("callScopeHash", _hash("wrong")),
        ("turnScopeHash", _hash("wrong")),
        ("segmentSetHash", _hash("wrong")),
        ("utteranceHash", _hash("wrong")),
        ("primaryModel", "wrong"),
        ("fallbackProvider", "wrong"),
        ("challengeExpiresAt", "2000-01-01T00:00:00.000Z"),
    ],
)
def test_parent_rejects_every_mismatched_or_stale_challenge(field, value):
    module = load_module()
    challenge = challenge_fixture()
    challenge[field] = value
    with pytest.raises(ValueError, match="challenge"):
        module.verify_challenge(challenge, scope=SCOPE, session=SESSION)


def test_parent_rejects_personal_owner_and_never_places_token_in_child_arguments():
    module = load_module()
    with pytest.raises(ValueError, match="synthetic"):
        module.validate_scope({**SCOPE, "ownerEmail": "person@example.com"}, SESSION)

    args, _env = module.cli_invocation(
        "arm", 7, SESSION, environ={"PATH": os.environ["PATH"]}
    )
    assert TOKEN not in " ".join(args)
    assert args[-2:] == ["--scope-fd", "7"]


def test_cleanup_removes_only_the_exact_copied_receipt():
    module = load_module()
    observed = []

    result = module.cleanup_parent_control(
        {
            "schemaVersion": 1,
            "caseId": "MPV-061",
            "controlId": "mpv061_" + "a" * 24,
            "receiptDigest": _hash("receipt"),
        },
        session=SESSION,
        invoke_cli=lambda command, payload, timeout: (
            observed.append((command, payload, timeout)) or {"removed": 1}
        ),
    )

    assert result == {"removed": 1}
    assert observed[0][0] == "cleanup"


def test_parent_rejects_non_regular_or_ambiguous_private_fd(tmp_path: Path):
    module = load_module()
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"{}")
        os.close(write_fd)
        write_fd = -1
        with pytest.raises(ValueError, match="private scope"):
            module._read_private_scope(read_fd)
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)

    scope_path = tmp_path / "scope.json"
    scope_path.write_text('{"caseId":"MPV-061","caseId":"forged"}', encoding="utf-8")
    scope_path.chmod(0o600)
    descriptor = os.open(scope_path, os.O_RDONLY)
    try:
        with pytest.raises(ValueError, match="private scope"):
            module._read_private_scope(descriptor)
    finally:
        os.close(descriptor)
