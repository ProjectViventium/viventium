#!/usr/bin/env python3
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HOST = os.environ.get("CURSOR_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CURSOR_BRIDGE_PORT", "18081"))
LOG_PATH = Path(
    os.environ.get(
        "CURSOR_BRIDGE_LOG",
        str(Path.home() / "Desktop" / "cursor-bridge-probe.jsonl"),
    )
)
DEFAULT_MODEL = os.environ.get("CURSOR_BRIDGE_MODEL", "SUBSCRIPTION OPUS")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_log(entry: dict) -> None:
    _ensure_parent(LOG_PATH)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {"_raw": raw.decode("utf-8", errors="replace")}


def _chat_completion_payload(model: str) -> dict:
    return {
        "id": f"chatcmpl-probe-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Local Cursor bridge probe reached successfully.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        },
    }


def _responses_payload(model: str) -> dict:
    return {
        "id": f"resp-probe-{int(time.time() * 1000)}",
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "status": "completed",
        "output": [
            {
                "id": f"msg-probe-{int(time.time() * 1000)}",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Local Cursor bridge probe reached successfully.",
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "CursorOpenAIProbe/0.1"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, events: list[dict]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        for event in events:
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _log(self, body: dict | None = None) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "method": self.command,
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "body": body,
        }
        _write_log(entry)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        self._log()
        if parsed.path in ("/healthz", "/v1/healthz"):
            self._send_json(200, {"ok": True, "model": DEFAULT_MODEL})
            return
        if parsed.path in ("/models", "/v1/models"):
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": DEFAULT_MODEL,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "local",
                        }
                    ],
                },
            )
            return
        self._send_json(404, {"error": f"Unhandled GET {parsed.path}"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = _read_json(self)
        self._log(body)
        model = body.get("model") or DEFAULT_MODEL
        is_stream = bool(body.get("stream"))
        if parsed.path in ("/chat/completions", "/v1/chat/completions"):
            if is_stream:
                chunk = {
                    "id": f"chatcmpl-probe-{int(time.time() * 1000)}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": "Local Cursor bridge probe reached successfully.",
                            },
                            "finish_reason": None,
                        }
                    ],
                }
                done = {
                    "id": chunk["id"],
                    "object": "chat.completion.chunk",
                    "created": chunk["created"],
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                self._send_sse([chunk, done])
            else:
                self._send_json(200, _chat_completion_payload(model))
            return
        if parsed.path in ("/responses", "/v1/responses"):
            if is_stream:
                created = int(time.time())
                resp_id = f"resp-probe-{int(time.time() * 1000)}"
                events = [
                    {
                        "type": "response.created",
                        "response": {
                            "id": resp_id,
                            "object": "response",
                            "created_at": created,
                            "model": model,
                            "status": "in_progress",
                        },
                    },
                    {
                        "type": "response.output_text.delta",
                        "delta": "Local Cursor bridge probe reached successfully.",
                    },
                    {
                        "type": "response.completed",
                        "response": _responses_payload(model),
                    },
                ]
                self._send_sse(events)
            else:
                self._send_json(200, _responses_payload(model))
            return
        self._send_json(404, {"error": f"Unhandled POST {parsed.path}"})

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))


def main() -> int:
    print(f"Cursor bridge probe listening on http://{HOST}:{PORT}", flush=True)
    print(f"Logging requests to {LOG_PATH}", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
