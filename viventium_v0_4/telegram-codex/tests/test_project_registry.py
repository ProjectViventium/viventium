from __future__ import annotations

from pathlib import Path

from app.project_registry import ProjectRegistry


def test_project_registry_loads_default_and_aliases(tmp_path):
    config_path = tmp_path / "projects.yaml"
    config_path.write_text(
        """
default_project: first
projects:
  first:
    path: /tmp/one
    description: First project
  second:
    path: /tmp/two
    description: Second project
""".strip(),
        encoding="utf-8",
    )

    registry = ProjectRegistry.from_file(config_path)
    assert registry.default_project().alias == "first"
    assert registry.get("second").path == Path("/tmp/two")


def test_project_registry_resolves_relative_paths_from_config_location(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "projects.yaml"
    config_path.write_text(
        """
default_project: sample
projects:
  sample:
    path: ../workspace
    description: Relative project
""".strip(),
        encoding="utf-8",
    )

    registry = ProjectRegistry.from_file(config_path)
    assert registry.default_project().path == workspace.resolve()
