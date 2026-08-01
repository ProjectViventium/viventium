#!/usr/bin/env python3
"""Persist, stop, prune, or seal the exact local MongoDB runtime engine identity.

This helper is intentionally small. The upgrade transaction module owns all
validation and atomic-write rules so normal lifecycle calls and upgrade
preflight consume one receipt contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import upgrade_transaction


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "record-mongo-engine",
        "prune-stale-native-pid",
        "stop-recorded-native-engine",
        "seal-mongo-engine",
    ):
        child = subparsers.add_parser(command)
        child.add_argument("--app-support-dir", type=Path, required=True)
        child.add_argument("--runtime-dir", type=Path, required=True)
        if command in {"record-mongo-engine", "seal-mongo-engine"}:
            child.add_argument(
                "--native-only",
                action="store_true",
                help=(
                    "Ignore machine-global Docker containers and inspect only "
                    "this App Support root's native engine receipt."
                ),
            )
        if command in {"prune-stale-native-pid", "stop-recorded-native-engine"}:
            child.add_argument("--pid-file", type=Path, action="append", default=[])
        if command == "stop-recorded-native-engine":
            child.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "record-mongo-engine":
            payload = upgrade_transaction.record_mongo_engine_identity(
                args.app_support_dir,
                args.runtime_dir,
                include_docker=not args.native_only,
            )
        elif args.command == "prune-stale-native-pid":
            if len(args.pid_file) != 1:
                raise upgrade_transaction.UpgradeTransactionError(
                    "Exactly one native MongoDB PID record is required"
                )
            result = upgrade_transaction.discard_stale_native_mongo_pid_file(
                args.app_support_dir,
                args.pid_file[0],
            )
            print(json.dumps({"ok": True, **result}, sort_keys=True))
            return 0
        elif args.command == "stop-recorded-native-engine":
            payload = upgrade_transaction.stop_recorded_native_mongo_engine(
                args.app_support_dir,
                args.runtime_dir,
                pid_files=tuple(args.pid_file),
                timeout_seconds=args.timeout_seconds,
            )
        else:
            payload = upgrade_transaction.seal_mongo_engine_identity(
                args.app_support_dir,
                args.runtime_dir,
                include_docker=not args.native_only,
            )
    except upgrade_transaction.UpgradeTransactionError as error:
        print(f"MongoDB engine identity operation failed: {error}", file=sys.stderr)
        return 4
    print(
        json.dumps(
            {
                "ok": True,
                "runtime_engine": payload["identity"]["runtime_engine"],
                "backend": payload["identity"]["backend"],
                "clean_stopped": payload["clean_stopped"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
