from __future__ import annotations

import atexit
import base64
import functools
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "viventium" / "parallel_work_release_gate.py"
OWNER_PROCESSES: list[subprocess.Popen[bytes]] = []
DETACHED_COMMAND_CONTRACT = (
    ROOT / "scripts/viventium/runtime_owner_command_contract.json"
)
FIXTURE_CASE_IDS = (
    "PWK-001",
    "PWK-UC-014",
    "REL-001",
    "REL-UC-004",
    "TR-026",
    "EMO-UC-047",
    "EMO-UC-048",
    "MPV-061",
    "TGDOC-010",
)
FIXTURE_CASE_SERVICES = {
    "TR-026": ("librechat-core", "telegram-bot"),
    "EMO-UC-047": ("glasshive-runtime", "librechat-core"),
    "EMO-UC-048": ("librechat-core", "telegram-bot"),
    "REL-UC-004": ("librechat-core",),
}


class _ExternalFixtureSigner:
    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path

    def sign(self, payload: bytes, namespace: str) -> str:
        result = subprocess.run(
            [
                "/usr/bin/ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(self.key_path),
                "-n",
                namespace,
            ],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout.decode("ascii")


class _ExternalFixtureWitness:
    def __init__(self) -> None:
        self.heads: dict[str, object] = {}

    def current(self, scope: str) -> object | None:
        return self.heads.get(scope)

    def advance(self, scope: str, *, expected: object | None, head: object) -> bool:
        if self.heads.get(scope) != expected:
            return False
        self.heads[scope] = head
        return True


class _ExternalFixtureWitnessEndpoint:
    """Explicit test transport only; production independently verifies real root ownership."""

    def __init__(self, owner_uid: int = 0) -> None:
        self.owner_uid = owner_uid

    def stat(self, *, follow_symlinks: bool = True) -> SimpleNamespace:
        assert follow_symlinks is False
        return SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=self.owner_uid)

    def __str__(self) -> str:
        return "/test-only/protected-release-witness.sock"


class _ExternalFixtureWitnessConnection:
    """A signed protocol test double; never accepted by the production resolver."""

    def __init__(
        self,
        gate,
        heads: dict[str, object],
        *,
        mutate=None,
        signing_key: Path | None = None,
    ) -> None:
        self.gate = gate
        self.heads = heads
        self.mutate = mutate
        self.signing_key = signing_key or _external_fixture_keys()["witness"]
        self.payload = b""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def settimeout(self, timeout: int) -> None:
        assert timeout > 0

    def connect(self, endpoint: str) -> None:
        assert endpoint == "/test-only/protected-release-witness.sock"

    def sendall(self, encoded_request: bytes) -> None:
        attestation = self.gate._load_external_release_attestation()
        request = json.loads(encoded_request)
        scope = request["scope"]
        operation = request["operation"]
        current = self.heads.get(scope)
        if operation == "probe":
            accepted = True
            current = None
        elif operation == "current":
            accepted = True
        else:
            accepted = current == request["expected"]
            if accepted:
                current = request["head"]
                self.heads[scope] = current
        response = {
            "accepted": accepted,
            "candidateDigest": request["candidateDigest"],
            "contractVersion": 1,
            "durability": self.gate.RELEASE_AUTHORITY_WITNESS_DURABILITY,
            "head": current,
            "nonce": request["nonce"],
            "operation": operation,
            "ownerBindingSha256": request["ownerBindingSha256"],
            "purpose": self.gate.RELEASE_AUTHORITY_WITNESS_RESPONSE_PURPOSE,
            "requestDigest": hashlib.sha256(encoded_request).hexdigest(),
            "scope": scope,
            "witnessIdentity": request["witnessIdentity"],
        }
        if self.mutate is not None:
            self.mutate(response)
        response["signature"] = _ExternalFixtureSigner(self.signing_key).sign(
            attestation._canonical_bytes(response),
            self.gate.RELEASE_AUTHORITY_WITNESS_NAMESPACE,
        )
        self.payload = attestation._canonical_bytes(response)

    def recv(self, maximum: int) -> bytes:
        assert len(self.payload) <= maximum
        payload, self.payload = self.payload, b""
        return payload


def _test_only_authenticated_witness(
    gate,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutate=None,
    endpoint_owner_uid: int = 0,
    peer_uid: int = 0,
    signing_key: Path | None = None,
):
    """Protocol-only injection; production still rejects the non-system root."""

    identity = "viventium.fixture.system-witness.v1"
    key = _external_fixture_keys()["witness"]
    signer_roots = f"{identity} {_fixture_public_key(key)}\n".encode("ascii")
    heads: dict[str, object] = {}
    monkeypatch.setattr(
        gate,
        "_release_authority_socket_peer_uid",
        lambda _connection: peer_uid,
    )
    monkeypatch.setattr(
        gate.socket,
        "socket",
        lambda *_args, **_kwargs: _ExternalFixtureWitnessConnection(
            gate, heads, mutate=mutate, signing_key=signing_key
        ),
    )
    return gate._ProtectedExternalReleaseLedgerWitness(
        attestation=gate._load_external_release_attestation(),
        candidate_digest="a" * 64,
        endpoint=_ExternalFixtureWitnessEndpoint(endpoint_owner_uid),
        owner_binding="b" * 64,
        signer_roots=signer_roots,
        witness_identity=identity,
    )


EXTERNAL_AUTHORITY_BOOTSTRAP_NAMESPACE = (
    "viventium-qa-release-authority-bootstrap-v1"
)
EXTERNAL_AUTHORITY_BOOTSTRAP_PURPOSE = (
    "viventium.qa.release.authority-bootstrap.v1"
)
EXTERNAL_AUTHORITY_WITNESS_PROTECTION = (
    "externally-protected-compare-and-swap-v1"
)
EXTERNAL_AUTHORITY_PROVIDER_SOURCE = """import sys


class ProtectedReleaseLedgerWitness:
    __slots__ = ("_backend", "witness_identity")
    protection = "externally-protected-compare-and-swap-v1"

    def __init__(self, backend, witness_identity):
        self._backend = backend
        self.witness_identity = witness_identity

    def current(self, scope):
        return self._backend.current(scope)

    def advance(self, scope, *, expected, head):
        return self._backend.advance(scope, expected=expected, head=head)


def resolve_release_attestation_authority(
    *,
    candidate_digest,
    owner_binding_sha256,
    policy_sha256,
    publisher_identity,
    publisher_fingerprint,
    witness_identity,
):
    gate = sys.modules["parallel_work_release_gate"]
    claim = {
        "contractVersion": 1,
        "candidateDigest": candidate_digest,
        "ownerBindingSha256": owner_binding_sha256,
        "policySha256": policy_sha256,
        "publisherIdentity": publisher_identity,
        "publisherFingerprint": publisher_fingerprint,
        "witnessIdentity": witness_identity,
    }
    if claim != gate._test_external_release_provider_claim:
        return None
    return {
        **claim,
        "ledgerWitness": ProtectedReleaseLedgerWitness(
            gate._test_external_release_authority.ledger_witness,
            witness_identity,
        ),
    }
"""


@functools.lru_cache(maxsize=1)
def _external_fixture_keys() -> dict[str, Path]:
    temporary = tempfile.TemporaryDirectory(prefix="viventium-external-qa-fixture-")
    atexit.register(temporary.cleanup)
    root = Path(temporary.name)
    keys: dict[str, Path] = {}
    for name in (
        "publisher",
        "witness",
        "observation-producer",
        "glasshive-runtime",
        "librechat-core",
        "telegram-bot",
    ):
        key = root / name
        subprocess.run(
            [
                "/usr/bin/ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                f"{name}@fixture.example.invalid",
                "-f",
                str(key),
            ],
            check=True,
            capture_output=True,
        )
        keys[name] = key
    return keys


def _fixture_public_key(key_path: Path) -> str:
    return " ".join(Path(f"{key_path}.pub").read_text(encoding="utf-8").split()[:2])


def _fixture_key_fingerprint(key_path: Path) -> str:
    wire = base64.b64decode(_fixture_public_key(key_path).split()[1], validate=True)
    return "SHA256:" + base64.b64encode(hashlib.sha256(wire).digest()).decode(
        "ascii"
    ).rstrip("=")


def _register_fixture_semantic_verifiers(gate) -> None:
    for case_id in ("PWK-001", "REL-001"):
        gate.REGISTERED_SEMANTIC_VERIFIERS.setdefault(
            case_id,
            {
                "id": f"fixture-{case_id.lower()}-semantic-v1",
                "path": Path(
                    "qa/parallel-orchestrator/scripts/installed_journey_qa.py"
                    if case_id.startswith("PWK-")
                    else "qa/release-readiness/scripts/rel_uc_004_semantic_verifier.py"
                ),
            },
        )


def _install_external_fixture_policy(root: Path, gate) -> None:
    _register_fixture_semantic_verifiers(gate)
    keys = _external_fixture_keys()
    identities = {
        name: f"{name}@fixture.example.invalid" for name in keys
    }
    allowed_signers = root / "qa" / "trust" / "parallel-work-release.allowed_signers"
    allowed_signers.parent.mkdir(parents=True, exist_ok=True)
    allowed_signers.write_text(
        "".join(
            f"{identities[name]} {_fixture_public_key(path)}\n"
            for name, path in keys.items()
            if name != "witness"
        ),
        encoding="utf-8",
    )
    producers: dict[str, dict[str, str]] = {
        "observation-producer": {
            "identity": identities["observation-producer"],
            "fingerprint": _fixture_key_fingerprint(keys["observation-producer"]),
            "role": "observation",
        }
    }
    for service_id in ("glasshive-runtime", "librechat-core", "telegram-bot"):
        producers[service_id] = {
            "identity": identities[service_id],
            "fingerprint": _fixture_key_fingerprint(keys[service_id]),
            "role": "service",
            "serviceId": service_id,
        }
    policy = {
        "contractVersion": 1,
        "allowedSigners": {
            "path": allowed_signers.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(allowed_signers.read_bytes()).hexdigest(),
        },
        "publisher": {
            "identity": identities["publisher"],
            "fingerprint": _fixture_key_fingerprint(keys["publisher"]),
        },
        "producers": producers,
        "cases": {
            case_id: {
                "surface": "voice" if case_id == "MPV-061" else "telegram",
                "verifierId": gate.REGISTERED_SEMANTIC_VERIFIERS[case_id]["id"],
                "producerIds": ["observation-producer"],
                "serviceProducerIds": list(FIXTURE_CASE_SERVICES.get(case_id, ())),
            }
            for case_id in FIXTURE_CASE_IDS
        },
        "maximumReceiptAgeSeconds": 86_400,
        "maximumFutureSkewSeconds": 60,
    }
    path = root / "scripts" / "viventium" / "qa_release_attestation_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gate._load_external_release_attestation()._canonical_bytes(policy))


def _provision_external_fixture_bootstrap(
    gate,
    *,
    installed_root: Path,
    owner_state: Path,
    candidate_digest: str,
    authority,
) -> Path:
    """Simulate only OS ownership; publisher signatures and provider code are real."""

    root = installed_root.parent / f"{installed_root.name}-system-release-authority"
    root.mkdir(mode=0o755)
    publisher_key = _external_fixture_keys()["publisher"]
    publisher_identity = "publisher@fixture.example.invalid"
    publisher_fingerprint = _fixture_key_fingerprint(publisher_key)
    witness_identity = "viventium.fixture.system-witness.v1"
    provider_path = root / "provider.py"
    provider_path.write_text(EXTERNAL_AUTHORITY_PROVIDER_SOURCE, encoding="utf-8")
    signers_path = root / "publisher.allowed_signers"
    signers_path.write_text(
        f"{publisher_identity} {_fixture_public_key(publisher_key)}\n",
        encoding="utf-8",
    )
    witness_key = _external_fixture_keys()["witness"]
    witness_signers_path = root / "witness.allowed_signers"
    witness_signers_path.write_text(
        f"{witness_identity} {_fixture_public_key(witness_key)}\n",
        encoding="utf-8",
    )
    owner_binding = gate._qa_receipt_owner_binding(installed_root, owner_state)
    assert owner_binding
    bootstrap = {
        "contractVersion": 1,
        "purpose": EXTERNAL_AUTHORITY_BOOTSTRAP_PURPOSE,
        "candidateDigest": candidate_digest,
        "ownerBindingSha256": owner_binding,
        "policySha256": authority.expected_policy_sha256,
        "publisher": {
            "identity": publisher_identity,
            "fingerprint": publisher_fingerprint,
        },
        "provider": {
            "file": "provider.py",
            "sha256": hashlib.sha256(provider_path.read_bytes()).hexdigest(),
        },
        "witness": {
            "durability": gate.RELEASE_AUTHORITY_WITNESS_DURABILITY,
            "fingerprint": _fixture_key_fingerprint(witness_key),
            "identity": witness_identity,
            "protection": EXTERNAL_AUTHORITY_WITNESS_PROTECTION,
            "socket": gate.RELEASE_AUTHORITY_WITNESS_SOCKET_NAME,
        },
    }
    bootstrap_path = root / "bootstrap.json"
    bootstrap_bytes = gate._load_external_release_attestation()._canonical_bytes(
        bootstrap
    )
    bootstrap_path.write_bytes(bootstrap_bytes)
    signature_path = root / "bootstrap.sig"
    signature_path.write_text(
        _ExternalFixtureSigner(publisher_key).sign(
            bootstrap_bytes, EXTERNAL_AUTHORITY_BOOTSTRAP_NAMESPACE
        ),
        encoding="ascii",
    )
    for path in (
        provider_path,
        signers_path,
        witness_signers_path,
        bootstrap_path,
        signature_path,
    ):
        path.chmod(0o444)

    def fixture_system_directory() -> tuple[Path, int]:
        descriptor = os.open(
            root,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        return root.resolve(strict=True), descriptor

    def fixture_root_owned_stat(descriptor: int) -> SimpleNamespace:
        details = os.fstat(descriptor)
        return SimpleNamespace(
            st_mode=details.st_mode,
            st_uid=0,
            st_nlink=details.st_nlink,
            st_size=details.st_size,
            st_dev=details.st_dev,
            st_ino=details.st_ino,
            st_mtime_ns=details.st_mtime_ns,
            st_ctime_ns=details.st_ctime_ns,
        )

    # Unprivileged tests cannot install a real root-owned system provider. Only
    # that OS provisioning boundary is simulated; the production resolver,
    # publisher signatures, immutable modes, provider digest, and witness run.
    gate._open_system_release_authority_directory = fixture_system_directory
    gate._release_authority_fstat = fixture_root_owned_stat
    gate._test_external_release_provider_claim = {
        "contractVersion": 1,
        "candidateDigest": candidate_digest,
        "ownerBindingSha256": owner_binding,
        "policySha256": authority.expected_policy_sha256,
        "publisherIdentity": publisher_identity,
        "publisherFingerprint": publisher_fingerprint,
        "witnessIdentity": witness_identity,
    }
    gate._test_external_release_bootstrap_root = root
    return root


def _rewrite_signed_external_fixture_bootstrap(
    gate,
    update,
) -> None:
    root = gate._test_external_release_bootstrap_root
    bootstrap_path = root / "bootstrap.json"
    signature_path = root / "bootstrap.sig"
    bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    update(bootstrap)
    raw = gate._load_external_release_attestation()._canonical_bytes(bootstrap)
    bootstrap_path.chmod(0o644)
    bootstrap_path.write_bytes(raw)
    bootstrap_path.chmod(0o444)
    signature_path.chmod(0o644)
    signature_path.write_text(
        _ExternalFixtureSigner(_external_fixture_keys()["publisher"]).sign(
            raw, EXTERNAL_AUTHORITY_BOOTSTRAP_NAMESPACE
        ),
        encoding="ascii",
    )
    signature_path.chmod(0o444)


@atexit.register
def _stop_owner_processes() -> None:
    _stop_owner_processes_from(0)


def _stop_owner_processes_from(start: int) -> None:
    processes = OWNER_PROCESSES[start:]
    del OWNER_PROCESSES[start:]
    for process in processes:
        if process.poll() is not None:
            continue
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)


@pytest.fixture(autouse=True)
def _bounded_owner_process_lifetime():
    start = len(OWNER_PROCESSES)
    yield
    _stop_owner_processes_from(start)


@pytest.fixture(autouse=True)
def _deterministic_storage_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=40_000, free=60_000),
    )


def _healthy_readiness_facts(
    prompt_layers: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "contractVersion": 1,
        "promptLayers": prompt_layers or {
            "contractVersion": 1,
            "producerScope": "viventium.prompt_registry.v1",
            "status": "verified",
            "unknownLayerCount": 0,
            "unknownLayerNames": [],
            "promptCount": 2,
            "layerCount": 2,
            "layerNames": ["main", "worker"],
            "registryHash": "a" * 64,
        },
        "storagePressure": {
            "version": 1,
            "status": "healthy",
            "usedPercent": 40,
            "availableBytes": 20 * 1024 * 1024 * 1024,
            "thresholdPercent": 90,
            "warningMarginPercent": 10,
        },
    }


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "parallel_work_release_gate", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_fixture_root(
    root: Path,
    *,
    pwk_status: str = "PASS",
    rel_status: str = "PASS",
    telegram_status: str = "PASS",
    emotional_status: str = "PASS",
    emotional_delivery_status: str = "PASS",
    voice_worker_status: str = "PASS",
    file_worker_status: str = "PASS",
    available_default: str = "false",
    mode_default: str = "focused",
) -> None:
    files = {
        "qa/parallel-orchestrator/cases.md": f"""# Parallel Work QA Cases

| Case | Requirement | Evidence | Current status |
| --- | --- | --- | --- |
| `PWK-001` | One mission | Trace | PASS |

| Use Case ID | Natural user action | Requirement | Surface | Evidence | Result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-014` | Original sequence | Release gate | Telegram | Trace | One result | {pwk_status} |
""",
        "qa/release-readiness/cases.md": f"""# Release Readiness QA Cases

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `REL-001` | Hygiene | Safe | Repo | Scan | PASS |
| `REL-UC-004` | Claim gate | Honest | CLI | Gate | {rel_status} |
""",
        "qa/telegram-runtime/cases.md": f"""# Telegram Runtime Cases

## Case TR-026: Rapid Segments Supersede One Unfinished Reply

- **Last run:** {telegram_status}
""",
        "qa/emotional-cortex/cases.md": f"""# Feelings / Emotional Cortex QA Cases

| ID | Natural user action | Real surface | Supporting evidence | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- |
| `EMO-UC-047` | Ask how Main feels during Parallel Work | Telegram | Native receipt | Pinned state | {emotional_status} |
| `EMO-UC-048` | Recover one completed insight after delivery failure | Telegram and browser | Delivery ledger | One visible result | {emotional_delivery_status} |
""",
        "qa/modern-playground-voice/cases.md": f"""# Modern Playground Voice Cases

### MPV-061 Full Queen Bee And Worker Bee Voice Parity

- Last Run: {voice_worker_status}
""",
        "qa/telegram-document-attachments/cases.md": f"""# Telegram Document Attachments QA Cases

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `TGDOC-010` | Worker file parity | Exact files and results | Telegram and Web | Installed matrix | {file_worker_status} |
""",
        "config.schema.yaml": f"""properties:
  integrations:
    properties:
      glasshive:
        properties:
          orchestration:
            properties:
              available:
                type: boolean
                default: {available_default}
              default_mode:
                type: string
                default: {mode_default}
""",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            **dict(__import__("os").environ),
            "GIT_AUTHOR_NAME": "Release Fixture",
            "GIT_AUTHOR_EMAIL": "release-fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Release Fixture",
            "GIT_COMMITTER_EMAIL": "release-fixture@example.invalid",
        },
    )
    return completed.stdout.strip()


def _helper_source_hash(helper_root: Path) -> str:
    digest = hashlib.sha256()
    for relative in (
        "Package.swift",
        "Sources/ViventiumHelper/ViventiumHelperApp.swift",
        "Sources/ViventiumHelper/LifeSetup.swift",
        "Sources/ViventiumHelper/Resources/Info.plist",
    ):
        path = helper_root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _runtime_owner_payload(
    gate,
    *,
    process: subprocess.Popen,
    installed_root: Path,
    app_support: Path,
    runtime_dir: Path,
    process_cwd: Path,
    config_file: Path,
    components_lock_file: Path,
    launch_mode: str = "detached",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contractVersion": 1,
        "repoRoot": str(installed_root.resolve()),
        "appSupportDir": str(app_support.resolve()),
        "configFile": str(config_file.resolve()),
        "runtimeDir": str(runtime_dir.resolve()),
        "componentsLockFile": str(components_lock_file.resolve()),
        "runtimeProfile": "isolated",
        "command": "start",
        "ownerLaunchMode": launch_mode,
        "ownerPid": str(process.pid),
        "ownerExecutablePath": str(
            (installed_root / "bin" / "viventium").resolve()
        ),
        "ownerProcessCwd": str(process_cwd.resolve()),
        "ownerProcessStartedAt": " ".join(
            subprocess.run(
                ["ps", "-p", str(process.pid), "-o", "lstart="],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.split()
        ),
        "ownerProcessCommand": " ".join(
            subprocess.run(
                ["ps", "-p", str(process.pid), "-o", "command="],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.split()
        ),
    }
    payload["ownerBindingSha256"] = gate._owner_binding_sha256(payload)
    return payload


def _write_release_identity_fixture(
    root: Path,
    outside: Path,
    *,
    external_attestation: bool = False,
):
    gate = _load_module()
    nested = root / "components" / "worker"
    nested.mkdir(parents=True)
    (nested / "worker.txt").write_text("worker source\n", encoding="utf-8")
    _git(nested, "init", "-q")
    _git(nested, "add", "worker.txt")
    _git(nested, "commit", "-qm", "fixture worker")
    nested_revision = _git(nested, "rev-parse", "HEAD")

    (root / "components.lock.json").write_text(
        json.dumps(
            {
                "version": 1,
                "components": [
                    {
                        "name": "worker",
                        "path": "components/worker",
                        "origin": "https://example.invalid/worker.git",
                        "upstream": "",
                        "ref": nested_revision,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    helper = root / "apps" / "macos" / "ViventiumHelper"
    for relative in (
        "Package.swift",
        "Sources/ViventiumHelper/ViventiumHelperApp.swift",
        "Sources/ViventiumHelper/LifeSetup.swift",
        "Sources/ViventiumHelper/Resources/Info.plist",
    ):
        path = helper / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{relative}\n", encoding="utf-8")
    prebuilt = helper / "prebuilt"
    prebuilt.mkdir(parents=True)
    binary = prebuilt / "ViventiumHelper-universal"
    binary.write_bytes(b"synthetic prebuilt fixture\n")
    binary.chmod(0o755)
    (prebuilt / "source.sha256").write_text(
        _helper_source_hash(helper) + "\n", encoding="utf-8"
    )
    (prebuilt / "binary.sha256").write_text(
        hashlib.sha256(binary.read_bytes()).hexdigest() + "\n", encoding="utf-8"
    )
    owner_executable = root / "bin" / "viventium"
    owner_executable.parent.mkdir(parents=True, exist_ok=True)
    owner_executable.write_text("#!/bin/sh\nsleep 120\n", encoding="utf-8")
    owner_executable.chmod(0o755)
    command_contract = root / "scripts/viventium/runtime_owner_command_contract.json"
    command_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DETACHED_COMMAND_CONTRACT, command_contract)
    shutil.copy2(
        ROOT / "scripts/viventium/parallel_work_runtime_artifact_manifest.json",
        root / "scripts/viventium/parallel_work_runtime_artifact_manifest.json",
    )
    (root / ".gitignore").write_text(
        "viventium_v0_4/LibreChat/client/dist/\n"
        "viventium_v0_4/LibreChat/packages/api/dist/\n",
        encoding="utf-8",
    )
    running_service = root / "viventium_v0_4/LibreChat/api/server/index.js"
    running_service.parent.mkdir(parents=True, exist_ok=True)
    running_service.write_text("// installed service fixture\n", encoding="utf-8")
    runtime_loaded_files = {
        "scripts/viventium/feelings_qa_parent_control.py": "# fixture\n",
        "scripts/viventium/glasshive_qa_fixture.py": "# fixture\n",
        "scripts/viventium/glasshive_qa_parent_control.py": "# fixture\n",
        "scripts/viventium/librechat_emo_qa_fixture.js": "// fixture\n",
        "scripts/viventium/librechat_emo_qa_parent_control.py": "# fixture\n",
        "scripts/viventium/local_qa_runtime_control.py": "# fixture\n",
        "scripts/viventium/local_qa_service_ack.py": "# fixture\n",
        "scripts/viventium/parallel_work_qa_evidence.py": "# fixture\n",
        "scripts/viventium/parallel_work_release_gate.py": "# fixture\n",
        "scripts/viventium/release_claim_qa_fault.py": "# fixture\n",
        "scripts/viventium/telegram_qa_parent_control.py": "# fixture\n",
        "viventium_v0_4/viventium-librechat-start.sh": "#!/bin/sh\n",
        "viventium_v0_4/LibreChat/api/app/clients/tools/util/handleTools.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/cache/index.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/config/index.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/strategies/index.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/utils/logger.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/server/services/viventium/ReleaseGateConsumer.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/server/services/viventium/localQaServiceAck.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/server/routes/viventium/parallelWorkHealth.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/models/Conversation.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/db/ReleaseLedger.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/api/server/controllers/agents/client.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/packages/data-schemas/dist/index.js":
            "export const schema = true;\n",
        "viventium_v0_4/LibreChat/packages/data-provider/dist/index.js":
            "export const provider = true;\n",
        "viventium_v0_4/LibreChat/api/package.json":
            '{"name":"@viventium/api-fixture"}\n',
        "viventium_v0_4/LibreChat/api/typedefs.js":
            "module.exports = {};\n",
        "viventium_v0_4/LibreChat/package.json":
            '{"name":"viventium-librechat-fixture"}\n',
        "viventium_v0_4/LibreChat/client/package.json":
            '{"name":"viventium-client-fixture"}\n',
        "viventium_v0_4/LibreChat/package-lock.json":
            '{"lockfileVersion":3,"name":"viventium-librechat-fixture"}\n',
        "viventium_v0_4/LibreChat/packages/api/package.json":
            '{"name":"@viventium/api"}\n',
        "viventium_v0_4/LibreChat/packages/client/package.json":
            '{"name":"@viventium/client"}\n',
        "viventium_v0_4/LibreChat/packages/data-provider/package.json":
            '{"name":"@viventium/data-provider"}\n',
        "viventium_v0_4/LibreChat/packages/data-provider/react-query/package.json":
            '{"name":"@viventium/data-provider-react-query"}\n',
        "viventium_v0_4/LibreChat/packages/data-schemas/package.json":
            '{"name":"@viventium/data-schemas"}\n',
        "viventium_v0_4/LibreChat/api/server/utils/emails/inviteUser.handlebars":
            "<p>Fixture invitation</p>\n",
        "viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/api.py":
            "# fixture\n",
        "viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/local_qa_service_ack.py":
            "# fixture\n",
        "viventium_v0_4/telegram-viventium/TelegramVivBot/bot.py": "# fixture\n",
        "viventium_v0_4/telegram-viventium/TelegramVivBot/local_qa_service_ack.py":
            "# fixture\n",
        "viventium_v0_4/telegram-viventium/TelegramVivBot/utils/orchestration.py":
            "# fixture\n",
        "viventium_v0_4/telegram-viventium/TelegramVivBot/utils/tr026_local_qa.py":
            "# fixture\n",
    }
    for relative, content in runtime_loaded_files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    if external_attestation:
        _install_external_fixture_policy(root, gate)

    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture release")
    shutil.copytree(root, outside)
    app_support = outside.parent / f"{outside.name}-app-support"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    runtime.chmod(0o700)
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_PARALLEL_WORK_AVAILABLE=false\n"
        "VIVENTIUM_PARALLEL_WORK_DEFAULT_MODE=focused\n",
        encoding="utf-8",
    )
    (runtime / "librechat.yaml").write_text("version: 1.2.1\n", encoding="utf-8")
    frontend_build = outside / "viventium_v0_4/LibreChat/client/dist/index.html"
    frontend_build.parent.mkdir(parents=True, exist_ok=True)
    frontend_build.write_text("<main>fixture</main>\n", encoding="utf-8")
    api_build = outside / "viventium_v0_4/LibreChat/packages/api/dist/index.js"
    api_build.parent.mkdir(parents=True, exist_ok=True)
    api_build.write_text("export const fixture = true;\n", encoding="utf-8")
    config_file = app_support / "config.yaml"
    config_file.write_text("version: 1\n", encoding="utf-8")
    prompt_bundle_path = runtime / "prompt-bundle.json"
    prompt_bundle = {
        "schema_version": 1,
        "prompt_count": 2,
        "prompts": {
            "main.answer": {
                "content_hash": "a1",
                "metadata": {"owner_layer": "main", "status": "active", "version": 1},
            },
            "worker.answer": {
                "content_hash": "b2",
                "metadata": {"owner_layer": "worker", "status": "active", "version": 1},
            },
        },
    }
    prompt_bundle_path.write_text(json.dumps(prompt_bundle) + "\n", encoding="utf-8")
    prompt_layers = gate.build_prompt_registry_facts(prompt_bundle)
    (runtime / "parallel-work-readiness-facts.json").write_text(
        json.dumps(_healthy_readiness_facts(prompt_layers)) + "\n",
        encoding="utf-8",
    )
    command_contract = json.loads(command_contract.read_text(encoding="utf-8"))
    command_values = {
        "ownerExecutablePath": str((outside / "bin" / "viventium").resolve()),
        "appSupportDir": str(app_support.resolve()),
        "configFile": str(config_file.resolve()),
        "runtimeDir": str(runtime.resolve()),
        "componentsLockFile": str((outside / "components.lock.json").resolve()),
    }
    owner_argv = [
        str(token).format(**command_values)
        for token in command_contract["detached"]["argvTemplate"]
    ]
    owner_process = subprocess.Popen(
        owner_argv,
        cwd=outside,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    OWNER_PROCESSES.append(owner_process)
    owner_state = app_support / "state" / "runtime" / "isolated" / "stack-owner.json"
    owner_state.parent.mkdir(parents=True)
    owner_state.write_text(
        json.dumps(
            _runtime_owner_payload(
                gate,
                process=owner_process,
                installed_root=outside,
                app_support=app_support,
                runtime_dir=runtime,
                process_cwd=outside,
                config_file=config_file,
                components_lock_file=outside / "components.lock.json",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    owner_state.chmod(0o600)
    gate._test_installed_root = outside
    gate._test_runtime_owner_state = owner_state
    identity = gate.build_release_artifact_identity(
        root, prompt_bundle_path, outside, owner_state
    )
    if external_attestation:
        policy_path = (
            outside / "scripts" / "viventium" / "qa_release_attestation_policy.json"
        )
        external_authority = gate.ExternalReleaseAttestationAuthority(
            expected_policy_sha256=hashlib.sha256(policy_path.read_bytes()).hexdigest(),
            ledger_path=runtime / gate.QA_RELEASE_ATTESTATION_LEDGER_NAME,
            ledger_witness=_ExternalFixtureWitness(),
        )
        candidate_digest, _artifact_digest = gate._qa_candidate_digests(identity)
        gate._test_external_release_authority = external_authority
        gate._test_external_release_policy = (
            gate._load_external_release_attestation().load_trust_policy(
                outside,
                expected_policy_sha256=external_authority.expected_policy_sha256,
                expected_candidate_digest=candidate_digest,
            )
        )
        _provision_external_fixture_bootstrap(
            gate,
            installed_root=outside,
            owner_state=owner_state,
            candidate_digest=candidate_digest,
            authority=external_authority,
        )
    return gate, prompt_bundle_path, identity, prompt_layers


def _owner_state_path(prompt_bundle_path: Path) -> Path:
    return (
        prompt_bundle_path.parent.parent
        / "state"
        / "runtime"
        / "isolated"
        / "stack-owner.json"
    )


def _write_runtime_claim_files(
    prompt_bundle_path: Path,
    readiness_facts: dict[str, object],
    artifact_identity: dict[str, object],
    qa_case_receipts: dict[str, object] | None = None,
) -> None:
    runtime = prompt_bundle_path.parent
    (runtime / "parallel-work-readiness-facts.json").write_text(
        json.dumps(readiness_facts) + "\n", encoding="utf-8"
    )
    (runtime / "parallel-work-artifact-identity.json").write_text(
        json.dumps(artifact_identity) + "\n", encoding="utf-8"
    )
    if qa_case_receipts is not None:
        (runtime / "parallel-work-qa-case-receipts.json").write_text(
            json.dumps(qa_case_receipts) + "\n", encoding="utf-8"
        )


def _qa_case_receipts(
    gate,
    artifact_identity: dict[str, object],
    *,
    run_at: datetime | None = None,
    authenticated: bool = True,
    externally_authenticated: bool = False,
) -> dict[str, object]:
    candidate_digest, artifact_digest = gate._qa_candidate_digests(artifact_identity)
    _register_fixture_semantic_verifiers(gate)
    if externally_authenticated and not authenticated:
        raise ValueError("external release receipts require authenticated observations")
    timestamp = (run_at or datetime.now(timezone.utc)).isoformat()
    authority = (
        gate._qa_receipt_attestation_authority(
            gate._test_installed_root,
            gate._test_runtime_owner_state,
            create=True,
        )
        if authenticated
        else None
    )
    if authenticated:
        assert authority is not None
    receipts: list[dict[str, object]] = []
    for case_id in FIXTURE_CASE_IDS:
        receipt: dict[str, object] = {
            "caseId": case_id,
            "runAt": timestamp,
            "candidateDigest": candidate_digest,
            "artifactDigest": artifact_digest,
            "evidenceDigest": hashlib.sha256(
                f"synthetic:{case_id}".encode()
            ).hexdigest(),
            "surface": "voice" if case_id == "MPV-061" else "telegram",
            "status": "PASS",
        }
        if case_id in gate.QA_RECEIPT_SERVICE_ACK_CASES:
            receipt["serviceAckDigest"] = (
                "sha256:"
                + (
                    hashlib.sha256(f"verified:{case_id}".encode()).hexdigest()
                    if authenticated
                    else "f" * 64
                )
            )
            if authenticated:
                receipt["serviceAckSessionRef"] = (
                    "qa_" + hashlib.sha256(case_id.encode()).hexdigest()[:24]
                )
        if authenticated:
            assert authority is not None
            receipt.update(
                {
                    "ownerBindingSha256": authority[1],
                    "receiptNonce": hashlib.sha256(
                        f"nonce:{case_id}:{timestamp}".encode()
                    ).hexdigest()[:32],
                    "verifierId": gate.REGISTERED_SEMANTIC_VERIFIERS[case_id]["id"],
                    "verifierManifestSha256": hashlib.sha256(
                        f"manifest:{case_id}".encode()
                    ).hexdigest(),
                }
            )
            if externally_authenticated:
                attestation = gate._load_external_release_attestation()
                policy = gate._test_external_release_policy
                signing_keys = _external_fixture_keys()
                services = []
                if case_id in FIXTURE_CASE_SERVICES:
                    session_ref = str(receipt["serviceAckSessionRef"])
                    for service_id in FIXTURE_CASE_SERVICES[case_id]:
                        signed_service = attestation.sign_service_acknowledgement(
                            {
                                "caseId": case_id,
                                "surface": receipt["surface"],
                                "candidateDigest": candidate_digest,
                                "artifactDigest": artifact_digest,
                                "ownerBindingSha256": authority[1],
                                "serviceId": service_id,
                                "sessionRef": session_ref,
                                "acknowledgedAt": timestamp,
                                "acknowledgementDigest": "sha256:"
                                + hashlib.sha256(
                                    f"fixture-service:{case_id}:{service_id}".encode()
                                ).hexdigest(),
                                "processIdentityDigest": hashlib.sha256(
                                    f"fixture-process:{case_id}:{service_id}".encode()
                                ).hexdigest(),
                            },
                            producer_id=service_id,
                            policy=policy,
                            signer=_ExternalFixtureSigner(signing_keys[service_id]),
                            now=datetime.fromisoformat(timestamp),
                        )
                        services.append(signed_service)
                    receipt["serviceAckDigest"] = (
                        attestation.service_acknowledgement_digest(services)
                    )
                observation = {
                    "caseId": case_id,
                    "surface": receipt["surface"],
                    "candidateDigest": candidate_digest,
                    "artifactDigest": artifact_digest,
                    "ownerBindingSha256": authority[1],
                    "evidenceDigest": receipt["evidenceDigest"],
                    "receiptNonce": receipt["receiptNonce"],
                    "verifierId": receipt["verifierId"],
                    "verifierManifestSha256": receipt["verifierManifestSha256"],
                    "observedAt": timestamp,
                    "observationNonce": hashlib.sha256(
                        f"fixture-observation:{case_id}:{timestamp}".encode()
                    ).hexdigest()[:32],
                    "serviceAckDigest": receipt.get("serviceAckDigest", ""),
                    "serviceAckSessionRef": receipt.get("serviceAckSessionRef", ""),
                }
                producer = attestation.sign_producer_observation(
                    observation,
                    producer_id="observation-producer",
                    policy=policy,
                    signer=_ExternalFixtureSigner(signing_keys["observation-producer"]),
                    now=datetime.fromisoformat(timestamp),
                )
                external = gate._test_external_release_authority
                receipt = attestation.issue_release_receipt(
                    receipt,
                    producer_attestations=[producer],
                    service_acknowledgements=services,
                    policy=policy,
                    signer=_ExternalFixtureSigner(signing_keys["publisher"]),
                    ledger_path=external.ledger_path,
                    ledger_witness=external.ledger_witness,
                    now=datetime.fromisoformat(timestamp),
                )
            else:
                receipt["attestation"] = gate._sign_qa_receipt(receipt, authority)
        receipts.append(receipt)
    return {
        "contractVersion": 1,
        "receipts": receipts,
    }


def test_detached_owner_command_matches_shared_cross_language_contract(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    contract = json.loads(DETACHED_COMMAND_CONTRACT.read_text(encoding="utf-8"))
    repo = tmp_path / "Installed Viventium"
    app_support = tmp_path / "Application Support" / "Viventium"
    runtime = app_support / "runtime"
    executable = repo / "bin" / "viventium"
    config = app_support / "config.yaml"
    lock = repo / "components.lock.json"
    for path in (runtime, executable.parent):
        path.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    installed_contract = (
        repo / "scripts/viventium/runtime_owner_command_contract.json"
    )
    installed_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DETACHED_COMMAND_CONTRACT, installed_contract)
    config.write_text("version: 1\n", encoding="utf-8")
    lock.write_text('{"version": 1}\n', encoding="utf-8")
    values = {
        "ownerExecutablePath": str(executable.resolve()),
        "appSupportDir": str(app_support.resolve()),
        "configFile": str(config.resolve()),
        "runtimeDir": str(runtime.resolve()),
        "componentsLockFile": str(lock.resolve()),
    }
    argv = [
        str(token).format(**values)
        for token in contract["detached"]["argvTemplate"]
    ]
    detached = " ".join(argv)

    for wrapper in contract["processWrappers"]:
        assert gate._owner_command_executes(
            f"{wrapper}{detached}",
            executable.resolve(),
            repo.resolve(),
            "start",
            app_support=app_support.resolve(),
            config_file=config.resolve(),
            runtime_dir=runtime.resolve(),
            components_lock_file=lock.resolve(),
            launch_mode="detached",
        )
    for rejected in (
        f"{sys.executable} -c import-time {executable.resolve()} {detached}",
        detached.replace(str(executable.resolve()), f"{executable.resolve()}-lookalike", 1),
        detached.replace(str(runtime.resolve()), str(app_support.resolve()), 1),
        detached.removesuffix(" --restart"),
        f"{detached} --forged-flag",
    ):
        assert not gate._owner_command_executes(
            rejected,
            executable.resolve(),
            repo.resolve(),
            "start",
            app_support=app_support.resolve(),
            config_file=config.resolve(),
            runtime_dir=runtime.resolve(),
            components_lock_file=lock.resolve(),
            launch_mode="detached",
        )

    launcher_source = (ROOT / "bin/viventium").read_text(encoding="utf-8")
    assert "runtime_owner_command_contract.json" in launcher_source
    assert 'contract["detached"]["argvTemplate"]' in launcher_source
    # Exercise the CLI's contract validation without launching a runtime.
    validation = launcher_source.split("canonical_detached = [", 1)[1].split(
        "compat_launcher =", 1
    )[0]
    validation = "canonical_detached = [" + validation
    exec(compile(validation, "bin/viventium contract validation", "exec"), {"contract": contract})
    contract["attached"]["flagOptions"].append("--forged-flag")
    with pytest.raises(SystemExit, match="Unsupported runtime owner command contract"):
        exec(compile(validation, "bin/viventium contract validation", "exec"), {"contract": contract})


def test_process_cwd_prefers_macos_kernel_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    expected = tmp_path.resolve()

    monkeypatch.setattr(gate.sys, "platform", "darwin")
    monkeypatch.setattr(gate, "_macos_process_cwd", lambda pid: expected)

    def reject_lsof(*_args, **_kwargs):
        raise AssertionError("macOS owner validation must not depend on lsof")

    monkeypatch.setattr(gate.subprocess, "run", reject_lsof)

    assert gate._process_cwd(os.getpid()) == expected


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS kernel process API")
def test_macos_kernel_process_reader_returns_current_working_directory() -> None:
    gate = _load_module()

    assert gate._macos_process_cwd(os.getpid()) == Path.cwd().resolve()


def test_attached_owner_accepts_exact_documented_restart_and_rejects_unknown_args(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    contract = json.loads(DETACHED_COMMAND_CONTRACT.read_text(encoding="utf-8"))
    repo = tmp_path / "Installed Viventium"
    app_support = tmp_path / "Application Support" / "Viventium"
    runtime = app_support / "runtime"
    executable = repo / "bin" / "viventium"
    config = app_support / "config.yaml"
    lock = repo / "components.lock.json"
    for path in (runtime, executable.parent):
        path.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    installed_contract = repo / "scripts/viventium/runtime_owner_command_contract.json"
    installed_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DETACHED_COMMAND_CONTRACT, installed_contract)
    config.write_text("version: 1\n", encoding="utf-8")
    lock.write_text('{"version": 1}\n', encoding="utf-8")
    values = {
        "ownerExecutablePath": str(executable.resolve()),
        "appSupportDir": str(app_support.resolve()),
        "configFile": str(config.resolve()),
        "runtimeDir": str(runtime.resolve()),
        "componentsLockFile": str(lock.resolve()),
        "command": "start",
    }
    commands = [
        " ".join(str(token).format(**values) for token in template)
        for template in contract["attached"]["argvTemplates"]
    ]
    restart_commands = [command for command in commands if command.endswith(" --restart")]

    assert len(restart_commands) == 2
    for command in restart_commands:
        assert gate._owner_command_executes(
            command,
            executable.resolve(),
            repo.resolve(),
            "start",
            app_support=app_support.resolve(),
            config_file=config.resolve(),
            runtime_dir=runtime.resolve(),
            components_lock_file=lock.resolve(),
            launch_mode="attached",
        )
        assert not gate._owner_command_executes(
            f"{command} --forged-flag",
            executable.resolve(),
            repo.resolve(),
            "start",
            app_support=app_support.resolve(),
            config_file=config.resolve(),
            runtime_dir=runtime.resolve(),
            components_lock_file=lock.resolve(),
            launch_mode="attached",
        )

    for relative_command in (
        "bash bin/viventium start --restart",
        "bash ./bin/viventium start --restart",
    ):
        assert gate._owner_command_executes(
            relative_command,
            executable.resolve(),
            repo.resolve(),
            "start",
            app_support=app_support.resolve(),
            config_file=config.resolve(),
            runtime_dir=runtime.resolve(),
            components_lock_file=lock.resolve(),
            launch_mode="attached",
        )

    for rejected_command in (
        "bash ../bin/viventium start --restart",
        "bash bin/viventium-lookalike start --restart",
        "bash bin/viventium start --restart --forged-flag",
    ):
        assert not gate._owner_command_executes(
            rejected_command,
            executable.resolve(),
            repo.resolve(),
            "start",
            app_support=app_support.resolve(),
            config_file=config.resolve(),
            runtime_dir=runtime.resolve(),
            components_lock_file=lock.resolve(),
            launch_mode="attached",
        )



@pytest.mark.parametrize("with_lock", [False, True])
@pytest.mark.parametrize("runtime_profile", ["isolated", "compat"])
def test_attached_dev_owner_accepts_supported_launch_options_and_rejects_injection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_lock: bool,
    runtime_profile: str,
) -> None:
    gate = _load_module()
    repo = tmp_path / "Installed Viventium"
    app_support = tmp_path / "Application Support" / "Viventium"
    runtime = app_support / "runtime"
    executable = repo / "bin/viventium"
    config = app_support / "config.yaml"
    lock = repo / "components.lock.json"
    runtime.mkdir(parents=True)
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/bash\nwhile :; do sleep 1; done\n", encoding="utf-8")
    executable.chmod(0o755)
    config.write_text("version: 1\n", encoding="utf-8")
    lock.write_text('{"version": 1}\n', encoding="utf-8")
    contract_path = repo / "scripts/viventium/runtime_owner_command_contract.json"
    contract_path.parent.mkdir(parents=True)
    shutil.copy2(DETACHED_COMMAND_CONTRACT, contract_path)
    preamble = [
        str(executable.resolve()),
        "--app-support-dir", str(app_support.resolve()),
        "--config-file", str(config.resolve()),
        "--runtime-dir", str(runtime.resolve()),
    ]
    if with_lock:
        preamble += ["--lock-file", str(lock.resolve())]
    options = [
        "--restart", "--skip-telegram", "--skip-v1-agent", "--skip-livekit",
        "--skip-playground", "--skip-voice-gateway", "--no-bootstrap",
        "--profile=" + runtime_profile,
    ]
    argv = [*preamble, "start", *options]
    process = subprocess.Popen(argv, cwd=repo, start_new_session=True)
    OWNER_PROCESSES.append(process)
    state = app_support / "state/runtime" / runtime_profile / "stack-owner.json"
    state.parent.mkdir(parents=True)
    payload = _runtime_owner_payload(
        gate, process=process, installed_root=repo, app_support=app_support,
        runtime_dir=runtime, process_cwd=repo, config_file=config,
        components_lock_file=lock, launch_mode="attached",
    )
    payload["runtimeProfile"] = runtime_profile
    payload["ownerBindingSha256"] = gate._owner_binding_sha256(payload)
    state.write_text(json.dumps(payload), encoding="utf-8")
    state.chmod(0o600)
    assert gate._runtime_owner_state_proves_active(repo, state)
    # A correctly rehashed receipt cannot relabel a live profile selector.
    other_profile = "compat" if runtime_profile == "isolated" else "isolated"
    other_state = app_support / "state/runtime" / other_profile / "stack-owner.json"
    other_state.parent.mkdir(parents=True)
    forged = {**payload, "runtimeProfile": other_profile}
    forged["ownerBindingSha256"] = gate._owner_binding_sha256(forged)
    other_state.write_text(json.dumps(forged), encoding="utf-8")
    other_state.chmod(0o600)
    assert not gate._runtime_owner_state_proves_active(repo, other_state)

    kwargs = dict(
        app_support=app_support.resolve(), config_file=config.resolve(),
        runtime_dir=runtime.resolve(), components_lock_file=lock.resolve(),
        launch_mode="attached", runtime_profile=runtime_profile,
    )
    live_image = Path("/bin/bash").resolve()
    # Both representations must enforce every token, including spaces inside paths.
    candidates = [
        ([*preamble, "start"], True),
        ([*preamble, "start", "--fast", "--modern-playground"], True),
        ([*preamble, "start", "--profile", runtime_profile], True),
        ([*preamble, "start", "--profile=" + runtime_profile], True),
        ([*preamble, "start", "--runtime-profile", runtime_profile], True),
        ([*preamble, "start", "--profile", "compat" if runtime_profile == "isolated" else "isolated"], False),
        ([*preamble, "start", "--profile=compat" if runtime_profile == "isolated" else "--profile=isolated"], False),
        ([*preamble, "start", "--runtime-profile", "compat" if runtime_profile == "isolated" else "isolated"], False),
        ([*argv, "--unknown-flag"], False),
        ([*argv, ";", "touch", "unexpected"], False),
        ([*argv, "$(touch unexpected)"], False),
        ([*argv, "--config-file", str(tmp_path / "other.yaml")], False),
        ([*argv, "--lock-file", str(tmp_path / "other.lock")], False),
        ([*argv, "--profile=unknown"], False),
        ([*argv, "--profile"], False),
        ([*argv, "--runtime-profile=" + runtime_profile], False),
        ([*argv, "--skip-telegram=anything"], False),
        ([*argv, "--stop"], False),
        ([*argv, "--help"], False),
        ([*argv, "launch"], False),
        ([str(executable.resolve()) + "-lookalike", *argv[1:]], False),
        ([*argv[:4], str(tmp_path / "other.yaml"), *argv[5:]], False),
    ]
    for candidate, expected in candidates:
        monkeypatch.setattr(
            gate, "_live_process_image_and_argv",
            lambda _pid, candidate=candidate: (live_image, ("bash", *candidate)),
        )
        assert gate._owner_command_executes(
            "bash " + " ".join(candidate), executable.resolve(), repo.resolve(),
            "start", **kwargs,
        ) is expected, candidate
        assert gate._owner_process_image_executes(
            process.pid, executable.resolve(), repo.resolve(), "start", **kwargs,
        ) is expected, candidate


def test_attached_owner_typed_argv_accepts_only_verified_repo_relative_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    gate = _load_module()
    repo = tmp_path / "Installed Viventium"
    app_support = tmp_path / "Application Support" / "Viventium"
    runtime = app_support / "runtime"
    executable = repo / "bin" / "viventium"
    config = app_support / "config.yaml"
    lock = repo / "components.lock.json"
    for path in (runtime, executable.parent):
        path.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    installed_contract = repo / "scripts/viventium/runtime_owner_command_contract.json"
    installed_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DETACHED_COMMAND_CONTRACT, installed_contract)
    config.write_text("version: 1\n", encoding="utf-8")
    lock.write_text('{"version": 1}\n', encoding="utf-8")
    live_argv = ("bash", "bin/viventium", "start", "--restart")
    monkeypatch.setattr(
        gate,
        "_live_process_image_and_argv",
        lambda _pid: (Path(shutil.which("bash") or "/bin/bash").resolve(), live_argv),
    )

    assert gate._owner_process_image_executes(
        42,
        executable.resolve(),
        repo.resolve(),
        "start",
        app_support=app_support.resolve(),
        config_file=config.resolve(),
        runtime_dir=runtime.resolve(),
        components_lock_file=lock.resolve(),
        launch_mode="attached",
    )

    live_argv = ("bash", "../bin/viventium", "start", "--restart")
    assert not gate._owner_process_image_executes(
        42,
        executable.resolve(),
        repo.resolve(),
        "start",
        app_support=app_support.resolve(),
        config_file=config.resolve(),
        runtime_dir=runtime.resolve(),
        components_lock_file=lock.resolve(),
        launch_mode="attached",
    )


def test_macos_relative_process_image_resolves_against_live_process_cwd(
    tmp_path: Path,
    monkeypatch,
) -> None:
    gate = _load_module()
    process_cwd = tmp_path / "telegram"
    relative_executable = Path(".venv/bin/python")
    executable = process_cwd / relative_executable
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"python")

    monkeypatch.setattr(gate, "_macos_process_cwd", lambda _pid: process_cwd)

    assert gate._resolve_macos_process_executable(
        42, str(relative_executable)
    ) == executable.resolve()
    assert gate._resolve_macos_process_executable(
        42, str(executable.resolve())
    ) == executable.resolve()

    monkeypatch.setattr(gate, "_macos_process_cwd", lambda _pid: None)
    assert gate._resolve_macos_process_executable(42, str(relative_executable)) is None


def test_ps_command_variant_accepted_false(tmp_path: Path) -> None:
    gate = _load_module()
    repo = tmp_path / "Installed Viventium"
    app_support = tmp_path / "Application Support" / "Viventium"
    runtime = app_support / "runtime"
    executable = repo / "bin" / "viventium"
    config = app_support / "config.yaml"
    lock = repo / "components.lock.json"
    for path in (runtime, executable.parent):
        path.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    contract_path = repo / "scripts/viventium/runtime_owner_command_contract.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DETACHED_COMMAND_CONTRACT, contract_path)
    config.write_text("version: 1\n", encoding="utf-8")
    lock.write_text('{"version": 1}\n', encoding="utf-8")
    values = {
        "ownerExecutablePath": str(executable.resolve()),
        "appSupportDir": str(app_support.resolve()),
        "configFile": str(config.resolve()),
        "runtimeDir": str(runtime.resolve()),
        "componentsLockFile": str(lock.resolve()),
    }
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    command = " ".join(
        str(token).format(**values)
        for token in contract["detached"]["argvTemplate"]
    )

    assert gate._owner_command_executes(
        f"{command} --forged-flag",
        executable.resolve(),
        repo.resolve(),
        "start",
        app_support=app_support.resolve(),
        config_file=config.resolve(),
        runtime_dir=runtime.resolve(),
        components_lock_file=lock.resolve(),
        launch_mode="detached",
    ) is False


def test_typed_argv_variant_accepted_false(tmp_path: Path, monkeypatch) -> None:
    gate = _load_module()
    repo = tmp_path / "Installed Viventium"
    app_support = tmp_path / "Application Support" / "Viventium"
    runtime = app_support / "runtime"
    executable = repo / "bin" / "viventium"
    config = app_support / "config.yaml"
    lock = repo / "components.lock.json"
    for path in (runtime, executable.parent):
        path.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    contract_path = repo / "scripts/viventium/runtime_owner_command_contract.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DETACHED_COMMAND_CONTRACT, contract_path)
    config.write_text("version: 1\n", encoding="utf-8")
    lock.write_text('{"version": 1}\n', encoding="utf-8")
    values = {
        "ownerExecutablePath": str(executable.resolve()),
        "appSupportDir": str(app_support.resolve()),
        "configFile": str(config.resolve()),
        "runtimeDir": str(runtime.resolve()),
        "componentsLockFile": str(lock.resolve()),
    }
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    argv = tuple(
        str(token).format(**values)
        for token in contract["detached"]["argvTemplate"]
    ) + ("--forged-flag",)
    monkeypatch.setattr(
        gate,
        "_live_process_image_and_argv",
        lambda _pid: (executable.resolve(), argv),
    )

    assert gate._owner_process_image_executes(
        42,
        executable.resolve(),
        repo.resolve(),
        "start",
        app_support=app_support.resolve(),
        config_file=config.resolve(),
        runtime_dir=runtime.resolve(),
        components_lock_file=lock.resolve(),
        launch_mode="detached",
    ) is False


def test_release_gate_fails_when_any_required_case_is_open(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(
        tmp_path,
        pwk_status="PARTIAL — fail-closed automation exists; exact installed path remains",
        rel_status="NOT RUN",
    )

    result = gate.evaluate_release_gate(
        tmp_path,
        mode="release",
        readiness_facts=_healthy_readiness_facts(),
    )

    assert result.release_ready is False
    assert result.exposure_allowed is False
    assert result.label == "NOT READY"
    assert {item.case_id for item in result.open_gates} == {
        "PWK-001",
        "PWK-UC-014",
        "REL-001",
        "REL-UC-004",
        "TR-026",
        "EMO-UC-047",
        "EMO-UC-048",
        "MPV-061",
        "TGDOC-010",
    }
    assert {item.case_id: item.status for item in result.open_gates}[
        "PWK-UC-014"
    ] == "PARTIAL"


def test_production_resolver_rejects_publisher_verified_fixture_without_root_owned_witness(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = (
        _write_release_identity_fixture(
            root,
            installed,
            external_attestation=True,
        )
    )
    candidate_digest, _artifact_digest = gate._qa_candidate_digests(identity)

    resolved = gate._resolve_external_release_attestation_authority(
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        candidate_digest=candidate_digest,
    )

    assert gate._resolve_external_release_attestation_authority.__module__ == gate.__name__
    assert gate._test_external_release_bootstrap_root != (
        gate.RELEASE_AUTHORITY_SYSTEM_DIRECTORY
    )
    assert resolved is None


def test_release_evaluation_blocks_without_real_production_witness_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root,
        installed,
        external_attestation=True,
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert gate._resolve_external_release_attestation_authority.__module__ == gate.__name__
    assert result.release_ready is False
    assert result.label == "NOT READY"
    assert result.qa_receipt_summary["status"] == "blocked"
    assert {
        item.detail for item in result.open_gates
    } == {"qa_receipt_external_attestation_missing"}


def test_release_rejects_publisher_wrapped_caller_owned_dictionary_witness(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root,
        installed,
        external_attestation=True,
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert isinstance(gate._test_external_release_authority.ledger_witness.heads, dict)
    assert result.release_ready is False
    assert result.qa_receipt_summary["status"] == "blocked"
    assert {
        item.detail for item in result.open_gates
    } == {"qa_receipt_external_attestation_missing"}


def test_release_rejects_caller_controlled_witness_and_ledger_rollback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root,
        installed,
        external_attestation=True,
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)
    authority = gate._test_external_release_authority
    ledger_before_revocation = authority.ledger_path.read_bytes()
    caller_owned_heads_before_revocation = dict(authority.ledger_witness.heads)
    _candidate_digest, artifact_digest = gate._qa_candidate_digests(identity)
    owner_binding = gate._qa_receipt_owner_binding(
        installed, _owner_state_path(prompt_bundle_path)
    )

    gate._load_external_release_attestation().record_case_outcome(
        case_id="TR-026",
        status="REVOKED",
        owner_binding_sha256=owner_binding,
        artifact_digest=artifact_digest,
        policy=gate._test_external_release_policy,
        signer=_ExternalFixtureSigner(_external_fixture_keys()["publisher"]),
        ledger_path=authority.ledger_path,
        ledger_witness=authority.ledger_witness,
    )
    authority.ledger_path.write_bytes(ledger_before_revocation)
    authority.ledger_witness.heads.clear()
    authority.ledger_witness.heads.update(caller_owned_heads_before_revocation)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert result.release_ready is False
    assert result.qa_receipt_summary["status"] == "blocked"


@pytest.mark.parametrize("mode", ("default", "release"))
def test_release_rejects_test_injected_authority_even_when_publisher_verified(
    tmp_path: Path,
    mode: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root,
        installed,
        external_attestation=True,
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)
    candidate_digest, _artifact_digest = gate._qa_candidate_digests(identity)
    resolved = gate._resolve_external_release_attestation_authority(
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        candidate_digest=candidate_digest,
    )
    assert resolved is None

    result = gate.evaluate_release_gate(
        root,
        mode=mode,
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
        external_attestation_authority=gate._test_external_release_authority,
    )

    assert result.release_ready is False
    assert result.label == "NOT READY"


def test_injected_witness_is_available_only_to_explicit_pre_gate_local_qa(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root,
        installed,
        external_attestation=True,
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)

    result = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
        external_attestation_authority=gate._test_external_release_authority,
    )

    assert result.qa_receipt_summary["status"] == "verified"
    assert result.open_gates == ()
    assert result.release_ready is False
    assert result.label == "PRE-GATE / NOT READY"


def test_protected_witness_requires_authenticated_signed_monotonic_external_checkpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    witness = _test_only_authenticated_witness(gate, monkeypatch)
    attestation = gate._load_external_release_attestation()
    scope = "c" * 64
    first = attestation.LedgerHead(sequence=1, entry_digest="d" * 64)
    second = attestation.LedgerHead(sequence=2, entry_digest="e" * 64)

    assert witness.prove() is True
    assert witness.current(scope) is None
    assert witness.advance(scope, expected=None, head=first) is True
    assert witness.current(scope) == first
    assert witness.advance(scope, expected=None, head=first) is False
    assert witness.advance(scope, expected=first, head=second) is True
    assert witness.current(scope) == second

    with pytest.raises(RuntimeError, match="monotonic"):
        witness.advance(scope, expected=second, head=first)


def test_protected_witness_peer_identity_comes_from_real_kernel_credentials() -> None:
    gate = _load_module()

    left, right = gate.socket.socketpair()
    try:
        assert gate._release_authority_socket_peer_uid(left) == os.getuid()
        assert gate._release_authority_socket_peer_uid(right) == os.getuid()
    finally:
        left.close()
        right.close()


@pytest.mark.parametrize(
    ("endpoint_owner_uid", "peer_uid"),
    (
        (os.getuid(), 0),
        (0, os.getuid()),
    ),
    ids=("owner-controlled-endpoint", "owner-controlled-peer"),
)
def test_protected_witness_rejects_owner_controlled_endpoint_or_service(
    monkeypatch: pytest.MonkeyPatch,
    endpoint_owner_uid: int,
    peer_uid: int,
) -> None:
    gate = _load_module()
    witness = _test_only_authenticated_witness(
        gate,
        monkeypatch,
        endpoint_owner_uid=endpoint_owner_uid,
        peer_uid=peer_uid,
    )

    with pytest.raises(RuntimeError, match="root-owned"):
        witness.prove()


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("candidateDigest", "f" * 64),
        ("ownerBindingSha256", "f" * 64),
        ("nonce", "f" * 64),
        ("requestDigest", "f" * 64),
        ("scope", "f" * 64),
        ("operation", "current"),
        ("witnessIdentity", "caller-controlled-witness"),
        ("durability", "caller-owned-dictionary-v1"),
        ("accepted", "true"),
    ),
)
def test_protected_witness_rejects_signed_replay_and_mismatched_external_claims(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: object,
) -> None:
    gate = _load_module()
    witness = _test_only_authenticated_witness(
        gate,
        monkeypatch,
        mutate=lambda response: response.update({field: replacement}),
    )

    with pytest.raises(RuntimeError, match="does not match"):
        witness.prove()


def test_protected_witness_rejects_a_publisher_or_caller_forged_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    witness = _test_only_authenticated_witness(
        gate,
        monkeypatch,
        signing_key=_external_fixture_keys()["publisher"],
    )

    with pytest.raises(RuntimeError, match="signature is invalid"):
        witness.prove()


def test_release_rejects_caller_supplied_authority_without_system_trust_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root,
        installed,
        external_attestation=True,
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)
    (gate._test_external_release_bootstrap_root / "bootstrap.json").unlink()

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
        external_attestation_authority=gate._test_external_release_authority,
    )

    assert result.release_ready is False
    assert result.label == "NOT READY"
    assert {
        item.detail for item in result.open_gates
    } == {"qa_receipt_external_attestation_missing"}


@pytest.mark.parametrize(
    "failure",
    (
        "absent_bootstrap",
        "same_user_authority",
        "mutable_bootstrap",
        "mutable_publisher_pin",
        "writable_provider",
        "wrong_candidate",
        "wrong_owner",
        "bad_publisher_signature",
        "replaced_publisher_pin",
        "unsigned_provider_change",
        "mutable_candidate_policy",
        "fake_witness",
        "wrong_provider_claim",
    ),
)
def test_production_resolver_rejects_untrusted_external_authority(
    tmp_path: Path,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = (
        _write_release_identity_fixture(
            root,
            installed,
            external_attestation=True,
        )
    )
    bootstrap_root = gate._test_external_release_bootstrap_root
    candidate_digest, _artifact_digest = gate._qa_candidate_digests(identity)
    owner_state = _owner_state_path(prompt_bundle_path)

    if failure == "absent_bootstrap":
        (bootstrap_root / "bootstrap.json").unlink()
        monkeypatch.setenv(
            "VIVENTIUM_RELEASE_AUTHORITY_BOOTSTRAP", str(bootstrap_root)
        )
        monkeypatch.setenv(
            "VIVENTIUM_QA_RELEASE_POLICY_SHA256",
            gate._test_external_release_authority.expected_policy_sha256,
        )
    elif failure == "same_user_authority":
        gate._release_authority_fstat = os.fstat
    elif failure == "mutable_bootstrap":
        (bootstrap_root / "bootstrap.json").chmod(0o644)
    elif failure == "mutable_publisher_pin":
        (bootstrap_root / "publisher.allowed_signers").chmod(0o644)
    elif failure == "writable_provider":
        (bootstrap_root / "provider.py").chmod(0o644)
    elif failure == "wrong_candidate":
        candidate_digest = "f" * 64
    elif failure == "wrong_owner":
        _rewrite_signed_external_fixture_bootstrap(
            gate,
            lambda bootstrap: bootstrap.update(
                {"ownerBindingSha256": "e" * 64}
            ),
        )
    elif failure == "bad_publisher_signature":
        signature = bootstrap_root / "bootstrap.sig"
        signature.chmod(0o644)
        signature.write_text(
            _ExternalFixtureSigner(_external_fixture_keys()["observation-producer"]).sign(
                (bootstrap_root / "bootstrap.json").read_bytes(),
                EXTERNAL_AUTHORITY_BOOTSTRAP_NAMESPACE,
            ),
            encoding="ascii",
        )
        signature.chmod(0o444)
    elif failure == "replaced_publisher_pin":
        signers = bootstrap_root / "publisher.allowed_signers"
        signers.chmod(0o644)
        signers.write_text(
            "publisher@fixture.example.invalid "
            + _fixture_public_key(_external_fixture_keys()["observation-producer"])
            + "\n",
            encoding="utf-8",
        )
        signers.chmod(0o444)
    elif failure == "unsigned_provider_change":
        provider = bootstrap_root / "provider.py"
        provider.chmod(0o644)
        provider.write_text(
            EXTERNAL_AUTHORITY_PROVIDER_SOURCE + "\n# unsigned replacement\n",
            encoding="utf-8",
        )
        provider.chmod(0o444)
    elif failure == "mutable_candidate_policy":
        policy = (
            installed / "scripts" / "viventium" / "qa_release_attestation_policy.json"
        )
        policy.write_bytes(policy.read_bytes() + b"\n")
    elif failure == "fake_witness":
        provider = bootstrap_root / "provider.py"
        provider.chmod(0o644)
        provider.write_text(
            EXTERNAL_AUTHORITY_PROVIDER_SOURCE.replace(
                "ProtectedReleaseLedgerWitness(\n"
                "            gate._test_external_release_authority.ledger_witness,\n"
                "            witness_identity,\n"
                "        )",
                "gate._test_external_release_authority.ledger_witness",
            ),
            encoding="utf-8",
        )
        provider.chmod(0o444)
        _rewrite_signed_external_fixture_bootstrap(
            gate,
            lambda bootstrap: bootstrap["provider"].update(
                {"sha256": hashlib.sha256(provider.read_bytes()).hexdigest()}
            ),
        )
    elif failure == "wrong_provider_claim":
        gate._test_external_release_provider_claim["ownerBindingSha256"] = (
            "e" * 64
        )

    assert gate._resolve_external_release_attestation_authority(
        installed_root=installed,
        runtime_owner_state=owner_state,
        candidate_digest=candidate_digest,
    ) is None


def test_release_gate_blocks_without_protected_witness_when_every_case_passes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    outside = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, outside, external_attestation=True
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=outside,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert result.release_ready is False
    assert result.exposure_allowed is False
    assert result.label == "NOT READY"
    assert {
        item.detail for item in result.open_gates
    } == {"qa_receipt_external_attestation_missing"}
    assert all(check.status == "PASS" for check in result.artifact_checks)
    owner_binding = result.to_dict()["owner_binding"]
    assert owner_binding["contractVersion"] == 1
    assert owner_binding["runtimeProfile"] == "isolated"
    assert owner_binding["ownerPid"].isdigit()
    assert owner_binding["ownerProcessStartedAt"]
    assert len(owner_binding["ownerBindingSha256"]) == 64
    assert len(owner_binding["ownerStateSha256"]) == 64
    assert owner_binding["generatedAt"].endswith("+00:00")
    assert owner_binding["expiresAt"].endswith("+00:00")
    assert owner_binding["maxAgeSeconds"] == gate.SNAPSHOT_TTL_SECONDS
    assert datetime.fromisoformat(owner_binding["expiresAt"]) - datetime.fromisoformat(
        owner_binding["generatedAt"]
    ) == timedelta(seconds=gate.SNAPSHOT_TTL_SECONDS)
    _write_runtime_claim_files(
        prompt_bundle_path,
        _healthy_readiness_facts(prompt_layers),
        identity,
        receipts,
    )
    assert gate.validate_serialized_release_snapshot(
        result.to_dict(), prompt_bundle_path.parent
    ) is True
    readiness_path = prompt_bundle_path.parent / "parallel-work-readiness-facts.json"
    identity_path = prompt_bundle_path.parent / "parallel-work-artifact-identity.json"
    snapshot_path = prompt_bundle_path.parent / "parallel-work-release-gate.json"
    readiness_path.write_text(
        json.dumps(_healthy_readiness_facts(prompt_layers)) + "\n", encoding="utf-8"
    )
    identity_path.write_text(json.dumps(identity) + "\n", encoding="utf-8")
    assert gate.main(
        [
            "--root",
            str(root),
            "--mode",
            "release",
            "--readiness-facts",
            str(readiness_path),
            "--artifact-identity",
            str(identity_path),
            "--installed-prompt-bundle",
            str(prompt_bundle_path),
            "--installed-root",
            str(outside),
            "--runtime-owner-state",
            str(_owner_state_path(prompt_bundle_path)),
            "--qa-case-receipts",
            str(prompt_bundle_path.parent / "parallel-work-qa-case-receipts.json"),
            "--output",
            str(snapshot_path),
            "--json",
        ]
    ) == 1
    assert gate.validate_serialized_release_snapshot(
        json.loads(snapshot_path.read_text(encoding="utf-8")), prompt_bundle_path.parent
    ) is True


def test_release_gate_rejects_forged_unsigned_receipts_and_service_acknowledgments(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    forged_receipts = _qa_case_receipts(gate, identity, authenticated=False)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=forged_receipts,
    )

    assert result.release_ready is False
    assert result.qa_receipt_summary["status"] == "blocked"
    assert any(
        item.detail == "qa_receipt_attestation_missing"
        for item in result.open_gates
    )


def test_release_gate_rejects_same_owner_hmac_without_an_external_release_attestation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    same_owner_forged_receipts = _qa_case_receipts(gate, identity)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=same_owner_forged_receipts,
    )

    assert result.release_ready is False
    assert result.qa_receipt_summary["status"] == "blocked"
    assert any(
        item.detail == "qa_receipt_external_attestation_missing"
        for item in result.open_gates
    )


def test_release_registry_covers_all_catalog_cases_without_replacing_specialists() -> None:
    gate = _load_module()
    catalog_cases = {
        f"{prefix}{number:03d}"
        for prefix, stop in (
            ("PWK-", 50),
            ("PWK-UC-", 14),
            ("REL-", 7),
            ("REL-UC-", 4),
        )
        for number in range(1, stop)
    }

    assert len(catalog_cases) == 71
    assert all(
        gate.REGISTERED_SEMANTIC_VERIFIERS[case_id]
        == {
            "id": "viventium-installed-catalog-v1",
            "path": Path(
                "qa/parallel-orchestrator/scripts/catalog_case_semantic_verifier.py"
            ),
        }
        for case_id in catalog_cases
    )
    assert gate.REGISTERED_SEMANTIC_VERIFIERS["PWK-UC-014"]["id"] == (
        "pwk-installed-journey-v1"
    )
    assert gate.REGISTERED_SEMANTIC_VERIFIERS["REL-UC-004"]["id"] == (
        "rel004-semantic-v1"
    )
    assert gate.REGISTERED_SEMANTIC_VERIFIERS["TR-026"]["id"] == "tr026-semantic-v1"


def test_default_gate_rejects_same_owner_hmac_without_external_attestation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )

    result = gate.evaluate_release_gate(
        root,
        mode="default",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=_qa_case_receipts(gate, identity),
    )

    assert result.release_ready is False
    assert result.qa_receipt_summary["status"] == "blocked"
    assert {
        item.detail for item in result.open_gates
    } == {"qa_receipt_external_attestation_missing"}


def test_explicit_local_qa_accepts_hmac_without_ever_becoming_release_ready(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    receipts = _qa_case_receipts(gate, identity)

    result = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert result.open_gates == ()
    assert result.qa_receipt_summary["status"] == "verified"
    assert result.release_ready is False
    assert result.label == "PRE-GATE / NOT READY"

    _write_runtime_claim_files(
        prompt_bundle_path,
        _healthy_readiness_facts(prompt_layers),
        identity,
        receipts,
    )
    snapshot = result.to_dict()
    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is True
    snapshot.update(
        {
            "mode": "release",
            "local_qa_override": False,
            "release_ready": True,
            "exposure_allowed": True,
            "label": "READY",
        }
    )
    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is False


def test_local_qa_snapshot_tolerates_storage_measurement_drift_within_same_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root, pwk_status="NOT RUN")
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    snapshot = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)

    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=45_000, free=55_000),
    )

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is True

    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=85_000, free=15_000),
    )

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is False


def test_local_qa_snapshot_remains_conservatively_valid_when_storage_improves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root, pwk_status="NOT RUN")
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=85_000, free=15_000),
    )
    snapshot = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)

    assert next(
        item
        for item in snapshot["readiness_checks"]
        if item["check_id"] == "STORAGE-PRESSURE"
    )["status"] == "FAIL"
    assert snapshot["release_ready"] is False

    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=70_000, free=30_000),
    )

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is True
    assert snapshot["release_ready"] is False


def test_local_qa_snapshot_rejects_storage_worsening_across_pressure_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root, pwk_status="NOT RUN")
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=85_000, free=15_000),
    )
    snapshot = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)

    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=96_000, free=4_000),
    )

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is False


def test_release_gate_rejects_tampered_external_authority_and_ledger_rollback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed, external_attestation=True
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)
    authority = gate._test_external_release_authority
    arguments = {
        "mode": "local-qa",
        "allow_local_qa_override": True,
        "readiness_facts": _healthy_readiness_facts(prompt_layers),
        "artifact_identity": identity,
        "installed_prompt_bundle_path": prompt_bundle_path,
        "installed_root": installed,
        "runtime_owner_state": _owner_state_path(prompt_bundle_path),
        "external_attestation_authority": authority,
    }
    baseline = gate.evaluate_release_gate(
        root, qa_case_receipts=receipts, **arguments
    )
    assert baseline.qa_receipt_summary["status"] == "verified"
    assert baseline.release_ready is False

    for field, nested in (
        ("publisherAttestation", None),
        ("producerAttestations", "signature"),
        ("serviceAcknowledgements", "signature"),
    ):
        tampered = json.loads(json.dumps(receipts))
        receipt = next(
            item for item in tampered["receipts"] if item["caseId"] == "TR-026"
        )
        if nested is None:
            receipt[field] = "hmac-sha256:" + "f" * 64
        else:
            receipt[field][0][nested] = "hmac-sha256:" + "f" * 64
        rejected = gate.evaluate_release_gate(
            root, qa_case_receipts=tampered, **arguments
        )
        assert rejected.release_ready is False
        assert next(
            item.detail for item in rejected.open_gates if item.case_id == "TR-026"
        ) == "qa_receipt_external_attestation_invalid"

    without_witness = gate.ExternalReleaseAttestationAuthority(
        expected_policy_sha256=authority.expected_policy_sha256,
        ledger_path=authority.ledger_path,
        ledger_witness=None,
    )
    missing_arguments = dict(arguments)
    missing_arguments["external_attestation_authority"] = without_witness
    missing = gate.evaluate_release_gate(
        root,
        qa_case_receipts=receipts,
        **missing_arguments,
    )
    assert missing.release_ready is False
    assert {
        item.detail for item in missing.open_gates
    } == {"qa_receipt_external_attestation_missing"}

    rolled_back = json.loads(authority.ledger_path.read_text(encoding="utf-8"))
    rolled_back["entries"].pop()
    authority.ledger_path.write_bytes(
        gate._load_external_release_attestation()._canonical_bytes(rolled_back)
    )
    blocked = gate.evaluate_release_gate(root, qa_case_receipts=receipts, **arguments)
    assert blocked.release_ready is False
    assert {
        item.detail for item in blocked.open_gates
    } == {"qa_receipt_external_attestation_invalid"}


def test_release_external_attestation_never_depends_on_an_owner_readable_hmac_key(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed, external_attestation=True
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)
    local_hmac_key = prompt_bundle_path.parent / gate.QA_RECEIPT_ATTESTATION_KEY_NAME
    assert local_hmac_key.is_file()
    local_hmac_key.unlink()

    result = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
        external_attestation_authority=gate._test_external_release_authority,
    )

    assert result.release_ready is False
    assert result.label == "PRE-GATE / NOT READY"
    assert result.qa_receipt_summary["status"] == "verified"


@pytest.mark.parametrize(
    ("field", "replacement", "expected_reason"),
    (
        ("attestation", "hmac-sha256:" + "0" * 64, "qa_receipt_attestation_invalid"),
        ("evidenceDigest", "0" * 64, "qa_receipt_attestation_invalid"),
        ("verifierId", "untrusted-semantic-v1", "qa_receipt_attestation_invalid"),
        ("verifierManifestSha256", "0" * 64, "qa_receipt_attestation_invalid"),
        ("receiptNonce", "0" * 32, "qa_receipt_attestation_invalid"),
        ("ownerBindingSha256", "0" * 64, "qa_receipt_owner_mismatch"),
        ("serviceAckDigest", "sha256:" + "f" * 64, "qa_receipt_attestation_invalid"),
        ("serviceAckSessionRef", "qa_" + "0" * 24, "qa_receipt_attestation_invalid"),
    ),
)
def test_release_gate_rejects_tampered_authenticated_receipt_fields(
    tmp_path: Path,
    field: str,
    replacement: str,
    expected_reason: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    receipts = _qa_case_receipts(gate, identity)
    receipt = next(item for item in receipts["receipts"] if item["caseId"] == "TR-026")
    receipt[field] = replacement

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert result.release_ready is False
    assert next(
        item.detail for item in result.open_gates if item.case_id == "TR-026"
    ) == expected_reason


def test_release_gate_rejects_authenticated_cross_case_receipt_replay(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    receipts = _qa_case_receipts(gate, identity)
    first, second = receipts["receipts"][:2]
    second["receiptNonce"] = first["receiptNonce"]
    authority = gate._qa_receipt_attestation_authority(
        installed, _owner_state_path(prompt_bundle_path)
    )
    second["attestation"] = gate._sign_qa_receipt(second, authority)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert result.release_ready is False
    assert {
        item.case_id
        for item in result.open_gates
        if item.detail == "qa_receipt_replay"
    } == {first["caseId"], second["caseId"]}


def test_release_gate_rejects_a_signed_unregistered_semantic_verifier(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    receipts = _qa_case_receipts(gate, identity)
    receipt = next(
        item for item in receipts["receipts"] if item["caseId"] == "TGDOC-010"
    )
    receipt["verifierId"] = "attacker-controlled-semantic-v1"
    authority = gate._qa_receipt_attestation_authority(
        installed, _owner_state_path(prompt_bundle_path)
    )
    receipt["attestation"] = gate._sign_qa_receipt(receipt, authority)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert result.release_ready is False
    assert next(
        item.detail for item in result.open_gates if item.case_id == "TGDOC-010"
    ) == "qa_receipt_verifier_unregistered"


@pytest.mark.parametrize("mutation", ("group_readable", "hard_link"))
def test_release_gate_rejects_an_insecure_private_receipt_signing_key(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    receipts = _qa_case_receipts(gate, identity)
    key = prompt_bundle_path.parent / gate.QA_RECEIPT_ATTESTATION_KEY_NAME
    if mutation == "group_readable":
        key.chmod(0o640)
    else:
        os.link(key, key.parent / "unsafe-hard-link")

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert result.release_ready is False
    assert {
        item.detail for item in result.open_gates
    } == {"qa_receipt_attestation_authority_unavailable"}


def test_receipt_owner_binding_survives_an_exact_runtime_owner_restart(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _layers = _write_release_identity_fixture(
        root, installed
    )
    owner_state = _owner_state_path(prompt_bundle_path)
    first = gate._qa_receipt_attestation_authority(
        installed, owner_state, create=True
    )
    assert first is not None
    receipts = _qa_case_receipts(gate, identity)
    original = json.loads(owner_state.read_text(encoding="utf-8"))
    restarted = subprocess.Popen(
        shlex.split(str(original["ownerProcessCommand"])),
        cwd=installed,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    OWNER_PROCESSES.append(restarted)
    owner_state.write_text(
        json.dumps(
            _runtime_owner_payload(
                gate,
                process=restarted,
                installed_root=installed,
                app_support=prompt_bundle_path.parent.parent,
                runtime_dir=prompt_bundle_path.parent,
                process_cwd=installed,
                config_file=prompt_bundle_path.parent.parent / "config.yaml",
                components_lock_file=installed / "components.lock.json",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    second = gate._qa_receipt_attestation_authority(installed, owner_state)

    assert second == first
    assert all(
        gate._qa_receipt_attestation_valid(receipt, second)
        for receipt in receipts["receipts"]
    )


def test_release_gate_never_uses_path_controlled_git_or_ps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, _identity, _layers = _write_release_identity_fixture(
        root, installed
    )
    poisoned = tmp_path / "poisoned-path"
    poisoned.mkdir()
    for name in ("git", "ps"):
        executable = poisoned / name
        executable.write_text("#!/bin/sh\nexit 91\n", encoding="utf-8")
        executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(poisoned))

    ok, revision = gate._git_output(installed, "rev-parse", "HEAD")

    assert ok is True
    assert len(revision) == 40
    assert gate._runtime_owner_state_proves_active(
        installed, _owner_state_path(prompt_bundle_path)
    ) is True


def test_serialized_release_contract_rejects_self_reported_nonexistent_qa_inventory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    receipts = _qa_case_receipts(gate, identity)
    snapshot = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    ).to_dict()
    candidate_digest, artifact_digest = gate._qa_candidate_digests(identity)
    forged_receipts = {
        "contractVersion": 1,
        "receipts": [
            {
                "artifactDigest": artifact_digest,
                "candidateDigest": candidate_digest,
                "caseId": "REL-UC-READY",
                "evidenceDigest": "a" * 64,
                "runAt": datetime.now(timezone.utc).isoformat(),
                "status": "PASS",
                "surface": "telegram",
            }
        ],
    }
    forged_gate = {
        "case_id": "REL-UC-READY",
        "status": "PASS",
        "source": "qa/release-readiness/cases.md",
        "detail": "[redacted]",
    }
    snapshot.update(
        {
            "gate_count": 1,
            "open_gate_count": 0,
            "gates": [forged_gate],
            "open_gates": [],
            "qa_receipt_summary": {
                "contractVersion": 1,
                "status": "verified",
                "receiptCount": 1,
                "receiptDigest": gate._canonical_hash(forged_receipts),
                "candidateDigest": candidate_digest,
                "artifactDigest": artifact_digest,
                "maxAgeSeconds": gate.QA_RECEIPT_TTL_SECONDS,
            },
        }
    )
    _write_runtime_claim_files(
        prompt_bundle_path, readiness, identity, forged_receipts
    )

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is False


def test_markdown_pass_requires_fresh_candidate_bound_case_receipts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed, external_attestation=True
    )
    common = {
        "mode": "local-qa",
        "allow_local_qa_override": True,
        "readiness_facts": _healthy_readiness_facts(prompt_layers),
        "artifact_identity": identity,
        "installed_prompt_bundle_path": prompt_bundle_path,
        "installed_root": installed,
        "runtime_owner_state": _owner_state_path(prompt_bundle_path),
        "external_attestation_authority": gate._test_external_release_authority,
    }

    missing_all = gate.evaluate_release_gate(root, **common)
    assert missing_all.release_ready is False
    assert all(
        record.status != "PASS"
        for record in missing_all.gates
        if record.source.startswith("qa/")
    )

    valid = _qa_case_receipts(gate, identity, externally_authenticated=True)
    accepted = gate.evaluate_release_gate(root, qa_case_receipts=valid, **common)
    assert accepted.release_ready is False
    assert accepted.qa_receipt_summary["status"] == "verified"
    assert accepted.open_gates == ()

    duplicate = json.loads(json.dumps(valid))
    duplicate["receipts"].append(dict(duplicate["receipts"][0]))
    missing = json.loads(json.dumps(valid))
    missing["receipts"].pop()
    stale = json.loads(json.dumps(valid))
    stale["receipts"][0]["runAt"] = (
        datetime.now(timezone.utc) - timedelta(days=2)
    ).isoformat()
    candidate_mismatch = json.loads(json.dumps(valid))
    candidate_mismatch["receipts"][0]["candidateDigest"] = "f" * 64
    artifact_mismatch = json.loads(json.dumps(valid))
    artifact_mismatch["receipts"][0]["artifactDigest"] = "f" * 64

    for forged in (
        duplicate,
        missing,
        stale,
        candidate_mismatch,
        artifact_mismatch,
    ):
        result = gate.evaluate_release_gate(
            root, qa_case_receipts=forged, **common
        )
        assert result.release_ready is False
        assert result.open_gates


def test_owner_writable_storage_policy_cannot_reuse_prior_candidate_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed, external_attestation=True
    )
    original_candidate, _artifact = gate._qa_candidate_digests(identity)
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)
    tampered_readiness = _healthy_readiness_facts(prompt_layers)
    tampered_readiness["storagePressure"] = {
        "version": 1,
        "status": "healthy",
        "usedPercent": 98.0,
        "availableBytes": 2_000,
        "thresholdPercent": 100,
        "warningMarginPercent": 1,
    }
    readiness_path = prompt_bundle_path.parent / "parallel-work-readiness-facts.json"
    readiness_path.write_text(
        json.dumps(tampered_readiness) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=98_000, free=2_000),
    )
    tampered_identity = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )
    tampered_candidate, _artifact = gate._qa_candidate_digests(tampered_identity)
    unbound_candidate = gate._qa_candidate_digests(identity, tampered_readiness)

    result = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=tampered_readiness,
        artifact_identity=tampered_identity,
        qa_case_receipts=receipts,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        external_attestation_authority=gate._test_external_release_authority,
    )

    assert tampered_candidate != original_candidate
    assert unbound_candidate == ("", "")
    assert all(
        tampered_identity["readiness"][key] != identity["readiness"][key]
        for key in gate.READINESS_IDENTITY_HASH_KEYS
    )
    assert result.qa_receipt_summary["status"] == "blocked"
    assert "qa_receipt_candidate_mismatch" in {
        record.detail for record in result.open_gates
    }


def test_local_pre_gate_reuses_scoped_receipt_only_when_claimed_artifacts_match(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    candidate_digest, artifact_digest = gate._qa_candidate_digests(identity)
    authority = gate._qa_receipt_attestation_authority(
        installed,
        _owner_state_path(prompt_bundle_path),
        create=True,
    )
    assert authority is not None
    timestamp = datetime.now(timezone.utc).isoformat()
    receipt = {
        "artifactClaims": gate._qa_receipt_artifact_claims("PWK-UC-015", identity),
        "artifactDigest": artifact_digest,
        "candidateDigest": candidate_digest,
        "caseId": "PWK-UC-015",
        "evidenceDigest": hashlib.sha256(b"installed-pwk-uc-015").hexdigest(),
        "ownerBindingSha256": authority[1],
        "receiptNonce": hashlib.sha256(timestamp.encode()).hexdigest()[:32],
        "runAt": timestamp,
        "status": "PASS",
        "surface": "web",
        "verifierId": "pwk-installed-journey-v1",
        "verifierManifestSha256": hashlib.sha256(b"pwk-verifier").hexdigest(),
    }
    receipt["attestation"] = gate._sign_qa_receipt(receipt, authority)
    receipts = {"contractVersion": 1, "receipts": [receipt]}
    current_identity = json.loads(json.dumps(identity))
    current_identity["source"]["worktreeHash"] = "1" * 64
    current_identity["installed"]["libreChatConfigSha256"] = "2" * 64
    records = (
        gate.GateRecord(
            "PWK-UC-015",
            "PASS",
            "qa/parallel-orchestrator/cases.md",
            "fixture",
        ),
    )
    common = {
        "readiness_facts": None,
        "installed_root": installed,
        "runtime_owner_state": _owner_state_path(prompt_bundle_path),
    }

    local, local_summary = gate._bind_catalog_gates_to_qa_receipts(
        records,
        receipts,
        current_identity,
        mode="local-qa",
        **common,
    )
    release, release_summary = gate._bind_catalog_gates_to_qa_receipts(
        records,
        receipts,
        current_identity,
        mode="release",
        **common,
    )

    assert local[0].status == "PASS"
    assert local[0].detail == "qa_receipt_verified"
    assert local_summary["status"] == "verified"
    assert release[0].status == "UNKNOWN"
    assert release[0].detail == "qa_receipt_candidate_mismatch"
    assert release_summary["status"] == "blocked"

    tampered = json.loads(json.dumps(receipts))
    tampered_receipt = tampered["receipts"][0]
    tampered_receipt["artifactClaims"]["runningServiceSha256"] = "3" * 64
    tampered_receipt["attestation"] = gate._sign_qa_receipt(
        tampered_receipt,
        authority,
    )
    rejected, rejected_summary = gate._bind_catalog_gates_to_qa_receipts(
        records,
        tampered,
        current_identity,
        mode="local-qa",
        **common,
    )
    assert rejected[0].status == "UNKNOWN"
    assert rejected[0].detail == "qa_receipt_artifact_claim_mismatch"
    assert rejected_summary["status"] == "blocked"


def test_canonical_local_qa_writes_a_valid_pre_gate_snapshot_without_pass_receipts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)
    runtime = prompt_bundle_path.parent
    snapshot_path = runtime / "parallel-work-release-gate.json"

    result = gate.main(
        [
            "--root",
            str(root),
            "--mode",
            "local-qa",
            "--allow-local-qa-override",
            "--readiness-facts",
            str(runtime / "parallel-work-readiness-facts.json"),
            "--artifact-identity",
            str(runtime / "parallel-work-artifact-identity.json"),
            "--qa-case-receipts",
            str(runtime / "parallel-work-qa-case-receipts.json"),
            "--installed-prompt-bundle",
            str(prompt_bundle_path),
            "--installed-root",
            str(installed),
            "--runtime-owner-state",
            str(_owner_state_path(prompt_bundle_path)),
            "--output",
            str(snapshot_path),
            "--json",
        ]
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert result == 0
    assert snapshot["label"] == "PRE-GATE / NOT READY"
    assert snapshot["release_ready"] is False
    assert snapshot["exposure_allowed"] is True
    assert snapshot["qa_receipt_summary"]["status"] == "blocked"
    assert gate.validate_snapshot_file(snapshot_path) is True


def test_runtime_service_manifest_digest_covers_loaded_release_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    before = identity["installed"]["runningServiceSha256"]
    loaded_service = (
        installed
        / "viventium_v0_4/LibreChat/api/server/services/viventium/ReleaseGateConsumer.js"
    )
    loaded_service.write_text("module.exports = { changed: true };\n", encoding="utf-8")

    after = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )

    assert after["installed"]["runtimeServiceManifestSha256"]
    assert after["installed"]["runningServiceSha256"] != before


def test_runtime_service_manifest_digest_covers_imported_api_dependency(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    before = identity["installed"]["runningServiceSha256"]
    imported_dependency = (
        installed
        / "viventium_v0_4/LibreChat/api/app/clients/tools/util/handleTools.js"
    )
    imported_dependency.write_text(
        "module.exports = { changed: true };\n", encoding="utf-8"
    )

    after = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )

    assert after["installed"]["runtimeServiceManifestSha256"]
    assert after["installed"]["runningServiceSha256"] != before


def test_runtime_service_manifest_digest_covers_tracked_source_deletion(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    before = identity["installed"]["runningServiceSha256"]
    tracked_source = (
        installed
        / "viventium_v0_4/LibreChat/api/server/services/viventium/ReleaseGateConsumer.js"
    )
    tracked_source.unlink()

    after = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )

    assert after["installed"]["runningServiceSha256"]
    assert after["installed"]["runningServiceSha256"] != before


def test_runtime_service_manifest_digest_excludes_untracked_source_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    before = identity["installed"]["runningServiceSha256"]
    untracked = (
        installed
        / "viventium_v0_4/LibreChat/api/server/services/viventium/UntrackedRuntime.js"
    )
    untracked.write_text("module.exports = { untracked: true };\n", encoding="utf-8")

    after = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )

    assert after["installed"]["runningServiceSha256"] == before


@pytest.mark.parametrize("nested_first", [False, True])
def test_runtime_service_manifest_uses_nearest_repo_independent_of_entry_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    nested_first: bool,
) -> None:
    gate = _load_module()
    root = tmp_path / "installed"
    nested = root / "nested"
    nested.mkdir(parents=True)
    root_file = root / "root-runtime.js"
    nested_file = nested / "nested-runtime.js"
    root_file.write_text("root\n", encoding="utf-8")
    nested_file.write_text("nested\n", encoding="utf-8")
    (root / ".gitignore").write_text("nested/\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".gitignore", "root-runtime.js")
    _git(root, "commit", "-qm", "root fixture")
    _git(nested, "init", "-q")
    _git(nested, "add", "nested-runtime.js")
    _git(nested, "commit", "-qm", "nested fixture")

    paths = ["root-runtime.js", "nested/nested-runtime.js"]
    if nested_first:
        paths.reverse()
    manifest = root / "scripts/viventium/parallel_work_runtime_artifact_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "contractVersion": 1,
                "entries": [
                    {"kind": "file", "path": path, "trackedOnly": True}
                    for path in paths
                ],
            }
        ),
        encoding="utf-8",
    )
    real_git_bytes = gate._git_bytes
    git_calls: list[tuple[str, ...]] = []

    def record_git_bytes(repository, *args, **kwargs):
        git_calls.append(tuple(str(value) for value in args))
        return real_git_bytes(repository, *args, **kwargs)

    monkeypatch.setattr(gate, "_git_bytes", record_git_bytes)

    manifest_sha, runtime_sha = gate._runtime_service_artifact_digests(root)

    assert len(manifest_sha) == 64
    assert len(runtime_sha) == 64
    assert sum(call[:2] == ("ls-files", "-z") for call in git_calls) == 2


def test_runtime_service_manifest_covers_api_runtime_trees_and_excludes_tests() -> None:
    manifest = json.loads(
        (
            ROOT
            / "scripts/viventium/parallel_work_runtime_artifact_manifest.json"
        ).read_text(encoding="utf-8")
    )
    entries = {entry["path"]: entry for entry in manifest["entries"]}
    api_trees = {
        "viventium_v0_4/LibreChat/api/app",
        "viventium_v0_4/LibreChat/api/cache",
        "viventium_v0_4/LibreChat/api/config",
        "viventium_v0_4/LibreChat/api/db",
        "viventium_v0_4/LibreChat/api/models",
        "viventium_v0_4/LibreChat/api/server",
        "viventium_v0_4/LibreChat/api/strategies",
        "viventium_v0_4/LibreChat/api/utils",
    }
    required_trees = api_trees | {
        "viventium_v0_4/GlassHive/runtime_phase1/src",
        "viventium_v0_4/telegram-viventium/TelegramVivBot",
    }

    assert required_trees.issubset(entries)
    for path in api_trees:
        entry = entries[path]
        assert {"__tests__", "cache", "data", "test", "tests"}.issubset(
            entry["excludeDirectories"]
        )
        assert entry["excludeFileSuffixes"] == [".spec.js", ".test.js"]


def test_runtime_service_manifest_binds_runtime_controls_but_not_offline_evidence_tools() -> None:
    manifest = json.loads(
        (
            ROOT
            / "scripts/viventium/parallel_work_runtime_artifact_manifest.json"
        ).read_text(encoding="utf-8")
    )
    entries = {entry["path"]: entry for entry in manifest["entries"]}
    required = {
        "bin/viventium",
        "scripts/viventium/feelings_qa_parent_control.py",
        "scripts/viventium/glasshive_qa_parent_control.py",
        "scripts/viventium/librechat_emo_qa_parent_control.py",
        "scripts/viventium/local_qa_runtime_control.py",
        "scripts/viventium/local_qa_service_ack.py",
        "scripts/viventium/release_claim_qa_fault.py",
        "scripts/viventium/telegram_qa_parent_control.py",
        "viventium_v0_4/viventium-librechat-start.sh",
        "viventium_v0_4/LibreChat/api/server/services/viventium/localQaServiceAck.js",
        "viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/local_qa_service_ack.py",
        "viventium_v0_4/telegram-viventium/TelegramVivBot/local_qa_service_ack.py",
        "viventium_v0_4/telegram-viventium/TelegramVivBot/utils/orchestration.py",
        "viventium_v0_4/telegram-viventium/TelegramVivBot/utils/tr026_local_qa.py",
    }

    assert required.issubset(entries)
    assert all((ROOT / path).is_file() for path in required)
    assert {
        "scripts/viventium/parallel_work_qa_evidence.py",
        "scripts/viventium/parallel_work_release_gate.py",
    }.isdisjoint(entries)


def test_runtime_service_manifest_binds_tracked_nonempty_runtime_inputs() -> None:
    librechat_root = ROOT / "viventium_v0_4/LibreChat"
    manifest = json.loads(
        (
            ROOT
            / "scripts/viventium/parallel_work_runtime_artifact_manifest.json"
        ).read_text(encoding="utf-8")
    )
    manifest_paths = {entry["path"] for entry in manifest["entries"]}
    required_files = {
        "package-lock.json",
        "client/package.json",
        "packages/api/package.json",
        "packages/client/package.json",
        "packages/data-provider/package.json",
        "packages/data-provider/react-query/package.json",
        "packages/data-schemas/package.json",
        "api/server/utils/emails/inviteUser.handlebars",
    }
    manifest_sha, running_sha = _load_module()._runtime_service_artifact_digests(ROOT)

    for relative_path in required_files:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(librechat_root),
                "ls-files",
                "--error-unmatch",
                relative_path,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, relative_path
        assert (librechat_root / relative_path).stat().st_size > 0, relative_path
    for relative_path in required_files - {"api/server/utils/emails/inviteUser.handlebars"}:
        manifest_path = f"viventium_v0_4/LibreChat/{relative_path}"
        assert manifest_path in manifest_paths
        assert next(
            entry for entry in manifest["entries"] if entry["path"] == manifest_path
        )["trackedOnly"] is True
    server_entry = next(
        entry
        for entry in manifest["entries"]
        if entry["path"] == "viventium_v0_4/LibreChat/api/server"
    )
    assert ".handlebars" in server_entry["extensions"]
    assert server_entry["trackedOnly"] is True
    assert all(
        entry["trackedOnly"] is False
        for entry in manifest["entries"]
        if entry["path"].endswith("/dist")
    )
    assert "viventium_v0_4/LibreChat/pnpm-lock.yaml" not in manifest_paths
    assert len(manifest_sha) == 64
    assert len(running_sha) == 64


@pytest.mark.parametrize(
    "relative_path",
    [
        "viventium_v0_4/LibreChat/package-lock.json",
        "viventium_v0_4/LibreChat/packages/api/package.json",
        "viventium_v0_4/LibreChat/packages/data-schemas/package.json",
        "viventium_v0_4/LibreChat/packages/data-provider/package.json",
        "viventium_v0_4/LibreChat/client/package.json",
        "viventium_v0_4/LibreChat/packages/client/package.json",
        "viventium_v0_4/LibreChat/packages/data-provider/react-query/package.json",
        "viventium_v0_4/LibreChat/api/server/utils/emails/inviteUser.handlebars",
    ],
)
def test_runtime_service_manifest_digest_covers_package_manifests(
    tmp_path: Path,
    relative_path: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    before = identity["installed"]["runningServiceSha256"]
    manifest_file = installed / relative_path
    manifest_file.write_text('{"changed":true}\n', encoding="utf-8")

    after = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )

    assert after["installed"]["runningServiceSha256"] != before


def test_release_snapshot_writer_is_atomic_durable_and_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _load_module()
    snapshot_path = tmp_path / "parallel-work-release-gate.json"
    events: list[str] = []
    real_fsync = gate.os.fsync
    real_replace = gate.os.replace

    def tracked_fsync(file_descriptor: int) -> None:
        mode = os.fstat(file_descriptor).st_mode
        events.append("directory_fsync" if stat.S_ISDIR(mode) else "file_fsync")
        real_fsync(file_descriptor)

    def tracked_replace(source: Path, target: Path) -> None:
        events.append("replace")
        real_replace(source, target)

    monkeypatch.setattr(gate.os, "fsync", tracked_fsync)
    monkeypatch.setattr(gate.os, "replace", tracked_replace)
    gate._write_snapshot(snapshot_path, {"contract_version": 1})

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == {
        "contract_version": 1
    }
    assert snapshot_path.stat().st_mode & 0o777 == 0o600
    assert events == ["file_fsync", "replace", "directory_fsync"]
    assert list(tmp_path.glob(".parallel-work-release-gate.json.*.tmp")) == []


@pytest.mark.parametrize(
    ("failure_stage", "expected_content", "expected_events"),
    [
        ("file_fsync", '{"old":true}\n', ["file_fsync"]),
        ("directory_fsync", '{\n  "new": true\n}\n', ["file_fsync", "replace", "directory_fsync"]),
    ],
)
def test_release_snapshot_writer_cleans_up_and_reports_fsync_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
    expected_content: str,
    expected_events: list[str],
) -> None:
    gate = _load_module()
    snapshot_path = tmp_path / "parallel-work-release-gate.json"
    snapshot_path.write_text('{"old":true}\n', encoding="utf-8")
    events: list[str] = []
    real_fsync = gate.os.fsync
    real_replace = gate.os.replace

    def tracked_fsync(file_descriptor: int) -> None:
        mode = os.fstat(file_descriptor).st_mode
        stage = "directory_fsync" if stat.S_ISDIR(mode) else "file_fsync"
        events.append(stage)
        if stage == failure_stage:
            raise OSError(f"synthetic {stage} failure")
        real_fsync(file_descriptor)

    def tracked_replace(source: Path, target: Path) -> None:
        events.append("replace")
        real_replace(source, target)

    monkeypatch.setattr(gate.os, "fsync", tracked_fsync)
    monkeypatch.setattr(gate.os, "replace", tracked_replace)

    with pytest.raises(OSError, match=f"synthetic {failure_stage} failure"):
        gate._write_snapshot(snapshot_path, {"new": True})

    assert snapshot_path.read_text(encoding="utf-8") == expected_content
    assert events == expected_events
    assert list(tmp_path.glob(".parallel-work-release-gate.json.*.tmp")) == []


def test_release_snapshot_writer_preserves_previous_file_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _load_module()
    snapshot_path = tmp_path / "parallel-work-release-gate.json"
    snapshot_path.write_text('{"old":true}\n', encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(gate.os, "replace", fail_replace)

    with pytest.raises(OSError, match="synthetic replace failure"):
        gate._write_snapshot(snapshot_path, {"new": True})

    assert snapshot_path.read_text(encoding="utf-8") == '{"old":true}\n'
    assert list(tmp_path.glob(".parallel-work-release-gate.json.*.tmp")) == []


def test_malformed_release_snapshot_read_fails_closed(tmp_path: Path) -> None:
    gate = _load_module()
    snapshot_path = tmp_path / "parallel-work-release-gate.json"
    snapshot_path.write_text("{", encoding="utf-8")

    assert gate._load_canonical_snapshot(snapshot_path) is None
    assert gate.validate_snapshot_file(snapshot_path) is False


def test_serialized_release_contract_rejects_forged_mixed_identity_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )
    forged = json.loads(json.dumps(result.to_dict()))
    forged["artifact_identity"]["installed"]["nestedRevisionsHash"] = "f" * 64

    assert gate.validate_serialized_release_snapshot(
        forged, prompt_bundle_path.parent
    ) is False


def test_serialized_release_contract_rejects_clean_commit_b_after_commit_a_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    snapshot = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is True
    (installed / "commit-b.txt").write_text("clean commit B\n", encoding="utf-8")
    _git(installed, "add", "commit-b.txt")
    _git(installed, "commit", "-qm", "clean commit B")

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is False


@pytest.mark.parametrize(
    "artifact_path",
    [
        "runtime.env",
        "librechat.yaml",
        "frontend-build",
        "api-build",
        "running-service",
        "owner-command-contract",
    ],
)
def test_serialized_release_contract_rejects_live_generated_or_running_artifact_drift(
    tmp_path: Path,
    artifact_path: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    snapshot = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)
    targets = {
        "runtime.env": prompt_bundle_path.parent / "runtime.env",
        "librechat.yaml": prompt_bundle_path.parent / "librechat.yaml",
        "frontend-build": installed / "viventium_v0_4/LibreChat/client/dist/index.html",
        "api-build": installed / "viventium_v0_4/LibreChat/packages/api/dist/index.js",
        "running-service": installed / "viventium_v0_4/LibreChat/api/server/index.js",
        "owner-command-contract": installed
        / "scripts/viventium/runtime_owner_command_contract.json",
    }

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is True
    targets[artifact_path].write_text("forged artifact\n", encoding="utf-8")

    assert gate.validate_serialized_release_snapshot(
        snapshot, prompt_bundle_path.parent
    ) is False


def test_local_qa_snapshot_renews_before_24h_expiry_only_after_live_revalidation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root, pwk_status="NOT RUN")
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    snapshot = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    generated = datetime.now(timezone.utc) - timedelta(hours=23, minutes=30)
    snapshot["owner_binding"]["generatedAt"] = generated.isoformat()
    snapshot["owner_binding"]["expiresAt"] = (
        generated + timedelta(seconds=gate.SNAPSHOT_TTL_SECONDS)
    ).isoformat()
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)
    snapshot_path = prompt_bundle_path.parent / "parallel-work-release-gate.json"
    snapshot_path.write_text(json.dumps(snapshot) + "\n", encoding="utf-8")
    old_expiry = snapshot["owner_binding"]["expiresAt"]

    assert gate.renew_local_qa_snapshot(snapshot_path) is True
    renewed = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert renewed["label"] == "PRE-GATE / NOT READY"
    assert renewed["release_ready"] is False
    assert renewed["exposure_allowed"] is True
    assert renewed["owner_binding"]["expiresAt"] > old_expiry
    assert gate.validate_serialized_release_snapshot(
        renewed, prompt_bundle_path.parent
    ) is True


def test_local_qa_snapshot_never_renews_after_live_artifact_drift(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root, pwk_status="NOT RUN")
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    snapshot = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    generated = datetime.now(timezone.utc) - timedelta(hours=23, minutes=30)
    snapshot["owner_binding"]["generatedAt"] = generated.isoformat()
    snapshot["owner_binding"]["expiresAt"] = (
        generated + timedelta(seconds=gate.SNAPSHOT_TTL_SECONDS)
    ).isoformat()
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)
    snapshot_path = prompt_bundle_path.parent / "parallel-work-release-gate.json"
    snapshot_path.write_text(json.dumps(snapshot) + "\n", encoding="utf-8")
    original_snapshot = snapshot_path.read_bytes()
    (installed / "bin" / "viventium").write_text(
        "#!/bin/sh\nsleep 121\n", encoding="utf-8"
    )

    assert gate.renew_local_qa_snapshot(snapshot_path) is False
    assert snapshot_path.read_bytes() == original_snapshot


@pytest.mark.parametrize("freshness", ["missing", "year_2000", "expired", "future"])
def test_serialized_release_contract_rejects_invalid_snapshot_freshness(
    tmp_path: Path,
    freshness: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    ).to_dict()
    now = datetime.now(timezone.utc)
    if freshness == "missing":
        result["owner_binding"].pop("expiresAt")
    elif freshness == "year_2000":
        generated = datetime(2000, 1, 1, tzinfo=timezone.utc)
        result["owner_binding"]["generatedAt"] = generated.isoformat()
        result["owner_binding"]["expiresAt"] = (
            generated + timedelta(seconds=gate.SNAPSHOT_TTL_SECONDS)
        ).isoformat()
    elif freshness == "expired":
        expires = now - timedelta(seconds=1)
        result["owner_binding"]["generatedAt"] = (
            expires - timedelta(seconds=gate.SNAPSHOT_TTL_SECONDS)
        ).isoformat()
        result["owner_binding"]["expiresAt"] = expires.isoformat()
    else:
        generated = now + timedelta(minutes=2)
        result["owner_binding"]["generatedAt"] = generated.isoformat()
        result["owner_binding"]["expiresAt"] = (
            generated + timedelta(seconds=gate.SNAPSHOT_TTL_SECONDS)
        ).isoformat()

    assert gate.validate_serialized_release_snapshot(
        result, prompt_bundle_path.parent
    ) is False


def test_missing_installed_root_never_defaults_to_source_root(tmp_path: Path) -> None:
    root = tmp_path / "source"
    runtime = tmp_path / "runtime"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, runtime
    )

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
    )

    installed_check = next(
        check
        for check in result.artifact_checks
        if check.check_id == "INSTALLED-ARTIFACT"
    )
    assert installed_check.status in {"FAIL", "UNKNOWN"}
    assert installed_check.reason == "installed_root_missing"
    assert result.release_ready is False


def test_local_qa_requires_active_installed_owner_with_complete_shaped_facts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root, pwk_status="NOT RUN")
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )

    result = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=None,
        runtime_owner_state=None,
    )

    installed_check = next(
        check
        for check in result.artifact_checks
        if check.check_id == "INSTALLED-ARTIFACT"
    )
    assert installed_check.reason == "installed_root_missing"
    assert result.exposure_allowed is False
    assert result.release_ready is False
    assert result.label == "PRE-GATE / NOT READY"


@pytest.mark.parametrize("mode", ["release", "local-qa"])
def test_claim_cli_rejects_fact_paths_outside_active_owner_runtime(
    tmp_path: Path,
    mode: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    alternate = tmp_path / "caller-controlled"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    alternate.mkdir()
    readiness_path = alternate / "parallel-work-readiness-facts.json"
    identity_path = alternate / "parallel-work-artifact-identity.json"
    alternate_prompt = alternate / "prompt-bundle.json"
    readiness_path.write_text(
        json.dumps(_healthy_readiness_facts(prompt_layers)) + "\n", encoding="utf-8"
    )
    identity_path.write_text(json.dumps(identity) + "\n", encoding="utf-8")
    alternate_prompt.write_bytes(prompt_bundle_path.read_bytes())
    args = [
        "--root",
        str(root),
        "--mode",
        mode,
        "--readiness-facts",
        str(readiness_path),
        "--artifact-identity",
        str(identity_path),
        "--qa-case-receipts",
        str(prompt_bundle_path.parent / "parallel-work-qa-case-receipts.json"),
        "--installed-prompt-bundle",
        str(alternate_prompt),
        "--installed-root",
        str(installed),
        "--runtime-owner-state",
        str(_owner_state_path(prompt_bundle_path)),
        "--json",
    ]
    if mode == "local-qa":
        args.append("--allow-local-qa-override")

    with pytest.raises(SystemExit):
        gate.main(args)


def test_invalid_explicit_installed_root_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=tmp_path / "missing-installed-root",
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    installed_check = next(
        check
        for check in result.artifact_checks
        if check.check_id == "INSTALLED-ARTIFACT"
    )
    assert installed_check.status == "FAIL"
    assert installed_check.reason == "installed_root_invalid"
    assert result.release_ready is False


def test_explicit_installed_clone_without_live_owner_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
    )

    installed_check = next(
        check
        for check in result.artifact_checks
        if check.check_id == "INSTALLED-ARTIFACT"
    )
    assert installed_check.status == "FAIL"
    assert installed_check.reason == "installed_runtime_not_active"
    assert result.release_ready is False


def test_stale_runtime_owner_process_cannot_prove_an_installed_clone(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    owner_state = _owner_state_path(prompt_bundle_path)
    payload = json.loads(owner_state.read_text(encoding="utf-8"))
    owner_state.write_text(
        json.dumps({**payload, "ownerPid": "99999999"}) + "\n",
        encoding="utf-8",
    )

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=owner_state,
    )

    installed_check = next(
        check
        for check in result.artifact_checks
        if check.check_id == "INSTALLED-ARTIFACT"
    )
    assert installed_check.status == "FAIL"
    assert installed_check.reason == "installed_runtime_not_active"
    assert result.release_ready is False


def test_runtime_owner_reader_rejects_public_or_reused_process_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, _identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    owner_state = _owner_state_path(prompt_bundle_path)
    payload = json.loads(owner_state.read_text(encoding="utf-8"))

    owner_state.chmod(0o644)
    assert gate._runtime_owner_state_proves_active(installed, owner_state) is False

    owner_state.chmod(0o600)
    payload["ownerProcessStartedAt"] = "Mon Jan 1 00:00:00 2000"
    payload["ownerBindingSha256"] = gate._owner_binding_sha256(payload)
    owner_state.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    assert gate._runtime_owner_state_proves_active(installed, owner_state) is False


def test_live_unrelated_process_with_installed_viventium_bait_argument_fails_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "arbitrary-clone"
    _write_fixture_root(root)
    gate, prompt_bundle_path, _identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    bait_process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(120)",
            str(installed / "bin" / "viventium"),
        ],
        cwd=installed,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    OWNER_PROCESSES.append(bait_process)
    owner_state = _owner_state_path(prompt_bundle_path)
    owner_state.write_text(
        json.dumps(
                _runtime_owner_payload(
                    gate,
                    process=bait_process,
                    installed_root=installed,
                    app_support=prompt_bundle_path.parent.parent,
                    runtime_dir=prompt_bundle_path.parent,
                    process_cwd=installed,
                    config_file=prompt_bundle_path.parent.parent / "config.yaml",
                    components_lock_file=installed / "components.lock.json",
                )
        )
        + "\n",
        encoding="utf-8",
    )

    identity = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        owner_state,
    )

    assert identity["installed"]["rootRevision"] == ""


@pytest.mark.parametrize("spoof_image", ["/bin/sleep", "/bin/sh"])
def test_canonical_owner_argv_with_wrong_live_executable_image_fails_closed(
    tmp_path: Path,
    spoof_image: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "spoofed-installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, _identity, _prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    owner_state = _owner_state_path(prompt_bundle_path)
    original = json.loads(owner_state.read_text(encoding="utf-8"))
    contract = json.loads(
        (installed / "scripts/viventium/runtime_owner_command_contract.json").read_text(
            encoding="utf-8"
        )
    )
    values = {
        "ownerExecutablePath": original["ownerExecutablePath"],
        "appSupportDir": original["appSupportDir"],
        "configFile": original["configFile"],
        "runtimeDir": original["runtimeDir"],
        "componentsLockFile": original["componentsLockFile"],
    }
    canonical_command = " ".join(
        str(token).format(**values)
        for token in contract["detached"]["argvTemplate"]
    )
    spoof_action = (
        "/bin/sleep 120"
        if spoof_image == "/bin/sleep"
        else "/bin/sh -c 'sleep 120'"
    )
    spoof = subprocess.Popen(
        [
            "/bin/bash",
            "-c",
            f"exec -a {shlex.quote(canonical_command)} {spoof_action}",
        ],
        cwd=installed,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    OWNER_PROCESSES.append(spoof)
    time.sleep(0.1)
    spoof_payload = _runtime_owner_payload(
        gate,
        process=spoof,
        installed_root=installed,
        app_support=prompt_bundle_path.parent.parent,
        runtime_dir=prompt_bundle_path.parent,
        process_cwd=installed,
        config_file=prompt_bundle_path.parent.parent / "config.yaml",
        components_lock_file=installed / "components.lock.json",
    )
    owner_state.write_text(json.dumps(spoof_payload) + "\n", encoding="utf-8")

    assert gate._runtime_owner_state_proves_active(installed, owner_state) is False
    identity = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        owner_state,
    )
    assert identity["installed"]["rootRevision"] == ""


def test_git_status_failure_never_becomes_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = _load_module()

    def fake_git_bytes(_root, *args, **_kwargs):
        if args == ("rev-parse", "--verify", "HEAD"):
            return True, b"a" * 40 + b"\n"
        return False, b""

    monkeypatch.setattr(gate, "_git_bytes", fake_git_bytes)

    identity = gate._git_identity(tmp_path)

    assert identity["clean"] is False
    assert identity["worktreeHash"] == ""


@pytest.mark.parametrize(
    "revision_output,status_output",
    [("corrupt", ""), ("a" * 40, "\x00corrupt-status")],
)
def test_corrupt_git_output_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    revision_output: str,
    status_output: str,
) -> None:
    gate = _load_module()

    def fake_git_bytes(_root, *args, **_kwargs):
        if args == ("rev-parse", "--verify", "HEAD"):
            return True, revision_output.encode("utf-8")
        if args[:2] == ("status", "--porcelain=v1"):
            return True, status_output.encode("utf-8")
        return True, b""

    monkeypatch.setattr(gate, "_git_bytes", fake_git_bytes)

    identity = gate._git_identity(tmp_path)

    assert identity["clean"] is False
    assert identity["worktreeHash"] == ""


def test_worktree_hash_binds_tracked_and_untracked_dirty_content_without_output(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "fixture")

    tracked.write_text("private-alpha\n", encoding="utf-8")
    tracked_alpha = gate._git_identity(repo)
    tracked.write_text("private-bravo\n", encoding="utf-8")
    tracked_bravo = gate._git_identity(repo)

    untracked = repo / "untracked.txt"
    untracked.write_text("private-charlie\n", encoding="utf-8")
    untracked_charlie = gate._git_identity(repo)
    untracked.write_text("private-delta--\n", encoding="utf-8")
    untracked_delta = gate._git_identity(repo)

    assert tracked_alpha["clean"] is False
    assert tracked_alpha["worktreeHash"] != tracked_bravo["worktreeHash"]
    assert untracked_charlie["worktreeHash"] != untracked_delta["worktreeHash"]
    serialized = json.dumps(
        [tracked_alpha, tracked_bravo, untracked_charlie, untracked_delta]
    )
    assert "private-" not in serialized
    assert str(repo) not in serialized


def test_worktree_hash_does_not_follow_untracked_symlink_content(tmp_path: Path) -> None:
    gate = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "fixture")

    external = tmp_path / "private-external.txt"
    external.write_text("private-alpha\n", encoding="utf-8")
    (repo / "external-link").symlink_to(external)
    before = gate._git_identity(repo)
    external.write_text("private-bravo\n", encoding="utf-8")
    after = gate._git_identity(repo)

    assert before["clean"] is False
    assert before["worktreeHash"] == after["worktreeHash"]
    assert str(external) not in json.dumps(before)


def test_git_identity_ignores_ambient_repository_redirects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    repo = tmp_path / "candidate"
    decoy = tmp_path / "decoy"
    for checkout, content in ((repo, "candidate\n"), (decoy, "decoy\n")):
        checkout.mkdir()
        (checkout / "tracked.txt").write_text(content, encoding="utf-8")
        _git(checkout, "init", "-q")
        _git(checkout, "add", "tracked.txt")
        _git(checkout, "commit", "-qm", "fixture")
    candidate_revision = _git(repo, "rev-parse", "HEAD")
    (repo / "tracked.txt").write_text("modified candidate\n", encoding="utf-8")
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))

    identity = gate._git_identity(repo)

    assert identity["revision"] == candidate_revision
    assert identity["clean"] is False
    assert gate.SHA256.fullmatch(str(identity["worktreeHash"])) is not None


@pytest.mark.parametrize("index_flag", ["--assume-unchanged", "--skip-worktree"])
def test_git_identity_fails_closed_for_hidden_index_flags(
    tmp_path: Path,
    index_flag: str,
) -> None:
    gate = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "fixture")
    _git(repo, "update-index", index_flag, "tracked.txt")
    tracked.write_text("hidden modification\n", encoding="utf-8")

    identity = gate._git_identity(repo)

    assert identity["clean"] is False
    assert identity["worktreeHash"] == ""


def test_git_identity_uses_bounded_streaming_not_subprocess_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "fixture")

    def reject_buffered_run(*_args, **_kwargs):
        raise AssertionError("Git output must not use buffered subprocess.run")

    monkeypatch.setattr(gate.subprocess, "run", reject_buffered_run)

    identity = gate._git_identity(repo)

    assert identity["clean"] is True


def test_git_output_limit_fails_before_accepting_oversized_status(tmp_path: Path) -> None:
    gate = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "fixture")
    (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    ok, output = gate._git_bytes(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        max_output_bytes=1,
    )

    assert ok is False
    assert output == b""


def test_git_identity_rejects_content_change_between_measurement_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "fixture")
    tracked.write_text("private-alpha\n", encoding="utf-8")
    real_hash_path = gate._hash_worktree_path
    calls = 0

    def mutate_after_first_hash(*args, **kwargs):
        nonlocal calls
        result = real_hash_path(*args, **kwargs)
        calls += 1
        if calls == 1:
            tracked.write_text("private-bravo\n", encoding="utf-8")
        return result

    monkeypatch.setattr(gate, "_hash_worktree_path", mutate_after_first_hash)

    identity = gate._git_identity(repo)

    assert calls >= 2
    assert identity["clean"] is False
    assert identity["worktreeHash"] == ""


def test_git_identity_rejects_ancestor_replacement_during_hashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = repo / "tracked.txt"
    tracked.write_text("committed\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "fixture")
    mutable = repo / "mutable"
    mutable.mkdir()
    (mutable / "payload.txt").write_text("private-local\n", encoding="utf-8")
    external = tmp_path / "external"
    external.mkdir()
    os.link(mutable / "payload.txt", external / "payload.txt")
    real_open = gate.os.open
    swapped = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal swapped
        decoded = os.fsdecode(path)
        if not swapped and decoded.endswith("payload.txt"):
            mutable.rename(repo / "pinned-mutable")
            mutable.symlink_to(external, target_is_directory=True)
            swapped = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(gate.os, "open", racing_open)

    identity = gate._git_identity(repo)

    assert swapped is True
    assert identity["clean"] is False
    assert identity["worktreeHash"] == ""


def test_serialized_gate_details_are_always_redacted(tmp_path: Path) -> None:
    private_path = "/path/to/private/evidence.json"
    _write_fixture_root(
        tmp_path,
        pwk_status=f"PARTIAL — evidence at {private_path}",
    )
    gate = _load_module()

    payload = gate.evaluate_release_gate(tmp_path).to_dict()
    serialized = json.dumps(payload)

    assert private_path not in serialized
    assert all(record["detail"] == "[redacted]" for record in payload["gates"])
    assert all(record["detail"] == "[redacted]" for record in payload["open_gates"])


def test_public_readiness_facts_never_expose_untrusted_private_reason_text(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    facts = _healthy_readiness_facts()
    facts["promptLayers"]["reason"] = "private_token=synthetic-private-marker /private/user/prompt"
    facts["storagePressure"]["reason"] = "storage_token=synthetic-storage-marker /private/user/data"

    public = gate.evaluate_release_gate(
        tmp_path,
        mode="release",
        readiness_facts=facts,
    ).to_dict()
    serialized = json.dumps(public, sort_keys=True)

    assert "synthetic-private-marker" not in serialized
    assert "synthetic-storage-marker" not in serialized
    assert "/private/user" not in serialized
    assert public["readiness_facts"]["promptLayers"]["reason"] == "prompt_layers_unknown"
    assert public["readiness_facts"]["storagePressure"]["reason"] == "storage_pressure_unknown"


def test_public_readiness_facts_drop_private_untrusted_identity_fields(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    facts = _healthy_readiness_facts()
    facts["contractVersion"] = "/private/synthetic-contract-marker"
    facts["promptLayers"].update(
        {
            "contractVersion": "/private/synthetic-prompt-contract-marker",
            "producerScope": "/private/synthetic-producer-marker",
            "status": "/private/synthetic-prompt-status-marker",
            "unknownLayerCount": "/private/synthetic-unknown-count-marker",
            "unknownLayerNames": ["/private/synthetic-unknown-layer-marker"],
            "layerNames": ["main", "/private/synthetic-layer-marker"],
            "registryHash": "/private/synthetic-registry-marker",
        }
    )
    facts["storagePressure"].update(
        {
            "status": "/private/synthetic-storage-status-marker",
            "availableBytes": "/private/synthetic-storage-count-marker",
        }
    )

    public = gate.evaluate_release_gate(
        tmp_path,
        mode="release",
        readiness_facts=facts,
    ).to_dict()
    serialized = json.dumps(public, sort_keys=True)

    assert "/private/synthetic" not in serialized
    assert public["readiness_facts"]["promptLayers"]["producerScope"] == "unknown"
    assert public["readiness_facts"]["promptLayers"]["status"] == "unknown"
    assert public["readiness_facts"]["promptLayers"]["unknownLayerNames"] == []
    assert public["readiness_facts"]["promptLayers"]["layerNames"] == ["main"]
    assert public["readiness_facts"]["promptLayers"]["registryHash"] == ""
    assert public["readiness_facts"]["storagePressure"]["status"] == "unknown"


def test_public_artifact_identity_never_exposes_untrusted_private_fields(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    identity = {
        "contractVersion": "/private/synthetic-contract-marker",
        "source": {
            "revision": "/private/synthetic-source-marker",
            "clean": "/private/synthetic-clean-marker",
            "worktreeHash": "/private/synthetic-worktree-marker",
            "componentsLockSha256": "/private/synthetic-lock-marker",
        },
        "nestedComponents": [
            {
                "name": "safe-component",
                "pin": "/private/synthetic-pin-marker",
                "revision": "/private/synthetic-revision-marker",
                "clean": "/private/synthetic-nested-clean-marker",
                "worktreeHash": "/private/synthetic-nested-hash-marker",
            },
            {"name": "/private/synthetic-component-marker"},
        ],
        "prebuiltHelper": {
            "sourceDeclaredSha256": "/private/synthetic-prebuilt-marker",
            "binaryExecutable": "/private/synthetic-executable-marker",
        },
        "installed": {
            "rootRevision": "/private/synthetic-root-marker",
            "runtimeEnvSha256": "/private/synthetic-runtime-marker",
        },
    }

    public = gate.evaluate_release_gate(
        tmp_path,
        mode="release",
        artifact_identity=identity,
    ).to_dict()
    serialized = json.dumps(public, sort_keys=True)

    assert "/private/synthetic" not in serialized
    projected = public["artifact_identity"]
    assert projected["contractVersion"] == 0
    assert projected["source"]["revision"] == ""
    assert projected["source"]["clean"] is False
    assert projected["nestedComponents"] == [
        {"name": "safe-component", "pin": "", "revision": "", "clean": False, "worktreeHash": ""}
    ]
    assert projected["prebuiltHelper"]["binaryExecutable"] is False
    assert projected["installed"]["rootRevision"] == ""


def test_pass_qa_cannot_hide_source_pin_prebuilt_or_installed_identity_drift(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    outside = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, outside, external_attestation=True
    )
    receipts = _qa_case_receipts(gate, identity, externally_authenticated=True)

    (root / "components" / "worker" / "worker.txt").write_text(
        "uncommitted nested drift\n", encoding="utf-8"
    )
    (root / "apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal").write_bytes(
        b"tampered prebuilt\n"
    )
    prompt_bundle_path.write_text('{"prompt_count":999,"prompts":{}}\n', encoding="utf-8")

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=outside,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    assert {
        item.detail for item in result.open_gates
    } == {"qa_receipt_external_attestation_missing"}
    assert result.release_ready is False
    assert {check.check_id: check.status for check in result.artifact_checks} == {
        "SOURCE-IDENTITY": "FAIL",
        "NESTED-PINS": "FAIL",
        "PREBUILT-IDENTITY": "FAIL",
        "INSTALLED-ARTIFACT": "FAIL",
    }
    assert {check.check_id: check.reason for check in result.artifact_checks} == {
        "SOURCE-IDENTITY": "source_identity_mismatch",
        "NESTED-PINS": "nested_pin_mismatch",
        "PREBUILT-IDENTITY": "prebuilt_identity_mismatch",
        "INSTALLED-ARTIFACT": "installed_artifact_mismatch",
    }
    assert {
        check.check_id for check in result.blocking_artifact_checks
    } == {
        "SOURCE-IDENTITY",
        "NESTED-PINS",
        "PREBUILT-IDENTITY",
        "INSTALLED-ARTIFACT",
    }


def test_dirty_candidate_recorded_before_manifest_keeps_fail_with_typed_reasons(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, _identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    for checkout in (root, installed):
        (checkout / "dirty-source.txt").write_text(
            "unchanged dirty source\n", encoding="utf-8"
        )
        (checkout / "components/worker/worker.txt").write_text(
            "unchanged dirty nested component\n", encoding="utf-8"
        )
    identity = gate.build_release_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )

    measured = gate._measured_artifact_identity(
        root,
        prompt_bundle_path,
        installed,
        _owner_state_path(prompt_bundle_path),
    )
    readiness = _healthy_readiness_facts(prompt_layers)
    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=readiness,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    assert gate._public_artifact_identity(identity) == measured
    assert {
        check.check_id: (check.status, check.reason)
        for check in result.artifact_checks
    } == {
        "SOURCE-IDENTITY": ("FAIL", "source_dirty"),
        "NESTED-PINS": ("FAIL", "nested_dirty"),
        "PREBUILT-IDENTITY": ("PASS", ""),
        "INSTALLED-ARTIFACT": ("FAIL", "installed_candidate_dirty"),
    }
    assert result.release_ready is False
    _write_runtime_claim_files(prompt_bundle_path, readiness, identity)
    assert gate.validate_serialized_release_snapshot(
        result.to_dict(), prompt_bundle_path.parent
    ) is True


@pytest.mark.parametrize(
    ("repository", "check_id", "reason"),
    [
        ("source", "SOURCE-IDENTITY", "source_worktree_hash_unavailable"),
        ("nested", "NESTED-PINS", "nested_worktree_hash_unavailable"),
        ("installed", "INSTALLED-ARTIFACT", "installed_worktree_hash_unavailable"),
    ],
)
def test_worktree_hash_failure_reports_unavailable_instead_of_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repository: str,
    check_id: str,
    reason: str,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    real_git_identity = gate._git_identity
    targets = {
        "source": root.resolve(),
        "nested": (root / "components" / "worker").resolve(),
        "installed": installed.resolve(),
    }

    def worktree_hash_unavailable(path: Path, *, ignore_submodules: bool = False):
        measured = real_git_identity(path, ignore_submodules=ignore_submodules)
        if Path(path).resolve() == targets[repository]:
            return {**measured, "clean": False, "worktreeHash": ""}
        return measured

    monkeypatch.setattr(gate, "_git_identity", worktree_hash_unavailable)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    source_check = next(
        check
        for check in result.artifact_checks
        if check.check_id == check_id
    )
    assert source_check.status == "FAIL"
    assert source_check.reason == reason


def test_local_override_never_sets_release_ready_even_when_every_check_passes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    outside = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, outside
    )

    result = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=outside,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    assert result.release_ready is False
    assert result.exposure_allowed is True
    assert result.label == "PRE-GATE / NOT READY"


def test_explicit_local_qa_breaks_open_gate_deadlock_only_when_integrity_passes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(
        root,
        pwk_status="NOT RUN",
        rel_status="PARTIAL",
        telegram_status="BLOCKED",
        emotional_status="FAIL",
        emotional_delivery_status="NOT RUN",
    )
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    common = {
        "readiness_facts": _healthy_readiness_facts(prompt_layers),
        "artifact_identity": identity,
        "installed_prompt_bundle_path": prompt_bundle_path,
        "installed_root": installed,
        "runtime_owner_state": _owner_state_path(prompt_bundle_path),
    }

    local_qa = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        **common,
    )
    release = gate.evaluate_release_gate(root, mode="release", **common)

    assert {item.case_id for item in local_qa.open_gates} >= {
        "PWK-UC-014",
        "REL-UC-004",
        "TR-026",
        "EMO-UC-047",
        "EMO-UC-048",
    }
    assert local_qa.exposure_allowed is True
    assert local_qa.release_ready is False
    assert local_qa.label == "PRE-GATE / NOT READY"
    assert release.exposure_allowed is False
    assert release.release_ready is False
    assert release.label == "NOT READY"


def test_explicit_local_qa_allows_shaped_dirty_prompt_storage_and_open_gate_facts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(
        root,
        pwk_status="NOT RUN",
        rel_status="PARTIAL",
        telegram_status="BLOCKED",
        emotional_status="FAIL",
        emotional_delivery_status="NOT RUN",
    )
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    monkeypatch.setattr(
        gate.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100_000, used=95_000, free=5_000),
    )
    (root / "dirty-source.txt").write_text("dirty\n", encoding="utf-8")
    (root / "components/worker/worker.txt").write_text(
        "dirty nested component\n", encoding="utf-8"
    )
    (root / "apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal").write_bytes(
        b"dirty prebuilt\n"
    )
    readiness = _healthy_readiness_facts(
        {**prompt_layers, "registryHash": "b" * 64}
    )
    readiness["storagePressure"] = {
        "version": 1,
        "status": "critical",
        "usedPercent": 95,
        "availableBytes": 1024,
        "thresholdPercent": 90,
        "warningMarginPercent": 10,
    }
    common = {
        "readiness_facts": readiness,
        "artifact_identity": identity,
        "installed_prompt_bundle_path": prompt_bundle_path,
        "installed_root": installed,
        "runtime_owner_state": _owner_state_path(prompt_bundle_path),
    }

    local_qa = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        **common,
    )
    release = gate.evaluate_release_gate(root, mode="release", **common)
    default = gate.evaluate_release_gate(root, mode="default", **common)

    assert {check.check_id for check in local_qa.blocking_checks} == {
        "PROMPT-LAYERS",
        "STORAGE-PRESSURE",
    }
    assert {check.check_id for check in local_qa.blocking_artifact_checks} == {
        "SOURCE-IDENTITY",
        "NESTED-PINS",
        "PREBUILT-IDENTITY",
        "INSTALLED-ARTIFACT",
    }
    assert local_qa.open_gates
    assert local_qa.exposure_allowed is True
    assert local_qa.release_ready is False
    assert local_qa.label == "PRE-GATE / NOT READY"
    for non_local in (release, default):
        assert non_local.exposure_allowed is False
        assert non_local.release_ready is False
        assert non_local.label == "NOT READY"

    readiness_path = prompt_bundle_path.parent / "parallel-work-readiness-facts.json"
    identity_path = prompt_bundle_path.parent / "parallel-work-artifact-identity.json"
    readiness_path.write_text(json.dumps(readiness) + "\n", encoding="utf-8")
    identity_path.write_text(json.dumps(identity) + "\n", encoding="utf-8")
    common_args = [
        "--root",
        str(root),
        "--readiness-facts",
        str(readiness_path),
        "--artifact-identity",
        str(identity_path),
        "--qa-case-receipts",
        str(prompt_bundle_path.parent / "parallel-work-qa-case-receipts.json"),
        "--installed-prompt-bundle",
        str(prompt_bundle_path),
        "--installed-root",
        str(installed),
        "--runtime-owner-state",
        str(_owner_state_path(prompt_bundle_path)),
        "--json",
    ]
    assert gate.main([*common_args, "--mode", "release"]) == 1
    assert (
        gate.main(
            [
                *common_args,
                "--mode",
                "local-qa",
                "--allow-local-qa-override",
            ]
        )
        == 0
    )


def test_explicit_local_qa_rejects_malformed_artifact_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root, pwk_status="NOT RUN")
    gate, prompt_bundle_path, _identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )

    result = gate.evaluate_release_gate(
        root,
        mode="local-qa",
        allow_local_qa_override=True,
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity={"contractVersion": 1},
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    assert result.exposure_allowed is False
    assert result.release_ready is False
    assert result.label == "PRE-GATE / NOT READY"


def test_prompt_registry_hash_mismatch_blocks_with_no_unknown_layer_names(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    outside = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, outside
    )
    prompt_layers = {**prompt_layers, "registryHash": "b" * 64}

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=outside,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    prompt_check = next(
        check for check in result.readiness_checks if check.check_id == "PROMPT-LAYERS"
    )
    assert prompt_check.status == "FAIL"
    assert prompt_check.reason == "prompt_layer_hash_mismatch"
    assert result.release_ready is False


def test_local_qa_override_is_explicit_and_never_reports_ready(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(
        tmp_path, pwk_status="BLOCKED — installed Telegram is unavailable"
    )

    with pytest.raises(ValueError, match="explicit local QA override"):
        gate.evaluate_release_gate(tmp_path, mode="local-qa")

    result = gate.evaluate_release_gate(
        tmp_path,
        mode="local-qa",
        allow_local_qa_override=True,
    )

    assert result.release_ready is False
    assert result.exposure_allowed is False
    assert result.local_qa_override is True
    assert result.label == "PRE-GATE / NOT READY"


def test_local_qa_override_cannot_accept_invalid_source_defaults(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(
        tmp_path,
        pwk_status="PARTIAL",
        available_default="enabled",
        mode_default="automatic",
    )

    result = gate.evaluate_release_gate(
        tmp_path,
        mode="local-qa",
        allow_local_qa_override=True,
    )

    assert result.source_defaults_valid is False
    assert result.exposure_allowed is False
    assert {item.case_id for item in result.open_gates} >= {
        "SOURCE-DEFAULT-AVAILABLE",
        "SOURCE-DEFAULT-MODE",
    }


def test_empty_required_catalog_fails_closed(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    (tmp_path / "qa/parallel-orchestrator/cases.md").write_text(
        "# Parallel Work QA Cases\n",
        encoding="utf-8",
    )

    records = gate.load_required_gates(tmp_path)
    open_gates = tuple(item for item in records if item.status != "PASS")

    assert {item.case_id for item in open_gates} == {"CATALOG-PWK"}


def test_mixed_pass_and_partial_status_fails_closed(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(
        tmp_path,
        emotional_status="PASS-AUTOMATED / PARTIAL-LIVE — installed path remains",
    )

    records = gate.load_required_gates(tmp_path)
    open_gates = tuple(item for item in records if item.status != "PASS")

    assert {item.case_id: item.status for item in open_gates} == {
        "EMO-UC-047": "PARTIAL"
    }


def test_escaped_pipe_in_failed_status_cannot_turn_the_gate_green(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    _write_fixture_root(
        tmp_path,
        emotional_status=r"FAIL — see run A \| run B PASS",
    )

    records = gate.load_required_gates(tmp_path)
    open_gates = tuple(item for item in records if item.status != "PASS")

    assert {item.case_id: item.status for item in open_gates} == {
        "EMO-UC-047": "FAIL"
    }


def test_completed_insight_delivery_case_is_a_required_gate(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path, emotional_delivery_status="NOT RUN")

    records = gate.load_required_gates(tmp_path)
    open_gates = tuple(item for item in records if item.status != "PASS")

    assert {item.case_id: item.status for item in open_gates} == {
        "EMO-UC-048": "NOT_RUN"
    }


def test_voice_and_file_worker_parity_cases_are_required_gates(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(
        tmp_path,
        voice_worker_status="NOT RUN",
        file_worker_status="PARTIAL — artifact opening remains",
    )

    records = gate.load_required_gates(tmp_path)
    open_gates = {
        item.case_id: item.status
        for item in records
        if item.case_id in {"MPV-061", "TGDOC-010"}
    }

    assert open_gates == {"MPV-061": "NOT_RUN", "TGDOC-010": "PARTIAL"}


def test_voice_and_file_worker_receipts_require_exact_candidate_and_surface(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed, external_attestation=True
    )
    common = {
        "mode": "local-qa",
        "allow_local_qa_override": True,
        "readiness_facts": _healthy_readiness_facts(prompt_layers),
        "artifact_identity": identity,
        "installed_prompt_bundle_path": prompt_bundle_path,
        "installed_root": installed,
        "runtime_owner_state": _owner_state_path(prompt_bundle_path),
        "external_attestation_authority": gate._test_external_release_authority,
    }
    valid = _qa_case_receipts(gate, identity, externally_authenticated=True)

    verified = gate.evaluate_release_gate(
        root, qa_case_receipts=valid, **common
    )
    assert verified.release_ready is False
    assert verified.qa_receipt_summary["status"] == "verified"

    for case_id in ("MPV-061", "TGDOC-010"):
        missing = json.loads(json.dumps(valid))
        missing["receipts"] = [
            receipt
            for receipt in missing["receipts"]
            if receipt["caseId"] != case_id
        ]
        missing_result = gate.evaluate_release_gate(
            root, qa_case_receipts=missing, **common
        )
        missing_gate = next(
            item for item in missing_result.open_gates if item.case_id == case_id
        )
        assert missing_gate.status == "UNKNOWN"
        assert missing_gate.detail == "qa_receipt_missing"

        wrong_surface = json.loads(json.dumps(valid))
        receipt = next(
            item for item in wrong_surface["receipts"] if item["caseId"] == case_id
        )
        receipt["surface"] = "api"
        surface_result = gate.evaluate_release_gate(
            root, qa_case_receipts=wrong_surface, **common
        )
        surface_gate = next(
            item for item in surface_result.open_gates if item.case_id == case_id
        )
        assert surface_gate.status == "UNKNOWN"
        assert surface_gate.detail == "qa_receipt_surface_mismatch"


def test_service_bound_pass_receipt_requires_signed_live_restart_digest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    receipts = _qa_case_receipts(gate, identity)
    receipt = next(item for item in receipts["receipts"] if item["caseId"] == "TR-026")
    del receipt["serviceAckDigest"]

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=_healthy_readiness_facts(prompt_layers),
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
        qa_case_receipts=receipts,
    )

    tr_gate = next(item for item in result.open_gates if item.case_id == "TR-026")
    assert tr_gate.status == "UNKNOWN"
    assert tr_gate.detail == "qa_receipt_invalid"


def test_status_words_in_requirement_cells_are_not_the_case_result(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path, rel_status="NOT RUN")
    path = tmp_path / "qa/release-readiness/cases.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "| `REL-UC-004` | Claim gate |",
            "| `REL-UC-004` | Leave one PARTIAL case |",
        ),
        encoding="utf-8",
    )

    result = gate.evaluate_release_gate(tmp_path, mode="release")

    rel_gate = next(item for item in result.open_gates if item.case_id == "REL-UC-004")
    assert rel_gate.status == "NOT_RUN"
    assert rel_gate.detail == "NOT RUN"


def test_inline_code_pipe_does_not_shift_the_status_column(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    path = tmp_path / "qa/parallel-orchestrator/cases.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "| `PWK-001` | One mission | Trace | PASS |",
            "| `PWK-001` | Keep `stopping|stop_failed` honest | Trace | PARTIAL |",
        ),
        encoding="utf-8",
    )

    result = gate.evaluate_release_gate(tmp_path, mode="release")

    pwk_gate = next(item for item in result.open_gates if item.case_id == "PWK-001")
    assert pwk_gate.status == "PARTIAL"


def test_future_prefixed_case_id_cannot_silently_leave_the_inventory(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    path = tmp_path / "qa/parallel-orchestrator/cases.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "| `PWK-001` | One mission | Trace | PASS |",
            "| `PWK-001` | One mission | Trace | PASS |\n"
            "| `PWK-SEC-001` | Security branch | Trace | NOT RUN |\n"
            "| `PWK-UC-014a` | Future suffix | Trace | NOT RUN |",
        ),
        encoding="utf-8",
    )

    records = gate.load_required_gates(tmp_path)
    open_gates = tuple(item for item in records if item.status != "PASS")

    assert {item.case_id for item in open_gates} == {
        "PWK-SEC-001",
        "PWK-UC-014a",
    }


def test_case_row_named_status_is_not_mistaken_for_a_header(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    path = tmp_path / "qa/parallel-orchestrator/cases.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "| `PWK-001` | One mission | Trace | PASS |",
            "| `PWK-001` | Status | Trace | NOT RUN |",
        ),
        encoding="utf-8",
    )

    records = gate.load_required_gates(tmp_path)
    open_gates = tuple(item for item in records if item.status != "PASS")

    assert {item.case_id for item in open_gates} == {"PWK-001"}


def test_missing_status_header_fails_closed(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    path = tmp_path / "qa/release-readiness/cases.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "| Automation | Last Run |", "| Automation | Evidence |"
        ),
        encoding="utf-8",
    )

    result = gate.evaluate_release_gate(tmp_path, mode="release")

    assert result.release_ready is False
    assert {
        item.status for item in result.open_gates if item.case_id.startswith("REL-")
    } == {"UNKNOWN"}


def test_duplicate_gate_error_does_not_leak_the_checkout_path(tmp_path: Path) -> None:
    _write_fixture_root(tmp_path)
    path = tmp_path / "qa/emotional-cortex/cases.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "| `EMO-UC-047` | Duplicate | Telegram | Receipt | State | PASS |\n",
        encoding="utf-8",
    )

    duplicate = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--root", str(tmp_path), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert duplicate.returncode == 2
    assert "duplicate release gate EMO-UC-047" in duplicate.stderr
    assert str(tmp_path) not in duplicate.stderr


@pytest.mark.parametrize("option", ["--installed-r", "--runtime-owner-s"])
def test_gate_cli_rejects_abbreviated_identity_authority_options(
    tmp_path: Path, option: str
) -> None:
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), option, str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert f"unrecognized arguments: {option}" in completed.stderr


def test_cli_blocks_release_but_allows_explicit_local_qa_override(
    tmp_path: Path,
) -> None:
    _write_fixture_root(tmp_path, pwk_status="NOT RUN")

    release = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--root", str(tmp_path), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    local_qa = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--root",
            str(tmp_path),
            "--mode",
            "local-qa",
            "--allow-local-qa-override",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert release.returncode == 1
    assert json.loads(release.stdout)["label"] == "NOT READY"
    assert str(tmp_path) not in release.stdout
    assert local_qa.returncode == 1
    assert json.loads(local_qa.stdout)["label"] == "PRE-GATE / NOT READY"
    assert str(tmp_path) not in local_qa.stdout


def test_repository_inventory_contains_original_sequence_and_release_claim_gate() -> (
    None
):
    gate = _load_module()
    result = gate.evaluate_release_gate(ROOT, mode="release")
    case_ids = {item.case_id for item in result.gates}

    assert {f"PWK-UC-{number:03d}" for number in range(14, 20)} <= case_ids
    assert {
        "REL-UC-004",
        "TR-026",
        "EMO-UC-047",
        "EMO-UC-048",
        "MPV-061",
        "TGDOC-010",
    } <= case_ids
    assert result.source_defaults_valid is True
    # Preserve every shared-tree QA row. Full capability parity in PWK-UC-019 is
    # release-blocking and may not be omitted to retain an earlier count.
    expected_case_ids = {
        "EMO-UC-047",
        "EMO-UC-048",
        "MPV-061",
        *(f"PWK-{number:03d}" for number in range(1, 76)),
        *(f"PWK-UC-{number:03d}" for number in range(1, 44)),
        *(f"REL-{number:03d}" for number in range(1, 7)),
        *(f"REL-UC-{number:03d}" for number in range(1, 5)),
        "TGDOC-010",
        "TR-026",
    }
    assert case_ids == expected_case_ids
    assert len(result.gates) == len(expected_case_ids)
    # Catalog prose is inventory only. With no structured receipts, every
    # candidate case remains open even where the Markdown row says PASS.
    assert len(result.open_gates) == len(result.gates)

    parallel_cases = (ROOT / "qa/parallel-orchestrator/cases.md").read_text(
        encoding="utf-8"
    )
    for phrase in [
        "How are you feeling?",
        "channel and model",
        "two independent synthetic HTML",
        "unrelated quick question",
        "Steer only artifact A",
        "separate browser windows",
        "one redacted trace",
    ]:
        assert phrase in parallel_cases

    telegram_cases = (ROOT / "qa/telegram-runtime/cases.md").read_text(encoding="utf-8")
    assert "280 ms" in telegram_cases
    assert "source order" in telegram_cases

    emotional_cases = (ROOT / "qa/emotional-cortex/cases.md").read_text(
        encoding="utf-8"
    )
    assert "request-pinned" in emotional_cases
    assert "native receipt" in emotional_cases
    assert "completed insight" in emotional_cases

    release_cases = (ROOT / "qa/release-readiness/cases.md").read_text(encoding="utf-8")
    for phrase in [
        "one PARTIAL",
        "prompt-layer mismatch",
        "disk pressure",
        "Parallel Work dark",
    ]:
        assert phrase in release_cases


def test_typed_prompt_mismatch_and_storage_pressure_fail_closed_without_changing_qa_rows(
    tmp_path: Path,
) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    facts = _healthy_readiness_facts()
    facts["promptLayers"] = {
        **facts["promptLayers"],
        "status": "unknown",
        "unknownLayerCount": 1,
        "unknownLayerNames": ["unknown"],
        "reason": "prompt_layers_unknown",
    }
    facts["storagePressure"] = {
        "version": 1,
        "status": "critical",
        "usedPercent": 96,
        "availableBytes": 4_300_000_000,
        "thresholdPercent": 95,
        "warningMarginPercent": 10,
    }

    result = gate.evaluate_release_gate(tmp_path, mode="release", readiness_facts=facts)

    assert result.release_ready is False
    assert result.label == "NOT READY"
    assert len(result.gates) == 9
    assert len(result.open_gates) == 9
    assert {gate.status for gate in result.open_gates} == {"UNKNOWN"}
    assert all(record.status == "PASS" for record in gate.load_required_gates(tmp_path))
    assert {check.check_id: check.status for check in result.blocking_checks} == {
        "PROMPT-LAYERS": "FAIL",
        "STORAGE-PRESSURE": "FAIL",
    }
    payload = result.to_dict()
    assert "prompt_layers_unknown" in json.dumps(payload)
    assert "storage_pressure" in json.dumps(payload)


def test_missing_or_malformed_typed_readiness_facts_fail_closed(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)

    missing = gate.evaluate_release_gate(tmp_path, mode="release")
    malformed = gate.evaluate_release_gate(
        tmp_path,
        mode="release",
        readiness_facts={
            "contractVersion": 1,
            "promptLayers": {},
            "storagePressure": {},
        },
    )

    assert missing.release_ready is False
    assert {check.check_id: check.status for check in missing.blocking_checks} == {
        "PROMPT-LAYERS": "UNKNOWN",
        "STORAGE-PRESSURE": "UNKNOWN",
    }
    assert malformed.release_ready is False
    assert all(check.status == "UNKNOWN" for check in malformed.blocking_checks)


def test_typed_storage_warning_also_fails_closed(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path)
    facts = _healthy_readiness_facts()
    facts["storagePressure"] = {
        "version": 1,
        "status": "warning",
        "usedPercent": 85,
        "availableBytes": 8 * 1024 * 1024 * 1024,
        "thresholdPercent": 90,
        "warningMarginPercent": 10,
    }

    result = gate.evaluate_release_gate(tmp_path, mode="release", readiness_facts=facts)

    assert result.release_ready is False
    assert {check.check_id: check.status for check in result.blocking_checks} == {
        "STORAGE-PRESSURE": "FAIL"
    }


def test_release_gate_remeasures_stale_persisted_storage_pressure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    facts = _healthy_readiness_facts(prompt_layers)
    facts["storagePressure"] = {
        "version": 1,
        "status": "critical",
        "usedPercent": 90.058,
        "availableBytes": 4_181_000_000,
        "thresholdPercent": 90,
        "warningMarginPercent": 10,
    }
    probed: list[Path] = []

    def recovered_disk_usage(path: Path) -> SimpleNamespace:
        probed.append(Path(path))
        return SimpleNamespace(total=100_000, used=89_000, free=11_000)

    monkeypatch.setattr(gate.shutil, "disk_usage", recovered_disk_usage)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=facts,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    storage_check = next(
        check
        for check in result.readiness_checks
        if check.check_id == "STORAGE-PRESSURE"
    )
    reported = result.readiness_facts["storagePressure"]
    assert probed == [prompt_bundle_path.parent]
    assert reported["status"] == "warning"
    assert reported["usedPercent"] == 89.0
    assert reported["availableBytes"] == 11_000
    assert storage_check.status == "FAIL"
    assert storage_check.reason == "storage_pressure"
    assert facts["storagePressure"]["usedPercent"] == 90.058


def test_storage_probe_uses_canonical_prompt_artifact_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _load_module()
    canonical_runtime = tmp_path / "canonical-runtime"
    canonical_runtime.mkdir()
    canonical_prompt = canonical_runtime / "prompt-bundle.json"
    canonical_prompt.write_text("{}\n", encoding="utf-8")
    alias_runtime = tmp_path / "runtime-alias"
    alias_runtime.symlink_to(canonical_runtime, target_is_directory=True)
    probed: list[Path] = []

    def disk_usage(path: Path) -> SimpleNamespace:
        probed.append(Path(path))
        return SimpleNamespace(total=100_000, used=40_000, free=60_000)

    monkeypatch.setattr(gate.shutil, "disk_usage", disk_usage)

    measured = gate._remeasure_storage_pressure(
        _healthy_readiness_facts(),
        alias_runtime / "prompt-bundle.json",
    )

    assert isinstance(measured, dict)
    assert probed == [canonical_runtime.resolve()]
    assert measured["storagePressure"]["status"] == "healthy"


def test_release_gate_fails_closed_when_live_storage_probe_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    installed = tmp_path / "installed"
    _write_fixture_root(root)
    gate, prompt_bundle_path, identity, prompt_layers = _write_release_identity_fixture(
        root, installed
    )
    facts = _healthy_readiness_facts(prompt_layers)

    def unavailable_disk_usage(_path: Path) -> SimpleNamespace:
        raise OSError("synthetic unavailable probe")

    monkeypatch.setattr(gate.shutil, "disk_usage", unavailable_disk_usage)

    result = gate.evaluate_release_gate(
        root,
        mode="release",
        readiness_facts=facts,
        artifact_identity=identity,
        installed_prompt_bundle_path=prompt_bundle_path,
        installed_root=installed,
        runtime_owner_state=_owner_state_path(prompt_bundle_path),
    )

    storage_check = next(
        check
        for check in result.readiness_checks
        if check.check_id == "STORAGE-PRESSURE"
    )
    reported = result.readiness_facts["storagePressure"]
    assert reported == {
        "version": 1,
        "status": "critical",
        "usedPercent": 100.0,
        "availableBytes": 0,
        "thresholdPercent": 90,
        "warningMarginPercent": 10,
        "reason": "storage_probe_unavailable",
    }
    assert storage_check.status == "FAIL"
    assert storage_check.reason == "storage_pressure"


def test_cli_rejects_unowned_snapshot_output_even_when_gate_is_open(
    tmp_path: Path,
) -> None:
    _write_fixture_root(tmp_path, pwk_status="PARTIAL")
    facts_path = tmp_path / "facts.json"
    output_path = tmp_path / "compiled" / "parallel-work-release-gate.json"
    facts_path.write_text(json.dumps(_healthy_readiness_facts()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--root",
            str(tmp_path),
            "--readiness-facts",
            str(facts_path),
            "--output",
            str(output_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "requires the exact active runtime owner" in completed.stderr
    assert output_path.exists() is False


def test_source_defaults_accept_automatic_mode_without_waiving_release_gates(tmp_path: Path) -> None:
    gate = _load_module()
    _write_fixture_root(tmp_path, pwk_status="PARTIAL", available_default="true", mode_default="parallel")
    result = gate.evaluate_release_gate(tmp_path)
    assert result.source_defaults_valid is True
    assert result.release_ready is False
    assert result.exposure_allowed is False
