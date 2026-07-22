from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "viventium" / "verify_native_release_sequence.py"
POLICY_VERIFIER = ROOT / "scripts" / "viventium" / "verify_native_bootstrap_policy.py"
INSTALLER = ROOT / "scripts" / "viventium" / "install_native_payload.py"


def load_installer():
    scripts = str(INSTALLER.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "install_native_payload_sequence_test", INSTALLER
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_policy(root: Path, *, sequence: object = 1) -> None:
    (root / "release.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_base": "https://github.com/ProjectViventium/viventium/releases/download",
                "release_id": "0.4.0",
                "release_tag": "v0.4.0",
                "sequence": sequence,
            }
        ),
        encoding="utf-8",
    )


def create_signer(root: Path) -> tuple[Path, Path]:
    key = root / "signing-key"
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-C",
            "qa@example.invalid",
            "-N",
            "",
            "-f",
            str(key),
        ],
        check=True,
    )
    public = subprocess.run(
        ["/usr/bin/ssh-keygen", "-y", "-f", str(key)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    allowed = root / "allowed_signers"
    allowed.write_text(f"bootstrap@viventium.example {public}\n", encoding="utf-8")
    return key, allowed


def write_history_entry(
    history: Path,
    key: Path,
    *,
    index: int,
    release_tag: str,
    release_id: str,
    sequence: int,
) -> Path:
    entry = history / f"{index:06d}"
    entry.mkdir(parents=True)
    (entry / "record.json").write_text(
        json.dumps({"release_tag": release_tag}), encoding="utf-8"
    )
    manifest = entry / "viventium-native-bootstrap-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_tag": release_tag,
                "release_id": release_id,
                "sequence": sequence,
                "artifacts": {
                    "arm64": {
                        "filename": "ViventiumBootstrap-arm64.zip",
                        "sha256": "a" * 64,
                        "size": 100,
                        "uncompressed_size": 400,
                    },
                    "x86_64": {
                        "filename": "ViventiumBootstrap-x86_64.zip",
                        "sha256": "b" * 64,
                        "size": 101,
                        "uncompressed_size": 404,
                    },
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-Y",
            "sign",
            "-q",
            "-f",
            str(key),
            "-n",
            "viventium-bootstrap",
            str(manifest),
        ],
        check=True,
    )
    return entry


def run_verifier(
    history: Path, allowed_signers: Path, *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--history-root",
            str(history),
            "--allowed-signers",
            str(allowed_signers),
            "--candidate-release-tag",
            "v0.4.1",
            "--candidate-sequence",
            "2",
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_embedded_release_policy_requires_positive_non_boolean_sequence(
    tmp_path: Path,
) -> None:
    installer = load_installer()
    write_policy(tmp_path, sequence=7)
    assert installer.load_policy(tmp_path)["sequence"] == 7

    for invalid in (True, 0, -1, "7", 1_000_000_000):
        write_policy(tmp_path, sequence=invalid)
        with pytest.raises(installer.BootstrapError, match="sequence"):
            installer.load_policy(tmp_path)


def test_install_capacity_accounts_for_download_expansion_and_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = load_installer()
    support = tmp_path / "support"
    download_root = tmp_path / "download"
    support.mkdir()
    download_root.mkdir()
    candidate = SimpleNamespace(
        payload={
            "artifact": {
                "size": 4 * 1024 * 1024 * 1024,
                "uncompressed_size": 8 * 1024 * 1024 * 1024,
            }
        }
    )
    required = (
        candidate.payload["artifact"]["size"]
        + candidate.payload["artifact"]["uncompressed_size"]
        + installer.NATIVE_INSTALL_RESERVE_BYTES
    )
    usage = SimpleNamespace(total=1 << 40, used=1, free=required - 1)
    monkeypatch.setattr(installer.shutil, "disk_usage", lambda _path: usage)

    with pytest.raises(installer.BootstrapError, match="free disk space"):
        installer.preflight_install_capacity(candidate, support, download_root)


def test_verified_payload_must_match_embedded_release_identity_and_sequence() -> None:
    installer = load_installer()
    policy = {"release_id": "0.4.0", "sequence": 7}

    installer.validate_candidate_policy(
        SimpleNamespace(release_id="0.4.0", sequence=7), policy
    )
    for candidate in (
        SimpleNamespace(release_id="0.3.0", sequence=7),
        SimpleNamespace(release_id="0.4.0", sequence=6),
        SimpleNamespace(release_id="0.4.0", sequence=8),
    ):
        with pytest.raises(installer.BootstrapError, match="does not match"):
            installer.validate_candidate_policy(candidate, policy)


def test_release_history_requires_first_sequence_to_be_one(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    _key, allowed_signers = create_signer(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--history-root",
            str(history),
            "--allowed-signers",
            str(allowed_signers),
            "--candidate-release-tag",
            "v0.4.0",
            "--candidate-sequence",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "first Native release sequence must be 1" in completed.stderr


def test_release_history_requires_exact_next_sequence(tmp_path: Path) -> None:
    history = tmp_path / "history"
    key, allowed_signers = create_signer(tmp_path)
    write_history_entry(
        history, key, index=1, release_tag="v0.4.0", release_id="0.4.0", sequence=1
    )

    completed = run_verifier(history, allowed_signers)
    assert completed.returncode == 0, completed.stderr

    skipped = run_verifier(history, allowed_signers, "--candidate-sequence", "3")
    assert skipped.returncode != 0
    assert "must be exactly 2" in skipped.stderr


def test_release_history_rejects_missing_signed_sequence(tmp_path: Path) -> None:
    history = tmp_path / "history"
    key, allowed_signers = create_signer(tmp_path)
    write_history_entry(
        history, key, index=1, release_tag="v0.4.0", release_id="0.4.0", sequence=1
    )
    write_history_entry(
        history, key, index=3, release_tag="v0.4.2", release_id="0.4.2", sequence=3
    )

    completed = run_verifier(history, allowed_signers, "--candidate-sequence", "4")

    assert completed.returncode != 0
    assert "incomplete; missing sequence 2" in completed.stderr


def test_release_history_rejects_duplicate_sequence_or_candidate_tag(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history"
    key, allowed_signers = create_signer(tmp_path)
    write_history_entry(
        history, key, index=1, release_tag="v0.4.0", release_id="0.4.0", sequence=1
    )
    write_history_entry(
        history,
        key,
        index=2,
        release_tag="v0.4.0-hotfix",
        release_id="0.4.0-hotfix",
        sequence=1,
    )

    duplicate = run_verifier(history, allowed_signers)
    assert duplicate.returncode != 0
    assert "duplicate published Native sequence 1" in duplicate.stderr

    for child in (history / "000002").iterdir():
        child.unlink()
    (history / "000002").rmdir()
    write_history_entry(
        history, key, index=2, release_tag="v0.4.1", release_id="0.4.1", sequence=2
    )
    reused_tag = run_verifier(history, allowed_signers, "--candidate-sequence", "3")
    assert reused_tag.returncode != 0
    assert (
        "candidate release tag already has Native release history" in reused_tag.stderr
    )


def test_release_history_rejects_tampered_signed_index(tmp_path: Path) -> None:
    history = tmp_path / "history"
    key, allowed_signers = create_signer(tmp_path)
    entry = write_history_entry(
        history, key, index=1, release_tag="v0.4.0", release_id="0.4.0", sequence=1
    )
    manifest = entry / "viventium-native-bootstrap-manifest.json"
    manifest.write_bytes(
        manifest.read_bytes().replace(b'"sequence":1', b'"sequence":9')
    )

    completed = run_verifier(history, allowed_signers)

    assert completed.returncode != 0
    assert "bootstrap signature is invalid" in completed.stderr


def test_release_history_rejects_noncanonical_but_validly_signed_index(
    tmp_path: Path,
) -> None:
    history = tmp_path / "history"
    key, allowed_signers = create_signer(tmp_path)
    entry = write_history_entry(
        history,
        key,
        index=1,
        release_tag="v0.4.0",
        release_id="0.4.0",
        sequence=1,
    )
    manifest = entry / "viventium-native-bootstrap-manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    Path(f"{manifest}.sig").unlink()
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-Y",
            "sign",
            "-q",
            "-f",
            str(key),
            "-n",
            "viventium-bootstrap",
            str(manifest),
        ],
        check=True,
    )

    completed = run_verifier(history, allowed_signers)

    assert completed.returncode != 0
    assert "canonical JSON" in completed.stderr


def test_release_history_rejects_unsafe_or_malformed_records(tmp_path: Path) -> None:
    history = tmp_path / "history"
    _key, allowed_signers = create_signer(tmp_path)
    entry = history / "000001"
    entry.mkdir(parents=True)
    (entry / "record.json").write_text("{}\n", encoding="utf-8")

    malformed = run_verifier(history, allowed_signers)
    assert malformed.returncode != 0
    assert "history record is invalid" in malformed.stderr

    (entry / "record.json").unlink()
    (entry / "record.json").symlink_to(tmp_path / "missing")
    unsafe = run_verifier(history, allowed_signers)
    assert unsafe.returncode != 0
    assert "history record is unsafe" in unsafe.stderr


def test_public_bootstrap_policy_must_match_approved_release_authority(
    tmp_path: Path,
) -> None:
    _key, allowed_signers = create_signer(tmp_path)
    signer_fields = allowed_signers.read_text(encoding="utf-8").split()
    public = " ".join(signer_fields[1:3])
    allowed_signers.write_text(
        f"releases@viventium.example {public}\n", encoding="utf-8"
    )
    team = tmp_path / "apple-team-id"
    team.write_text("ABCDE12345\n", encoding="utf-8")
    install_script = tmp_path / "install.sh"
    install_script.write_text(
        "\n".join(
            (
                f'NATIVE_BOOTSTRAP_ALLOWED_SIGNER="bootstrap@viventium.example {public}"',
                'NATIVE_BOOTSTRAP_TEAM_ID="ABCDE12345"',
                'NATIVE_BOOTSTRAP_MINIMUM_SEQUENCE="7"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(POLICY_VERIFIER),
        "--install-script",
        str(install_script),
        "--allowed-signers",
        str(allowed_signers),
        "--apple-team-id",
        str(team),
        "--sequence",
        "7",
    ]

    accepted = subprocess.run(command, check=False, capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stderr

    key_blob = public.split()[1]
    allowed_signers.write_text(
        f"releases@viventium.example ecdsa-sha2-nistp256 {key_blob}\n",
        encoding="utf-8",
    )
    install_script.write_text(
        "\n".join(
            (
                "NATIVE_BOOTSTRAP_ALLOWED_SIGNER=\"bootstrap@viventium.example "
                f"ecdsa-sha2-nistp256 {key_blob}\"",
                'NATIVE_BOOTSTRAP_TEAM_ID="ABCDE12345"',
                'NATIVE_BOOTSTRAP_MINIMUM_SEQUENCE="7"',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    unsupported = subprocess.run(command, check=False, capture_output=True, text=True)
    assert unsupported.returncode != 0
    assert "key type is invalid" in unsupported.stderr

    allowed_signers.write_text(
        f"releases@viventium.example {public}\n", encoding="utf-8"
    )

    install_script.write_text(
        'NATIVE_BOOTSTRAP_ALLOWED_SIGNER=""\n'
        'NATIVE_BOOTSTRAP_TEAM_ID=""\n'
        'NATIVE_BOOTSTRAP_MINIMUM_SEQUENCE="7"\n',
        encoding="utf-8",
    )
    missing = subprocess.run(command, check=False, capture_output=True, text=True)
    assert missing.returncode != 0
    assert "public Native bootstrap trust is not provisioned" in missing.stderr
