import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'TelegramVivBot'))
from TelegramVivBot.utils.librechat_bridge import LibreChatBridge, LibreChatSession
from TelegramVivBot import config


@pytest.fixture(autouse=True)
def isolated_delivery_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CORTEX_ACK_STORE_PATH", str(tmp_path / "acks.sqlite3"))


class Preferences:
    def __init__(self, legacy=''):
        self.values = {'LIBRECHAT_CONVERSATION_ID': legacy,
                       'LIBRECHAT_CONVERSATION_STATE_VERSION': '2'}
        self.writes = []

    def get_config(self, _key, field):
        return self.values.get(field)

    def set_config(self, _key, field, value):
        self.values[field] = dict(value) if isinstance(value, dict) else value
        self.writes.append((field, self.values[field]))

    def set_librechat_conversation_state(self, key, state):
        self.set_config(key, 'LIBRECHAT_CONVERSATION_STATE', state)
        self.values['LIBRECHAT_CONVERSATION_ID'] = state['conversation_id']
        self.values['LIBRECHAT_CONVERSATION_STATE_VERSION'] = '2'


def test_existing_conversation_migrates_once_and_fresh_state_survives_bridge_restart(monkeypatch):
    prefs = Preferences('prior-chat')
    monkeypatch.setattr(config, 'Users', prefs)
    first = config.get_librechat_conversation_state('chat:user')
    again = config.get_librechat_conversation_state('chat:user')
    assert first == again
    assert first['conversation_id'] == 'prior-chat'
    assert len(first['generation']) == 64
    assert len(prefs.writes) == 1


def test_reset_rotates_one_durable_preference_and_ignores_legacy_id(monkeypatch):
    prefs = Preferences('prior-chat')
    monkeypatch.setattr(config, 'Users', prefs)
    monkeypatch.setattr(config, 'ChatGPTbot', None)
    monkeypatch.setattr(config, 'VIVENTIUM_TELEGRAM_BACKEND', 'librechat')
    config.InitEngine(chat_id=None, initialize_stt=False)
    before = config.ChatGPTbot.capture_conversation_state('chat:user')
    writes = len(prefs.writes)
    config.ChatGPTbot.reset('chat:user')
    after = config.ChatGPTbot.capture_conversation_state('chat:user')
    assert len(prefs.writes) == writes + 1
    assert prefs.writes[-1][0] == 'LIBRECHAT_CONVERSATION_STATE'
    assert after['conversation_id'] == ''
    assert after['generation'] != before['generation']
    monkeypatch.setattr(config, 'ChatGPTbot', None)
    config.InitEngine(chat_id=None, initialize_stt=False)
    assert config.ChatGPTbot.capture_conversation_state('chat:user') == after


def make_bridge(state):
    def set_id(_key, value):
        state['conversation_id'] = value
        if not value:
            state['generation'] = 'b' * 64
    bridge = LibreChatBridge(get_conversation_id=lambda _: state['conversation_id'],
                            set_conversation_id=set_id,
                            get_conversation_state=lambda _: dict(state))
    bridge.base_url = 'http://example.com'
    bridge.secret = 'test-secret'
    bridge.include_insights = False
    bridge.insight_grace_s = 0
    return bridge


def call(bridge, sequence, **extra):
    return bridge.ask_stream_async('Original goal', 'chat:user', telegram_chat_id='chat',
        telegram_user_id='user', telegram_message_id=sequence,
        source_order_scope='c'*64, source_event_id=str(sequence).rjust(64,'0'), **extra)


def test_overlapping_fresh_starts_share_generation_until_first_response():
    async def scenario():
        state = {'conversation_id': '', 'generation': 'a'*64}
        bridge = make_bridge(state)
        starts = []
        release = asyncio.Event()
        async def start(**kwargs):
            starts.append(kwargs)
            await release.wait()
            return None
        bridge._start_chat = start
        async def consume(sequence):
            return [event async for event in call(bridge, sequence)]
        first = asyncio.create_task(consume(1))
        second = asyncio.create_task(consume(2))
        for _ in range(8):
            await asyncio.sleep(0)
        assert len(starts) == 2
        assert [(s['conversation_id'], s['conversation_generation']) for s in starts] == [('new','a'*64)]*2
        release.set()
        await asyncio.gather(first,second)


    asyncio.run(scenario())


def test_reset_during_preparation_does_not_rebind_old_input_to_new_conversation():
    async def scenario():
        state = {'conversation_id': '', 'generation': 'a'*64}
        bridge = make_bridge(state)
        original = bridge.capture_conversation_state('chat:user')
        bridge.reset('chat:user')
        async def unexpected(**_kwargs):
            raise AssertionError('Pre-reset source must not launch after reset')
        bridge._start_chat = unexpected
        events = [event async for event in call(bridge,1,conversation_state=original)]
        assert events == [{'type':'superseded','reason':'conversation_reset'}]
        assert bridge.capture_conversation_state('chat:user')['generation'] == 'b'*64


    asyncio.run(scenario())


def test_delayed_response_cannot_restore_saved_conversation_after_reset():
    async def scenario():
        state = {'conversation_id': '', 'generation': 'a'*64}
        bridge = make_bridge(state)
        started = asyncio.Event()
        release = asyncio.Event()
        async def start(**_kwargs):
            started.set()
            await release.wait()
            return LibreChatSession(stream_id='old-stream', conversation_id='old-canonical')
        async def stream(*_args, **_kwargs):
            if False:
                yield None
        bridge._start_chat = start
        bridge._stream_response = stream
        async def consume():
            return [event async for event in call(bridge,1)]
        task = asyncio.create_task(consume())
        await started.wait()
        bridge.reset('chat:user')
        release.set()
        await task
        assert state == {'conversation_id':'','generation':'b'*64}


    asyncio.run(scenario())


def test_reset_storage_failure_is_not_reported_as_success():
    bridge = make_bridge({'conversation_id':'old','generation':'a'*64})
    def broken(*_args):
        raise OSError('storage unavailable')
    bridge._set_conversation_id = broken
    with pytest.raises(OSError,match='storage unavailable'):
        bridge.reset('chat:user')


def test_legacy_receiver_change_rotates_generation_on_upgrade(monkeypatch):
    prefs = Preferences('prior-chat')
    monkeypatch.setattr(config, 'Users', prefs)
    prior = config.get_librechat_conversation_state('chat:user')
    prefs.values['LIBRECHAT_CONVERSATION_ID'] = 'legacy-new-chat'
    current = config.get_librechat_conversation_state('chat:user')
    assert current['conversation_id'] == 'legacy-new-chat'
    assert current['generation'] != prior['generation']
    assert prefs.values['LIBRECHAT_CONVERSATION_STATE'] == current


def test_state_and_rollback_mirror_persist_once_and_failure_restores_memory(monkeypatch):
    owner = config.UserConfig.__new__(config.UserConfig)
    owner.mode = 'multiusers'
    owner.user_id = 'chat:user'
    owner.users = config.NestedDict()
    owner.users['chat:user'] = config.NestedDict()
    owner.user_init = lambda _: None
    original = {'conversation_id':'old','generation':'a'*64}
    writes = []
    owner._persist_user_config = lambda _: writes.append(dict(owner.users['chat:user'].data))
    owner.set_librechat_conversation_state('chat:user',original)
    assert len(writes) == 1
    assert writes[0]['LIBRECHAT_CONVERSATION_ID'] == 'old'
    assert writes[0]['LIBRECHAT_CONVERSATION_STATE'] == original
    def failed(_):
        raise OSError('persist failed')
    owner._persist_user_config = failed
    with pytest.raises(OSError,match='persist failed'):
        owner.set_librechat_conversation_state('chat:user',{'conversation_id':'','generation':'b'*64})
    assert owner.users['chat:user'].data == writes[0]
