"""The stack launcher must derive every trusted path from the physical directory.

macOS aliases ``/tmp`` to ``/private/tmp``. When a caller (the macOS helper or the CLI) hands the
launcher a logical root, strict symlink guards such as the RAG PostgreSQL migration reject the
Compose path even though the file is a regular file. The launcher owns that normalization once, so
this test executes the launcher's own derivation lines against a symlinked root.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from scripts.viventium import rag_postgres_migration

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"

START_MARKER = "# Feature: Physical trusted root paths."


def _derivation_block() -> str:
    text = LAUNCHER.read_text(encoding="utf-8")
    start = text.index(START_MARKER)
    end = text.index("\n", text.index("VIVENTIUM_WORKSPACE_DIR=", start))
    block = text[start:end]
    librechat_line = re.search(r"^LIBRECHAT_DIR=.*$", text, re.MULTILINE)
    assert librechat_line, "launcher must derive LIBRECHAT_DIR"
    return block + "\n" + librechat_line.group(0) + "\n"


def _run_derivation(env: dict[str, str]) -> dict[str, str]:
    script = _derivation_block() + (
        "printf 'ROOT_DIR=%s\\nVIVENTIUM_CORE_DIR=%s\\nVIVENTIUM_WORKSPACE_DIR=%s\\nLIBRECHAT_DIR=%s\\n' "
        '"$ROOT_DIR" "$VIVENTIUM_CORE_DIR" "$VIVENTIUM_WORKSPACE_DIR" "$LIBRECHAT_DIR"\n'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    real = tmp_path / "real"
    (real / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    (real / "scripts" / "viventium").mkdir(parents=True)
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    return real.resolve(), alias


def test_logical_helper_root_becomes_physical_for_every_derived_path(tmp_path: Path) -> None:
    real, alias = _workspace(tmp_path)

    derived = _run_derivation({"VIVENTIUM_HELPER_V0_ROOT": str(alias / "viventium_v0_4")})

    assert derived["ROOT_DIR"] == str(real / "viventium_v0_4")
    assert derived["VIVENTIUM_CORE_DIR"] == str(real)
    assert derived["VIVENTIUM_WORKSPACE_DIR"] == str(real.parent)
    assert derived["LIBRECHAT_DIR"] == str(real / "viventium_v0_4" / "LibreChat")


def test_logical_core_and_librechat_overrides_become_physical(tmp_path: Path) -> None:
    real, alias = _workspace(tmp_path)

    derived = _run_derivation(
        {
            "VIVENTIUM_HELPER_V0_ROOT": str(real / "viventium_v0_4"),
            "VIVENTIUM_HELPER_CORE_ROOT": str(alias),
            "VIVENTIUM_LIBRECHAT_DIR": str(alias / "viventium_v0_4" / "LibreChat"),
        }
    )

    assert derived["VIVENTIUM_CORE_DIR"] == str(real)
    assert derived["LIBRECHAT_DIR"] == str(real / "viventium_v0_4" / "LibreChat")


def test_missing_root_is_passed_through_unchanged(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist" / "viventium_v0_4"

    derived = _run_derivation({"VIVENTIUM_HELPER_V0_ROOT": str(missing)})

    assert derived["ROOT_DIR"] == str(missing)
    assert derived["LIBRECHAT_DIR"] == str(missing / "LibreChat")


def test_migration_guard_still_rejects_symlinked_compose_paths(tmp_path: Path) -> None:
    """The strict guard is kept; the launcher fix removes the false positive, not the check."""
    real, alias = _workspace(tmp_path)
    compose = real / "viventium_v0_4" / "LibreChat" / "rag.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    rag_postgres_migration._reject_symlink_components(compose, "RAG PostgreSQL Compose file")
    with pytest.raises(rag_postgres_migration.MigrationError, match="must not contain symlinks"):
        rag_postgres_migration._reject_symlink_components(
            alias / "viventium_v0_4" / "LibreChat" / "rag.yml",
            "RAG PostgreSQL Compose file",
        )
