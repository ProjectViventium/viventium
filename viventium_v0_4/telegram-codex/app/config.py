from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


def _read_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _resolve_path(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _default_machine_state_root() -> Path:
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "Viventium" / "state" / "telegram-codex").resolve()

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return (Path(local_app_data).expanduser() / "Viventium" / "state" / "telegram-codex").resolve()

    xdg_state_home = os.environ.get("XDG_STATE_HOME", "").strip()
    if xdg_state_home:
        return (Path(xdg_state_home).expanduser() / "viventium" / "telegram-codex").resolve()
    return (Path.home() / ".local" / "state" / "viventium" / "telegram-codex").resolve()


_BOT_IDENTITY_SANITIZER = re.compile(r"[^a-z0-9._-]+")


def _bot_identity_slug(username: str, token: str) -> str:
    normalized_username = username.strip().lstrip("@").lower()
    if normalized_username:
        safe_username = _BOT_IDENTITY_SANITIZER.sub("-", normalized_username).strip("-.")
        if safe_username:
            return safe_username
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else "unknown-bot"
    return f"token-{digest}"


def _looks_like_legacy_paired_users_path(path: Path, project_root: Path) -> bool:
    normalized = path.expanduser().resolve()
    if normalized == (project_root / "runtime" / "state" / "paired_users.json").resolve():
        return True
    parts = normalized.parts
    if normalized.name == "paired_users.json" and len(parts) >= 3 and parts[-2] == "state" and parts[-3] == "runtime":
        return True
    return (
        normalized.name == "paired_users.json"
        and len(parts) >= 4
        and parts[-2] == "state"
        and parts[-3] == "telegram-codex"
        and "runtime" in parts
    )


def _pick_config_file(root: Path, tracked_name: str) -> Path:
    tracked_path = root / tracked_name
    if tracked_path.exists():
        return tracked_path
    example_path = tracked_path.with_name(f"{tracked_path.stem}.example{tracked_path.suffix}")
    if example_path.exists():
        return example_path
    raise RuntimeError(f"Missing config file: {tracked_path}")


@dataclass(frozen=True)
class BotSettings:
    token: str
    username: str
    private_chat_only: bool


@dataclass(frozen=True)
class PairingSettings:
    host: str
    port: int
    link_ttl_minutes: int
    bootstrap_if_empty: bool

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass(frozen=True)
class CodexSettings:
    command: str
    model: str
    sandbox: str
    approval_policy: str
    skip_git_repo_check: bool


@dataclass(frozen=True)
class TranscriptionSettings:
    whisper_mode: str
    language: str
    model_name: str
    model_path: str
    threads: int


@dataclass(frozen=True)
class RuntimeSettings:
    root: Path
    logs_dir: Path
    sessions_path: Path
    paired_users_path: Path
    paired_users_migration_sources: tuple[Path, ...]
    pending_pairs_path: Path
    project_registry_path: Path


@dataclass(frozen=True)
class AppConfig:
    root: Path
    bot: BotSettings
    pairing: PairingSettings
    codex: CodexSettings
    transcription: TranscriptionSettings
    runtime: RuntimeSettings


def load_config(root: Path | None = None) -> AppConfig:
    project_root = root or Path(__file__).resolve().parents[1]
    settings_override = (
        os.environ.get("TELEGRAM_CODEX_SETTINGS_FILE")
        or os.environ.get("VIVENTIUM_TELEGRAM_CODEX_SETTINGS_FILE")
        or ""
    )
    settings_path = (
        Path(settings_override).expanduser().resolve()
        if settings_override
        else _pick_config_file(project_root, "config/settings.yaml")
    )
    raw = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}

    bot_raw = raw.get("bot") or {}
    pairing_raw = raw.get("pairing") or {}
    codex_raw = raw.get("codex") or {}
    transcription_raw = raw.get("transcription") or {}
    runtime_raw = raw.get("runtime") or {}
    projects_raw = raw.get("projects") or {}

    env_file_path = str(
        os.environ.get("TELEGRAM_CODEX_ENV_FILE")
        or os.environ.get("VIVENTIUM_TELEGRAM_CODEX_ENV_FILE")
        or bot_raw.get("env_file")
        or ".env"
    )
    env_file = _resolve_path(project_root, env_file_path)
    merged_env = dict(_read_env_file(env_file))
    merged_env.update(os.environ)

    token = str(merged_env.get("TELEGRAM_CODEX_BOT_TOKEN") or merged_env.get("BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            f"TELEGRAM_CODEX_BOT_TOKEN is missing. Set it in {env_file} or export it in the environment."
        )

    username = str(
        merged_env.get("TELEGRAM_CODEX_BOT_USERNAME") or merged_env.get("TELEGRAM_BOT_USERNAME") or ""
    ).strip()

    bot_identity = _bot_identity_slug(username, token)

    project_registry_override = (
        os.environ.get("TELEGRAM_CODEX_PROJECTS_FILE")
        or os.environ.get("VIVENTIUM_TELEGRAM_CODEX_PROJECTS_FILE")
        or ""
    )

    configured_paired_users_raw = str(runtime_raw.get("paired_users_path") or "").strip()
    configured_paired_users_path = (
        _resolve_path(project_root, configured_paired_users_raw) if configured_paired_users_raw else None
    )
    stable_pairing_root_raw = str(runtime_raw.get("stable_pairing_root") or "").strip()
    stable_pairing_root = (
        _resolve_path(project_root, stable_pairing_root_raw)
        if stable_pairing_root_raw
        else (_default_machine_state_root() / "paired-users")
    )
    stable_paired_users_path = (stable_pairing_root / f"{bot_identity}.json").resolve()

    if configured_paired_users_path and not _looks_like_legacy_paired_users_path(
        configured_paired_users_path, project_root
    ):
        paired_users_path = configured_paired_users_path
    else:
        paired_users_path = stable_paired_users_path

    paired_users_migration_sources: list[Path] = []
    legacy_paired_users_raw = str(runtime_raw.get("legacy_paired_users_path") or "").strip()
    if legacy_paired_users_raw:
        paired_users_migration_sources.append(_resolve_path(project_root, legacy_paired_users_raw))
    if configured_paired_users_path and configured_paired_users_path != paired_users_path:
        paired_users_migration_sources.append(configured_paired_users_path)

    deduped_migration_sources: list[Path] = []
    seen_migration_sources: set[Path] = set()
    for candidate in paired_users_migration_sources:
        resolved_candidate = candidate.resolve()
        if resolved_candidate == paired_users_path or resolved_candidate in seen_migration_sources:
            continue
        seen_migration_sources.add(resolved_candidate)
        deduped_migration_sources.append(resolved_candidate)

    return AppConfig(
        root=project_root,
        bot=BotSettings(
            token=token,
            username=username,
            private_chat_only=bool(bot_raw.get("private_chat_only", True)),
        ),
        pairing=PairingSettings(
            host=str(pairing_raw.get("host") or "127.0.0.1"),
            port=int(pairing_raw.get("port") or 8765),
            link_ttl_minutes=int(pairing_raw.get("link_ttl_minutes") or 15),
            bootstrap_if_empty=bool(pairing_raw.get("bootstrap_if_empty", True)),
        ),
        codex=CodexSettings(
            command=str(codex_raw.get("command") or "codex"),
            model=str(codex_raw.get("model") or "gpt-5.4"),
            sandbox=str(codex_raw.get("sandbox") or "workspace-write"),
            approval_policy=str(codex_raw.get("approval_policy") or "never"),
            skip_git_repo_check=bool(codex_raw.get("skip_git_repo_check", False)),
        ),
        transcription=TranscriptionSettings(
            whisper_mode=str(transcription_raw.get("whisper_mode") or "pywhispercpp"),
            language=str(transcription_raw.get("language") or "en"),
            model_name=str(transcription_raw.get("model_name") or "large-v3-turbo"),
            model_path=str(transcription_raw.get("model_path") or ""),
            threads=int(transcription_raw.get("threads") or 8),
        ),
        runtime=RuntimeSettings(
            root=project_root,
            logs_dir=_resolve_path(project_root, str(runtime_raw.get("logs_dir") or "runtime/logs")),
            sessions_path=_resolve_path(
                project_root, str(runtime_raw.get("sessions_path") or "runtime/state/chat_sessions.json")
            ),
            paired_users_path=paired_users_path,
            paired_users_migration_sources=tuple(deduped_migration_sources),
            pending_pairs_path=_resolve_path(
                project_root, str(runtime_raw.get("pending_pairs_path") or "runtime/state/pair_tokens.json")
            ),
            project_registry_path=(
                Path(project_registry_override).expanduser().resolve()
                if project_registry_override
                else _resolve_path(project_root, str(projects_raw.get("registry_file") or "config/projects.yaml"))
            ),
        ),
    )
