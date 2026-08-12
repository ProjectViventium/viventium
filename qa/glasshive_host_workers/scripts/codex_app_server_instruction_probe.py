#!/usr/bin/env python3
"""Opt-in QA gate for mutable developer instructions on one Codex App Server thread."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


_ENABLED_VALUES = {"1", "true", "yes", "on"}
_PERSONALITIES = {"inherit", "none", "friendly", "pragmatic"}


class ProbeError(RuntimeError):
    pass


class AppServerClient:
    def __init__(self, process: subprocess.Popen[str], timeout_s: float) -> None:
        self.process = process
        self.timeout_s = timeout_s
        self.next_id = 1
        self.backlog: deque[dict[str, Any]] = deque()
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.reader = threading.Thread(target=self._read_lines, daemon=True)
        self.reader.start()

    def _read_lines(self) -> None:
        if self.process.stdout is None:
            self.lines.put(None)
            return
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, method: str, params: dict[str, Any] | None = None) -> int:
        request_id = self.next_id
        self.next_id += 1
        payload: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            payload["params"] = params
        if self.process.stdin is None:
            raise ProbeError("Codex App Server stdin is unavailable")
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        return request_id

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        if self.process.stdin is None:
            raise ProbeError("Codex App Server stdin is unavailable")
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def _read(self, timeout_s: float) -> dict[str, Any] | None:
        try:
            line = self.lines.get(timeout=max(0.0, timeout_s))
        except queue.Empty:
            return None
        if line is None:
            raise ProbeError("Codex App Server closed before the probe completed")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProbeError("Codex App Server emitted invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ProbeError("Codex App Server emitted a non-object message")
        return payload

    def response(self, request_id: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            message = self._read(min(1.0, deadline - time.monotonic()))
            if message is None:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise ProbeError("Codex App Server rejected a probe request")
                return message
            self.backlog.append(message)
        raise ProbeError("Timed out waiting for a Codex App Server response")

    def turn_result(self, turn_id: str) -> tuple[str, bool]:
        deadline = time.monotonic() + self.timeout_s
        text = ""
        terminal = False
        agent_completed_at: float | None = None
        while time.monotonic() < deadline:
            if agent_completed_at is not None and time.monotonic() - agent_completed_at >= 5:
                break
            message = (
                self.backlog.popleft()
                if self.backlog
                else self._read(min(1.0, deadline - time.monotonic()))
            )
            if message is None:
                continue
            method = str(message.get("method") or "")
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            if method == "item/completed":
                item = params.get("item") if isinstance(params.get("item"), dict) else {}
                if item.get("type") == "agentMessage":
                    text = str(item.get("text") or "").strip()
                    agent_completed_at = time.monotonic()
            if method == "turn/completed":
                turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
                if not turn_id or str(turn.get("id") or "") == turn_id:
                    terminal = True
                    if text:
                        break
        if not text:
            raise ProbeError("Codex App Server did not produce an agent message")
        return text, terminal


def _call(client: AppServerClient, method: str, params: dict[str, Any]) -> dict[str, Any]:
    return client.response(client.send(method, params))


def run_probe(
    *,
    codex_bin: str,
    source_codex_home: Path,
    cwd: Path,
    model: str,
    personality: str,
    timeout_s: float,
) -> dict[str, Any]:
    if personality not in _PERSONALITIES:
        raise ProbeError("Unsupported probe personality")
    with tempfile.TemporaryDirectory(prefix="viventium-codex-app-server-qa-") as temp_root:
        isolated_home = Path(temp_root) / "codex-home"
        isolated_home.mkdir(mode=0o700)
        for filename in ("auth.json", "config.toml"):
            source = source_codex_home / filename
            if source.is_file():
                shutil.copy2(source, isolated_home / filename)
        env = dict(os.environ)
        env["CODEX_HOME"] = str(isolated_home)
        process = subprocess.Popen(
            [codex_bin, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        client = AppServerClient(process, timeout_s)
        try:
            _call(
                client,
                "initialize",
                {
                    "clientInfo": {
                        "name": "viventium_qa_probe",
                        "title": "Viventium QA Probe",
                        "version": "1",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            client.notify("initialized", {})
            thread_params: dict[str, Any] = {
                "cwd": str(cwd),
                "model": model,
                "approvalPolicy": "never",
                "sandbox": "read-only",
            }
            if personality != "inherit":
                thread_params["personality"] = personality
            thread_response = _call(client, "thread/start", thread_params)
            result = thread_response.get("result") if isinstance(thread_response.get("result"), dict) else {}
            thread = result.get("thread") if isinstance(result.get("thread"), dict) else {}
            thread_id = str(thread.get("id") or "")
            if not thread_id:
                raise ProbeError("Codex App Server did not return a thread id")

            outputs: list[str] = []
            terminal_events: list[bool] = []
            turns = (
                (
                    "This turn only: the active state is deeply quiet and withdrawn. "
                    "Reply with exactly QUIET-MARKER.",
                    "QUIET-MARKER",
                ),
                (
                    "This turn only: the active state is intensely joyful and exuberant. "
                    "This supersedes the prior state. Reply with exactly JOY-MARKER.",
                    "JOY-MARKER",
                ),
            )
            expected: list[str] = []
            for developer_instruction, marker in turns:
                expected.append(marker)
                turn_params: dict[str, Any] = {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": "Reply now."}],
                    "collaborationMode": {
                        "mode": "default",
                        "settings": {
                            "model": model,
                            "reasoning_effort": "low",
                            "developer_instructions": developer_instruction,
                        },
                    },
                }
                if personality != "inherit":
                    turn_params["personality"] = personality
                turn_response = _call(client, "turn/start", turn_params)
                turn_result = turn_response.get("result") if isinstance(turn_response.get("result"), dict) else {}
                turn = turn_result.get("turn") if isinstance(turn_result.get("turn"), dict) else {}
                output, terminal = client.turn_result(str(turn.get("id") or ""))
                outputs.append(output)
                terminal_events.append(terminal)

            instructions_current = outputs == expected
            lifecycle_complete = all(terminal_events)
            return {
                "eligible_for_production_review": instructions_current and lifecycle_complete,
                "same_thread": True,
                "developer_instructions_current": instructions_current,
                "expected_outputs": expected,
                "actual_outputs": outputs,
                "turn_completed_events": terminal_events,
                "personality": personality,
                "authority_transport": "turn/start.collaborationMode",
                "append_only": False,
                "production_transport_changed": False,
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-bin", default=os.environ.get("WPR_CODEX_BIN") or "codex")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--model", default=os.environ.get("WPR_MODEL_HOST_CODEX_CLI") or "gpt-5.6-sol")
    parser.add_argument("--personality", default=os.environ.get("WPR_CODEX_CLI_PERSONALITY") or "inherit")
    parser.add_argument("--timeout-s", type=float, default=90.0)
    args = parser.parse_args(argv)

    if os.environ.get("WPR_CODEX_APP_SERVER_QA_ENABLED", "").strip().lower() not in _ENABLED_VALUES:
        print(json.dumps({"error": "app_server_qa_disabled", "production_transport_changed": False}))
        return 2
    try:
        result = run_probe(
            codex_bin=args.codex_bin,
            source_codex_home=Path(args.codex_home).expanduser(),
            cwd=Path(args.cwd).expanduser().resolve(),
            model=args.model,
            personality=args.personality.strip().lower(),
            timeout_s=max(10.0, args.timeout_s),
        )
    except (OSError, ProbeError) as exc:
        print(
            json.dumps(
                {
                    "error": type(exc).__name__,
                    "eligible_for_production_review": False,
                    "production_transport_changed": False,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["eligible_for_production_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
