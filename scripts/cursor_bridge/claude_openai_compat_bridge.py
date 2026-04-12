#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HOST = os.environ.get("CURSOR_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CURSOR_BRIDGE_PORT", "18081"))
CLAUDE_MODEL = os.environ.get("CURSOR_BRIDGE_CLAUDE_MODEL", "claude-opus-4-6")
CLAUDE_EFFORT = os.environ.get("CURSOR_BRIDGE_CLAUDE_EFFORT", "max")
CLAUDE_OPENAI_MODEL_ID = os.environ.get(
    "CURSOR_BRIDGE_CLAUDE_OPENAI_MODEL_ID",
    os.environ.get("CURSOR_BRIDGE_OPENAI_MODEL_ID", "SUBSCRIPTION OPUS"),
)
CODEX_MODEL = os.environ.get("CURSOR_BRIDGE_CODEX_MODEL", "gpt-5.4")
CODEX_REASONING_EFFORT = os.environ.get("CURSOR_BRIDGE_CODEX_REASONING_EFFORT", "xhigh")
CODEX_OPENAI_MODEL_ID = os.environ.get(
    "CURSOR_BRIDGE_CODEX_OPENAI_MODEL_ID",
    "CODEX_SUBSCRIPTION",
)
# Use a clearly synthetic local token that cannot be mistaken for a provider secret.
AUTH_TOKEN = os.environ.get("CURSOR_BRIDGE_AUTH_TOKEN", "local-bridge-token")
TIMEOUT_SECONDS = int(os.environ.get("CURSOR_BRIDGE_TIMEOUT_SECONDS", "240"))
WORKDIR = Path(os.environ.get("CURSOR_BRIDGE_WORKDIR", os.getcwd()))
LOG_PATH = Path(
    os.environ.get(
        "CURSOR_BRIDGE_LOG",
        str(Path.home() / "Library" / "Logs" / "Viventium" / "cursor-claude-bridge.jsonl"),
    )
)

BRIDGE_SYSTEM_PROMPT = (
    "You are serving as the language model behind an OpenAI-compatible bridge for Cursor IDE. "
    "Return only the assistant's final answer text. "
    "Treat the provided conversation and context as the full task. "
    "Do not execute shell commands, edit files, or perform extra tool work inside this bridge. "
    "Do not mention bridge internals, tool protocols, Claude Code, or Codex unless the user directly asks."
)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_log(entry: dict[str, Any]) -> None:
    _ensure_parent(LOG_PATH)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {"_raw": raw.decode("utf-8", errors="replace")}


def _extract_bearer_token(headers: Any) -> str:
    auth_header = headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return ""
    return auth_header.split(" ", 1)[1].strip()


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
                continue

            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type") or "").strip()
            if item_type in {"text", "input_text", "output_text"}:
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
                continue

            if item_type in {"message", "input_message"}:
                role = str(item.get("role") or "user").strip() or "user"
                inner_text = _content_to_text(item.get("content"))
                if inner_text:
                    parts.append(f"{role.upper()}:\n{inner_text}")
                continue

            # Non-text payloads are intentionally skipped.

        return "\n\n".join(part for part in parts if part).strip()
    if isinstance(content, dict):
        return _content_to_text([content])
    return str(content).strip()


def _normalize_chat_messages(messages: list[dict[str, Any]] | None) -> tuple[str, str]:
    system_parts: list[str] = []
    convo_parts: list[str] = []

    for message in messages or []:
        role = str(message.get("role") or "user").strip() or "user"
        text = _content_to_text(message.get("content"))
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
        else:
            convo_parts.append(f"{role.upper()}:\n{text}")

    if convo_parts:
        convo_parts.append("ASSISTANT:")

    return "\n\n".join(system_parts).strip(), "\n\n".join(convo_parts).strip()


def _normalize_responses_input(body: dict[str, Any]) -> tuple[str, str]:
    system_parts: list[str] = []
    instructions = _content_to_text(body.get("instructions"))
    if instructions:
        system_parts.append(instructions)

    input_value = body.get("input")
    if isinstance(input_value, str):
        return "\n\n".join(system_parts).strip(), f"USER:\n{input_value.strip()}\n\nASSISTANT:"

    if not isinstance(input_value, list):
        return "\n\n".join(system_parts).strip(), "USER:\n\nASSISTANT:"

    convo_parts: list[str] = []
    for item in input_value:
        if not isinstance(item, dict):
            text = _content_to_text(item)
            if text:
                convo_parts.append(f"USER:\n{text}")
            continue

        item_type = str(item.get("type") or "").strip()
        if item_type in {"message", "input_message"}:
            role = str(item.get("role") or "user").strip() or "user"
            text = _content_to_text(item.get("content"))
            if text:
                convo_parts.append(f"{role.upper()}:\n{text}")
            continue

        if item_type in {"text", "input_text"}:
            text = _content_to_text(item)
            if text:
                convo_parts.append(f"USER:\n{text}")

    if convo_parts:
        convo_parts.append("ASSISTANT:")

    return "\n\n".join(system_parts).strip(), "\n\n".join(convo_parts).strip()


def _combine_system_prompt(extra_system: str) -> str:
    parts = [BRIDGE_SYSTEM_PROMPT]
    if extra_system.strip():
        parts.append(extra_system.strip())
    return "\n\n".join(parts)


def _compose_codex_prompt(prompt: str, *, system_prompt: str) -> str:
    parts: list[str] = []
    if system_prompt.strip():
        parts.append(f"SYSTEM:\n{system_prompt.strip()}")
    if prompt.strip():
        parts.append(prompt.strip())
    return "\n\n".join(parts).strip() or "USER:\n\nASSISTANT:"


def _first_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return ""


def _parse_codex_exec_output(stdout_text: str) -> tuple[str, dict[str, Any]]:
    final_text = ""
    usage: dict[str, Any] = {}

    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "turn.completed":
            usage = event.get("usage") or usage
            continue

        if event.get("type") != "item.completed":
            continue

        item = event.get("item") or {}
        if item.get("type") != "agent_message":
            continue
        text = _first_string(item.get("text"), event.get("text"), event.get("content")).strip()
        if text:
            final_text = text

    if not final_text:
        raise RuntimeError("codex returned an empty result")

    return final_text, {"usage": usage}


def _select_backend_for_model(model: str) -> str:
    normalized = (model or "").strip()
    if not normalized:
        return "claude"

    if normalized in {CLAUDE_OPENAI_MODEL_ID, CLAUDE_MODEL} or normalized.startswith("claude-"):
        return "claude"

    codex_aliases = {
        CODEX_OPENAI_MODEL_ID,
        "CODEX_SUBSCRIPTION",
        "SUBSCRIPTION GPT 5.4 XHIGH",
        CODEX_MODEL,
        f"{CODEX_MODEL}-{CODEX_REASONING_EFFORT}",
        f"{CODEX_MODEL}-{CODEX_REASONING_EFFORT}-thinking",
    }
    if normalized in codex_aliases or normalized.startswith("gpt-5.4"):
        return "codex"

    raise RuntimeError(
        f"Unsupported model '{normalized}'. Expected one of "
        f"{CLAUDE_OPENAI_MODEL_ID!r}, {CODEX_OPENAI_MODEL_ID!r}, {CLAUDE_MODEL!r}, or {CODEX_MODEL!r}."
    )


def _run_claude(prompt: str, *, system_prompt: str) -> tuple[str, dict[str, Any]]:
    cmd = [
        "claude",
        "-p",
        "--model",
        CLAUDE_MODEL,
        "--effort",
        CLAUDE_EFFORT,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--tools=",
        "--system-prompt",
        system_prompt,
        prompt,
    ]

    env = dict(os.environ)
    # Prefer the first-party Claude subscription auth already present on this Mac.
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)

    completed = subprocess.run(
        cmd,
        cwd=str(WORKDIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(stderr or f"claude exited with code {completed.returncode}")

    payload = json.loads(completed.stdout)
    result_text = str(payload.get("result") or "").strip()
    if not result_text:
        raise RuntimeError("claude returned an empty result")
    return result_text, payload


def _run_codex(prompt: str, *, system_prompt: str) -> tuple[str, dict[str, Any]]:
    cmd = [
        "codex",
        "exec",
        "--json",
        "-m",
        CODEX_MODEL,
        "-c",
        f'model_reasoning_effort="{CODEX_REASONING_EFFORT}"',
        "-c",
        "mcp_servers={}",
        "--skip-git-repo-check",
        "-C",
        str(WORKDIR),
        _compose_codex_prompt(prompt, system_prompt=system_prompt),
    ]

    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_BASE_URL", None)
    env.pop("OPENAI_ORG_ID", None)

    completed = subprocess.run(
        cmd,
        cwd=str(WORKDIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        raise RuntimeError(stderr or stdout or f"codex exited with code {completed.returncode}")

    return _parse_codex_exec_output(completed.stdout)


def _run_model(model: str, prompt: str, *, system_prompt: str) -> tuple[str, dict[str, Any]]:
    backend = _select_backend_for_model(model)
    if backend == "claude":
        return _run_claude(prompt, system_prompt=system_prompt)
    return _run_codex(prompt, system_prompt=system_prompt)


def _chat_usage(payload: dict[str, Any]) -> dict[str, int]:
    usage = payload.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _chat_completion_payload(model: str, text: str, usage_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": _chat_usage(usage_payload),
    }


def _responses_payload(model: str, text: str, usage_payload: dict[str, Any]) -> dict[str, Any]:
    usage = _chat_usage(usage_payload)
    return {
        "id": f"resp-{uuid.uuid4()}",
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "status": "completed",
        "output": [
            {
                "id": f"msg-{uuid.uuid4()}",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": usage["prompt_tokens"],
            "output_tokens": usage["completion_tokens"],
            "total_tokens": usage["total_tokens"],
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "CursorSubscriptionBridge/0.2"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, events: list[dict[str, Any]]) -> None:
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

    def _log(self, *, body: dict[str, Any] | None = None, status: int | None = None, note: str | None = None) -> None:
        entry: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "method": self.command,
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
        }
        if body is not None:
            entry["body"] = body
        if status is not None:
            entry["status"] = status
        if note:
            entry["note"] = note
        _write_log(entry)

    def _require_auth(self) -> bool:
        if not AUTH_TOKEN:
            return True
        if _extract_bearer_token(self.headers) == AUTH_TOKEN:
            return True
        self._log(status=401, note="auth_failed")
        self._send_json(
            401,
            {
                "error": {
                    "message": "Invalid or missing bearer token.",
                    "type": "invalid_request_error",
                }
            },
        )
        return False

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
            self._send_json(
                200,
                {
                    "ok": True,
                    "claude_openai_model_id": CLAUDE_OPENAI_MODEL_ID,
                    "codex_openai_model_id": CODEX_OPENAI_MODEL_ID,
                    "claude_model": CLAUDE_MODEL,
                    "claude_effort": CLAUDE_EFFORT,
                    "codex_model": CODEX_MODEL,
                    "codex_reasoning_effort": CODEX_REASONING_EFFORT,
                    "workdir": str(WORKDIR),
                },
            )
            return
        if parsed.path in ("/models", "/v1/models"):
            now = int(time.time())
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": CLAUDE_OPENAI_MODEL_ID,
                            "object": "model",
                            "created": now,
                            "owned_by": "local-subscription-bridge",
                        },
                        {
                            "id": CODEX_OPENAI_MODEL_ID,
                            "object": "model",
                            "created": now,
                            "owned_by": "local-subscription-bridge",
                        },
                        {
                            "id": CLAUDE_MODEL,
                            "object": "model",
                            "created": now,
                            "owned_by": "local-claude-bridge",
                        },
                        {
                            "id": CODEX_MODEL,
                            "object": "model",
                            "created": now,
                            "owned_by": "local-codex-bridge",
                        },
                    ],
                },
            )
            return
        self._send_json(404, {"error": f"Unhandled GET {parsed.path}"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = _read_json(self)
        self._log(body=body)

        if not self._require_auth():
            return

        try:
            if parsed.path in ("/chat/completions", "/v1/chat/completions"):
                self._handle_chat_completions(body)
                return
            if parsed.path in ("/responses", "/v1/responses"):
                self._handle_responses(body)
                return
            self._send_json(404, {"error": f"Unhandled POST {parsed.path}"})
        except subprocess.TimeoutExpired:
            self._send_json(
                504,
                {
                    "error": {
                        "message": f"Subscription bridge timed out after {TIMEOUT_SECONDS}s.",
                        "type": "bridge_timeout",
                    }
                },
            )
        except Exception as exc:
            self._send_json(
                502,
                {
                    "error": {
                        "message": str(exc),
                        "type": "bridge_error",
                    }
                },
            )

    def _handle_chat_completions(self, body: dict[str, Any]) -> None:
        model = str(body.get("model") or CLAUDE_OPENAI_MODEL_ID)
        system_text, prompt = _normalize_chat_messages(body.get("messages"))
        if not prompt:
            prompt = "USER:\n\nASSISTANT:"

        text, usage_payload = _run_model(model, prompt, system_prompt=_combine_system_prompt(system_text))

        if body.get("stream"):
            created = int(time.time())
            stream_id = f"chatcmpl-{uuid.uuid4()}"
            self._send_sse(
                [
                    {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": text},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    },
                ]
            )
            return

        self._send_json(200, _chat_completion_payload(model, text, usage_payload))

    def _handle_responses(self, body: dict[str, Any]) -> None:
        model = str(body.get("model") or CLAUDE_OPENAI_MODEL_ID)
        system_text, prompt = _normalize_responses_input(body)
        text, usage_payload = _run_model(model, prompt, system_prompt=_combine_system_prompt(system_text))

        if body.get("stream"):
            response_payload = _responses_payload(model, text, usage_payload)
            self._send_sse(
                [
                    {
                        "type": "response.created",
                        "response": {
                            "id": response_payload["id"],
                            "object": "response",
                            "created_at": response_payload["created_at"],
                            "model": model,
                            "status": "in_progress",
                        },
                    },
                    {
                        "type": "response.output_text.delta",
                        "delta": text,
                    },
                    {
                        "type": "response.completed",
                        "response": response_payload,
                    },
                ]
            )
            return

        self._send_json(200, _responses_payload(model, text, usage_payload))

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))


def main() -> int:
    print(f"Cursor subscription bridge listening on http://{HOST}:{PORT}", flush=True)
    print(f"Claude OpenAI model id: {CLAUDE_OPENAI_MODEL_ID}", flush=True)
    print(f"Codex OpenAI model id: {CODEX_OPENAI_MODEL_ID}", flush=True)
    print(f"Claude model: {CLAUDE_MODEL}", flush=True)
    print(f"Claude effort: {CLAUDE_EFFORT}", flush=True)
    print(f"Codex model: {CODEX_MODEL}", flush=True)
    print(f"Codex reasoning effort: {CODEX_REASONING_EFFORT}", flush=True)
    print(f"Working directory: {WORKDIR}", flush=True)
    print(f"Request log: {LOG_PATH}", flush=True)
    if AUTH_TOKEN:
        print("Bearer token auth: enabled", flush=True)
    else:
        print("Bearer token auth: disabled", flush=True)

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
