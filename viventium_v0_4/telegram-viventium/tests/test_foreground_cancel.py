import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TelegramVivBot.utils import librechat_bridge as module


def make_bridge():
    bridge = module.LibreChatBridge(get_conversation_id=lambda _chat: "conversation-1", set_conversation_id=lambda *_args: None)
    bridge.base_url = "http://example.com"
    bridge.secret = "synthetic-secret"
    bridge._set_stream_identity(stream_id="stream-1", telegram_chat_id="111", telegram_user_id="9",
                                telegram_username="", telegram_message_id="222", telegram_message_thread_id="77")
    bridge._conversation_by_stream["stream-1"] = "conversation-1"
    bridge._response_message_ids["stream-1"] = "failed-response"
    return bridge


def proof(response_id="failed-response", **overrides):
    value = {"version": 1, "action": "cancel", "responseMessageId": response_id, "receipt": "a" * 64,
             "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
    return {**value, **overrides}


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original(**{**kwargs, "transport": transport}))


async def failure(bridge, payload=None, **kwargs):
    return await bridge._foreground_failure_event(
        "The model needs attention because progress stopped.", error_class="provider_progress_stalled",
        payload=payload or {}, chat_id="111:77:9", stream_id="stream-1", **kwargs)


async def cancel(bridge, **overrides):
    return await bridge.cancel_foreground("111:77:9", **{
        "telegram_user_id": "9", "telegram_chat_id": "111", "telegram_message_thread_id": "77",
        "operation_id": "tg-cancel-operation-1", **overrides})


@pytest.mark.asyncio
async def test_cancel_revalidates_exact_response_and_uses_fresh_receipt(monkeypatch):
    bridge = make_bridge()
    requests = []
    def respond(request):
        requests.append(request)
        assert request.headers["X-VIVENTIUM-TELEGRAM-SECRET"] == "synthetic-secret"
        assert dict(request.url.params) == {"telegramChatId": "111", "telegramUserId": "9",
                                           "telegramMessageThreadId": "77", "conversationId": "conversation-1"}
        if request.method == "GET":
            return httpx.Response(200, json=proof(receipt=("a" if len(requests) == 1 else "b") * 64))
        assert json.loads(request.content) == {"receipt": "b" * 64, "operationId": "tg-cancel-operation-1"}
        return httpx.Response(200, json={"version": 1, "state": "cancelled", "capacityReleased": True})
    mock_http(monkeypatch, respond)
    event = await failure(bridge)
    assert event["foreground_cancel_available"] is True
    assert event["text"].endswith(module.TELEGRAM_FOREGROUND_CANCEL_HINT)
    result = await cancel(bridge)
    assert "capacity was released" in result
    assert [request.method for request in requests] == ["GET", "GET", "POST"]
    assert all("/foreground/failed-response/" in request.url.path for request in requests)
    assert bridge._foreground_attention_by_chat == {}
    assert await cancel(bridge) == module.TELEGRAM_FOREGROUND_CANCEL_UNAVAILABLE
    assert len(requests) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", [{"telegram_user_id": "10"}, {"telegram_chat_id": "112"}, {"telegram_message_thread_id": "78"}])
async def test_foreign_owner_chat_or_thread_cannot_use_cached_proof(monkeypatch, identity):
    bridge = make_bridge()
    requests = []
    mock_http(monkeypatch, lambda request: requests.append(request) or httpx.Response(200, json=proof()))
    await failure(bridge)
    assert await cancel(bridge, **identity) == module.TELEGRAM_FOREGROUND_CANCEL_UNAVAILABLE
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    httpx.Response(409, json={"error": "not_eligible"}),
    httpx.Response(200, json=proof(response_id="foreign-response")),
    httpx.Response(200, json=proof(receipt="")),
    httpx.Response(200, json=proof(receipt={"token": "a" * 64})),
    httpx.Response(200, json=proof(version=True)),
    httpx.Response(200, json=proof(expiresAt="invalid")),
    httpx.Response(200, json=proof(expiresAt="2000-01-01T00:00:00+00:00")),
])
async def test_missing_invalid_or_expired_proof_never_offers_cancel(monkeypatch, response):
    bridge = make_bridge()
    mock_http(monkeypatch, lambda _request: response)
    event = await failure(bridge)
    assert "foreground_cancel_available" not in event
    assert "/cancel" not in event["text"]
    assert await cancel(bridge) == module.TELEGRAM_FOREGROUND_CANCEL_UNAVAILABLE


@pytest.mark.asyncio
async def test_stale_receipt_revalidation_never_posts(monkeypatch):
    bridge = make_bridge()
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=proof()) if len(requests) == 1 else httpx.Response(409, json={"error": "stale"})
    mock_http(monkeypatch, respond)
    await failure(bridge)
    assert await cancel(bridge) == module.TELEGRAM_FOREGROUND_CANCEL_UNAVAILABLE
    assert [request.method for request in requests] == ["GET", "GET"]
    assert bridge._foreground_attention_by_chat


@pytest.mark.asyncio
@pytest.mark.parametrize("state, released, retained", [
    ("cancelled", False, True), ("already_cancelled", False, True), ("pending", False, True),
    ("already_cancelled", True, False), ("already_completed", False, False),
])
async def test_cancel_reports_capacity_truth_and_retains_unconfirmed_action(monkeypatch, state, released, retained):
    bridge = make_bridge()
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=proof() if request.method == "GET" else {
        "version": 1, "state": state, "capacityReleased": released, "message": "must not override release proof"}))
    await failure(bridge)
    result = await cancel(bridge)
    assert bool(bridge._foreground_attention_by_chat) is retained
    if retained:
        assert "not confirmed" in result
        assert "was cancelled" not in result
    elif state == "already_completed":
        assert "already completed" in result
    else:
        assert "capacity was released" in result


@pytest.mark.asyncio
async def test_cancel_receipt_conflict_preserves_exact_action(monkeypatch):
    bridge = make_bridge()
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=proof()) if request.method == "GET" else httpx.Response(409))
    await failure(bridge)
    assert "could not be cancelled" in await cancel(bridge)
    assert bridge._foreground_attention_by_chat["111:77:9"]["response_message_id"] == "failed-response"


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [
    {"version": True, "state": "cancelled", "capacityReleased": True},
    {"version": 1, "state": "unknown", "capacityReleased": True},
    {"version": 1, "state": "cancelled", "capacityReleased": "true"},
])
async def test_malformed_cancel_result_cannot_claim_success(monkeypatch, result):
    bridge = make_bridge()
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=proof() if request.method == "GET" else result))
    await failure(bridge)
    assert await cancel(bridge) == "Cancellation could not be confirmed. Please try /cancel again."
    assert bridge._foreground_attention_by_chat


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["top", "metadata"])
async def test_structured_original_response_pointer_repopulates_after_restart(monkeypatch, location):
    bridge = make_bridge()
    bridge._response_message_ids.clear()
    requests = []
    pointer = {"version": 1, "responseMessageId": "original-response"}
    payload = {"foregroundAttention": pointer} if location == "top" else {
        "responseMessage": {"metadata": {"viventium": {"foregroundAttention": pointer}}}}
    mock_http(monkeypatch, lambda request: requests.append(request) or httpx.Response(200, json=proof("original-response")))
    event = await failure(bridge, payload)
    assert event["foreground_cancel_available"] is True
    assert "original-response" not in event["text"]
    assert requests[0].url.path.endswith("/original-response/attention")


@pytest.mark.asyncio
async def test_new_preflight_without_admission_uses_structured_original_response(monkeypatch):
    bridge = make_bridge()
    bridge._response_message_ids.clear()
    request = httpx.Request("POST", "http://example.com/api/viventium/telegram/chat")
    response = httpx.Response(409, request=request, json={"code": "provider_progress_stalled",
        "foregroundAttention": {"version": 1, "responseMessageId": "original-response"}})
    async def fail_start(**_kwargs):
        raise httpx.HTTPStatusError("synthetic diagnostic", request=request, response=response)
    monkeypatch.setattr(bridge, "_start_chat_with_connect_retry", fail_start)
    mock_http(monkeypatch, lambda _request: httpx.Response(200, json=proof("original-response")))
    events = [event async for event in bridge.ask_stream_async("new message", "111:77:9",
        telegram_chat_id="111", telegram_user_id="9", telegram_message_id="223", telegram_message_thread_id="77",
        source_order_scope="a" * 64, source_event_id="b" * 64)]
    assert len(events) == 1
    assert events[0]["foreground_cancel_available"] is True
    assert bridge._foreground_attention_by_chat["111:77:9"]["source_sequence"] == "223"


@pytest.mark.asyncio
@pytest.mark.parametrize("sse_error", [True, False])
async def test_real_stream_failure_adds_verified_cancel_hint(monkeypatch, sse_error):
    bridge = make_bridge()
    payload = {"error": "synthetic private diagnostic", "error_class": "provider_progress_stalled",
               "foregroundAttention": {"version": 1, "responseMessageId": "original-response"}}
    if sse_error:
        payload["_sse_event"] = "error"
    else:
        payload.update(final=True, responseMessage={"messageId": "failed-response", "error": "synthetic private diagnostic"})
    def respond(request):
        if "/stream/" in request.url.path:
            return httpx.Response(200, text="data: " + json.dumps(payload) + "\n\n", headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=proof("original-response"))
    mock_http(monkeypatch, respond)
    events = [event async for event in bridge._stream_response("stream-1", "111:77:9")]
    errors = [event for event in events if isinstance(event, dict) and event.get("type") == "bridge_error"]
    assert len(errors) == 1
    assert errors[0]["foreground_cancel_available"] is True
    assert "private" not in errors[0]["text"]


@pytest.mark.asyncio
async def test_cache_expires_and_only_newer_success_clears_action(monkeypatch):
    bridge = make_bridge()
    mock_http(monkeypatch, lambda _request: httpx.Response(200, json=proof()))
    await failure(bridge)
    cached = bridge._foreground_attention_by_chat["111:77:9"]
    assert cached["expires_at"] <= module.time.time() + 900
    await bridge._foreground_failure_event("other error", error_class="provider_auth_missing", payload={}, chat_id="111:77:9")
    assert bridge._foreground_attention_by_chat["111:77:9"] is cached
    bridge._stream_identity["stream-1"]["telegram_message_id"] = "221"
    bridge._clear_foreground_attention_on_success("111:77:9", "stream-1")
    assert bridge._foreground_attention_by_chat
    bridge._stream_identity["stream-1"]["telegram_message_id"] = "223"
    bridge._clear_foreground_attention_on_success("111:77:9", "stream-1")
    assert not bridge._foreground_attention_by_chat
    await failure(bridge)
    bridge._foreground_attention_by_chat["111:77:9"]["expires_at"] = 0
    assert await cancel(bridge) == module.TELEGRAM_FOREGROUND_CANCEL_UNAVAILABLE


def test_foreground_cache_is_bounded():
    bridge = make_bridge()
    bridge._foreground_attention_by_chat = {str(index): {"expires_at": module.time.time() + 900} for index in range(300)}
    bridge._prune_foreground_attention()
    assert len(bridge._foreground_attention_by_chat) == 256
    assert "0" not in bridge._foreground_attention_by_chat


@pytest.mark.asyncio
@pytest.mark.parametrize("final_text, retained", [("", True), ("A completed reply.", False)])
async def test_only_successful_new_final_clears_foreground_action(monkeypatch, final_text, retained):
    bridge = make_bridge()
    payload = {"final": True, "responseMessage": {"messageId": "new-response",
               "content": [{"type": "text", "text": final_text}]}}
    def respond(request):
        if "/stream/" in request.url.path:
            return httpx.Response(200, text="data: " + json.dumps(payload) + "\n\n")
        return httpx.Response(200, json=proof())
    mock_http(monkeypatch, respond)
    await failure(bridge)
    bridge._stream_identity["stream-1"]["telegram_message_id"] = "223"
    _events = [event async for event in bridge._stream_response("stream-1", "111:77:9")]
    assert bool(bridge._foreground_attention_by_chat) is retained


@pytest.mark.asyncio
async def test_cancel_after_restart_without_new_verified_failure_is_unavailable(monkeypatch):
    bridge = make_bridge()
    def no_request(_request):
        raise AssertionError("A restart must not infer the latest work to cancel")
    mock_http(monkeypatch, no_request)
    assert await cancel(bridge) == module.TELEGRAM_FOREGROUND_CANCEL_UNAVAILABLE
