#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from host_cli_auth import detect_worker_profile


DEFAULTS_VERSION = 1


def resolve_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _version(value: Any) -> int:
    try:
        return int(str(value or "0").strip())
    except ValueError:
        return 0


def _set_default(mapping: dict[str, Any], key: str, value: Any) -> bool:
    if key in mapping:
        return False
    mapping[key] = value
    return True


def ensure_default_nightly_routines(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    changed = False
    runtime = config.setdefault("runtime", {})
    integrations = config.setdefault("integrations", {})
    routines = runtime.setdefault("nightly_routines", {})
    prior_version = _version(routines.get("defaults_version"))

    if prior_version < DEFAULTS_VERSION:
        changed = _set_default(routines, "enabled", True) or changed
        routines["defaults_version"] = DEFAULTS_VERSION
        changed = True
        changed = _set_default(routines, "auto_worker_profile", True) or changed

        prompt_workbench = runtime.setdefault("prompt_workbench", {})
        changed = _set_default(prompt_workbench, "enabled", True) or changed
        seed = prompt_workbench.setdefault("seed_nightly", {})
        changed = _set_default(seed, "enabled", True) or changed
        changed = _set_default(seed, "active", True) or changed
        changed = _set_default(seed, "executor", "glasshive_host") or changed

        memory_hardening = runtime.setdefault("memory_hardening", {})
        changed = _set_default(memory_hardening, "enabled", True) or changed
        changed = _set_default(memory_hardening, "schedule", "0 3 * * *") or changed
        changed = _set_default(memory_hardening, "operator_user_email", "") or changed
        changed = _set_default(memory_hardening, "dry_run_first", True) or changed

        glasshive = integrations.setdefault("glasshive", {})
        changed = _set_default(glasshive, "enabled", True) or changed
        host_worker = glasshive.setdefault("host_worker", {})
        changed = _set_default(host_worker, "enabled", True) or changed
        changed = _set_default(host_worker, "workspace_root", "~/viventium") or changed
        changed = _set_default(host_worker, "default_execution_mode", "host") or changed

    if resolve_bool(routines.get("auto_worker_profile"), False):
        profile = detect_worker_profile()
        if profile:
            glasshive = integrations.setdefault("glasshive", {})
            host_worker = glasshive.setdefault("host_worker", {})
            if not str(host_worker.get("default_worker_profile") or "").strip():
                host_worker["default_worker_profile"] = profile
                changed = True

    return config, changed


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Viventium default local nightly routines to config.yaml.")
    parser.add_argument("--config", required=True, help="Path to canonical Viventium config.yaml")
    parser.add_argument("--write", action="store_true", help="Write changes back to config.yaml")
    parser.add_argument("--json", action="store_true", help="Print JSON status")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable no-op output")
    args = parser.parse_args()

    path = Path(args.config).expanduser()
    config = load_config(path)
    updated, changed = ensure_default_nightly_routines(config)
    if changed and args.write:
        path.write_text(yaml.safe_dump(updated, sort_keys=False), encoding="utf-8")

    if args.json:
        runtime = updated.get("runtime", {}) or {}
        integrations = updated.get("integrations", {}) or {}
        glasshive = integrations.get("glasshive", {}) or {}
        host_worker = glasshive.get("host_worker", {}) or {}
        memory_hardening = runtime.get("memory_hardening", {}) or {}
        prompt_workbench = runtime.get("prompt_workbench", {}) or {}
        print(
            json.dumps(
                {
                    "changed": changed,
                    "defaultsVersion": (runtime.get("nightly_routines") or {}).get("defaults_version"),
                    "glasshiveEnabled": resolve_bool(glasshive.get("enabled"), False),
                    "promptWorkbenchEnabled": resolve_bool(prompt_workbench.get("enabled"), False),
                    "nightlySeedActive": resolve_bool(
                        ((prompt_workbench.get("seed_nightly") or {}) if isinstance(prompt_workbench, dict) else {}).get("active"),
                        False,
                    ),
                    "memoryHardeningEnabled": resolve_bool(memory_hardening.get("enabled"), False),
                    "workerProfile": host_worker.get("default_worker_profile") or "",
                    "memoryProvider": memory_hardening.get("provider") or "",
                },
                sort_keys=True,
            )
        )
    elif changed and not args.quiet:
        print("Viventium default nightly routines updated in canonical config.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
