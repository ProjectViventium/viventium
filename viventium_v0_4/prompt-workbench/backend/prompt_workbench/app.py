from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, cognitive_integrity, drafts, evals, frames, prompt_service, scheduled_prompts, sync_engine
from .paths import WORKBENCH_ROOT, resolve_repo_path
from .runtime_env import load_viventium_runtime_env


load_viventium_runtime_env()
logger = logging.getLogger("prompt_workbench.nightly_seed")
BUILD_RECEIPT_NAME = ".viventium-build-receipt.json"
_IGNORED_INPUT_DIRECTORIES = frozenset(
    {"node_modules", "dist", "__pycache__", ".pytest_cache", ".vite", "tests", "__tests__"}
)
_FRONTEND_ROOT_FILES = (
    "index.html",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "vite.config.ts",
)


def _backend_source_hash() -> str | None:
    digest = hashlib.sha256()
    try:
        for source in sorted((WORKBENCH_ROOT / "backend" / "prompt_workbench").glob("*.py")):
            digest.update(source.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source.read_bytes())
    except OSError:
        return None
    return digest.hexdigest()[:16]


_BACKEND_BOOT_SOURCE_HASH = _backend_source_hash()


def _is_test_source(path: Path) -> bool:
    return any(marker in path.name for marker in (".test.", ".spec."))


def _bounded_frontend_files() -> list[Path]:
    candidates = [WORKBENCH_ROOT / relative for relative in _FRONTEND_ROOT_FILES]
    for search_root in (WORKBENCH_ROOT / "src", WORKBENCH_ROOT / "public"):
        if not search_root.is_dir():
            continue
        candidates.extend(
            child
            for child in search_root.rglob("*")
            if child.is_file()
            and not child.is_symlink()
            and not _IGNORED_INPUT_DIRECTORIES.intersection(
                child.relative_to(WORKBENCH_ROOT).parts
            )
            and not _is_test_source(child)
        )
    return sorted(
        {
            candidate
            for candidate in candidates
            if candidate.is_file() and not candidate.is_symlink()
        },
        key=lambda candidate: candidate.relative_to(WORKBENCH_ROOT).as_posix(),
    )


def _content_identity(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for candidate in files:
        relative = candidate.relative_to(WORKBENCH_ROOT).as_posix().encode("utf-8")
        body = candidate.read_bytes()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(len(body)).encode("ascii"))
        digest.update(b"\0")
        digest.update(body)
        digest.update(b"\0")
    return digest.hexdigest()


def _frontend_input_identity() -> str:
    return _content_identity(_bounded_frontend_files())


def _built_asset_identity() -> tuple[str, int]:
    dist = WORKBENCH_ROOT / "dist"
    files = sorted(
        (
            child
            for child in dist.rglob("*")
            if child.is_file()
            and not child.is_symlink()
            and child != dist / BUILD_RECEIPT_NAME
        ),
        key=lambda candidate: candidate.relative_to(WORKBENCH_ROOT).as_posix(),
    )
    return _content_identity(files), len(files)


def _frontend_build_status() -> dict[str, Any]:
    receipt_path = WORKBENCH_ROOT / "dist" / BUILD_RECEIPT_NAME
    receipt: dict[str, Any] = {}
    if receipt_path.is_file() and not receipt_path.is_symlink():
        try:
            parsed = json.loads(receipt_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                receipt = parsed
        except (json.JSONDecodeError, OSError, UnicodeError):
            pass
    try:
        current_input_hash = _frontend_input_identity()
        current_asset_hash, current_file_count = _built_asset_identity()
    except OSError:
        current_input_hash = ""
        current_asset_hash = ""
        current_file_count = 0
    receipt_input_hash = receipt.get("frontendInputHash")
    receipt_asset_hash = receipt.get("builtAssetHash")
    receipt_file_count = receipt.get("builtFileCount")
    schema_version = receipt.get("schemaVersion")
    hashes_valid = all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in (
            receipt_input_hash,
            receipt_asset_hash,
            current_input_hash,
            current_asset_hash,
        )
    )
    counts_valid = (
        isinstance(receipt_file_count, int)
        and not isinstance(receipt_file_count, bool)
        and receipt_file_count > 0
        and current_file_count > 0
    )
    source_current = hashes_valid and receipt_input_hash == current_input_hash
    assets_current = (
        hashes_valid
        and counts_valid
        and receipt_asset_hash == current_asset_hash
        and receipt_file_count == current_file_count
    )
    receipt_available = receipt_path.is_file() and not receipt_path.is_symlink()
    return {
        "receiptAvailable": receipt_available,
        "schemaVersion": schema_version if isinstance(schema_version, int) else None,
        "receiptFrontendInputHash": receipt_input_hash,
        "currentFrontendInputHash": current_input_hash or None,
        "receiptBuiltAssetHash": receipt_asset_hash,
        "currentBuiltAssetHash": current_asset_hash or None,
        "receiptBuiltFileCount": receipt_file_count,
        "currentBuiltFileCount": current_file_count,
        "sourceCurrent": source_current,
        "assetsCurrent": assets_current,
        "receiptValid": bool(
            receipt_available
            and schema_version == 1
            and source_current
            and assets_current
        ),
    }


def _env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _seed_nightly_enabled() -> bool:
    raw = (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ENABLED") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _seed_nightly_executor() -> str:
    value = (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_EXECUTOR") or "glasshive_host").strip()
    return value if value in {"glasshive_host", "viventium_agent"} else "glasshive_host"


def _seed_health_context_enabled() -> bool:
    return _env_flag("VIVENTIUM_PROMPT_WORKBENCH_SEED_HEALTH_CONTEXT_ENABLED")


def _seed_health_context_executor() -> str:
    value = (
        os.getenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_HEALTH_CONTEXT_EXECUTOR")
        or "glasshive_host"
    ).strip()
    return value if value in {"glasshive_host", "viventium_agent"} else "glasshive_host"


def _seed_builtin_scheduled_prompts() -> bool:
    seed_nightly = _seed_nightly_enabled()
    seed_health_context = _seed_health_context_enabled()
    if not seed_nightly and not seed_health_context:
        return True
    user_id = (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID") or "").strip()
    email = (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL") or "").strip()
    if not user_id or user_id in {"local-admin", "test-admin"}:
        admin_user = auth._select_local_admin_user(auth._query_local_admin_users())
        if admin_user:
            user_id = admin_user["_id"]
            email = admin_user.get("email", "")
    if not user_id or user_id in {"local-admin", "test-admin"}:
        return False
    try:
        if seed_nightly:
            scheduled_prompts.seed_nightly_prompt(
                user_id=user_id,
                email=email or None,
                active=_env_flag("VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE"),
                executor=_seed_nightly_executor(),
            )
        if seed_health_context:
            scheduled_prompts.seed_health_context_prompt(
                user_id=user_id,
                email=email or None,
                active=_env_flag("VIVENTIUM_PROMPT_WORKBENCH_SEED_HEALTH_CONTEXT_ACTIVE"),
                executor=_seed_health_context_executor(),
            )
    except Exception as exc:
        # Built-in private prompt seeding is best-effort; admin APIs still surface failures when edited.
        logger.warning("Built-in nightly reflection seed failed: %s", exc.__class__.__name__)
        return False
    return True


def _seed_when_first_admin_exists() -> None:
    try:
        max_attempts = int((os.getenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_MAX_ATTEMPTS") or "480").strip())
    except ValueError:
        max_attempts = 480
    try:
        interval_seconds = float((os.getenv("VIVENTIUM_PROMPT_WORKBENCH_SEED_POLL_SECONDS") or "15").strip())
    except ValueError:
        interval_seconds = 15.0
    max_attempts = max(1, max_attempts)
    interval_seconds = max(0.2, interval_seconds)
    for _ in range(max_attempts):
        time.sleep(interval_seconds)
        if _seed_builtin_scheduled_prompts():
            return
    logger.warning(
        "Built-in nightly reflection seed could not resolve a unique local admin before the retry window closed."
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    seeded = _seed_builtin_scheduled_prompts()
    if not seeded and (_seed_nightly_enabled() or _seed_health_context_enabled()):
        threading.Thread(
            target=_seed_when_first_admin_exists,
            name="prompt-workbench-nightly-seed",
            daemon=True,
        ).start()
    yield


app = FastAPI(title="Viventium Prompt Workbench", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5179",
        "http://localhost:5179",
        "http://127.0.0.1:8781",
        "http://localhost:8781",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _allowed_host_values() -> set[str]:
    configured = {
        host.strip().lower()
        for host in (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ALLOWED_HOSTS") or "").split(",")
        if host.strip()
    }
    return configured | {"127.0.0.1", "localhost", "::1", "[::1]", "testserver"}


def _host_name(host_header: str) -> str:
    value = (host_header or "").strip().lower()
    if value.startswith("[::1]"):
        return "[::1]"
    return value.rsplit(":", 1)[0] if ":" in value else value


@app.middleware("http")
async def enforce_loopback_host_header(request, call_next):
    host = _host_name(request.headers.get("host", ""))
    if host and host not in _allowed_host_values():
        return PlainTextResponse("Prompt Workbench only accepts loopback hostnames.", status_code=400)
    if "workbench_token" in request.query_params:
        if request.url.path.startswith("/api/"):
            return PlainTextResponse("URL credentials are not supported.", status_code=400)
        safe_query = urlencode(
            [
                (key, value)
                for key, value in request.query_params.multi_items()
                if key != "workbench_token"
            ]
        )
        safe_location = request.url.path + (f"?{safe_query}" if safe_query else "")
        return RedirectResponse(safe_location, status_code=303)
    return await call_next(request)


def _auth_user_id(context: auth.AuthContext) -> str:
    return context.user_id or "local-admin"


def _is_index_request(path: str) -> bool:
    return path in {"", "/", "/index.html"}


@app.middleware("http")
async def set_local_static_cache_policy(request, call_next):
    path = request.url.path
    if _is_index_request(path):
        request.scope["headers"] = tuple(
            (key, value)
            for key, value in request.scope.get("headers", ())
            if key.lower() not in {b"if-none-match", b"if-modified-since"}
        )
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "no-referrer"
    if _is_index_request(path):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    elif path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


class RenderRequest(BaseModel):
    promptId: str
    variables: dict[str, Any] = Field(default_factory=dict)


class DraftRequest(BaseModel):
    targetPath: str
    newText: str
    kind: str = "source-edit"
    reason: str = ""


class ApplyDraftRequest(BaseModel):
    idempotencyToken: str


class PullRequest(BaseModel):
    env: str = "local"


class ImportLiveRequest(BaseModel):
    agentId: str
    promptId: str | None = None


class PushReviewedRequest(BaseModel):
    reviewToken: str
    env: str = "local"


class EvalRunRequest(BaseModel):
    maxCases: int = 1
    live: bool = False
    family: str | None = None
    surface: str | None = None
    promptId: str | None = None
    caseIds: list[str] = Field(default_factory=list, max_length=100)


class EvalCaseDraftRequest(BaseModel):
    familyId: str
    caseId: str
    updatedCase: dict[str, Any]
    create: bool = False
    reason: str = ""


class VariableRenderRequest(BaseModel):
    promptText: str
    userId: str | None = None
    email: str | None = None


class ScheduledPromptRequest(BaseModel):
    title: str = "Scheduled prompt"
    promptText: str
    schedule: dict[str, Any] = Field(default_factory=lambda: {"type": "daily", "time": "03:00", "timezone": "UTC"})
    active: bool = False
    memoryWriteMode: str = "off"
    sourcePromptId: str | None = None
    templateId: str | None = None
    executor: str | None = None
    channel: str | list[str] | None = None
    conversationPolicy: str | None = None
    glasshiveWorkerStrategy: str | None = None


class ScheduledPromptPatchRequest(BaseModel):
    title: str | None = None
    promptText: str | None = None
    sourcePromptId: str | None = None
    schedule: dict[str, Any] | None = None
    active: bool | None = None
    memoryWriteMode: str | None = None
    executor: str | None = None
    channel: str | list[str] | None = None
    conversationPolicy: str | None = None
    glasshiveWorkerStrategy: str | None = None


class ScheduledPromptManualRunRequest(BaseModel):
    confirmUserLevelDelivery: bool = False


class ScheduledPromptMemoryProposalApplyRequest(BaseModel):
    apply: bool = False


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/cognitive-integrity")
def api_cognitive_integrity(
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    return cognitive_integrity.cognitive_integrity_report(user_id=_auth_user_id(context))


@app.get("/api/build-version")
def build_version() -> dict[str, Any]:
    current_backend_hash = _backend_source_hash()
    backend = {
        "loadedSourceHash": _BACKEND_BOOT_SOURCE_HASH,
        "currentSourceHash": current_backend_hash,
        "sourceCurrent": bool(_BACKEND_BOOT_SOURCE_HASH and _BACKEND_BOOT_SOURCE_HASH == current_backend_hash),
    }
    index_path = WORKBENCH_ROOT / "dist" / "index.html"
    frontend = _frontend_build_status()
    try:
        index_html = index_path.read_text(encoding="utf-8")
    except OSError:
        return {
            "available": False,
            "indexHash": None,
            "entryAssets": [],
            "backend": backend,
            "frontend": frontend,
        }
    entry_assets = sorted(set(re.findall(r"/assets/[^\"']+", index_html)))
    return {
        "available": True,
        "indexHash": hashlib.sha256(index_html.encode("utf-8")).hexdigest()[:16],
        "entryAssets": entry_assets,
        "backend": backend,
        "frontend": frontend,
    }


@app.get("/api/auth/status")
def auth_status(request: Request) -> dict[str, Any]:
    return auth.get_auth_context(request).payload()


@app.get("/api/variables")
def variables(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return scheduled_prompts.variable_registry()


@app.get("/api/scheduled-prompts/templates/nightly-subconscious")
def nightly_scheduled_prompt_template(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return scheduled_prompts.nightly_prompt_template()


@app.get("/api/scheduled-prompts/templates/health-context")
def health_context_scheduled_prompt_template(
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    return scheduled_prompts.health_context_prompt_template()


@app.post("/api/variables/render")
def render_variables(
    request: VariableRenderRequest,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    user_id = _auth_user_id(context)
    try:
        return scheduled_prompts.render_variables(request.promptText, user_id=user_id, email=context.email)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/scheduled-prompts")
def api_scheduled_prompts(
    context: auth.AuthContext = Depends(auth.require_admin),
    readOnly: bool = False,
) -> dict[str, Any]:
    return scheduled_prompts.list_scheduled_prompts(
        user_id=_auth_user_id(context),
        read_only=readOnly,
    )


@app.post("/api/scheduled-prompts")
def create_scheduled_prompt(
    request: ScheduledPromptRequest,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    user_id = _auth_user_id(context)
    try:
        return scheduled_prompts.create_scheduled_prompt(request.model_dump(), user_id=user_id, email=context.email)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/scheduled-prompts/{scheduled_prompt_id}")
def update_scheduled_prompt(
    scheduled_prompt_id: str,
    request: ScheduledPromptPatchRequest,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.update_scheduled_prompt(
            scheduled_prompt_id,
            {key: value for key, value in request.model_dump().items() if value is not None},
            user_id=_auth_user_id(context),
            email=context.email,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scheduled prompt: {scheduled_prompt_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/scheduled-prompts/{scheduled_prompt_id}")
def delete_scheduled_prompt(
    scheduled_prompt_id: str,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.delete_scheduled_prompt(scheduled_prompt_id, user_id=_auth_user_id(context))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/scheduled-prompts/{scheduled_prompt_id}/manual-runs")
def manual_run_scheduled_prompt(
    scheduled_prompt_id: str,
    request: ScheduledPromptManualRunRequest | None = None,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.manual_run(
            scheduled_prompt_id,
            user_id=_auth_user_id(context),
            confirm_user_level_delivery=bool(request and request.confirmUserLevelDelivery),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scheduled prompt: {scheduled_prompt_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/scheduled-prompts/{scheduled_prompt_id}/runs")
def scheduled_prompt_runs(
    scheduled_prompt_id: str,
    context: auth.AuthContext = Depends(auth.require_admin),
    readOnly: bool = False,
) -> dict[str, Any]:
    try:
        return scheduled_prompts.list_runs(
            scheduled_prompt_id,
            user_id=_auth_user_id(context),
            read_only=readOnly,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scheduled prompt: {scheduled_prompt_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/api/scheduled-prompts/{scheduled_prompt_id}/memory-proposals")
def scheduled_prompt_memory_proposals(
    scheduled_prompt_id: str,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.list_memory_proposals(scheduled_prompt_id, user_id=_auth_user_id(context))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scheduled prompt: {scheduled_prompt_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/scheduled-prompts/{scheduled_prompt_id}/periphery-artifacts")
def scheduled_prompt_periphery_artifacts(
    scheduled_prompt_id: str,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.list_periphery_artifacts(scheduled_prompt_id, user_id=_auth_user_id(context))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scheduled prompt: {scheduled_prompt_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/scheduled-prompts/{scheduled_prompt_id}/periphery-snapshot")
def scheduled_prompt_periphery_snapshot(
    scheduled_prompt_id: str,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.periphery_snapshot_status(
            scheduled_prompt_id,
            user_id=_auth_user_id(context),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scheduled prompt: {scheduled_prompt_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/scheduled-prompts/{scheduled_prompt_id}/periphery-snapshot")
def refresh_scheduled_prompt_periphery_snapshot(
    scheduled_prompt_id: str,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.refresh_periphery_snapshot(
            scheduled_prompt_id,
            user_id=_auth_user_id(context),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scheduled prompt: {scheduled_prompt_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/scheduled-prompts/{scheduled_prompt_id}/periphery-artifacts/{artifact_id}")
def scheduled_prompt_periphery_artifact(
    scheduled_prompt_id: str,
    artifact_id: str,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.read_periphery_artifact(
            scheduled_prompt_id,
            artifact_id,
            user_id=_auth_user_id(context),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown periphery artifact") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/scheduled-prompts/{scheduled_prompt_id}/memory-proposals/{proposal_id}/apply")
def scheduled_prompt_memory_proposal_apply(
    scheduled_prompt_id: str,
    proposal_id: str,
    request: ScheduledPromptMemoryProposalApplyRequest,
    context: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return scheduled_prompts.apply_memory_proposal(
            scheduled_prompt_id,
            proposal_id,
            user_id=_auth_user_id(context),
            apply=request.apply,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown memory proposal: {proposal_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/prompts")
def prompts(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return {
        "prompts": prompt_service.list_prompts(),
        "flow": prompt_service.flow_graph(),
        "evalBank": evals.eval_bank_summary(),
    }


@app.get("/api/prompts/{prompt_id}")
def prompt_detail(
    prompt_id: str,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return prompt_service.get_prompt(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown prompt: {prompt_id}") from exc


@app.get("/api/prompts/{prompt_id}/workbench-context")
def prompt_workbench_context(
    prompt_id: str,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return prompt_service.workbench_context(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown prompt: {prompt_id}") from exc


@app.get("/api/prompts/{prompt_id}/revisions/{revision}")
def prompt_revision(
    prompt_id: str,
    revision: str,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return prompt_service.get_prompt_revision(prompt_id, revision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/prompts/render")
def render_prompt(
    request: RenderRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return prompt_service.render_prompt_payload(request.promptId, request.variables)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sync/status")
def sync_status(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return sync_engine.get_status()


@app.post("/api/sync/pull-live")
def sync_pull_live(
    request: PullRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    return sync_engine.pull_live(env=request.env)


@app.post("/api/sync/import-live-draft")
def sync_import_live(
    request: ImportLiveRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return sync_engine.import_live_draft(agent_id=request.agentId, prompt_id=request.promptId)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sync/push-live-dry-run")
def sync_push_live_dry_run(
    request: PullRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return sync_engine.push_live_dry_run(env=request.env)
    except drafts.ActiveDraftBlockError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "blockingDrafts": exc.blocking_drafts},
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sync/push-live-reviewed")
def sync_push_live_reviewed(
    request: PushReviewedRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return sync_engine.push_live_reviewed(review_token=request.reviewToken, env=request.env)
    except drafts.ActiveDraftBlockError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "blockingDrafts": exc.blocking_drafts},
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/drafts")
def create_draft(
    request: DraftRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return drafts.create_file_draft(
            target_path=resolve_repo_path(request.targetPath),
            new_text=request.newText,
            kind=request.kind,
            reason=request.reason,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/drafts")
def list_drafts(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return {"drafts": drafts.list_drafts()}


@app.get("/api/drafts/{draft_id}")
def get_draft(
    draft_id: str,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return drafts.get_draft(draft_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/drafts/{draft_id}/apply")
def apply_draft(
    draft_id: str,
    request: ApplyDraftRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        draft = drafts.get_draft(draft_id)
        result = drafts.apply_draft(draft_id, request.idempotencyToken)
        if draft.get("kind") == "live-import":
            sync_engine.advance_matching_reconciled_rows()
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/drafts/{draft_id}")
def discard_draft(
    draft_id: str,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return drafts.discard_draft(draft_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/evals")
def eval_bank(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return evals.eval_bank_summary()


@app.get("/api/evals/execution-route")
def configured_eval_execution_route(
    _: auth.AuthContext = Depends(auth.require_admin),
    family: str | None = None,
) -> dict[str, Any]:
    route = (
        evals._configured_family_execution_route(family)
        if family is not None
        else evals._configured_execution_route(None)
    )
    if route is None:
        raise HTTPException(status_code=503, detail="configured_execution_route_unavailable")
    return route


@app.post("/api/evals/run")
def eval_run(
    request: EvalRunRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return evals.run_exact_model_eval(
            max_cases=max(1, request.maxCases),
            live=request.live,
            family=request.family,
            surface=request.surface,
            prompt_id=request.promptId,
            case_ids=request.caseIds,
        )
    except drafts.ActiveDraftBlockError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "blockingDrafts": exc.blocking_drafts},
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/evals/case-draft")
def eval_case_draft(
    request: EvalCaseDraftRequest,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return evals.create_eval_case_draft(
            family_id=request.familyId,
            case_id=request.caseId,
            updated_case=request.updatedCase,
            create=request.create,
            reason=request.reason,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/evals/runs")
def eval_runs(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return {"runs": evals.list_eval_runs()}


@app.get("/api/evals/runs/{run_id}")
def eval_run_detail(
    run_id: str,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    try:
        return evals.get_eval_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/evals/promptfoo/{prompt_id}")
def eval_promptfoo(
    prompt_id: str,
    _: auth.AuthContext = Depends(auth.require_admin),
) -> dict[str, Any]:
    return evals.promptfoo_config(prompt_id)


@app.get("/api/frames")
def recent_frames(_: auth.AuthContext = Depends(auth.require_admin)) -> dict[str, Any]:
    return frames.recent_frame_snapshot()


dist = WORKBENCH_ROOT / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="static")
