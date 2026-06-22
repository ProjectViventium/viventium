#!/usr/bin/env python3
"""Run public-safe browser QA against a live provider-backed GlassHive worker.

This harness is intentionally outside the default deterministic suite. It uses
real local Codex/Claude credentials, starts the local GlassHive API/UI on a
temporary DB, drives the browser-visible worker/artifact surfaces, and verifies
the same workspace is continued.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import secrets
import signal
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_SRC = REPO_ROOT / "viventium_v0_4" / "GlassHive" / "runtime_phase1" / "src"
sys.path.insert(0, str(RUNTIME_SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from workers_projects_runtime.api import create_app  # noqa: E402

from local_user_grade_browser_qa import (  # noqa: E402
    PlaywrightCli,
    QaFailure,
    _json_request,
    _record,
)


FIRST_MARKER = "GLASSHIVE_LIVE_BROWSER_WAIT"
CONTINUE_MARKER = "GLASSHIVE_LIVE_BROWSER_CONTINUE"
FULL_MATRIX_ARTIFACTS = [
    "artifacts/provider-browser-wait.md",
    "output/provider-data.csv",
    "reports/provider-report.html",
    "artifacts/provider-report.pdf",
    "artifacts/provider-book.xlsx",
    "artifacts/provider-brief.docx",
    "artifacts/provider-deck.pptx",
]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "playwright" / "glasshive-live-provider-browser-wait-continue"
TERMINAL_STATES = {"completed", "failed", "cancelled", "interrupted"}
SIGNED_QUERY_SENTINELS = tuple("gh_" + name + "=" for name in ("token", "sig", "exp", "kind"))
FORBIDDEN_VISIBLE_SNIPPETS = (
    *SIGNED_QUERY_SENTINELS,
    "signature=",
    "/v1/" + "signed-links/",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_state(base_url: str, run_id: str, states: set[str], *, timeout_sec: float, poll_sec: float) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _json_request(f"{base_url}/v1/runs/{urllib.parse.quote(run_id)}")
        if str(last.get("state") or "") in states:
            return last
        time.sleep(poll_sec)
    return last


def _wait_for_terminal(base_url: str, run_id: str, *, timeout_sec: float, poll_sec: float) -> tuple[dict[str, Any], list[str]]:
    deadline = time.time() + timeout_sec
    states: list[str] = []
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _json_request(f"{base_url}/v1/runs/{urllib.parse.quote(run_id)}")
        state = str(last.get("state") or "")
        states.append(state)
        if state in TERMINAL_STATES:
            return last, states
        time.sleep(poll_sec)
    last = _json_request(f"{base_url}/v1/runs/{urllib.parse.quote(run_id)}")
    states.append(str(last.get("state") or ""))
    return last, states


def _start_server(state_root: Path, *, host_timeout_sec: float) -> tuple[uvicorn.Server, threading.Thread, str]:
    os.environ.setdefault("GLASSHIVE_ALLOWED_WORKER_PROFILES", "codex-cli,claude-code,openclaw-general")
    os.environ.setdefault("GLASSHIVE_DEFAULT_WORKER_PROFILE", "codex-cli")
    os.environ.setdefault("GLASSHIVE_HOST_RUN_TIMEOUT_SEC", str(int(host_timeout_sec)))
    os.environ["GLASSHIVE_SIGNED_LINK_SECRET"] = "public-safe-live-provider-browser-secret"
    os.environ["GLASSHIVE_LINK_REF_STATE_PATH"] = str(state_root / "link_refs.sqlite3")
    os.environ["WPR_HOST_WORKSPACE_ROOT"] = str(state_root / "host-workspaces")
    os.environ.setdefault("GLASSHIVE_LINK_REF_TTL_SECONDS", "0")

    app = create_app(db_path=str(state_root / "runtime.sqlite3"), runtime_backend="openclaw")
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise QaFailure("Live-provider browser QA server did not start")
    return server, thread, f"http://127.0.0.1:{port}"


def _stop_server(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=10)


def _scan_visible(values: dict[str, Any]) -> list[str]:
    serialized = json.dumps(values, sort_keys=True)
    found = [snippet for snippet in FORBIDDEN_VISIBLE_SNIPPETS if snippet in serialized]
    home = str(Path.home())
    if home and home in serialized:
        found.append("<local-home-path>")
    return found


def _links(pw: PlaywrightCli) -> list[dict[str, str]]:
    result = pw.eval("Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText, href: a.href}))")
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _link_by_text(links: list[dict[str, str]], text: str) -> str:
    needle = text.lower()
    for link in links:
        if needle in str(link.get("text") or "").lower() and str(link.get("href") or ""):
            return str(link["href"])
    raise QaFailure(f"Missing link containing {text!r}: {links}")


def _bytes_request(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def _validate_downloaded_artifact(path: str, payload: bytes) -> None:
    suffix = Path(path).suffix.lower()
    if suffix in {".md", ".csv", ".html"}:
        text = payload.decode("utf-8", errors="replace")
        if FIRST_MARKER not in text:
            raise QaFailure(f"{path} download did not contain {FIRST_MARKER}")
        return
    if suffix == ".pdf":
        if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-4096:]:
            raise QaFailure(f"{path} download is not a structurally valid PDF")
        return
    if suffix in {".xlsx", ".docx", ".pptx"}:
        expected_member = {
            ".xlsx": "xl/workbook.xml",
            ".docx": "word/document.xml",
            ".pptx": "ppt/presentation.xml",
        }[suffix]
        temp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            temp.write(payload)
            temp.close()
            with zipfile.ZipFile(temp.name) as archive:
                if expected_member not in archive.namelist():
                    raise QaFailure(f"{path} download missed OOXML member {expected_member}")
        finally:
            try:
                Path(temp.name).unlink()
            except OSError:
                pass
        return
    if not payload:
        raise QaFailure(f"{path} download was empty")


def _artifact_instruction(args: argparse.Namespace, artifact_path: str) -> str:
    if args.artifact_mode == "full-matrix":
        artifacts = ", ".join(FULL_MATRIX_ARTIFACTS)
        return (
            "Public-safe provider-backed browser QA. Do not browse the web. Wait about "
            f"{args.delay_seconds} seconds before finalizing so browser and API polling can observe an active run. "
            f"Create these artifacts, each containing marker {FIRST_MARKER} where the format allows visible text: "
            f"{artifacts}. Use ordinary local document tooling as needed for PDF, XLSX, DOCX, and PPTX. "
            f"Finish with FINAL REPORT: created the full artifact matrix with marker {FIRST_MARKER}."
        )
    return (
        "Public-safe provider-backed browser QA. Do not browse the web. Wait about "
        f"{args.delay_seconds} seconds before finalizing so browser and API polling can observe an active run. "
        f"Create {artifact_path} containing marker {FIRST_MARKER}. Finish with "
        f"FINAL REPORT: created {artifact_path} with marker {FIRST_MARKER}."
    )


def run_live_browser_qa(args: argparse.Namespace) -> dict[str, Any]:
    state_root = Path(tempfile.mkdtemp(prefix="glasshive-live-browser-"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_profile = "".join(ch if ch.isalnum() else "-" for ch in str(args.profile or "worker")).strip("-") or "worker"
    unique = f"{int(time.time())}-{safe_profile}-{secrets.token_hex(3)}"
    pw = PlaywrightCli(
        session=f"glasshive-live-provider-{safe_profile}-{os.getpid()}-{secrets.token_hex(4)}",
        output_dir=output_dir,
        headed=args.headed,
    )
    checks: list[dict[str, Any]] = []
    server: uvicorn.Server | None = None
    thread: threading.Thread | None = None
    try:
        server, thread, base_url = _start_server(state_root, host_timeout_sec=max(args.first_timeout_sec, args.continue_timeout_sec))
        project = _json_request(
            f"{base_url}/v1/projects",
            method="POST",
            payload={
                "owner_id": "public-browser-provider-user",
                "title": f"Public-safe provider browser QA {unique}",
                "goal": "Exercise provider-backed visible wait and continuation without private data.",
                "default_worker_profile": args.profile,
            },
        )
        worker = _json_request(
            f"{base_url}/v1/projects/{urllib.parse.quote(str(project['project_id']))}/workers",
            method="POST",
            payload={
                "owner_id": "public-browser-provider-user",
                "name": f"Provider browser QA worker {unique}",
                "role": "Local provider-backed browser QA",
                "profile": args.profile,
                "execution_mode": args.execution_mode,
            },
        )
        worker_id = str(worker["worker_id"])
        worker_url = f"{base_url}/ui/workers/{urllib.parse.quote(worker_id)}"
        artifact_path = "artifacts/provider-browser-wait.md"
        expected_artifact_paths = FULL_MATRIX_ARTIFACTS if args.artifact_mode == "full-matrix" else [artifact_path]
        instruction = _artifact_instruction(args, artifact_path)
        first = _json_request(
            f"{base_url}/v1/workers/{urllib.parse.quote(worker_id)}/assign",
            method="POST",
            payload={"instruction": instruction, "effort": args.effort},
        )
        first_run_id = str(first["run_id"])
        running = _wait_for_state(base_url, first_run_id, {"running"}, timeout_sec=args.running_timeout_sec, poll_sec=args.poll_sec)
        _record(checks, "first_run_visible_running_state", running.get("state") == "running", running, "API observed active provider run")

        pw.open(worker_url)
        worker_text_running = str(pw.eval("document.body.innerText"))
        _record(
            checks,
            "worker_page_visible_during_run",
            "Provider browser QA worker" in worker_text_running,
            worker_text_running[:1000],
            "worker page is visible during provider run",
        )
        pw.reload()
        worker_text_after_reload = str(pw.eval("document.body.innerText"))
        _record(
            checks,
            "worker_page_reload_during_run",
            "Provider browser QA worker" in worker_text_after_reload,
            worker_text_after_reload[:1000],
            "worker page remains visible after reload",
        )

        first_state, first_states = _wait_for_terminal(
            base_url,
            first_run_id,
            timeout_sec=args.first_timeout_sec,
            poll_sec=args.poll_sec,
        )
        _record(checks, "first_run_completed", first_state.get("state") == "completed", first_state, "first provider run completed")
        pw.open(worker_url)
        completed_text = str(pw.eval("document.body.innerText"))
        _record(checks, "first_output_visible", FIRST_MARKER in completed_text, completed_text[:1500], "first marker visible on worker page")

        artifacts = _json_request(f"{base_url}/v1/workers/{urllib.parse.quote(worker_id)}/artifacts")
        items = artifacts.get("items") if isinstance(artifacts.get("items"), list) else []
        items_by_path = {str(item.get("path") or ""): item for item in items if isinstance(item, dict)}
        missing_artifact_paths = [path for path in expected_artifact_paths if path not in items_by_path]
        _record(
            checks,
            "artifact_inventory_contains_expected_files",
            not missing_artifact_paths,
            {"missing": missing_artifact_paths, "items": items},
            "artifact inventory includes expected provider files",
        )
        artifact_item = next((item for item in items if str(item.get("path") or "") == artifact_path), None)
        _record(checks, "artifact_inventory_contains_provider_file", artifact_item is not None, items, "artifact inventory includes provider file")
        assert artifact_item is not None
        downloaded_artifacts: list[dict[str, Any]] = []
        for expected_path in expected_artifact_paths:
            item = items_by_path.get(expected_path)
            if not item:
                continue
            download_url = urllib.parse.urljoin(base_url, str(item.get("download_url") or ""))
            payload = _bytes_request(download_url)
            _validate_downloaded_artifact(expected_path, payload)
            downloaded_artifacts.append({"path": expected_path, "bytes": len(payload)})
        _record(
            checks,
            "artifact_downloads_structurally_valid",
            len(downloaded_artifacts) == len(expected_artifact_paths),
            downloaded_artifacts,
            "expected provider artifacts download and validate structurally",
        )
        open_url = urllib.parse.urljoin(base_url, str(artifact_item.get("open_url") or ""))
        pw.open(open_url)
        artifact_text = str(pw.eval("document.body.innerText"))
        artifact_links = _links(pw)
        _record(checks, "artifact_preview_visible", FIRST_MARKER in artifact_text, artifact_text[:1000], "artifact preview shows first marker")
        _record(
            checks,
            "artifact_preview_redacted",
            not _scan_visible({"text": artifact_text, "links": artifact_links, "url": str(pw.eval("location.href"))}),
            _scan_visible({"text": artifact_text, "links": artifact_links, "url": str(pw.eval("location.href"))}),
            "artifact preview has no signed-token or local-path leakage",
        )
        workspace_href = _link_by_text(artifact_links, "View workspace")
        pw.open(workspace_href)
        workspace_url = str(pw.eval("location.href"))
        workspace_text = str(pw.eval("document.body.innerText"))
        _record(checks, "workspace_short_ref_visible", "/w/" in workspace_url, workspace_url, "workspace opened via tokenless short ref")
        _record(
            checks,
            "workspace_visible_redacted",
            not _scan_visible({"text": workspace_text, "url": workspace_url}),
            _scan_visible({"text": workspace_text, "url": workspace_url}),
            "workspace view has no signed-token or local-path leakage",
        )

        continuation = _json_request(
            f"{base_url}/v1/workers/{urllib.parse.quote(worker_id)}/message",
            method="POST",
            payload={
                "message": (
                    f"Continue in the same workspace. Append marker {CONTINUE_MARKER} to {artifact_path}. "
                    f"Finish with FINAL REPORT: appended {CONTINUE_MARKER}."
                )
            },
        )
        continuation_state, continuation_states = _wait_for_terminal(
            base_url,
            str(continuation["run_id"]),
            timeout_sec=args.continue_timeout_sec,
            poll_sec=args.poll_sec,
        )
        _record(
            checks,
            "continuation_completed",
            continuation_state.get("state") == "completed",
            continuation_state,
            "same-worker continuation completed",
        )
        pw.open(open_url)
        continued_artifact_text = str(pw.eval("document.body.innerText"))
        _record(
            checks,
            "continued_artifact_visible",
            CONTINUE_MARKER in continued_artifact_text,
            continued_artifact_text[:1500],
            "artifact preview shows continuation marker",
        )

        workspace_dir = Path(str(worker.get("workspace_dir") or ""))
        evidence_path = workspace_dir / "glasshive-run" / "evidence.json"
        evidence: dict[str, Any] = {}
        if evidence_path.exists():
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence_result = evidence.get("evidence_result") if isinstance(evidence.get("evidence_result"), dict) else {}
        transcript = evidence.get("transcript") if isinstance(evidence.get("transcript"), dict) else {}
        transcript_meta = transcript.get("metadata") if isinstance(transcript.get("metadata"), dict) else {}
        _record(
            checks,
            "evidence_status_truthful",
            evidence_result.get("status") in {"pass", "warn"},
            evidence_result,
            "latest run evidence is pass or advisory warn",
        )
        _record(
            checks,
            "transcript_metadata_recorded",
            bool(transcript_meta),
            transcript_meta,
            "transcript tail metadata is present for provider CLI evidence",
        )

        final_forbidden = _scan_visible(
            {
                "worker_text": completed_text,
                "artifact_text": continued_artifact_text,
                "workspace_text": workspace_text,
                "workspace_url": workspace_url,
            }
        )
        _record(checks, "public_visible_redaction", not final_forbidden, final_forbidden, "no forbidden signed-link or local path leakage")

        return {
            "schema": "glasshive.live-provider-browser-wait-continue-qa.v1",
            "passed": all(check["passed"] for check in checks),
            "profile": args.profile,
            "execution_mode": args.execution_mode,
            "effort": args.effort,
            "artifact_mode": args.artifact_mode,
            "expected_artifacts": expected_artifact_paths,
            "first_observed_states": list(dict.fromkeys(first_states)),
            "continue_observed_states": list(dict.fromkeys(continuation_states)),
            "checks": checks,
            "evidence_status": evidence_result.get("status"),
            "workspace_state_root": state_root.name,
            "browser_commands": pw.commands,
        }
    finally:
        pw.close()
        if server is not None and thread is not None:
            _stop_server(server, thread)
        if not args.keep_state and state_root.exists():
            shutil.rmtree(state_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="codex-cli", choices=["codex-cli", "claude-code", "openclaw-general"])
    parser.add_argument("--execution-mode", default="host", choices=["host", "docker"])
    parser.add_argument("--effort", default="xhigh")
    parser.add_argument("--artifact-mode", default="markdown", choices=["markdown", "full-matrix"])
    parser.add_argument("--delay-seconds", type=int, default=35)
    parser.add_argument("--running-timeout-sec", type=float, default=30.0)
    parser.add_argument("--first-timeout-sec", type=float, default=420.0)
    parser.add_argument("--continue-timeout-sec", type=float, default=420.0)
    parser.add_argument("--poll-sec", type=float, default=5.0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--keep-state", action="store_true")
    args = parser.parse_args()

    try:
        evidence = run_live_browser_qa(args)
    except (QaFailure, TimeoutError, OSError, json.JSONDecodeError) as exc:
        evidence = {
            "schema": "glasshive.live-provider-browser-wait-continue-qa.v1",
            "passed": False,
            "error": str(exc),
            "profile": args.profile,
            "execution_mode": args.execution_mode,
            "effort": args.effort,
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 1
    finally:
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, signal.default_int_handler)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
