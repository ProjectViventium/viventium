#!/usr/bin/env python3
"""Install a signed Native payload from the signed bootstrap release policy."""

from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import stat
from pathlib import Path

import native_payload


MAX_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024 * 1024
NATIVE_INSTALL_RESERVE_BYTES = 10 * 1024 * 1024 * 1024


class BootstrapError(RuntimeError):
    pass


def raise_install_cancel(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def owned_process_group_alive(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # A process group that still exists can briefly report EPERM on macOS after
        # its leader exits. Treat it as alive so cancellation continues to the
        # bounded SIGKILL fallback instead of abandoning an owned descendant.
        return True
    return True


def terminate_owned_process(process: subprocess.Popen, timeout: float = 5.0) -> None:
    process_group = process.pid
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while owned_process_group_alive(process_group) and time.monotonic() < deadline:
        if process.poll() is None:
            try:
                process.wait(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                continue
        time.sleep(0.01)
    if not owned_process_group_alive(process_group):
        return
    try:
        os.killpg(process_group, signal.SIGKILL)
    except ProcessLookupError:
        return
    if process.poll() is None:
        process.wait(timeout=timeout)
    deadline = time.monotonic() + timeout
    while owned_process_group_alive(process_group) and time.monotonic() < deadline:
        time.sleep(0.01)
    if owned_process_group_alive(process_group):
        raise BootstrapError("an installer child process group could not be terminated")


def run_owned_process(
    arguments: list[str],
    *,
    stdout: int | None = subprocess.DEVNULL,
    stderr: int | None = subprocess.DEVNULL,
    text: bool = False,
) -> subprocess.CompletedProcess:
    process = subprocess.Popen(
        arguments,
        stdout=stdout,
        stderr=stderr,
        text=text,
        start_new_session=True,
    )
    try:
        captured_stdout, captured_stderr = process.communicate()
    except BaseException:
        terminate_owned_process(process)
        raise
    return subprocess.CompletedProcess(
        arguments,
        process.returncode,
        stdout=captured_stdout,
        stderr=captured_stderr,
    )


def run_release(release: Path, command: str, support: Path, *arguments: str) -> bool:
    try:
        completed = run_owned_process(
            [
                str(release / "bin" / f"viventium-native-{command}"),
                "--app-support-dir",
                str(support),
                *arguments,
            ]
        )
    except OSError:
        return False
    return completed.returncode == 0


def inspected_data_schema(release: Path, support: Path) -> int:
    try:
        completed = run_owned_process(
            [
                str(release / "bin" / "viventium-native-schema"),
                "--app-support-dir",
                str(support),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as error:
        raise BootstrapError("Native data schema inspection could not start") from error
    try:
        value = json.loads(completed.stdout)
        current = value["current"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise BootstrapError("Native data schema inspection failed closed") from error
    if completed.returncode != 0 or value.get("schema_version") != 1 or isinstance(current, bool) or not isinstance(current, int):
        raise BootstrapError("Native data schema inspection failed closed")
    return current


def restart_prior_release(release: Path | None, support: Path, *, was_running: bool) -> None:
    if release is None:
        return
    arguments = ("--no-open",) if was_running else ("--no-start", "--no-open")
    if not run_release(release, "install", support, *arguments):
        raise BootstrapError("the prior Native release pointer was restored but its runtime could not be restored")
    if was_running and not run_release(release, "health", support):
        raise BootstrapError("the prior Native release restarted without passing semantic health")


def resources_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_policy(root: Path) -> dict[str, object]:
    path = root / "release.json"
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BootstrapError("signed release policy is unavailable or invalid") from error
    required = {"schema_version", "release_tag", "release_id", "release_base", "sequence"}
    if set(policy) != required or policy["schema_version"] != 1:
        raise BootstrapError("signed release policy schema is invalid")
    for key in ("release_tag", "release_id"):
        value = policy[key]
        if not isinstance(value, str) or not value or len(value) > 80:
            raise BootstrapError("signed release policy value is invalid")
        if any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for character in value
        ):
            raise BootstrapError("signed release policy value is invalid")
    sequence = policy["sequence"]
    if (
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or not 1 <= sequence <= 999_999_999
    ):
        raise BootstrapError("signed release policy sequence is invalid")
    if policy["release_base"] != "https://github.com/ProjectViventium/viventium/releases/download":
        raise BootstrapError("signed release origin is not approved")
    return policy


def architecture() -> str:
    value = platform.machine()
    if value not in {"arm64", "x86_64"}:
        raise BootstrapError("this Mac architecture is not supported")
    return value


def lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def validate_or_create_support(path: Path) -> None:
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
        raise BootstrapError("Native App Support parent path is unsafe") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise BootstrapError("Native App Support parent path is unsafe")
    for component in reversed(missing):
        try:
            component.mkdir(mode=0o700)
        except OSError as error:
            raise BootstrapError("Native App Support path could not be created safely") from error
    try:
        metadata = path.lstat()
    except OSError as error:
        raise BootstrapError("Native App Support path is unsafe") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise BootstrapError("Native App Support path is unsafe")
    for child in ("native", "state", "runtime", "logs", "data", "backups"):
        candidate = path / child
        if candidate.exists() or candidate.is_symlink():
            child_metadata = candidate.lstat()
            if stat.S_ISLNK(child_metadata.st_mode) or not stat.S_ISDIR(child_metadata.st_mode) or child_metadata.st_uid != os.getuid():
                raise BootstrapError(f"Native App Support child is unsafe: {child}")


def refuse_cross_mode_support(support: Path) -> None:
    runtime_env = support / "runtime" / "runtime.env"
    native_owned = (support / "state" / "native-runtime.json").is_file() or (
        support / "state" / "native-data-schema.json"
    ).is_file()
    if runtime_env.is_file() and "VIVENTIUM_RUNTIME_PROFILE=native" not in runtime_env.read_text(encoding="utf-8", errors="replace").splitlines():
        raise BootstrapError("Existing source/Docker App Support requires an explicit reviewed migration to Native")
    legacy = [support / "state" / "mongo-data", support / "state" / "runtime" / "mongo-data"]
    runtime_state = support / "state" / "runtime"
    if runtime_state.is_dir():
        legacy.extend(runtime_state.glob("*/mongo-data"))
    if any(path.is_dir() and next(path.iterdir(), None) is not None for path in legacy):
        raise BootstrapError("Existing source/Docker Mongo data requires an explicit reviewed migration to Native")
    if (support / "config.yaml").exists() and not native_owned:
        raise BootstrapError("Existing App Support ownership is ambiguous; refusing Native mutation")


def refuse_pending_native_restore(support: Path) -> None:
    """A new signed release must never interpret another release's recovery journal."""
    journal = support / "state" / "native-restore-transaction.json"
    if journal.exists() or journal.is_symlink():
        raise BootstrapError(
            "A Native restore requires recovery by the currently installed release before upgrade"
        )


def validate_https_release_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise BootstrapError("release asset requires a valid HTTPS release URL") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (port is not None and port != 443)
    ):
        raise BootstrapError("release asset requires a valid HTTPS release URL")
    return url


class ValidatedHTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject an unsafe redirect target before urllib opens the next request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_https_release_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str, destination: Path, maximum: int) -> None:
    request = urllib.request.Request(
        validate_https_release_url(url), headers={"User-Agent": "ViventiumBootstrap/1"}
    )
    opener = urllib.request.build_opener(ValidatedHTTPSRedirectHandler())
    try:
        # Initial and redirected URLs are validated as credential-free HTTPS release URLs.
        with opener.open(  # nosec B310
            request, timeout=60
        ) as response, destination.open("xb") as handle:
            validate_https_release_url(response.geturl())
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > maximum:
                raise BootstrapError("release asset exceeds its size limit")
            copied = 0
            while chunk := response.read(1024 * 1024):
                copied += len(chunk)
                if copied > maximum:
                    raise BootstrapError("release asset exceeds its size limit")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise BootstrapError("release asset download failed") from error


def preflight_install_capacity(
    candidate: native_payload.VerifiedCandidate,
    support: Path,
    download_root: Path,
) -> None:
    artifact = candidate.payload["artifact"]
    compressed = int(artifact["size"])
    unpacked = int(artifact["uncompressed_size"])
    try:
        support_device = support.stat().st_dev
        download_device = download_root.stat().st_dev
        if support_device == download_device:
            required = compressed + unpacked + NATIVE_INSTALL_RESERVE_BYTES
            available = shutil.disk_usage(support).free
            if available < required:
                raise BootstrapError(
                    "Native install needs more free disk space before download and expansion"
                )
            return
        support_required = unpacked + NATIVE_INSTALL_RESERVE_BYTES
        download_required = compressed + NATIVE_INSTALL_RESERVE_BYTES
        if shutil.disk_usage(support).free < support_required:
            raise BootstrapError(
                "Native install needs more free disk space before expansion"
            )
        if shutil.disk_usage(download_root).free < download_required:
            raise BootstrapError(
                "Native install needs more free disk space before download"
            )
    except BootstrapError:
        raise
    except OSError as error:
        raise BootstrapError("Native install free disk space could not be verified") from error


def self_check(root: Path, *, candidate: bool) -> None:
    required = (
        root / "runtime" / "python" / "bin" / "python3",
        root / "scripts" / "native_payload.py",
        root / "scripts" / "install_native_payload.py",
    )
    if any(not path.is_file() for path in required) or not os.access(required[0], os.X_OK):
        raise BootstrapError("bootstrap resources are incomplete")
    if not candidate:
        load_policy(root)
        allowed = root / "allowed_signers"
        if not allowed.is_file() or not allowed.read_text(encoding="utf-8").strip():
            raise BootstrapError("manifest trust policy is unavailable")


def validate_candidate_policy(
    candidate: native_payload.VerifiedCandidate, policy: dict[str, object]
) -> None:
    if (
        candidate.release_id != policy["release_id"]
        or candidate.sequence != policy["sequence"]
    ):
        raise BootstrapError("signed payload does not match the bootstrap release policy")


def install(args: argparse.Namespace) -> None:
    root = resources_root()
    self_check(root, candidate=False)
    policy = load_policy(root)
    arch = architecture()
    stem = f"viventium-native-{policy['release_id']}-{arch}.zip"
    base = f"{policy['release_base']}/{policy['release_tag']}"
    support = lexical_path(args.app_support_dir)
    validate_or_create_support(support)
    refuse_cross_mode_support(support)
    refuse_pending_native_restore(support)
    install_root = support / "native"
    with tempfile.TemporaryDirectory(prefix="viventium-native-download.") as temporary_raw:
        temporary = Path(temporary_raw)
        manifest = temporary / f"{stem}.manifest.json"
        signature = temporary / f"{stem}.manifest.json.sig"
        artifact = temporary / stem
        download(f"{base}/{manifest.name}", manifest, MAX_MANIFEST_BYTES)
        download(f"{base}/{signature.name}", signature, MAX_SIGNATURE_BYTES)
        manifest_candidate = native_payload.verify_manifest(
            manifest,
            signature_path=signature,
            allowed_signers_path=root / "allowed_signers",
            expected_arch=arch,
            current_macos=platform.mac_ver()[0],
        )
        validate_candidate_policy(manifest_candidate, policy)
        if (
            (install_root / "releases").is_dir()
            and (install_root / "staging").is_dir()
        ):
            native_payload.prune_install_storage(install_root)
        preflight_install_capacity(manifest_candidate, support, temporary)
        download(f"{base}/{artifact.name}", artifact, MAX_PAYLOAD_BYTES)
        candidate = native_payload.verify_candidate(
            manifest,
            artifact,
            signature_path=signature,
            allowed_signers_path=root / "allowed_signers",
            expected_arch=arch,
            current_macos=platform.mac_ver()[0],
        )
        validate_candidate_policy(candidate, policy)
        staged = native_payload.stage_candidate(candidate, artifact, install_root)
        prior = native_payload.recover_interrupted_activation(candidate, install_root)
        prior_was_running = prior is not None and run_release(prior, "health", support)
        current_schema = inspected_data_schema(staged, support)
        if prior is not None and not run_release(prior, "stop", support):
            raise BootstrapError("the prior Native release could not be stopped safely")

        def transactional_health(release: Path) -> bool:
            installed = run_release(release, "install", support, "--no-open")
            healthy = installed and run_release(release, "health", support)
            if healthy and args.no_start:
                healthy = run_release(release, "stop", support)
            if not healthy:
                run_release(release, "stop", support)
            return healthy

        try:
            native_payload.activate_candidate(
                candidate,
                staged,
                install_root,
                current_data_schema=current_schema,
                health_check=transactional_health,
            )
            # A clean reactivation intentionally skips the activation callback; it still
            # has to repair/install the active release and prove the exact caller state.
            if prior is not None and prior.resolve() == staged.resolve():
                arguments = ("--no-start", "--no-open") if args.no_start else ("--no-open",)
                if not run_release(staged, "install", support, *arguments):
                    raise BootstrapError("the active Native release could not complete setup")
                if not args.no_start and not run_release(staged, "health", support):
                    raise BootstrapError("the active Native release failed semantic health")
            native_payload.prune_install_storage(install_root)
        except BaseException:
            restart_prior_release(prior, support, was_running=prior_was_running)
            raise
    if not args.no_start:
        subprocess.run(["/usr/bin/open", "http://127.0.0.1:3190"], check=False)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--self-check", action="store_true")
    value.add_argument("--candidate", action="store_true")
    value.add_argument("--no-start", action="store_true")
    value.add_argument(
        "--app-support-dir",
        type=Path,
        default=Path.home() / "Library" / "Application Support" / "Viventium",
    )
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    signal.signal(signal.SIGTERM, raise_install_cancel)
    try:
        if args.self_check:
            self_check(resources_root(), candidate=args.candidate)
        else:
            install(args)
    except (BootstrapError, native_payload.PayloadError) as error:
        print(f"Viventium Bootstrap: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Viventium Bootstrap: installation cancelled safely", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
