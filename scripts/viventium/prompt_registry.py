from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "prompts"
)
PROMPT_REF_KEY = "promptRef"
PROMPT_REFS_KEY = "promptRefs"
PROMPT_VARS_KEY = "promptVars"

REQUIRED_FRONTMATTER_FIELDS = {
    "id",
    "owner_layer",
    "target",
    "version",
    "status",
    "safety_class",
    "output_contract",
}

PRIVATE_PATTERN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("local_absolute_path", re.compile(r"(?:/Users|/home|/private/var|/var/folders)/[^\s`'\"<>]+")),
    ("email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    (
        "secret_like_token",
        re.compile(r"\b(?:sk|pk|rk|ghp|gho|github_pat|xox[baprs]?)-[A-Za-z0-9_\-]{8,}\b"),
    ),
    (
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.I),
    ),
)

VARIABLE_RE = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")
KNOWN_RUNTIME_PLACEHOLDERS = frozenset(
    {
        "current_user",
        "current_date",
        "current_datetime",
        "glasshive_worker_capability_summary",
        "glasshive_worker_execution_instruction",
        "iso_datetime",
    }
)


class PromptRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class PromptEntry:
    id: str
    path: Path
    metadata: dict[str, Any]
    body: str
    content_hash: str


def _sha256_prefix(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise PromptRegistryError(f"Prompt is missing YAML frontmatter: {_relative_to_repo(path)}")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise PromptRegistryError(f"Prompt frontmatter is not closed: {_relative_to_repo(path)}")

    raw_meta = text[4:end]
    body = text[end + len("\n---\n") :]
    metadata = yaml.safe_load(raw_meta) or {}
    if not isinstance(metadata, dict):
        raise PromptRegistryError(f"Prompt frontmatter must be a mapping: {_relative_to_repo(path)}")
    return metadata, body.rstrip() + "\n"


def _scan_public_prompt_safety(path: Path, metadata: dict[str, Any], body: str) -> None:
    safety_class = str(metadata.get("safety_class") or "").strip()
    if safety_class not in {"public_product", "public_safe"}:
        raise PromptRegistryError(
            f"Prompt in public source tree must use public-safe safety_class, got "
            f"{safety_class!r}: {_relative_to_repo(path)}"
        )

    scanned = f"{yaml.safe_dump(metadata, sort_keys=True)}\n{body}"
    for label, pattern in PRIVATE_PATTERN_RULES:
        if pattern.search(scanned):
            raise PromptRegistryError(
                f"Private pattern {label} found in public prompt: {_relative_to_repo(path)}"
            )


def parse_prompt_file(path: Path) -> PromptEntry:
    metadata, body = _split_frontmatter(path)
    missing = sorted(REQUIRED_FRONTMATTER_FIELDS - set(metadata))
    if missing:
        raise PromptRegistryError(
            f"Prompt frontmatter missing {', '.join(missing)}: {_relative_to_repo(path)}"
        )

    prompt_id = str(metadata.get("id") or "").strip()
    if not prompt_id:
        raise PromptRegistryError(f"Prompt id is empty: {_relative_to_repo(path)}")
    if not re.match(r"^[a-z0-9][a-z0-9_.-]*$", prompt_id):
        raise PromptRegistryError(f"Prompt id is invalid: {prompt_id!r} in {_relative_to_repo(path)}")
    if str(metadata.get("status") or "").strip() not in {"active", "draft", "deprecated"}:
        raise PromptRegistryError(f"Prompt status is invalid for {prompt_id}: {_relative_to_repo(path)}")
    if not isinstance(metadata.get("version"), int) or metadata.get("version") < 1:
        raise PromptRegistryError(f"Prompt version must be a positive integer for {prompt_id}")

    _scan_public_prompt_safety(path, metadata, body)
    normalized = f"{yaml.safe_dump(metadata, sort_keys=True)}---\n{body}"
    return PromptEntry(
        id=prompt_id,
        path=path,
        metadata=metadata,
        body=body,
        content_hash=_sha256_prefix(normalized),
    )


def load_prompt_registry(root: Path | str | None = None) -> dict[str, PromptEntry]:
    prompt_root = Path(root or DEFAULT_PROMPT_ROOT)
    if not prompt_root.exists():
        return {}

    entries: dict[str, PromptEntry] = {}
    for path in sorted(prompt_root.rglob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        entry = parse_prompt_file(path)
        if entry.id in entries:
            first = _relative_to_repo(entries[entry.id].path)
            second = _relative_to_repo(path)
            raise PromptRegistryError(f"Duplicate prompt id {entry.id!r}: {first} and {second}")
        entries[entry.id] = entry
    return entries


def _lookup_variable(variables: dict[str, Any], key: str) -> str:
    current: Any = variables
    for segment in key.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            raise PromptRegistryError(f"Missing prompt variable: {key}")
    if isinstance(current, (list, tuple)):
        return ", ".join(str(item) for item in current)
    if current is None:
        raise PromptRegistryError(f"Prompt variable is null: {key}")
    return str(current)


def _substitute_variables(text: str, variables: dict[str, Any], *, strict: bool = False) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        try:
            return _lookup_variable(variables, key)
        except PromptRegistryError:
            if strict:
                raise
            if key not in KNOWN_RUNTIME_PLACEHOLDERS:
                raise PromptRegistryError(
                    f"Unknown unfilled prompt variable {key!r}; add promptVars, "
                    "mark the prompt strict, or register an allowed runtime placeholder."
                )
            return match.group(0)

    return VARIABLE_RE.sub(replace, text)


def render_prompt(
    prompt_id: str,
    registry: dict[str, PromptEntry],
    *,
    variables: dict[str, Any] | None = None,
    _stack: tuple[str, ...] = (),
) -> str:
    if prompt_id in _stack:
        cycle = " -> ".join([*_stack, prompt_id])
        raise PromptRegistryError(f"Prompt include cycle detected: {cycle}")
    entry = registry.get(prompt_id)
    if not entry:
        raise PromptRegistryError(f"Unknown promptRef: {prompt_id}")

    rendered_parts: list[str] = []
    includes = entry.metadata.get("includes") or []
    if not isinstance(includes, list):
        raise PromptRegistryError(f"Prompt includes must be a list: {prompt_id}")
    for include_id in includes:
        rendered_parts.append(
            render_prompt(
                str(include_id),
                registry,
                variables=variables,
                _stack=(*_stack, prompt_id),
            ).strip()
        )
    # Match the runtime JavaScript resolver: front-matter spacing is not part
    # of the prompt body contract and must not create cross-runtime drift.
    rendered_parts.append(entry.body.strip())
    rendered = "\n\n".join(part for part in rendered_parts if part).rstrip() + "\n"
    return _substitute_variables(
        rendered,
        variables or {},
        strict=bool(entry.metadata.get("strict_variables")),
    )


def resolve_prompt_refs(value: Any, registry: dict[str, PromptEntry]) -> Any:
    if isinstance(value, list):
        return [resolve_prompt_refs(item, registry) for item in value]
    if not isinstance(value, dict):
        return value

    allowed_ref_keys = {PROMPT_REF_KEY, PROMPT_REFS_KEY, PROMPT_VARS_KEY, "separator"}
    keys = set(value)
    if PROMPT_REF_KEY in value and keys.issubset(allowed_ref_keys):
        prompt_id = str(value[PROMPT_REF_KEY]).strip()
        variables = value.get(PROMPT_VARS_KEY) or {}
        if not isinstance(variables, dict):
            raise PromptRegistryError(f"promptVars must be a mapping for {prompt_id}")
        return render_prompt(prompt_id, registry, variables=variables).rstrip()
    if PROMPT_REFS_KEY in value and keys.issubset(allowed_ref_keys):
        prompt_ids = value[PROMPT_REFS_KEY]
        if not isinstance(prompt_ids, list):
            raise PromptRegistryError("promptRefs must be a list")
        variables = value.get(PROMPT_VARS_KEY) or {}
        if not isinstance(variables, dict):
            raise PromptRegistryError("promptVars must be a mapping for promptRefs")
        separator = str(value.get("separator") or "\n\n")
        return separator.join(
            render_prompt(str(prompt_id), registry, variables=variables).rstrip()
            for prompt_id in prompt_ids
        )

    return {key: resolve_prompt_refs(nested, registry) for key, nested in value.items()}


def build_prompt_bundle(root: Path | str | None = None) -> dict[str, Any]:
    prompt_root = Path(root or DEFAULT_PROMPT_ROOT).resolve()
    registry = load_prompt_registry(prompt_root)
    prompts: dict[str, Any] = {}
    for prompt_id, entry in sorted(registry.items()):
        metadata = dict(entry.metadata)
        try:
            prompt_path = entry.path.resolve().relative_to(prompt_root).as_posix()
        except ValueError as error:
            raise PromptRegistryError(
                f"Prompt escapes the registry root: {prompt_id}"
            ) from error
        prompts[prompt_id] = {
            "id": prompt_id,
            "path": prompt_path,
            "metadata": metadata,
            "body": entry.body,
            "content_hash": entry.content_hash,
            "body_hash": _sha256_prefix(entry.body),
        }

    return {
        "schema_version": 1,
        "prompt_root": ".",
        "prompt_count": len(prompts),
        "prompts": prompts,
    }


def load_and_resolve_prompt_refs(value: Any, root: Path | str | None = None) -> Any:
    return resolve_prompt_refs(value, load_prompt_registry(root))


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate and compile the Viventium prompt registry.")
    parser.add_argument("--root", default=str(DEFAULT_PROMPT_ROOT), help="Prompt registry root")
    parser.add_argument("--json-out", default="", help="Optional prompt bundle JSON output path")
    args = parser.parse_args(argv)

    bundle = build_prompt_bundle(args.root)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(out, 0o600)
    else:
        print(json.dumps({k: v for k, v in bundle.items() if k != "prompts"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
