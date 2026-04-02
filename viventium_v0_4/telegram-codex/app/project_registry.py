from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Project:
    alias: str
    path: Path
    description: str


class ProjectRegistry:
    def __init__(self, *, default_alias: str, projects: dict[str, Project]) -> None:
        self.default_alias = default_alias
        self._projects = projects

    @classmethod
    def from_file(cls, path: Path) -> "ProjectRegistry":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_projects = data.get("projects") or {}
        projects: dict[str, Project] = {}
        base_dir = path.parent
        for alias, item in raw_projects.items():
            if not isinstance(item, dict):
                continue
            raw_path = Path(str(item.get("path") or "")).expanduser()
            project_path = raw_path if raw_path.is_absolute() else (base_dir / raw_path).resolve()
            projects[alias] = Project(
                alias=alias,
                path=project_path,
                description=str(item.get("description") or ""),
            )

        default_alias = str(data.get("default_project") or "").strip()
        if not default_alias and projects:
            default_alias = next(iter(projects))
        if default_alias not in projects:
            raise RuntimeError(f"Default project alias '{default_alias}' is missing from {path}")
        return cls(default_alias=default_alias, projects=projects)

    def default_project(self) -> Project:
        return self._projects[self.default_alias]

    def get(self, alias: str | None) -> Project:
        if alias and alias in self._projects:
            return self._projects[alias]
        return self.default_project()

    def aliases(self) -> list[str]:
        return list(self._projects)

    def all_projects(self) -> list[Project]:
        return list(self._projects.values())
