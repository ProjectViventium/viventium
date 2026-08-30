#!/usr/bin/env python3
"""Publisher-rooted, fail-closed release evidence attestation.

The installed candidate must supply a publisher-authenticated SHA-256 digest for
``scripts/viventium/qa_release_attestation_policy.json``. That policy pins one
publisher Ed25519 public key, separate installed-producer keys, the exact
case/surface/verifier requirements, and the complete SSH allowed-signers file.

No private signing key is loaded, created, or trusted by this module. Callers
must provide an externally authorized hardware, offline, or protected-agent
``ExternalSigner`` and an independently protected compare-and-swap
``TrustedLedgerWitness``. A mutable owner-readable file, unrestricted same-user
agent, self-created keypair, or owner-controlled witness is not a release trust
boundary. Missing external authority or witness always prevents release proof.

The parent release evaluator must obtain ``expected_policy_sha256`` and
``expected_candidate_digest`` from a separately publisher-verified, immutable
installed candidate. Values declared by receipts, environment variables, mutable
runtime files, or evidence producers cannot establish trust.
"""

from __future__ import annotations

import base64
import contextlib
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import struct
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Protocol


_FROZEN_DATACLASS_OPTIONS = {
    "frozen": True,
    **({"slots": True} if sys.version_info >= (3, 10) else {}),
}


CONTRACT_VERSION = 1
SSH_KEYGEN = Path("/usr/bin/ssh-keygen")
POLICY_RELATIVE_PATH = Path("scripts/viventium/qa_release_attestation_policy.json")
RECEIPT_NAMESPACE = "viventium-qa-release-receipt-v1"
PRODUCER_NAMESPACE = "viventium-qa-release-producer-v1"
SERVICE_NAMESPACE = "viventium-qa-release-service-v1"
LEDGER_NAMESPACE = "viventium-qa-release-ledger-v1"
RECEIPT_PURPOSE = "viventium.qa.release.receipt.v1"
PRODUCER_PURPOSE = "viventium.qa.release.producer.v1"
SERVICE_PURPOSE = "viventium.qa.release.service.v1"
LEDGER_PURPOSE = "viventium.qa.release.ledger-entry.v1"
LEDGER_FILE_PURPOSE = "viventium.qa.release.ledger.v1"
ZERO_DIGEST = "0" * 64
MAX_POLICY_BYTES = 256 * 1024
MAX_SIGNERS_BYTES = 128 * 1024
MAX_LEDGER_BYTES = 8 * 1024 * 1024
MAX_SIGNATURE_BYTES = 16 * 1024
MAX_PRODUCERS = 64
MAX_CASES = 512
MAX_LEDGER_ENTRIES = 10_000
MAX_RECEIPT_AGE_SECONDS = 86_400
MAX_FUTURE_SKEW_SECONDS = 60
SHA256 = re.compile(r"[0-9a-f]{64}")
SHA256_REF = re.compile(r"sha256:[0-9a-f]{64}")
NONCE = re.compile(r"[0-9a-f]{32}")
SESSION_REF = re.compile(r"qa_[0-9a-f]{24}")
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}")
SIGNER_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9@._:+-]{0,159}")
FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")
SURFACES = frozenset(
    {"api", "cli", "installer", "scheduler", "telegram", "voice", "web", "workbench"}
)

POLICY_FIELDS = frozenset(
    {
        "allowedSigners",
        "cases",
        "contractVersion",
        "maximumFutureSkewSeconds",
        "maximumReceiptAgeSeconds",
        "producers",
        "publisher",
    }
)
RECEIPT_BASE_FIELDS = frozenset(
    {
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "evidenceDigest",
        "ownerBindingSha256",
        "receiptNonce",
        "runAt",
        "status",
        "surface",
        "verifierId",
        "verifierManifestSha256",
    }
)
RECEIPT_ENVELOPE_FIELDS = frozenset(
    {
        "attestationContractVersion",
        "attestationPurpose",
        "attestationSequence",
        "producerAttestations",
        "publisherAttestation",
        "publisherIdentity",
        "serviceAcknowledgements",
    }
)
PRODUCER_BASE_FIELDS = frozenset(
    {
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "evidenceDigest",
        "observationNonce",
        "observedAt",
        "ownerBindingSha256",
        "receiptNonce",
        "serviceAckDigest",
        "serviceAckSessionRef",
        "surface",
        "verifierId",
        "verifierManifestSha256",
    }
)
SERVICE_BASE_FIELDS = frozenset(
    {
        "acknowledgedAt",
        "acknowledgementDigest",
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "ownerBindingSha256",
        "processIdentityDigest",
        "serviceId",
        "sessionRef",
        "surface",
    }
)
SUBATTESTATION_FIELDS = frozenset(
    {"contractVersion", "producerId", "purpose", "signature", "signerIdentity"}
)
LEDGER_ENTRY_FIELDS = frozenset(
    {
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "contractVersion",
        "evidenceDigest",
        "globalPreviousEntryDigest",
        "globalSequence",
        "ownerBindingSha256",
        "previousEntryDigest",
        "purpose",
        "receiptDigest",
        "receiptNonce",
        "recordedAt",
        "sequence",
        "serviceAckDigest",
        "signature",
        "signerIdentity",
        "status",
        "surface",
    }
)
OUTCOME_STATUSES = frozenset({"FAIL", "PARTIAL", "BLOCKED", "REVOKED"})


class AttestationError(RuntimeError):
    """A release-security prerequisite or authenticated claim was rejected."""


class ReceiptSupersededError(AttestationError):
    """An authenticated receipt is no longer the current outcome for its case."""


class ExternalSigner(Protocol):
    """A separately authenticated hardware, offline, or protected-agent signer."""

    def sign(self, payload: bytes, namespace: str) -> str | bytes:
        """Return an OpenSSH armored signature without exposing a private key."""


@dataclass(**_FROZEN_DATACLASS_OPTIONS)
class LedgerHead:
    sequence: int
    entry_digest: str


class TrustedLedgerWitness(Protocol):
    """An external, non-rollbackable compare-and-swap ledger checkpoint."""

    def current(self, scope: str) -> LedgerHead | None:
        """Read the latest protected checkpoint for one installed candidate."""

    def advance(
        self,
        scope: str,
        *,
        expected: LedgerHead | None,
        head: LedgerHead,
    ) -> bool:
        """Advance only when the protected current head exactly equals expected."""


@dataclass(**_FROZEN_DATACLASS_OPTIONS)
class ProducerIdentity:
    producer_id: str
    identity: str
    fingerprint: str
    role: str
    service_id: str | None


@dataclass(**_FROZEN_DATACLASS_OPTIONS)
class CasePolicy:
    case_id: str
    surface: str
    verifier_id: str
    producer_ids: tuple[str, ...]
    service_producer_ids: tuple[str, ...]


@dataclass(**_FROZEN_DATACLASS_OPTIONS)
class TrustPolicy:
    installed_root: Path
    policy_path: Path
    policy_sha256: str
    candidate_digest: str
    allowed_signers_path: Path
    allowed_signers_sha256: str
    publisher_identity: str
    publisher_fingerprint: str
    producers: Mapping[str, ProducerIdentity]
    cases: Mapping[str, CasePolicy]
    maximum_receipt_age_seconds: int
    maximum_future_skew_seconds: int


@dataclass(**_FROZEN_DATACLASS_OPTIONS)
class VerifiedReleaseReceipt:
    case_id: str
    surface: str
    sequence: int
    candidate_digest: str
    artifact_digest: str
    owner_binding_sha256: str
    evidence_digest: str
    signer_identity: str
    producer_ids: tuple[str, ...]
    service_ids: tuple[str, ...]
    ledger_digest: str


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AttestationError("attestation payload is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_dict(value: object, expected: frozenset[str] | set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(expected):
        raise AttestationError(f"{label} has an invalid field contract")
    return value


def _safe_name(value: object, label: str) -> str:
    if not isinstance(value, str) or SAFE_NAME.fullmatch(value) is None:
        raise AttestationError(f"{label} is invalid")
    return value


def _identity(value: object, label: str) -> str:
    if not isinstance(value, str) or SIGNER_IDENTITY.fullmatch(value) is None:
        raise AttestationError(f"{label} is invalid")
    return value


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise AttestationError(f"{label} digest is invalid")
    return value


def _fingerprint(value: object, label: str) -> str:
    if not isinstance(value, str) or FINGERPRINT.fullmatch(value) is None:
        raise AttestationError(f"{label} fingerprint is invalid")
    return value


def _json_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AttestationError("trusted policy contains duplicate fields")
        result[key] = value
    return result


def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
    private: bool,
) -> bytes:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > maximum_bytes
                or before.st_mode & 0o022
                or before.st_uid not in {0, os.getuid()}
                or (private and stat.S_IMODE(before.st_mode) != 0o600)
                or (private and before.st_uid != os.getuid())
            ):
                raise AttestationError(f"{label} is not a trusted regular file")
            payload = bytearray()
            while len(payload) <= maximum_bytes:
                chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        current = path.stat(follow_symlinks=False)
    except (OSError, ValueError) as exc:
        raise AttestationError(f"{label} is unavailable") from exc
    if (
        len(payload) > maximum_bytes
        or before.st_size != len(payload)
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino)
    ):
        raise AttestationError(f"{label} changed while being verified")
    return bytes(payload)


def _safe_installed_path(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise AttestationError(f"{label} is invalid")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise AttestationError(f"{label} escapes the installed candidate")
    try:
        resolved = (root / relative).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AttestationError(f"{label} is unavailable") from exc
    if not resolved.is_relative_to(root):
        raise AttestationError(f"{label} escapes the installed candidate")
    return resolved


def _ssh_ed25519_fingerprint(encoded: str) -> str:
    try:
        wire = base64.b64decode(encoded.encode("ascii"), validate=True)
        if len(wire) < 8:
            raise ValueError("truncated key")
        type_length = struct.unpack(">I", wire[:4])[0]
        type_end = 4 + type_length
        if wire[4:type_end] != b"ssh-ed25519" or len(wire) < type_end + 4:
            raise ValueError("unsupported key type")
        key_length = struct.unpack(">I", wire[type_end : type_end + 4])[0]
        if key_length != 32 or len(wire) != type_end + 4 + key_length:
            raise ValueError("invalid Ed25519 key")
    except (UnicodeError, ValueError, struct.error) as exc:
        raise AttestationError("trusted signer must use one valid Ed25519 key") from exc
    return "SHA256:" + base64.b64encode(hashlib.sha256(wire).digest()).decode(
        "ascii"
    ).rstrip("=")


def _allowed_signer_roots(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("ascii")
    except UnicodeError as exc:
        raise AttestationError("trusted signer roots are invalid") from exc
    roots: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[1] != "ssh-ed25519":
            raise AttestationError("trusted signer roots must be exact Ed25519 entries")
        identity = _identity(parts[0], "trusted signer identity")
        if identity in roots:
            raise AttestationError("trusted signer identities must be distinct")
        roots[identity] = _ssh_ed25519_fingerprint(parts[2])
    if not roots or len(roots) > MAX_PRODUCERS + 1:
        raise AttestationError("trusted signer roots are unavailable")
    return roots


def _bounded_integer(value: object, *, maximum: int, minimum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise AttestationError(f"{label} is invalid")
    return value


def load_trust_policy(
    installed_root: Path,
    *,
    expected_policy_sha256: str | None,
    expected_candidate_digest: str | None,
) -> TrustPolicy:
    """Load only trust roots pinned by a separately verified installed candidate."""

    if not isinstance(expected_policy_sha256, str) or SHA256.fullmatch(
        expected_policy_sha256
    ) is None:
        raise AttestationError("a publisher-pinned trusted policy digest is required")
    candidate_digest = _hash(expected_candidate_digest, "trusted installed candidate")
    try:
        root = Path(installed_root).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AttestationError("trusted installed candidate is unavailable") from exc
    policy_path = root / POLICY_RELATIVE_PATH
    policy_bytes = _read_regular_file(
        policy_path,
        maximum_bytes=MAX_POLICY_BYTES,
        label="trusted publisher policy",
        private=False,
    )
    if hashlib.sha256(policy_bytes).hexdigest() != expected_policy_sha256:
        raise AttestationError("trusted policy digest does not match the installed candidate")
    try:
        decoded = json.loads(policy_bytes, object_pairs_hook=_json_no_duplicates)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise AttestationError("trusted publisher policy is invalid") from exc
    if _canonical_bytes(decoded) != policy_bytes:
        raise AttestationError("trusted publisher policy is not canonical")
    payload = _exact_dict(decoded, POLICY_FIELDS, "trusted publisher policy")
    if payload["contractVersion"] != CONTRACT_VERSION:
        raise AttestationError("trusted policy contract is unsupported")

    signer_file = _exact_dict(payload["allowedSigners"], {"path", "sha256"}, "trusted signers")
    allowed_signers_path = _safe_installed_path(
        root, signer_file["path"], "trusted signer roots"
    )
    allowed_signers_sha256 = _hash(signer_file["sha256"], "trusted signer roots")
    signer_bytes = _read_regular_file(
        allowed_signers_path,
        maximum_bytes=MAX_SIGNERS_BYTES,
        label="trusted signer roots",
        private=False,
    )
    if hashlib.sha256(signer_bytes).hexdigest() != allowed_signers_sha256:
        raise AttestationError("trusted signer roots do not match their candidate pin")
    roots = _allowed_signer_roots(signer_bytes)

    publisher = _exact_dict(payload["publisher"], {"identity", "fingerprint"}, "publisher")
    publisher_identity = _identity(publisher["identity"], "publisher identity")
    publisher_fingerprint = _fingerprint(publisher["fingerprint"], "publisher")
    if roots.get(publisher_identity) != publisher_fingerprint:
        raise AttestationError("publisher signer does not match the pinned trust root")

    raw_producers = payload["producers"]
    if not isinstance(raw_producers, dict) or not raw_producers or len(raw_producers) > MAX_PRODUCERS:
        raise AttestationError("trusted installed producers are unavailable")
    identities = {publisher_identity}
    fingerprints = {publisher_fingerprint}
    producers: dict[str, ProducerIdentity] = {}
    for raw_id, raw in raw_producers.items():
        producer_id = _safe_name(raw_id, "producer identity")
        if not isinstance(raw, dict) or raw.get("role") not in {"observation", "service"}:
            raise AttestationError("trusted producer role is invalid")
        required_fields = {"identity", "fingerprint", "role"}
        if raw["role"] == "service":
            required_fields.add("serviceId")
        producer = _exact_dict(raw, required_fields, "trusted producer")
        identity = _identity(producer["identity"], "producer signer identity")
        fingerprint = _fingerprint(producer["fingerprint"], "producer")
        if identity in identities or fingerprint in fingerprints:
            raise AttestationError("publisher and producer signing roots must be distinct")
        if roots.get(identity) != fingerprint:
            raise AttestationError("producer signer does not match the pinned trust root")
        identities.add(identity)
        fingerprints.add(fingerprint)
        service_id = (
            _safe_name(producer["serviceId"], "trusted service identity")
            if producer["role"] == "service"
            else None
        )
        producers[producer_id] = ProducerIdentity(
            producer_id=producer_id,
            identity=identity,
            fingerprint=fingerprint,
            role=str(producer["role"]),
            service_id=service_id,
        )
    if set(roots) != identities:
        raise AttestationError("trusted signer roots contain undeclared identities")

    raw_cases = payload["cases"]
    if not isinstance(raw_cases, dict) or not raw_cases or len(raw_cases) > MAX_CASES:
        raise AttestationError("trusted QA case policy is unavailable")
    cases: dict[str, CasePolicy] = {}
    for raw_case_id, raw_case in raw_cases.items():
        case_id = _safe_name(raw_case_id, "trusted QA case")
        case = _exact_dict(
            raw_case,
            {"producerIds", "serviceProducerIds", "surface", "verifierId"},
            "trusted QA case",
        )
        surface = case["surface"]
        if surface not in SURFACES:
            raise AttestationError("trusted QA case surface is invalid")
        verifier_id = _safe_name(case["verifierId"], "trusted QA case verifier")
        raw_observers = case["producerIds"]
        raw_services = case["serviceProducerIds"]
        if (
            not isinstance(raw_observers, list)
            or not raw_observers
            or not isinstance(raw_services, list)
            or any(not isinstance(value, str) for value in raw_observers + raw_services)
            or len(set(raw_observers + raw_services)) != len(raw_observers + raw_services)
        ):
            raise AttestationError("trusted QA case producers must be distinct")
        for producer_id in raw_observers:
            if producer_id not in producers or producers[producer_id].role != "observation":
                raise AttestationError("trusted QA observation producer is unavailable")
        for producer_id in raw_services:
            if producer_id not in producers or producers[producer_id].role != "service":
                raise AttestationError("trusted QA service producer is unavailable")
        cases[case_id] = CasePolicy(
            case_id=case_id,
            surface=str(surface),
            verifier_id=verifier_id,
            producer_ids=tuple(raw_observers),
            service_producer_ids=tuple(raw_services),
        )

    return TrustPolicy(
        installed_root=root,
        policy_path=policy_path,
        policy_sha256=expected_policy_sha256,
        candidate_digest=candidate_digest,
        allowed_signers_path=allowed_signers_path,
        allowed_signers_sha256=allowed_signers_sha256,
        publisher_identity=publisher_identity,
        publisher_fingerprint=publisher_fingerprint,
        producers=MappingProxyType(producers),
        cases=MappingProxyType(cases),
        maximum_receipt_age_seconds=_bounded_integer(
            payload["maximumReceiptAgeSeconds"],
            maximum=MAX_RECEIPT_AGE_SECONDS,
            minimum=1,
            label="trusted receipt maximum age",
        ),
        maximum_future_skew_seconds=_bounded_integer(
            payload["maximumFutureSkewSeconds"],
            maximum=MAX_FUTURE_SKEW_SECONDS,
            minimum=0,
            label="trusted receipt future skew",
        ),
    )


def _verify_trust_files(policy: TrustPolicy) -> bytes:
    if not isinstance(policy, TrustPolicy):
        raise AttestationError("trusted publisher policy is unavailable")
    current_policy = _read_regular_file(
        policy.policy_path,
        maximum_bytes=MAX_POLICY_BYTES,
        label="trusted publisher policy",
        private=False,
    )
    if hashlib.sha256(current_policy).hexdigest() != policy.policy_sha256:
        raise AttestationError("trusted policy digest changed after candidate verification")
    signers = _read_regular_file(
        policy.allowed_signers_path,
        maximum_bytes=MAX_SIGNERS_BYTES,
        label="trusted signer roots",
        private=False,
    )
    if hashlib.sha256(signers).hexdigest() != policy.allowed_signers_sha256:
        raise AttestationError("trusted signer roots changed after candidate verification")
    return signers


def release_attestation_metadata(
    policy: TrustPolicy,
    *,
    case_id: str,
) -> dict[str, object]:
    """Expose the public-safe verification contract to Python and Node consumers."""

    _verify_trust_files(policy)
    case = _case(policy, case_id)
    return {
        "contractVersion": CONTRACT_VERSION,
        "algorithm": "ssh-ed25519",
        "candidateDigest": policy.candidate_digest,
        "policySha256": policy.policy_sha256,
        "allowedSignersSha256": policy.allowed_signers_sha256,
        "publisherIdentity": policy.publisher_identity,
        "publisherFingerprint": policy.publisher_fingerprint,
        "namespaces": {
            "receipt": RECEIPT_NAMESPACE,
            "producer": PRODUCER_NAMESPACE,
            "service": SERVICE_NAMESPACE,
            "ledger": LEDGER_NAMESPACE,
        },
        "case": {
            "caseId": case.case_id,
            "surface": case.surface,
            "verifierId": case.verifier_id,
            "producerIds": list(case.producer_ids),
            "serviceProducerIds": list(case.service_producer_ids),
        },
        "requiresExternalPublisherSigner": True,
        "requiresExternalMonotonicWitness": True,
        "requiresProducerAttestation": True,
        "requiresServiceAttestation": bool(case.service_producer_ids),
    }


def _trusted_ssh_keygen() -> str:
    try:
        details = SSH_KEYGEN.stat()
    except OSError as exc:
        raise AttestationError("trusted SSH signature verifier is unavailable") from exc
    if (
        not stat.S_ISREG(details.st_mode)
        or details.st_uid != 0
        or details.st_mode & 0o022
        or not os.access(SSH_KEYGEN, os.X_OK)
    ):
        raise AttestationError("trusted SSH signature verifier is unavailable")
    return str(SSH_KEYGEN)


def _signature_text(value: object, label: str) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeError as exc:
            raise AttestationError(f"{label} signature is invalid") from exc
    if (
        not isinstance(value, str)
        or len(value.encode("utf-8")) > MAX_SIGNATURE_BYTES
        or not value.startswith("-----BEGIN SSH SIGNATURE-----\n")
        or "-----END SSH SIGNATURE-----" not in value
        or "\x00" in value
    ):
        raise AttestationError(f"{label} signature is invalid")
    return value


def _verify_signature(
    payload: bytes,
    signature: object,
    *,
    policy: TrustPolicy,
    identity: str,
    namespace: str,
    label: str,
) -> None:
    trusted_signers = _verify_trust_files(policy)
    armored = _signature_text(signature, label)
    verifier = _trusted_ssh_keygen()
    try:
        with tempfile.TemporaryDirectory(prefix="viventium-qa-attestation-") as temporary:
            signature_path = Path(temporary) / "signature"
            signers_path = Path(temporary) / "trusted-signers"
            create_flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            signature_fd = os.open(signature_path, create_flags, 0o600)
            try:
                signers_fd = os.open(signers_path, create_flags, 0o600)
                try:
                    with os.fdopen(signature_fd, "w+b", closefd=False) as signature_file:
                        signature_file.write(armored.encode("ascii"))
                        signature_file.flush()
                        signature_file.seek(0)
                        signature_path.unlink()
                        with os.fdopen(signers_fd, "w+b", closefd=False) as signer_file:
                            signer_file.write(trusted_signers)
                            signer_file.flush()
                            signer_file.seek(0)
                            signers_path.unlink()
                            result = subprocess.run(
                                [
                                    verifier,
                                    "-Y",
                                    "verify",
                                    "-f",
                                    f"/dev/fd/{signers_fd}",
                                    "-I",
                                    identity,
                                    "-n",
                                    namespace,
                                    "-s",
                                    f"/dev/fd/{signature_fd}",
                                ],
                                input=payload,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                                pass_fds=(signers_fd, signature_fd),
                                check=False,
                                timeout=15,
                            )
                finally:
                    os.close(signers_fd)
            finally:
                os.close(signature_fd)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise AttestationError(f"{label} signature verification failed") from exc
    if result.returncode != 0:
        raise AttestationError(f"{label} signature verification failed")


def _external_signature(
    unsigned: Mapping[str, object],
    *,
    signer: ExternalSigner | None,
    policy: TrustPolicy,
    identity: str,
    namespace: str,
    label: str,
) -> str:
    if signer is None or not callable(getattr(signer, "sign", None)):
        raise AttestationError("an external protected signer is required")
    payload = _canonical_bytes(dict(unsigned))
    try:
        signed = signer.sign(payload, namespace)
    except Exception as exc:
        raise AttestationError(f"external {label} signer is unavailable") from exc
    armored = _signature_text(signed, label)
    _verify_signature(
        payload,
        armored,
        policy=policy,
        identity=identity,
        namespace=namespace,
        label=label,
    )
    return armored


def _now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise AttestationError("attestation verification time is invalid")
    return current.astimezone(timezone.utc)


def _timestamp(
    value: object,
    *,
    policy: TrustPolicy,
    now: datetime,
    label: str,
    allow_stale: bool = False,
) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise AttestationError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise AttestationError(f"{label} timestamp is invalid")
    instant = parsed.astimezone(timezone.utc)
    if instant > now + timedelta(seconds=policy.maximum_future_skew_seconds):
        raise AttestationError(f"{label} timestamp is in the future")
    if not allow_stale and now - instant > timedelta(seconds=policy.maximum_receipt_age_seconds):
        raise AttestationError(f"{label} is stale")
    return instant


def _case(policy: TrustPolicy, case_id: object) -> CasePolicy:
    if not isinstance(case_id, str) or case_id not in policy.cases:
        raise AttestationError("QA case is absent from the publisher-pinned policy")
    return policy.cases[case_id]


def _service_claims(
    payload: Mapping[str, object],
    case: CasePolicy,
    *,
    label: str,
) -> None:
    digest = payload.get("serviceAckDigest", "")
    session = payload.get("serviceAckSessionRef", "")
    if case.service_producer_ids:
        if (
            not isinstance(digest, str)
            or SHA256_REF.fullmatch(digest) is None
            or not isinstance(session, str)
            or SESSION_REF.fullmatch(session) is None
        ):
            raise AttestationError(f"{label} service acknowledgment is invalid")
    elif digest != "" or session != "":
        raise AttestationError(f"{label} service acknowledgment is unexpected")


def _validate_producer_base(
    observation: object,
    *,
    producer_id: str,
    policy: TrustPolicy,
    now: datetime,
) -> tuple[dict, CasePolicy, ProducerIdentity]:
    payload = _exact_dict(observation, PRODUCER_BASE_FIELDS, "producer observation")
    case = _case(policy, payload["caseId"])
    producer = policy.producers.get(producer_id)
    if (
        producer is None
        or producer.role != "observation"
        or producer_id not in case.producer_ids
    ):
        raise AttestationError("producer identity is not authorized for this case")
    if payload["surface"] != case.surface:
        raise AttestationError("producer observation surface does not match the QA case")
    if payload["candidateDigest"] != policy.candidate_digest:
        raise AttestationError("producer observation candidate does not match the installed candidate")
    for field, label in (
        ("artifactDigest", "producer artifact"),
        ("ownerBindingSha256", "producer owner"),
        ("evidenceDigest", "producer evidence"),
        ("verifierManifestSha256", "producer verifier"),
    ):
        _hash(payload[field], label)
    if payload["verifierId"] != case.verifier_id:
        raise AttestationError("producer observation verifier does not match the QA case")
    for field in ("observationNonce", "receiptNonce"):
        if not isinstance(payload[field], str) or NONCE.fullmatch(payload[field]) is None:
            raise AttestationError("producer observation nonce is invalid")
    _timestamp(payload["observedAt"], policy=policy, now=now, label="producer observation")
    _service_claims(payload, case, label="producer observation")
    return payload, case, producer


def sign_producer_observation(
    observation: Mapping[str, object],
    *,
    producer_id: str,
    policy: TrustPolicy,
    signer: ExternalSigner | None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Sign one actual installed producer observation with its pinned Ed25519 key."""

    checked_at = _now(now)
    payload, _case_policy, producer = _validate_producer_base(
        dict(observation), producer_id=producer_id, policy=policy, now=checked_at
    )
    unsigned = {
        **payload,
        "contractVersion": CONTRACT_VERSION,
        "producerId": producer_id,
        "purpose": PRODUCER_PURPOSE,
        "signerIdentity": producer.identity,
    }
    return {
        **unsigned,
        "signature": _external_signature(
            unsigned,
            signer=signer,
            policy=policy,
            identity=producer.identity,
            namespace=PRODUCER_NAMESPACE,
            label="producer",
        ),
    }


def _verify_producer_observation(
    observation: object,
    *,
    policy: TrustPolicy,
    receipt: Mapping[str, object],
    now: datetime,
) -> str:
    item = _exact_dict(
        observation,
        PRODUCER_BASE_FIELDS | SUBATTESTATION_FIELDS,
        "producer observation",
    )
    producer_id = _safe_name(item["producerId"], "producer identity")
    base = {key: item[key] for key in PRODUCER_BASE_FIELDS}
    _validated, _case_policy, producer = _validate_producer_base(
        base, producer_id=producer_id, policy=policy, now=now
    )
    if (
        item["contractVersion"] != CONTRACT_VERSION
        or item["purpose"] != PRODUCER_PURPOSE
        or item["signerIdentity"] != producer.identity
    ):
        raise AttestationError("producer identity or signature domain is invalid")
    for field in (
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "evidenceDigest",
        "ownerBindingSha256",
        "receiptNonce",
        "surface",
        "verifierId",
        "verifierManifestSha256",
    ):
        if item[field] != receipt.get(field):
            raise AttestationError(f"producer observation {field} does not match the receipt")
    for field in ("serviceAckDigest", "serviceAckSessionRef"):
        if item[field] != receipt.get(field, ""):
            raise AttestationError("producer observation service acknowledgment does not match")
    unsigned = {key: value for key, value in item.items() if key != "signature"}
    _verify_signature(
        _canonical_bytes(unsigned),
        item["signature"],
        policy=policy,
        identity=producer.identity,
        namespace=PRODUCER_NAMESPACE,
        label="producer",
    )
    return producer_id


def _validate_service_base(
    observation: object,
    *,
    producer_id: str,
    policy: TrustPolicy,
    now: datetime,
) -> tuple[dict, CasePolicy, ProducerIdentity]:
    payload = _exact_dict(observation, SERVICE_BASE_FIELDS, "service acknowledgment")
    case = _case(policy, payload["caseId"])
    producer = policy.producers.get(producer_id)
    if (
        producer is None
        or producer.role != "service"
        or producer_id not in case.service_producer_ids
        or payload["serviceId"] != producer.service_id
    ):
        raise AttestationError("service acknowledgment producer identity is invalid")
    if payload["surface"] != case.surface:
        raise AttestationError("service acknowledgment surface does not match the QA case")
    if payload["candidateDigest"] != policy.candidate_digest:
        raise AttestationError("service acknowledgment candidate does not match")
    for field, label in (
        ("artifactDigest", "service artifact"),
        ("ownerBindingSha256", "service owner"),
        ("processIdentityDigest", "service process"),
    ):
        _hash(payload[field], label)
    if (
        not isinstance(payload["acknowledgementDigest"], str)
        or SHA256_REF.fullmatch(payload["acknowledgementDigest"]) is None
    ):
        raise AttestationError("service acknowledgment digest is invalid")
    if (
        not isinstance(payload["sessionRef"], str)
        or SESSION_REF.fullmatch(payload["sessionRef"]) is None
    ):
        raise AttestationError("service acknowledgment session is invalid")
    _timestamp(payload["acknowledgedAt"], policy=policy, now=now, label="service acknowledgment")
    return payload, case, producer


def sign_service_acknowledgement(
    observation: Mapping[str, object],
    *,
    producer_id: str,
    policy: TrustPolicy,
    signer: ExternalSigner | None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Sign one sanitized, real service acknowledgment under its service-only key."""

    payload, _case_policy, producer = _validate_service_base(
        dict(observation), producer_id=producer_id, policy=policy, now=_now(now)
    )
    unsigned = {
        **payload,
        "contractVersion": CONTRACT_VERSION,
        "producerId": producer_id,
        "purpose": SERVICE_PURPOSE,
        "signerIdentity": producer.identity,
    }
    return {
        **unsigned,
        "signature": _external_signature(
            unsigned,
            signer=signer,
            policy=policy,
            identity=producer.identity,
            namespace=SERVICE_NAMESPACE,
            label="service",
        ),
    }


def _verify_service_acknowledgement(
    observation: object,
    *,
    policy: TrustPolicy,
    receipt: Mapping[str, object],
    now: datetime,
) -> tuple[str, str, str]:
    item = _exact_dict(
        observation,
        SERVICE_BASE_FIELDS | SUBATTESTATION_FIELDS,
        "service acknowledgment",
    )
    producer_id = _safe_name(item["producerId"], "service producer identity")
    base = {key: item[key] for key in SERVICE_BASE_FIELDS}
    _validated, _case_policy, producer = _validate_service_base(
        base, producer_id=producer_id, policy=policy, now=now
    )
    if (
        item["contractVersion"] != CONTRACT_VERSION
        or item["purpose"] != SERVICE_PURPOSE
        or item["signerIdentity"] != producer.identity
    ):
        raise AttestationError("service producer identity or signature domain is invalid")
    for field in (
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "ownerBindingSha256",
        "surface",
    ):
        if item[field] != receipt.get(field):
            raise AttestationError(f"service acknowledgment {field} does not match")
    if item["sessionRef"] != receipt.get("serviceAckSessionRef"):
        raise AttestationError("service acknowledgment session does not match")
    unsigned = {key: value for key, value in item.items() if key != "signature"}
    _verify_signature(
        _canonical_bytes(unsigned),
        item["signature"],
        policy=policy,
        identity=producer.identity,
        namespace=SERVICE_NAMESPACE,
        label="service",
    )
    return producer_id, str(item["serviceId"]), str(item["processIdentityDigest"])


def service_acknowledgement_digest(acknowledgements: Sequence[Mapping[str, object]]) -> str:
    """Bind the exact ordered, producer-signed service acknowledgments."""

    if not isinstance(acknowledgements, Sequence) or isinstance(
        acknowledgements, (str, bytes)
    ):
        raise AttestationError("service acknowledgment set is invalid")
    normalized = [dict(item) for item in acknowledgements]
    return "sha256:" + _digest(normalized)


def _validate_receipt_base(
    receipt: object,
    *,
    policy: TrustPolicy,
    now: datetime,
    envelope: bool,
) -> tuple[dict, CasePolicy]:
    if not isinstance(receipt, dict):
        raise AttestationError("release receipt is invalid")
    case = _case(policy, receipt.get("caseId"))
    expected = set(RECEIPT_BASE_FIELDS)
    if case.service_producer_ids:
        expected.update({"serviceAckDigest", "serviceAckSessionRef"})
    if envelope:
        expected.update(RECEIPT_ENVELOPE_FIELDS)
    item = _exact_dict(receipt, expected, "release receipt")
    if item["status"] != "PASS":
        raise AttestationError("release receipt must represent an authenticated PASS")
    if item["surface"] != case.surface:
        raise AttestationError("release receipt surface does not match the QA case")
    if item["candidateDigest"] != policy.candidate_digest:
        raise AttestationError("release receipt candidate does not match the installed candidate")
    for field, label in (
        ("artifactDigest", "release artifact"),
        ("ownerBindingSha256", "release owner"),
        ("evidenceDigest", "release evidence"),
        ("verifierManifestSha256", "release verifier"),
    ):
        _hash(item[field], label)
    if item["verifierId"] != case.verifier_id:
        raise AttestationError("release receipt verifier does not match the QA case")
    if not isinstance(item["receiptNonce"], str) or NONCE.fullmatch(item["receiptNonce"]) is None:
        raise AttestationError("release receipt nonce is invalid")
    _timestamp(item["runAt"], policy=policy, now=now, label="release receipt")
    _service_claims(item, case, label="release receipt")
    return item, case


def _validate_attestation_sets(
    receipt: Mapping[str, object],
    *,
    producers: object,
    services: object,
    policy: TrustPolicy,
    case: CasePolicy,
    now: datetime,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(producers, list) or not isinstance(services, list):
        raise AttestationError("producer and service attestation sets are invalid")
    producer_ids = tuple(
        _verify_producer_observation(item, policy=policy, receipt=receipt, now=now)
        for item in producers
    )
    if producer_ids != case.producer_ids:
        raise AttestationError("producer attestations do not match the publisher-pinned case")
    verified_services = tuple(
        _verify_service_acknowledgement(item, policy=policy, receipt=receipt, now=now)
        for item in services
    )
    service_producer_ids = tuple(item[0] for item in verified_services)
    if service_producer_ids != case.service_producer_ids:
        raise AttestationError("service attestations do not match the publisher-pinned case")
    process_digests = tuple(item[2] for item in verified_services)
    if len(set(process_digests)) != len(process_digests):
        raise AttestationError("service attestations cannot reuse one service process")
    if case.service_producer_ids:
        if receipt.get("serviceAckDigest") != service_acknowledgement_digest(services):
            raise AttestationError("service acknowledgment digest does not match signed services")
    elif services:
        raise AttestationError("service attestations are not authorized for this QA case")
    return producer_ids, tuple(item[1] for item in verified_services)


def _require_witness(witness: TrustedLedgerWitness | None) -> TrustedLedgerWitness:
    if (
        witness is None
        or not callable(getattr(witness, "current", None))
        or not callable(getattr(witness, "advance", None))
    ):
        raise AttestationError("an external monotonic ledger witness is required")
    return witness


def _private_runtime_directory(path: Path) -> Path:
    try:
        directory = path.parent.resolve(strict=True)
        details = directory.stat()
    except (OSError, RuntimeError) as exc:
        raise AttestationError("private ledger directory is unavailable") from exc
    if (
        not stat.S_ISDIR(details.st_mode)
        or stat.S_IMODE(details.st_mode) != 0o700
        or details.st_uid != os.getuid()
        or path.name in {"", ".", ".."}
    ):
        raise AttestationError("private ledger directory must be owner-only")
    return directory / path.name


@contextlib.contextmanager
def _locked_ledger(path: Path) -> Iterator[Path]:
    ledger = _private_runtime_directory(Path(path))
    lock_path = ledger.parent / f".{ledger.name}.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_uid != os.getuid()
            or details.st_nlink != 1
        ):
            raise AttestationError("private ledger lock is invalid")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except (OSError, RuntimeError) as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise AttestationError("private ledger lock is unavailable") from exc
    try:
        yield ledger
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_private_json(path: Path, payload: object) -> None:
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(_canonical_bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        directory = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise AttestationError("private release ledger could not be persisted") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _witness_scope(policy: TrustPolicy, ledger_path: Path) -> str:
    return _digest(
        {
            "candidateDigest": policy.candidate_digest,
            "contractVersion": CONTRACT_VERSION,
            "ledgerPathSha256": hashlib.sha256(str(ledger_path).encode("utf-8")).hexdigest(),
            "policySha256": policy.policy_sha256,
            "purpose": "viventium.qa.release.ledger-witness.v1",
        }
    )


def _head(value: object) -> LedgerHead | None:
    if value is None:
        return None
    if (
        not isinstance(value, LedgerHead)
        or isinstance(value.sequence, bool)
        or not isinstance(value.sequence, int)
        or value.sequence < 1
        or SHA256.fullmatch(value.entry_digest) is None
    ):
        raise AttestationError("external monotonic ledger witness returned an invalid checkpoint")
    return value


def _case_scope(entry: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(entry["candidateDigest"]),
        str(entry["ownerBindingSha256"]),
        str(entry["caseId"]),
    )


def _advance_witness_checkpoint(
    witness: TrustedLedgerWitness,
    *,
    scope: str,
    previous_head: LedgerHead | None,
    head: LedgerHead,
) -> None:
    try:
        accepted = witness.advance(scope, expected=previous_head, head=head)
    except Exception as exc:
        raise AttestationError("external monotonic ledger witness is unavailable") from exc
    if accepted is not True:
        raise AttestationError("external monotonic ledger witness rejected the update")
    try:
        confirmed = _head(witness.current(scope))
    except Exception as exc:
        if isinstance(exc, AttestationError):
            raise
        raise AttestationError("external monotonic ledger witness is unavailable") from exc
    if confirmed != head:
        raise AttestationError("external monotonic ledger witness did not retain the update")


def _load_ledger(
    path: Path,
    *,
    policy: TrustPolicy,
    witness: TrustedLedgerWitness,
    now: datetime,
    recover_interrupted: bool = False,
) -> tuple[list[dict[str, object]], LedgerHead | None]:
    if not path.exists() and not path.is_symlink():
        entries: list[dict[str, object]] = []
    else:
        raw = _read_regular_file(
            path,
            maximum_bytes=MAX_LEDGER_BYTES,
            label="private release ledger",
            private=True,
        )
        try:
            decoded = json.loads(raw, object_pairs_hook=_json_no_duplicates)
        except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise AttestationError("private release ledger is invalid") from exc
        if _canonical_bytes(decoded) != raw:
            raise AttestationError("private release ledger is not canonical")
        ledger = _exact_dict(
            decoded, {"contractVersion", "entries", "purpose"}, "private release ledger"
        )
        if ledger["contractVersion"] != CONTRACT_VERSION or ledger["purpose"] != LEDGER_FILE_PURPOSE:
            raise AttestationError("private release ledger contract is invalid")
        if not isinstance(ledger["entries"], list) or len(ledger["entries"]) > MAX_LEDGER_ENTRIES:
            raise AttestationError("private release ledger entry list is invalid")
        entries = ledger["entries"]

    global_previous = ZERO_DIGEST
    case_heads: dict[tuple[str, str, str], tuple[int, str]] = {}
    used_nonces: set[str] = set()
    for position, value in enumerate(entries, start=1):
        entry = _exact_dict(value, LEDGER_ENTRY_FIELDS, "release ledger entry")
        case = _case(policy, entry["caseId"])
        if (
            entry["contractVersion"] != CONTRACT_VERSION
            or entry["purpose"] != LEDGER_PURPOSE
            or entry["signerIdentity"] != policy.publisher_identity
            or entry["candidateDigest"] != policy.candidate_digest
            or entry["surface"] != case.surface
            or entry["status"] not in {"PASS", *OUTCOME_STATUSES}
            or isinstance(entry["globalSequence"], bool)
            or entry["globalSequence"] != position
            or entry["globalPreviousEntryDigest"] != global_previous
        ):
            raise AttestationError("release ledger entry chain is invalid")
        for field, label in (
            ("artifactDigest", "ledger artifact"),
            ("ownerBindingSha256", "ledger owner"),
            ("evidenceDigest", "ledger evidence"),
            ("receiptDigest", "ledger receipt"),
            ("previousEntryDigest", "ledger previous entry"),
        ):
            _hash(entry[field], label)
        if not isinstance(entry["receiptNonce"], str) or NONCE.fullmatch(entry["receiptNonce"]) is None:
            raise AttestationError("release ledger receipt nonce is invalid")
        if entry["receiptNonce"] in used_nonces:
            raise AttestationError("release ledger contains a receipt nonce replay")
        used_nonces.add(entry["receiptNonce"])
        expected_sequence, previous_case_digest = case_heads.get(
            _case_scope(entry), (0, ZERO_DIGEST)
        )
        if (
            isinstance(entry["sequence"], bool)
            or entry["sequence"] != expected_sequence + 1
            or entry["previousEntryDigest"] != previous_case_digest
        ):
            raise AttestationError("release ledger case sequence is invalid")
        if entry["serviceAckDigest"] and (
            not isinstance(entry["serviceAckDigest"], str)
            or SHA256_REF.fullmatch(entry["serviceAckDigest"]) is None
        ):
            raise AttestationError("release ledger service acknowledgment is invalid")
        _timestamp(
            entry["recordedAt"],
            policy=policy,
            now=now,
            label="release ledger entry",
            allow_stale=True,
        )
        unsigned = {key: item for key, item in entry.items() if key != "signature"}
        _verify_signature(
            _canonical_bytes(unsigned),
            entry["signature"],
            policy=policy,
            identity=policy.publisher_identity,
            namespace=LEDGER_NAMESPACE,
            label="ledger",
        )
        entry_digest = _digest(entry)
        global_previous = entry_digest
        case_heads[_case_scope(entry)] = (int(entry["sequence"]), entry_digest)

    expected_head = LedgerHead(len(entries), global_previous) if entries else None
    scope = _witness_scope(policy, path)
    try:
        current = _head(witness.current(scope))
    except Exception as exc:
        if isinstance(exc, AttestationError):
            raise
        raise AttestationError("external monotonic ledger witness is unavailable") from exc
    if current != expected_head:
        # A verified one-entry-ahead ledger is durable intent, not committed proof.
        # Only a locked issuer may retry its exact protected compare-and-swap.
        previous_head = (
            LedgerHead(len(entries) - 1, _digest(entries[-2]))
            if len(entries) > 1
            else None
        )
        if (
            not recover_interrupted
            or expected_head is None
            or current != previous_head
        ):
            raise AttestationError("release ledger rollback rejected by the external witness")
        _advance_witness_checkpoint(
            witness,
            scope=scope,
            previous_head=current,
            head=expected_head,
        )
    return entries, expected_head


def _next_entry(
    *,
    entries: list[dict[str, object]],
    receipt: Mapping[str, object],
    status: str,
    receipt_digest: str,
    now: datetime,
    policy: TrustPolicy,
    signer: ExternalSigner | None,
) -> dict[str, object]:
    nonce = str(receipt["receiptNonce"])
    if any(item.get("receiptNonce") == nonce for item in entries):
        raise AttestationError("release receipt nonce replay was rejected")
    scope = _case_scope(receipt)
    previous_case = next(
        (item for item in reversed(entries) if _case_scope(item) == scope), None
    )
    case_sequence = int(previous_case["sequence"]) + 1 if previous_case else 1
    unsigned = {
        "artifactDigest": str(receipt["artifactDigest"]),
        "candidateDigest": str(receipt["candidateDigest"]),
        "caseId": str(receipt["caseId"]),
        "contractVersion": CONTRACT_VERSION,
        "evidenceDigest": str(receipt.get("evidenceDigest") or ZERO_DIGEST),
        "globalPreviousEntryDigest": _digest(entries[-1]) if entries else ZERO_DIGEST,
        "globalSequence": len(entries) + 1,
        "ownerBindingSha256": str(receipt["ownerBindingSha256"]),
        "previousEntryDigest": _digest(previous_case) if previous_case else ZERO_DIGEST,
        "purpose": LEDGER_PURPOSE,
        "receiptDigest": receipt_digest,
        "receiptNonce": nonce,
        "recordedAt": now.isoformat(),
        "sequence": case_sequence,
        "serviceAckDigest": str(receipt.get("serviceAckDigest") or ""),
        "signerIdentity": policy.publisher_identity,
        "status": status,
        "surface": str(receipt["surface"]),
    }
    return {
        **unsigned,
        "signature": _external_signature(
            unsigned,
            signer=signer,
            policy=policy,
            identity=policy.publisher_identity,
            namespace=LEDGER_NAMESPACE,
            label="ledger",
        ),
    }


def _persist_and_advance(
    path: Path,
    *,
    entries: list[dict[str, object]],
    previous_head: LedgerHead | None,
    entry: dict[str, object],
    policy: TrustPolicy,
    witness: TrustedLedgerWitness,
) -> None:
    payload = {
        "contractVersion": CONTRACT_VERSION,
        "entries": [*entries, entry],
        "purpose": LEDGER_FILE_PURPOSE,
    }
    _atomic_private_json(path, payload)
    head = LedgerHead(len(entries) + 1, _digest(entry))
    _advance_witness_checkpoint(
        witness,
        scope=_witness_scope(policy, path),
        previous_head=previous_head,
        head=head,
    )


def issue_release_receipt(
    receipt: Mapping[str, object],
    *,
    producer_attestations: Sequence[Mapping[str, object]],
    service_acknowledgements: Sequence[Mapping[str, object]],
    policy: TrustPolicy,
    signer: ExternalSigner | None,
    ledger_path: Path,
    ledger_witness: TrustedLedgerWitness | None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Issue a release receipt only after genuine installed producers attest it."""

    checked_at = _now(now)
    witness = _require_witness(ledger_witness)
    if signer is None or not callable(getattr(signer, "sign", None)):
        raise AttestationError("an external protected signer is required")
    item, case = _validate_receipt_base(
        dict(receipt), policy=policy, now=checked_at, envelope=False
    )
    producers = [dict(value) for value in producer_attestations]
    services = [dict(value) for value in service_acknowledgements]
    _validate_attestation_sets(
        item, producers=producers, services=services, policy=policy, case=case, now=checked_at
    )

    with _locked_ledger(Path(ledger_path)) as ledger:
        entries, previous_head = _load_ledger(
            ledger,
            policy=policy,
            witness=witness,
            now=checked_at,
            recover_interrupted=True,
        )
        scope = _case_scope(item)
        previous_case = next(
            (entry for entry in reversed(entries) if _case_scope(entry) == scope), None
        )
        matching_nonce = next(
            (entry for entry in entries if entry["receiptNonce"] == item["receiptNonce"]),
            None,
        )
        if matching_nonce is not None and (
            matching_nonce is not previous_case or matching_nonce["status"] != "PASS"
        ):
            raise AttestationError("release receipt nonce replay was rejected")
        sequence = (
            int(matching_nonce["sequence"])
            if matching_nonce is not None
            else int(previous_case["sequence"]) + 1
            if previous_case
            else 1
        )
        unsigned = {
            **item,
            "attestationContractVersion": CONTRACT_VERSION,
            "attestationPurpose": RECEIPT_PURPOSE,
            "attestationSequence": sequence,
            "producerAttestations": producers,
            "publisherIdentity": policy.publisher_identity,
            "serviceAcknowledgements": services,
        }
        authenticated = {
            **unsigned,
            "publisherAttestation": _external_signature(
                unsigned,
                signer=signer,
                policy=policy,
                identity=policy.publisher_identity,
                namespace=RECEIPT_NAMESPACE,
                label="publisher",
            ),
        }
        if matching_nonce is not None:
            # Idempotent retries may return only the exact already signed receipt.
            if matching_nonce["receiptDigest"] != _digest(authenticated):
                raise AttestationError("release receipt nonce replay was rejected")
            return authenticated
        entry = _next_entry(
            entries=entries,
            receipt=authenticated,
            status="PASS",
            receipt_digest=_digest(authenticated),
            now=checked_at,
            policy=policy,
            signer=signer,
        )
        _persist_and_advance(
            ledger,
            entries=entries,
            previous_head=previous_head,
            entry=entry,
            policy=policy,
            witness=witness,
        )
    return authenticated


def record_case_outcome(
    *,
    case_id: str,
    status: str,
    owner_binding_sha256: str,
    artifact_digest: str,
    policy: TrustPolicy,
    signer: ExternalSigner | None,
    ledger_path: Path,
    ledger_witness: TrustedLedgerWitness | None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Append an authenticated failure/revocation that permanently supersedes PASS."""

    if status not in OUTCOME_STATUSES:
        raise AttestationError("release ledger outcome must fail, block, or revoke the case")
    checked_at = _now(now)
    witness = _require_witness(ledger_witness)
    case = _case(policy, case_id)
    receipt = {
        "artifactDigest": _hash(artifact_digest, "release artifact"),
        "candidateDigest": policy.candidate_digest,
        "caseId": case_id,
        "evidenceDigest": ZERO_DIGEST,
        "ownerBindingSha256": _hash(owner_binding_sha256, "release owner"),
        "receiptNonce": secrets.token_hex(16),
        "surface": case.surface,
    }
    with _locked_ledger(Path(ledger_path)) as ledger:
        entries, previous_head = _load_ledger(
            ledger,
            policy=policy,
            witness=witness,
            now=checked_at,
            recover_interrupted=True,
        )
        entry = _next_entry(
            entries=entries,
            receipt=receipt,
            status=status,
            receipt_digest=ZERO_DIGEST,
            now=checked_at,
            policy=policy,
            signer=signer,
        )
        _persist_and_advance(
            ledger,
            entries=entries,
            previous_head=previous_head,
            entry=entry,
            policy=policy,
            witness=witness,
        )
    return entry


def verify_release_receipt(
    receipt: Mapping[str, object],
    *,
    policy: TrustPolicy,
    ledger_path: Path,
    ledger_witness: TrustedLedgerWitness | None,
    expected_case_id: str,
    expected_surface: str,
    expected_candidate_digest: str,
    expected_artifact_digest: str,
    expected_owner_binding: str,
    expected_verifier_id: str,
    expected_verifier_manifest_sha256: str,
    expected_evidence_digest: str | None = None,
    expected_service_ack_digest: str | None = None,
    expected_service_ack_session_ref: str | None = None,
    now: datetime | None = None,
) -> VerifiedReleaseReceipt:
    """Verify all publisher, producer, service, context, and anti-replay proofs."""

    checked_at = _now(now)
    witness = _require_witness(ledger_witness)
    if not isinstance(receipt, dict):
        raise AttestationError("release receipt is invalid")
    comparisons = (
        ("caseId", expected_case_id, "case"),
        ("surface", expected_surface, "surface"),
        ("candidateDigest", expected_candidate_digest, "candidate"),
        ("artifactDigest", expected_artifact_digest, "artifact"),
        ("ownerBindingSha256", expected_owner_binding, "owner"),
        ("verifierId", expected_verifier_id, "verifier"),
        ("verifierManifestSha256", expected_verifier_manifest_sha256, "verifier"),
    )
    for field, expected, label in comparisons:
        if receipt.get(field) != expected:
            raise AttestationError(f"release receipt {label} binding does not match")
    if expected_evidence_digest is not None and receipt.get("evidenceDigest") != expected_evidence_digest:
        raise AttestationError("release receipt evidence binding does not match")
    if expected_candidate_digest != policy.candidate_digest:
        raise AttestationError("release receipt candidate is not the publisher-pinned candidate")
    item, case = _validate_receipt_base(
        receipt, policy=policy, now=checked_at, envelope=True
    )
    expected_ack = expected_service_ack_digest if expected_service_ack_digest is not None else ""
    expected_session = (
        expected_service_ack_session_ref if expected_service_ack_session_ref is not None else ""
    )
    if (
        item.get("serviceAckDigest", "") != expected_ack
        or item.get("serviceAckSessionRef", "") != expected_session
    ):
        raise AttestationError("release receipt service acknowledgment binding does not match")
    if (
        item["attestationContractVersion"] != CONTRACT_VERSION
        or item["attestationPurpose"] != RECEIPT_PURPOSE
        or item["publisherIdentity"] != policy.publisher_identity
        or isinstance(item["attestationSequence"], bool)
        or not isinstance(item["attestationSequence"], int)
        or item["attestationSequence"] < 1
    ):
        raise AttestationError("publisher signature identity or receipt domain is invalid")
    unsigned = {
        key: value for key, value in item.items() if key != "publisherAttestation"
    }
    _verify_signature(
        _canonical_bytes(unsigned),
        item["publisherAttestation"],
        policy=policy,
        identity=policy.publisher_identity,
        namespace=RECEIPT_NAMESPACE,
        label="publisher",
    )
    producer_ids, service_ids = _validate_attestation_sets(
        item,
        producers=item["producerAttestations"],
        services=item["serviceAcknowledgements"],
        policy=policy,
        case=case,
        now=checked_at,
    )
    with _locked_ledger(Path(ledger_path)) as ledger:
        entries, _head_value = _load_ledger(
            ledger, policy=policy, witness=witness, now=checked_at
        )
        scope = _case_scope(item)
        current = next(
            (entry for entry in reversed(entries) if _case_scope(entry) == scope), None
        )
    if current is None:
        raise AttestationError("release receipt has no authenticated ledger entry")
    if current["status"] != "PASS" or current["sequence"] != item["attestationSequence"]:
        raise ReceiptSupersededError("release receipt was superseded or revoked")
    if (
        current["receiptDigest"] != _digest(item)
        or current["receiptNonce"] != item["receiptNonce"]
        or current["artifactDigest"] != item["artifactDigest"]
        or current["evidenceDigest"] != item["evidenceDigest"]
        or current["serviceAckDigest"] != item.get("serviceAckDigest", "")
    ):
        raise AttestationError("release receipt does not match its signed ledger entry")
    return VerifiedReleaseReceipt(
        case_id=str(item["caseId"]),
        surface=str(item["surface"]),
        sequence=int(item["attestationSequence"]),
        candidate_digest=str(item["candidateDigest"]),
        artifact_digest=str(item["artifactDigest"]),
        owner_binding_sha256=str(item["ownerBindingSha256"]),
        evidence_digest=str(item["evidenceDigest"]),
        signer_identity=str(item["publisherIdentity"]),
        producer_ids=producer_ids,
        service_ids=service_ids,
        ledger_digest=_digest(current),
    )
