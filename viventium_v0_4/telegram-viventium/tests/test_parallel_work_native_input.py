import asyncio

import pytest

from TelegramVivBot.utils import orchestration


def permission_payload():
    return {
        'version': 1, 'kind': 'permission', 'runtimeName': 'Grok', 'mode': 'form',
        'requestId': 'request-1', 'requestFingerprint': 'a' * 64, 'runId': 'run-1',
        'attemptId': 'attempt-1', 'expiresAt': '2099-01-01T00:00:00Z',
        'message': 'Run the requested operation?',
        'requestedSchema': {'type': 'object', 'required': ['optionId'], 'properties': {
            'optionId': {'type': 'string', 'enum': ['allow_once', 'reject_once'],
                         'enumNames': ['Allow once', 'Reject once']}}},
    }


def work_payload():
    return {'workRef': 'work-1', 'title': 'Synthetic image', 'state': 'needs_input',
            'actions': ['resume', 'stop'], 'pendingNativeInput': permission_payload()}


def test_current_native_permission_preserves_offered_choices_and_hides_generic_resume():
    item = orchestration._parse_work_item(work_payload())
    assert item.pending_native_input.options == (('allow_once', 'Allow once'), ('reject_once', 'Reject once'))
    assert item.actions == ('stop',)
    assert item.pending_native_input.response('reject_once') == {
        'version': 1, 'requestId': 'request-1', 'requestFingerprint': 'a' * 64,
        'action': 'accept', 'content': {'optionId': 'reject_once'},
    }
    with pytest.raises(ValueError):
        item.pending_native_input.response('invented_allow')


@pytest.mark.parametrize('mutation', ['expired', 'missing_fingerprint', 'invalid_options'])
def test_malformed_or_expired_permission_never_becomes_generic_resume(mutation):
    raw = work_payload()
    pending = raw['pendingNativeInput']
    if mutation == 'expired':
        pending['expiresAt'] = '2000-01-01T00:00:00Z'
    elif mutation == 'missing_fingerprint':
        pending.pop('requestFingerprint')
    else:
        pending['requestedSchema']['properties']['optionId']['enum'] = ['allow_once', 'allow_once']
    item = orchestration._parse_work_item(raw)
    assert item.pending_native_input is None
    assert item.actions == ('stop',)


def test_native_choice_token_is_topic_scoped_bounded_and_replays_exact_body(tmp_path):
    store = orchestration.CallbackCapabilityStore(tmp_path / 'callbacks.sqlite3', action_lease_s=5)
    body = orchestration._parse_work_item(work_payload()).pending_native_input.response('allow_once')
    issued = store.issue_actions(telegram_user_id='owner', chat_id='chat', message_thread_id='7',
        targets=[('work-1', 'resume')], native_input=body, expires_at=110.0, now=100.0)[0]
    assert 'allow_once' not in orchestration.action_callback_data(issued.token)
    assert store.reserve_action(issued.token, telegram_user_id='owner', chat_id='chat', message_thread_id='8', now=101) is None
    assert store.reserve_action(issued.token, telegram_user_id='other', chat_id='chat', message_thread_id='7', now=101) is None
    first = store.reserve_action(issued.token, telegram_user_id='owner', chat_id='chat', message_thread_id='7', now=101)
    assert first.target.native_input == body
    store.complete_action(first, succeeded=False, definitive=False, now=102)
    restarted = orchestration.CallbackCapabilityStore(store.path, action_lease_s=5)
    replay = restarted.reserve_action(issued.token, telegram_user_id='owner', chat_id='chat', message_thread_id='7', now=103)
    assert replay.operation_id == first.operation_id
    assert replay.target.native_input == body
    assert replay.replay is True
    restarted.complete_action(replay, succeeded=False, definitive=False, now=104)
    late = restarted.reserve_action(issued.token, telegram_user_id='owner', chat_id='chat', message_thread_id='7', now=111)
    assert late.operation_id == first.operation_id
    assert late.target.native_input == body
    fresh = store.issue_actions(telegram_user_id='owner', chat_id='chat', message_thread_id='7',
        targets=[('work-1', 'resume')], native_input=body, expires_at=110.0, now=100.0)[0]
    assert restarted.reserve_action(fresh.token, telegram_user_id='owner', chat_id='chat', message_thread_id='7', now=111) is None


@pytest.mark.parametrize('status, pending, accepted', [('pending', True, False), ('accepted', False, True), ('already_accepted', False, True)])
def test_owner_choice_forwards_exact_native_body_and_preserves_ack_uncertainty(monkeypatch, status, pending, accepted):
    client = orchestration.OrchestrationClient('https://example.test', 'synthetic-secret')
    item = orchestration._parse_work_item(work_payload())
    body = item.pending_native_input.response('allow_once')
    captured = []

    async def request(method, path, **kwargs):
        captured.append(kwargs['json_body'])
        return {'status': status, 'confirmationPending': pending}

    async def snapshot(_):
        return orchestration.parse_snapshot({'available': True, 'mode': 'parallel'},
            {'snapshot': 'fresh', 'work': [work_payload()], 'overflowCount': 0})

    monkeypatch.setattr(client, '_request_json', request)
    monkeypatch.setattr(client, 'get_snapshot', snapshot)
    result = asyncio.run(client.act('owner', 'work-1', 'resume', native_input=body,
        operation_id='a90c54b3-ae6a-4ffd-b5cd-4d237a761e42'))
    assert captured[0]['nativeInput'] == body
    assert result.action_receipt.accepted is accepted
    assert result.action_receipt.confirmation_pending is pending
