from __future__ import annotations

import asyncio
import os
import re
import shlex
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response


UI_UPSTREAM = os.environ.get("GLASSHIVE_QA_PROXY_UPSTREAM", "http://127.0.0.1:8879").rstrip("/")
RUNTIME_UPSTREAM = os.environ.get("GLASSHIVE_QA_RUNTIME_UPSTREAM", "http://127.0.0.1:8876").rstrip("/")
TENANT = os.environ.get("GLASSHIVE_QA_PROXY_TENANT_ID", "tenant_public_safe")
USER_ID = os.environ.get("GLASSHIVE_QA_PROXY_USER_ID", "standardqa-browser-user")
USER_EMAIL = os.environ.get("GLASSHIVE_QA_PROXY_USER_EMAIL", "standardqa@example.invalid")
USER_ROLE = os.environ.get("GLASSHIVE_QA_PROXY_USER_ROLE", "member")
HOST = os.environ.get("GLASSHIVE_QA_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("GLASSHIVE_QA_PROXY_PORT", "8874"))
SAFE_NOVNC_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
NOVNC_VIEW_CACHE_TTL_SECONDS = 15.0
NOVNC_ASSET_CACHE_TTL_SECONDS = 10 * 60.0
_NOVNC_VIEW_CACHE: dict[str, tuple[float, str]] = {}
_NOVNC_ASSET_CACHE: dict[str, tuple[float, int, bytes, str]] = {}
_NOVNC_ASSET_CLIENT: httpx.AsyncClient | None = None

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _load_local_env() -> None:
    for env_path in (
        Path.home() / "Library/Application Support/Viventium/runtime/runtime.env",
        Path.home() / "Library/Application Support/Viventium/runtime/runtime.local.env",
    ):
        try:
            lines = env_path.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            try:
                part = shlex.split(stripped, comments=True, posix=True)[0]
            except Exception:
                continue
            key, _, value = part.partition("=")
            if key and key not in os.environ:
                os.environ[key] = value


def identity_headers(*, role: str | None = None) -> dict[str, str]:
    return {
        "X-Viventium-Tenant-Id": TENANT,
        "X-Viventium-User-Id": USER_ID,
        "X-Viventium-User-Email": USER_EMAIL,
        "X-Viventium-User-Role": role or USER_ROLE,
    }


def runtime_headers(*, role: str = "operator") -> dict[str, str]:
    headers = identity_headers(role=role)
    api_token = os.environ.get("WPR_API_TOKEN", "").strip()
    if api_token:
        headers["X-WPR-Token"] = api_token
    return headers


async def runtime_view_url(worker_id: str) -> str:
    now = time.monotonic()
    cached = _NOVNC_VIEW_CACHE.get(worker_id)
    if cached and cached[0] > now:
        return cached[1]
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{RUNTIME_UPSTREAM}/v1/workers/{worker_id}/live", headers=runtime_headers())
    response.raise_for_status()
    runtime = response.json().get("runtime_details") or {}
    view_url = str(runtime.get("view_url") or "").strip()
    if not view_url:
        raise RuntimeError("No live desktop is available for this worker")
    _NOVNC_VIEW_CACHE[worker_id] = (now + NOVNC_VIEW_CACHE_TTL_SECONDS, view_url)
    return view_url


def safe_novnc_asset_path(rest: str) -> str:
    value = str(rest or "").strip().lstrip("/")
    if (
        not value
        or value.startswith(".")
        or "\\" in value
        or ".." in Path(value).parts
        or not SAFE_NOVNC_PATH_RE.fullmatch(value)
    ):
        raise ValueError("invalid noVNC asset path")
    return value


def novnc_asset_client() -> httpx.AsyncClient:
    global _NOVNC_ASSET_CLIENT
    if _NOVNC_ASSET_CLIENT is None:
        _NOVNC_ASSET_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=3.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            follow_redirects=False,
        )
    return _NOVNC_ASSET_CLIENT


async def fetch_novnc_asset(target: str) -> httpx.Response:
    global _NOVNC_ASSET_CLIENT
    try:
        return await novnc_asset_client().get(target)
    except httpx.HTTPError:
        if _NOVNC_ASSET_CLIENT is not None:
            await _NOVNC_ASSET_CLIENT.aclose()
            _NOVNC_ASSET_CLIENT = None
        return await novnc_asset_client().get(target)


async def relay_websocket(websocket: WebSocket, upstream_url: str, *, headers: dict[str, str] | None = None) -> None:
    await websocket.accept()
    try:
        async with websockets.connect(upstream_url, additional_headers=headers, max_size=None) as upstream_ws:
            async def client_to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        await upstream_ws.close()
                        return
                    if message.get("bytes") is not None:
                        await upstream_ws.send(message["bytes"])
                    elif message.get("text") is not None:
                        await upstream_ws.send(message["text"])

            async def upstream_to_client() -> None:
                async for message in upstream_ws:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(str(message))

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


_load_local_env()
app = FastAPI()


@app.on_event("shutdown")
async def close_novnc_asset_client() -> None:
    global _NOVNC_ASSET_CLIENT
    if _NOVNC_ASSET_CLIENT is not None:
        await _NOVNC_ASSET_CLIENT.aclose()
        _NOVNC_ASSET_CLIENT = None


@app.get("/novnc/{worker_id}/{rest:path}")
async def proxy_novnc_http_asset(worker_id: str, rest: str, request: Request) -> Response:
    if os.environ.get("GLASSHIVE_QA_PROXY_DIRECT_NOVNC_ASSETS", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return await proxy_http(f"novnc/{worker_id}/{rest}", request)
    try:
        asset_path = safe_novnc_asset_path(rest)
    except ValueError:
        return Response(content=b'{"detail":"Invalid noVNC asset path"}', status_code=400, media_type="application/json")
    view_url = await runtime_view_url(worker_id)
    parsed = urlparse(view_url)
    target = f"{parsed.scheme}://{parsed.netloc}/{asset_path}"
    now = time.monotonic()
    cached = _NOVNC_ASSET_CACHE.get(target)
    if cached and cached[0] > now:
        _, status_code, content, content_type = cached
        return Response(
            content=content,
            status_code=status_code,
            media_type=content_type or None,
            headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
        )
    upstream = await fetch_novnc_asset(target)
    content_type = upstream.headers.get("content-type", "")
    if upstream.status_code == 200 and len(upstream.content) <= 2 * 1024 * 1024:
        _NOVNC_ASSET_CACHE[target] = (now + NOVNC_ASSET_CACHE_TTL_SECONDS, upstream.status_code, upstream.content, content_type)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=content_type or None,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_http(path: str, request: Request) -> Response:
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP
        and not key.lower().startswith("x-viventium-")
        and key.lower() not in {"x-wpr-token", "authorization"}
    }
    headers.update(identity_headers())
    target = f"{UI_UPSTREAM}/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
        upstream = await client.request(request.method, target, content=body, headers=headers)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={key: value for key, value in upstream.headers.items() if key.lower() not in HOP_BY_HOP},
    )


@app.websocket("/novnc/{worker_id}/{rest:path}")
async def proxy_novnc_ws(worker_id: str, rest: str, websocket: WebSocket) -> None:
    view_url = await runtime_view_url(worker_id)
    parsed = urlparse(view_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    target_path = "/" + (rest.strip("/") or "websockify")
    target = f"{scheme}://{parsed.netloc}{target_path}"
    if websocket.url.query:
        target = f"{target}?{websocket.url.query}"
    await relay_websocket(websocket, target)


@app.websocket("/{path:path}")
async def proxy_ui_ws(path: str, websocket: WebSocket) -> None:
    upstream_base = UI_UPSTREAM.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    target = f"{upstream_base}/{path}"
    if websocket.url.query:
        target = f"{target}?{websocket.url.query}"
    await relay_websocket(websocket, target, headers=identity_headers())


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
