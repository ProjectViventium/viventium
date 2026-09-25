#!/usr/bin/env python3
"""Verify the selected local xPerfect service using kernel process identity."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import parallel_work_release_gate as process_inspector


def service_process_matches(pid: int, component_root: Path, service: str, port: int) -> bool:
    """Health from another checkout is not readiness for the selected component."""
    if service not in {"runtime", "mcp", "ui"} or pid <= 0 or not 0 < port < 65536:
        return False
    try:
        if component_root.is_symlink():
            return False
        root = component_root.resolve(strict=True)
        service_root = root / ("frontends/glass-drive-ui" if service == "ui" else "runtime_phase1")
        expected_cwd = service_root.resolve(strict=True)
        expected_python = (service_root / ".venv/bin/python").resolve(strict=True)
        observed = process_inspector._live_process_image_and_argv(pid)
        if observed is None or process_inspector._process_cwd(pid) != expected_cwd:
            return False
        image, argv = observed
        allowed_image = expected_python
        if sys.platform == "darwin":
            framework_image = expected_python.parent.parent / "Resources/Python.app/Contents/MacOS/Python"
            if framework_image.is_file():
                allowed_image = framework_image.resolve(strict=True)
        interpreters = {expected_python, allowed_image}
        if image not in interpreters or not argv:
            return False
        # A macOS framework interpreter re-executes its Python.app and passes that path as argv[0].
        if Path(argv[0]).resolve(strict=True) not in interpreters:
            return False
        if service == "mcp":
            if argv[1:3] != ("-m", "workers_projects_runtime.mcp_server"):
                return False
            options = argv[3:]
        else:
            target = "glass_drive_ui.server:app" if service == "ui" else "workers_projects_runtime.api:create_app"
            if argv[1:3] == ("-m", "uvicorn"):
                target_position = 3
            elif len(argv) > 2 and Path(argv[1]).resolve(strict=True) == (service_root / ".venv/bin/uvicorn").resolve(strict=True):
                target_position = 2
            else:
                return False
            if len(argv) <= target_position or argv[target_position] != target:
                return False
            options = argv[target_position + 1:]
            if service == "runtime" and "--factory" not in options:
                return False
        if options.count("--port") != 1:
            return False
        position = options.index("--port")
        if position + 1 >= len(options) or options[position + 1] != str(port):
            return False
        # Do not accept a process replaced during inspection.
        return process_inspector._live_process_image_and_argv(pid) == observed
    except (OSError, RuntimeError, ValueError, IndexError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--component-root", type=Path, required=True)
    parser.add_argument("--service", choices=("runtime", "mcp", "ui"), required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if args.pid <= 0 or not 0 < args.port < 65536:
        return 1
    return 0 if service_process_matches(args.pid, args.component_root, args.service, args.port) else 1


if __name__ == "__main__":
    raise SystemExit(main())
