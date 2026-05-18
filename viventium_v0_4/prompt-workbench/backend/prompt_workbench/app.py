from __future__ import annotations

import hashlib
import re
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import drafts, evals, frames, prompt_service, sync_engine
from .paths import WORKBENCH_ROOT, resolve_repo_path


app = FastAPI(title="Viventium Prompt Workbench", version="0.1.0")
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
    if _is_index_request(path):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
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


class EvalCaseDraftRequest(BaseModel):
    familyId: str
    caseId: str
    updatedCase: dict[str, Any]
    create: bool = False
    reason: str = ""


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/build-version")
def build_version() -> dict[str, Any]:
    index_path = WORKBENCH_ROOT / "dist" / "index.html"
    try:
        index_html = index_path.read_text(encoding="utf-8")
    except OSError:
        return {"available": False, "indexHash": None, "entryAssets": []}
    entry_assets = sorted(set(re.findall(r"/assets/[^\"']+", index_html)))
    return {
        "available": True,
        "indexHash": hashlib.sha256(index_html.encode("utf-8")).hexdigest()[:16],
        "entryAssets": entry_assets,
    }


@app.get("/api/prompts")
def prompts() -> dict[str, Any]:
    return {
        "prompts": prompt_service.list_prompts(),
        "flow": prompt_service.flow_graph(),
        "evalBank": evals.eval_bank_summary(),
    }


@app.get("/api/prompts/{prompt_id}")
def prompt_detail(prompt_id: str) -> dict[str, Any]:
    try:
        return prompt_service.get_prompt(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown prompt: {prompt_id}") from exc


@app.get("/api/prompts/{prompt_id}/workbench-context")
def prompt_workbench_context(prompt_id: str) -> dict[str, Any]:
    try:
        return prompt_service.workbench_context(prompt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown prompt: {prompt_id}") from exc


@app.post("/api/prompts/render")
def render_prompt(request: RenderRequest) -> dict[str, Any]:
    try:
        return prompt_service.render_prompt_payload(request.promptId, request.variables)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sync/status")
def sync_status() -> dict[str, Any]:
    return sync_engine.get_status()


@app.post("/api/sync/pull-live")
def sync_pull_live(request: PullRequest) -> dict[str, Any]:
    return sync_engine.pull_live(env=request.env)


@app.post("/api/sync/import-live-draft")
def sync_import_live(request: ImportLiveRequest) -> dict[str, Any]:
    try:
        return sync_engine.import_live_draft(agent_id=request.agentId, prompt_id=request.promptId)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sync/push-live-dry-run")
def sync_push_live_dry_run(request: PullRequest) -> dict[str, Any]:
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
def sync_push_live_reviewed(request: PushReviewedRequest) -> dict[str, Any]:
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
def create_draft(request: DraftRequest) -> dict[str, Any]:
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
def list_drafts() -> dict[str, Any]:
    return {"drafts": drafts.list_drafts()}


@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: str) -> dict[str, Any]:
    try:
        return drafts.get_draft(draft_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/drafts/{draft_id}/apply")
def apply_draft(draft_id: str, request: ApplyDraftRequest) -> dict[str, Any]:
    try:
        return drafts.apply_draft(draft_id, request.idempotencyToken)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/drafts/{draft_id}")
def discard_draft(draft_id: str) -> dict[str, Any]:
    try:
        return drafts.discard_draft(draft_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/evals")
def eval_bank() -> dict[str, Any]:
    return evals.eval_bank_summary()


@app.post("/api/evals/run")
def eval_run(request: EvalRunRequest) -> dict[str, Any]:
    try:
        return evals.run_exact_model_eval(
            max_cases=max(1, request.maxCases),
            live=request.live,
            family=request.family,
            surface=request.surface,
            prompt_id=request.promptId,
        )
    except drafts.ActiveDraftBlockError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "blockingDrafts": exc.blocking_drafts},
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/evals/case-draft")
def eval_case_draft(request: EvalCaseDraftRequest) -> dict[str, Any]:
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
def eval_runs() -> dict[str, Any]:
    return {"runs": evals.list_eval_runs()}


@app.get("/api/evals/runs/{run_id}")
def eval_run_detail(run_id: str) -> dict[str, Any]:
    try:
        return evals.get_eval_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/evals/promptfoo/{prompt_id}")
def eval_promptfoo(prompt_id: str) -> dict[str, Any]:
    return evals.promptfoo_config(prompt_id)


@app.get("/api/frames")
def recent_frames() -> dict[str, Any]:
    return {"frames": frames.recent_frames()}


dist = WORKBENCH_ROOT / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="static")
