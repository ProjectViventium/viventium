import asyncio
import os
import stat
import time

import pytest

from TelegramVivBot.utils import orchestration


def _preference_payload(*, enabled=False, available=True, has_known_work=False):
    return {
        "available": available,
        "mode": "parallel" if available and enabled else "focused",
        "hasKnownWork": has_known_work,
    }


def _active_work_payload(*, state="fresh", items=None, overflow_count=0, cursor=""):
    return {
        "snapshot": state,
        "work": None if state == "unavailable" else (items or []),
        "overflowCount": None if state == "unavailable" else overflow_count,
        **({"cursor": cursor} if cursor else {}),
    }


def _work_payload(*, actions=None):
    return {
        "workRef": "ghw_private-ref:1",
        "title": "Research durable workers",
        "state": "running",
        "statusSummary": "Comparing native harness capabilities.",
        "updatedAt": "2026-08-12T14:59:00Z",
        "actions": actions or ["message", "steer", "pause", "stop"],
    }


def test_orchestration_client_get_uses_canonical_routes_and_validates_action_mask(monkeypatch):
    captured = []

    class _Response:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class _Client:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, **kwargs):
            captured.append((method, url, kwargs))
            if url.endswith("/orchestration/work"):
                return _Response(
                    _active_work_payload(
                        items=[_work_payload(actions=["pause", "delete", "pause", "steer"])]
                    )
                )
            return _Response(_preference_payload())

    monkeypatch.setattr(orchestration.httpx, "AsyncClient", _Client)
    client = orchestration.OrchestrationClient("http://127.0.0.1:3180/", "service-secret")

    snapshot = asyncio.run(client.get_snapshot("user-123"))

    assert {(method, url) for method, url, _kwargs in captured} == {
        ("GET", "http://127.0.0.1:3180/api/viventium/telegram/orchestration"),
        ("GET", "http://127.0.0.1:3180/api/viventium/telegram/orchestration/work"),
    }
    assert all(
        kwargs == {
            "headers": {"X-VIVENTIUM-TELEGRAM-SECRET": "service-secret"},
            "params": {"telegramUserId": "user-123"},
        }
        for _method, _url, kwargs in captured
    )
    assert snapshot.active_state == "fresh"
    assert snapshot.items[0].work_ref == "ghw_private-ref:1"
    assert snapshot.items[0].actions == ("pause", "steer")


def test_orchestration_client_patch_sets_account_preference_and_returns_snapshot(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return _preference_payload(enabled=True)

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, kwargs=kwargs)
            return _Response()

    monkeypatch.setattr(orchestration.httpx, "AsyncClient", _Client)
    client = orchestration.OrchestrationClient("http://127.0.0.1:3180", "service-secret")

    snapshot = asyncio.run(client.set_parallel_work("user-123", True))

    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/api/viventium/telegram/orchestration")
    assert captured["kwargs"]["json"] == {
        "telegramUserId": "user-123",
        "mode": "parallel",
    }
    assert snapshot.parallel_work_enabled is True


def test_orchestration_client_pages_with_an_opaque_cursor_and_keeps_rollback_roster(monkeypatch):
    captured = []

    class _Response:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, **kwargs):
            captured.append((url, kwargs.get("params")))
            if url.endswith("/orchestration/work"):
                return _Response(_active_work_payload(items=[_work_payload()]))
            return _Response(_preference_payload(available=False, has_known_work=True))

    monkeypatch.setattr(orchestration.httpx, "AsyncClient", _Client)
    client = orchestration.OrchestrationClient("http://127.0.0.1:3180", "service-secret")

    snapshot = asyncio.run(client.get_snapshot("user-123", cursor="signed.next-page"))

    assert snapshot.parallel_work_available is False
    assert snapshot.has_known_work is True
    assert snapshot.items[0].work_ref == "ghw_private-ref:1"
    assert captured == [
        (
            "http://127.0.0.1:3180/api/viventium/telegram/orchestration",
            {"telegramUserId": "user-123"},
        ),
        (
            "http://127.0.0.1:3180/api/viventium/telegram/orchestration/work",
            {"telegramUserId": "user-123", "cursor": "signed.next-page"},
        ),
    ]


def test_orchestration_client_action_requires_instruction_and_encodes_work_ref(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200
        text = ""

        def __init__(self, payload, status_code=200):
            self.payload = payload
            self.status_code = status_code

        def json(self):
            return self.payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, **kwargs):
            if method == "POST":
                captured.update(method=method, url=url, kwargs=kwargs)
                return _Response(
                    {"workRef": "ghw_private-ref:1", "action": "steer", "state": "running"},
                    status_code=202,
                )
            if url.endswith("/orchestration/work"):
                return _Response(
                    _active_work_payload(items=[_work_payload(actions=["steer"])])
                )
            return _Response(_preference_payload(enabled=True))

    monkeypatch.setattr(orchestration.httpx, "AsyncClient", _Client)
    client = orchestration.OrchestrationClient("http://127.0.0.1:3180", "service-secret")

    with pytest.raises(ValueError, match="instruction"):
        asyncio.run(
            client.act(
                "user-123",
                "ghw_private-ref:1",
                "steer",
                instruction="   ",
                operation_id="018f47d3-8965-7f6a-a826-7c06afedc001",
            )
        )

    snapshot = asyncio.run(
        client.act(
            "user-123",
            "ghw_private-ref:1",
            "steer",
            instruction="Focus on the restart race.",
            operation_id="018f47d3-8965-7f6a-a826-7c06afedc001",
        )
    )

    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/api/viventium/telegram/orchestration/work/ghw_private-ref%3A1/actions"
    )
    assert captured["kwargs"]["json"] == {
        "telegramUserId": "user-123",
        "action": "steer",
        "instruction": "Focus on the restart race.",
        "operationId": "018f47d3-8965-7f6a-a826-7c06afedc001",
    }
    assert snapshot.action_receipt.accepted is True


def test_orchestration_client_preserves_link_required_and_unavailable_truth(monkeypatch):
    responses = []

    class _Response:
        text = ""

        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, *args, **kwargs):
            return responses.pop(0)

    monkeypatch.setattr(orchestration.httpx, "AsyncClient", _Client)
    client = orchestration.OrchestrationClient("http://127.0.0.1:3180", "service-secret")
    responses.append(
        _Response(
            401,
            {
                "error": "Link the Telegram account to continue.",
                "code": "TELEGRAM_ACCOUNT_NOT_LINKED",
                "linkRequired": True,
                "linkUrl": "https://example.com/telegram/link/synthetic",
            },
        )
    )

    with pytest.raises(orchestration.OrchestrationLinkRequired) as raised:
        asyncio.run(client.get_snapshot("user-123"))
    assert raised.value.link_url == "https://example.com/telegram/link/synthetic"

    responses.append(_Response(401, {"error": "Telegram account not linked"}))
    with pytest.raises(orchestration.OrchestrationError) as prose_only:
        asyncio.run(client.get_snapshot("user-123"))
    assert not isinstance(prose_only.value, orchestration.OrchestrationLinkRequired)

    responses.extend(
        [
            _Response(200, _preference_payload()),
            _Response(200, {"snapshot": "unavailable", "work": None, "overflowCount": None}),
        ]
    )
    unavailable = asyncio.run(client.get_snapshot("user-123"))
    assert unavailable.active_state == "unavailable"
    assert unavailable.items == ()
    assert "unavailable" in unavailable.notice.lower()


def test_callback_capability_is_opaque_scoped_durable_one_use_and_ttl(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    store = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    issued = store.issue_actions(
        telegram_user_id="user-123",
        chat_id="chat-456",
        targets=[("ghw_secret-ref", "pause")],
        now=100.0,
    )

    callback_data = orchestration.action_callback_data(issued[0].token)
    assert len(callback_data.encode("utf-8")) <= 64
    assert "ghw_secret-ref" not in callback_data

    restarted = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    assert restarted.consume_action(
        issued[0].token,
        telegram_user_id="other-user",
        chat_id="chat-456",
        now=101.0,
    ) is None
    target = restarted.consume_action(
        issued[0].token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=101.0,
    )
    assert target.work_ref == "ghw_secret-ref"
    assert target.action == "pause"
    assert restarted.consume_action(
        issued[0].token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=102.0,
    ) is None

    expired = store.issue_actions(
        telegram_user_id="user-123",
        chat_id="chat-456",
        targets=[("work-2", "resume")],
        now=200.0,
    )[0]
    assert store.consume_action(
        expired.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=231.0,
    ) is None


def test_callback_capability_store_hardens_existing_database_and_sidecars_to_owner_only(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    path.touch(mode=0o644)
    os.chmod(path, 0o644)

    store = orchestration.CallbackCapabilityStore(path, ttl_s=30)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = path.with_name(f"{path.name}{suffix}")
        sidecar.touch(mode=0o644)
        os.chmod(sidecar, 0o644)
    store._secure_storage_files()
    assert all(
        stat.S_IMODE(path.with_name(f"{path.name}{suffix}").stat().st_mode) == 0o600
        for suffix in ("-wal", "-shm", "-journal")
    )


def test_action_reservation_replays_same_operation_after_lost_response_and_restart(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    store = orchestration.CallbackCapabilityStore(path, ttl_s=60, action_lease_s=5)
    issued = store.issue_actions(
        telegram_user_id="user-123",
        chat_id="chat-456",
        targets=[("work-private", "steer")],
        now=100.0,
    )[0]

    first = store.reserve_action(
        issued.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=101.0,
    )
    assert first.target == issued
    assert first.operation_id == issued.token
    assert first.replay is False

    # A concurrent duplicate cannot execute while the first delivery is unresolved.
    assert store.reserve_action(
        issued.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=102.0,
    ) is None

    # A crash/restart followed by lease expiry reuses the exact operation id so Core/GlassHive
    # can replay the authoritative idempotent receipt instead of creating a second action.
    restarted = orchestration.CallbackCapabilityStore(path, ttl_s=60, action_lease_s=5)
    replay = restarted.reserve_action(
        issued.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=107.0,
    )
    assert replay.target == issued
    assert replay.operation_id == first.operation_id
    assert replay.replay is True

    restarted.complete_action(replay, succeeded=True, receipt="accepted", now=108.0)
    assert restarted.reserve_action(
        issued.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=109.0,
    ) is None


def test_action_reservation_consumes_definitive_failure_and_requires_refresh(tmp_path):
    store = orchestration.CallbackCapabilityStore(
        tmp_path / "callbacks.sqlite3", ttl_s=60, action_lease_s=5
    )
    issued = store.issue_actions(
        telegram_user_id="user-123",
        chat_id="chat-456",
        targets=[("work-private", "pause")],
        now=100.0,
    )[0]
    reservation = store.reserve_action(
        issued.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=101.0,
    )

    store.complete_action(reservation, succeeded=False, definitive=True, now=102.0)
    retry = store.reserve_action(
        issued.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=103.0,
    )
    assert retry is None


def test_prompt_action_replays_same_instruction_and_operation_after_restart(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    store = orchestration.CallbackCapabilityStore(path, ttl_s=60, action_lease_s=5)
    prompt = store.reserve_prompt(
        telegram_user_id="user-123",
        chat_id="chat-456",
        work_ref="work-private",
        action="steer",
        now=100.0,
    )

    first, instruction = store.reserve_prompt_action(
        prompt.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        instruction="Check the restart race first.",
        now=101.0,
    )
    assert instruction == "Check the restart race first."
    store.complete_action(first, succeeded=False, definitive=False, now=102.0)

    restarted = orchestration.CallbackCapabilityStore(path, ttl_s=60, action_lease_s=5)
    replay, replay_instruction = restarted.reserve_prompt_action(
        prompt.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=103.0,
    )
    assert replay.operation_id == first.operation_id == prompt.token
    assert replay.replay is True
    assert replay_instruction == instruction
    assert restarted.reserve_prompt_action(
        prompt.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        instruction="A changed instruction must not replace the durable one.",
        now=109.0,
    ) is None


def test_orchestration_error_tracks_indeterminate_transport_truth():
    assert orchestration.OrchestrationError("retry", indeterminate=True).indeterminate is True
    assert orchestration.OrchestrationError("rejected").indeterminate is False


def test_page_capability_is_opaque_scoped_durable_one_use_and_ttl(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    store = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    token = store.issue_page(
        telegram_user_id="user-123",
        chat_id="chat-456",
        cursor="signed.next-page",
        now=100.0,
    )

    callback_data = orchestration.page_callback_data(token)
    assert len(callback_data.encode("utf-8")) <= 64
    assert "signed.next-page" not in callback_data

    restarted = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    assert restarted.consume_page(
        token,
        telegram_user_id="other-user",
        chat_id="chat-456",
        now=101.0,
    ) is None
    assert restarted.consume_page(
        token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=101.0,
    ) == "signed.next-page"
    assert restarted.consume_page(
        token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=102.0,
    ) is None


def test_page_reservation_survives_lost_response_and_restart(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    store = orchestration.CallbackCapabilityStore(path, ttl_s=30, action_lease_s=5)
    token = store.issue_page(
        telegram_user_id="user-123",
        chat_id="chat-456",
        cursor="signed.next-page",
        now=100.0,
    )

    first = store.reserve_page(
        token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=101.0,
    )
    assert first.cursor == "signed.next-page"
    assert first.replay is False
    assert store.reserve_page(
        token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=102.0,
    ) is None
    store.complete_page(first, succeeded=False, definitive=False, now=103.0)

    restarted = orchestration.CallbackCapabilityStore(path, ttl_s=30, action_lease_s=5)
    replay = restarted.reserve_page(
        token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=104.0,
    )
    assert replay.cursor == first.cursor
    assert replay.replay is True
    restarted.complete_page(replay, succeeded=True, now=105.0)
    assert restarted.reserve_page(
        token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=106.0,
    ) is None


def test_instruction_prompt_mapping_is_durable_scoped_and_one_use(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    store = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    prompt = store.issue_prompt(
        telegram_user_id="user-123",
        chat_id="chat-456",
        prompt_message_id="789",
        work_ref="work-private",
        action="message",
        now=100.0,
    )

    restarted = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    assert restarted.consume_prompt(
        telegram_user_id="user-123",
        chat_id="wrong-chat",
        prompt_message_id="789",
        now=101.0,
    ) is None
    resolved = restarted.consume_prompt(
        telegram_user_id="user-123",
        chat_id="chat-456",
        prompt_message_id="789",
        now=101.0,
    )
    assert resolved.token == prompt.token
    assert resolved.work_ref == "work-private"
    assert resolved.action == "message"
    assert restarted.consume_prompt(
        telegram_user_id="user-123",
        chat_id="chat-456",
        prompt_message_id="789",
        now=102.0,
    ) is None


def test_reserved_instruction_survives_crash_between_prompt_send_and_message_binding(tmp_path):
    path = tmp_path / "callbacks.sqlite3"
    store = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    reserved = store.reserve_prompt(
        telegram_user_id="user-123",
        chat_id="chat-456",
        work_ref="work-private",
        action="steer",
        now=100.0,
    )

    restarted = orchestration.CallbackCapabilityStore(path, ttl_s=30)
    resolved = restarted.consume_prompt_token(
        reserved.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=101.0,
    )

    assert resolved == reserved
    assert restarted.consume_prompt_token(
        reserved.token,
        telegram_user_id="user-123",
        chat_id="chat-456",
        now=102.0,
    ) is None


@pytest.mark.parametrize("action", ["queue", "message", "steer", "pause", "resume", "stop", "retry", "dismiss"])
def test_callback_store_accepts_only_product_action_vocabulary(tmp_path, action):
    store = orchestration.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    issued = store.issue_actions(
        telegram_user_id="user-123",
        chat_id="chat-456",
        targets=[("work-private", action)],
    )
    assert issued[0].action == action

    with pytest.raises(ValueError, match="Unsupported work action"):
        store.issue_actions(
            telegram_user_id="user-123",
            chat_id="chat-456",
            targets=[("work-private", "delete")],
        )


def test_active_work_text_keeps_focused_mode_work_visible_and_reports_overflow():
    snapshot = orchestration.parse_snapshot(
        _preference_payload(enabled=False),
        _active_work_payload(
            items=[_work_payload(actions=["message", "pause"])],
            overflow_count=3,
            cursor="signed.next-page",
        ),
    )

    text = orchestration.format_active_work(snapshot)

    assert "Parallel work: Off" in text
    assert "New automatic delegation is focused" in text
    assert "Research durable workers" in text
    assert "Comparing native harness capabilities." in text
    assert "3 more active items are not shown" in text
    assert "ghw_private-ref" not in text


def test_active_work_text_reports_overflow_even_when_paging_cursor_is_unavailable():
    snapshot = orchestration.parse_snapshot(
        _preference_payload(),
        _active_work_payload(
            items=[_work_payload()],
            overflow_count=3,
            cursor="",
        ),
    )

    assert snapshot.has_more is True
    assert snapshot.next_cursor == ""
    assert "3 more active items are not shown" in orchestration.format_active_work(snapshot)


@pytest.mark.parametrize(
    ("state", "items", "expected", "forbidden"),
    [
        ("fresh", [], "No active work.", "unavailable"),
        ("stale", [_work_payload()], "last known active work", "No active work"),
        ("unavailable", [], "Existing work may still be running", "No active work"),
    ],
)
def test_active_work_text_distinguishes_empty_stale_and_unavailable(
    state,
    items,
    expected,
    forbidden,
):
    snapshot = orchestration.parse_snapshot(
        _preference_payload(),
        _active_work_payload(state=state, items=items),
    )

    text = orchestration.format_active_work(snapshot)

    assert expected.lower() in text.lower()
    assert forbidden.lower() not in text.lower()


def test_settings_text_reports_account_wide_unavailable_and_enabled_states():
    enabled = orchestration.parse_snapshot(_preference_payload(enabled=True))
    unavailable = orchestration.parse_snapshot(_preference_payload(available=False))

    assert "Account-wide" in orchestration.format_parallel_work_settings(enabled)
    assert "On" in orchestration.format_parallel_work_settings(enabled)
    assert "unavailable" in orchestration.format_parallel_work_settings(unavailable).lower()


def test_unavailable_launch_switch_keeps_known_work_visible_and_pageable():
    snapshot = orchestration.parse_snapshot(
        _preference_payload(available=False, has_known_work=True),
        _active_work_payload(
            items=[_work_payload()],
            overflow_count=2,
            cursor="signed.next-page",
        ),
    )

    assert snapshot.parallel_work_available is False
    assert snapshot.has_known_work is True
    assert snapshot.items[0].title == "Research durable workers"
    assert snapshot.has_more is True
    assert snapshot.next_cursor == "signed.next-page"


def test_safe_link_url_rejects_non_web_authority():
    assert orchestration.safe_link_url("javascript:alert(1)") == ""
    assert orchestration.safe_link_url("file:///tmp/private") == ""
    assert (
        orchestration.safe_link_url("https://example.com/telegram/link/synthetic")
        == "https://example.com/telegram/link/synthetic"
    )
