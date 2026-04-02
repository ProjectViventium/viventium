# === VIVENTIUM START ===
# Feature: Preferences config hot-path regression tests.
# Purpose: Keep /info -> Preferences -> checkbox interactions fast by ensuring
# we avoid redundant config writes and status lookups in menu rendering.
# Added: 2026-02-15
# === VIVENTIUM END ===

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot import config as telegram_config


def _build_user_config(monkeypatch):
    saved = []

    def _fake_save_user_config(user_id, cfg):
        saved.append((user_id, dict(cfg)))

    def _fake_load_user_config(_user_id):
        return {}

    original_exists = telegram_config.os.path.exists

    def _fake_exists(path):
        if path == telegram_config.CONFIG_DIR:
            return False
        return original_exists(path)

    monkeypatch.setattr(telegram_config, "save_user_config", _fake_save_user_config)
    monkeypatch.setattr(telegram_config, "load_user_config", _fake_load_user_config)
    monkeypatch.setattr(telegram_config.os.path, "exists", _fake_exists)

    preferences = {
        "LONG_TEXT": True,
        "LONG_TEXT_SPLIT": True,
        "FILE_UPLOAD_MESS": True,
        "VOICE_RESPONSES_ENABLED": True,
        "ALWAYS_VOICE_RESPONSE": False,
        "LIBRECHAT_CONVERSATION_STATE_VERSION": "",
        "CLIENT_TIMEZONE": "America/Toronto",
    }
    cfg = telegram_config.UserConfig(
        mode="multiusers",
        api_key="k",
        api_url="https://example.com/v1/chat/completions",
        engine="grok-4-fast-reasoning",
        preferences=preferences,
        language="English",
        languages=None,
        systemprompt="sp",
    )
    return cfg, saved


def test_get_config_does_not_rewrite_on_every_read(monkeypatch):
    cfg, saved = _build_user_config(monkeypatch)
    saved.clear()

    assert cfg.get_config("user-1", "LONG_TEXT") is True
    assert len(saved) == 1

    assert cfg.get_config("user-1", "VOICE_RESPONSES_ENABLED") is True
    assert len(saved) == 1


def test_set_config_same_value_skips_persist(monkeypatch):
    cfg, saved = _build_user_config(monkeypatch)
    cfg.get_config("user-1", "ALWAYS_VOICE_RESPONSE")
    saved.clear()

    cfg.set_config("user-1", "ALWAYS_VOICE_RESPONSE", False)
    assert saved == []

    cfg.set_config("user-1", "ALWAYS_VOICE_RESPONSE", True)
    assert len(saved) == 1
    assert saved[0][0] == "user-1"
    assert saved[0][1]["ALWAYS_VOICE_RESPONSE"] is True


def test_internal_conversation_state_version_is_supported(monkeypatch):
    cfg, saved = _build_user_config(monkeypatch)

    assert cfg.get_config("user-1", "LIBRECHAT_CONVERSATION_STATE_VERSION") == ""
    saved.clear()

    cfg.set_config("user-1", "LIBRECHAT_CONVERSATION_STATE_VERSION", "2")

    assert len(saved) == 1
    assert saved[0][1]["LIBRECHAT_CONVERSATION_STATE_VERSION"] == "2"


def test_toggle_config_flips_boolean_and_persists_once(monkeypatch):
    cfg, saved = _build_user_config(monkeypatch)
    cfg.get_config("user-1", "LONG_TEXT")
    saved.clear()

    new_value = cfg.toggle_config("user-1", "LONG_TEXT")
    assert new_value is False
    assert cfg.get_config("user-1", "LONG_TEXT") is False
    assert len(saved) == 1
    assert saved[0][1]["LONG_TEXT"] is False


def test_create_buttons_uses_status_map_without_get_status(monkeypatch):
    def _fail_get_status(*_args, **_kwargs):
        raise AssertionError("get_status should not be called when status_map is provided")

    monkeypatch.setattr(telegram_config, "get_status", _fail_get_status)
    buttons = telegram_config.create_buttons(
        ["LONG_TEXT", "ALWAYS_VOICE_RESPONSE"],
        plugins_status=True,
        chatid="user-1",
        Suffix="_PREFERENCES",
        status_map={"LONG_TEXT": True, "ALWAYS_VOICE_RESPONSE": False},
    )

    flattened = [btn for row in buttons for btn in row]
    labels = [btn.text for btn in flattened]
    assert any(label.startswith("✅ ") for label in labels)
    assert any(label.startswith("☑️ ") for label in labels)


def test_update_first_buttons_message_adds_call_button_when_available(monkeypatch):
    monkeypatch.setattr(
        telegram_config,
        "get_telegram_call_url",
        lambda chatid: f"http://198.51.100.25:3300/?chatid={chatid}",
    )

    buttons = telegram_config.update_first_buttons_message("user-1")
    flattened = [btn for row in buttons for btn in row]

    call_button = next(btn for btn in flattened if btn.text == "Call Viventium")
    prefs_button = next(btn for btn in flattened if btn.text == "Preferences")

    assert call_button.url == "http://198.51.100.25:3300/?chatid=user-1"
    assert prefs_button.callback_data == "PREFERENCES"


def test_get_telegram_call_url_uses_convo_key_but_sends_real_telegram_user_id(monkeypatch):
    calls = []

    class _Resp:
        status_code = 200
        content = b'{"callUrl":"http://198.51.100.25:3300/?ok=1"}'

        @staticmethod
        def json():
            return {"callUrl": "http://198.51.100.25:3300/?ok=1"}

    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://localhost:3180")
    monkeypatch.setenv("VIVENTIUM_CALL_SESSION_SECRET", "secret")
    monkeypatch.setattr(
        telegram_config.Users,
        "get_config",
        lambda convo_id, key: {
            ("123456789:123456789", "LIBRECHAT_CONVERSATION_ID"): "conv-1",
            ("123456789:123456789", "LIBRECHAT_AGENT_ID"): "agent-1",
        }.get((convo_id, key), ""),
    )

    def _fake_post(url, json=None, headers=None, timeout=None):
        calls.append((url, json, headers, timeout))
        return _Resp()

    monkeypatch.setattr(telegram_config.requests, "post", _fake_post)
    telegram_config._CALL_URL_CACHE.clear()

    result = telegram_config.get_telegram_call_url("123456789:123456789")

    assert result == "http://198.51.100.25:3300/?ok=1"
    assert calls
    assert calls[0][1]["telegramUserId"] == "123456789"
    assert calls[0][1]["conversationId"] == "conv-1"
    assert calls[0][1]["agentId"] == "agent-1"


def test_get_telegram_call_link_result_marks_link_required(monkeypatch):
    class _Resp:
        status_code = 401
        content = b'{"error":"Telegram account not linked","linkRequired":true}'
        text = '{"error":"Telegram account not linked","linkRequired":true}'

        @staticmethod
        def json():
            return {"error": "Telegram account not linked", "linkRequired": True}

    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://localhost:3180")
    monkeypatch.setenv("VIVENTIUM_CALL_SESSION_SECRET", "secret")
    monkeypatch.setattr(telegram_config.Users, "get_config", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(telegram_config.requests, "post", lambda *_args, **_kwargs: _Resp())
    telegram_config._CALL_URL_CACHE.clear()

    result = telegram_config.get_telegram_call_link_result("123456789")

    assert result["url"] == ""
    assert result["status_code"] == 401
    assert result["link_required"] is True
    assert result["public_url_required"] is False
    assert result["error"] == "Telegram account not linked"


def test_get_telegram_call_link_result_marks_public_playground_required(monkeypatch):
    class _Resp:
        status_code = 409
        content = b'{"error":"Telegram calls need a configured public HTTPS Viventium voice URL","publicPlaygroundRequired":true}'
        text = '{"error":"Telegram calls need a configured public HTTPS Viventium voice URL","publicPlaygroundRequired":true}'

        @staticmethod
        def json():
            return {
                "error": "Telegram calls need a configured public HTTPS Viventium voice URL",
                "publicPlaygroundRequired": True,
            }

    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://localhost:3180")
    monkeypatch.setenv("VIVENTIUM_CALL_SESSION_SECRET", "secret")
    monkeypatch.setattr(telegram_config.Users, "get_config", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(telegram_config.requests, "post", lambda *_args, **_kwargs: _Resp())
    telegram_config._CALL_URL_CACHE.clear()

    result = telegram_config.get_telegram_call_link_result("123456789")

    assert result["url"] == ""
    assert result["status_code"] == 409
    assert result["link_required"] is False
    assert result["public_url_required"] is True
    assert result["error"] == "Telegram calls need a configured public HTTPS Viventium voice URL"


def test_get_telegram_call_url_does_not_cache_insecure_remote_urls(monkeypatch):
    class _Resp:
        status_code = 200
        content = b'{"callUrl":"http://198.51.100.25:3300/?ok=1"}'
        text = '{"callUrl":"http://198.51.100.25:3300/?ok=1"}'

        @staticmethod
        def json():
            return {"callUrl": "http://198.51.100.25:3300/?ok=1"}

    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://localhost:3180")
    monkeypatch.setenv("VIVENTIUM_CALL_SESSION_SECRET", "secret")
    monkeypatch.setattr(telegram_config.Users, "get_config", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(telegram_config.requests, "post", lambda *_args, **_kwargs: _Resp())
    telegram_config._CALL_URL_CACHE.clear()

    result = telegram_config.get_telegram_call_url("123456789")

    assert result == "http://198.51.100.25:3300/?ok=1"
    assert telegram_config._CALL_URL_CACHE == {}
