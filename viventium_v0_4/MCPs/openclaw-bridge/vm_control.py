#!/usr/bin/env python3
# VIVENTIUM START
# Purpose: Codex-first CLI for VM lifecycle control in the OpenClaw bridge.
# Contract:
#   start/resume/stop/terminate/list/status/takeover
#   required --user, optional --vm (default: 001)
# VIVENTIUM END

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict

from openclaw_manager import OPENCLAW_DEFAULT_VM_ID, OpenClawManager, normalize_vm_id


def _print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Control VM-scoped OpenClaw runtimes managed by openclaw-bridge",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser, include_vm: bool = True) -> None:
        sub.add_argument("--user", required=True, help="Viventium user id")
        if include_vm:
            sub.add_argument(
                "--vm",
                default=OPENCLAW_DEFAULT_VM_ID,
                help=f"VM id (default: {OPENCLAW_DEFAULT_VM_ID})",
            )

    for name in ("start", "resume", "stop", "terminate", "status", "takeover"):
        sp = subparsers.add_parser(name, help=f"{name} a VM")
        add_common(sp, include_vm=True)
        if name == "takeover":
            sp.add_argument(
                "--no-auth",
                action="store_true",
                help="Disable takeover auth key requirement",
            )
            sp.add_argument(
                "--view-only",
                action="store_true",
                help="Enable read-only desktop stream mode",
            )

    list_parser = subparsers.add_parser("list", help="list VM instances for a user")
    add_common(list_parser, include_vm=False)

    return parser


async def _dispatch(args: argparse.Namespace) -> int:
    manager = OpenClawManager()
    user_id = args.user
    vm_id = normalize_vm_id(getattr(args, "vm", OPENCLAW_DEFAULT_VM_ID))

    if args.command == "start":
        await manager.start_instance(user_id, vm_id)
        info = manager.get_instance_info(user_id, vm_id) or {}
        info["event"] = "started"
        _print_json(info)
        return 0

    if args.command == "resume":
        await manager.resume_instance(user_id, vm_id)
        info = manager.get_instance_info(user_id, vm_id) or {}
        info["event"] = "resumed"
        _print_json(info)
        return 0

    if args.command == "stop":
        await manager.stop_instance(user_id, vm_id)
        info = manager.get_instance_info(user_id, vm_id) or {
            "user_id": user_id,
            "vm_id": vm_id,
            "state": "paused",
        }
        info["event"] = "paused"
        _print_json(info)
        return 0

    if args.command == "terminate":
        await manager.terminate_instance(user_id, vm_id)
        _print_json(
            {
                "event": "terminated",
                "user_id": user_id,
                "vm_id": vm_id,
                "state": "terminated",
            }
        )
        return 0

    if args.command == "list":
        _print_json({"user_id": user_id, "vms": manager.list_instances(user_id=user_id)})
        return 0

    if args.command == "status":
        info = manager.get_instance_info(user_id, vm_id)
        if not info:
            _print_json(
                {
                    "status": "not_running",
                    "user_id": user_id,
                    "vm_id": vm_id,
                    "message": "No VM instance found. Start one first.",
                }
            )
            return 0
        _print_json(info)
        return 0

    if args.command == "takeover":
        takeover = await manager.takeover_instance(
            user_id,
            vm_id=vm_id,
            require_auth=not args.no_auth,
            view_only=bool(args.view_only),
        )
        _print_json(takeover)
        return 0

    raise RuntimeError(f"Unknown command: {args.command}")


def main() -> int:
    parser = _base_parser()
    args = parser.parse_args()
    return asyncio.run(_dispatch(args))


if __name__ == "__main__":
    raise SystemExit(main())
