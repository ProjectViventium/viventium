from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ensure_app_support_layout_is_owner_private_under_public_umask(
    tmp_path: Path,
) -> None:
    app_support = tmp_path / "support"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "umask 022; "
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                f"ensure_app_support_layout '{app_support}'"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    for directory in (
        app_support,
        app_support / "runtime",
        app_support / "state",
        app_support / "state" / "continuity",
        app_support / "snapshots",
        app_support / "logs",
    ):
        assert directory.is_dir()
        assert directory.stat().st_mode & 0o777 == 0o700


def test_ensure_app_support_layout_refuses_symlinked_managed_directory(
    tmp_path: Path,
) -> None:
    app_support = tmp_path / "support"
    external = tmp_path / "external"
    external.mkdir(mode=0o755)
    app_support.symlink_to(external, target_is_directory=True)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                f"ensure_app_support_layout '{app_support}'"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert external.stat().st_mode & 0o777 == 0o755
    assert not (external / "runtime").exists()


@pytest.mark.parametrize(
    "candidate_kind",
    ["filesystem_root", "home", "relative", "dotdot", "workspace", "symlink_parent"],
)
def test_ensure_app_support_layout_refuses_broad_or_ambiguous_roots_without_mutation(
    tmp_path: Path,
    candidate_kind: str,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir(mode=0o755)
    external = tmp_path / "external"
    external.mkdir(mode=0o755)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(external, target_is_directory=True)
    if candidate_kind == "filesystem_root":
        candidate = Path("/")
    elif candidate_kind == "home":
        candidate = fake_home
    elif candidate_kind == "relative":
        candidate = Path("relative-app-support")
    elif candidate_kind == "dotdot":
        candidate = tmp_path / "safe" / ".." / "escaped"
    elif candidate_kind == "workspace":
        candidate = REPO_ROOT
    else:
        candidate = linked_parent / "Viventium"

    candidate_mode_before = candidate.stat().st_mode if candidate.exists() else None
    home_mode_before = fake_home.stat().st_mode
    external_mode_before = external.stat().st_mode

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"REPO_ROOT={str(REPO_ROOT)!r}\n"
                f"WORKSPACE_ROOT={str(REPO_ROOT.parent)!r}\n"
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                f"ensure_app_support_layout {str(candidate)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "HOME": str(fake_home)},
    )

    assert completed.returncode != 0
    if candidate_mode_before is not None:
        assert candidate.stat().st_mode == candidate_mode_before
    assert fake_home.stat().st_mode == home_mode_before
    assert external.stat().st_mode == external_mode_before
    assert not (external / "runtime").exists()
    if candidate_kind == "relative":
        assert not (REPO_ROOT / candidate).exists()
    if candidate_kind == "dotdot":
        assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize(
    "protected_suffix",
    ["", "Documents", "Library/Application Support"],
)
def test_ensure_app_support_layout_rejects_trailing_slash_protected_roots(
    tmp_path: Path,
    protected_suffix: str,
) -> None:
    fake_home = tmp_path / "home"
    (fake_home / "Documents").mkdir(parents=True)
    (fake_home / "Library" / "Application Support").mkdir(parents=True)
    protected = fake_home / protected_suffix if protected_suffix else fake_home
    before_mode = protected.stat().st_mode

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                f"ensure_app_support_layout {f'{protected}/'!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "HOME": str(fake_home)},
    )

    assert completed.returncode != 0
    assert protected.stat().st_mode == before_mode
    assert not (protected / "runtime").exists()
    assert not (protected / "state").exists()


def test_resolve_existing_product_python_prefers_ready_bootstrap_without_mutating_it(
    tmp_path: Path,
) -> None:
    bootstrap_root = tmp_path / "bootstrap-python"
    bootstrap_python = bootstrap_root / "bin" / "python3"
    bootstrap_python.parent.mkdir(parents=True)
    bootstrap_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"-\" ]]; then\n"
        "  payload=\"$(cat)\"\n"
        "  if [[ \"$payload\" == *'find_spec(\"yaml\")'* ]]; then exit 0; fi\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    bootstrap_python.chmod(0o755)
    before = bootstrap_python.stat().st_mtime_ns

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                "resolve_existing_product_python yaml"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            **dict(os.environ),
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
        },
    )

    assert completed.stdout.strip() == str(bootstrap_python)
    assert bootstrap_python.stat().st_mtime_ns == before


def test_resolve_repo_python_skips_present_but_unrunnable_interpreter(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    broken = fake_bin / "python3.12"
    broken.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    broken.chmod(0o755)
    working = fake_bin / "python3"
    working.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    working.chmod(0o755)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"PATH={str(fake_bin)!r}:/bin:/usr/bin\n"
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                "resolve_repo_python\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={**os.environ, "VIVENTIUM_PYTHON_BIN": ""},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "python3"


def test_bootstrap_python_falls_back_after_first_interpreter_cannot_create_venv(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    bad_marker = tmp_path / "bad-attempted"
    good_marker = tmp_path / "good-attempted"
    broken = fake_bin / "python3.12"
    broken.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        f"  touch {str(bad_marker)!r}\n"
        "  mkdir -p \"$3/bin\"\n"
        "  touch \"$3/partial-only\"\n"
        "  printf '#!/bin/sh\\nexit 0\\n' >\"$3/bin/python3\"\n"
        "  chmod +x \"$3/bin/python3\"\n"
        "  exit 1\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    broken.chmod(0o755)
    working = fake_bin / "python3"
    working.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        f"  touch {str(good_marker)!r}\n"
        "  mkdir -p \"$3/bin\"\n"
        "  cat >\"$3/bin/python3\" <<'PYEOF'\n"
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"pip\" ] && [ \"${3:-}\" = \"--version\" ]; then exit 0; fi\n"
        "exit 1\n"
        "PYEOF\n"
        "  chmod +x \"$3/bin/python3\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    working.chmod(0o755)
    bootstrap_root = tmp_path / "bootstrap-python"

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"PATH={str(fake_bin)!r}:/bin:/usr/bin\n"
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                "create_bootstrap_python python3.12\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
            "VIVENTIUM_PYTHON_BIN": "",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == str(bootstrap_root / "bin" / "python3")
    assert bad_marker.exists()
    assert good_marker.exists()
    assert (bootstrap_root / "bin" / "python3").is_file()
    assert not (bootstrap_root / "partial-only").exists()


def test_bootstrap_python_creates_default_app_support_layout_on_true_first_install(
    tmp_path: Path,
) -> None:
    app_support = tmp_path / "new-app-support"
    fake_python = tmp_path / "working-python"
    fake_python.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  cat >\"$3/bin/python3\" <<'PYEOF'\n"
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"pip\" ] && [ \"${3:-}\" = \"--version\" ]; then exit 0; fi\n"
        "exit 1\n"
        "PYEOF\n"
        "  chmod +x \"$3/bin/python3\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                f"create_bootstrap_python {str(fake_python)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": "",
            "VIVENTIUM_PYTHON_BIN": "",
        },
    )

    bootstrap_root = app_support / "state" / "bootstrap-python"
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == str(bootstrap_root / "bin" / "python3")
    assert bootstrap_root.is_dir()
    for directory in (app_support, app_support / "state"):
        assert directory.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("receipt_kind", ["missing", "pid_reused"])
def test_bootstrap_python_lock_recovers_interrupted_or_reused_pid_owner(
    tmp_path: Path,
    receipt_kind: str,
) -> None:
    bootstrap_root = tmp_path / "bootstrap-python"
    lock_dir = tmp_path / "bootstrap-python.lock"
    lock_dir.mkdir(mode=0o700)
    if receipt_kind == "pid_reused":
        (lock_dir / "owner").write_text(
            f"pid={os.getpid()}\n"
            "start=definitely-not-this-process\n"
            "token=stale-owner\n"
            "created=1\n",
            encoding="utf-8",
        )
        (lock_dir / "owner").chmod(0o600)
    stale_time = time.time() - 10
    os.utime(lock_dir, (stale_time, stale_time))

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                "acquire_bootstrap_python_lock\n"
                "release_bootstrap_python_lock\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
        },
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr
    assert not lock_dir.exists()


def test_bootstrap_python_rebuilds_inline_only_partial_environment(
    tmp_path: Path,
) -> None:
    bootstrap_root = tmp_path / "bootstrap-python"
    partial = bootstrap_root / "bin" / "python3"
    partial.parent.mkdir(parents=True)
    partial.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    partial.chmod(0o755)
    base_python = tmp_path / "working-python"
    base_python.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  cat >\"$3/bin/python3\" <<'PYEOF'\n"
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"pip\" ] && [ \"${3:-}\" = \"--version\" ]; then exit 0; fi\n"
        "exit 1\n"
        "PYEOF\n"
        "  chmod +x \"$3/bin/python3\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    base_python.chmod(0o755)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                f"create_bootstrap_python {str(base_python)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
            "VIVENTIUM_PYTHON_BIN": "",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == str(bootstrap_root / "bin" / "python3")
    assert subprocess.run(
        [str(bootstrap_root / "bin" / "python3"), "-m", "pip", "--version"],
        check=False,
    ).returncode == 0


def test_bootstrap_python_failure_preserves_existing_partial_environment(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    broken = fake_bin / "python3.12"
    broken.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  printf '#!/bin/sh\\nexit 0\\n' >\"$3/bin/python3\"\n"
        "  chmod +x \"$3/bin/python3\"\n"
        "  exit 1\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    broken.chmod(0o755)
    for candidate_name in ("python3.11", "python3.10", "python3", "python"):
        (fake_bin / candidate_name).symlink_to(broken.name)
    bootstrap_root = tmp_path / "bootstrap-python"
    bootstrap_root.mkdir()
    preserved = bootstrap_root / "preserved-partial"
    preserved.write_text("keep for recovery\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"PATH={str(fake_bin)!r}:/bin:/usr/bin\n"
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                "create_bootstrap_python python3.12\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
            "VIVENTIUM_PYTHON_BIN": "",
        },
    )

    assert completed.returncode != 0
    assert "Failed to create a usable Viventium bootstrap Python environment" in completed.stderr
    assert preserved.read_text(encoding="utf-8") == "keep for recovery\n"


@pytest.mark.parametrize(
    "unsafe_kind",
    ("home", "app_support", "workspace", "dotdot", "symlink_parent"),
)
def test_bootstrap_python_refuses_broad_or_ambiguous_roots_without_deleting(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    app_support = tmp_path / "app-support"
    app_support.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    symlink_parent = tmp_path / "linked-parent"
    symlink_parent.symlink_to(real_parent, target_is_directory=True)
    roots = {
        "home": home,
        "app_support": app_support,
        "workspace": workspace,
        "dotdot": tmp_path / "safe" / ".." / "bootstrap-python",
        "symlink_parent": symlink_parent / "bootstrap-python",
    }
    root = roots[unsafe_kind]
    protected_root = (
        real_parent / "bootstrap-python"
        if unsafe_kind == "symlink_parent"
        else root
    )
    protected_root.mkdir(parents=True, exist_ok=True)
    sentinel = protected_root / "must-survive"
    sentinel.write_text("preserved\n", encoding="utf-8")
    broken_python = tmp_path / "broken-python"
    broken_python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    broken_python.chmod(0o755)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
                f"create_bootstrap_python {str(broken_python)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "HOME": str(home),
            "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(root),
        },
    )

    assert completed.returncode != 0
    assert "unsafe Viventium bootstrap Python root" in completed.stderr
    assert sentinel.read_text(encoding="utf-8") == "preserved\n"


def test_concurrent_bootstrap_python_repairs_publish_one_complete_environment(
    tmp_path: Path,
) -> None:
    bootstrap_root = tmp_path / "bootstrap-python"
    fake_python = tmp_path / "python3.12"
    fake_python.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  owner=\"$3/.owner-$$\"\n"
        "  touch \"$owner\"\n"
        "  sleep 0.4\n"
        "  [ -f \"$owner\" ] || exit 3\n"
        "  cat >\"$3/bin/python3\" <<'PYEOF'\n"
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"pip\" ] && [ \"${3:-}\" = \"--version\" ]; then exit 0; fi\n"
        "exit 1\n"
        "PYEOF\n"
        "  chmod +x \"$3/bin/python3\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    command = [
        "/bin/bash",
        "-c",
        (
            f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
            f"create_bootstrap_python {str(fake_python)!r}\n"
        ),
    ]
    env = {
        **os.environ,
        "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
        "VIVENTIUM_PYTHON_BIN": "",
    }

    first = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    time.sleep(0.1)
    second = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    first_stdout, first_stderr = first.communicate(timeout=10)
    second_stdout, second_stderr = second.communicate(timeout=10)

    assert first.returncode == 0, first_stderr
    assert second.returncode == 0, second_stderr
    expected = str(bootstrap_root / "bin" / "python3")
    assert first_stdout.strip() == expected
    assert second_stdout.strip() == expected
    assert subprocess.run(
        [expected, "-m", "pip", "--version"],
        check=False,
    ).returncode == 0
    assert not (tmp_path / "bootstrap-python.lock").exists()
    assert not list(tmp_path.glob("bootstrap-python.build.*"))


def test_concurrent_requirements_repairs_serialize_pip_and_stamp_writes(
    tmp_path: Path,
) -> None:
    bootstrap_root = tmp_path / "bootstrap-python"
    pip_active = tmp_path / "pip-active"
    overlap = tmp_path / "pip-overlap"
    fake_python = tmp_path / "python3.12"
    fake_python.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"venv\" ]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  cat >\"$3/bin/python3\" <<'PYEOF'\n"
        "#!/bin/sh\n"
        f"active={str(pip_active)!r}\n"
        f"overlap={str(overlap)!r}\n"
        "if [ \"${1:-}\" = \"-\" ]; then cat >/dev/null; exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"pip\" ] && [ \"${3:-}\" = \"--version\" ]; then exit 0; fi\n"
        "if [ \"${1:-}\" = \"-m\" ] && [ \"${2:-}\" = \"pip\" ] && [ \"${3:-}\" = \"install\" ]; then\n"
        "  if ! mkdir \"$active\" 2>/dev/null; then touch \"$overlap\"; exit 7; fi\n"
        "  sleep 0.4\n"
        "  rmdir \"$active\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n"
        "PYEOF\n"
        "  chmod +x \"$3/bin/python3\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("PyYAML==6.0.2\n", encoding="utf-8")
    command = [
        "/bin/bash",
        "-c",
        (
            f"source {str(REPO_ROOT / 'scripts/viventium/common.sh')!r}\n"
            f"ensure_python_requirements_file {str(fake_python)!r} {str(requirements)!r}\n"
        ),
    ]
    env = {
        **os.environ,
        "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
        "VIVENTIUM_PYTHON_BIN": "",
    }
    first = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    time.sleep(0.1)
    second = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    first_stdout, first_stderr = first.communicate(timeout=10)
    second_stdout, second_stderr = second.communicate(timeout=10)

    assert first.returncode == 0, first_stderr
    assert second.returncode == 0, second_stderr
    assert first_stdout.strip() == str(bootstrap_root / "bin" / "python3")
    assert second_stdout.strip() == str(bootstrap_root / "bin" / "python3")
    assert not overlap.exists()
    assert not pip_active.exists()
    assert (bootstrap_root / "requirements.sha256").is_file()
    assert not (tmp_path / "bootstrap-python.lock").exists()


def test_ensure_python_module_retries_with_break_system_packages(tmp_path: Path) -> None:
    marker = tmp_path / "yaml-installed"
    fake_base_python = tmp_path / "python3.12"
    fake_base_python.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail

MARKER="{marker}"
if [[ "${{1:-}}" == "-" ]]; then
  payload="$(cat)"
  if [[ "$payload" == *'find_spec("yaml")'* ]]; then
    if [[ -f "$MARKER" ]]; then
      exit 0
    fi
    exit 1
  fi
  exit 0
fi

if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "venv" ]]; then
  root="${{3:-}}"
  mkdir -p "$root/bin"
  cat >"$root/bin/python3" <<'PYEOF'
#!/usr/bin/env bash
set -euo pipefail
MARKER="{marker}"
if [[ "${{1:-}}" == "-" ]]; then
  payload="$(cat)"
  if [[ "$payload" == *'find_spec("yaml")'* && -f "$MARKER" ]]; then
    exit 0
  fi
  if [[ "$payload" == *'find_spec("yaml")'* ]]; then
    exit 1
  fi
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "--version" ]]; then
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "install" && "${{4:-}}" == "PyYAML" ]]; then
  echo "externally-managed-environment" >&2
  exit 1
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "install" && "${{4:-}}" == "--break-system-packages" && "${{5:-}}" == "PyYAML" ]]; then
  touch "$MARKER"
  exit 0
fi
exit 0
PYEOF
  chmod +x "$root/bin/python3"
  exit 0
fi

exit 0
""",
        encoding="utf-8",
    )
    fake_base_python.chmod(0o755)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                f"ensure_python_module '{fake_base_python}' yaml PyYAML"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            **dict(os.environ),
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(tmp_path / "bootstrap-python"),
        },
    )

    assert completed.returncode == 0
    assert marker.exists()


def test_ensure_python_requirements_file_recreates_unusable_bootstrap_python(tmp_path: Path) -> None:
    bootstrap_root = tmp_path / "bootstrap-python"
    bogus_python = bootstrap_root / "bin" / "python3"
    bogus_python.parent.mkdir(parents=True, exist_ok=True)
    bogus_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"-m\" && \"${2:-}\" == \"pip\" && \"${3:-}\" == \"--version\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"-\" ]]; then\n"
        "  exit 1\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    bogus_python.chmod(0o755)

    marker = tmp_path / "venv-created"
    fake_base_python = tmp_path / "python3.12"
    fake_base_python.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail

if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "venv" ]]; then
  root="${{3:-}}"
  mkdir -p "$root/bin"
  touch "{marker}"
  cat >"$root/bin/python3" <<'PYEOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${{1:-}}" == "-" ]]; then
  cat >/dev/null
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "--version" ]]; then
  exit 0
fi
if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" && "${{3:-}}" == "install" ]]; then
  exit 0
fi
exit 0
PYEOF
  chmod +x "$root/bin/python3"
  exit 0
fi

exit 0
""",
        encoding="utf-8",
    )
    fake_base_python.chmod(0o755)

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("PyYAML==6.0.2\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                f"ensure_python_requirements_file '{fake_base_python}' '{requirements}'"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            **dict(os.environ),
            "VIVENTIUM_BOOTSTRAP_PYTHON_ROOT": str(bootstrap_root),
        },
    )

    assert completed.returncode == 0
    assert marker.exists()
    assert completed.stdout.strip() == str(bootstrap_root / "bin" / "python3")


def test_viventium_port_listener_active_detects_open_socket() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]

    try:
        completed = subprocess.run(
            [
                "bash",
                "-lc",
                (
                    f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                    f"if viventium_port_listener_active '{port}'; then printf 'active\\n'; "
                    "else printf 'inactive\\n'; fi"
                ),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    finally:
        server.close()

    assert completed.stdout.strip() == "active"


def test_viventium_port_listener_active_rejects_closed_socket() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source '{REPO_ROOT / 'scripts/viventium/common.sh'}' && "
                "if viventium_port_listener_active '9'; then printf 'active\\n'; "
                "else printf 'inactive\\n'; fi"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "inactive"
