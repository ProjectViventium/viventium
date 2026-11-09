"""Local configuration, workspace scope and native process lifetime."""
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
from math import ceil
import os
from pathlib import Path
import shutil
import signal
import struct
from tempfile import TemporaryDirectory
from time import monotonic
import tomllib
from uuid import uuid4

from anyio import CancelScope

from . import images, video


class MediaError(Exception):
    """A concise failure suitable for returning to the worker."""


@dataclass(frozen=True)
class Artifact:
    model: str
    path: str
    mime_type: str
    bytes: int
    elapsed_seconds: float
    seed: int
    width: int
    height: int
    duration_seconds: float | None = None
    has_audio: bool | None = None


@dataclass(frozen=True)
class Model:
    runtime: Path
    weights: Path

    def missing(self, name: str) -> bool:
        commands = (("sd-cli",) if name == video.MODEL else images.RUNTIMES[name])
        if any(not (self.runtime / command).is_file() or not os.access(self.runtime / command, os.X_OK)
               for command in commands):
            return True
        if name == video.MODEL:
            return any(not (self.weights / file).is_file() for file in video.WEIGHTS.values())
        try:
            for component in ("text_encoder", "transformer", "vae"):
                directory = self.weights / component
                index = directory / "model.safetensors.index.json"
                shards = set(json.loads(index.read_text(encoding="utf-8"))["weight_map"].values())
                if not shards or any(not (directory / name).is_file() for name in shards):
                    return True
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            return True
        return False


@dataclass(frozen=True)
class Settings:
    file: Path
    models: dict[str, Model]
    timeout: int
    ffmpeg: Path

    @classmethod
    def read(cls, path: Path) -> "Settings":
        path = path.expanduser().resolve(strict=True)
        with path.open("rb") as config_file:
            config = tomllib.load(config_file)
        models = {}
        for name, spec in config.get("models", {}).items():
            if name not in images.MODELS and name != video.MODEL:
                raise ValueError(f"Unknown local media model: {name}")
            enabled = spec.get("enabled", False)
            if not isinstance(enabled, bool):
                raise ValueError(f"Expected true or false for {name}.enabled")
            if enabled:
                models[name] = Model(absolute(spec["runtime"]), absolute(spec["weights"]))
        timeout = config.get("render_timeout_seconds", 1800)
        if type(timeout) is not int or timeout < 1:
            raise ValueError("render_timeout_seconds must be a positive integer")
        ffmpeg = config.get("ffmpeg") or shutil.which("ffmpeg")
        return cls(path, models, timeout, absolute(ffmpeg) if ffmpeg else Path("/unavailable/ffmpeg"))

    def ready(self, name: str) -> bool:
        model = self.models.get(name)
        return model is not None and not model.missing(name) and (
            name != video.MODEL or all(path.is_file() and os.access(path, os.X_OK)
                                       for path in (self.ffmpeg, self.ffmpeg.with_name("ffprobe")))
        )


def absolute(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Configure absolute paths for local model files and executables")
    return path


@dataclass(frozen=True)
class Workspace:
    root: Path
    output_root: Path | None = None

    @classmethod
    def open(cls, path: Path) -> "Workspace":
        path = path.expanduser().resolve(strict=True)
        if not path.is_dir():
            raise ValueError("The authorized workspace must be a directory")
        return cls(path)

    def reference(self, value: str | None) -> Path | None:
        if value is None:
            return None
        path = (self.root / value).resolve()
        if not (path.is_relative_to(self.root) or
                (self.output_root and path.is_relative_to(self.output_root / "artifacts"))):
            raise MediaError("Reference is outside the authorized workspace.")
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpeg", ".jpg", ".webp"}:
            raise MediaError("Reference must be a PNG, JPEG or WebP file in the workspace.")
        return path

    def artifacts(self) -> Path:
        path = (self.output_root or self.root) / "artifacts"
        if path.is_symlink():
            raise MediaError("The workspace artifacts directory must be a real directory.")
        try:
            path.mkdir(mode=0o700, exist_ok=True)
        except OSError as error:
            raise MediaError("The workspace artifacts directory is unavailable.") from error
        return path


@contextmanager
def render_slot(config: Path):
    with config.with_suffix(config.suffix + ".render.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MediaError("The local renderer is busy. Retry after the active render finishes.") from error
        yield


async def run_native(args: list[str], cwd: Path, timeout: int, *, capture: bool = False) -> bytes:
    env = {key: os.environ[key] for key in ("HOME", "PATH", "TMPDIR", "LANG") if key in os.environ}
    env.update(HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TRANSFORMERS_OFFLINE="1")
    try:
        process = await asyncio.create_subprocess_exec(
            *args, cwd=cwd, env=env, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True,
        )
    except OSError as error:
        raise MediaError("The configured local executable could not start.") from error
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout)
        if process.returncode:
            raise MediaError(f"The local engine exited with code {process.returncode}.")
        return stdout or b""
    except TimeoutError as error:
        raise MediaError("The local render timed out.") from error
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            with CancelScope(shield=True):
                await process.wait()


async def render(settings: Settings, workspace: Workspace, model: str, prompt: str, *,
                 width: int, height: int, seed: int, reference: str | None, frames: int = 56) -> Artifact:
    if not prompt.strip() or "\0" in prompt:
        raise MediaError("Enter a non-empty generation prompt.")
    if min(width, height, frames) < 1 or seed < 0:
        raise MediaError("Dimensions and frame count must be positive. The seed must be nonnegative.")
    if not settings.ready(model):
        raise MediaError("That local model is unavailable. Check the enabled models and their files.")
    source = workspace.reference(reference)
    if source and model in images.RUNTIMES and len(images.RUNTIMES[model]) == 1:
        raise MediaError(f"{model} accepts text input only. Select a configured reference-edit model.")
    engine = settings.models[model]
    is_video = model == video.MODEL
    extension, mime = ("mp4", "video/mp4") if is_video else ("png", "image/png")
    artifacts = workspace.artifacts()
    final = artifacts / f"{model}-{uuid4().hex}.{extension}"
    started = monotonic()
    with render_slot(settings.file), TemporaryDirectory(prefix=".media-", dir=artifacts) as folder:
        work = Path(folder)
        prompt_file = work / "prompt.txt"
        prompt_file.write_bytes(prompt.encode("utf-8"))
        prompt_file.chmod(0o600)
        result = work / f"output.{extension}"
        native_args = dict(width=width, height=height, seed=seed, reference=source)
        if is_video:
            native = work / "output.avi"
            await run_native(video.command(engine.runtime, engine.weights, prompt_file, native, frames=frames,
                                           **native_args), work, settings.timeout)
            remaining = max(1, ceil(settings.timeout - (monotonic() - started)))
            await run_native(video.encode(settings.ffmpeg, native, result), work, remaining)
        else:
            await run_native(images.command(model, engine.runtime, engine.weights, prompt_file, result,
                                            **native_args), work, settings.timeout)
        if not result.is_file():
            raise MediaError("The local engine finished without a usable media file.")
        duration, has_audio = None, None
        if is_video:
            try:
                raw = await run_native(video.probe(settings.ffmpeg.with_name("ffprobe"), result),
                                       work, 15, capture=True)
                metadata = json.loads(raw)
                stream = next(row for row in metadata["streams"] if row["codec_type"] == "video")
                width, height = stream["width"], stream["height"]
                duration = float(metadata["format"]["duration"])
                has_audio = any(row["codec_type"] == "audio" for row in metadata["streams"])
                if not duration > 0 or min(width, height) < 1:
                    raise ValueError("Empty video stream")
            except (ValueError, KeyError, TypeError, StopIteration) as error:
                raise MediaError("The local engine produced an invalid video file.") from error
        else:
            with result.open("rb") as handle:
                header = handle.read(24)
            if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                raise MediaError("The local engine produced an invalid PNG file.")
            width, height = struct.unpack(">II", header[16:24])
        result.chmod(0o600)
        result.replace(final)
    path = final if workspace.output_root else final.relative_to(workspace.root)
    return Artifact(model, path.as_posix(), mime, final.stat().st_size,
                    round(monotonic() - started, 2), seed, width, height, duration, has_audio)


def bootstrap(config: Path, workspace: Workspace, interpreter: str, timeout: int, *,
              worker_cwd: bool = False, worker_temp_output: bool = False) -> dict:
    workspace_flag = "--workspace-parent" if worker_cwd else "--workspace"
    args = ["-m", "viventium_media.server", "serve", "--config", str(config), workspace_flag, str(workspace.root)]
    if worker_temp_output:
        args.append("--worker-temp-output")
    codex = "\n".join([
        "[mcp_servers.viventium_media]",
        f"command = {json.dumps(interpreter, ensure_ascii=False)}",
        f"args = {json.dumps(args, ensure_ascii=False)}",
        f"tool_timeout_sec = {timeout + 60}",
    ])
    return {
        "codex_config_append": codex,
        "claude_project_mcp": {"mcpServers": {"viventium_media": {"command": interpreter, "args": args}}},
    }
