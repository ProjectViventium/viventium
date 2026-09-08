#!/usr/bin/env python3
"""Byte-stream adapter for the selected, verified Telegram transcription owner."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import sys


def result(status, *, code=None, transcript=None):
    value = {"status": status}
    if code:
        value["code"] = code
    if transcript is not None:
        value["transcript"] = transcript
    return value


def engine_readiness(config):
    """Inspect the configured owner without loading/downloading a replacement model."""
    if config.WHISPER_MODE in ("local", "pywhispercpp"):
        if importlib.util.find_spec("pywhispercpp") is None or shutil.which("ffmpeg") is None:
            return result("unavailable", code="transcription_dependencies_unavailable")
        explicit = config.LOCAL_WHISPER_MODEL_PATH
        if explicit and explicit != "/path/to/your/ggml-model.bin":
            model = Path(explicit).expanduser()
        else:
            name = config._normalize_local_whisper_model_name(os.environ.get("LOCAL_WHISPER_MODEL_NAME"))
            filename = config._LOCAL_WHISPER_MODEL_FILES.get(name)
            if not filename:
                return result("unavailable", code="transcription_model_unsupported")
            cache = Path(os.environ.get("VIVENTIUM_WHISPER_CACHE_DIR") or Path.home() / ".cache/whisper")
            model = cache.expanduser() / filename
            if not model.is_file():
                return result("unavailable", code="transcription_model_unavailable")
            if config._sha1_file(model) != config._LOCAL_WHISPER_MODEL_SHA1.get(filename):
                return result("unavailable", code="transcription_model_invalid")
        if not model.is_file() or not os.access(model, os.R_OK):
            return result("unavailable", code="transcription_model_unavailable")
        # This is the same verified configured model. Prevent the engine's installer fallback
        # from downloading anything during a read-only tool invocation.
        config.LOCAL_WHISPER_MODEL_PATH = str(model)
    elif config.WHISPER_MODE == "assemblyai":
        if not config.ASSEMBLYAI_API_KEY:
            return result("unavailable", code="transcription_auth_unavailable")
    elif config.WHISPER_MODE == "openai":
        # Constructing the configured HTTP client performs no transcription/network call.
        config.ensure_stt_engine()
        if not config.whisperBot:
            return result("unavailable", code="transcription_auth_unavailable")
    else:
        return result("unavailable", code="transcription_provider_unsupported")
    return result("ready")


def transcription_failure_code(error):
    """Retain existing typed HTTP/network failures; never classify human error wording."""
    import requests

    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (TimeoutError, requests.exceptions.Timeout)):
            return "transcription_timeout"
        if isinstance(current, (ConnectionError, requests.exceptions.ConnectionError)):
            return "transcription_network_unavailable"
        response = getattr(current, "response", None)
        status = getattr(response, "status_code", None)
        if status in (401, 403):
            return "transcription_auth_rejected"
        if status == 429:
            try:
                code = response.json().get("error", {}).get("code")
            except (ValueError, AttributeError):
                code = None
            return "transcription_quota_exhausted" if code == "insufficient_quota" else "transcription_rate_limited"
        if isinstance(status, int) and status >= 400:
            return "transcription_provider_rejected"
        current = current.__cause__ or current.__context__
    return "transcription_failed"


def run_engine(args):
    from dotenv import dotenv_values

    runtime = Path(os.environ.get("VIVENTIUM_RUNTIME_DIR") or Path(args.app_support_dir) / "runtime")
    # Reuse the same compiled provider/engine settings as the receiver. Never source shell text.
    for env_file in (runtime / "runtime.env", runtime / "service-env/telegram.config.env"):
        for key, value in dotenv_values(env_file).items():
            if value is not None:
                os.environ[key] = value
    sys.path.insert(0, args.engine)
    logging.disable(logging.CRITICAL)
    with contextlib.redirect_stdout(sys.stderr):
        import config
        ready = engine_readiness(config)
        if ready["status"] != "ready" or args.check:
            return ready
        from aient.aient.utils.scripts import get_audio_message

        audio = sys.stdin.buffer.read(args.max_bytes + 1)
        if not audio or len(audio) != args.max_bytes:
            return result("rejected", code="audio_size_invalid")
        try:
            transcript = get_audio_message(audio, raise_errors=True)
        except Exception as error:
            return result("unavailable", code=transcription_failure_code(error))
    return result("completed", transcript=transcript)


def main():
    # Selected component code is sealed; imports must not add cache files to it.
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-support-dir", required=True)
    parser.add_argument("--max-bytes", type=int, default=100 * 1024 * 1024)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--engine", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.max_bytes < 1 or args.max_bytes > 1024 * 1024 * 1024:
        parser.error("invalid byte limit")
    try:
        if args.engine:
            # One bounded call through the existing runtime lock directory; competing calls
            # return capacity honestly instead of loading another speech model concurrently.
            lock_dir = Path(args.app_support_dir) / "state/runtime/locks"
            lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (lock_dir / "transcription-tool.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    value = result("unavailable", code="transcription_busy")
                else:
                    value = run_engine(args)
        else:
            from telegram_runtime_component import resolve

            selection = resolve(argparse.Namespace(
                app_support_dir=args.app_support_dir,
                selection_file=str(Path(args.app_support_dir) / "runtime/components/telegram-viventium.json"),
            ))
            os.execve(selection["python"], [selection["python"], str(Path(__file__).resolve()),
                *sys.argv[1:], "--engine", selection["execution_root"]], dict(os.environ))
    except Exception:
        value = result("unavailable", code="transcription_runtime_unavailable")
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
