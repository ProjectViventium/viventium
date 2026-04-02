#!/usr/bin/env python3
"""Drive the installed ViventiumHelper menu and record lifecycle evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    kAXChildrenAttribute,
    kAXPressAction,
    kAXRoleAttribute,
    kAXSubroleAttribute,
    kAXTitleAttribute,
)


HEALTH_ENDPOINTS = {
    "api": ("http://127.0.0.1:3180/api/health", {200}),
    "web": ("http://127.0.0.1:3190/", {200}),
    "playground": ("http://127.0.0.1:3300/", {200}),
    "scheduling_mcp": ("http://127.0.0.1:7110/health", {200}),
    "livekit": ("http://127.0.0.1:7888/", {200}),
    "rag": ("http://127.0.0.1:8110/health", {200}),
    "google_mcp": ("http://127.0.0.1:8111/health", {200}),
    "ms365_mcp": ("http://127.0.0.1:6274/mcp", {401}),
}

STOP_TIMEOUT_SECONDS = 300
START_TIMEOUT_SECONDS = 240
QUIT_TIMEOUT_SECONDS = 420
RELAUNCH_TIMEOUT_SECONDS = 30
AUTOSTART_TIMEOUT_SECONDS = 300


@dataclass
class MenuItem:
    title: str
    enabled: bool
    element: Any


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ax_get(element: Any, attribute: str) -> tuple[int, Any]:
    return AXUIElementCopyAttributeValue(element, attribute, None)


def run_osascript(script: str) -> str:
    completed = subprocess.run(
        ["osascript", "-"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "osascript failed")
    return completed.stdout.strip()


def helper_pid() -> int | None:
    result = subprocess.run(
        "pgrep -x ViventiumHelper | head -n1",
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    value = result.stdout.strip()
    return int(value) if value else None


def launcher_pids() -> list[str]:
    result = subprocess.run(
        "pgrep -fal 'viventium-librechat-start|bin/viventium'",
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def query_endpoint(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=2) as response:
            return {"status": response.status}
    except HTTPError as exc:
        return {"status": exc.code, "error": type(exc).__name__}
    except URLError as exc:
        return {"status": None, "error": type(exc).__name__, "detail": str(exc.reason)}
    except Exception as exc:  # pragma: no cover - defensive QA utility
        return {"status": None, "error": type(exc).__name__, "detail": str(exc)}


def health_snapshot() -> dict[str, dict[str, Any]]:
    return {name: query_endpoint(url) for name, (url, _expected) in HEALTH_ENDPOINTS.items()}


def stack_is_healthy(snapshot: dict[str, dict[str, Any]]) -> bool:
    for name, (_url, expected_codes) in HEALTH_ENDPOINTS.items():
        if snapshot[name]["status"] not in expected_codes:
            return False
    return True


def stack_is_stopped(snapshot: dict[str, dict[str, Any]]) -> bool:
    return all(details["status"] is None for details in snapshot.values())


def wait_until(
    description: str,
    predicate: Callable[[], bool],
    timeout_seconds: float,
    poll_seconds: float = 1.0,
) -> dict[str, Any]:
    started = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        if predicate():
            return {"ok": True, "description": description, "elapsed_seconds": round(time.monotonic() - started, 2)}
        time.sleep(poll_seconds)
    return {"ok": False, "description": description, "elapsed_seconds": round(time.monotonic() - started, 2)}


def helper_menu_item() -> Any:
    pid = helper_pid()
    if pid is None:
        raise RuntimeError("ViventiumHelper is not running")
    app = AXUIElementCreateApplication(pid)
    err, app_children = ax_get(app, kAXChildrenAttribute)
    if err != 0 or not app_children:
        raise RuntimeError(f"Unable to read helper AX children: err={err}")
    menu_bars = [child for child in app_children if ax_get(child, kAXRoleAttribute)[1] == "AXMenuBar"]
    if not menu_bars:
        raise RuntimeError("Unable to find helper menu bar")
    status_bar = None
    for candidate in menu_bars:
        err, children = ax_get(candidate, kAXChildrenAttribute)
        if err == 0 and children:
            first = children[0]
            if ax_get(first, kAXSubroleAttribute)[1] == "AXMenuExtra":
                status_bar = candidate
                break
    if status_bar is None:
        raise RuntimeError("Unable to find helper AXMenuExtra")
    err, items = ax_get(status_bar, kAXChildrenAttribute)
    if err != 0 or not items:
        raise RuntimeError(f"Unable to read helper menu extra: err={err}")
    return items[0]


def open_helper_menu_via_osascript() -> list[MenuItem]:
    output = run_osascript(
        """
tell application "System Events"
  tell process "ViventiumHelper"
    click menu bar item "V" of menu bar 2
    delay 0.2
    set reportLines to {}
    repeat with mi in every menu item of menu 1 of menu bar item "V" of menu bar 2
      set itemTitle to name of mi
      if itemTitle is missing value then set itemTitle to ""
      try
        set itemEnabled to enabled of mi
      on error
        set itemEnabled to false
      end try
      set end of reportLines to (itemTitle & tab & itemEnabled)
    end repeat
  end tell
  key code 53
  set AppleScript's text item delimiters to linefeed
  set joinedOutput to reportLines as text
  set AppleScript's text item delimiters to ""
  return joinedOutput
end tell
        """.strip()
    )
    result_items = []
    for line in output.splitlines():
        title, _, enabled_text = line.partition("\t")
        result_items.append(MenuItem(title=title, enabled=enabled_text == "true", element=None))
    return result_items


def open_helper_menu() -> list[MenuItem]:
    try:
        item = helper_menu_item()
        result = AXUIElementPerformAction(item, kAXPressAction)
        if result != 0:
            raise RuntimeError(f"Unable to press helper menu extra: err={result}")
        time.sleep(0.35)
        err, menu_children = ax_get(item, kAXChildrenAttribute)
        if err != 0 or not menu_children:
            raise RuntimeError(f"Unable to read helper menu children: err={err}")
        menu = menu_children[0]
        err, menu_items = ax_get(menu, kAXChildrenAttribute)
        if err != 0 or menu_items is None:
            raise RuntimeError(f"Unable to read helper menu items: err={err}")
        result_items = []
        for entry in menu_items:
            title = ax_get(entry, kAXTitleAttribute)[1] or ""
            enabled = bool(ax_get(entry, "AXEnabled")[1])
            result_items.append(MenuItem(title=title, enabled=enabled, element=entry))
        return result_items
    except Exception:
        return open_helper_menu_via_osascript()


def menu_snapshot() -> list[dict[str, Any]]:
    return [{"title": item.title, "enabled": item.enabled} for item in open_helper_menu()]


def menu_has_enabled_title(title: str) -> bool:
    try:
        items = open_helper_menu()
    except Exception:
        return False
    return any(item.title == title and item.enabled for item in items)


def press_menu_title(title: str) -> dict[str, Any]:
    menu_items = open_helper_menu()
    snapshot = [{"title": item.title, "enabled": item.enabled} for item in menu_items]
    for item in menu_items:
        if item.title == title:
            if not item.enabled:
                raise RuntimeError(f"Menu item '{title}' is disabled")
            if item.element is None:
                escaped_title = title.replace('"', '\\"')
                run_osascript(
                    f"""
tell application "System Events"
  tell process "ViventiumHelper"
    click menu bar item "V" of menu bar 2
    delay 0.2
    click menu item "{escaped_title}" of menu 1 of menu bar item "V" of menu bar 2
  end tell
end tell
                    """.strip()
                )
            else:
                result = AXUIElementPerformAction(item.element, kAXPressAction)
                if result != 0:
                    raise RuntimeError(f"Failed to press menu item '{title}': err={result}")
            return {"menu_before_press": snapshot, "pressed": title}
    raise RuntimeError(f"Menu item '{title}' not found in {snapshot}")


def tail_from(path: Path, offset: int) -> str:
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(offset)
        return handle.read()


def run_cycle(out_dir: Path, helper_app: str) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    helper_log = Path.home() / "Library" / "Application Support" / "Viventium" / "logs" / "viventium-helper.log"
    stop_log = Path.home() / "Library" / "Application Support" / "Viventium" / "logs" / "helper-stop.log"
    helper_log_offset = helper_log.stat().st_size if helper_log.exists() else 0
    stop_log_offset = stop_log.stat().st_size if stop_log.exists() else 0

    results: dict[str, Any] = {
        "started_at": iso_now(),
        "helper_app": helper_app,
        "initial": {
            "helper_pid": helper_pid(),
            "launcher_pids": launcher_pids(),
            "health": health_snapshot(),
        },
        "steps": [],
    }

    if not results["initial"]["helper_pid"]:
        raise RuntimeError("Helper must already be running for this QA cycle")
    if not stack_is_healthy(results["initial"]["health"]):
        raise RuntimeError("Stack is not healthy before helper lifecycle retest")

    # Stop: helper stays alive, stack goes down.
    stop_press = press_menu_title("Stop")
    stop_wait = wait_until(
        "stack stopped while helper stays alive",
        lambda: stack_is_stopped(health_snapshot()) and helper_pid() is not None,
        STOP_TIMEOUT_SECONDS,
    )
    stop_state = {
        **stop_press,
        "wait": stop_wait,
        "menu_interactive_wait": wait_until("helper shows Start after Stop", lambda: menu_has_enabled_title("Start"), 30, 0.5),
        "helper_pid_after": helper_pid(),
        "health_after": health_snapshot(),
        "menu_after": menu_snapshot(),
    }
    results["steps"].append({"action": "Stop", **stop_state})
    if not stop_wait["ok"]:
        raise RuntimeError("Helper Stop did not stop the stack while keeping helper alive")

    # Start: helper stays alive, stack becomes healthy.
    start_press = press_menu_title("Start")
    start_wait = wait_until(
        "stack healthy after Start",
        lambda: stack_is_healthy(health_snapshot()) and helper_pid() is not None,
        START_TIMEOUT_SECONDS,
    )
    start_state = {
        **start_press,
        "wait": start_wait,
        "menu_interactive_wait": wait_until("helper shows Stop after Start", lambda: menu_has_enabled_title("Stop"), 30, 0.5),
        "quit_interactive_wait": wait_until("helper shows Quit after Start", lambda: menu_has_enabled_title("Quit"), 60, 0.5),
        "helper_pid_after": helper_pid(),
        "health_after": health_snapshot(),
        "menu_after": menu_snapshot(),
    }
    results["steps"].append({"action": "Start", **start_state})
    if not start_wait["ok"]:
        raise RuntimeError("Helper Start did not bring stack back to healthy state")
    if not start_state["quit_interactive_wait"]["ok"]:
        raise RuntimeError("Helper Start reached healthy ports but Quit never became re-enabled")

    # Quit: helper exits, stack goes down.
    quit_press = press_menu_title("Quit")
    quit_wait = wait_until(
        "helper exited and stack stopped after Quit",
        lambda: helper_pid() is None and stack_is_stopped(health_snapshot()),
        QUIT_TIMEOUT_SECONDS,
    )
    quit_state = {
        **quit_press,
        "wait": quit_wait,
        "helper_pid_after": helper_pid(),
        "health_after": health_snapshot(),
    }
    results["steps"].append({"action": "Quit", **quit_state})
    if not quit_wait["ok"]:
        raise RuntimeError("Helper Quit did not fully stop the stack and exit the helper")

    # Relaunch helper and validate auto-start.
    subprocess.run(["open", "-a", helper_app], check=True)
    relaunch_wait = wait_until("helper relaunched", lambda: helper_pid() is not None, RELAUNCH_TIMEOUT_SECONDS)
    auto_start_wait = wait_until(
        "stack healthy after helper relaunch auto-start",
        lambda: stack_is_healthy(health_snapshot()) and helper_pid() is not None,
        AUTOSTART_TIMEOUT_SECONDS,
    )
    relaunch_state = {
        "wait_helper": relaunch_wait,
        "wait_stack": auto_start_wait,
        "quit_interactive_wait": wait_until(
            "helper shows Quit after relaunch",
            lambda: menu_has_enabled_title("Quit"),
            60,
            0.5,
        ),
        "helper_pid_after": helper_pid(),
        "health_after": health_snapshot(),
    }
    results["steps"].append({"action": "Relaunch", **relaunch_state})
    if not relaunch_wait["ok"] or not auto_start_wait["ok"]:
        raise RuntimeError("Helper relaunch did not restore a healthy stack")
    if not relaunch_state["quit_interactive_wait"]["ok"]:
        raise RuntimeError("Helper relaunch restored healthy ports but Quit never became re-enabled")

    results["ended_at"] = iso_now()
    results["logs"] = {
        "helper_log_tail": tail_from(helper_log, helper_log_offset),
        "stop_log_tail": tail_from(stop_log, stop_log_offset),
    }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, help="Directory that will receive summary.json")
    parser.add_argument(
        "--helper-app",
        default=str(Path.home() / "Applications" / "Viventium.app"),
        help="Installed helper app bundle path used for relaunch",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    try:
        results = run_cycle(out_dir, args.helper_app)
    except Exception as exc:
        failure = {
            "started_at": iso_now(),
            "error": type(exc).__name__,
            "message": str(exc),
            "helper_pid": helper_pid(),
            "launcher_pids": launcher_pids(),
            "health": health_snapshot(),
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "summary.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, indent=2))
        return 1

    (out_dir / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
