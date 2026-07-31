#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_STATE_CONTRACTS = {
    "first_upgrade_bridge",
    "helper_runtime_intent",
    "managed_agents",
    "mongo",
    "mongo_engine_identity",
    "rag_postgres",
    "schedules",
    "telegram",
    "uploads",
}
MONGO_ENGINE_REQUIREMENT = {
    "required_for": "durable-stopped-or-ambiguous-storage",
    "accepted_proof": "direct-running-engine-or-clean-stop-receipt-v1",
    "unsupported_status": "mongo_engine_proof_required",
    "recovery": "observed-intermediate-clean-stop-or-supported-snapshot-restore",
}


class UpgradeSupportError(RuntimeError):
    pass


def load_policy(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpgradeSupportError("upgrade support policy is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise UpgradeSupportError("upgrade support policy schema is unsupported")
    floor = payload.get("support_floor")
    if (
        not isinstance(floor, dict)
        or not SHA_RE.fullmatch(str(floor.get("parent_commit") or ""))
        or not isinstance(floor.get("published_at"), str)
    ):
        raise UpgradeSupportError("upgrade support floor is invalid")
    if payload.get("supported_canonical_config_versions") != [1]:
        raise UpgradeSupportError("canonical config compatibility policy is invalid")
    continuity_versions = payload.get("supported_continuity_manifest_versions")
    if continuity_versions != [2]:
        raise UpgradeSupportError("continuity compatibility policy is invalid")
    contracts = payload.get("state_contracts")
    if not isinstance(contracts, dict) or set(contracts) != EXPECTED_STATE_CONTRACTS:
        raise UpgradeSupportError("upgrade state contracts are incomplete")
    if any(not isinstance(value, str) or not value for value in contracts.values()):
        raise UpgradeSupportError("upgrade state contract identifier is invalid")
    state_requirements = payload.get("predecessor_state_requirements")
    if (
        not isinstance(state_requirements, dict)
        or state_requirements.get("mongo_engine_identity")
        != MONGO_ENGINE_REQUIREMENT
    ):
        raise UpgradeSupportError(
            "upgrade predecessor state requirements are incomplete"
        )
    return payload


def assess_predecessor(
    repo_root: Path,
    policy: dict[str, Any],
    predecessor: str = "HEAD",
) -> dict[str, Any]:
    floor = str(policy["support_floor"]["parent_commit"])
    exists = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{floor}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if exists.returncode != 0:
        return {
            "supported": False,
            "status": "history_missing",
            "support_floor": floor,
        }
    ancestor = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", floor, predecessor],
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestor.returncode == 0:
        status = "supported"
    elif ancestor.returncode == 1:
        status = "predecessor_before_support_floor"
    else:
        status = "history_unreadable"
    return {
        "supported": status == "supported",
        "status": status,
        "support_floor": floor,
    }


def assess_mongo_engine_state(
    app_support_dir: Path,
    runtime_dir: Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    try:
        import importlib.util

        transaction_path = Path(__file__).with_name("upgrade_transaction.py")
        specification = importlib.util.spec_from_file_location(
            "viventium_upgrade_support_transaction",
            transaction_path,
        )
        if specification is None or specification.loader is None:
            raise UpgradeSupportError(
                "MongoDB engine proof inspector is unavailable"
            )
        transaction = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(transaction)
        inventory, _ = transaction.mongo_storage_inventory(
            app_support_dir.resolve(),
            runtime_dir.resolve(),
        )
    except UpgradeSupportError:
        raise
    except Exception:
        requirement = policy["predecessor_state_requirements"][
            "mongo_engine_identity"
        ]
        return {
            "supported": False,
            "status": requirement["unsupported_status"],
            "recovery": requirement["recovery"],
            "mongo_engine_proof": "unavailable",
        }
    return {
        "supported": True,
        "status": "supported",
        "recovery": "",
        "mongo_engine_proof": str(
            inventory.get("observed_from") or "direct-runtime-observation"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the bounded source-upgrade support floor.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--app-support-dir", type=Path)
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        result = assess_predecessor(args.repo_root.resolve(), policy)
        if result["supported"] and (
            args.app_support_dir is not None or args.runtime_dir is not None
        ):
            if args.app_support_dir is None or args.runtime_dir is None:
                raise UpgradeSupportError(
                    "MongoDB engine proof scope is incomplete"
                )
            state_result = assess_mongo_engine_state(
                args.app_support_dir,
                args.runtime_dir,
                policy,
            )
            result.update(state_result)
    except UpgradeSupportError as exc:
        result = {"supported": False, "status": str(exc), "support_floor": ""}
    if args.json:
        print(json.dumps(result, sort_keys=True))
    elif not result["supported"]:
        if result.get("status") == "mongo_engine_proof_required":
            print(
                "This durable MongoDB state has no verified creator-engine proof. "
                "Use a reviewed intermediate release to observe and cleanly stop "
                "the current engine, or restore a complete supported snapshot into "
                "a fresh same-profile install."
            )
        else:
            print(
                "This checkout predates the reviewed universal-upgrade support floor or lacks its history.",
            )
    return 0 if result["supported"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
