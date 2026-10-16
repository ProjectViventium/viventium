"""Notification is only a wake hint; existing claims and bounded polling own delivery."""
import asyncio
import json
import logging

import httpx
import pytest
from test_librechat_bridge import _make_bridge
from TelegramVivBot.utils import librechat_bridge as bridge_module


@pytest.mark.asyncio
@pytest.mark.parametrize('supported', [True, False])
async def test_claim_negotiates_wait_without_changing_callback_identity_or_authorization(monkeypatch, supported):
    requests = []
    original_client = httpx.AsyncClient

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'deliveries': [], **({'waitSupported': True} if supported else {})})

    monkeypatch.setattr(bridge_module.httpx, 'AsyncClient', lambda **kwargs:
        original_client(transport=httpx.MockTransport(respond), **kwargs))
    bridge = _make_bridge()
    assert await bridge._claim_glasshive_deliveries(limit=2, callback_id='callback-one', wait_s=9) == []
    payload = json.loads(requests[0].content)
    assert payload['waitMs'] == 5000
    assert payload['callbackId'] == 'callback-one'
    assert payload['dispatcherId'] == bridge._glasshive_delivery_dispatcher_id
    assert requests[0].headers['X-VIVENTIUM-TELEGRAM-SECRET'] == 'test-secret'
    assert bridge._glasshive_delivery_wait_supported is supported


@pytest.mark.asyncio
async def test_claim_records_content_free_wait_inclusive_time_for_actual_claims(monkeypatch, caplog):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(bridge_module.httpx, 'AsyncClient', lambda **kwargs:
        original_client(transport=httpx.MockTransport(lambda _request:
            httpx.Response(200, json={'deliveries': [{'deliveryId': 'private-id', 'claimId': 'private-claim'}],
                                      'waitSupported': True})), **kwargs))
    caplog.set_level(logging.INFO)
    bridge = _make_bridge()
    assert len(await bridge._claim_glasshive_deliveries(wait_s=5)) == 1
    records = [record.message for record in caplog.records if 'delivery claimed count=' in record.message]
    assert len(records) == 1
    assert 'claim_ms=' in records[0] and 'wait_requested_ms=5000' in records[0]
    assert 'private-id' not in records[0] and 'private-claim' not in records[0]


@pytest.mark.asyncio
async def test_dispatcher_does_not_sleep_again_after_supported_wait_and_claims_before_delivery(monkeypatch):
    bridge = _make_bridge()
    bridge._glasshive_delivery_wait_supported = True
    calls = []
    delivered = []

    async def claim(*, limit, wait_s):
        calls.append((limit, wait_s))
        if len(calls) == 1:
            return []
        if len(calls) == 2:
            return [{'deliveryId': 'one', 'claimId': 'durable-claim'}]
        raise asyncio.CancelledError

    async def deliver(row):
        delivered.append(row)
        return True

    async def forbidden_sleep(_delay):
        raise AssertionError('a second fixed sleep adds poll latency')

    bridge._claim_glasshive_deliveries = claim
    bridge._deliver_glasshive_delivery_bounded = deliver
    monkeypatch.setattr(asyncio, 'sleep', forbidden_sleep)
    await bridge._run_glasshive_delivery_dispatcher()
    assert len(calls) == 3
    assert delivered == [{'deliveryId': 'one', 'claimId': 'durable-claim'}]


@pytest.mark.asyncio
async def test_older_backend_keeps_existing_empty_poll_sleep(monkeypatch):
    bridge = _make_bridge()
    bridge._glasshive_delivery_wait_supported = False
    sleeps = []

    async def claim(*, limit, wait_s):
        return []

    async def sleep(delay):
        sleeps.append(delay)
        raise asyncio.CancelledError

    bridge._claim_glasshive_deliveries = claim
    monkeypatch.setattr(asyncio, 'sleep', sleep)
    await bridge._run_glasshive_delivery_dispatcher()
    assert sleeps == [bridge.glasshive_delivery_poll_s]
