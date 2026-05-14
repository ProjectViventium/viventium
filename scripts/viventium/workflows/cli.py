#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
WORKFLOW_NAMES = {"heal", "feature-request", "bug-report"}
APPROVABLE_WORKFLOWS = {"feature-request", "bug-report"}
RAW_PRIVATE_NOTE = (
    "Raw workflow artifacts are private local operator artifacts. Do not copy them into git, QA, "
    "support bundles, PRs, or public docs without the redaction/promotion step."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "workflow") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or fallback)[:72]


def redacted_path(path: Path) -> str:
    home = Path.home()
    try:
        return "~/" + str(path.resolve().relative_to(home.resolve()))
    except Exception:
        return str(path)


def redact_text(value: str) -> str:
    text = value.replace(str(Path.home()), "~")
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "<email>", text)
    text = re.sub(r"\b[0-9a-f]{24}\b", "<mongo-id>", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "<uuid>",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)=\S+", r"\1=<redacted>", text)
    return text


def read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            env[key] = value
    return env


def command_available(name: str) -> bool:
    return any((Path(part) / name).exists() for part in os.environ.get("PATH", "").split(os.pathsep) if part)


def preferred_profile(provider: str) -> str:
    if provider == "claude":
        return "claude-code"
    return "codex-cli"


def normalize_reasoning_effort(value: str) -> str:
    normalized = str(value or "xhigh").strip().lower()
    allowed = {"low", "medium", "high", "xhigh"}
    if normalized not in allowed:
        raise SystemExit(f"Unsupported reasoning effort: {value}")
    return normalized


def create_pr_after_user_approval(ctx: "WorkflowContext") -> bool:
    raw = ctx.runtime_env.get(
        "VIVENTIUM_WORK_REQUEST_CREATE_PR_AFTER_USER_APPROVAL",
        ctx.runtime_env.get("VIVENTIUM_FEATURE_REQUEST_CREATE_PR_AFTER_USER_APPROVAL", "true"),
    )
    return str(raw).lower() == "true"


@dataclass
class WorkflowContext:
    repo_root: Path
    app_support_dir: Path
    runtime_dir: Path
    runtime_env: dict[str, str]

    @property
    def state_dir(self) -> Path:
        return self.app_support_dir / "state" / "workflows"

    @property
    def runs_dir(self) -> Path:
        return self.state_dir / "runs"

    @property
    def active_file(self) -> Path:
        return self.state_dir / "active.json"

    @property
    def glasshive_base_url(self) -> str:
        raw = self.runtime_env.get("WPR_MCP_BASE_URL") or "http://127.0.0.1:8766"
        return raw.rstrip("/")

    @property
    def glasshive_enabled(self) -> bool:
        return (
            self.runtime_env.get("START_GLASSHIVE", "false").lower() == "true"
            and self.runtime_env.get("GLASSHIVE_HOST_WORKERS_ENABLED", "false").lower() == "true"
        )


def context_from_args(args: argparse.Namespace) -> WorkflowContext:
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    runtime_env = read_env_file(runtime_dir / "runtime.env")
    runtime_env.update(read_env_file(runtime_dir / "runtime.local.env"))
    return WorkflowContext(
        repo_root=Path(args.repo_root).expanduser().resolve(),
        app_support_dir=Path(args.app_support_dir).expanduser().resolve(),
        runtime_dir=runtime_dir,
        runtime_env=runtime_env,
    )


def active_run(ctx: WorkflowContext) -> dict[str, Any] | None:
    if not ctx.active_file.exists():
        return None
    try:
        payload = json.loads(ctx.active_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    run_dir = Path(payload.get("run_dir") or "")
    summary = run_dir / "summary.json"
    if summary.exists():
        try:
            return json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            return payload
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def append_event(run_dir: Path, event_type: str, message: str, **extra: Any) -> None:
    events = run_dir / "events.jsonl"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "ts": utc_now(),
        "event_type": event_type,
        "message": redact_text(message),
        **extra,
    }
    with events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    try:
        events.chmod(0o600)
    except OSError:
        pass


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 3.0) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def create_isolated_worktree(ctx: WorkflowContext, workflow: str, run_id: str, title: str) -> tuple[str, Path, str]:
    prefix_by_workflow = {
        "heal": "heal",
        "feature-request": "feature",
        "bug-report": "bugfix",
    }
    prefix = prefix_by_workflow.get(workflow, "workflow")
    timestamp = slugify(run_id.split("-", 1)[0].lower(), "run")
    slug = slugify(title, workflow)
    branch = f"{prefix}/{slug}-{timestamp}"
    worktree = ctx.state_dir / "worktrees" / prefix / f"{slug}-{timestamp}"
    worktree.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if worktree.exists():
        raise RuntimeError(f"Isolated workflow worktree already exists: {worktree}")
    base = run_git(ctx.repo_root, "rev-parse", "HEAD")
    if base.returncode != 0:
        raise RuntimeError(redact_text(base.stderr.strip() or base.stdout.strip() or "git rev-parse failed"))
    base_commit = base.stdout.strip()
    proc = run_git(ctx.repo_root, "worktree", "add", "-b", branch, str(worktree), "HEAD")
    if proc.returncode != 0:
        raise RuntimeError(redact_text(proc.stderr.strip() or proc.stdout.strip() or "git worktree add failed"))
    try:
        worktree.chmod(0o700)
    except OSError:
        pass
    return branch, worktree, base_commit


def glasshive_healthy(ctx: WorkflowContext) -> tuple[bool, str]:
    if not ctx.glasshive_enabled:
        return False, "GlassHive host workers are disabled in the compiled runtime env."
    errors: list[str] = []
    for path in ("/health", "/v1/metrics/summary", "/v1/metrics"):
        try:
            http_json("GET", f"{ctx.glasshive_base_url}{path}", timeout=2.0)
            return True, ""
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    detail = "; ".join(errors)
    return False, f"GlassHive control plane is not reachable at {ctx.glasshive_base_url}: {detail}"


def materialize_heal_prompts(
    run_dir: Path,
    repo_root: Path,
    mode: str,
    effort: str,
    provider: str,
    worktree_path: Path | None = None,
) -> None:
    context = {
        "project_root": redacted_path(repo_root),
        "write_target": redacted_path(worktree_path or repo_root),
        "mode": mode,
        "reasoning_effort": effort,
        "provider": provider,
    }
    apply_boundary = (
        f"\nApply mode write boundary:\nMake code changes only in this isolated worktree: {worktree_path}\n"
        "Do not modify the active user checkout.\n"
        if worktree_path is not None
        else "\nDiagnose-only mode: do not make code changes.\n"
    )
    (run_dir / "00-heal-workflow.md").write_text(
        redact_text(
            f"""# Viventium Self-Healing Workflow

You are running through the Viventium self-healing harness. Follow this exact flow and write the
handoff files named below in Markdown.

## Project

- project root to study: {repo_root}
- write target: {worktree_path or repo_root}
- mode: {mode}
- reasoning effort: {effort}
- provider: {provider}

## Required Flow

1. Study the project root, relevant logs, DB state, code, nested repos, and nested Markdown docs.
2. Write `01-rca.md` with the RCA, including debate/stress-test notes that validate the RCA.
3. Stop and request orchestrator review using `02-orchestrator-rca-review-prompt.md`.
4. After RCA approval, write `03-proposed-fix.md`, aligned with `docs/requirements_and_learnings/01_Key_Principles.md` and relevant nested docs.
5. Stop and request orchestrator review using `04-orchestrator-fix-review-prompt.md`.
6. Only after both gates pass, and only when mode is `apply`, make the approved fix in the isolated worktree and run documented tests/QA.

## Boundaries

{apply_boundary}
- Raw artifacts are private local operator artifacts.
- Do not push, create a remote PR, or make cloud-side changes.
"""
        ),
        encoding="utf-8",
    )
    (run_dir / "01-rca-prompt.md").write_text(
        redact_text(
            f"""There seems to be some issues with Viventium.

Study this project in: {repo_root}
Fully study relevant logs, DB state, code, nested repos, and nested Markdown docs.
With a full understanding, write an RCA in Markdown.
Debate and stress test the RCA before concluding.
{apply_boundary}

Context:
{json.dumps(context, indent=2)}

Privacy:
{RAW_PRIVATE_NOTE}
"""
        ),
        encoding="utf-8",
    )
    (run_dir / "02-orchestrator-rca-review-prompt.md").write_text(
        "Review 01-rca.md. Challenge the RCA, list gaps, and either approve or request revision.\n",
        encoding="utf-8",
    )
    (run_dir / "03-proposed-fix-prompt.md").write_text(
        "Using the approved RCA, propose a fix aligned with 01_Key_Principles.md and QA policy.\n",
        encoding="utf-8",
    )
    (run_dir / "04-orchestrator-fix-review-prompt.md").write_text(
        "Review 03-proposed-fix.md. Challenge fit, blast radius, tests, and public/private safety.\n",
        encoding="utf-8",
    )
    (run_dir / "05-implementation-prompt.md").write_text(
        (
            "Only in explicit apply mode: implement the approved fix in the isolated worktree "
            f"{worktree_path} and run QA.\n"
            if worktree_path is not None
            else "Diagnose-only mode: stop after RCA/proposed-fix artifacts and do not modify files.\n"
        ),
        encoding="utf-8",
    )


def materialize_feature_prompts(run_dir: Path, request: str, effort: str, provider: str, create_pr_after_approval: bool) -> None:
    (run_dir / "00-feature-request-workflow.md").write_text(
        f"""# Viventium Feature Request Workflow

Follow this exact flow.

1. Complete `feature-request.md` intake before implementation.
2. Ensure the intake includes success criteria, non-obvious cases, missing requirements, non-goals, impacted surfaces, and QA acceptance.
3. Stop for user approval before writing code.
4. After user approval, Viventium will create an isolated feature worktree and provide `03-approved-implementation-prompt.md`.
5. Implement only from the approved spec and only in the isolated worktree.
6. Prepare PR-ready local artifacts only after QA passes and public-safety checks pass.
7. Do not push, create a remote PR, or make cloud-side changes unless Viventium explicitly asks in a later step.
"""
    )
    approved_spec = f"""# Feature Request Intake

## User Request
{redact_text(request)}

## Intake Required Before Build
- success criteria
- non-obvious cases
- missing requirements
- non-goals
- impacted surfaces
- QA acceptance

## Provider
- provider: {provider}
- reasoning effort: {effort}

## PR Policy
- create PR after user approval: {"true" if create_pr_after_approval else "false"}
- when false, ask the user: "Would you like me to create a feature request PR to Viventium?"

## Privacy
{RAW_PRIVATE_NOTE}
"""
    (run_dir / "feature-request.md").write_text(approved_spec, encoding="utf-8")
    (run_dir / "01-intake-prompt.md").write_text(
        "Complete the feature-request intake in feature-request.md before implementation begins.\n",
        encoding="utf-8",
    )
    (run_dir / "02-implementation-prompt.md").write_text(
        "After user approval, implement from feature-request.md in an isolated feature worktree.\n",
        encoding="utf-8",
    )


def materialize_bug_report_prompts(
    run_dir: Path,
    report: dict[str, str],
    effort: str,
    provider: str,
    create_pr_after_approval: bool,
) -> None:
    def field(name: str) -> str:
        return redact_text((report.get(name) or "").strip() or "_Not provided yet._")

    (run_dir / "00-bug-report-workflow.md").write_text(
        f"""# Viventium Bug Report Workflow

Follow this exact flow.

1. Complete `bug-report.md` intake before implementation.
2. Ensure the intake captures what happened, steps to reproduce, expected behavior, actual behavior, other details, non-obvious cases, impacted surfaces, evidence to inspect, and QA acceptance.
3. If the report is missing necessary repro details, stop and ask for the missing data instead of guessing.
4. Stop for user approval before writing code.
5. After user approval, Viventium will create an isolated bugfix worktree and provide `07-approved-bugfix-prompt.md`.
6. In the isolated worktree, reproduce or validate the bug from the approved report, inspect relevant logs/evidence, write an RCA, propose the fix, and only then implement.
7. Prepare PR-ready local artifacts only after QA passes and public-safety checks pass.
8. Do not push, create a remote PR, or make cloud-side changes unless Viventium explicitly asks in a later step.
""",
        encoding="utf-8",
    )
    bug_report = f"""# Bug Report Intake

## What Happened
{field("what_happened")}

## Steps To Reproduce
{field("steps_to_reproduce")}

## Expected Behavior
{field("expected")}

## Actual Behavior
{field("actual")}

## Other Details
{field("details")}

## Reproduction Readiness
- confirm the bug is specific enough to reproduce or validate
- identify missing reproduction details

## Non-Obvious Cases
- list cases that could look similar but require a different fix
- list edge cases the fix must not break

## Impacted Surfaces
- list affected UI, CLI, helper, runtime, installer, docs, and QA surfaces

## Evidence To Inspect
- list relevant logs, generated state, App Support artifacts, code paths, nested repos, and docs

## QA Acceptance
- define visible user acceptance
- define backend/log evidence
- define regression coverage

## Provider
- provider: {provider}
- reasoning effort: {effort}

## PR Policy
- create PR after user approval: {"true" if create_pr_after_approval else "false"}
- when false, ask the user: "Would you like me to create a bug fix PR to Viventium?"

## Privacy
{RAW_PRIVATE_NOTE}
"""
    (run_dir / "bug-report.md").write_text(bug_report, encoding="utf-8")
    (run_dir / "01-intake-prompt.md").write_text(
        (
            "Complete the bug-report intake in bug-report.md before implementation begins. "
            "Ask for missing repro details instead of coding from an ambiguous bug report.\n"
        ),
        encoding="utf-8",
    )
    (run_dir / "02-rca-prompt.md").write_text(
        (
            "After user approval, reproduce or validate the bug from bug-report.md, inspect relevant "
            "logs/evidence/state, and write an RCA before proposing a fix.\n"
        ),
        encoding="utf-8",
    )
    (run_dir / "03-orchestrator-rca-review-prompt.md").write_text(
        "Review the bug RCA. Challenge reproduction evidence, causal chain, and missing cases.\n",
        encoding="utf-8",
    )
    (run_dir / "04-proposed-fix-prompt.md").write_text(
        "Using the approved bug RCA, propose a fix aligned with 01_Key_Principles.md and QA policy.\n",
        encoding="utf-8",
    )
    (run_dir / "05-orchestrator-fix-review-prompt.md").write_text(
        "Review the proposed bug fix. Challenge fit, blast radius, tests, and public/private safety.\n",
        encoding="utf-8",
    )
    (run_dir / "06-implementation-prompt.md").write_text(
        "After RCA and fix review gates pass, implement only in the isolated bugfix worktree and run QA.\n",
        encoding="utf-8",
    )


def start_workflow(args: argparse.Namespace) -> int:
    ctx = context_from_args(args)
    if args.workflow not in WORKFLOW_NAMES:
        raise SystemExit(f"Unknown workflow: {args.workflow}")
    args.reasoning_effort = normalize_reasoning_effort(args.reasoning_effort)
    ctx.runs_dir.mkdir(parents=True, exist_ok=True)
    current = active_run(ctx)
    if current and current.get("state") in {"running", "queued", "awaiting_approval"}:
        raise SystemExit(f"Workflow already active: {current.get('run_id')}")

    provider = args.provider
    if provider == "auto":
        provider = "codex" if command_available("codex") else "claude" if command_available("claude") else "none"
    if provider == "none":
        raise SystemExit("No local Codex or Claude CLI was found on PATH.")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + slugify(args.workflow)
    run_dir = ctx.runs_dir / run_id
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    workflow_branch = ""
    workflow_base_commit = ""
    worktree_path: Path | None = None

    if args.workflow == "heal":
        if args.mode == "apply":
            try:
                workflow_branch, worktree_path, workflow_base_commit = create_isolated_worktree(
                    ctx,
                    "heal",
                    run_id,
                    "viventium-heal",
                )
            except RuntimeError as exc:
                raise SystemExit(str(exc)) from exc
        materialize_heal_prompts(
            run_dir,
            ctx.repo_root,
            args.mode,
            args.reasoning_effort,
            provider,
            worktree_path,
        )
    elif args.workflow == "feature-request":
        create_pr_after_approval = create_pr_after_user_approval(ctx)
        materialize_feature_prompts(
            run_dir,
            args.request or "",
            args.reasoning_effort,
            provider,
            create_pr_after_approval,
        )
    else:
        create_pr_after_approval = create_pr_after_user_approval(ctx)
        report = {
            "what_happened": args.what_happened or args.request or "",
            "steps_to_reproduce": args.steps_to_reproduce or "",
            "expected": args.expected or "",
            "actual": args.actual or "",
            "details": args.details or "",
        }
        materialize_bug_report_prompts(
            run_dir,
            report,
            args.reasoning_effort,
            provider,
            create_pr_after_approval,
        )
    for artifact in run_dir.glob("*"):
        try:
            artifact.chmod(0o600)
        except OSError:
            pass

    healthy, health_error = glasshive_healthy(ctx)
    state = "queued"
    failure_class = ""
    if not healthy:
        if not args.allow_degraded:
            state = "blocked"
            failure_class = "glasshive_unavailable"
        else:
            state = "degraded_ready"
            failure_class = "glasshive_degraded_mode"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "workflow": args.workflow,
        "state": state,
        "phase": "intake" if args.workflow in APPROVABLE_WORKFLOWS else "",
        "mode": args.mode,
        "provider": provider,
        "profile": preferred_profile(provider),
        "reasoning_effort": args.reasoning_effort,
        "work_request_create_pr_after_user_approval": create_pr_after_user_approval(ctx),
        "feature_request_create_pr_after_user_approval": create_pr_after_user_approval(ctx),
        "started_at": utc_now(),
        "run_dir": str(run_dir),
        "workflow_branch": workflow_branch,
        "workflow_base_commit": workflow_base_commit,
        "isolated_worktree": str(worktree_path) if worktree_path is not None else "",
        "glasshive_base_url": ctx.glasshive_base_url,
        "glasshive_enabled": ctx.glasshive_enabled,
        "failure_class": failure_class,
        "message": health_error if not healthy else "Workflow artifacts prepared for GlassHive host-worker dispatch.",
    }

    if healthy:
        title = f"Viventium {args.workflow.replace('-', ' ').title()} {run_id}"
        if args.workflow == "heal":
            goal = "Diagnose and heal Viventium using the approved RCA/proposed-fix workflow."
        elif args.workflow == "bug-report":
            goal = "Complete bug-report intake, then diagnose and fix from the approved report after user approval."
        else:
            goal = "Complete feature-request intake and implementation workflow after user approval."
        try:
            project = http_json(
                "POST",
                f"{ctx.glasshive_base_url}/v1/projects",
                {
                    "owner_id": "local-viventium-workflows",
                    "title": title,
                    "goal": goal,
                    "default_worker_profile": preferred_profile(provider),
                },
                timeout=4.0,
            )
            worker = http_json(
                "POST",
                f"{ctx.glasshive_base_url}/v1/projects/{project['project_id']}/workers/find-or-resume",
                {
                    "owner_id": "local-viventium-workflows",
                    "name": title,
                    "role": args.workflow,
                    "profile": preferred_profile(provider),
                    "backend": "openclaw",
                    "execution_mode": "host",
                    "alias": slugify(f"viventium-{args.workflow}"),
                    "bootstrap_profile": "host-login",
                    "bootstrap_bundle": {
                        "version": 1,
                        "files": [
                            {"path": str(path.name), "content": path.read_text(encoding="utf-8")}
                            for path in sorted(run_dir.glob("*.md"))
                        ],
                        "env": {
                            "VIVENTIUM_WORKFLOW": args.workflow,
                            "VIVENTIUM_WORKFLOW_RUN_ID": run_id,
                            "VIVENTIUM_WORKFLOW_BRANCH": workflow_branch,
                            "VIVENTIUM_WORKFLOW_WORKTREE": str(worktree_path) if worktree_path is not None else "",
                        },
                    },
                },
                timeout=4.0,
            )
            if args.workflow == "heal":
                instruction = (run_dir / "00-heal-workflow.md").read_text(encoding="utf-8")
            elif args.workflow == "bug-report":
                instruction = (run_dir / "00-bug-report-workflow.md").read_text(encoding="utf-8")
            else:
                instruction = (run_dir / "00-feature-request-workflow.md").read_text(encoding="utf-8")
            run = http_json(
                "POST",
                f"{ctx.glasshive_base_url}/v1/workers/{worker['worker_id']}/assign",
                {"instruction": instruction},
                timeout=4.0,
            )
            summary.update(
                {
                    "state": "running",
                    "glasshive_project_id": project["project_id"],
                    "glasshive_worker_id": worker["worker_id"],
                    "glasshive_run_id": run["run_id"],
                    "message": "Workflow dispatched to GlassHive host worker.",
                }
            )
        except Exception as exc:
            summary.update(
                {
                    "state": "blocked",
                    "failure_class": "glasshive_dispatch_failed",
                    "message": redact_text(str(exc)),
                }
            )

    write_json(run_dir / "summary.json", summary)
    write_json(ctx.active_file, {"run_id": run_id, "run_dir": str(run_dir), "workflow": args.workflow})
    append_event(run_dir, "run.started", summary["message"], state=summary["state"])
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(summary["message"])
        print(f"Run artifacts: {redacted_path(run_dir)}")
    return 0 if summary["state"] in {"queued", "running", "degraded_ready"} else 2


def refresh_from_glasshive(ctx: WorkflowContext, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = str(payload.get("glasshive_project_id") or "").strip()
    run_id = str(payload.get("glasshive_run_id") or "").strip()
    run_dir_text = str(payload.get("run_dir") or "").strip()
    if not project_id or not run_id or not run_dir_text:
        return payload
    try:
        runs = http_json("GET", f"{ctx.glasshive_base_url}/v1/projects/{project_id}/runs", timeout=2.0)
    except Exception:
        return payload
    items = runs.get("items", []) if isinstance(runs, dict) else []
    glasshive_run = next((item for item in items if isinstance(item, dict) and item.get("run_id") == run_id), None)
    if not glasshive_run:
        return payload
    glasshive_state = str(glasshive_run.get("state") or "").strip()
    if not glasshive_state:
        return payload
    payload["glasshive_run_state"] = glasshive_state
    if glasshive_state == "completed":
        if payload.get("workflow") in APPROVABLE_WORKFLOWS and payload.get("phase", "intake") == "intake":
            payload["state"] = "awaiting_approval"
            if payload.get("workflow") == "bug-report":
                payload["message"] = "Bug report intake is ready for user approval."
            else:
                payload["message"] = "Feature request intake is ready for user approval."
        else:
            payload["state"] = "completed"
            payload["message"] = "Workflow run completed."
    elif glasshive_state in {"queued", "running"}:
        payload["state"] = glasshive_state
    elif glasshive_state in {"failed", "cancelled"}:
        payload["state"] = glasshive_state
    write_json(Path(run_dir_text) / "summary.json", payload)
    return payload


def cleanup_isolated_worktree(ctx: WorkflowContext, payload: dict[str, Any]) -> dict[str, Any]:
    worktree_text = str(payload.get("isolated_worktree") or "").strip()
    branch = str(payload.get("workflow_branch") or "").strip()
    base_commit = str(payload.get("workflow_base_commit") or "").strip()
    if not worktree_text:
        payload["cleanup_state"] = "not_needed"
        return payload
    worktree = Path(worktree_text)
    if not worktree.exists():
        payload["cleanup_state"] = "worktree_missing"
        return payload
    status = run_git(worktree, "status", "--porcelain")
    if status.returncode != 0:
        payload["cleanup_state"] = "blocked_status_failed"
        payload["cleanup_message"] = redact_text(status.stderr.strip() or status.stdout.strip())
        return payload
    if status.stdout.strip():
        payload["cleanup_state"] = "blocked_dirty_worktree"
        payload["cleanup_message"] = "Isolated workflow worktree has local changes; leaving it for manual review."
        return payload
    remove = run_git(ctx.repo_root, "worktree", "remove", str(worktree))
    if remove.returncode != 0:
        payload["cleanup_state"] = "blocked_remove_failed"
        payload["cleanup_message"] = redact_text(remove.stderr.strip() or remove.stdout.strip())
        return payload
    payload["cleanup_state"] = "worktree_removed"
    if branch and (branch.startswith("heal/") or branch.startswith("feature/") or branch.startswith("bugfix/")) and base_commit:
        branch_head = run_git(ctx.repo_root, "rev-parse", branch)
        if branch_head.returncode == 0 and branch_head.stdout.strip() == base_commit:
            deleted = run_git(ctx.repo_root, "branch", "-D", branch)
            if deleted.returncode == 0:
                payload["cleanup_state"] = "worktree_and_branch_removed"
            else:
                payload["cleanup_message"] = redact_text(deleted.stderr.strip() or deleted.stdout.strip())
    return payload


def interrupt_glasshive_worker(ctx: WorkflowContext, payload: dict[str, Any]) -> dict[str, Any]:
    worker_id = str(payload.get("glasshive_worker_id") or "").strip()
    if not worker_id:
        return payload
    healthy, health_error = glasshive_healthy(ctx)
    if not healthy:
        payload["glasshive_cancel_error"] = health_error
        return payload
    try:
        http_json("POST", f"{ctx.glasshive_base_url}/v1/workers/{worker_id}/interrupt", timeout=3.0)
        payload["glasshive_cancelled"] = True
    except Exception as exc:
        payload["glasshive_cancel_error"] = redact_text(str(exc))
    return payload


def approve_workflow(args: argparse.Namespace) -> int:
    ctx = context_from_args(args)
    payload = active_run(ctx)
    if not payload:
        raise SystemExit("No active workflow.")
    payload = refresh_from_glasshive(ctx, payload)
    workflow = str(payload.get("workflow") or "")
    if workflow not in APPROVABLE_WORKFLOWS:
        raise SystemExit("The active workflow is not awaiting an approval step.")
    if payload.get("phase") == "implementation":
        raise SystemExit("Workflow implementation is already approved.")
    run_id = str(payload.get("run_id") or "").strip()
    run_dir = Path(str(payload.get("run_dir") or ""))
    spec_name = "bug-report.md" if workflow == "bug-report" else "feature-request.md"
    spec = run_dir / spec_name
    if not run_id or not run_dir.exists() or not spec.exists():
        raise SystemExit("Workflow artifacts are incomplete.")
    title = args.slug or spec.read_text(encoding="utf-8", errors="replace").splitlines()[0] or "feature"
    try:
        workflow_branch, worktree_path, workflow_base_commit = create_isolated_worktree(
            ctx,
            workflow,
            run_id,
            title,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    implementation_prompt = (
        run_dir / "07-approved-bugfix-prompt.md"
        if workflow == "bug-report"
        else run_dir / "03-approved-implementation-prompt.md"
    )
    if workflow == "bug-report":
        prompt = f"""The user has approved this Viventium bug report for local diagnosis and fix.

Approved bug report: {spec}
Implementation write target: {worktree_path}
Local branch: {workflow_branch}

Rules:
- Make code changes only in the isolated bugfix worktree.
- Do not modify the active user checkout.
- Reproduce or validate the bug from the approved report before changing code.
- Inspect relevant logs, evidence, state, docs, and nested repos before writing the RCA.
- Write RCA and proposed-fix artifacts before implementation.
- Run the documented Viventium QA acceptance for affected surfaces.
- Prepare PR-ready local artifacts only after QA passes and public-safety checks pass.
- Do not push or create a remote PR unless Viventium explicitly asks at that later step.
"""
    else:
        prompt = f"""The user has approved this Viventium feature request for local implementation.

Approved spec: {spec}
Implementation write target: {worktree_path}
Local branch: {workflow_branch}

Rules:
- Make code changes only in the isolated feature worktree.
- Do not modify the active user checkout.
- Run the documented Viventium QA acceptance for affected surfaces.
- Prepare PR-ready local artifacts only after QA passes and public-safety checks pass.
- Do not push or create a remote PR unless Viventium explicitly asks at that later step.
"""
    implementation_prompt.write_text(redact_text(prompt), encoding="utf-8")
    try:
        implementation_prompt.chmod(0o600)
    except OSError:
        pass

    payload.update(
        {
            "phase": "implementation",
            "state": "queued",
            "approved_at": utc_now(),
            "workflow_branch": workflow_branch,
            "workflow_base_commit": workflow_base_commit,
            "isolated_worktree": str(worktree_path),
            "message": (
                "Bug report approved; isolated bugfix worktree prepared."
                if workflow == "bug-report"
                else "Feature request approved; isolated implementation worktree prepared."
            ),
        }
    )

    healthy, health_error = glasshive_healthy(ctx)
    if healthy and payload.get("glasshive_worker_id"):
        try:
            run = http_json(
                "POST",
                f"{ctx.glasshive_base_url}/v1/workers/{payload['glasshive_worker_id']}/assign",
                {"instruction": implementation_prompt.read_text(encoding="utf-8")},
                timeout=4.0,
            )
            payload.update(
                {
                    "state": "running",
                    "glasshive_intake_run_id": payload.get("glasshive_run_id", ""),
                    "glasshive_run_id": run.get("run_id", ""),
                    "glasshive_implementation_run_id": run.get("run_id", ""),
                    "message": (
                        "Bug fix implementation dispatched to GlassHive host worker."
                        if workflow == "bug-report"
                        else "Feature implementation dispatched to GlassHive host worker."
                    ),
                }
            )
        except Exception as exc:
            payload.update(
                {
                    "state": "blocked",
                    "failure_class": "glasshive_dispatch_failed",
                    "message": redact_text(str(exc)),
                }
            )
    elif not healthy:
        payload.update(
            {
                "state": "blocked",
                "failure_class": "glasshive_unavailable",
                "message": health_error,
            }
        )

    write_json(run_dir / "summary.json", payload)
    write_json(ctx.active_file, {"run_id": run_id, "run_dir": str(run_dir), "workflow": workflow})
    append_event(run_dir, f"{workflow}.approved", payload["message"], state=payload["state"])
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["message"])
        print(f"Worktree: {redacted_path(worktree_path)}")
    return 0 if payload["state"] in {"queued", "running"} else 2


def status(args: argparse.Namespace) -> int:
    ctx = context_from_args(args)
    payload = active_run(ctx) or {"schema_version": SCHEMA_VERSION, "state": "idle"}
    if payload.get("state") not in {"idle", "blocked", "cancelled", "completed", "failed"}:
        payload = refresh_from_glasshive(ctx, payload)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Workflow state: {payload.get('state', 'idle')}")
        if payload.get("run_id"):
            print(f"Run: {payload['run_id']}")
            print(f"Artifacts: {redacted_path(Path(payload['run_dir']))}")
    return 0


def cancel(args: argparse.Namespace) -> int:
    ctx = context_from_args(args)
    payload = active_run(ctx)
    if not payload:
        print("No active workflow.")
        return 0
    payload = interrupt_glasshive_worker(ctx, payload)
    payload["state"] = "cancelled"
    payload["cancelled_at"] = utc_now()
    payload = cleanup_isolated_worktree(ctx, payload)
    run_dir = Path(payload["run_dir"])
    write_json(run_dir / "summary.json", payload)
    try:
        ctx.active_file.unlink()
    except FileNotFoundError:
        pass
    append_event(run_dir, "run.cancelled", "Workflow cancelled by operator")
    print(f"Cancelled workflow {payload.get('run_id')}.")
    return 0


def open_artifacts(args: argparse.Namespace) -> int:
    ctx = context_from_args(args)
    payload = active_run(ctx)
    if not payload:
        raise SystemExit("No active workflow.")
    run_dir = Path(payload["run_dir"])
    if sys.platform == "darwin":
        subprocess.run(["open", str(run_dir)], check=False)
    print(redacted_path(run_dir))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bin/viventium workflows")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--app-support-dir", required=True)
    parser.add_argument("--runtime-dir", required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("workflow", choices=sorted(WORKFLOW_NAMES))
    start.add_argument("--mode", choices=["diagnose", "apply"], default="diagnose")
    start.add_argument("--provider", choices=["auto", "codex", "claude"], default="auto")
    start.add_argument("--reasoning-effort", default="xhigh")
    start.add_argument("--request", default="")
    start.add_argument("--what-happened", default="")
    start.add_argument("--steps-to-reproduce", default="")
    start.add_argument("--expected", default="")
    start.add_argument("--actual", default="")
    start.add_argument("--details", default="")
    start.add_argument("--allow-degraded", action="store_true")
    start.add_argument("--json", action="store_true")
    start.set_defaults(func=start_workflow)

    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--json", action="store_true")
    status_cmd.set_defaults(func=status)

    approve_cmd = sub.add_parser("approve")
    approve_cmd.add_argument("--slug", default="")
    approve_cmd.add_argument("--json", action="store_true")
    approve_cmd.set_defaults(func=approve_workflow)

    cancel_cmd = sub.add_parser("cancel")
    cancel_cmd.set_defaults(func=cancel)

    open_cmd = sub.add_parser("open-artifacts")
    open_cmd.set_defaults(func=open_artifacts)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
