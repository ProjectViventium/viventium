from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_ORIGIN_PREFIX = "https://github.com/ProjectViventium/"
FULL_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_component_manifest_uses_projectviventium_origins() -> None:
    payload = load_json(REPO_ROOT / "devops" / "git" / "repos.json")
    invalid = {
        entry["path"]: entry["origin"]
        for entry in payload["repos"]
        if str(entry.get("path", "")).startswith("viventium_v0_4/")
        and not str(entry.get("origin", "")).startswith(PUBLIC_ORIGIN_PREFIX)
    }

    assert invalid == {}


def test_components_lock_matches_public_component_manifest_origins() -> None:
    repos_payload = load_json(REPO_ROOT / "devops" / "git" / "repos.json")
    lock_payload = load_json(REPO_ROOT / "components.lock.json")

    origin_by_path = {entry["path"]: entry["origin"] for entry in repos_payload["repos"]}
    mismatched = {
        entry["path"]: {
            "lock_origin": entry["origin"],
            "manifest_origin": origin_by_path.get(entry["path"]),
        }
        for entry in lock_payload["components"]
        if origin_by_path.get(entry["path"]) != entry["origin"]
    }

    assert mismatched == {}


def test_components_lock_uses_full_commit_shas_for_public_components() -> None:
    lock_payload = load_json(REPO_ROOT / "components.lock.json")

    invalid = {
        entry["path"]: entry["ref"]
        for entry in lock_payload["components"]
        if str(entry.get("origin", "")).startswith(PUBLIC_ORIGIN_PREFIX)
        and not FULL_GIT_SHA_RE.fullmatch(str(entry.get("ref", "")))
    }

    assert invalid == {}
