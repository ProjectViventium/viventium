#!/usr/bin/env python3
"""Relocatable, dependency-free-at-target supervisor for a Native payload."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path


class RuntimeError_(RuntimeError):
    pass


SERVICE_ORDER = ("mongodb", "librechat", "frontend-proxy")
SERVICE_PORTS = {
    "frontend-proxy": (3190, 3191),
}
SANDPACK_INDEX_SHA256 = "ace51687532a2e9cbfcc11d790bc96b250c477cfa3545ab285915b9eca8e7aa6"


@contextmanager
def lifecycle_lock(support: Path, *, timeout: float = 30.0):
    """Serialize mutating Native lifecycle operations without touching App Support."""
    # TMPDIR is caller-controlled and may differ between Terminal, Finder, and
    # LaunchAgent processes. A fixed system temporary root gives every process
    # one lock namespace before App Support exists or is safe to mutate.
    lock_root = Path("/private/tmp" if sys.platform == "darwin" else "/tmp")
    try:
        metadata = lock_root.lstat()
    except OSError as error:
        raise RuntimeError_("Native lifecycle lock directory is unavailable") from error
    if (
        lock_root.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != 0
        or not metadata.st_mode & stat.S_ISVTX
    ):
        raise RuntimeError_("Native lifecycle lock directory is unsafe")
    digest = hashlib.sha256(os.fsencode(support)).hexdigest()
    lock_path = lock_root / f"viventium-native-lifecycle-{digest}.lock"
    try:
        descriptor = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as error:
        raise RuntimeError_("Native lifecycle lock is unavailable") from error
    try:
        lock_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(lock_metadata.st_mode)
            or lock_metadata.st_uid != os.getuid()
            or stat.S_IMODE(lock_metadata.st_mode) != 0o600
        ):
            raise RuntimeError_("Native lifecycle lock is unsafe")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError_("Another Native lifecycle operation is still running")
                time.sleep(0.1)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def release_root() -> Path:
    return Path(__file__).resolve().parents[2]


def user_home() -> Path:
    return Path.home()


def default_support() -> Path:
    return user_home() / "Library" / "Application Support" / "Viventium"


def lexical_support(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    if absolute.parent == absolute:
        return absolute
    # Resolve only the parent. This canonicalizes macOS aliases such as
    # /var -> /private/var and user-created parent aliases so equivalent
    # support paths share one lock, while preserving a symlink at the support
    # leaf for validate_support_children() to reject.
    return absolute.parent.resolve(strict=False) / absolute.name


def validate_existing_private_directory(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    try:
        metadata = path.lstat()
    except OSError as error:
        raise RuntimeError_(f"Native mutable path is unsafe: {path.name}") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise RuntimeError_(f"Native mutable path is unsafe: {path.name}")


def ensure_private_directory(path: Path) -> None:
    validate_existing_private_directory(path)
    if not path.exists():
        missing: list[Path] = []
        current = path
        while not current.exists() and not current.is_symlink():
            missing.append(current)
            if current.parent == current:
                break
            current = current.parent
        try:
            metadata = current.lstat()
        except OSError as error:
            raise RuntimeError_(f"Native mutable parent path is unsafe: {current}") from error
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError_(f"Native mutable parent path is unsafe: {current}")
        for component in reversed(missing):
            try:
                component.mkdir(mode=0o700)
            except (FileExistsError, OSError) as error:
                raise RuntimeError_(f"Native mutable path is unsafe: {component.name}") from error
            validate_existing_private_directory(component)
    if stat.S_IMODE(path.lstat().st_mode) != 0o700:
        path.chmod(0o700)


def validate_support_children(support: Path) -> None:
    validate_existing_private_directory(support)
    for relative in ("state", "runtime", "logs", "data", "data/mongodb", "backups", "snapshots"):
        current = support
        for component in Path(relative).parts:
            current = current / component
            validate_existing_private_directory(current)


def ensure_support_directories(support: Path, *relatives: str) -> None:
    ensure_private_directory(support)
    for relative in relatives:
        current = support
        for component in Path(relative).parts:
            current = current / component
            ensure_private_directory(current)


def write_atomic(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def runtime_secrets(support: Path) -> dict[str, str]:
    path = support / "state" / "native-secrets.json"
    lock_path = support / "state" / "native-secrets.lock"
    expected_lengths = {
        "JWT_SECRET": 64,
        "JWT_REFRESH_SECRET": 64,
        "CREDS_KEY": 64,
        "CREDS_IV": 32,
    }
    validate_support_children(support)
    ensure_support_directories(support, "state")
    lock_descriptor = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        lock_metadata = os.fstat(lock_descriptor)
        if lock_metadata.st_uid != os.getuid() or stat.S_IMODE(lock_metadata.st_mode) != 0o600:
            raise RuntimeError_("Native machine-secret lock has unsafe ownership or permissions")
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        if not path.exists():
            values = {key: secrets.token_hex(length // 2) for key, length in expected_lengths.items()}
            write_atomic(path, json.dumps(values, sort_keys=True, separators=(",", ":")) + "\n")
    finally:
        os.close(lock_descriptor)
    try:
        metadata = path.lstat()
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError_("Native machine secrets are unavailable or invalid") from error
    if path.is_symlink() or not path.is_file() or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError_("Native machine secrets have unsafe ownership or permissions")
    if set(values) != set(expected_lengths):
        raise RuntimeError_("Native machine secrets schema is invalid")
    for key, length in expected_lengths.items():
        value = values[key]
        if not isinstance(value, str) or len(value) != length or any(c not in "0123456789abcdef" for c in value):
            raise RuntimeError_("Native machine secrets contain an invalid value")
    return values


def runtime_state(support: Path) -> dict[str, object]:
    validate_support_children(support)
    path = support / "state" / "native-runtime.json"
    try:
        metadata = path.lstat()
    except OSError as error:
        raise RuntimeError_("Native runtime is not installed for this user") from error
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise RuntimeError_("Native runtime state is unsafe")
    if not path.is_file():
        raise RuntimeError_("Native runtime is not installed for this user")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError_("Native runtime state is invalid") from error
    if payload.get("schema_version") != 1:
        raise RuntimeError_("Native runtime state schema is unsupported")
    return payload


def installed_release_root(support: Path, *, allow_missing: bool = False) -> Path:
    """Return the active immutable release, refusing stale release CLIs/hooks."""
    state_path = support / "state" / "native-runtime.json"
    if not state_path.exists() and not state_path.is_symlink():
        if allow_missing:
            return release_root()
        raise RuntimeError_("Native runtime is not installed for this user")
    state = runtime_state(support)
    active = Path(str(state.get("release_root", ""))).resolve()
    current = release_root()
    if active != current:
        raise RuntimeError_("Installed release pointer does not match this payload")
    return active


def mongodb_socket_path(support: Path) -> Path:
    return support / "runtime" / "mongodb-27117.sock"


def mongodb_uri(support: Path) -> str:
    socket_host = urllib.parse.quote(str(mongodb_socket_path(support)), safe="")
    return f"mongodb://{socket_host}/LibreChat"


def native_api_socket_path(support: Path) -> Path:
    return support / "runtime" / "librechat-api.sock"


def validate_native_socket_lengths(support: Path) -> None:
    # Darwin's sockaddr_un.sun_path is 104 bytes including its terminating NUL.
    # Validate both service socket names before launching any child so a long
    # custom App Support path fails with a useful, deterministic error.
    maximum = 103 if sys.platform == "darwin" else 107
    for path in (mongodb_socket_path(support), native_api_socket_path(support)):
        if len(os.fsencode(path)) > maximum:
            raise RuntimeError_("Native App Support path is too long for private service sockets")


def required_assets(root: Path) -> tuple[Path, ...]:
    return (
        root / "runtime" / "node" / "bin" / "node",
        root / "runtime" / "python" / "bin" / "python3",
        root / "runtime" / "mongodb" / "bin" / "mongod",
        root / "runtime" / "librechat" / "api" / "server" / "index.js",
        root / "runtime" / "librechat" / "client" / "dist" / "index.html",
        root / "runtime" / "librechat" / "client" / "dist" / "sandpack-bundler" / "index.html",
        root / "runtime" / "librechat" / "node_modules",
        root / "runtime" / "proxy.js",
        root / "runtime" / "scripts" / "native_process_guard.py",
        root / "runtime" / "scripts" / "continuity_bundle.py",
        root / "runtime" / "scripts" / "continuity_mongo.cjs",
        root / "runtime" / "scripts" / "native_first_admin_recovery.js",
        root / "runtime" / "scripts" / "native_verify_agent.js",
        root / "bin" / "viventium-native-registration-close",
        root / "runtime" / "defaults" / "librechat.yaml",
        root / "runtime" / "defaults" / "native-runtime.env",
        root / "runtime" / "defaults" / "prompt-bundle.json",
        root / "runtime" / "defaults" / "viventium-agents.yaml",
        root / "runtime" / "librechat" / "scripts" / "viventium-seed-agents.js",
        root / "runtime" / "librechat" / "scripts" / "viventium-reconcile-user-defaults.js",
        root / "runtime" / "librechat" / "config" / "issue-password-reset-link.js",
        root / "release-metadata" / "build.json",
    )


def packaged_health(root: Path) -> None:
    missing = [str(path.relative_to(root)) for path in required_assets(root) if not path.exists()]
    if missing:
        raise RuntimeError_("Native payload is incomplete: " + ", ".join(missing))
    for executable in required_assets(root)[:3]:
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RuntimeError_(f"Native executable is unavailable: {executable.name}")
    sandpack_index = (
        root / "runtime" / "librechat" / "client" / "dist" / "sandpack-bundler" / "index.html"
    )
    try:
        sandpack_metadata = sandpack_index.lstat()
        sandpack_body = sandpack_index.read_bytes()
        sandpack_digest = hashlib.sha256(sandpack_body).hexdigest()
        release_metadata = json.loads(
            (root / "release-metadata" / "build.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError_("Native isolated artifact runtime is unavailable") from error
    expected_digest = release_metadata.get("sandpack_index_sha256")
    mode = release_metadata.get("mode")
    if (
        stat.S_ISLNK(sandpack_metadata.st_mode)
        or not stat.S_ISREG(sandpack_metadata.st_mode)
        or sandpack_metadata.st_uid != os.getuid()
        or b'IS_ONPREM:"true"' not in sandpack_body
        or mode not in {"local-qa", "candidate"}
        or not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
        or sandpack_digest != expected_digest
        or (mode == "candidate" and expected_digest != SANDPACK_INDEX_SHA256)
    ):
        raise RuntimeError_("Native isolated artifact runtime failed its release identity check")


NATIVE_FIXED_ENV = {
    "VIVENTIUM_RUNTIME_PROFILE": "native",
    "VIVENTIUM_INSTALL_MODE": "native",
    "VIVENTIUM_INSTALL_EXPERIENCE": "express",
    "VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED": "true",
    "OPENAI_API_KEY": "user_provided",
    "ANTHROPIC_API_KEY": "user_provided",
    "GROQ_API_KEY": "user_provided",
    "XAI_API_KEY": "user_provided",
    "VIVENTIUM_LC_API_PORT": "3180",
    "VIVENTIUM_LC_FRONTEND_PORT": "3190",
    "VIVENTIUM_PLAYGROUND_PORT": "3300",
    "SANDPACK_BUNDLER_URL": "http://127.0.0.1:3191/",
    "SANDPACK_STATIC_BUNDLER_URL": "http://127.0.0.1:3191/",
}
NATIVE_ALLOWED_PLAIN_ENV = {
    "DEBUG_LOGGING",
    "MONGO_AUTO_INDEX",
    "OTUC_ACTIVATION_LLM",
    "OTUC_ACTIVATION_PROVIDER",
    "OTUC_LLM_MODEL",
    "OTUC_LLM_PROVIDER",
    "PLAYGROUND_VARIANT",
    "SAFE_MODE",
    "SEARCH",
    "TTS_PROVIDER_PRIMARY",
}


def load_native_runtime_env(path: Path) -> dict[str, str]:
    """Load only the compiler-owned, secret-free Native behavior contract."""
    try:
        metadata = path.lstat()
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RuntimeError_("Native runtime environment is unavailable") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or len(content.encode("utf-8")) > 1024 * 1024
    ):
        raise RuntimeError_("Native runtime environment is unsafe")

    result: dict[str, str] = {}
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            words = shlex.split(raw_line, comments=False, posix=True)
        except ValueError as error:
            raise RuntimeError_("Native runtime environment contains invalid quoting") from error
        if len(words) != 1 or "=" not in words[0]:
            raise RuntimeError_(f"Native runtime environment has an invalid line: {line_number}")
        key, value = words[0].split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in result:
            raise RuntimeError_("Native runtime environment has an invalid or duplicate key")
        if not (
            key.startswith("VIVENTIUM_")
            or key.startswith("START_")
            or key in NATIVE_ALLOWED_PLAIN_ENV
            or key in NATIVE_FIXED_ENV
        ):
            raise RuntimeError_("Native runtime environment contains an unapproved key")
        if key not in NATIVE_FIXED_ENV and any(
            fragment in key for fragment in ("SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "API_KEY")
        ):
            raise RuntimeError_("Native runtime environment contains a secret-shaped key")
        if key not in NATIVE_FIXED_ENV and key.endswith(
            ("_DIR", "_FILE", "_ORIGIN", "_PATH", "_PORT", "_ROOT", "_URL", "_USER_EMAIL")
        ):
            raise RuntimeError_("Native runtime environment contains a path or network key")
        if (
            not value
            or (value == "user_provided" and key not in NATIVE_FIXED_ENV)
            or "${" in value
            or "\x00" in value
            or value.startswith(("/", "~"))
        ):
            raise RuntimeError_("Native runtime environment contains an unsafe value")
        if key.startswith("START_") and value != "false":
            raise RuntimeError_("Native runtime environment may not start external services")
        result[key] = value

    if any(result.get(key) != value for key, value in NATIVE_FIXED_ENV.items()):
        raise RuntimeError_("Native runtime environment does not match the fixed Native profile")
    return result


def native_child_environment(support: Path) -> dict[str, str]:
    """Build a minimal child environment without inheriting host provider credentials."""
    ensure_support_directories(support, "runtime/tmp")
    environment = {
        "HOME": str(user_home()),
        "PATH": "/usr/bin:/bin",
        "TMPDIR": str(support / "runtime" / "tmp"),
        "LANG": "en_US.UTF-8",
    }
    environment.update(load_native_runtime_env(support / "runtime" / "runtime.env"))
    return environment


def build_metadata(root: Path) -> dict[str, object]:
    try:
        value = json.loads((root / "release-metadata" / "build.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError_("Native build metadata is invalid") from error
    schema = value.get("data_schema")
    if (
        not isinstance(schema, dict)
        or set(schema) != {"minimum", "maximum", "target"}
        or any(isinstance(schema[key], bool) or not isinstance(schema[key], int) for key in schema)
        or not 1 <= schema["minimum"] <= schema["target"] <= schema["maximum"]
    ):
        raise RuntimeError_("Native data schema policy is invalid")
    source_commit = value.get("source_commit")
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise RuntimeError_("Native release identity is invalid")
    return value


def data_schema_state_path(support: Path) -> Path:
    return support / "state" / "native-data-schema.json"


def inspect_data_schema(support: Path, root: Path) -> int:
    validate_support_children(support)
    policy = build_metadata(root)["data_schema"]
    if not isinstance(policy, dict):
        raise RuntimeError_("Native data-schema policy is invalid")
    path = data_schema_state_path(support)
    if not path.exists():
        data = support / "data" / "mongodb"
        if data.is_dir() and next(data.iterdir(), None) is not None:
            raise RuntimeError_(
                "Existing Native data schema is unknown; refusing to guess or mutate it"
            )
        return int(policy["target"])
    try:
        metadata = path.lstat()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError_("Native data schema state is invalid") from error
    if (
        path.is_symlink()
        or not path.is_file()
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or set(value) != {"schema_version", "current"}
        or value.get("schema_version") != 1
        or isinstance(value.get("current"), bool)
        or not isinstance(value.get("current"), int)
        or value["current"] < 1
    ):
        raise RuntimeError_("Native data schema state is unsafe or unsupported")
    return int(value["current"])


def copy_checkpoint_source(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise RuntimeError_("Native pre-migration checkpoint source contains a symlink")
    if not source.exists():
        return
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)
        return
    for current, directories, files in os.walk(source, topdown=True, followlinks=False):
        current_path = Path(current)
        relative = current_path.relative_to(source)
        target = destination / relative
        target.mkdir(parents=True, exist_ok=True)
        for name in [*directories, *files]:
            if (current_path / name).is_symlink():
                raise RuntimeError_("Native pre-migration checkpoint source contains a symlink")
        for name in files:
            shutil.copy2(current_path / name, target / name, follow_symlinks=False)


def create_pre_migration_checkpoint(support: Path, current: int, target: int) -> Path:
    validate_support_children(support)
    ensure_support_directories(support, "backups")
    backup_root = support / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    token = f"{int(time.time())}-{uuid.uuid4().hex}"
    staged = backup_root / f".native-pre-migration-{token}.staging"
    final = backup_root / f"native-pre-migration-{token}"
    staged.mkdir(mode=0o700)
    try:
        for relative in ("config.yaml", "state", "data/mongodb"):
            copy_checkpoint_source(support / relative, staged / relative)
        checkpoint = {
            "schema_version": 1,
            "current": current,
            "target": target,
            "created_at": int(time.time()),
        }
        write_atomic(staged / "checkpoint.json", json.dumps(checkpoint, sort_keys=True) + "\n")
        os.replace(staged, final)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise
    return final


def prepare_data_schema(support: Path, root: Path) -> int:
    policy = build_metadata(root)["data_schema"]
    if not isinstance(policy, dict):
        raise RuntimeError_("Native data-schema policy is invalid")
    current = inspect_data_schema(support, root)
    minimum = int(policy["minimum"])
    maximum = int(policy["maximum"])
    target = int(policy["target"])
    if not minimum <= current <= maximum:
        raise RuntimeError_(
            f"Native data schema {current} is outside candidate compatibility {minimum}..{maximum}"
        )
    if current != target:
        create_pre_migration_checkpoint(support, current, target)
        raise RuntimeError_(
            f"Native data schema {current}->{target} requires a reviewed migration implementation; checkpoint created"
        )
    write_atomic(
        data_schema_state_path(support),
        json.dumps({"schema_version": 1, "current": current}, sort_keys=True, separators=(",", ":")) + "\n",
    )
    return current


def helper_owner(app: Path) -> dict[str, object] | None:
    marker = app / "Contents" / "Resources" / "viventium-owner.json"
    try:
        if app.is_symlink() or marker.is_symlink() or not marker.is_file():
            return None
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if value.get("product") != "ai.viventium.helper" or value.get("schema_version") != 1:
        return None
    return value


def helper_tree_is_safe(app: Path) -> bool:
    try:
        if app.is_symlink() or not app.is_dir():
            return False
        for current, directories, files in os.walk(app, topdown=True, followlinks=False):
            root = Path(current)
            for name in [*directories, *files]:
                path = root / name
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    return False
                if not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
                    return False
        return True
    except OSError:
        return False


def ensure_helper_applications_directory() -> Path:
    home = Path(os.path.abspath(os.fspath(user_home())))
    applications = home / "Applications"
    if applications.exists() or applications.is_symlink():
        try:
            metadata = applications.lstat()
        except OSError as error:
            raise RuntimeError_("Native helper Applications directory is unsafe") from error
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            raise RuntimeError_("Native helper Applications directory is unsafe")
        return applications
    try:
        home_metadata = home.lstat()
    except OSError as error:
        raise RuntimeError_("Native helper Applications parent is unsafe") from error
    if (
        stat.S_ISLNK(home_metadata.st_mode)
        or not stat.S_ISDIR(home_metadata.st_mode)
        or home_metadata.st_uid != os.getuid()
    ):
        raise RuntimeError_("Native helper Applications parent is unsafe")
    try:
        applications.mkdir(mode=0o755)
    except (FileExistsError, OSError) as error:
        raise RuntimeError_("Native helper Applications directory is unsafe") from error
    metadata = applications.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise RuntimeError_("Native helper Applications directory is unsafe")
    return applications


def install_helper(source: Path, support: Path) -> Path | None:
    validate_support_children(support)
    ensure_support_directories(support, "state")
    if helper_owner(source) is None or not helper_tree_is_safe(source):
        raise RuntimeError_("Packaged helper ownership marker is invalid")
    target = ensure_helper_applications_directory() / "Viventium.app"
    if target.exists() or target.is_symlink():
        if helper_owner(target) is None or not helper_tree_is_safe(target):
            raise RuntimeError_("Refusing to replace an unrelated application at ~/Applications/Viventium.app")
    token = uuid.uuid4().hex
    staged = target.with_name(f".Viventium.app.installing.{token}")
    backup_dir = support / "state" / "helper-backups"
    ensure_private_directory(backup_dir)
    backup = backup_dir / f"Viventium-{int(time.time())}-{token}.app"
    moved_prior = False
    try:
        shutil.copytree(source, staged, symlinks=False)
        if helper_owner(staged) is None:
            raise RuntimeError_("Staged helper ownership verification failed")
        if target.exists():
            os.replace(target, backup)
            moved_prior = True
        os.replace(staged, target)
        if helper_owner(target) is None:
            raise RuntimeError_("Activated helper ownership verification failed")
        return backup if moved_prior else None
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        if moved_prior and backup.exists():
            if target.exists():
                if helper_owner(target) is not None and helper_tree_is_safe(target):
                    shutil.rmtree(target)
                else:
                    raise RuntimeError_("Helper activation failed and an unrelated app now occupies the target; prior helper remains backed up")
            os.replace(backup, target)
        raise


def rollback_helper(target: Path, backup: Path | None) -> None:
    if target.exists() and helper_owner(target) is not None and helper_tree_is_safe(target):
        shutil.rmtree(target)
    if backup is not None and backup.exists():
        os.replace(backup, target)


def ensure_first_admin_state(support: Path) -> dict[str, object]:
    validate_support_children(support)
    ensure_support_directories(support, "state")
    path = support / "state" / "native-first-admin.json"
    if not path.exists():
        value = {"schema_version": 1, "status": "open", "token": secrets.token_hex(32)}
        write_atomic(path, json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        return value
    try:
        metadata = path.lstat()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError_("Native first-admin state is invalid") from error
    if (
        path.is_symlink()
        or not path.is_file()
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or value.get("schema_version") != 1
        or value.get("status") not in {"open", "pending", "closed"}
    ):
        raise RuntimeError_("Native first-admin state is unsafe or unsupported")
    if value["status"] in {"open", "pending"}:
        token = value.get("token")
        if not isinstance(token, str) or len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
            raise RuntimeError_("Native first-admin token is invalid")
    elif "token" in value:
        raise RuntimeError_("Closed Native first-admin state retains a token")
    return value


def install(args: argparse.Namespace, *, _lock_held: bool = False) -> None:
    support = lexical_support(args.app_support_dir)
    if not _lock_held:
        with lifecycle_lock(support):
            install(args, _lock_held=True)
        return
    root = release_root()
    packaged_health(root)
    validate_support_children(support)
    refuse_cross_mode_install(support)
    if native_restore_journal_path(support).exists() or native_restore_journal_path(support).is_symlink():
        recover_native_restore_before_lifecycle(support, root)
    preexisting_services: dict[str, int | None] = {}
    if not args.no_start:
        preflight_service_ports(support, root)
        preexisting_services = guard_pid_snapshot(support, root)
    ensure_support_directories(support, "logs", "runtime", "state", "data/mongodb", "backups")
    prepare_data_schema(support, root)

    config = support / "config.yaml"
    if not config.exists():
        shutil.copyfile(root / "runtime" / "defaults" / "config.yaml", config)
        config.chmod(0o600)
    runtime_secrets(support)
    first_admin = ensure_first_admin_state(support)
    packaged_runtime_env = root / "runtime" / "defaults" / "native-runtime.env"
    load_native_runtime_env(packaged_runtime_env)
    write_atomic(
        support / "runtime" / "runtime.env",
        packaged_runtime_env.read_text(encoding="utf-8"),
    )

    helper_source = root / "apps" / "Viventium.app"
    helper_target = user_home() / "Applications" / "Viventium.app"
    helper_backup: Path | None = None
    previous_state_path = support / "state" / "native-runtime.json"
    previous_state = previous_state_path.read_bytes() if previous_state_path.is_file() else None
    if not args.local_qa and not args.no_helper and helper_source.is_dir():
        helper_backup = install_helper(helper_source, support)
        helper_config = {
            "repoRoot": str(root),
            "appSupportDir": str(support),
            "allowProtectedRepoRoot": True,
            "showInStatusBar": True,
            "nativeRuntime": True,
        }
        write_atomic(
            support / "helper-config.json",
            json.dumps(helper_config, sort_keys=True, separators=(",", ":")) + "\n",
        )
    state = {
        "schema_version": 1,
        "release_root": str(root),
        "installed_at": int(time.time()),
        "local_qa": bool(args.local_qa),
    }
    write_atomic(
        support / "state" / "native-runtime.json",
        json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n",
    )
    try:
        if not args.no_start:
            start(args, _lock_held=True)
            health(type("HealthArgs", (), {"app_support_dir": support, "installed_only": False})())
        if not args.local_qa and not args.no_helper:
            subprocess.run(["/usr/bin/open", "-gj", str(helper_target)], check=False)
        if not args.no_start and not args.no_open:
            path = "__viventium_native_first_admin" if first_admin["status"] == "open" else ""
            token = f"?token={first_admin['token']}" if first_admin["status"] == "open" else ""
            subprocess.run(["/usr/bin/open", f"http://127.0.0.1:3190/{path}{token}"], check=False)
    except BaseException:
        if not args.no_start:
            stop_attempt_services(support, root, preexisting_services)
        if not args.local_qa and not args.no_helper:
            rollback_helper(helper_target, helper_backup)
        if previous_state is None:
            previous_state_path.unlink(missing_ok=True)
        else:
            write_atomic(previous_state_path, previous_state.decode("utf-8"))
        raise
    print(f"Viventium Native installed at {root}")


def refuse_cross_mode_install(support: Path) -> None:
    runtime_env = support / "runtime" / "runtime.env"
    native_state = support / "state" / "native-runtime.json"
    if native_state.exists() or native_state.is_symlink():
        installed_release_root(support)
    native_owned = native_state.is_file() or data_schema_state_path(support).is_file()
    if runtime_env.is_file():
        values = runtime_env.read_text(encoding="utf-8", errors="replace").splitlines()
        profile = next(
            (line.split("=", 1)[1] for line in values if line.startswith("VIVENTIUM_RUNTIME_PROFILE=")),
            "",
        )
        if profile and profile != "native":
            raise RuntimeError_(
                "Existing App Support belongs to the source/Docker runtime; Native migration is not yet transactional, so all existing data was preserved"
            )
    legacy_roots = (
        support / "state" / "mongo-data",
        support / "state" / "runtime" / "mongo-data",
    )
    nested_legacy = support / "state" / "runtime"
    legacy_data = any(path.is_dir() and next(path.iterdir(), None) is not None for path in legacy_roots)
    if nested_legacy.is_dir():
        legacy_data = legacy_data or any(
            path.is_dir() and next(path.iterdir(), None) is not None
            for path in nested_legacy.glob("*/mongo-data")
        )
    if legacy_data or ((support / "config.yaml").exists() and not native_owned):
        raise RuntimeError_(
            "Established non-Native App Support requires a reviewed source/Docker-to-Native migration; refusing to overwrite runtime.env or present empty history"
        )


def pid_path(support: Path, service: str) -> Path:
    return support / "runtime" / f"{service}.process.json"


def quarantine_pid_record(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    quarantine = path.with_name(f"{path.name}.stale.{int(time.time())}.{uuid.uuid4().hex}")
    try:
        os.replace(path, quarantine)
    except OSError:
        pass


def process_value(pid: int, field: str) -> str | None:
    completed = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", f"{field}="],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


_EXECUTABLE_DIGEST_CACHE: dict[tuple[str, int, int], str] = {}


def executable_digest(path: Path) -> str:
    resolved = path.resolve(strict=True)
    metadata = resolved.stat()
    key = (str(resolved), metadata.st_size, metadata.st_mtime_ns)
    cached = _EXECUTABLE_DIGEST_CACHE.get(key)
    if cached is not None:
        return cached
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    _EXECUTABLE_DIGEST_CACHE[key] = value
    return value


def process_executable(pid: int) -> Path | None:
    if sys.platform != "darwin":
        command = process_value(pid, "command")
        if command is None:
            return None
        candidate = command.split(" ", 1)[0]
        return Path(candidate) if Path(candidate).is_absolute() else None
    completed = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-a", "-p", str(pid), "-d", "txt", "-Fn"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    paths = [Path(line[1:]) for line in completed.stdout.splitlines() if line.startswith("n/")]
    if not paths or not paths[0].is_absolute():
        return None
    executable = paths[0]
    if executable.name == "dyld" or executable.name.startswith("dyld_shared_cache"):
        return None
    return executable


def live_pid(path: Path, root: Path, *, quarantine_invalid: bool = True) -> int | None:
    try:
        metadata = path.lstat()
        record = json.loads(path.read_text(encoding="utf-8"))
        if (
            path.is_symlink()
            or not path.is_file()
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or record.get("schema_version") != 1
            or record.get("release_root") != str(root)
            or record.get("service") != path.name.removesuffix(".process.json")
        ):
            raise ValueError
        pid = record["pid"]
        token = record["token"]
        started = record["process_start"]
        interpreter_digest = record["interpreter_sha256"]
        if (
            not isinstance(pid, int)
            or pid <= 1
            or not isinstance(token, str)
            or len(token) != 64
            or not isinstance(interpreter_digest, str)
        ):
            raise ValueError
        if os.getpgid(pid) != pid:
            raise ValueError
        command = process_value(pid, "command")
        current_start = process_value(pid, "lstart")
        guard = str(root / "runtime" / "scripts" / "native_process_guard.py")
        interpreter = root / "runtime" / "python" / "bin" / "python3"
        running_interpreter = process_executable(pid)
        if (
            command is None
            or current_start != started
            or " -E -s -B " not in command
            or guard not in command
            or f"--token {token}" not in command
            or executable_digest(interpreter) != interpreter_digest
            or running_interpreter is None
            or running_interpreter.resolve(strict=True) != interpreter.resolve(strict=True)
        ):
            raise ValueError
        os.kill(pid, 0)
        return pid
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        if quarantine_invalid:
            quarantine_pid_record(path)
        return None


def listener_pids(port: int) -> set[int]:
    """Return every PID listening on one Native TCP port, or fail closed."""
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise RuntimeError_("Native listener ownership port is invalid")
    try:
        completed = subprocess.run(
            [
                "/usr/sbin/lsof",
                "-nP",
                "-a",
                f"-iTCP:{port}",
                "-sTCP:LISTEN",
                "-t",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError_("Native listener ownership could not be verified") from error
    if (
        completed.returncode == 1
        and not completed.stdout.strip()
        and not completed.stderr.strip()
    ):
        return set()
    if completed.returncode != 0:
        raise RuntimeError_("Native listener ownership could not be verified")
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        match = re.fullmatch(r"([1-9][0-9]*)", line)
        if match is None:
            raise RuntimeError_("Native listener ownership response was invalid")
        pids.add(int(match.group(1)))
    return pids


def all_tcp_listener_pids() -> set[int]:
    """Return every local TCP-listener PID, or fail closed."""
    try:
        completed = subprocess.run(
            [
                "/usr/sbin/lsof",
                "-nP",
                "-a",
                "-iTCP",
                "-sTCP:LISTEN",
                "-t",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError_("Native TCP listener inventory could not be verified") from error
    if completed.returncode == 1 and not completed.stdout.strip() and not completed.stderr.strip():
        return set()
    if completed.returncode != 0:
        raise RuntimeError_("Native TCP listener inventory could not be verified")
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        match = re.fullmatch(r"([1-9][0-9]*)", line)
        if match is None:
            raise RuntimeError_("Native TCP listener inventory response was invalid")
        pids.add(int(match.group(1)))
    return pids


def process_group_tcp_listener_pids(guard_pid: int) -> set[int]:
    if guard_pid <= 1:
        raise RuntimeError_("Native process-group ownership is invalid")
    values: set[int] = set()
    for pid in all_tcp_listener_pids():
        try:
            if os.getpgid(pid) == guard_pid:
                values.add(pid)
        except OSError:
            continue
    return values


def processes_using_native_mutable_state(support: Path, *, timeout: float = 10.0) -> set[int]:
    """Find open handles below every live root; stale/missing pid files cannot bypass this proof."""
    pids: set[int] = set()
    deadline = time.monotonic() + max(1.0, min(float(timeout), 30.0))
    for relative in NATIVE_RESTORE_ROOTS:
        path = support / relative
        if not path.exists() or path.is_symlink():
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError_("Native restore quiescence inspection timed out")
        command = ["/usr/sbin/lsof", "-nP", "-t"]
        if path.is_dir():
            command.extend(["+D", str(path)])
        else:
            command.extend(["--", str(path)])
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=remaining,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError_("Native restore quiescence could not be proven") from error
        if completed.returncode == 1 and not completed.stdout.strip():
            continue
        if completed.returncode != 0:
            raise RuntimeError_("Native restore quiescence could not be proven")
        for line in completed.stdout.splitlines():
            if re.fullmatch(r"[1-9][0-9]*", line) is None:
                raise RuntimeError_("Native restore quiescence response was invalid")
            pids.add(int(line))
    return pids


def assert_native_restore_quiesced(
    support: Path,
    root: Path,
    *,
    transaction_id: str,
    timeout: float = 10.0,
) -> None:
    if SAFE_NATIVE_TRANSACTION.fullmatch(transaction_id) is None:
        raise RuntimeError_("Native restore transaction identity is unsafe")
    if any(listener_pids(port) for port in SERVICE_PORTS["frontend-proxy"]):
        raise RuntimeError_("Native restore cannot activate while a web listener remains")
    socket_paths = [
        native_api_socket_path(support),
        mongodb_socket_path(support),
        support / "runtime" / f"nr-{transaction_id[:8]}.sock",
    ]
    if any(unix_socket_pids(path) for path in socket_paths):
        raise RuntimeError_("Native restore cannot activate while a private service remains")
    for service in (*SERVICE_ORDER, "native-restore-staging"):
        if live_pid(pid_path(support, service), root, quarantine_invalid=False) is not None:
            raise RuntimeError_("Native restore cannot activate while an owned service remains")
    if processes_using_native_mutable_state(support, timeout=timeout):
        raise RuntimeError_("Native restore mutable state is not quiescent")


def assert_native_snapshot_capture_state(support: Path, root: Path) -> None:
    mongo_guard = require_owned_service("mongodb", support, root)
    if any(listener_pids(port) for port in SERVICE_PORTS["frontend-proxy"]) or unix_socket_pids(
        native_api_socket_path(support)
    ):
        raise RuntimeError_("Native snapshot could not quiesce web writes")
    mongo_listeners = unix_socket_pids(mongodb_socket_path(support))
    if not listeners_owned_by_guard(mongo_listeners, mongo_guard):
        raise RuntimeError_("Native snapshot MongoDB ownership changed")
    if process_group_tcp_listener_pids(mongo_guard):
        raise RuntimeError_("Native snapshot MongoDB unexpectedly exposed TCP")


def validate_coherent_service_state(snapshot: dict[str, int | None]) -> set[str]:
    running = {name for name, pid in snapshot.items() if pid is not None}
    allowed = [set(), {"mongodb"}, set(SERVICE_ORDER)]
    if running not in allowed:
        raise RuntimeError_("Native runtime service state is inconsistent; repair it before continuity work")
    return running


def restore_exact_service_state(
    support: Path,
    root: Path,
    prior: dict[str, int | None],
    *,
    timeout: float,
) -> None:
    wanted = validate_coherent_service_state(prior)
    if wanted == set(SERVICE_ORDER):
        start(
            type("StartArgs", (), {"app_support_dir": support, "timeout": timeout})(),
            _lock_held=True,
            _allow_pending_restore=True,
        )
    elif wanted == {"mongodb"}:
        if owned_mongodb_socket_pid(support, root) is None:
            # start() is the only supported dependency-aware launcher; converge
            # back to Mongo-only immediately after it establishes ownership.
            start(
                type("StartArgs", (), {"app_support_dir": support, "timeout": timeout})(),
                _lock_held=True,
                _allow_pending_restore=True,
            )
        stop_service("frontend-proxy", support, root)
        stop_service("librechat", support, root)
    else:
        for service in reversed(SERVICE_ORDER):
            stop_service(service, support, root)
    observed = guard_pid_snapshot(support, root)
    if {name for name, pid in observed.items() if pid is not None} != wanted:
        raise RuntimeError_("Native continuity could not restore the exact prior service state")


def listeners_owned_by_guard(listeners: set[int], guard_pid: int) -> bool:
    if not listeners or guard_pid <= 1:
        return False
    try:
        return all(pid > 1 and os.getpgid(pid) == guard_pid for pid in listeners)
    except OSError:
        return False


def preflight_service_ports(support: Path, root: Path) -> None:
    """Refuse to start before mutation when a required port is foreign or ambiguous."""
    for service, ports in SERVICE_PORTS.items():
        owned_pid = live_pid(
            pid_path(support, service), root, quarantine_invalid=False
        )
        for port in ports:
            listeners = listener_pids(port)
            if listeners and (
                owned_pid is None or not listeners_owned_by_guard(listeners, owned_pid)
            ):
                raise RuntimeError_(
                    f"Native port {port} ({service}) is already in use by another process; "
                    "no changes were made"
                )


def unix_socket_pids(path: Path) -> set[int]:
    """Return processes holding one exact Unix socket path, or fail closed."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return set()
    except OSError as error:
        raise RuntimeError_("Native Unix socket ownership could not be verified") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISSOCK(metadata.st_mode):
        raise RuntimeError_("Native Unix socket ownership could not be verified")
    try:
        completed = subprocess.run(
            ["/usr/sbin/lsof", "-nP", "-a", "-U", "-t", "--", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError_("Native Unix socket ownership could not be verified") from error
    if completed.returncode == 1 and not completed.stdout.strip():
        if not completed.stderr.strip():
            return set()
        try:
            path.lstat()
        except FileNotFoundError:
            return set()
        except OSError as error:
            raise RuntimeError_("Native Unix socket ownership could not be verified") from error
    if completed.returncode != 0:
        raise RuntimeError_("Native Unix socket ownership could not be verified")
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        match = re.fullmatch(r"([1-9][0-9]*)", line)
        if match is None:
            raise RuntimeError_("Native Unix socket ownership response was invalid")
        pids.add(int(match.group(1)))
    return pids


def private_socket_metadata(path: Path, label: str) -> os.stat_result | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise RuntimeError_(f"Native {label} socket is unavailable") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISSOCK(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise RuntimeError_(f"Native {label} socket path is unsafe")
    return metadata


def api_socket_metadata(support: Path) -> os.stat_result | None:
    return private_socket_metadata(native_api_socket_path(support), "API")


def mongodb_socket_metadata(support: Path) -> os.stat_result | None:
    return private_socket_metadata(mongodb_socket_path(support), "MongoDB")


def preflight_private_socket(
    support: Path,
    root: Path,
    *,
    service: str,
    path: Path,
    label: str,
) -> None:
    """Reject a foreign socket and remove only a proven stale owned socket."""
    validate_native_socket_lengths(support)
    ensure_support_directories(support, "runtime")
    if private_socket_metadata(path, label) is None:
        return
    listeners = unix_socket_pids(path)
    guard_pid = live_pid(pid_path(support, service), root, quarantine_invalid=False)
    if listeners:
        if guard_pid is None or not listeners_owned_by_guard(listeners, guard_pid):
            raise RuntimeError_(f"Native {label} socket is already owned by another process")
        return
    path.unlink()


def preflight_api_socket(support: Path, root: Path) -> None:
    preflight_private_socket(
        support,
        root,
        service="librechat",
        path=native_api_socket_path(support),
        label="API",
    )


def preflight_mongodb_socket(support: Path, root: Path) -> None:
    preflight_private_socket(
        support,
        root,
        service="mongodb",
        path=mongodb_socket_path(support),
        label="MongoDB",
    )


def owned_private_socket_pid(
    support: Path,
    root: Path,
    *,
    service: str,
    path: Path,
    label: str,
) -> int | None:
    pid = live_pid(pid_path(support, service), root, quarantine_invalid=False)
    if pid is None or private_socket_metadata(path, label) is None:
        return None
    listeners = unix_socket_pids(path)
    if not listeners_owned_by_guard(listeners, pid):
        return None
    return pid


def owned_api_socket_pid(support: Path, root: Path) -> int | None:
    return owned_private_socket_pid(
        support,
        root,
        service="librechat",
        path=native_api_socket_path(support),
        label="API",
    )


def owned_mongodb_socket_pid(support: Path, root: Path) -> int | None:
    return owned_private_socket_pid(
        support,
        root,
        service="mongodb",
        path=mongodb_socket_path(support),
        label="MongoDB",
    )


def owned_listener_pid(service: str, support: Path, root: Path) -> int | None:
    ports = SERVICE_PORTS[service]
    # Status/health are observational surfaces; only lifecycle cleanup may
    # quarantine a stale record.
    pid = live_pid(pid_path(support, service), root, quarantine_invalid=False)
    if pid is None or any(
        not listeners_owned_by_guard(listener_pids(port), pid) for port in ports
    ):
        return None
    return pid


def owned_service_pid(service: str, support: Path, root: Path) -> int | None:
    if service == "mongodb":
        return owned_mongodb_socket_pid(support, root)
    if service == "librechat":
        return owned_api_socket_pid(support, root)
    return owned_listener_pid(service, support, root)


def guard_pid_snapshot(support: Path, root: Path) -> dict[str, int | None]:
    return {
        service: live_pid(
            pid_path(support, service), root, quarantine_invalid=False
        )
        for service in SERVICE_ORDER
    }


def require_owned_service(service: str, support: Path, root: Path) -> int:
    pid = owned_service_pid(service, support, root)
    if pid is None:
        raise RuntimeError_(
            f"Native {service} ownership changed; refusing to access another process"
        )
    return pid


def stop_attempt_services(
    support: Path,
    root: Path,
    preexisting: dict[str, int | None],
    attempted: set[str] | None = None,
) -> None:
    """Drain only guards that were not present before this lifecycle attempt."""
    for service in reversed(SERVICE_ORDER):
        if preexisting.get(service) is None and (
            attempted is None or service in attempted
        ):
            stop_service(service, support, root)


def spawn(service: str, command: list[str], support: Path, *, cwd: Path, env: dict[str, str]) -> None:
    validate_support_children(support)
    ensure_support_directories(support, "logs", "runtime")
    root = release_root()
    record_path = pid_path(support, service)
    existing = live_pid(record_path, root)
    if existing is not None:
        return
    token = secrets.token_hex(32)
    guard_command = [
        str(root / "runtime" / "python" / "bin" / "python3"),
        "-E",
        "-s",
        "-B",
        str(root / "runtime" / "scripts" / "native_process_guard.py"),
        "--token",
        token,
        "--",
        *command,
    ]
    log_path = support / "logs" / f"{service}.log"
    rotate_log(log_path)
    process: subprocess.Popen[bytes] | None = None
    try:
        with log_path.open("ab", buffering=0) as log:
            process = subprocess.Popen(
                guard_command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        started = None
        for _ in range(40):
            started = process_value(process.pid, "lstart")
            if started is not None:
                break
            if process.poll() is not None:
                break
            time.sleep(0.025)
        if started is None or process.poll() is not None:
            raise RuntimeError_(f"Native service exited during launch: {service}")
        record = {
            "schema_version": 1,
            "pid": process.pid,
            "token": token,
            "process_start": started,
            "interpreter_sha256": executable_digest(root / "runtime" / "python" / "bin" / "python3"),
            "release_root": str(root),
            "service": service,
        }
        write_atomic(record_path, json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        if live_pid(record_path, root) != process.pid:
            raise RuntimeError_(f"Native service ownership verification failed: {service}")
    except BaseException:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if process is not None and record.get("pid") == process.pid:
                record_path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError):
            pass
        raise


def rotate_log(path: Path, *, maximum_bytes: int = 10 * 1024 * 1024, generations: int = 3) -> None:
    if path.exists() or path.is_symlink():
        metadata = path.lstat()
        if path.is_symlink() or not path.is_file() or metadata.st_uid != os.getuid():
            raise RuntimeError_(f"Native log path is unsafe: {path.name}")
        if metadata.st_size < maximum_bytes:
            return
    for generation in range(generations, 0, -1):
        source = path if generation == 1 else path.with_name(f"{path.name}.{generation - 1}")
        destination = path.with_name(f"{path.name}.{generation}")
        if destination.exists():
            destination.unlink()
        if source.exists():
            os.replace(source, destination)


def semantic_http_ready(
    url: str,
    expected_release: str | None = None,
    expected_sha256: str | None = None,
) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port not in {3190, 3191}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (expected_sha256 is None and port != 3190)
        or (expected_sha256 is not None and (port != 3191 or parsed.path != "/index.html"))
    ):
        return False
    try:
        # Only the exact app-owned loopback HTTP ports pass the validation above.
        with urllib.request.urlopen(  # nosec B310
            url, timeout=1
        ) as response:
            if response.status >= 500:
                return False
            if expected_sha256 is not None:
                body = response.read(1024 * 1024 + 1)
                return (
                    len(body) <= 1024 * 1024
                    and hashlib.sha256(body).hexdigest() == expected_sha256
                )
            if expected_release is not None:
                value = json.loads(response.read())
                return value == {"release": expected_release, "status": "ok"}
            return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def semantic_unix_http_ready(path: Path, request_path: str = "/api/config") -> bool:
    if not request_path.startswith("/") or "\r" in request_path or "\n" in request_path:
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1)
            connection.connect(str(path))
            connection.sendall(
                f"GET {request_path} HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode(
                    "ascii"
                )
            )
            status_line = b""
            while b"\r\n" not in status_line and len(status_line) <= 4096:
                chunk = connection.recv(512)
                if not chunk:
                    break
                status_line += chunk
        match = re.match(rb"HTTP/1\.[01] ([1-5][0-9]{2}) ", status_line)
        return match is not None and int(match.group(1)) < 500
    except OSError:
        return False


def wait_owned_api_socket(support: Path, root: Path, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    path = native_api_socket_path(support)
    while time.monotonic() < deadline:
        pid = owned_api_socket_pid(support, root)
        if pid is not None:
            path.chmod(0o600)
            if semantic_unix_http_ready(path):
                time.sleep(0.25)
                if (
                    owned_api_socket_pid(support, root) == pid
                    and stat.S_IMODE(path.lstat().st_mode) == 0o600
                    and semantic_unix_http_ready(path)
                ):
                    return True
        time.sleep(0.1)
    return False


def semantic_unix_socket_ready(path: Path) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1)
            connection.connect(str(path))
        return True
    except OSError:
        return False


def wait_owned_mongodb_socket(support: Path, root: Path, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    path = mongodb_socket_path(support)
    while time.monotonic() < deadline:
        pid = owned_mongodb_socket_pid(support, root)
        if pid is not None:
            tcp_listeners = process_group_tcp_listener_pids(pid)
            if tcp_listeners:
                raise RuntimeError_("Native MongoDB must not expose a TCP listener")
            path.chmod(0o600)
            if semantic_unix_socket_ready(path):
                time.sleep(0.25)
                if (
                    owned_mongodb_socket_pid(support, root) == pid
                    and not process_group_tcp_listener_pids(pid)
                    and stat.S_IMODE(path.lstat().st_mode) == 0o600
                    and semantic_unix_socket_ready(path)
                ):
                    return True
        time.sleep(0.1)
    return False


def wait_owned_service(
    service: str,
    port: int,
    support: Path,
    root: Path,
    timeout: float,
    *,
    semantic_url: str | None = None,
    expected_release: str | None = None,
    expected_sha256: str | None = None,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pid = live_pid(pid_path(support, service), root)
        if pid is None:
            time.sleep(0.1)
            continue
        listeners = listener_pids(port)
        if listeners and not listeners_owned_by_guard(listeners, pid):
            raise RuntimeError_(
                f"TCP listener on port {port} does not belong to {service}; refusing foreign readiness"
            )
        if not listeners_owned_by_guard(listeners, pid):
            time.sleep(0.1)
            continue
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                ready = semantic_url is None or semantic_http_ready(
                    semantic_url, expected_release, expected_sha256
                )
        except OSError:
            ready = False
        if ready:
            time.sleep(0.25)
            if live_pid(pid_path(support, service), root) == pid and (
                listeners_owned_by_guard(listener_pids(port), pid)
                and (
                    semantic_url is None
                    or semantic_http_ready(semantic_url, expected_release, expected_sha256)
                )
            ):
                return True
        time.sleep(0.1)
    return False


def run_native_maintenance(
    label: str,
    command: list[str],
    support: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    required_service: str | None = None,
    root: Path | None = None,
) -> None:
    owned_pid: int | None = None
    if required_service is not None:
        if root is None:
            raise RuntimeError_("Native maintenance ownership policy is incomplete")
        owned_pid = require_owned_service(required_service, support, root)
    log_path = support / "logs" / f"native-{label}.log"
    rotate_log(log_path)
    with log_path.open("ab", buffering=0) as log:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    if required_service is not None and root is not None:
        if require_owned_service(required_service, support, root) != owned_pid:
            raise RuntimeError_(
                f"Native {required_service} ownership changed during maintenance"
            )
    if completed.returncode != 0:
        raise RuntimeError_(f"Native {label.replace('-', ' ')} failed; inspect {log_path.name}")


def verify_default_agent(root: Path, support: Path, env: dict[str, str]) -> None:
    librechat = root / "runtime" / "librechat"
    mongo_uri = mongodb_uri(support)
    run_native_maintenance(
        "default-agent-verification",
        [
            str(root / "runtime" / "node" / "bin" / "node"),
            str(root / "runtime" / "scripts" / "native_verify_agent.js"),
            str(librechat),
            mongo_uri,
            str(root / "runtime" / "defaults" / "viventium-agents.yaml"),
        ],
        support,
        cwd=librechat,
        env=env,
        required_service="mongodb",
        root=root,
    )


def maintain_native_identity(
    root: Path,
    support: Path,
    env: dict[str, str],
    first_admin: dict[str, object],
) -> None:
    """Seed user-owned defaults only after the real first admin exists."""
    if first_admin.get("status") != "closed":
        return
    librechat = root / "runtime" / "librechat"
    run_native_maintenance(
        "user-default-reconciliation",
        [
            str(root / "runtime" / "node" / "bin" / "node"),
            "scripts/viventium-reconcile-user-defaults.js",
        ],
        support,
        cwd=librechat,
        env=env,
        required_service="mongodb",
        root=root,
    )
    run_native_maintenance(
        "default-agent-seed",
        [
            str(root / "runtime" / "node" / "bin" / "node"),
            "scripts/viventium-seed-agents.js",
            f"--bundle={root / 'runtime' / 'defaults' / 'viventium-agents.yaml'}",
            "--public",
        ],
        support,
        cwd=librechat,
        env=env,
        required_service="mongodb",
        root=root,
    )
    verify_default_agent(root, support, env)


def start(
    args: argparse.Namespace,
    *,
    _lock_held: bool = False,
    _allow_pending_restore: bool = False,
) -> None:
    support = lexical_support(args.app_support_dir)
    if not _lock_held:
        with lifecycle_lock(support):
            start(args, _lock_held=True)
        return
    validate_support_children(support)
    state = runtime_state(support)
    root = Path(str(state["release_root"])).resolve()
    if root != release_root():
        raise RuntimeError_("Installed release pointer does not match this payload")
    packaged_health(root)
    if not _allow_pending_restore:
        recover_native_restore_before_lifecycle(support, root)
    metadata = build_metadata(root)
    sandpack_index_sha256 = str(metadata["sandpack_index_sha256"])
    preflight_service_ports(support, root)
    preflight_mongodb_socket(support, root)
    preflight_api_socket(support, root)
    preexisting = guard_pid_snapshot(support, root)
    attempted: set[str] = set()
    try:
        first_admin = ensure_first_admin_state(support)
        mongo_uri = mongodb_uri(support)
        env = native_child_environment(support)
        env.update(runtime_secrets(support))
        env.update(
            {
                "NODE_ENV": "production",
                "NODE_OPTIONS": "--max-old-space-size=1024",
                "HOST": "127.0.0.1",
                "PORT": "3180",
                "VIVENTIUM_NATIVE_API_SOCKET": str(native_api_socket_path(support)),
                "MONGO_URI": mongo_uri,
                "CONFIG_PATH": str(root / "runtime" / "defaults" / "librechat.yaml"),
                "VIVENTIUM_PROMPT_BUNDLE_PATH": str(root / "runtime" / "defaults" / "prompt-bundle.json"),
                "ALLOW_REGISTRATION": "true" if first_admin["status"] == "open" else "false",
                "VIVENTIUM_BOOTSTRAP_REGISTRATION_ONCE": "true",
                "ALLOW_UNVERIFIED_EMAIL_LOGIN": "true",
                "DOMAIN_CLIENT": "http://127.0.0.1:3190",
                "DOMAIN_SERVER": "http://127.0.0.1:3190",
                "VIVENTIUM_CONNECTED_ACCOUNTS_RETURN_ORIGIN": "http://127.0.0.1:3190",
                "VIVENTIUM_INSTALL_EXPERIENCE": "express",
                "VIVENTIUM_NATIVE_RELEASE_ROOT": str(root),
                "VIVENTIUM_NATIVE_RELEASE_ID": str(metadata["source_commit"]),
                "VIVENTIUM_APP_SUPPORT_DIR": str(support),
                "VIVENTIUM_NATIVE_FIRST_ADMIN_STATE": str(support / "state" / "native-first-admin.json"),
                "VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET": str(native_api_socket_path(support)),
                "VIVENTIUM_NATIVE_PROXY_LISTEN_PORT": "3190",
                "VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT": "3191",
                "VIVENTIUM_NATIVE_SANDPACK_INDEX_SHA256": sandpack_index_sha256,
                "VIVENTIUM_NATIVE_SANDPACK_ROOT": str(
                    root / "runtime" / "librechat" / "client" / "dist" / "sandpack-bundler"
                ),
                "VIVENTIUM_NATIVE_REGISTRATION_CLOSE_HOOK": str(
                    root / "bin" / "viventium-native-registration-close"
                ),
            }
        )
        spawn(
            "mongodb",
            [
                str(root / "runtime" / "mongodb" / "bin" / "mongod"),
                "--bind_ip", str(mongodb_socket_path(support)),
                "--port", "27117",
                "--nounixsocket",
                "--filePermissions", "0600",
                "--dbpath", str(support / "data" / "mongodb"),
                "--wiredTigerCacheSizeGB", "0.5",
                "--quiet",
            ],
            support,
            cwd=support,
            env=env,
        )
        if preexisting["mongodb"] is None:
            attempted.add("mongodb")
        if not wait_owned_mongodb_socket(support, root, args.timeout):
            raise RuntimeError_("Bundled MongoDB did not become ready")
        librechat = root / "runtime" / "librechat"
        run_native_maintenance(
            "first-admin-recovery",
            [
                str(root / "runtime" / "node" / "bin" / "node"),
                str(root / "runtime" / "scripts" / "native_first_admin_recovery.js"),
                str(support / "state" / "native-first-admin.json"),
                str(librechat),
                mongo_uri,
            ],
            support,
            cwd=librechat,
            env=env,
            required_service="mongodb",
            root=root,
        )
        first_admin = ensure_first_admin_state(support)
        env["ALLOW_REGISTRATION"] = "true" if first_admin["status"] == "open" else "false"
        maintain_native_identity(root, support, env, first_admin)
        spawn(
            "librechat",
            [str(root / "runtime" / "node" / "bin" / "node"), "api/server/index.js"],
            support,
            cwd=librechat,
            env=env,
        )
        if preexisting["librechat"] is None:
            attempted.add("librechat")
        if not wait_owned_api_socket(support, root, args.timeout):
            raise RuntimeError_("Bundled LibreChat did not become ready")
        spawn(
            "frontend-proxy",
            [str(root / "runtime" / "node" / "bin" / "node"), str(root / "runtime" / "proxy.js")],
            support,
            cwd=root,
            env=env,
        )
        if preexisting["frontend-proxy"] is None:
            attempted.add("frontend-proxy")
        if not wait_owned_service(
            "frontend-proxy",
            3190,
            support,
            root,
            args.timeout,
            semantic_url="http://127.0.0.1:3190/__viventium_native_health",
            expected_release=str(metadata["source_commit"]),
        ):
            raise RuntimeError_("Native web proxy did not become ready")
        if not wait_owned_service(
            "frontend-proxy",
            3191,
            support,
            root,
            args.timeout,
            semantic_url="http://127.0.0.1:3191/index.html",
            expected_sha256=sandpack_index_sha256,
        ):
            raise RuntimeError_("Native isolated artifact runtime did not become ready")
    except BaseException:
        stop_attempt_services(support, root, preexisting, attempted)
        raise
    print("Viventium Native is ready at http://127.0.0.1:3190")


def stop_service(service: str, support: Path, root: Path) -> None:
    path = pid_path(support, service)
    pid = live_pid(path, root)
    if pid is not None:
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            pass
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and live_pid(path, root) == pid:
            time.sleep(0.1)
        if live_pid(path, root) == pid:
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                pass
    path.unlink(missing_ok=True)
    socket_path = {
        "librechat": native_api_socket_path(support),
        "mongodb": mongodb_socket_path(support),
    }.get(service)
    if socket_path is not None:
        label = "API" if service == "librechat" else "MongoDB"
        if private_socket_metadata(socket_path, label) is not None and not unix_socket_pids(
            socket_path
        ):
            socket_path.unlink()


def stop(args: argparse.Namespace, *, _lock_held: bool = False) -> None:
    support = lexical_support(args.app_support_dir)
    if not _lock_held:
        with lifecycle_lock(support):
            stop(args, _lock_held=True)
        return
    validate_support_children(support)
    root = installed_release_root(support, allow_missing=True)
    if native_restore_journal_path(support).exists() or native_restore_journal_path(support).is_symlink():
        recover_native_restore_before_lifecycle(support, root)
    for service in ("frontend-proxy", "librechat", "mongodb"):
        stop_service(service, support, root)


def registration_close(args: argparse.Namespace) -> None:
    support = lexical_support(args.app_support_dir)
    with lifecycle_lock(support):
        validate_support_children(support)
        root = installed_release_root(support)
        recover_native_restore_before_lifecycle(support, root)
        if ensure_first_admin_state(support)["status"] != "closed":
            raise RuntimeError_("Native registration close reload requires a closed first-admin state")
        stop_service("librechat", support, root)
        start(args, _lock_held=True)


def health(args: argparse.Namespace) -> None:
    root = release_root()
    packaged_health(root)
    support = lexical_support(args.app_support_dir)
    validate_support_children(support)
    reject_pending_restore_for_read(support)
    if args.installed_only:
        state = runtime_state(support)
        if Path(str(state["release_root"])).resolve() != root:
            raise RuntimeError_("Installed release pointer does not match this payload")
        return
    state_path = support / "state" / "native-runtime.json"
    if not state_path.exists():
        return
    for service in SERVICE_ORDER:
        owned = owned_service_pid(service, support, root)
        if owned is None:
            raise RuntimeError_(f"Native service is not running: {service}")
    if not semantic_unix_http_ready(native_api_socket_path(support), "/api/health"):
        raise RuntimeError_("Native LibreChat API did not pass its semantic health probe")
    metadata = build_metadata(root)
    release_id = str(metadata["source_commit"])
    sandpack_index_sha256 = str(metadata["sandpack_index_sha256"])
    if not semantic_http_ready(
        "http://127.0.0.1:3190/__viventium_native_health", release_id
    ):
        raise RuntimeError_("Native web surface does not belong to the active release")
    if not semantic_http_ready(
        "http://127.0.0.1:3191/index.html", expected_sha256=sandpack_index_sha256
    ):
        raise RuntimeError_("Native isolated artifact runtime failed its semantic health probe")
    if ensure_first_admin_state(support)["status"] == "closed":
        verify_default_agent(root, support, native_child_environment(support))


def status(args: argparse.Namespace) -> None:
    support = lexical_support(args.app_support_dir)
    validate_support_children(support)
    reject_pending_restore_for_read(support)
    root = release_root()
    result = {
        service: owned_service_pid(service, support, root)
        for service in SERVICE_ORDER
    }
    print(json.dumps(result, sort_keys=True))
    if not all(result.values()):
        raise RuntimeError_("Native runtime is not fully running")


def doctor(args: argparse.Namespace) -> None:
    health(type("HealthArgs", (), {"app_support_dir": args.app_support_dir, "installed_only": False})())
    print(json.dumps({"schema_version": 1, "healthy": True}, sort_keys=True))


def configure(args: argparse.Namespace) -> None:
    reject_pending_restore_for_read(lexical_support(args.app_support_dir))
    if args.print_path:
        print(release_root() / "runtime" / "defaults" / "librechat.yaml")
        return
    raise RuntimeError_(
        "Native runtime settings are immutable in this candidate; editing config.yaml would not affect the running service"
    )


def password_reset_link(args: argparse.Namespace, *, _lock_held: bool = False) -> None:
    """Issue a short-lived local reset link without enabling public password reset."""
    email = str(args.email).strip()
    if (
        not email
        or len(email) > 320
        or any(character.isspace() or ord(character) < 32 for character in email)
    ):
        raise RuntimeError_("A valid account email is required for password recovery")

    support = lexical_support(args.app_support_dir)
    if not _lock_held:
        with lifecycle_lock(support):
            password_reset_link(args, _lock_held=True)
        return
    validate_support_children(support)
    state = runtime_state(support)
    root = Path(str(state["release_root"])).resolve()
    if root != release_root():
        raise RuntimeError_("Installed release pointer does not match this payload")
    packaged_health(root)

    librechat = root / "runtime" / "librechat"
    script = librechat / "config" / "issue-password-reset-link.js"
    if not script.is_file() or script.is_symlink():
        raise RuntimeError_("Bundled Native password-reset helper is unavailable")

    # Password recovery must also work after a reboot or manual stop. Starting is
    # idempotent for an already healthy Native runtime and does not open a browser.
    start(
        type(
            "StartArgs",
            (),
            {"app_support_dir": support, "timeout": args.timeout},
        )(),
        _lock_held=True,
    )
    environment = native_child_environment(support)
    environment.update(runtime_secrets(support))
    mongo_uri = mongodb_uri(support)
    environment.update(
        {
            "MONGO_URI": mongo_uri,
            "DOMAIN_CLIENT": "http://127.0.0.1:3190",
        }
    )
    owned_mongodb = require_owned_service("mongodb", support, root)
    completed = subprocess.run(
        [
            str(root / "runtime" / "node" / "bin" / "node"),
            str(script),
            "--email",
            email,
        ],
        cwd=librechat,
        env=environment,
        check=False,
    )
    if require_owned_service("mongodb", support, root) != owned_mongodb:
        raise RuntimeError_("Native mongodb ownership changed during password recovery")
    if completed.returncode != 0:
        raise RuntimeError_("Native password-reset link could not be issued")


def upgrade(args: argparse.Namespace) -> None:
    reject_pending_restore_for_read(lexical_support(args.app_support_dir))
    if args.check:
        result = {
            "schema_version": 1,
            "ready_to_upgrade": False,
            "update_available": False,
            "blockers": ["native_signed_bootstrap_required"],
            "commits_behind": 0,
            "component_refresh_required": [],
        }
        print(json.dumps(result, sort_keys=True))
        return
    raise RuntimeError_(
        "Native upgrades require a freshly verified signed Viventium Bootstrap; in-place source updates are forbidden"
    )


NATIVE_RESTORE_ROOTS = (
    "config.yaml",
    "data/mongodb",
    "data/uploads",
    "state/runtime/native/scheduling",
    "state/runtime/native/continuity",
)
NATIVE_RESTORE_LABELS = {
    "config.yaml": "config",
    "data/mongodb": "mongodb",
    "data/uploads": "uploads",
    "state/runtime/native/scheduling": "schedules",
    "state/runtime/native/continuity": "continuity",
}
SAFE_NATIVE_TRANSACTION = re.compile(r"^[0-9a-f]{32}$")
SAFE_NATIVE_RELEASE = re.compile(r"^[0-9a-f]{40}$")
NATIVE_CONTINUITY_MAX_BYTES = 512 * 1024 * 1024 * 1024
NATIVE_CONTINUITY_MAX_FILES = 5_000_000
NATIVE_CONTINUITY_MIN_FREE_RESERVE = 512 * 1024 * 1024
NATIVE_RESTORE_JOURNAL_MAX_BYTES = 1024 * 1024


def load_continuity_module(root: Path):
    path = root / "runtime" / "scripts" / "continuity_bundle.py"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError_("Bundled Native continuity validator is unavailable")
    spec = importlib.util.spec_from_file_location(
        f"viventium_native_continuity_{hashlib.sha256(os.fsencode(path)).hexdigest()}",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError_("Bundled Native continuity validator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_restore_journal_path(support: Path) -> Path:
    return support / "state" / "native-restore-transaction.json"


def reject_pending_restore_for_read(support: Path) -> None:
    path = native_restore_journal_path(support)
    if path.exists() or path.is_symlink():
        raise RuntimeError_(
            "Native restore recovery is pending; run a mutating lifecycle command from the installed release first"
        )


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_existing_directories(*paths: Path) -> None:
    seen: set[Path] = set()
    for path in paths:
        if path in seen or not path.is_dir() or path.is_symlink():
            continue
        seen.add(path)
        fsync_directory(path)


def durable_replace(source: Path, destination: Path, *transaction_dirs: Path) -> None:
    """Rename durably across both directory entries before journal advancement."""
    source_parent = source.parent
    destination_parent = destination.parent
    os.replace(source, destination)
    fsync_existing_directories(
        source_parent,
        destination_parent,
        *transaction_dirs,
    )


def durable_unlink(path: Path, *transaction_dirs: Path) -> None:
    parent = path.parent
    path.unlink()
    fsync_existing_directories(parent, *transaction_dirs)


def bounded_private_tree_size(path: Path, *, deadline: float) -> tuple[int, int]:
    return validate_owner_private_tree(
        path,
        allow_missing=True,
        deadline=deadline,
        maximum_entries=NATIVE_CONTINUITY_MAX_FILES,
        maximum_bytes=NATIVE_CONTINUITY_MAX_BYTES,
    )


def preflight_native_restore_capacity(snapshot: Path, support: Path, *, timeout: float) -> None:
    current = snapshot
    while True:
        try:
            metadata = current.lstat()
        except OSError as error:
            raise RuntimeError_("Native restore snapshot path is unavailable") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError_("Native restore snapshot path contains a symlink boundary")
        if current.parent == current:
            break
        current = current.parent
    deadline = time.monotonic() + max(1.0, min(float(timeout), 300.0))
    snapshot_bytes, snapshot_files = bounded_private_tree_size(snapshot, deadline=deadline)
    active_bytes = 0
    active_files = 0
    for relative in NATIVE_RESTORE_ROOTS:
        size, count = bounded_private_tree_size(support / relative, deadline=deadline)
        active_bytes += size
        active_files += count
    if snapshot_files + active_files > NATIVE_CONTINUITY_MAX_FILES:
        raise RuntimeError_("Native restore input contains too many files")
    # Staging can temporarily hold the logical bundle, expanded Mongo state, and a
    # complete prior checkpoint. A 2x snapshot allowance plus current state is a
    # bounded conservative preflight; exact adapter expansion remains separately capped.
    required = snapshot_bytes * 2 + active_bytes + NATIVE_CONTINUITY_MIN_FREE_RESERVE
    try:
        free = shutil.disk_usage(support).free
    except OSError as error:
        raise RuntimeError_("Native restore disk capacity could not be verified") from error
    if free < required:
        raise RuntimeError_("Native restore needs more free disk space before staging")


def preflight_native_restore_expansion_capacity(
    manifest: dict[str, object], support: Path
) -> None:
    """Reserve space for validated archive expansion after the private input copy."""
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError_("Native snapshot artifact metadata is invalid")
    expanded_bytes = 0
    for item in artifacts:
        if not isinstance(item, dict):
            raise RuntimeError_("Native snapshot artifact metadata is invalid")
        stored_size = item.get("size")
        declared_size = item.get("uncompressedSize", stored_size)
        if (
            isinstance(stored_size, bool)
            or not isinstance(stored_size, int)
            or stored_size < 0
            or isinstance(declared_size, bool)
            or not isinstance(declared_size, int)
            or declared_size < 0
        ):
            raise RuntimeError_("Native snapshot artifact size metadata is invalid")
        expanded_bytes += max(stored_size, declared_size)
        if expanded_bytes > NATIVE_CONTINUITY_MAX_BYTES:
            raise RuntimeError_("Native snapshot expansion exceeds the supported byte bound")
    # The private bundle is already charged to disk when this runs. Preserve room
    # for extracted data plus transient database import/index overhead and a
    # minimum operating reserve before any adapter starts writing staged state.
    required = expanded_bytes * 2 + NATIVE_CONTINUITY_MIN_FREE_RESERVE
    try:
        free = shutil.disk_usage(support).free
    except OSError as error:
        raise RuntimeError_("Native restore expansion capacity could not be verified") from error
    if free < required:
        raise RuntimeError_("Native restore needs more free disk space before expansion")


def validate_owner_private_tree(
    path: Path,
    *,
    allow_missing: bool = False,
    deadline: float | None = None,
    maximum_entries: int | None = None,
    maximum_bytes: int | None = None,
) -> tuple[int, int]:
    def enforce_bound(entries: int, size: int) -> None:
        if deadline is not None and time.monotonic() > deadline:
            raise RuntimeError_("Native continuity filesystem inspection timed out")
        if maximum_entries is not None and entries > maximum_entries:
            raise RuntimeError_("Native continuity input contains too many entries")
        if maximum_bytes is not None and size > maximum_bytes:
            raise RuntimeError_("Native continuity input exceeds the supported byte bound")

    if not path.exists() and not path.is_symlink():
        if allow_missing:
            return 0, 0
        raise RuntimeError_(f"Native restore path is missing: {path.name}")
    try:
        root_metadata = path.lstat()
    except OSError as error:
        raise RuntimeError_(f"Native restore path is unsafe: {path.name}") from error
    if (
        stat.S_ISLNK(root_metadata.st_mode)
        or root_metadata.st_uid != os.getuid()
        or root_metadata.st_mode & 0o077
    ):
        raise RuntimeError_(f"Native restore path has unsafe ownership or permissions: {path.name}")
    if stat.S_ISREG(root_metadata.st_mode):
        if root_metadata.st_nlink != 1:
            raise RuntimeError_(f"Native restore path is hard-linked: {path.name}")
        enforce_bound(1, root_metadata.st_size)
        return root_metadata.st_size, 1
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError_(f"Native restore path is unsafe: {path.name}")
    entries = 1
    size = 0
    enforce_bound(entries, size)
    for current, directories, files in os.walk(path, topdown=True, followlinks=False):
        enforce_bound(entries, size)
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if (
            stat.S_ISLNK(current_metadata.st_mode)
            or not stat.S_ISDIR(current_metadata.st_mode)
            or current_metadata.st_uid != os.getuid()
            or current_metadata.st_mode & 0o077
        ):
            raise RuntimeError_("Native restore tree contains an unsafe directory")
        for name in [*directories, *files]:
            child = current_path / name
            metadata = child.lstat()
            entries += 1
            if name in files:
                size += metadata.st_size
            enforce_bound(entries, size)
            if (
                stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o077
            ):
                raise RuntimeError_("Native restore tree contains a symlink or unsafe permissions")
            if name in files and (
                not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            ):
                raise RuntimeError_("Native restore tree contains a special or hard-linked file")
    return size, entries


def make_tree_owner_private(path: Path) -> None:
    if not path.exists() or path.is_symlink():
        return
    for current, directories, files in os.walk(path, topdown=False, followlinks=False):
        current_path = Path(current)
        for name in files:
            child = current_path / name
            metadata = child.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError_("Native restore staging tree contains an unsafe entry")
            child.chmod(0o600)
        for name in directories:
            child = current_path / name
            metadata = child.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise RuntimeError_("Native restore staging tree contains an unsafe entry")
            child.chmod(0o700)
        current_path.chmod(0o700)


def remove_owner_private_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    validate_owner_private_tree(path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_private_file(source: Path, destination: Path) -> None:
    validate_owner_private_tree(source)
    expected = source.lstat()
    ensure_private_directory(destination.parent)
    source_descriptor = os.open(
        source,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        opened = os.fstat(source_descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.getuid()
            or opened.st_nlink != 1
            or opened.st_mode & 0o077
            or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (expected.st_dev, expected.st_ino, expected.st_size, expected.st_mtime_ns)
        ):
            raise RuntimeError_("Native restore source changed before private staging")
        destination_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(source_descriptor, "rb") as source_handle, os.fdopen(
            destination_descriptor, "wb"
        ) as target:
            source_descriptor = -1
            shutil.copyfileobj(source_handle, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
            after = os.fstat(source_handle.fileno())
            if (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise RuntimeError_("Native restore source changed during private staging")
    except BaseException:
        Path(destination).unlink(missing_ok=True)
        raise
    finally:
        if source_descriptor >= 0:
            os.close(source_descriptor)


def private_tree_fingerprint(path: Path, *, deadline: float) -> str:
    validate_owner_private_tree(
        path,
        deadline=deadline,
        maximum_entries=NATIVE_CONTINUITY_MAX_FILES,
        maximum_bytes=NATIVE_CONTINUITY_MAX_BYTES,
    )
    digest = hashlib.sha256()
    entries = [path]
    if path.is_dir():
        entries.extend(sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()))
    for entry in entries:
        if time.monotonic() > deadline:
            raise RuntimeError_("Native restore input verification timed out")
        metadata = entry.lstat()
        relative = "." if entry == path else entry.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.S_IMODE(metadata.st_mode)).encode("ascii"))
        digest.update(b"\0")
        if stat.S_ISREG(metadata.st_mode):
            descriptor = os.open(entry, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_uid != os.getuid()
                    or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                    != (
                        metadata.st_dev,
                        metadata.st_ino,
                        metadata.st_size,
                        metadata.st_mtime_ns,
                    )
                ):
                    raise RuntimeError_("Native restore input changed during verification")
                while chunk := os.read(descriptor, 1024 * 1024):
                    if time.monotonic() > deadline:
                        raise RuntimeError_("Native restore input verification timed out")
                    digest.update(chunk)
                after = os.fstat(descriptor)
                if (
                    opened.st_size,
                    opened.st_mtime_ns,
                    opened.st_ctime_ns,
                ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise RuntimeError_("Native restore input changed during verification")
            finally:
                os.close(descriptor)
        elif stat.S_ISDIR(metadata.st_mode):
            digest.update(b"directory")
        else:
            raise RuntimeError_("Native restore input contains an unsafe entry")
        digest.update(b"\0")
    return digest.hexdigest()


def copy_verified_private_tree(
    source: Path,
    destination: Path,
    *,
    timeout: float,
) -> None:
    deadline = time.monotonic() + max(1.0, min(float(timeout), 3600.0))
    before = private_tree_fingerprint(source, deadline=deadline)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError_("Native restore private input stage already exists")
    ensure_private_directory(destination)
    try:
        for current, directories, files in os.walk(source, topdown=True, followlinks=False):
            if time.monotonic() > deadline:
                raise RuntimeError_("Native restore input copy timed out")
            current_path = Path(current)
            relative = current_path.relative_to(source)
            target = destination / relative
            ensure_private_directory(target)
            for name in directories:
                ensure_private_directory(target / name)
            for name in files:
                copy_private_file(current_path / name, target / name)
        make_tree_owner_private(destination)
        source_after = private_tree_fingerprint(source, deadline=deadline)
        copied = private_tree_fingerprint(destination, deadline=deadline)
        if before != source_after or before != copied:
            raise RuntimeError_("Native restore input changed while it was privately staged")
        fsync_existing_directories(destination, destination.parent)
    except BaseException:
        with contextlib.suppress(Exception):
            remove_owner_private_path(destination)
        raise


def read_native_restore_journal(support: Path, *, release_identity: str) -> dict[str, object]:
    path = native_restore_journal_path(support)
    try:
        metadata = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if (
                (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                != (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
                or opened.st_size > NATIVE_RESTORE_JOURNAL_MAX_BYTES
            ):
                raise RuntimeError_("Native restore journal changed during inspection")
            raw = os.read(descriptor, NATIVE_RESTORE_JOURNAL_MAX_BYTES + 1)
            after = os.fstat(descriptor)
            if (
                len(raw) > NATIVE_RESTORE_JOURNAL_MAX_BYTES
                or (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_size,
                    opened.st_mtime_ns,
                    opened.st_ctime_ns,
                )
                != (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                )
            ):
                raise RuntimeError_("Native restore journal changed during inspection")
        finally:
            os.close(descriptor)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError_("Native restore journal is unavailable or invalid") from error
    if not isinstance(payload, dict):
        raise RuntimeError_("Native restore journal is unavailable or invalid")
    transaction_id = payload.get("transactionId")
    expected_stage = f".native-restore-stage.{transaction_id}"
    expected_checkpoint = f"native-restore-{transaction_id}"
    roots = payload.get("roots")
    prior_services = payload.get("priorServices")
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or payload.get("schemaVersion") != 1
        or not isinstance(transaction_id, str)
        or SAFE_NATIVE_TRANSACTION.fullmatch(transaction_id) is None
        or payload.get("releaseIdentity") != release_identity
        or payload.get("stageName") != expected_stage
        or payload.get("checkpointName") != expected_checkpoint
        or set(payload) != {
            "schemaVersion",
            "transactionId",
            "releaseIdentity",
            "stageName",
            "checkpointName",
            "phase",
            "priorServices",
            "roots",
        }
        or not isinstance(prior_services, list)
        or prior_services
        != [service for service in SERVICE_ORDER if service in prior_services]
        or len(set(prior_services)) != len(prior_services)
        or set(prior_services)
        not in (set(), {"mongodb"}, set(SERVICE_ORDER))
        or not isinstance(roots, dict)
        or set(roots) != set(NATIVE_RESTORE_ROOTS)
    ):
        raise RuntimeError_("Native restore journal is unsafe or belongs to another release")
    phase = payload.get("phase")
    if phase not in {
        "staging",
        "activation_pending",
        "activated",
        "rolling_back",
        "rollback_incomplete",
        "service_recovery_pending",
    }:
        raise RuntimeError_("Native restore journal phase is invalid")
    allowed_states = {
        (False, False, False, False),
        (True, False, False, False),
        (True, True, False, False),
        (True, True, True, False),
        (True, True, True, True),
        (False, False, True, False),
        (False, False, True, True),
    }
    observed_states: list[tuple[bool, bool, bool, bool]] = []
    observed_rollback_states: list[str] = []
    for relative in NATIVE_RESTORE_ROOTS:
        row = roots[relative]
        boolean_keys = {
            "priorMovePending",
            "priorMoved",
            "newActivationPending",
            "newActivated",
            "rollbackOwnedNew",
            "rollbackHadPrior",
            "rollbackPreserveActive",
        }
        if (
            not isinstance(row, dict)
            or set(row) != {*boolean_keys, "rollbackState"}
            or any(not isinstance(row.get(key), bool) for key in boolean_keys)
        ):
            raise RuntimeError_(f"Native restore journal root state is invalid: {relative}")
        rollback_state = row.get("rollbackState")
        if rollback_state not in {
            "inactive",
            "ready",
            "new_removal_pending",
            "new_removed",
            "prior_restore_pending",
            "prior_restored",
            "complete",
        }:
            raise RuntimeError_(f"Native restore journal rollback state is invalid: {relative}")
        state = (
            row["priorMovePending"],
            row["priorMoved"],
            row["newActivationPending"],
            row["newActivated"],
        )
        if state not in allowed_states:
            raise RuntimeError_(f"Native restore journal root state is invalid: {relative}")
        rollback_active = phase == "rolling_back" or (
            phase == "rollback_incomplete" and rollback_state != "inactive"
        )
        if rollback_active and rollback_state == "inactive":
            raise RuntimeError_(f"Native restore journal rollback state is invalid: {relative}")
        if not rollback_active and phase != "service_recovery_pending" and (
            rollback_state != "inactive"
            or row["rollbackOwnedNew"]
            or row["rollbackHadPrior"]
            or row["rollbackPreserveActive"]
        ):
            raise RuntimeError_(f"Native restore journal rollback state is invalid: {relative}")
        if phase == "service_recovery_pending" and rollback_state != "complete":
            raise RuntimeError_(f"Native restore journal service recovery state is invalid: {relative}")
        if rollback_state in {"new_removal_pending", "new_removed"} and not row[
            "rollbackOwnedNew"
        ]:
            raise RuntimeError_(f"Native restore journal rollback state is invalid: {relative}")
        if rollback_state in {"prior_restore_pending", "prior_restored"} and not row[
            "rollbackHadPrior"
        ]:
            raise RuntimeError_(f"Native restore journal rollback state is invalid: {relative}")
        if row["rollbackPreserveActive"] and (
            row["rollbackOwnedNew"] or row["rollbackHadPrior"]
        ):
            raise RuntimeError_(f"Native restore journal rollback state is invalid: {relative}")
        observed_states.append(state)
        observed_rollback_states.append(rollback_state)
    untouched = (False, False, False, False)
    complete_states = {
        (True, True, True, True),
        (False, False, True, True),
    }
    saw_incomplete = False
    for state in observed_states:
        if state in complete_states and not saw_incomplete:
            continue
        if state == untouched:
            saw_incomplete = True
            continue
        if saw_incomplete:
            raise RuntimeError_("Native restore journal root sequence is invalid")
        saw_incomplete = True
    if phase == "staging" and any(state != untouched for state in observed_states):
        raise RuntimeError_("Native restore journal staging state is invalid")
    if phase == "activated" and any(state not in complete_states for state in observed_states):
        raise RuntimeError_("Native restore journal activated state is incomplete")
    if phase == "rollback_incomplete" and not (
        all(state == "inactive" for state in observed_rollback_states)
        or all(state != "inactive" for state in observed_rollback_states)
    ):
        raise RuntimeError_("Native restore journal rollback initialization is incomplete")
    return payload


def write_native_restore_journal(support: Path, payload: dict[str, object]) -> None:
    write_atomic(
        native_restore_journal_path(support),
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    )
    transaction_id = payload.get("transactionId")
    if isinstance(transaction_id, str) and SAFE_NATIVE_TRANSACTION.fullmatch(transaction_id):
        fsync_existing_directories(
            support,
            support / "state",
            support / f".native-restore-stage.{transaction_id}",
            support / "backups" / f"native-restore-{transaction_id}",
        )


def new_native_restore_journal(
    transaction_id: str,
    release_identity: str,
    prior_services: dict[str, int | None] | None = None,
) -> dict[str, object]:
    prior_services = prior_services or {service: None for service in SERVICE_ORDER}
    running = validate_coherent_service_state(prior_services)
    return {
        "schemaVersion": 1,
        "transactionId": transaction_id,
        "releaseIdentity": release_identity,
        "stageName": f".native-restore-stage.{transaction_id}",
        "checkpointName": f"native-restore-{transaction_id}",
        "phase": "staging",
        "priorServices": [service for service in SERVICE_ORDER if service in running],
        "roots": {
            relative: {
                "priorMovePending": False,
                "priorMoved": False,
                "newActivationPending": False,
                "newActivated": False,
                "rollbackOwnedNew": False,
                "rollbackHadPrior": False,
                "rollbackPreserveActive": False,
                "rollbackState": "inactive",
            }
            for relative in NATIVE_RESTORE_ROOTS
        },
    }


def begin_native_restore(
    support: Path,
    transaction_id: str,
    *,
    release_identity: str,
    prior_services: dict[str, int | None] | None = None,
) -> None:
    if (
        SAFE_NATIVE_TRANSACTION.fullmatch(transaction_id) is None
        or SAFE_NATIVE_RELEASE.fullmatch(release_identity) is None
    ):
        raise RuntimeError_("Native restore transaction identity is unsafe")
    if native_restore_journal_path(support).exists() or native_restore_journal_path(support).is_symlink():
        raise RuntimeError_("A Native restore transaction already requires recovery")
    write_native_restore_journal(
        support,
        new_native_restore_journal(
            transaction_id,
            release_identity,
            prior_services,
        ),
    )


def rollback_native_restore_from_journal(
    support: Path,
    payload: dict[str, object],
    *,
    finalize: bool = True,
    fault_after_prior_restore: str | None = None,
) -> None:
    transaction_id = str(payload["transactionId"])
    stage = support / f".native-restore-stage.{transaction_id}"
    checkpoint = support / "backups" / f"native-restore-{transaction_id}"
    roots = payload["roots"]
    if not isinstance(roots, dict):
        raise RuntimeError_("Native restore journal roots are invalid")
    phase = payload.get("phase")
    rollback_rows: list[tuple[str, Path, Path, Path, dict[str, object]]] = []

    rollback_initialized = all(
        isinstance(row, dict) and row.get("rollbackState") != "inactive"
        for row in roots.values()
    )
    if phase != "rolling_back" and not (
        phase == "rollback_incomplete" and rollback_initialized
    ):
        # Resolve every activation-pending ambiguity and validate the complete
        # checkpoint before deleting even one active root. The resolved
        # ownership facts are durably journaled as one transition so a later
        # rollback crash never has to infer them from partially moved paths.
        for relative in reversed(NATIVE_RESTORE_ROOTS):
            row = roots[relative]
            if not isinstance(row, dict):
                raise RuntimeError_("Native restore journal root state is invalid")
            active = support / relative
            staged = stage / relative
            prior = checkpoint / "prior" / relative
            owns_active = bool(
                row.get("newActivated")
                or (
                    row.get("newActivationPending")
                    and not staged.exists()
                    and active.exists()
                )
            )
            prior_was_moved = bool(
                row.get("priorMoved")
                or (row.get("priorMovePending") and prior.exists())
            )
            if owns_active:
                validate_owner_private_tree(active)
            if prior_was_moved:
                validate_owner_private_tree(prior)
            elif owns_active and bool(
                row.get("priorMovePending") or row.get("priorMoved")
            ):
                raise RuntimeError_("Native restore prior checkpoint is incomplete")
            row["rollbackOwnedNew"] = owns_active
            row["rollbackHadPrior"] = prior_was_moved
            row["rollbackPreserveActive"] = bool(
                not owns_active and not prior_was_moved and active.exists()
            )
            if row["rollbackPreserveActive"]:
                validate_owner_private_tree(active)
            row["rollbackState"] = "ready"
        payload["phase"] = "rolling_back"
        write_native_restore_journal(support, payload)

    # Validate every remaining rollback source/result before resuming any
    # destructive step. This is the restart-safe equivalent of the initial
    # full-checkpoint prevalidation once earlier roots have already returned.
    for relative in reversed(NATIVE_RESTORE_ROOTS):
        row = roots[relative]
        if not isinstance(row, dict):
            raise RuntimeError_("Native restore journal root state is invalid")
        active = support / relative
        staged = stage / relative
        prior = checkpoint / "prior" / relative
        state = str(row["rollbackState"])
        owns_active = bool(row["rollbackOwnedNew"])
        prior_was_moved = bool(row["rollbackHadPrior"])
        preserve_active = bool(row["rollbackPreserveActive"])
        active_present = active.exists() or active.is_symlink()
        prior_present = prior.exists() or prior.is_symlink()
        if state in {"ready", "new_removal_pending"}:
            if owns_active and active_present:
                validate_owner_private_tree(active)
            elif owns_active and state == "ready":
                raise RuntimeError_("Native restore rollback active root is missing")
            if prior_was_moved:
                validate_owner_private_tree(prior)
        elif state == "new_removed":
            if active_present:
                raise RuntimeError_("Native restore rollback target changed unexpectedly")
            if prior_was_moved:
                validate_owner_private_tree(prior)
        elif state == "prior_restore_pending":
            if active_present == prior_present:
                raise RuntimeError_("Native restore rollback prior move is ambiguous")
            validate_owner_private_tree(active if active_present else prior)
        elif state in {"prior_restored", "complete"}:
            if prior_was_moved:
                if not active_present or prior_present:
                    raise RuntimeError_("Native restore rollback prior state is incomplete")
                validate_owner_private_tree(active)
            elif preserve_active:
                if not active_present:
                    raise RuntimeError_("Native restore rollback preserved root is missing")
                validate_owner_private_tree(active)
            elif active_present:
                raise RuntimeError_("Native restore rollback target changed unexpectedly")
        else:
            raise RuntimeError_("Native restore journal rollback state is invalid")
        rollback_rows.append((relative, active, staged, prior, row))

    for relative, active, _staged, prior, row in rollback_rows:
        state = str(row["rollbackState"])
        owns_active = bool(row["rollbackOwnedNew"])
        prior_was_moved = bool(row["rollbackHadPrior"])
        if state == "ready":
            if owns_active:
                row["rollbackState"] = "new_removal_pending"
                write_native_restore_journal(support, payload)
                state = "new_removal_pending"
            elif prior_was_moved:
                row["rollbackState"] = "prior_restore_pending"
                write_native_restore_journal(support, payload)
                state = "prior_restore_pending"
            else:
                row["rollbackState"] = "complete"
                write_native_restore_journal(support, payload)
                continue
        if state == "new_removal_pending":
            if active.exists() or active.is_symlink():
                validate_owner_private_tree(active)
                remove_owner_private_path(active)
                fsync_existing_directories(active.parent, checkpoint, stage)
            row["rollbackState"] = "new_removed"
            write_native_restore_journal(support, payload)
            state = "new_removed"
        if state == "new_removed":
            if active.exists() or active.is_symlink():
                raise RuntimeError_("Native restore rollback target changed unexpectedly")
            if prior_was_moved:
                row["rollbackState"] = "prior_restore_pending"
                write_native_restore_journal(support, payload)
                state = "prior_restore_pending"
            else:
                row["rollbackState"] = "complete"
                write_native_restore_journal(support, payload)
                continue
        if state == "prior_restore_pending":
            active_present = active.exists() or active.is_symlink()
            prior_present = prior.exists() or prior.is_symlink()
            if prior_present and not active_present:
                validate_owner_private_tree(prior)
                ensure_private_directory(active.parent)
                durable_replace(prior, active, checkpoint, stage)
                if fault_after_prior_restore == NATIVE_RESTORE_LABELS[relative]:
                    raise RuntimeError_(
                        f"Injected Native rollback fault after {fault_after_prior_restore} prior restore"
                    )
            elif active_present and not prior_present:
                validate_owner_private_tree(active)
            else:
                raise RuntimeError_("Native restore rollback prior move is ambiguous")
            row["rollbackState"] = "prior_restored"
            write_native_restore_journal(support, payload)
            state = "prior_restored"
        if state == "prior_restored":
            row["rollbackState"] = "complete"
            write_native_restore_journal(support, payload)
    if stage.exists() or stage.is_symlink():
        remove_owner_private_path(stage)
        fsync_existing_directories(stage.parent, support)
    if checkpoint.exists() or checkpoint.is_symlink():
        remove_owner_private_path(checkpoint)
        fsync_existing_directories(checkpoint.parent, support)
    if finalize:
        durable_unlink(native_restore_journal_path(support), support, support / "state")
    else:
        payload["phase"] = "service_recovery_pending"
        write_native_restore_journal(support, payload)


def recover_native_restore(
    support: Path,
    *,
    release_identity: str,
    finalize: bool = True,
) -> None:
    journal = native_restore_journal_path(support)
    if not journal.exists() and not journal.is_symlink():
        return
    payload = read_native_restore_journal(support, release_identity=release_identity)
    try:
        rollback_native_restore_from_journal(support, payload, finalize=finalize)
    except Exception as error:
        raise RuntimeError_(
            "Native restore recovery could not prove a complete rollback; some activation may already have occurred, but no further active root was deleted without a complete prior checkpoint"
        ) from error


def activate_native_restore_state(
    support: Path,
    stage: Path,
    transaction_id: str,
    *,
    release_identity: str,
    fault_after: str | None = None,
    defer_rollback_for_test: bool = False,
    finalize: bool = True,
) -> Path:
    if (
        SAFE_NATIVE_TRANSACTION.fullmatch(transaction_id) is None
        or SAFE_NATIVE_RELEASE.fullmatch(release_identity) is None
        or stage != support / f".native-restore-stage.{transaction_id}"
    ):
        raise RuntimeError_("Native restore transaction identity is unsafe")
    validate_existing_private_directory(support)
    if stat.S_IMODE(support.lstat().st_mode) != 0o700:
        raise RuntimeError_("Native App Support must remain owner-only during restore")
    validate_owner_private_tree(stage)
    if os.stat(stage).st_dev != os.stat(support).st_dev:
        raise RuntimeError_("Native restore staging must use the same filesystem as App Support")
    for relative in NATIVE_RESTORE_ROOTS:
        validate_owner_private_tree(stage / relative)
        validate_owner_private_tree(support / relative, allow_missing=True)

    checkpoint = support / "backups" / f"native-restore-{transaction_id}"
    if checkpoint.exists() or checkpoint.is_symlink():
        raise RuntimeError_("Native restore checkpoint path already exists")
    ensure_private_directory(checkpoint / "prior")
    journal_path = native_restore_journal_path(support)
    if journal_path.exists() or journal_path.is_symlink():
        payload = read_native_restore_journal(support, release_identity=release_identity)
        if payload.get("transactionId") != transaction_id or payload.get("phase") != "staging":
            raise RuntimeError_("Native restore journal does not match the staged transaction")
    else:
        payload = new_native_restore_journal(transaction_id, release_identity)
    payload["phase"] = "activation_pending"
    write_native_restore_journal(support, payload)
    try:
        roots = payload["roots"]
        if not isinstance(roots, dict):
            raise RuntimeError_("Native restore activation state is invalid")
        for relative in NATIVE_RESTORE_ROOTS:
            row = roots[relative]
            if not isinstance(row, dict):
                raise RuntimeError_("Native restore activation state is invalid")
            active = support / relative
            staged = stage / relative
            prior = checkpoint / "prior" / relative
            if active.exists() or active.is_symlink():
                row["priorMovePending"] = True
                write_native_restore_journal(support, payload)
                ensure_private_directory(prior.parent)
                durable_replace(active, prior, support, stage, checkpoint)
                row["priorMoved"] = True
                write_native_restore_journal(support, payload)
            row["newActivationPending"] = True
            write_native_restore_journal(support, payload)
            ensure_private_directory(active.parent)
            durable_replace(staged, active, support, stage, checkpoint)
            row["newActivated"] = True
            write_native_restore_journal(support, payload)
            if fault_after == NATIVE_RESTORE_LABELS[relative]:
                raise RuntimeError_(f"Injected Native restore fault after {fault_after} activation")
        if stage.exists():
            remove_owner_private_path(stage)
            fsync_existing_directories(stage.parent, checkpoint, support)
        write_atomic(
            checkpoint / "checkpoint.json",
            json.dumps(
                {
                    "schemaVersion": 1,
                    "transactionId": transaction_id,
                    "releaseIdentity": release_identity,
                    "kind": "native_pre_restore_local_checkpoint",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )
        payload["phase"] = "activated"
        write_native_restore_journal(support, payload)
        if finalize:
            durable_unlink(native_restore_journal_path(support), support, support / "state")
        return checkpoint
    except BaseException:
        if defer_rollback_for_test:
            raise
        try:
            rollback_native_restore_from_journal(support, payload)
        except Exception as rollback_error:
            payload["phase"] = "rollback_incomplete"
            with contextlib.suppress(Exception):
                write_native_restore_journal(support, payload)
            raise RuntimeError_(
                "Native restore failed and automatic rollback was incomplete"
            ) from rollback_error
        raise


def commit_native_restore(support: Path, *, release_identity: str) -> Path:
    payload = read_native_restore_journal(support, release_identity=release_identity)
    if payload.get("phase") != "activated":
        raise RuntimeError_("Native restore cannot commit before complete activation")
    checkpoint = support / "backups" / str(payload["checkpointName"])
    validate_owner_private_tree(checkpoint)
    durable_unlink(native_restore_journal_path(support), support, support / "state")
    return checkpoint


def stop_restore_mongod(root: Path, support: Path, socket_path: Path) -> None:
    stop_service("native-restore-staging", support, root)
    if socket_path.exists() or socket_path.is_symlink():
        metadata = private_socket_metadata(socket_path, "restore MongoDB")
        if metadata is not None and not unix_socket_pids(socket_path):
            socket_path.unlink()


def stage_native_restore_database(
    root: Path,
    support: Path,
    stage_database: Path,
    snapshot: Path,
    mongo_artifact: dict[str, object],
    mongo_ledger: list[dict[str, object]],
    transaction_id: str,
    continuity,
    *,
    timeout: float,
) -> None:
    ensure_private_directory(stage_database)
    socket_path = support / "runtime" / f"nr-{transaction_id[:8]}.sock"
    if socket_path.exists() or socket_path.is_symlink():
        raise RuntimeError_("Native restore MongoDB socket path already exists")
    command = [
        str(root / "runtime" / "mongodb" / "bin" / "mongod"),
        "--bind_ip",
        str(socket_path),
        "--port",
        "27117",
        "--nounixsocket",
        "--filePermissions",
        "0600",
        "--dbpath",
        str(stage_database),
        "--wiredTigerCacheSizeGB",
        "0.5",
        "--quiet",
    ]
    spawn(
        "native-restore-staging",
        command,
        support,
        cwd=support,
        env=native_child_environment(support),
    )
    (support / "logs" / "native-restore-staging.log").chmod(0o600)
    guard_pid = live_pid(pid_path(support, "native-restore-staging"), root)
    if guard_pid is None:
        raise RuntimeError_("Native restore staging process ownership could not be proven")
    claimed = False
    uri = continuity.native_mongo_uri(socket_path)
    scratch = stage_database.parent / "mongo-import"
    try:
        deadline = time.monotonic() + timeout
        ready = False
        while time.monotonic() < deadline:
            if live_pid(pid_path(support, "native-restore-staging"), root) != guard_pid:
                break
            metadata = private_socket_metadata(socket_path, "restore MongoDB")
            if metadata is not None:
                listeners = unix_socket_pids(socket_path)
                if (
                    listeners_owned_by_guard(listeners, guard_pid)
                    and not process_group_tcp_listener_pids(guard_pid)
                    and semantic_unix_socket_ready(socket_path)
                ):
                    ready = True
                    break
            time.sleep(0.1)
        if not ready:
            raise RuntimeError_("Staged Native restore MongoDB did not become ready")
        if not continuity.mongo_database_empty(
            uri,
            root,
            socket_path=socket_path,
        ):
            raise RuntimeError_("Staged Native restore MongoDB is not empty")
        continuity.claim_mongo_database(
            uri,
            root,
            transaction_id,
            socket_path=socket_path,
        )
        claimed = True
        continuity.apply_mongo_logical(
            snapshot / str(mongo_artifact["path"]),
            mongo_ledger,
            uri,
            scratch,
            root,
            transaction_id,
            socket_path=socket_path,
        )
        continuity.release_mongo_claim(
            uri,
            root,
            transaction_id,
            socket_path=socket_path,
        )
        claimed = False
    except Exception as error:
        if claimed:
            with contextlib.suppress(Exception):
                continuity.drop_mongo_database(
                    uri,
                    root,
                    transaction_id,
                    socket_path=socket_path,
                )
        raise RuntimeError_("Native restore database staging failed") from error
    finally:
        stop_restore_mongod(root, support, socket_path)
        if scratch.exists():
            remove_owner_private_path(scratch)
    make_tree_owner_private(stage_database)
    validate_owner_private_tree(stage_database)


def validate_native_snapshot_data_schema(
    manifest: dict[str, object],
    metadata: dict[str, object],
    *,
    current_schema: int,
) -> None:
    runtime_selection = manifest.get("runtimeSelection")
    policy = metadata.get("data_schema")
    if not isinstance(runtime_selection, dict) or not isinstance(policy, dict):
        raise RuntimeError_("Native snapshot data schema metadata is missing")
    snapshot_schema = runtime_selection.get("dataSchema")
    minimum = policy.get("minimum")
    maximum = policy.get("maximum")
    target = policy.get("target")
    values = (snapshot_schema, minimum, maximum, target, current_schema)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise RuntimeError_("Native snapshot data schema metadata is invalid")
    if not minimum <= snapshot_schema <= maximum:
        raise RuntimeError_("Native snapshot data schema is outside this release compatibility range")
    if snapshot_schema != target or snapshot_schema != current_schema:
        raise RuntimeError_(
            "Native snapshot data schema requires a reviewed migration before restore"
        )


def prepare_native_restore_stage(
    root: Path,
    support: Path,
    snapshot_path: Path,
    transaction_id: str,
    continuity,
    *,
    timeout: float,
) -> Path:
    for relative in NATIVE_RESTORE_ROOTS:
        active = support / relative
        try:
            snapshot_path.relative_to(active)
        except ValueError:
            continue
        raise RuntimeError_("Native snapshot overlaps mutable state selected for replacement")
    preflight_native_restore_capacity(snapshot_path, support, timeout=timeout)
    stage = support / f".native-restore-stage.{transaction_id}"
    if stage.exists() or stage.is_symlink():
        raise RuntimeError_("Native restore staging path already exists")
    ensure_private_directory(stage)
    snapshot_input = stage / ".snapshot-input"
    try:
        copy_verified_private_tree(snapshot_path, snapshot_input, timeout=timeout)
        validation = continuity.validate_bundle(snapshot_input)
        if not validation.get("recoverable"):
            raise RuntimeError_("Selected snapshot is not a complete recoverable Viventium bundle")
        continuity.validate_owned_private_bundle(snapshot_input)
        manifest = continuity.read_manifest(snapshot_input)
        preflight_native_restore_expansion_capacity(manifest, support)
        runtime_selection = manifest.get("runtimeSelection")
        if not isinstance(runtime_selection, dict) or runtime_selection.get("profile") != "native":
            raise RuntimeError_(
                "Native restore accepts only a Native snapshot; cross-profile migration requires a separate reviewed flow"
            )
        if runtime_selection.get("sourceDatabase") != "LibreChat":
            raise RuntimeError_("Native snapshot database identity is unsupported")
        current_schema = inspect_data_schema(support, root)
        validate_native_snapshot_data_schema(
            manifest,
            build_metadata(root),
            current_schema=current_schema,
        )
        artifacts = {
            str(item["role"]): item
            for item in manifest.get("artifacts", [])
            if isinstance(item, dict) and isinstance(item.get("role"), str)
        }
        domains = {
            str(item["name"]): item
            for item in manifest.get("domains", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if "canonical_config" not in artifacts or "mongo_archive" not in artifacts:
            raise RuntimeError_("Native snapshot lacks required canonical artifacts")
        config_source = snapshot_input / str(artifacts["canonical_config"]["path"])
        copy_private_file(config_source, stage / "config.yaml")
        continuity.validate_artifact_content(stage / "config.yaml", "canonical_config")

        uploads_stage = stage / "data" / "uploads"
        ensure_private_directory(uploads_stage)
        if domains.get("files", {}).get("status") == "captured":
            continuity.extract_regular_tar(
                snapshot_input / str(artifacts["user_files_archive"]["path"]),
                uploads_stage,
            )

        scheduling_stage = stage / "state" / "runtime" / "native" / "scheduling"
        ensure_private_directory(scheduling_stage)
        if domains.get("schedules", {}).get("status") == "captured":
            schedule_source = snapshot_input / str(artifacts["schedules_database"]["path"])
            copy_private_file(schedule_source, scheduling_stage / "schedules.db")
            continuity.validate_artifact_content(
                scheduling_stage / "schedules.db", "schedules_database"
            )

        continuity_stage = stage / "state" / "runtime" / "native" / "continuity"
        ensure_private_directory(continuity_stage)
        now = int(time.time())
        write_atomic(
            continuity_stage / "recall-rebuild-required.json",
            json.dumps(
                {
                    "schemaVersion": 1,
                    "reason": "native_restore_requires_derived_recall_rebuild",
                    "createdAt": now,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )
        write_atomic(
            continuity_stage / "reauthentication-required.json",
            json.dumps(
                {
                    "schemaVersion": 1,
                    "providerCredentials": "reauth_required",
                    "channelCredentials": "reauth_required",
                    "browserSessions": "reauth_required",
                    "userPasswords": "reset_required",
                    "createdAt": now,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )
        mongo_ledger = manifest.get("inventory", {}).get("mongoCollections")
        if not isinstance(mongo_ledger, list):
            raise RuntimeError_("Native snapshot Mongo inventory is invalid")
        stage_native_restore_database(
            root,
            support,
            stage / "data" / "mongodb",
            snapshot_input,
            artifacts["mongo_archive"],
            mongo_ledger,
            transaction_id,
            continuity,
            timeout=timeout,
        )
        remove_owner_private_path(snapshot_input)
        fsync_existing_directories(stage)
        make_tree_owner_private(stage)
        validate_owner_private_tree(stage)
        return stage
    except BaseException:
        if stage.exists() or stage.is_symlink():
            with contextlib.suppress(Exception):
                remove_owner_private_path(stage)
        raise


def recover_native_restore_before_lifecycle(support: Path, root: Path) -> None:
    journal = native_restore_journal_path(support)
    if not journal.exists() and not journal.is_symlink():
        return
    metadata = build_metadata(root)
    release_identity = str(metadata["source_commit"])
    payload = read_native_restore_journal(support, release_identity=release_identity)
    transaction_id = str(payload["transactionId"])
    prior_running = set(payload["priorServices"])
    prior_services = {
        service: 1 if service in prior_running else None for service in SERVICE_ORDER
    }
    stop_restore_mongod(
        root,
        support,
        support / "runtime" / f"nr-{transaction_id[:8]}.sock",
    )
    for service in reversed(SERVICE_ORDER):
        stop_service(service, support, root)
    if payload.get("phase") != "service_recovery_pending":
        recover_native_restore(
            support,
            release_identity=release_identity,
            finalize=False,
        )
    restore_exact_service_state(
        support,
        root,
        prior_services,
        timeout=60.0,
    )
    durable_unlink(native_restore_journal_path(support), support, support / "state")


def snapshot(args: argparse.Namespace, *, _lock_held: bool = False) -> None:
    support = lexical_support(args.app_support_dir)
    if not _lock_held:
        with lifecycle_lock(support):
            snapshot(args, _lock_held=True)
        return
    validate_support_children(support)
    root = installed_release_root(support)
    packaged_health(root)
    recover_native_restore_before_lifecycle(support, root)
    preexisting = guard_pid_snapshot(support, root)
    validate_coherent_service_state(preexisting)
    try:
        if owned_mongodb_socket_pid(support, root) is None:
            start(
                type(
                    "StartArgs",
                    (),
                    {"app_support_dir": support, "timeout": args.timeout},
                )(),
                _lock_held=True,
                _allow_pending_restore=True,
            )
        require_owned_service("mongodb", support, root)
        stop_service("frontend-proxy", support, root)
        stop_service("librechat", support, root)
        assert_native_snapshot_capture_state(support, root)
        continuity = load_continuity_module(root)
        ensure_support_directories(support, "snapshots", "data/uploads")
        metadata = build_metadata(root)
        result = continuity.capture_bundle(
            repo_root=root,
            app_support=support,
            runtime_dir=support / "runtime",
            output_root=support / "snapshots",
            uploads_dir=support / "data" / "uploads",
            mongo_uri=mongodb_uri(support),
            mongo_socket=mongodb_socket_path(support),
            data_schema=inspect_data_schema(support, root),
            release_identity=str(metadata["source_commit"]),
        )
        created = Path(str(result.get("snapshotDir", "")))
        try:
            created.relative_to(support / "snapshots")
        except ValueError as error:
            raise RuntimeError_("Native snapshot escaped the App Support snapshot boundary") from error
        if not result.get("recoverable"):
            raise RuntimeError_("Native snapshot did not produce recoverable proof")
        proof = continuity.validate_bundle(created)
        continuity.validate_owned_private_bundle(created)
        if not proof.get("recoverable"):
            raise RuntimeError_("Native snapshot proof changed before publication")
        write_atomic(support / "snapshots" / "LATEST_PATH", str(created) + "\n")
    except Exception as error:
        if isinstance(error, RuntimeError_):
            raise
        raise RuntimeError_(f"Native snapshot failed: {error}") from error
    finally:
        restore_exact_service_state(
            support,
            root,
            preexisting,
            timeout=float(args.timeout),
        )
    print(f"Viventium Native backup created: {created}")


def restore(args: argparse.Namespace, *, _lock_held: bool = False) -> None:
    support = lexical_support(args.app_support_dir)
    if not _lock_held:
        with lifecycle_lock(support):
            restore(args, _lock_held=True)
        return
    validate_support_children(support)
    root = installed_release_root(support)
    packaged_health(root)
    metadata = build_metadata(root)
    release_identity = str(metadata["source_commit"])
    recover_native_restore_before_lifecycle(support, root)
    validate_native_socket_lengths(support)
    state_path = support / "state" / "native-runtime.json"
    state_before = state_path.read_bytes()
    preexisting = guard_pid_snapshot(support, root)
    prior_running = validate_coherent_service_state(preexisting)
    continuity = load_continuity_module(root)
    transaction_id = uuid.uuid4().hex
    snapshot_path = Path(os.path.abspath(os.fspath(args.snapshot.expanduser())))
    stage: Path | None = None
    activated = False
    services_quiesced = False
    try:
        stage = prepare_native_restore_stage(
            root,
            support,
            snapshot_path,
            transaction_id,
            continuity,
            timeout=args.timeout,
        )
        begin_native_restore(
            support,
            transaction_id,
            release_identity=release_identity,
            prior_services=preexisting,
        )
        services_quiesced = True
        for service in reversed(SERVICE_ORDER):
            stop_service(service, support, root)
        stop_restore_mongod(
            root,
            support,
            support / "runtime" / f"nr-{transaction_id[:8]}.sock",
        )
        assert_native_restore_quiesced(
            support,
            root,
            transaction_id=transaction_id,
            timeout=min(float(args.timeout), 30.0),
        )
        activate_native_restore_state(
            support,
            stage,
            transaction_id,
            release_identity=release_identity,
            finalize=False,
        )
        activated = True
        desired_after_restore = (
            {name: None for name in SERVICE_ORDER}
            if args.no_start
            else preexisting
        )
        restore_exact_service_state(
            support,
            root,
            desired_after_restore,
            timeout=float(args.timeout),
        )
        if prior_running == set(SERVICE_ORDER) and not args.no_start:
            health(
                type(
                    "HealthArgs",
                    (),
                    {"app_support_dir": support, "installed_only": False},
                )()
            )
        if state_path.read_bytes() != state_before:
            raise RuntimeError_("Native restore changed the immutable release pointer")
        commit_native_restore(support, release_identity=release_identity)
    except Exception as error:
        recovery_restored_services = False
        if activated or native_restore_journal_path(support).exists():
            for service in reversed(SERVICE_ORDER):
                with contextlib.suppress(Exception):
                    stop_service(service, support, root)
            try:
                recover_native_restore_before_lifecycle(support, root)
                recovery_restored_services = True
            except Exception as rollback_error:
                raise RuntimeError_(
                    "Native restore failed and prior-state restart could not be proven"
                ) from rollback_error
        elif stage is not None and (stage.exists() or stage.is_symlink()):
            with contextlib.suppress(Exception):
                remove_owner_private_path(stage)
        if services_quiesced and not recovery_restored_services:
            try:
                restore_exact_service_state(
                    support,
                    root,
                    preexisting,
                    timeout=float(args.timeout),
                )
            except Exception as restart_error:
                raise RuntimeError_(
                    "Native restore failed and prior-state restart could not be proven"
                ) from restart_error
        if isinstance(error, RuntimeError_):
            raise
        raise RuntimeError_(f"Native restore failed: {error}") from error
    print(
        "Viventium Native restore completed. Reset the local browser password, reconnect accounts, and rebuild Recall before normal use."
    )


NATIVE_UNINSTALL_STORAGE_NAMES = {"native", "runtime", "logs"}


def validate_owned_runtime_storage(path: Path, support: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.parent != support or path.name not in NATIVE_UNINSTALL_STORAGE_NAMES:
        raise RuntimeError_("Native runtime storage path is unsafe")
    try:
        root_metadata = path.lstat()
    except OSError as error:
        raise RuntimeError_("Native runtime storage path is unsafe") from error
    if (
        stat.S_ISLNK(root_metadata.st_mode)
        or not stat.S_ISDIR(root_metadata.st_mode)
        or root_metadata.st_uid != os.getuid()
    ):
        raise RuntimeError_("Native runtime storage path is unsafe")
    for current, directories, files in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if (
            stat.S_ISLNK(current_metadata.st_mode)
            or not stat.S_ISDIR(current_metadata.st_mode)
            or current_metadata.st_uid != os.getuid()
        ):
            raise RuntimeError_("Native runtime storage tree is unsafe")
        for name in [*directories, *files]:
            child = current_path / name
            metadata = child.lstat()
            if stat.S_ISLNK(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise RuntimeError_("Native runtime storage tree is unsafe")
            if name in files and (
                not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            ):
                raise RuntimeError_("Native runtime storage tree is unsafe")
            if name in directories and not stat.S_ISDIR(metadata.st_mode):
                raise RuntimeError_("Native runtime storage tree is unsafe")


def remove_owned_runtime_storage(path: Path, support: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    validate_owned_runtime_storage(path, support)
    directories: list[Path] = []
    files: list[Path] = []
    for current, child_directories, child_files in os.walk(
        path, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        directories.append(current_path)
        files.extend(current_path / name for name in child_files)
        directories.extend(current_path / name for name in child_directories)
    for file_path in files:
        file_path.chmod(0o600)
    for directory in sorted(set(directories), key=lambda item: len(item.parts), reverse=True):
        directory.chmod(0o700)
    shutil.rmtree(path)


def uninstall(args: argparse.Namespace, *, _lock_held: bool = False) -> None:
    support = lexical_support(args.app_support_dir)
    if not _lock_held:
        with lifecycle_lock(support):
            uninstall(args, _lock_held=True)
        return
    helper = user_home() / "Applications" / "Viventium.app"
    helper_present = helper.exists() or helper.is_symlink()
    if helper_present:
        if helper_owner(helper) is None or not helper_tree_is_safe(helper):
            raise RuntimeError_("Refusing to remove an unrelated application during Native uninstall")
    stop(type("StopArgs", (), {"app_support_dir": support})(), _lock_held=True)
    if helper_present:
        if helper_owner(helper) is None or not helper_tree_is_safe(helper):
            raise RuntimeError_("Native helper ownership changed during uninstall")
        shutil.rmtree(helper)
    runtime_storage = [support / name for name in sorted(NATIVE_UNINSTALL_STORAGE_NAMES)]
    for path in runtime_storage:
        validate_owned_runtime_storage(path, support)
    for path in runtime_storage:
        remove_owned_runtime_storage(path, support)
    (support / "helper-config.json").unlink(missing_ok=True)
    (support / "state" / "native-runtime.json").unlink(missing_ok=True)
    print(
        "Viventium Native was uninstalled; app-owned payloads, runtime cache, and logs were removed while user configuration, data, and backups were preserved"
    )


def schema(args: argparse.Namespace) -> None:
    support = lexical_support(args.app_support_dir)
    reject_pending_restore_for_read(support)
    current = inspect_data_schema(support, release_root())
    print(json.dumps({"schema_version": 1, "current": current}, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    subparsers = value.add_subparsers(dest="command", required=True)
    for name in ("install", "start", "stop", "registration-close", "status", "health", "doctor", "configure", "password-reset-link", "upgrade", "snapshot", "restore", "uninstall", "schema"):
        command = subparsers.add_parser(name)
        command.add_argument("--app-support-dir", type=Path, default=default_support())
        if name in {"install", "start", "registration-close"}:
            command.add_argument("--timeout", type=float, default=60)
        if name == "install":
            command.add_argument("--no-start", action="store_true")
            command.add_argument("--local-qa", action="store_true")
            command.add_argument("--no-helper", action="store_true")
            command.add_argument("--no-open", action="store_true")
        if name == "health":
            command.add_argument("--installed-only", action="store_true")
        if name == "configure":
            command.add_argument("--print-path", action="store_true")
        if name == "password-reset-link":
            command.add_argument("email")
            command.add_argument("--timeout", type=float, default=60)
        if name == "upgrade":
            command.add_argument("--check", action="store_true")
            command.add_argument("--json", action="store_true")
            command.add_argument("--restart", action="store_true")
        if name == "snapshot":
            command.add_argument("--timeout", type=float, default=60)
        if name == "restore":
            command.add_argument("snapshot", type=Path)
            command.add_argument("--timeout", type=float, default=60)
            command.add_argument("--no-start", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        {
            "install": install,
            "start": start,
            "stop": stop,
            "registration-close": registration_close,
            "status": status,
            "health": health,
            "doctor": doctor,
            "configure": configure,
            "password-reset-link": password_reset_link,
            "upgrade": upgrade,
            "snapshot": snapshot,
            "restore": restore,
            "uninstall": uninstall,
            "schema": schema,
        }[args.command](args)
    except KeyboardInterrupt:
        print("Viventium Native: operation interrupted after safe cleanup", file=sys.stderr)
        return 130
    except (RuntimeError_, OSError) as error:
        print(f"Viventium Native: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
