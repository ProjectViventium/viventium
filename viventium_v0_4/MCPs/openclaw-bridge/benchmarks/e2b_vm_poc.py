#!/usr/bin/env python3
# VIVENTIUM START
# Purpose: E2B VM control POC benchmark + capability artifact generator.
# Outputs under:
#   .viventium/artifacts/openclaw-e2b-poc/<timestamp>/
# VIVENTIUM END

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Ensure imports resolve when script is invoked from benchmarks/ path.
BRIDGE_ROOT = Path(__file__).resolve().parents[1]
if str(BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_ROOT))

from openclaw_manager import OPENCLAW_DEFAULT_VM_ID, OpenClawManager, normalize_vm_id


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    # .../viventium_v0_4/MCPs/openclaw-bridge/benchmarks/e2b_vm_poc.py -> core repo root
    return Path(__file__).resolve().parents[4]


def _artifact_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = _repo_root() / ".viventium" / "artifacts" / "openclaw-e2b-poc" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _pkg_metadata(name: str) -> Dict[str, str]:
    try:
        version = importlib.metadata.version(name)
        md = importlib.metadata.metadata(name)
        return {
            "name": name,
            "version": version,
            "license": md.get("License", ""),
            "home_page": md.get("Home-page", ""),
            "summary": md.get("Summary", ""),
        }
    except importlib.metadata.PackageNotFoundError:
        return {
            "name": name,
            "version": "",
            "license": "",
            "home_page": "",
            "summary": "not installed",
        }


async def _probe_tools_invoke(base_url: str, token: str) -> Dict[str, Any]:
    payload = {"tool": "__viventium_probe__", "args": {}}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{base_url.rstrip('/')}/tools/invoke", json=payload, headers=headers)
        return {
            "ok": resp.status_code in (200, 404),
            "status_code": resp.status_code,
            "latency_seconds": round(time.perf_counter() - started, 4),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_seconds": round(time.perf_counter() - started, 4),
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _run_agent_smoke(base_url: str, token: str) -> Dict[str, Any]:
    payload = {
        "model": "default",
        "input": "Reply with exactly: VM_AGENT_OK",
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{base_url.rstrip('/')}/v1/responses", json=payload, headers=headers)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        text_parts: List[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text_parts.append(content.get("text", ""))
        return {
            "ok": resp.status_code == 200,
            "status_code": resp.status_code,
            "latency_seconds": round(time.perf_counter() - started, 4),
            "output_text": "\n".join(text_parts).strip(),
            "raw_excerpt": str(data)[:1200],
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_seconds": round(time.perf_counter() - started, 4),
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _run(args: argparse.Namespace) -> Dict[str, Any]:
    user_id = args.user
    vm_id = normalize_vm_id(args.vm)
    vm_two = normalize_vm_id(args.second_vm)

    os.environ.setdefault("OPENCLAW_RUNTIME", "e2b")
    manager = OpenClawManager()

    if manager.runtime_mode != "e2b":
        raise RuntimeError(
            f"OPENCLAW_RUNTIME resolved to '{manager.runtime_mode}', expected 'e2b'. "
            "Set OPENCLAW_RUNTIME=e2b and ensure e2b dependencies + E2B_API_KEY are available."
        )

    benchmark: Dict[str, Any] = {
        "started_at": _iso_now(),
        "user_id": user_id,
        "vm_id": vm_id,
        "runtime_mode": manager.runtime_mode,
        "environment": {
            "OPENCLAW_RUNTIME": os.environ.get("OPENCLAW_RUNTIME", ""),
            "OPENCLAW_MODEL": os.environ.get("OPENCLAW_MODEL", ""),
            "OPENCLAW_E2B_TEMPLATE": os.environ.get("OPENCLAW_E2B_TEMPLATE", ""),
            "E2B_API_KEY_present": bool(os.environ.get("E2B_API_KEY", "").strip()),
        },
    }

    # Cold start
    t0 = time.perf_counter()
    vm_one = await manager.start_instance(user_id, vm_id)
    benchmark["cold_start_seconds"] = round(time.perf_counter() - t0, 4)
    benchmark["vm_001"] = manager.get_instance_info(user_id, vm_id)

    # First tool invoke
    probe = await _probe_tools_invoke(vm_one.base_url, vm_one.gateway_token)
    benchmark["first_tool_invoke"] = probe

    # Agent task latency
    benchmark["agent_task"] = await _run_agent_smoke(vm_one.base_url, vm_one.gateway_token)

    # E2B metrics snapshot
    benchmark["e2b_metrics"] = manager.collect_runtime_metrics(user_id, vm_id)

    # Persistence marker check (bootstrap idempotency signal)
    marker_path = f"/workspace/.viventium/openclaw/vm-{vm_id}/.bootstrap_complete"
    marker_cmd = f"test -f {marker_path} && echo PRESENT || echo MISSING"
    marker_result = manager.run_shell(user_id, vm_id, marker_cmd, timeout=30)
    benchmark["bootstrap_marker_check"] = marker_result

    # Pause / resume timings
    t_pause = time.perf_counter()
    await manager.stop_instance(user_id, vm_id)
    benchmark["pause_seconds"] = round(time.perf_counter() - t_pause, 4)

    t_resume = time.perf_counter()
    resumed = await manager.resume_instance(user_id, vm_id)
    benchmark["resume_seconds"] = round(time.perf_counter() - t_resume, 4)
    benchmark["vm_001_after_resume"] = manager.get_instance_info(user_id, vm_id)
    benchmark["resume_probe"] = await _probe_tools_invoke(resumed.base_url, resumed.gateway_token)

    # Isolation check with second VM
    vm_two_instance = await manager.start_instance(user_id, vm_two)
    benchmark["vm_002"] = manager.get_instance_info(user_id, vm_two)
    benchmark["isolation_check"] = {
        "vm_001_sandbox_id": vm_one.sandbox_id,
        "vm_002_sandbox_id": vm_two_instance.sandbox_id,
        "distinct_sandboxes": vm_one.sandbox_id != vm_two_instance.sandbox_id,
    }

    # Dependency versions + license snapshot
    benchmark["dependencies"] = [
        _pkg_metadata("e2b"),
        _pkg_metadata("e2b-desktop"),
        _pkg_metadata("fastmcp"),
        _pkg_metadata("httpx"),
    ]

    benchmark["finished_at"] = _iso_now()
    return benchmark


def _write_report(out_dir: Path, payload: Dict[str, Any]) -> None:
    json_path = out_dir / "benchmark.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str))

    md_path = out_dir / "benchmark.md"
    lines = [
        "# OpenClaw E2B VM POC Benchmark",
        "",
        f"- Started: `{payload.get('started_at', '')}`",
        f"- Finished: `{payload.get('finished_at', '')}`",
        f"- User: `{payload.get('user_id', '')}`",
        f"- VM: `{payload.get('vm_id', '')}`",
        "",
        "## Timings",
        "",
        f"- Cold start: `{payload.get('cold_start_seconds', 'n/a')}s`",
        f"- Pause: `{payload.get('pause_seconds', 'n/a')}s`",
        f"- Resume: `{payload.get('resume_seconds', 'n/a')}s`",
        f"- First tool invoke: `{payload.get('first_tool_invoke', {}).get('latency_seconds', 'n/a')}s`",
        f"- Agent task: `{payload.get('agent_task', {}).get('latency_seconds', 'n/a')}s`",
        "",
        "## Capability Checks",
        "",
        f"- Tool invoke ok: `{payload.get('first_tool_invoke', {}).get('ok', False)}`",
        f"- Agent task ok: `{payload.get('agent_task', {}).get('ok', False)}`",
        f"- Distinct VM sandboxes: `{payload.get('isolation_check', {}).get('distinct_sandboxes', False)}`",
        f"- Bootstrap marker: `{payload.get('bootstrap_marker_check', {}).get('stdout', '').strip()}`",
        "",
        "## Artifacts",
        "",
        f"- JSON: `{json_path}`",
    ]
    md_path.write_text("\n".join(lines) + "\n")

    deps_path = out_dir / "dependencies_licenses.json"
    deps_path.write_text(json.dumps(payload.get("dependencies", []), indent=2, default=str))


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OpenClaw E2B VM POC benchmark")
    parser.add_argument("--user", required=True, help="Viventium user id")
    parser.add_argument("--vm", default=OPENCLAW_DEFAULT_VM_ID, help="Primary VM id (default: 001)")
    parser.add_argument("--second-vm", default="002", help="Secondary VM id for isolation check")
    return parser


def main() -> int:
    args = _arg_parser().parse_args()
    out_dir = _artifact_dir()
    payload = asyncio.run(_run(args))
    _write_report(out_dir, payload)
    print(json.dumps({"artifacts_dir": str(out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
