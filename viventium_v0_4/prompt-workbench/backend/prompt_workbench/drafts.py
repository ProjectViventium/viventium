from __future__ import annotations

import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .paths import PROMPTS_ROOT, PROMPT_BANK_PATH, relative_to_repo, resolve_repo_path, workbench_private_root

from scripts.viventium.prompt_registry import PRIVATE_PATTERN_RULES, PromptRegistryError, parse_prompt_file


BLOCKING_DRAFT_KINDS = {"source-edit", "live-import", "eval-edit"}
PROMPT_DRAFT_KINDS = {"source-edit", "live-import"}


class ActiveDraftBlockError(ValueError):
    def __init__(self, message: str, blocking_drafts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.blocking_drafts = [_blocking_draft_summary(draft) for draft in blocking_drafts]


def list_drafts(
    *,
    private_root: Path | None = None,
    limit: int = 20,
    target_path: str | None = None,
    prompt_id: str | None = None,
) -> list[dict[str, Any]]:
    root = private_root or workbench_private_root()
    drafts_dir = root / "drafts"
    if not drafts_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    seen_active: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in sorted(drafts_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        public = _public_draft(draft)
        if target_path and public.get("targetPath") != target_path:
            continue
        if prompt_id and public.get("promptId") != prompt_id:
            continue
        if public.get("status") == "draft":
            key = (
                str(public.get("targetPath") or ""),
                str(public.get("baseHash") or ""),
                str(public.get("newHash") or ""),
                str(public.get("kind") or ""),
            )
            if key in seen_active:
                seen_active[key]["duplicateCount"] = int(seen_active[key].get("duplicateCount") or 1) + 1
                continue
            seen_active[key] = public
        rows.append(public)
        if len(rows) >= limit:
            break
    return rows


def active_blocking_drafts(
    *,
    private_root: Path | None = None,
    prompt_id: str | None = None,
    include_eval_drafts: bool = True,
    all_prompt_drafts: bool = False,
    limit: int = 500,
) -> list[dict[str, Any]]:
    rows = list_drafts(private_root=private_root, limit=limit)
    active: list[dict[str, Any]] = []
    for draft in rows:
        if draft.get("status") != "draft":
            continue
        kind = str(draft.get("kind") or "")
        if kind not in BLOCKING_DRAFT_KINDS:
            continue
        if kind == "eval-edit":
            if include_eval_drafts:
                active.append(draft)
            continue
        if all_prompt_drafts or not prompt_id or prompt_id == "main.conscious_agent":
            active.append(draft)
            continue
        if draft.get("promptId") == prompt_id:
            active.append(draft)
    return active


def assert_no_active_blocking_drafts(
    action: str,
    *,
    private_root: Path | None = None,
    prompt_id: str | None = None,
    include_eval_drafts: bool = True,
    all_prompt_drafts: bool = False,
) -> None:
    blocking = active_blocking_drafts(
        private_root=private_root,
        prompt_id=prompt_id,
        include_eval_drafts=include_eval_drafts,
        all_prompt_drafts=all_prompt_drafts,
    )
    if not blocking:
        return
    count = len(blocking)
    scope = "all source/eval drafts" if all_prompt_drafts else f"drafts for {prompt_id or 'the selected prompt'}"
    raise ActiveDraftBlockError(
        f"{action} blocked: apply or discard {count} pending {scope} before continuing.",
        blocking,
    )


def get_draft(draft_id: str, *, private_root: Path | None = None) -> dict[str, Any]:
    draft = _load_draft(draft_id, private_root=private_root)
    return _public_draft(draft)


def create_file_draft(
    *,
    target_path: Path,
    new_text: str,
    kind: str,
    reason: str = "",
    private_root: Path | None = None,
) -> dict[str, Any]:
    target_path = target_path.expanduser().resolve()
    _ensure_allowed_target(target_path)
    current_text = target_path.read_text(encoding="utf-8")
    _validate_public_safe_text(target_path, new_text)
    if target_path.suffix == ".md":
        _validate_public_prompt_text(target_path, new_text)
    if current_text == new_text or _semantically_same(target_path, current_text, new_text):
        raise ValueError("No changes detected; edit the prompt or eval before saving a draft.")

    token = _token(target_path, current_text, new_text)
    existing = _find_existing_active_draft(
        target_path=target_path,
        base_hash=_sha(current_text),
        new_hash=_sha(new_text),
        kind=kind,
        private_root=private_root,
    )
    if existing:
        public = _public_draft(existing)
        public["duplicate"] = True
        return public

    draft_id = str(uuid4())
    patch = "".join(
        difflib.unified_diff(
            current_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{relative_to_repo(target_path)}",
            tofile=f"b/{relative_to_repo(target_path)}",
        )
    )
    draft = {
        "id": draft_id,
        "kind": kind,
        "targetPath": relative_to_repo(target_path),
        "targetAbsolutePath": str(target_path),
        "baseHash": _sha(current_text),
        "newHash": _sha(new_text),
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": reason,
        "promptId": _prompt_id_for_target(target_path, new_text),
        "idempotencyToken": token,
        "patch": patch,
        "changeSummary": _patch_stats(patch),
        "currentText": current_text,
        "newText": new_text,
        "status": "draft",
    }
    root = private_root or workbench_private_root()
    drafts_dir = root / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    path = drafts_dir / f"{draft_id}.json"
    path.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return _public_draft(draft)


def apply_draft(draft_id: str, idempotency_token: str, *, private_root: Path | None = None) -> dict[str, Any]:
    draft_path, draft = _load_draft_with_path(draft_id, private_root=private_root)
    if draft.get("status") == "applied":
        raise ValueError("Draft has already been applied")
    if draft.get("status") == "discarded":
        raise ValueError("Draft has been discarded")
    if draft.get("idempotencyToken") != idempotency_token:
        raise ValueError("Draft idempotency token does not match reviewed diff")
    target = Path(str(draft["targetAbsolutePath"])).resolve()
    _ensure_allowed_target(target)
    current_text = target.read_text(encoding="utf-8")
    current_hash = _sha(current_text)
    if current_hash != draft.get("baseHash"):
        if current_hash == draft.get("newHash") or _semantically_same(target, current_text, str(draft["newText"])):
            draft["status"] = "applied"
            draft["appliedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            draft["alreadyApplied"] = True
            draft_path.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            draft_path.chmod(0o600)
            return {
                "id": draft_id,
                "status": "applied",
                "targetPath": draft["targetPath"],
                "newHash": draft["newHash"],
                "alreadyApplied": True,
            }
        raise ValueError("Target changed since draft was created; refresh and review again")
    new_text = str(draft["newText"])
    _validate_public_safe_text(target, new_text)
    if target.suffix == ".md":
        _validate_public_prompt_text(target, new_text)
    target.write_text(new_text, encoding="utf-8")
    draft["status"] = "applied"
    draft["appliedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    draft_path.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "id": draft_id,
        "status": "applied",
        "targetPath": draft["targetPath"],
        "newHash": draft["newHash"],
    }


def discard_draft(draft_id: str, *, private_root: Path | None = None) -> dict[str, Any]:
    draft_path, draft = _load_draft_with_path(draft_id, private_root=private_root)
    if draft.get("status") == "applied":
        raise ValueError("Applied drafts cannot be discarded")
    draft["status"] = "discarded"
    draft["discardedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    draft_path.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    draft_path.chmod(0o600)
    return {"id": draft_id, "status": "discarded", "targetPath": draft["targetPath"]}


def _load_draft(draft_id: str, *, private_root: Path | None = None) -> dict[str, Any]:
    return _load_draft_with_path(draft_id, private_root=private_root)[1]


def _load_draft_with_path(draft_id: str, *, private_root: Path | None = None) -> tuple[Path, dict[str, Any]]:
    root = private_root or workbench_private_root()
    draft_path = root / "drafts" / f"{draft_id}.json"
    if not draft_path.exists():
        raise FileNotFoundError(f"Unknown draft: {draft_id}")
    return draft_path, json.loads(draft_path.read_text(encoding="utf-8"))


def _public_draft(draft: dict[str, Any]) -> dict[str, Any]:
    public_draft = dict(draft)
    public_draft.pop("currentText", None)
    public_draft.pop("newText", None)
    public_draft.pop("targetAbsolutePath", None)
    if "changeSummary" not in public_draft:
        public_draft["changeSummary"] = _patch_stats(str(public_draft.get("patch") or ""))
    if not public_draft.get("promptId") and str(public_draft.get("targetPath") or "").endswith(".md"):
        public_draft["promptId"] = _prompt_id_from_existing_path(str(public_draft.get("targetPath") or ""))
    return public_draft


def _blocking_draft_summary(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": draft.get("id"),
        "kind": draft.get("kind"),
        "promptId": draft.get("promptId"),
        "targetPath": draft.get("targetPath"),
        "status": draft.get("status"),
        "createdAt": draft.get("createdAt"),
        "changeSummary": draft.get("changeSummary"),
    }


def _find_existing_active_draft(
    *,
    target_path: Path,
    base_hash: str,
    new_hash: str,
    kind: str,
    private_root: Path | None = None,
) -> dict[str, Any] | None:
    root = private_root or workbench_private_root()
    drafts_dir = root / "drafts"
    if not drafts_dir.exists():
        return None
    target = relative_to_repo(target_path)
    newest: tuple[float, dict[str, Any]] | None = None
    for path in drafts_dir.glob("*.json"):
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (
            draft.get("status") == "draft"
            and draft.get("targetPath") == target
            and draft.get("baseHash") == base_hash
            and draft.get("newHash") == new_hash
            and draft.get("kind") == kind
        ):
            row = (path.stat().st_mtime, draft)
            if newest is None or row[0] > newest[0]:
                newest = row
    return newest[1] if newest else None


def _prompt_id_for_target(target_path: Path, text: str) -> str | None:
    if target_path.suffix == ".md" and PROMPTS_ROOT.resolve() in target_path.resolve().parents:
        try:
            return str(parse_prompt_file_from_text(target_path, text).metadata.get("id") or "")
        except PromptRegistryError:
            return None
    return None


def _prompt_id_from_existing_path(target_path: str) -> str | None:
    try:
        path = resolve_repo_path(target_path).resolve()
        if path.exists() and PROMPTS_ROOT.resolve() in path.parents:
            return str(parse_prompt_file(path).metadata.get("id") or "")
    except Exception:
        return None
    return None


def parse_prompt_file_from_text(target_path: Path, text: str):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / target_path.name
        tmp_path.write_text(text, encoding="utf-8")
        return parse_prompt_file(tmp_path)


def _patch_stats(patch: str) -> dict[str, int | str]:
    additions = 0
    deletions = 0
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    if additions and deletions:
        label = f"{additions} added, {deletions} removed"
    elif additions:
        label = f"{additions} added"
    elif deletions:
        label = f"{deletions} removed"
    else:
        label = "metadata-only or unchanged diff"
    return {"additions": additions, "deletions": deletions, "label": label}


def _ensure_allowed_target(path: Path) -> None:
    prompts_root = PROMPTS_ROOT.resolve()
    prompt_bank = PROMPT_BANK_PATH.resolve()
    if not (path == prompt_bank or path == prompts_root or prompts_root in path.parents):
        raise ValueError(f"Draft target is outside prompt/eval source roots: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Draft target does not exist: {path}")


def _validate_public_prompt_text(target_path: Path, text: str) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / target_path.name
        tmp_path.write_text(text, encoding="utf-8")
        try:
            parse_prompt_file(tmp_path)
        except PromptRegistryError as exc:
            raise ValueError(str(exc)) from exc


def _validate_public_safe_text(target_path: Path, text: str) -> None:
    for label, pattern in PRIVATE_PATTERN_RULES:
        if pattern.search(text):
            raise ValueError(f"Private pattern {label} found in public draft: {relative_to_repo(target_path)}")


def _semantically_same(target_path: Path, current_text: str, new_text: str) -> bool:
    if target_path.suffix != ".json":
        return False
    try:
        return json.loads(current_text) == json.loads(new_text)
    except json.JSONDecodeError:
        return False


def _sha(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _token(path: Path, before: str, after: str) -> str:
    return hashlib.sha256(
        f"{path}\n{_sha(before, 64)}\n{_sha(after, 64)}".encode("utf-8")
    ).hexdigest()[:24]
