#!/usr/bin/env python3
"""Run public-safe user-grade browser QA against the local GlassHive fixture.

The fixture is provider-free and cloud-free, but this script drives it through a
real browser via the bundled Playwright CLI. It verifies the same evidence shape
expected from live runs: visible UI, refresh persistence, short-link artifact
navigation, active-run controls, artifact bytes, document signatures, and DB
state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_SCRIPT = REPO_ROOT / "qa" / "glasshive_deep_research" / "scripts" / "local_user_grade_fixture.py"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "playwright" / "glasshive-local-user-grade-browser-qa"
PUBLIC_MARKER = "GLASSHIVE_BROWSER_QA_MARKER"
SIGNED_QUERY_NAMES = ("token", "sig", "exp", "kind")
SIGNED_QUERY_SENTINELS = tuple("gh_" + name + "=" for name in SIGNED_QUERY_NAMES)
FORBIDDEN_PUBLIC_PATTERNS = (
    *SIGNED_QUERY_SENTINELS,
    "signature=",
    "workspace_dir",
    "state_dir",
)


class QaFailure(AssertionError):
    """Raised when a local browser QA expectation fails."""


def _json_request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _bytes_request(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "*/*"}, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def _wait_run(base_url: str, run_id: str, *, terminal: bool = True, timeout_sec: float = 20) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _json_request(f"{base_url}/v1/runs/{urllib.parse.quote(run_id)}")
        state = str(last.get("state") or "")
        if terminal and state in {"completed", "failed", "cancelled", "interrupted", "paused"}:
            return last
        if not terminal and state in {"running", "paused", "interrupted"}:
            return last
        time.sleep(0.25)
    return last


def _wait_for_state(base_url: str, run_id: str, states: set[str], *, timeout_sec: float = 20) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _json_request(f"{base_url}/v1/runs/{urllib.parse.quote(run_id)}")
        if str(last.get("state") or "") in states:
            return last
        time.sleep(0.25)
    return last


def _extract_cli_result(stdout: str) -> Any:
    match = re.search(r"### Result\n(?P<payload>.*?)(?:\n### Ran Playwright code|\Z)", stdout, flags=re.S)
    if not match:
        return stdout.strip()
    payload = match.group("payload").strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload


class PlaywrightCli:
    def __init__(self, *, session: str, output_dir: Path, headed: bool = False) -> None:
        code_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        self.binary = Path(os.environ.get("PWCLI") or code_home / "skills" / "playwright" / "scripts" / "playwright_cli.sh")
        if not self.binary.exists():
            raise QaFailure(f"Playwright CLI wrapper not found at {self.binary}")
        if shutil.which("npx") is None:
            raise QaFailure("npx is required by the bundled Playwright CLI wrapper")
        self.session = session
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headed = headed
        self.commands: list[dict[str, object]] = []

    def run(self, *args: str, timeout_sec: float = 60) -> subprocess.CompletedProcess[str]:
        cmd = [str(self.binary), "--session", self.session, *args]
        if args and args[0] == "open" and self.headed and "--headed" not in args:
            cmd.append("--headed")
        result = subprocess.run(
            cmd,
            cwd=str(self.output_dir),
            text=True,
            capture_output=True,
            timeout=timeout_sec,
        )
        self.commands.append(
            {
                "args": [arg if not arg.startswith("http://127.0.0.1") else "<local-url>" for arg in args],
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-1000:],
                "stderr_tail": result.stderr[-1000:],
            }
        )
        if result.returncode != 0:
            raise QaFailure(f"Playwright CLI failed for {args}: {result.stderr or result.stdout}")
        return result

    def open(self, url: str) -> None:
        self.run("open", url, timeout_sec=90)

    def reload(self) -> None:
        self.run("reload", timeout_sec=60)

    def snapshot(self) -> str:
        return self.run("snapshot", timeout_sec=60).stdout

    def eval(self, expression: str) -> Any:
        return _extract_cli_result(self.run("eval", expression, timeout_sec=60).stdout)

    def close(self) -> None:
        try:
            subprocess.run(
                [str(self.binary), "--session", self.session, "close"],
                cwd=str(self.output_dir),
                text=True,
                capture_output=True,
                timeout=20,
            )
        except (subprocess.SubprocessError, OSError):
            return


def _record(checks: list[dict[str, Any]], name: str, passed: bool, actual: Any, expected: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "expected": expected, "actual": actual})
    if not passed:
        raise QaFailure(f"{name} failed: expected {expected}; actual={actual!r}")


def _find_link(links: list[dict[str, str]], *, text_contains: str | None = None, href_contains: str | None = None) -> str:
    for link in links:
        text = str(link.get("text") or "")
        href = str(link.get("href") or "")
        if text_contains and text_contains.lower() not in text.lower():
            continue
        if href_contains and href_contains not in href:
            continue
        if href:
            return href
    raise QaFailure(f"Missing link text={text_contains!r} href={href_contains!r}: {links}")


def _scan_forbidden(values: dict[str, Any]) -> list[str]:
    found: list[str] = []
    serialized = json.dumps(values, sort_keys=True)
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        if pattern in serialized:
            found.append(pattern)
    home_path = str(Path.home())
    if home_path and home_path in serialized:
        found.append("<local-home-path>")
    return found


def _document_signature_checks(workspace_dir: Path) -> dict[str, bool]:
    artifacts = workspace_dir / "artifacts"
    checks = {
        "pdf_header": (artifacts / "report.pdf").read_bytes().startswith(b"%PDF-"),
        "xlsx_ooxml": False,
        "docx_ooxml": False,
        "pptx_ooxml": False,
        "csv_marker": PUBLIC_MARKER in (workspace_dir / "output" / "data.csv").read_text(encoding="utf-8"),
        "html_marker": PUBLIC_MARKER in (workspace_dir / "reports" / "report.html").read_text(encoding="utf-8"),
    }
    for key, relative in {
        "xlsx_ooxml": "artifacts/book.xlsx",
        "docx_ooxml": "artifacts/brief.docx",
        "pptx_ooxml": "artifacts/deck.pptx",
    }.items():
        with zipfile.ZipFile(workspace_dir / relative) as archive:
            names = set(archive.namelist())
        checks[key] = "[Content_Types].xml" in names
    return checks


def _sqlite_counts(db_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        for table in ("projects", "workers", "runs", "events"):
            try:
                row = conn.execute(f"select count(*) from {table}").fetchone()
            except sqlite3.Error:
                continue
            counts[table] = int(row[0] if row else 0)
    return counts


def _start_fixture(state_root: Path) -> tuple[subprocess.Popen[str], dict[str, Any]]:
    process = subprocess.Popen(
        [sys.executable, str(FIXTURE_SCRIPT), "--fresh", "--state-root", str(state_root)],
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    deadline = time.time() + 30
    stderr_tail = ""
    while time.time() < deadline:
        line = process.stdout.readline()
        if line.startswith("GLASSHIVE_QA_SERVER "):
            return process, json.loads(line.removeprefix("GLASSHIVE_QA_SERVER ").strip())
        if process.poll() is not None:
            if process.stderr:
                stderr_tail = process.stderr.read()[-2000:]
            raise QaFailure(f"Fixture exited before startup: {stderr_tail}")
    process.terminate()
    raise QaFailure("Timed out waiting for fixture startup")


def run_browser_qa(*, output_dir: Path, headed: bool = False) -> dict[str, Any]:
    state_root = Path(tempfile.mkdtemp(prefix="glasshive-browser-qa-"))
    process: subprocess.Popen[str] | None = None
    pw = PlaywrightCli(session=f"glasshive-local-{int(time.time())}", output_dir=output_dir, headed=headed)
    checks: list[dict[str, Any]] = []
    try:
        process, fixture = _start_fixture(state_root)
        base_url = str(fixture["base_url"])
        worker = fixture["worker"]
        worker_id = str(worker["worker_id"])
        workspace_dir = Path(str(worker["workspace_dir"]))

        pw.open(str(fixture["project_url"]))
        project_snapshot = pw.snapshot()
        project_text = str(pw.eval("document.body.innerText"))
        _record(checks, "project_ui_visible", "Public-safe local browser QA" in project_text, project_text[:500], "project title visible")

        pw.open(str(fixture["artifact_open_url"]))
        artifact_snapshot = pw.snapshot()
        artifact_text = str(pw.eval("document.body.innerText"))
        links = pw.eval(
            "Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText, href: a.href}))"
        )
        _record(checks, "artifact_preview_visible", PUBLIC_MARKER in artifact_text, artifact_text[:500], "artifact marker visible")
        _record(checks, "artifact_preview_has_links", isinstance(links, list) and len(links) >= 2, links, "workspace and download links")
        workspace_href = _find_link(links, text_contains="View workspace", href_contains="/w/")
        download_href = _find_link(links, text_contains="Download")
        parsed_download = urllib.parse.urlparse(download_href)
        _record(
            checks,
            "artifact_download_uses_short_ref",
            parsed_download.path.startswith(("/v1/link-refs/", "/r/")) and not parsed_download.query,
            download_href,
            "tokenless short-ref download indirection",
        )
        forbidden = _scan_forbidden({"artifact_text": artifact_text, "artifact_links": links})
        _record(checks, "artifact_page_redacted", not forbidden, forbidden, "no signed-token query or local path leakage")
        downloaded = _bytes_request(download_href)
        _record(checks, "artifact_download_bytes", PUBLIC_MARKER.encode("utf-8") in downloaded, len(downloaded), "download contains marker")

        pw.open(workspace_href)
        workspace_snapshot = pw.snapshot()
        workspace_text = str(pw.eval("document.body.innerText"))
        _record(checks, "workspace_short_ref_visible", "Pause" in workspace_text and "Interrupt" in workspace_text, workspace_text[:700], "workspace controls visible")
        current_url = str(pw.eval("location.href"))
        _record(
            checks,
            "workspace_uses_short_ref",
            "/w/" in current_url and SIGNED_QUERY_SENTINELS[0] not in current_url,
            current_url,
            "tokenless /w/{ref}",
        )
        pw.reload()
        reloaded_text = str(pw.eval("document.body.innerText"))
        _record(
            checks,
            "workspace_refresh_controls_persist",
            "Pause" in reloaded_text and "Resume" in reloaded_text and "Interrupt" in reloaded_text,
            reloaded_text[:700],
            "watch controls persist after reload",
        )

        pw.open(str(fixture["worker_url"]))
        worker_page_text = str(pw.eval("document.body.innerText"))
        artifact_inventory = _json_request(f"{base_url}/v1/workers/{urllib.parse.quote(worker_id)}/artifacts")
        artifact_paths = [str(item.get("path") or "") for item in artifact_inventory.get("items", [])]
        _record(
            checks,
            "visible_worker_page_artifacts_persist",
            "answer.md" in worker_page_text and "output/data.csv" in worker_page_text,
            worker_page_text[:1000],
            "diagnostic worker page shows generated artifacts",
        )
        _record(
            checks,
            "artifact_api_inventory_persists",
            "answer.md" in artifact_paths and "artifacts/report.pdf" in artifact_paths,
            artifact_paths,
            "artifact API inventory includes text and professional artifacts",
        )

        active = _json_request(
            f"{base_url}/v1/workers/{urllib.parse.quote(worker_id)}/assign",
            method="POST",
            payload={"instruction": "GH_QA_SLEEP public-safe active-run control check.", "effort": "high"},
        )
        active_run_id = str(active["run_id"])
        running = _wait_for_state(base_url, active_run_id, {"running"}, timeout_sec=8)
        _record(checks, "active_run_observed", running.get("state") == "running", running, "running state observed")

        pause_response = _json_request(f"{workspace_href}/actions/pause", method="POST", payload={})
        _record(
            checks,
            "workspace_pause_action",
            pause_response.get("state") == "paused",
            pause_response,
            "signed workspace pause returns paused worker state",
        )

        resume_response = _json_request(f"{workspace_href}/actions/resume", method="POST", payload={})
        resumed = _wait_for_state(base_url, active_run_id, {"running"}, timeout_sec=8)
        _record(
            checks,
            "workspace_resume_action",
            resume_response.get("state") == "running" and resumed.get("state") == "running",
            {"response": resume_response, "run": resumed},
            "signed workspace resume returns running worker and active run remains visible",
        )

        interrupt_response = _json_request(f"{workspace_href}/actions/interrupt", method="POST", payload={})
        interrupted = _wait_for_state(base_url, active_run_id, {"interrupted"}, timeout_sec=8)
        _record(checks, "workspace_interrupt_action", interrupted.get("state") == "interrupted", interrupt_response, "signed workspace interrupt works")

        continuation = _json_request(
            f"{base_url}/v1/workers/{urllib.parse.quote(worker_id)}/message",
            method="POST",
            payload={"message": "Continue after interruption and recreate public-safe fixture deliverables."},
        )
        continued = _wait_run(base_url, str(continuation["run_id"]), timeout_sec=70)
        _record(checks, "continue_after_interrupt", continued.get("state") == "completed", continued, "continuation completes")
        pw.open(str(fixture["worker_url"]))
        continued_text = str(pw.eval("document.body.innerText"))
        _record(
            checks,
            "continued_worker_output_visible",
            PUBLIC_MARKER in continued_text and "FINAL REPORT" in continued_text,
            continued_text[:1000],
            "continued output visible on worker detail surface",
        )

        signatures = _document_signature_checks(workspace_dir)
        _record(checks, "document_signatures", all(signatures.values()), signatures, "PDF/OOXML/CSV/HTML signatures pass")

        db_counts = _sqlite_counts(Path(str(fixture["db_path"])))
        _record(
            checks,
            "sqlite_state_correlates",
            db_counts.get("projects", 0) >= 1 and db_counts.get("workers", 0) >= 1 and db_counts.get("runs", 0) >= 3,
            db_counts,
            "DB contains project, worker, initial run, active run, and continuation",
        )

        final_forbidden = _scan_forbidden(
            {
                "project_text": project_text,
                "artifact_text": artifact_text,
                "workspace_text": continued_text,
                "links": links,
                "current_url": current_url,
            }
        )
        _record(checks, "public_surface_redaction", not final_forbidden, final_forbidden, "no forbidden public-surface leakage")

        return {
            "schema": "glasshive.local-user-grade-browser-qa.v1",
            "passed": all(check["passed"] for check in checks),
            "fixture": {
                "base_url": base_url,
                "profile": worker.get("profile"),
                "execution_mode": worker.get("execution_mode"),
            },
            "checks": checks,
            "playwright": {
                "session": pw.session,
                "commands": pw.commands,
                "project_snapshot_tail": project_snapshot[-1000:],
                "artifact_snapshot_tail": artifact_snapshot[-1000:],
                "workspace_snapshot_tail": workspace_snapshot[-1000:],
            },
            "db_counts": db_counts,
            "state_root_name": state_root.name,
        }
    finally:
        pw.close()
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--headed", action="store_true", help="Open a headed browser window for visual inspection.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        evidence = run_browser_qa(output_dir=args.output_dir, headed=args.headed)
    except (QaFailure, subprocess.TimeoutExpired, urllib.error.URLError) as exc:
        evidence = {
            "schema": "glasshive.local-user-grade-browser-qa.v1",
            "passed": False,
            "error": str(exc),
        }
        (args.output_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 1

    (args.output_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
