import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import TelegramVivBot.utils.librechat_bridge as bridge_module
from TelegramVivBot.utils.librechat_bridge import LibreChatBridge


class _Response:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _CoreContract:
    def __init__(
        self,
        *,
        authorizations: list[tuple[int, dict[str, Any]]],
        renewals: list[tuple[int, dict[str, Any]]] | None = None,
        status_code: int = 200,
    ):
        self.authorizations = list(authorizations)
        self.renewals = list(renewals or [])
        self.status_code = status_code
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def install(self, monkeypatch) -> None:
        contract = self

        class _Client:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, _exc_type, _exc, _traceback):
                return False

            async def post(self, url, *, json, headers):
                assert headers == {"X-VIVENTIUM-TELEGRAM-SECRET": "test-secret"}
                if url.endswith("/authorize"):
                    kind = "authorize"
                    response = contract.authorizations.pop(0)
                elif url.endswith("/renew"):
                    kind = "renew"
                    response = contract.renewals.pop(0)
                elif url.endswith("/release"):
                    kind = "release"
                    response = (200, {"released": True})
                elif url.endswith("/status"):
                    kind = "status"
                    response = (
                        contract.status_code,
                        {"delivery": {"status": json["status"]}},
                    )
                else:
                    raise AssertionError(f"unexpected Core URL: {url}")
                contract.calls.append((kind, dict(json)))
                return _Response(*response)

        monkeypatch.setattr(bridge_module.httpx, "AsyncClient", _Client)


def _bridge() -> LibreChatBridge:
    bridge = LibreChatBridge(
        get_conversation_id=lambda _chat_id: "new",
        set_conversation_id=lambda _chat_id, _conversation_id: None,
    )
    bridge.secret = "test-secret"
    bridge.base_url = "http://core.example.invalid"
    bridge.glasshive_delivery_lease_ms = 30_000
    return bridge


def _delivery() -> dict[str, Any]:
    return {
        "deliveryId": "ghcd-generation-a",
        "claimId": "claim-generation-a",
        "telegramChatId": "406",
        "text": "Generation A terminal result.",
        "terminalCallbackResultKey": f"ghtr_{'a' * 64}",
        "terminalCallbackAcceptedOperationId": "a" * 32,
        "terminalCallbackEffectGeneration": 1,
        "terminalCallbackId": f"cb_terminal_{'a' * 64}",
        "terminalCallbackResultRevision": 1,
        "terminalCallbackResultDigest": f"sha256:{'a' * 64}",
    }


def _permit(generation: int = 1) -> dict[str, Any]:
    return {
        "deliveryId": "ghcd-generation-a",
        "claimId": "claim-generation-a",
        "surface": "telegram",
        "permitId": f"permit-{generation}",
        "permitGeneration": generation,
        "expiresAt": "2099-08-23T22:00:30.000Z",
        "resultRevision": 1,
        "resultDigest": f"sha256:{'a' * 64}",
    }


@pytest.mark.asyncio
async def test_authorization_denial_fences_stale_delivery_before_telegram_send(
    monkeypatch,
):
    core = _CoreContract(
        authorizations=[(409, {"error": "terminal_callback_superseded"})]
    )
    core.install(monkeypatch)
    bridge = _bridge()
    telegram_messages: list[tuple[int, str]] = []

    async def telegram_api_send(chat_id, text, **_kwargs):
        telegram_messages.append((chat_id, text))
        return {"message_ids": ["stale-message"]}

    bridge.set_on_message_callback(telegram_api_send)

    assert await bridge._deliver_glasshive_delivery(_delivery()) is False
    assert telegram_messages == []
    assert core.calls == [
        (
            "authorize",
            {
                "claimId": "claim-generation-a",
                "leaseMs": 30_000,
            },
        )
    ]


@pytest.mark.asyncio
async def test_expired_authorization_is_rejected_before_telegram_send(monkeypatch):
    expired_permit = {**_permit(), "expiresAt": "2020-01-01T00:00:00.000Z"}
    core = _CoreContract(authorizations=[(200, {"permit": expired_permit})])
    core.install(monkeypatch)
    bridge = _bridge()
    telegram_messages: list[tuple[int, str]] = []

    async def telegram_api_send(chat_id, text, **_kwargs):
        telegram_messages.append((chat_id, text))
        return {"message_ids": ["stale-message"]}

    bridge.set_on_message_callback(telegram_api_send)

    assert await bridge._deliver_glasshive_delivery(_delivery()) is False
    assert telegram_messages == []
    assert [kind for kind, _payload in core.calls] == ["authorize"]


@pytest.mark.asyncio
async def test_sent_status_propagates_exact_dispatch_permit(monkeypatch):
    permit = _permit()
    renewed_permit = {**permit, "expiresAt": "2099-08-23T22:01:30.000Z"}
    core = _CoreContract(
        authorizations=[(200, {"permit": permit})],
        renewals=[(200, {"permit": renewed_permit})],
    )
    core.install(monkeypatch)
    bridge = _bridge()

    async def telegram_api_send(_chat_id, _text, **_kwargs):
        await _kwargs["before_side_effect"]()
        return {"message_ids": ["telegram-message-1"]}

    bridge.set_on_message_callback(telegram_api_send)

    assert await bridge._deliver_glasshive_delivery(_delivery()) is True
    assert core.calls == [
        (
            "authorize",
            {
                "claimId": "claim-generation-a",
                "leaseMs": 30_000,
            },
        ),
        (
            "renew",
            {
                "claimId": "claim-generation-a",
                "dispatchPermit": permit,
                "leaseMs": 30_000,
            },
        ),
        (
            "status",
            {
                "claimId": "claim-generation-a",
                "status": "sent",
                "telegramMessageIds": ["telegram-message-1"],
                "dispatchPermit": renewed_permit,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_transport_exception_records_unknown_without_release_or_retry(
    monkeypatch,
):
    permit = _permit()
    renewed_permit = {**permit, "expiresAt": "2099-08-23T22:01:30.000Z"}
    core = _CoreContract(
        authorizations=[(200, {"permit": permit})],
        renewals=[(200, {"permit": renewed_permit})],
    )
    core.install(monkeypatch)
    bridge = _bridge()

    async def telegram_api_send(_chat_id, _text, **_kwargs):
        await _kwargs["before_side_effect"]()
        raise RuntimeError("synthetic Telegram send failure")

    bridge.set_on_message_callback(telegram_api_send)

    assert await bridge._deliver_glasshive_delivery(_delivery()) is False
    assert core.calls == [
        (
            "authorize",
            {
                "claimId": "claim-generation-a",
                "leaseMs": 30_000,
            },
        ),
        (
            "renew",
            {
                "claimId": "claim-generation-a",
                "dispatchPermit": permit,
                "leaseMs": 30_000,
            },
        ),
        (
            "status",
            {
                "claimId": "claim-generation-a",
                "status": "delivery_unknown",
                "reason": "telegram_send_outcome_unknown:synthetic Telegram send failure",
                "dispatchPermit": renewed_permit,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_busy_authorization_replay_acquires_fresh_permit_and_sends_once(
    monkeypatch,
):
    permit = _permit(2)
    core = _CoreContract(
        authorizations=[
            (409, {"error": "delivery_dispatch_busy"}),
            (200, {"permit": permit}),
        ],
        renewals=[
            (
                200,
                {
                    "permit": {
                        **permit,
                        "expiresAt": "2099-08-23T22:01:30.000Z",
                    }
                },
            )
        ],
    )
    core.install(monkeypatch)
    bridge = _bridge()
    telegram_messages: list[tuple[int, str]] = []

    async def telegram_api_send(chat_id, text, **_kwargs):
        await _kwargs["before_side_effect"]()
        telegram_messages.append((chat_id, text))
        return {"message_ids": ["telegram-message-2"]}

    bridge.set_on_message_callback(telegram_api_send)
    delivery = _delivery()

    assert await bridge._deliver_glasshive_delivery(delivery) is False
    assert await bridge._deliver_glasshive_delivery(delivery) is True
    assert telegram_messages == [(406, "Generation A terminal result.")]
    assert [kind for kind, _payload in core.calls] == [
        "authorize",
        "authorize",
        "renew",
        "status",
    ]
    assert core.calls[-1][1]["dispatchPermit"]["expiresAt"] == (
        "2099-08-23T22:01:30.000Z"
    )


@pytest.mark.asyncio
async def test_multisegment_delivery_renews_permit_before_second_telegram_send(
    monkeypatch,
):
    first_permit = _permit(1)
    renewed_permit = {**first_permit, "expiresAt": "2099-08-23T22:01:30.000Z"}
    final_permit = {**first_permit, "expiresAt": "2099-08-23T22:02:30.000Z"}
    core = _CoreContract(
        authorizations=[(200, {"permit": first_permit})],
        renewals=[
            (200, {"permit": renewed_permit}),
            (200, {"permit": final_permit}),
        ],
    )
    core.install(monkeypatch)
    bridge = _bridge()
    telegram_messages: list[str] = []

    async def telegram_api_send(_chat_id, text, **_kwargs):
        await _kwargs["before_side_effect"]()
        telegram_messages.append(text)
        return {"message_ids": [f"telegram-message-{len(telegram_messages)}"]}

    bridge.set_on_message_callback(telegram_api_send)
    delivery = _delivery()
    delivery["text"] = "First segment.\n{MSG_BREAK}\nSecond segment."

    assert await bridge._deliver_glasshive_delivery(delivery) is True
    assert len(telegram_messages) == 2
    assert [kind for kind, _payload in core.calls] == [
        "authorize",
        "renew",
        "renew",
        "status",
    ]
    assert core.calls[-1][1]["dispatchPermit"] == final_permit


@pytest.mark.asyncio
async def test_stalled_telegram_send_renews_before_short_permit_can_expire(monkeypatch):
    first_permit = _permit(1)
    renewed_permit = {**first_permit, "expiresAt": "2099-08-23T22:01:30.000Z"}
    final_permit = {**first_permit, "expiresAt": "2099-08-23T22:02:30.000Z"}
    core = _CoreContract(
        authorizations=[(200, {"permit": first_permit})],
        renewals=[
            (200, {"permit": renewed_permit}),
            (200, {"permit": final_permit}),
        ],
    )
    core.install(monkeypatch)
    bridge = _bridge()
    bridge.glasshive_delivery_lease_ms = 30

    async def telegram_api_send(_chat_id, _text, **_kwargs):
        await _kwargs["before_side_effect"]()
        await asyncio.sleep(0.015)
        return {"message_ids": ["telegram-message-slow"]}

    bridge.set_on_message_callback(telegram_api_send)

    assert await bridge._deliver_glasshive_delivery(_delivery()) is True
    assert [kind for kind, _payload in core.calls] == [
        "authorize",
        "renew",
        "renew",
        "status",
    ]
    assert core.calls[-1][1]["dispatchPermit"] == final_permit


@pytest.mark.asyncio
async def test_bounded_delivery_timeout_before_authorization_records_failed():
    bridge = _bridge()
    delivery = _delivery()
    statuses: list[tuple[str, str, str]] = []

    async def stalled_delivery(_delivery):
        await asyncio.Event().wait()

    async def record_status(_delivery, status, *, error="", reason=""):
        statuses.append((status, error, reason))
        return True

    bridge._deliver_glasshive_delivery = stalled_delivery  # type: ignore[method-assign]
    bridge._mark_glasshive_delivery_status = record_status  # type: ignore[method-assign]
    bridge._glasshive_delivery_attempt_timeout_s = lambda: 0.01  # type: ignore[method-assign]

    assert await bridge._deliver_glasshive_delivery_bounded(delivery) is False
    assert len(statuses) == 1
    assert statuses[0][0] == "failed"
    assert "timed out before Telegram transport authorization" in statuses[0][1]
    assert statuses[0][2] == ""


@pytest.mark.asyncio
async def test_bounded_delivery_timeout_after_authorization_records_unknown():
    bridge = _bridge()
    delivery = _delivery()
    statuses: list[tuple[str, str, str]] = []

    async def stalled_delivery(current):
        current["dispatchPermit"] = _permit()
        await asyncio.Event().wait()

    async def record_status(_delivery, status, *, error="", reason=""):
        statuses.append((status, error, reason))
        return True

    bridge._deliver_glasshive_delivery = stalled_delivery  # type: ignore[method-assign]
    bridge._mark_glasshive_delivery_status = record_status  # type: ignore[method-assign]
    bridge._glasshive_delivery_attempt_timeout_s = lambda: 0.01  # type: ignore[method-assign]

    assert await bridge._deliver_glasshive_delivery_bounded(delivery) is False
    assert len(statuses) == 1
    assert statuses[0][0] == "delivery_unknown"
    assert statuses[0][1] == ""
    assert "timed out after Telegram transport authorization" in statuses[0][2]
