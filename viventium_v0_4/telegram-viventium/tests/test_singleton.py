from pathlib import Path
import os
import sys

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
