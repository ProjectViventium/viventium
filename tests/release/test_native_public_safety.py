from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER = REPO_ROOT / "scripts" / "viventium" / "verify_native_public_safety.py"


def synthetic_macos_home(*parts: str) -> str:
    return "/" + "/".join(("Users", *parts))


def run_verifier(candidate: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--candidate-root",
            str(candidate),
            *extra,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def write(path: Path, content: bytes | str = b"fixture\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    return path


def candidate_fixture(tmp_path: Path) -> Path:
    candidate = tmp_path / "candidate"
    write(candidate / "payload" / "runtime" / "defaults" / "prompt-bundle.json", '{"prompt_root":"."}\n')
    write(candidate / "payload" / "runtime" / "librechat" / "node_modules" / "example" / "README.md", "/home/example is documentation\n")
    write(candidate / "payload" / "runtime" / "librechat" / "node_modules" / "example" / "logs" / "index.js", "export {}\n")
    write(
        candidate
        / "bootstrap"
        / "ViventiumBootstrap.app"
        / "Contents"
        / "Resources"
        / "runtime"
        / "python"
        / "README.md",
        synthetic_macos_home("upstream-builder", "source")
        + " and sk-"
        + "x" * 32
        + " are third-party metadata\n",
    )
    write(candidate / "payload" / "release-metadata" / "build.json", '{"mode":"candidate"}\n')
    write(candidate / "bootstrap" / "ViventiumBootstrap.app" / "Contents" / "Info.plist", "<plist/>\n")
    return candidate


def test_native_public_safety_accepts_a_clean_candidate(tmp_path: Path) -> None:
    completed = run_verifier(candidate_fixture(tmp_path), "--forbid-prefix", "/private/build/root")

    assert completed.returncode == 0, completed.stderr
    assert '"status":"pass"' in completed.stdout


def test_native_public_safety_rejects_forbidden_artifacts(tmp_path: Path) -> None:
    candidate = candidate_fixture(tmp_path)
    write(candidate / "payload" / "runtime" / "librechat" / "logs" / ".request-audit.json")
    write(candidate / "payload" / "runtime" / "librechat" / "node_modules" / "example" / ".cache" / "compiler.json")
    write(candidate / "payload" / "runtime" / "python" / "lib" / "__pycache__" / "module.pyc")

    completed = run_verifier(candidate)

    assert completed.returncode != 0
    assert "forbidden artifact path" in completed.stderr
    assert "logs/.request-audit.json" in completed.stderr
    assert ".cache/compiler.json" in completed.stderr
    assert "__pycache__/module.pyc" in completed.stderr


def test_native_public_safety_rejects_a_symlinked_candidate_root(tmp_path: Path) -> None:
    candidate = candidate_fixture(tmp_path)
    linked_candidate = tmp_path / "linked-candidate"
    linked_candidate.symlink_to(candidate, target_is_directory=True)

    completed = run_verifier(linked_candidate)

    assert completed.returncode != 0
    assert "candidate root must be a real directory" in completed.stderr


def test_native_public_safety_scans_binary_files_for_exact_producer_prefixes(tmp_path: Path) -> None:
    candidate = candidate_fixture(tmp_path)
    producer_root = "/private/var/folders/aa/build-workspace"
    write(
        candidate / "payload" / "runtime" / "python" / "lib" / "module.bin",
        b"\x00compiled-at:" + producer_root.encode() + b"/module.py\x00",
    )

    completed = run_verifier(candidate, "--forbid-prefix", producer_root)

    assert completed.returncode != 0
    assert "forbidden producer prefix" in completed.stderr
    assert "module.bin" in completed.stderr


def test_native_public_safety_rejects_private_paths_and_secrets_in_owned_outputs(tmp_path: Path) -> None:
    candidate = candidate_fixture(tmp_path)
    write(
        candidate / "payload" / "runtime" / "defaults" / "prompt-bundle.json",
        '{"path":"'
        + synthetic_macos_home("build-owner", "private", "prompt.md")
        + '","api_key":"sk-'
        + "x" * 32
        + '"}\n',
    )

    completed = run_verifier(candidate)

    assert completed.returncode != 0
    assert "private absolute path" in completed.stderr
    assert "high-confidence secret" in completed.stderr


def test_native_public_safety_scans_customized_librechat_outside_dependencies(tmp_path: Path) -> None:
    candidate = candidate_fixture(tmp_path)
    write(
        candidate / "payload" / "runtime" / "librechat" / "api" / "server.js",
        f'const localPath = "{synthetic_macos_home("private-builder", "worktree")}";\n'
        'const leaked = "sk-' + "z" * 32 + '";\n',
    )

    completed = run_verifier(candidate)

    assert completed.returncode != 0
    assert "private absolute path" in completed.stderr
    assert "high-confidence secret" in completed.stderr
    assert "payload/runtime/librechat/api/server.js" in completed.stderr
