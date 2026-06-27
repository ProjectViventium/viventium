#!/usr/bin/env python3
"""Serve public-safe GlassHive watch fixtures for noVNC lifecycle states.

This is a local QA helper, not production code. It serves the real GlassHive
static watch/desktop assets while returning synthetic worker payloads and
deliberately controlled noVNC paths. Completed/parked workers should report a
settled workspace instead of an endless reconnect. Active workers should retry
after a dropped desktop connection and reattach.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC_DIR = (
    REPO_ROOT
    / "viventium_v0_4"
    / "GlassHive"
    / "frontends"
    / "glass-drive-ui"
    / "src"
    / "glass_drive_ui"
    / "static"
)


def fixture_case(worker_id: str) -> str:
    if worker_id.endswith("-active-disconnect"):
        return "active_disconnect"
    if worker_id.endswith("-no-view"):
        return "no_view"
    if worker_id.endswith("-disconnect"):
        return "disconnect"
    return "import_502"


def live_payload(worker_id: str) -> dict[str, object]:
    case = fixture_case(worker_id)
    view_available = case != "no_view"
    view_healthy = case != "no_view"
    active = case == "active_disconnect"
    return {
        "worker": {
            "worker_id": worker_id,
            "name": "Active Fixture Worker" if active else "Completed Fixture Worker",
            "project_id": "project-completed-fixture",
            "profile": "codex-cli",
            "state": "running" if active else "ready",
        },
        "project_title": "Active Desktop Fixture" if active else "Completed Desktop Fixture",
        "runtime_details": {
            "mode": "docker-workstation",
            "runtime": "codex-cli",
            "sandbox_state": "running",
            "view_available": view_available,
            "view_health": {
                "healthy": view_healthy,
                "reason": "fixture_no_view" if case == "no_view" else "fixture_desktop_probe",
            },
        },
        "latest_run": {
            "run_id": "run-active-fixture" if active else "run-completed-fixture",
            "state": "running" if active else "completed",
            "instruction": (
                "Keep the desktop running for public-safe reconnect QA."
                if active
                else "Create two public-safe deliverables."
            ),
        },
        "latest_output": (
            "Delivered page ready - pdf-inspection-report.html\n\n"
            "The uploaded PDF is available inside the GlassHive workspace at "
            "`uploads/glasshive-ui-upload-smoke.pdf`."
        ),
        "deliverable": {
            "kind": "file",
            "label": "pdf-inspection-report.html",
            "workspace_path": "deliveries/pdf-inspection-report.html",
            "open_url": "/v1/link-refs/open-html-fixture",
            "download_url": "/v1/link-refs/download-html-fixture",
        },
        "artifacts": {
            "items": [
                {
                    "path": "deliveries/pdf-inspection-report.html",
                    "size": 3072,
                    "open_url": "/v1/link-refs/open-html-fixture",
                    "download_url": "/v1/link-refs/download-html-fixture",
                },
                {
                    "path": "deliveries/pdf-inspection-report.txt",
                    "size": 350,
                    "open_url": "/v1/link-refs/open-txt-fixture",
                    "download_url": "/v1/link-refs/download-txt-fixture",
                },
            ]
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "GlassHiveCompletedDesktopFixture/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        self._send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _send_js(self, status: int, body: str) -> None:
        self._send_bytes(status, body.encode("utf-8"), "text/javascript")

    def _send_static(self, name: str) -> None:
        path = STATIC_DIR / name
        if not path.is_file() or STATIC_DIR not in path.resolve().parents:
            self._send_bytes(404, b"not found", "text/plain")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self._send_bytes(200, path.read_bytes(), content_type)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.send_response(302)
            self.send_header(
                "Location",
                "/watch/worker-completed-import-502?surface=desktop&project_id=project-completed-fixture",
            )
            self.end_headers()
            return
        if path.startswith("/watch/"):
            self._send_static("watch.html")
            return
        if path.startswith("/desktop/"):
            self._send_static("desktop.html")
            return
        if path.startswith("/static/"):
            self._send_static(path.removeprefix("/static/"))
            return
        if path.startswith("/api/worker/") and path.endswith("/live"):
            worker_id = path.removeprefix("/api/worker/").removesuffix("/live")
            self._send_json(200, live_payload(worker_id))
            return
        if path.startswith("/novnc/"):
            worker_id = path.removeprefix("/novnc/").split("/", 1)[0]
            if fixture_case(worker_id) == "active_disconnect" and path.endswith("/core/rfb.js"):
                self._send_js(
                    200,
                    """
let instanceCount = 0;
export default class RFB extends EventTarget {
  constructor(stage, url, options) {
    super();
    this.stage = stage;
    this.url = url;
    this.options = options;
    instanceCount += 1;
    if (instanceCount === 1) {
      setTimeout(() => {
        this.dispatchEvent(new CustomEvent('connect', { detail: {} }));
      }, 10);
      setTimeout(() => {
        this.dispatchEvent(new CustomEvent('disconnect', { detail: { clean: false } }));
      }, 50);
    } else {
      setTimeout(() => {
        this.dispatchEvent(new CustomEvent('connect', { detail: {} }));
      }, 10);
    }
  }
  disconnect() {}
  focus() {}
  clipboardPasteFrom() {}
}
""".strip(),
                )
                return
            if fixture_case(worker_id) == "disconnect" and path.endswith("/core/rfb.js"):
                self._send_js(
                    200,
                    """
export default class RFB extends EventTarget {
  constructor(stage, url, options) {
    super();
    this.stage = stage;
    this.url = url;
    this.options = options;
    setTimeout(() => {
      this.dispatchEvent(new CustomEvent('disconnect', { detail: { clean: false } }));
    }, 25);
  }
  disconnect() {}
  focus() {}
  clipboardPasteFrom() {}
}
""".strip(),
                )
                return
            self._send_bytes(502, b"fixture noVNC unavailable", "text/plain")
            return
        if path.startswith("/v1/link-refs/"):
            self._send_bytes(200, b"fixture artifact", "text/plain")
            return
        self._send_bytes(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path.startswith("/api/worker/"):
            self._send_json(200, {"status": "accepted"})
            return
        self._send_bytes(404, b"not found", "text/plain")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    host, port = httpd.server_address
    print(
        f"http://{host}:{port}/watch/worker-completed-import-502?surface=desktop&project_id=project-completed-fixture",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
