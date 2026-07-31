from pathlib import Path
import asyncio
import json
import os
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot.utils.singleton import (
    SingletonAlreadyRunning,
    acquire_telegram_singleton_lock,
    cancel_telegram_singleton_readiness,
    clear_telegram_singleton_receipt,
    schedule_telegram_singleton_readiness,
    telegram_singleton_lock_path,
)


def test_telegram_singleton_blocks_second_same_token_process():
    token = f"123456:test-singleton-{os.getpid()}"
    first = acquire_telegram_singleton_lock(token)
    try:
        with pytest.raises(SingletonAlreadyRunning) as exc_info:
            acquire_telegram_singleton_lock(token)
        assert exc_info.value.owner_pid == str(os.getpid())
    finally:
        first.close()


def test_telegram_singleton_lock_path_does_not_expose_token():
    token = "123456:very-secret-token-value"
    path = telegram_singleton_lock_path(token)
    assert "very-secret" not in str(path)
    assert str(path).endswith(".lock")


def test_telegram_singleton_reacquires_after_release(tmp_path):
    token = f"123456:test-reacquire-{os.getpid()}"
    first = acquire_telegram_singleton_lock(token, lock_dir=tmp_path)
    first.close()

    second = acquire_telegram_singleton_lock(token, lock_dir=tmp_path)
    try:
        assert second
    finally:
        second.close()


def test_telegram_singleton_different_tokens_do_not_collide(tmp_path):
    first = acquire_telegram_singleton_lock("123456:first-token", lock_dir=tmp_path)
    second = acquire_telegram_singleton_lock("123456:second-token", lock_dir=tmp_path)
    try:
        assert telegram_singleton_lock_path("123456:first-token", lock_dir=tmp_path) != (
            telegram_singleton_lock_path("123456:second-token", lock_dir=tmp_path)
        )
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize("token", ["", "   "])
def test_telegram_singleton_requires_token(token, tmp_path):
    with pytest.raises(ValueError):
        acquire_telegram_singleton_lock(token, lock_dir=tmp_path)


def test_owner_readiness_receipt_is_owner_only_and_never_contains_token(
    tmp_path, monkeypatch
):
    token = "123456:receipt-secret-value"
    receipt = tmp_path / "state" / "owner.json"
    execution_root = tmp_path / "runtime-components" / "telegram" / "TelegramVivBot"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_OWNER_RECEIPT", str(receipt))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_OWNER_REPO_ROOT", str(ROOT))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_EXECUTION_ROOT", str(execution_root))
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "user-configs"))
    monkeypatch.setenv(
        "VIVENTIUM_TELEGRAM_OWNER_LAUNCH_SCRIPT", str(tmp_path / "launch.sh")
    )

    lock = acquire_telegram_singleton_lock(token, lock_dir=tmp_path / "locks")
    try:
        pending = json.loads(receipt.read_text(encoding="utf-8"))
        assert pending["schema_version"] == 2
        assert pending["repo_root"] == str(ROOT.resolve())
        assert pending["execution_root"] == str(execution_root.resolve())
        assert pending["ready"] is False
        assert pending["readiness_proof"] == "initializing"
        assert token not in receipt.read_text(encoding="utf-8")
        assert receipt.stat().st_mode & 0o777 == 0o600

        async def publish_after_running():
            application = SimpleNamespace(
                updater=SimpleNamespace(running=False),
                running=False,
            )
            task = schedule_telegram_singleton_readiness(
                application,
                token,
                transport="polling",
            )
            await asyncio.sleep(0)
            application.updater.running = True
            application.running = True
            await task

        asyncio.run(publish_after_running())
        ready = json.loads(receipt.read_text(encoding="utf-8"))
        assert ready["ready"] is True
        assert ready["readiness_proof"] == "polling_started"
        assert ready["process_start_id"]
    finally:
        clear_telegram_singleton_receipt()
        lock.close()

    assert not receipt.exists()


def test_failure_between_post_init_and_polling_keeps_receipt_pending(
    tmp_path, monkeypatch
):
    token = "123456:failure-between-post-init-and-polling"
    receipt = tmp_path / "state" / "owner.json"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_OWNER_RECEIPT", str(receipt))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_OWNER_REPO_ROOT", str(ROOT))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_EXECUTION_ROOT", str(TELEGRAM_ROOT))
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "user-configs"))
    monkeypatch.setenv(
        "VIVENTIUM_TELEGRAM_OWNER_LAUNCH_SCRIPT", str(tmp_path / "launch.sh")
    )
    lock = acquire_telegram_singleton_lock(token, lock_dir=tmp_path / "locks")

    try:
        async def fail_before_polling():
            # post_init scheduled the watcher; updater bootstrap then failed
            # before either public running state could become true.
            application = SimpleNamespace(
                updater=SimpleNamespace(running=False),
                running=False,
            )
            task = schedule_telegram_singleton_readiness(
                application,
                token,
                transport="polling",
            )
            await asyncio.sleep(0.05)
            await cancel_telegram_singleton_readiness(task)

        asyncio.run(fail_before_polling())
        pending = json.loads(receipt.read_text(encoding="utf-8"))
        assert pending["ready"] is False
        assert pending["readiness_proof"] == "initializing"
    finally:
        clear_telegram_singleton_receipt()
        lock.close()


def test_pinned_ptb_application_requires_both_running_states_before_ready(
    tmp_path, monkeypatch
):
    telegram_ext = pytest.importorskip("telegram.ext")
    token = "123456:pinned-ptb-readiness"
    receipt = tmp_path / "state" / "owner.json"
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_OWNER_RECEIPT", str(receipt))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_OWNER_REPO_ROOT", str(ROOT))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_EXECUTION_ROOT", str(TELEGRAM_ROOT))
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "user-configs"))
    monkeypatch.setenv(
        "VIVENTIUM_TELEGRAM_OWNER_LAUNCH_SCRIPT", str(tmp_path / "launch.sh")
    )
    lock = acquire_telegram_singleton_lock(token, lock_dir=tmp_path / "locks")

    async def exercise_real_application():
        application = telegram_ext.ApplicationBuilder().token(token).build()
        task = schedule_telegram_singleton_readiness(
            application,
            token,
            transport="polling",
        )
        # Models Updater.start_polling returning while Application.start has
        # not yet succeeded. This must still be pending.
        application.updater._running = True
        await asyncio.sleep(0.05)
        assert json.loads(receipt.read_text(encoding="utf-8"))["ready"] is False
        application._running = True
        await task

    try:
        asyncio.run(exercise_real_application())
        ready = json.loads(receipt.read_text(encoding="utf-8"))
        assert ready["ready"] is True
        assert ready["readiness_proof"] == "polling_started"
    finally:
        clear_telegram_singleton_receipt()
        lock.close()
