from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "TelegramVivBot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

_fake_pil = types.ModuleType("PIL")
_fake_pil_image = types.ModuleType("PIL.Image")
_fake_pil.Image = _fake_pil_image
sys.modules.setdefault("PIL", _fake_pil)
sys.modules.setdefault("PIL.Image", _fake_pil_image)
if "config" in sys.modules and not hasattr(sys.modules["config"], "__file__"):
    sys.modules.pop("config", None)
if "md2tgmd" in sys.modules and not hasattr(sys.modules["md2tgmd"], "__path__"):
    sys.modules.pop("md2tgmd", None)

import bot as tg_bot  # noqa: E402
import local_qa_service_ack as ack_module  # noqa: E402


_QA_ENV_KEYS = (
    "VIVENTIUM_LOCAL_QA_CASE_ID",
    "VIVENTIUM_LOCAL_QA_SESSION_REF",
)


@pytest.fixture(autouse=True)
def _isolate_local_qa_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _QA_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _write_helper(tmp_path: Path, body: str) -> Path:
    helper = tmp_path / "qa-ack-helper"
    helper.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    helper.chmod(0o700)
    return helper


def _activate(monkeypatch: pytest.MonkeyPatch, helper: Path) -> None:
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_CASE_ID", "TR-026")
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_SESSION_REF", "qa_synthetic_session")
    monkeypatch.setattr(ack_module, "_HELPER_PATH", helper)


@pytest.mark.parametrize(
    "present_keys",
    [(), ("VIVENTIUM_LOCAL_QA_CASE_ID",), ("VIVENTIUM_LOCAL_QA_SESSION_REF",)],
)
def test_ack_is_inactive_unless_case_and_session_are_both_set(
    present_keys: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in present_keys:
        monkeypatch.setenv(key, "synthetic")

    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("inactive local QA must not launch a helper")

    monkeypatch.setattr(ack_module.subprocess, "run", forbidden_run)

    assert ack_module.acknowledge_local_qa_service("telegram-bot") is False


@pytest.mark.parametrize(
    "unsafe_kind",
    ["relative", "symlink", "world_writable", "not_executable", "directory"],
)
def test_ack_rejects_unsafe_helper_without_launching_it(
    unsafe_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    helper = _write_helper(tmp_path, "raise SystemExit(0)")
    configured: Path | str = helper
    if unsafe_kind == "relative":
        configured = Path("qa-ack-helper")
    elif unsafe_kind == "symlink":
        configured = tmp_path / "qa-ack-link"
        configured.symlink_to(helper)
    elif unsafe_kind == "world_writable":
        helper.chmod(0o722)
    elif unsafe_kind == "not_executable":
        helper.chmod(0o600)
    elif unsafe_kind == "directory":
        configured = tmp_path / "qa-ack-directory"
        configured.mkdir(mode=0o700)

    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_CASE_ID", "TR-026")
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_SESSION_REF", "qa_synthetic_session")
    monkeypatch.setattr(ack_module, "_HELPER_PATH", Path(configured))
    monkeypatch.setattr(
        ack_module.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unsafe helper must not launch")
        ),
    )

    with caplog.at_level(logging.WARNING, logger=ack_module.__name__):
        assert ack_module.acknowledge_local_qa_service("telegram-bot") is False

    assert [record.getMessage() for record in caplog.records] == [
        "local_qa_service_ack_failed"
    ]


def test_ack_invokes_exact_command_with_inherited_environment_and_suppressed_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    capture_path = tmp_path / "capture.json"
    helper = _write_helper(
        tmp_path,
        "\n".join(
            (
                "import json, os, pathlib, sys",
                "pathlib.Path(os.environ['SYNTHETIC_ACK_CAPTURE']).write_text(",
                "    json.dumps({'argv': sys.argv[1:], "
                "'inherited': os.environ.get('SYNTHETIC_PARENT_VALUE')}),",
                "    encoding='utf-8',",
                ")",
                "print('child-private-stdout')",
                "print('child-private-stderr', file=sys.stderr)",
            )
        ),
    )
    _activate(monkeypatch, helper)
    monkeypatch.setenv("SYNTHETIC_ACK_CAPTURE", str(capture_path))
    monkeypatch.setenv("SYNTHETIC_PARENT_VALUE", "inherited")

    assert ack_module.acknowledge_local_qa_service("telegram-bot") is True

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured == {
        "argv": [
            "acknowledge",
            "--service-id",
            "telegram-bot",
            "--pid",
            str(os.getpid()),
            "--executable",
            sys.executable,
        ],
        "inherited": "inherited",
    }
    assert capfd.readouterr() == ("", "")


def test_nonzero_helper_logs_only_safe_marker_and_does_not_raise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    helper = _write_helper(
        tmp_path,
        "import sys\nprint('private-child-output')\nraise SystemExit(7)",
    )
    _activate(monkeypatch, helper)

    with caplog.at_level(logging.WARNING, logger=ack_module.__name__):
        assert ack_module.acknowledge_local_qa_service("telegram-bot") is False

    assert [record.getMessage() for record in caplog.records] == [
        "local_qa_service_ack_failed"
    ]
    assert str(helper) not in caplog.text
    assert "private-child-output" not in caplog.text


@pytest.mark.parametrize(
    "failure",
    (
        subprocess.TimeoutExpired(cmd="synthetic", timeout=5),
        OSError("synthetic private child failure"),
    ),
)
def test_timeout_or_launch_error_logs_only_safe_marker_and_does_not_raise(
    failure: Exception,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    helper = _write_helper(tmp_path, "raise SystemExit(0)")
    _activate(monkeypatch, helper)

    def fail_run(*_args, **kwargs):
        assert kwargs["timeout"] == 5
        assert "env" not in kwargs
        raise failure

    monkeypatch.setattr(ack_module.subprocess, "run", fail_run)
    with caplog.at_level(logging.WARNING, logger=ack_module.__name__):
        assert ack_module.acknowledge_local_qa_service("telegram-bot") is False

    assert [record.getMessage() for record in caplog.records] == [
        "local_qa_service_ack_failed"
    ]
    assert "synthetic private child failure" not in caplog.text


@pytest.mark.asyncio
async def test_telegram_ack_runs_after_post_init_ready_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class _Bot:
        async def set_my_commands(self, _commands):
            return None

        async def set_my_description(self, _description):
            return None

    application = types.SimpleNamespace(bot=_Bot(), bot_data={})
    monkeypatch.setattr(tg_bot.config, "ChatGPTbot", None)
    monkeypatch.setattr(
        tg_bot,
        "schedule_telegram_singleton_readiness",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        tg_bot,
        "_write_telegram_ready_marker",
        lambda: events.append("ready") or True,
    )

    def acknowledge(service_id: str) -> bool:
        assert tg_bot._SOURCE_ORDER_RECOVERY_TASK_KEY in application.bot_data
        assert tg_bot._BOT_METADATA_TASK_KEY in application.bot_data
        events.append(f"ack:{service_id}")
        return True

    monkeypatch.setattr(
        tg_bot, "acknowledge_local_qa_service", acknowledge, raising=False
    )

    await tg_bot.post_init(application)
    assert events == ["ready", "ack:telegram-bot"]
    await tg_bot.post_shutdown(application)


@pytest.mark.asyncio
async def test_telegram_remains_available_when_acknowledgement_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    helper = _write_helper(tmp_path, "raise SystemExit(9)")
    _activate(monkeypatch, helper)

    class _Bot:
        async def set_my_commands(self, _commands):
            return None

        async def set_my_description(self, _description):
            return None

    application = types.SimpleNamespace(bot=_Bot(), bot_data={})
    monkeypatch.setattr(tg_bot.config, "ChatGPTbot", None)
    monkeypatch.setattr(
        tg_bot,
        "schedule_telegram_singleton_readiness",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(tg_bot, "_write_telegram_ready_marker", lambda: True)

    with caplog.at_level(logging.WARNING, logger=ack_module.__name__):
        await tg_bot.post_init(application)

    assert tg_bot._SOURCE_ORDER_RECOVERY_TASK_KEY in application.bot_data
    assert [record.getMessage() for record in caplog.records] == [
        "local_qa_service_ack_failed"
    ]
    await tg_bot.post_shutdown(application)
