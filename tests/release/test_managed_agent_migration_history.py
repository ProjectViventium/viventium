from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRECHAT_ROOT = REPO_ROOT / "viventium_v0_4" / "LibreChat"
GENERATOR = LIBRECHAT_ROOT / "scripts" / "viventium-generate-managed-agent-migrations.js"


def test_librechat_checkout_verifies_all_predecessors_without_parent_history(
    tmp_path: Path,
) -> None:
    # A component bootstrapped with Git's blob filter is intentionally a partial
    # clone. Cloning that checkout locally produces a child whose origin cannot
    # satisfy missing promised blobs, so it is not a faithful public-install
    # simulation. Run the component-owned hermetic audit from an unrelated cwd
    # instead: no parent-root argument or parent history is available to the
    # generator, while its real public origin remains able to satisfy blobs.
    assert not (tmp_path / "components.lock.json").exists()

    completed = subprocess.run(
        ["node", str(GENERATOR), "--check"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    assert "self-contained and matches all 65 predecessor objects" in completed.stdout


def test_explicit_parent_history_audit_matches_the_hermetic_artifact() -> None:
    completed = subprocess.run(
        ["node", str(GENERATOR), "--check", f"--parent-root={REPO_ROOT}", "--parent-rev=HEAD"],
        cwd=LIBRECHAT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    assert "matches public history" in completed.stdout


def test_parent_history_audit_ignores_a_later_release_pin_after_the_recorded_boundary(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent-after-release-pin"
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(REPO_ROOT), str(parent)],
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Viventium Synthetic QA"], cwd=parent, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "qa@example.com"], cwd=parent, check=True
    )
    lock_path = parent / "components.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    component = next(
        item
        for item in lock["components"]
        if item.get("name") == "LibreChat"
        or item.get("path") == "viventium_v0_4/LibreChat"
    )
    candidate_refs = subprocess.run(
        ["git", "rev-list", "--max-count=3", "origin/main"],
        cwd=LIBRECHAT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    component["ref"] = next(ref for ref in candidate_refs if ref != component["ref"])
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "components.lock.json"], cwd=parent, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "synthetic later component pin"],
        cwd=parent,
        check=True,
    )

    completed = subprocess.run(
        [
            "node",
            str(GENERATOR),
            "--check",
            f"--parent-root={parent}",
            "--parent-rev=HEAD",
        ],
        cwd=LIBRECHAT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    assert "through its recorded history boundary" in completed.stdout
