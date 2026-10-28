# === VIVENTIUM START ===
# Feature: Preferences config hot-path regression tests.
# Purpose: Keep /info -> Preferences -> checkbox interactions fast by ensuring
# we avoid redundant config writes and status lookups in menu rendering.
# Added: 2026-02-15
# === VIVENTIUM END ===

import sys
import asyncio
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot import config as telegram_config


def test_legacy_long_text_split_preference_is_not_forwarded() -> None:
    launcher = (ROOT.parent / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert "\n    LONG_TEXT_SPLIT\n" not in launcher


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


def test_existing_preferences_are_not_rewritten_or_overridden_on_startup(monkeypatch):
    saved = []
    existing = {
        "systemprompt": "preserve the user's legacy value",
        "LONG_TEXT": False,
        "UNKNOWN_PERSONALIZATION": {"kept": True},
    }
    monkeypatch.setattr(
        telegram_config,
        "save_user_config",
        lambda user_id, cfg: saved.append((user_id, dict(cfg))),
    )
    monkeypatch.setattr(
        telegram_config,
        "load_user_config",
        lambda _user_id: dict(existing),
    )
    monkeypatch.setattr(telegram_config.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(telegram_config.os, "listdir", lambda _path: ["global.json"])

    cfg = telegram_config.UserConfig(
        mode="multiusers",
        api_key="new-default-key",
        api_url="https://example.invalid/v1",
        engine="gpt-5",
        preferences={"LONG_TEXT": True, "ALWAYS_VOICE_RESPONSE": False},
        language="English",
        languages=None,
        systemprompt="new release default",
    )

    assert saved == []
    assert cfg.users["global"].data["systemprompt"] == existing["systemprompt"]
    assert cfg.users["global"].data["LONG_TEXT"] is False
    assert cfg.users["global"].data["UNKNOWN_PERSONALIZATION"] == {"kept": True}
    assert cfg.users["global"].data["ALWAYS_VOICE_RESPONSE"] is False


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
        ["LONG_TEXT", "FILE_UPLOAD_MESS", "ALWAYS_VOICE_RESPONSE"],
        plugins_status=True,
        chatid="user-1",
        Suffix="_PREFERENCES",
        status_map={"LONG_TEXT": True, "FILE_UPLOAD_MESS": False, "ALWAYS_VOICE_RESPONSE": False},
    )

    flattened = [btn for row in buttons for btn in row]
    labels = [btn.text for btn in flattened]
    assert "✅ Long text merge" in labels
    assert "☑️ File upload message" in labels
    assert "⬜ Always Include Voice Reply · OFF" in labels


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


def test_update_first_buttons_message_can_skip_call_link_fetch(monkeypatch):
    def _fail_fetch(_chatid):
        raise AssertionError("call-link HTTP fetch should not run in the Preferences hot path")

    monkeypatch.setattr(telegram_config, "get_telegram_call_url", _fail_fetch)
    telegram_config._CALL_URL_CACHE.clear()

    buttons = telegram_config.update_first_buttons_message("user-1", fetch_call_url=False)
    flattened = [btn for row in buttons for btn in row]

    assert [btn.text for btn in flattened] == ["Preferences"]
    assert flattened[0].callback_data == "PREFERENCES"


def test_update_first_buttons_message_uses_explicit_call_url_without_fetch(monkeypatch):
    def _fail_fetch(_chatid):
        raise AssertionError("explicit call_url should avoid call-link HTTP fetch")

    monkeypatch.setattr(telegram_config, "get_telegram_call_url", _fail_fetch)

    buttons = telegram_config.update_first_buttons_message(
        "user-1",
        call_url="http://198.51.100.25:3300/?ok=1",
        fetch_call_url=False,
    )
    flattened = [btn for row in buttons for btn in row]

    assert flattened[0].text == "Call Viventium"
    assert flattened[0].url == "http://198.51.100.25:3300/?ok=1"
    assert flattened[1].text == "Preferences"


def test_update_first_buttons_message_uses_cached_call_url_without_fetch(monkeypatch):
    def _fail_fetch(_chatid):
        raise AssertionError("cached call_url should avoid call-link HTTP fetch")

    monkeypatch.setattr(telegram_config, "get_telegram_call_url", _fail_fetch)
    telegram_config._CALL_URL_CACHE.clear()
    telegram_config._CALL_URL_CACHE["user-1"] = {
        "url": "https://voice.example.test/?cached=1",
        "expires_at": time.time() + 60,
    }

    buttons = telegram_config.update_first_buttons_message("user-1", fetch_call_url=False)
    flattened = [btn for row in buttons for btn in row]

    assert flattened[0].text == "Call Viventium"
    assert flattened[0].url == "https://voice.example.test/?cached=1"
    assert flattened[1].text == "Preferences"


def test_voice_preference_sync_is_backgrounded_in_running_event_loop(monkeypatch):
    calls = []

    def _slow_sync(*args):
        time.sleep(0.15)
        calls.append(args)

    async def _run():
        monkeypatch.setattr(telegram_config, "sync_voice_preferences", _slow_sync)

        start = time.perf_counter()
        task = telegram_config.schedule_voice_preferences_sync("user-1", True, True)
        elapsed = time.perf_counter() - start

        assert task is not None
        assert elapsed < 0.05
        await task

    asyncio.run(_run())

    assert calls == [("user-1", True, True, True)]


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
            ("123456789:123456789", "LIBRECHAT_CONVERSATION_STATE"): {
                "conversation_id": "conv-1", "generation": "a" * 64,
            },
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


@pytest.mark.parametrize(
    "fragment_key",
    ["viventiumCallLaunch", "viventiumCallCapability"],
)
def test_get_telegram_call_url_never_caches_call_bearer_fragments(monkeypatch, fragment_key):
    call_url = f"https://voice.example.test/call-bootstrap?callSessionId=call-1#{fragment_key}={'L' * 43}"

    class _Resp:
        status_code = 200
        content = b"result"
        text = "result"

        @staticmethod
        def json():
            return {"callUrl": call_url}

    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://localhost:3180")
    monkeypatch.setenv("VIVENTIUM_CALL_SESSION_SECRET", "secret")
    monkeypatch.setattr(telegram_config.Users, "get_config", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(telegram_config.requests, "post", lambda *_args, **_kwargs: _Resp())
    telegram_config._CALL_URL_CACHE.clear()

    assert telegram_config.get_telegram_call_url("123456789") == call_url
    assert telegram_config._CALL_URL_CACHE == {}


def test_cached_legacy_call_bearer_is_removed_instead_of_reused():
    telegram_config._CALL_URL_CACHE.clear()
    telegram_config._CALL_URL_CACHE["123456789"] = {
        "url": (
            "https://voice.example.test/call-bootstrap?callSessionId=call-1"
            f"#viventiumCallCapability={'C' * 43}"
        ),
        "expires_at": time.time() + 60,
    }

    assert telegram_config.get_cached_telegram_call_url("123456789") == ""
    assert telegram_config._CALL_URL_CACHE == {}


VOICE_KEYS = ("VOICE_RESPONSES_ENABLED", "REPLY_VOICE_WITH_VOICE", "ALWAYS_VOICE_RESPONSE")


def _voice_config(monkeypatch, tmp_path, mode, *, existing=None):
    import json
    monkeypatch.setattr(telegram_config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(telegram_config, "ADMIN_LIST", None)
    storage_key = "global" if mode == "global" else "123:123"
    path = tmp_path / f"{storage_key}.json"
    values = {**{key: True for key in VOICE_KEYS}, "CLIENT_TIMEZONE": "", "LONG_TEXT": True}
    path.write_text(json.dumps(values if existing is None else existing), encoding="utf-8")
    cfg = telegram_config.UserConfig(mode=mode, preferences=values)
    return cfg, storage_key, path


@pytest.mark.parametrize("mode", ["global", "multiusers"])
@pytest.mark.parametrize("key", VOICE_KEYS)
@pytest.mark.parametrize("operation", ["set", "toggle"])
def test_voice_preference_changes_persist_and_sync_authenticated_requester(
    monkeypatch, tmp_path, mode, key, operation,
):
    import json
    cfg, storage_key, path = _voice_config(monkeypatch, tmp_path, mode)
    synced, saved = [], []
    original_save = telegram_config.save_user_config
    def save(user_id, values):
        saved.append(user_id)
        original_save(user_id, values)
    monkeypatch.setattr(telegram_config, "save_user_config", save)
    monkeypatch.setattr(telegram_config, "schedule_voice_preferences_sync", lambda *args: synced.append(args))
    if operation == "set":
        cfg.set_config("123:123", key, False, telegram_user_id=123)
    else:
        assert cfg.toggle_config("123:123", key, telegram_user_id=123) is False
    assert saved == [storage_key]
    assert synced == [(
        "123", key != "ALWAYS_VOICE_RESPONSE", key != "VOICE_RESPONSES_ENABLED",
        key != "REPLY_VOICE_WITH_VOICE",
    )]
    assert json.loads(path.read_text())[key] is False
    reloaded = telegram_config.UserConfig(mode=mode, preferences=cfg.preferences)
    assert reloaded.get_config("123:123", key) is False


@pytest.mark.parametrize("mode", ["global", "multiusers"])
def test_voice_preferences_preserve_explicit_legacy_false_and_missing_new_default(
    monkeypatch, tmp_path, mode,
):
    import json
    legacy = {"VOICE_RESPONSES_ENABLED": False, "ALWAYS_VOICE_RESPONSE": False,
        "CLIENT_TIMEZONE": "", "LONG_TEXT": True, "UNRELATED_SETTING": {"keep": "exact"}}
    cfg, _, path = _voice_config(monkeypatch, tmp_path, mode, existing=legacy)
    original_bytes = path.read_bytes()
    assert cfg.get_config("123:123", "VOICE_RESPONSES_ENABLED") is False
    assert cfg.get_config("123:123", "ALWAYS_VOICE_RESPONSE") is False
    assert cfg.get_config("123:123", "REPLY_VOICE_WITH_VOICE") is True
    assert path.read_bytes() == original_bytes
    monkeypatch.setattr(telegram_config, "schedule_voice_preferences_sync", lambda *args: None)
    cfg.toggle_config("123:123", "REPLY_VOICE_WITH_VOICE", telegram_user_id=123)
    persisted = json.loads(path.read_text())
    assert persisted["UNRELATED_SETTING"] == legacy["UNRELATED_SETTING"]
    assert persisted["VOICE_RESPONSES_ENABLED"] is False
    assert persisted["ALWAYS_VOICE_RESPONSE"] is False
    assert persisted["REPLY_VOICE_WITH_VOICE"] is False


@pytest.mark.parametrize("mode", ["global", "multiusers"])
def test_voice_sync_does_not_guess_owner_and_idempotent_explicit_set_can_refresh_core(
    monkeypatch, tmp_path, mode,
):
    cfg, _, path = _voice_config(monkeypatch, tmp_path, mode)
    synced = []
    monkeypatch.setattr(telegram_config, "schedule_voice_preferences_sync", lambda *args: synced.append(args))
    cfg.set_config("123:123", "ALWAYS_VOICE_RESPONSE", False)
    cfg.set_config("123:123", "LONG_TEXT", False, telegram_user_id=123)
    assert synced == []
    before = path.read_bytes()
    cfg.set_config("123:123", "ALWAYS_VOICE_RESPONSE", False, telegram_user_id=123)
    assert synced == [("123", False, True, True)]
    assert path.read_bytes() == before


def test_voice_sync_wire_retains_legacy_fields_and_adds_new_default(monkeypatch):
    calls = []
    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://127.0.0.1:3180")
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_SECRET", "synthetic-bridge-secret")
    class Response:
        status_code = 200
    def post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return Response()
    monkeypatch.setattr(telegram_config.requests, "post", post)
    telegram_config.sync_voice_preferences("123", False, True)
    assert calls == [("http://127.0.0.1:3180/api/viventium/telegram/preferences", {
        "telegramUserId": "123", "alwaysVoiceResponse": False,
        "voiceResponsesEnabled": True, "replyVoiceWithVoice": True,
    })]


def test_voice_public_defaults_and_preferences_order(monkeypatch, tmp_path):
    import ast
    source = ast.parse(Path(telegram_config.__file__).read_text())
    assignment = next(node for node in source.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "PREFERENCES" for target in node.targets))
    for key in VOICE_KEYS:
        monkeypatch.delenv(key, raising=False)
    namespace = {"os": telegram_config.os, "_get_bool_env": telegram_config._get_bool_env,
        "VIVENTIUM_TELEGRAM_DEFAULT_TIMEZONE": ""}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), "<product-preferences>", "exec"), namespace)
    assert all(namespace["PREFERENCES"][key] is True for key in VOICE_KEYS)
    cfg, _, _ = _voice_config(monkeypatch, tmp_path, "global")
    monkeypatch.setattr(telegram_config, "Users", cfg)
    monkeypatch.setattr(telegram_config, "PREFERENCES", cfg.preferences)
    rows = telegram_config.update_menu_buttons(cfg.preferences, "_PREFERENCES", "123:123")
    assert [row[0].text for row in rows[:3]] == [
        "✅ Master Switch · ON", "✅ Reply Voice with Voice · ON", "✅ Always Include Voice Reply · ON",
    ]
    assert all(len(row) == 1 for row in rows[:3])
    help_text = telegram_config.update_info_message()
    assert "Always Include Voice Reply includes all replies and proactive messages" in help_text
    assert "the model can still skip audio" in help_text
    assert "Always Include Voice Reply is off" in help_text


def test_voice_sync_preserves_toggle_order_without_blocking_other_owners(monkeypatch):
    import threading
    completed = []
    first_started, release_first = threading.Event(), threading.Event()
    def sync(owner, always, master, reply):
        if owner == "123" and not master:
            first_started.set()
            assert release_first.wait(2)
        completed.append((owner, master))
    monkeypatch.setattr(telegram_config, "sync_voice_preferences", sync)
    async def run():
        first = telegram_config.schedule_voice_preferences_sync("123", False, False, True)
        second = telegram_config.schedule_voice_preferences_sync("123", False, True, True)
        independent = telegram_config.schedule_voice_preferences_sync("456", True, True, True)
        try:
            assert await asyncio.to_thread(first_started.wait, 2)
            await independent
            assert ("123", True) not in completed
        finally:
            release_first.set()
        await asyncio.gather(first, second)
        await asyncio.sleep(0)
    asyncio.run(run())
    assert [value for owner, value in completed if owner == "123"] == [False, True]
    assert telegram_config._VOICE_PREFERENCE_SYNC_TASKS == {}


@pytest.mark.parametrize("group_key", ["-505:123", "-505:7:123", "505:123", "123:7:123"])
def test_group_or_topic_voice_settings_do_not_replace_private_core_preferences(monkeypatch, tmp_path, group_key):
    cfg, _, private_path = _voice_config(monkeypatch, tmp_path, "multiusers")
    synced = []
    monkeypatch.setattr(telegram_config, "schedule_voice_preferences_sync", lambda *args: synced.append(args))
    before = private_path.read_bytes()
    cfg.toggle_config(group_key, "REPLY_VOICE_WITH_VOICE", telegram_user_id=123)
    assert cfg.get_config(group_key, "REPLY_VOICE_WITH_VOICE") is False
    assert cfg.get_config("123:123", "REPLY_VOICE_WITH_VOICE") is True
    assert private_path.read_bytes() == before
    assert synced == []


@pytest.mark.parametrize("key", VOICE_KEYS)
@pytest.mark.parametrize("operation", ["set", "toggle"])
def test_global_voice_changes_require_configured_administrator_before_any_write(
    monkeypatch, tmp_path, key, operation,
):
    cfg, _, path = _voice_config(monkeypatch, tmp_path, "global")
    monkeypatch.setattr(telegram_config, "ADMIN_LIST", ["123"])
    synced = []
    monkeypatch.setattr(telegram_config, "schedule_voice_preferences_sync", lambda *args: synced.append(args))
    before = path.read_bytes()
    for requester in (None, "999"):
        with pytest.raises(PermissionError, match="configured administrator"):
            if operation == "set":
                cfg.set_config("123:123", key, False, telegram_user_id=requester)
            else:
                cfg.toggle_config("123:123", key, telegram_user_id=requester)
    assert path.read_bytes() == before
    assert cfg.get_config("123:123", key) is True
    assert synced == []
    if operation == "set":
        cfg.set_config("123:123", key, False, telegram_user_id=123)
    else:
        cfg.toggle_config("123:123", key, telegram_user_id=123)
    assert cfg.get_config("123:123", key) is False
    assert synced[0][0] == "123"


def test_unrestricted_global_voice_configuration_keeps_existing_shared_control(monkeypatch, tmp_path):
    cfg, _, _ = _voice_config(monkeypatch, tmp_path, "global")
    synced = []
    monkeypatch.setattr(telegram_config, "schedule_voice_preferences_sync", lambda *args: synced.append(args))
    assert telegram_config.ADMIN_LIST is None
    cfg.toggle_config("999:999", "VOICE_RESPONSES_ENABLED", telegram_user_id=999)
    assert cfg.get_config("999:999", "VOICE_RESPONSES_ENABLED") is False
    assert synced == [("999", True, False, True)]


@pytest.mark.parametrize("key", VOICE_KEYS)
@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("status_source", ["snapshot", "saved"])
def test_voice_toggle_label_has_explicit_state_and_empty_off_icon(monkeypatch, key, enabled, status_source):
    import types
    monkeypatch.setattr(telegram_config, "Users", types.SimpleNamespace(get_config=lambda *_args: enabled))
    options = {"status_map": {key: enabled}} if status_source == "snapshot" else {}
    rows = telegram_config.create_buttons([key], plugins_status=True, chatid="123:123",
        Suffix="_PREFERENCES", **options)
    button = rows[0][0]
    label = telegram_config.PREFERENCE_DISPLAY_NAMES[key]
    assert button.text == (f"✅ {label} · ON" if enabled else f"⬜ {label} · OFF")
    assert button.callback_data == f"{key}_PREFERENCES"
