#!/usr/bin/env python3
"""Minimal role-scoped reverse proxy for automatic Parallel Work containers.

The proxy deliberately has no generic forward-proxy or CONNECT behavior. It accepts only the
provider or MCP paths owned by its configured role and forwards a small request-header allowlist to
the host Core API. Request/response bodies and authorization headers are never logged.
"""

from __future__ import annotations

import http.client
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


MAX_REQUEST_BYTES = 2 * 1024 * 1024
ROUTES = {
    "provider": {
        "/openai/v1/responses": "/api/viventium/glasshive/providers/openai/v1/responses",
        "/anthropic/v1/messages": "/api/viventium/glasshive/providers/anthropic/v1/messages",
    },
    "broker": {
        "/mcp": "/api/viventium/glasshive/capabilities/mcp",
    },
}
FORWARDED_REQUEST_HEADERS = {
    "accept": "Accept",
    "anthropic-beta": "Anthropic-Beta",
    "anthropic-version": "Anthropic-Version",
    "authorization": "Authorization",
    "content-type": "Content-Type",
}
FORWARDED_RESPONSE_HEADERS = {
    "content-type",
    "openai-processing-ms",
    "retry-after",
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
    "x-request-id",
}


def route_for(role: str, path: str) -> str | None:
    if not isinstance(path, str) or not path.startswith("/") or "?" in path or "#" in path:
        return None
    return ROUTES.get(str(role or "").strip().lower(), {}).get(path)


def forward_headers(headers, *, content_length: int) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_name, raw_value in headers.items():
        output_name = FORWARDED_REQUEST_HEADERS.get(str(raw_name).lower())
        value = str(raw_value)
        if (
            output_name
            and value
            and len(value) <= 8192
            and "\r" not in value
            and "\n" not in value
        ):
            result[output_name] = value
    result["Content-Length"] = str(content_length)
    return result


def _configuration() -> tuple[str, str, int]:
    role = str(os.environ.get("VIVENTIUM_PARALLEL_PROXY_ROLE") or "").strip().lower()
    if role not in ROUTES:
        raise RuntimeError("VIVENTIUM_PARALLEL_PROXY_ROLE must be provider or broker")
    parsed = urlsplit(str(os.environ.get("VIVENTIUM_PARALLEL_PROXY_UPSTREAM") or "").strip())
    if (
        parsed.scheme != "http"
        or parsed.hostname != "host.docker.internal"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.port is None
    ):
        raise RuntimeError("VIVENTIUM_PARALLEL_PROXY_UPSTREAM must be an exact local Core URL")
    return role, parsed.hostname, parsed.port


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ViventiumParallelProxy/1"

    def log_message(self, _format: str, *_args) -> None:
        return

    def _empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path != "/health":
            self._empty(404)
            return
        payload = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        try:
            role, upstream_host, upstream_port = _configuration()
        except RuntimeError:
            self._empty(503)
            return
        upstream_path = route_for(role, self.path)
        if upstream_path is None:
            self._empty(404)
            return
        try:
            content_length = int(self.headers.get("Content-Length") or "")
        except ValueError:
            content_length = -1
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self._empty(413)
            return
        body = self.rfile.read(content_length)
        if len(body) != content_length:
            self._empty(400)
            return
        connection = http.client.HTTPConnection(upstream_host, upstream_port, timeout=720)
        try:
            connection.request(
                "POST",
                upstream_path,
                body=body,
                headers=forward_headers(self.headers, content_length=content_length),
            )
            upstream = connection.getresponse()
            self.send_response(upstream.status)
            self.send_header("Cache-Control", "no-store")
            # Upstream bodies may be streamed without a Content-Length. Close framing keeps the
            # worker client from waiting indefinitely after the final byte.
            self.send_header("Connection", "close")
            self.close_connection = True
            for name, value in upstream.getheaders():
                if name.lower() in FORWARDED_RESPONSE_HEADERS:
                    self.send_header(name, value)
            self.end_headers()
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError, TimeoutError):
            if not self.wfile.closed:
                try:
                    self._empty(502)
                except (BrokenPipeError, OSError):
                    pass
        finally:
            connection.close()


def main() -> None:
    _configuration()
    raw_port = str(os.environ.get("VIVENTIUM_PARALLEL_PROXY_PORT") or "8080").strip()
    port = int(raw_port)
    if port < 1024 or port > 65535:
        raise RuntimeError("VIVENTIUM_PARALLEL_PROXY_PORT is invalid")
    server = ThreadingHTTPServer(("0.0.0.0", port), ProxyHandler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
