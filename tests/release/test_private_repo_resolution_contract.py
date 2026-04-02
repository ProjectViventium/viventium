from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_private_repo_resolution_avoids_parent_directory_globs() -> None:
    cli_text = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    assert '"$workspace_root"/*private-companion-repo*' not in cli_text

    for script in [
        REPO_ROOT / "viventium_v0_4" / "viventium-skyvern-start.sh",
        REPO_ROOT / "viventium_v0_4" / "viventium-local-state-snapshot.sh",
    ]:
        text = script.read_text(encoding="utf-8")
        assert '"$workspace_root"/*private-companion-repo*' not in text
        assert '"$repo_root/private-companion-repo"' in text
        assert '"$workspace_root/private-companion-repo"' in text
        assert '"$workspace_root/private-companion-repo"' in text
        assert '"$workspace_root/.private-companion-repo"' in text

        if script.name == "viventium-skyvern-start.sh":
            assert '"$repo_root/private-companion-repo"' in text
            assert '"$repo_root/.private-companion-repo"' in text

    librechat_launcher = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    assert '"$workspace_root"/*private-companion-repo*' not in librechat_launcher


def test_private_yaml_validation_is_bounded_and_fail_open() -> None:
    cli_text = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert 'VIVENTIUM_PRIVATE_YAML_VALIDATE_TIMEOUT_SECONDS' in cli_text
    assert 'raise TimeoutError("timed out while reading YAML")' in cli_text
    assert "signal.alarm(timeout_seconds)" in cli_text
    assert "Warning: ignoring unreadable or invalid private LibreChat source-of-truth YAML" in cli_text
    assert "Warning: ignoring unreadable or invalid private Viventium agents bundle" in cli_text


def test_private_launcher_compat_loading_is_bounded_and_fail_open() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert "text_file_is_readable_with_timeout()" in launcher_text
    assert 'raise TimeoutError("timed out while reading text file")' in launcher_text
    assert "Warning: ignoring unreadable private launcher compat file" in launcher_text
