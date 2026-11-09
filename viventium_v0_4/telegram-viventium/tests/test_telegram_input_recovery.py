import ast
import asyncio
import importlib.util
import logging
import os
import re
import sys
import tempfile
import time
from datetime import timedelta
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "TelegramVivBot"))


def load_bot_owners(*names, **values):
    tree = ast.parse((ROOT / "TelegramVivBot/bot.py").read_text())
    nodes = [node for node in tree.body if getattr(node, "name", "") in names]
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.decorator_list = []
    namespace = {"asyncio": asyncio, "logger": logging.getLogger(__name__),
                 "uuid": uuid, "re": re, **values}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "bot-owners", "exec"), namespace)
    return namespace


class InputRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_lost_preparation_claim_cancels_only_its_owned_task(self):
        preparation_started = asyncio.Event()
        release_renewal = asyncio.Event()
        cancelled = asyncio.Event()
        async def renewal_wait(_seconds):
            await release_renewal.wait()
        async def operation():
            preparation_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        owners = load_bot_owners("_run_with_telegram_input_claims", asyncio=SimpleNamespace(
            current_task=asyncio.current_task, create_task=asyncio.create_task,
            sleep=renewal_wait, CancelledError=asyncio.CancelledError,
        ))
        guard = SimpleNamespace(input_claim={"claimToken": "original"},
            robot=SimpleNamespace(input_status=AsyncMock(side_effect=RuntimeError("replaced claim"))))
        task = asyncio.create_task(owners["_run_with_telegram_input_claims"]([guard], operation))
        await preparation_started.wait()
        release_renewal.set()
        self.assertIsNone(await asyncio.wait_for(task, 1))
        self.assertTrue(cancelled.is_set())
        guard.robot.input_status.assert_awaited_once_with(guard.input_claim, "renew")

    def test_current_presentation_binding_never_rewrites_original_source(self):
        owners = load_bot_owners("_TelegramSourceOrderGuard", Any=Any, Literal=Literal)
        guard = owners["_TelegramSourceOrderGuard"](bot=None, robot=None, telegram_user_id=7,
            chat_id=8, thread_id=None, source_sequence=41)
        guard.source_event_id = "a" * 64
        guard.source_order_scope = "b" * 64
        guard.input_claim = {"sourceMessageId": "original"}
        binding = {"sourceEventId": "a" * 64, "sourceOrderScope": "b" * 64,
            "sourceMessageId": "original", "sourceSequence": 41, "presentationSourceSequence": 43}
        guard.bind_input_presentation(binding)
        self.assertEqual(guard.source_sequence, 41)
        self.assertEqual(guard.presentation_source_sequence, 43)
        for field, value in (("sourceMessageId", "other"), ("sourceEventId", "c" * 64),
                             ("sourceOrderScope", "c" * 64), ("sourceSequence", 42)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                guard.bind_input_presentation({**binding, field: value})
        self.assertEqual(guard.presentation_source_sequence, 43)

    async def test_retained_duplicate_resumes_the_same_stream_with_current_presentation_authority(self):
        spec = importlib.util.spec_from_file_location("preparation_test_bridge",
            ROOT / "TelegramVivBot/utils/librechat_bridge.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("VIVENTIUM_TELEGRAM_CORTEX_ACK_STORE_PATH")
            os.environ["VIVENTIUM_TELEGRAM_CORTEX_ACK_STORE_PATH"] = str(Path(directory) / "ack.sqlite3")
            try:
                state = {"conversation_id": "existing", "generation": "a" * 64}
                bridge = module.LibreChatBridge(get_conversation_id=lambda _: "existing",
                    set_conversation_id=lambda *_: None, get_conversation_state=lambda _: state)
                bridge.base_url = "https://example.invalid"
                bridge.secret = "synthetic-secret"
                bridge.insight_grace_s = 0
                bridge._start_chat = AsyncMock(side_effect=AssertionError("Must not start another turn"))
                binding = {"sourceEventId": "c" * 64, "sourceMessageId": "original-source",
                    "sourceOrderScope": "b" * 64, "sourceSequence": 42, "presentationSourceSequence": 43}
                bridge.continue_input = AsyncMock(return_value={"duplicate": True, "streamId": "retained-stream",
                    "conversationId": "existing", "logical_turn_id": "current-turn", "revision": 2,
                    "inputPresentation": binding})
                async def stream(stream_id, *_args, **_kwargs):
                    self.assertEqual(stream_id, "retained-stream")
                    identity = bridge._stream_identity[stream_id]
                    self.assertEqual(identity["telegram_message_id"], "42")
                    self.assertEqual(bridge._poll_delivery_authority(stream_id)["source_sequence"], 43)
                    yield "Useful retained result"
                bridge._stream_response = stream
                claim = {"sourceEventId": "c" * 64, "claimToken": "current-claim"}
                result = [item async for item in bridge.ask_stream_async("Original goal", "8:7",
                    telegram_chat_id="8", telegram_user_id="7", telegram_message_id=42,
                    source_order_scope="b" * 64, source_event_id="c" * 64,
                    input_claim=claim, input_recovery=claim)]
                self.assertEqual(result[0], {"type": "input_presentation", "input_presentation": binding})
                self.assertEqual(result[-1], "Useful retained result")
                bridge._start_chat.assert_not_called()
                bridge.continue_input.assert_awaited_once_with(claim)
            finally:
                if previous is None:
                    os.environ.pop("VIVENTIUM_TELEGRAM_CORTEX_ACK_STORE_PATH", None)
                else:
                    os.environ["VIVENTIUM_TELEGRAM_CORTEX_ACK_STORE_PATH"] = previous

    async def test_ingress_retains_before_slow_preparation_and_does_not_drop_older_owned_input(self):
        retained = []
        prepared = []
        started = asyncio.Event()
        release = asyncio.Event()

        class Guard:
            def __init__(self, **values):
                self.__dict__.update(values)
                self.input_claim = None

        class Bridge:
            def capture_conversation_state(self, _key):
                return {"conversation_id": "existing", "generation": "a" * 64}

            async def observe_source_order(self, **values):
                retained.append(values)
                sequence = values["source_sequence"]
                return {"stale": sequence == 1, "source_order_scope": "b" * 64,
                        "source_event_id": str(sequence).rjust(64, "0"),
                        "input": {"claimed": True, "claimToken": str(sequence),
                                  "sourceEventId": str(sequence).rjust(64, "0"),
                                  "sourceMessageId": f"source-{sequence}"}}

        bridge = Bridge()
        owners = load_bot_owners(
            "_observe_ingress_source_guard", "command_bot",
            _TelegramSourceOrderGuard=Guard, _note_telegram_source_message=lambda *_: None,
            TelegramLinkRequired=type("LinkRequired", (Exception,), {}),
            capture_telegram_preparation=lambda update, **_: {"message": {"text": update.text}},
        )

        async def observe(update, context, **values):
            return await owners["_observe_ingress_source_guard"](
                bot=context.bot, robot=bridge, update_message=update,
                chat_id=8, thread_id=None, source_sequence=update.message_id, **values,
            )

        async def prepare(update, _context, _title, _has_command, guard):
            self.assertEqual(retained[-1]["input"]["preparation"]["message"]["text"], update.text)
            if update.message_id == 1:
                started.set()
                await release.wait()
            prepared.append((update.text, guard.input_claim["sourceMessageId"]))

        async def run(_guards, operation):
            return await operation()

        owners.update(_observe_telegram_update_ingress=observe,
                      _command_bot_prepared=prepare, _run_with_telegram_input_claims=run)
        context = SimpleNamespace(bot=object(), args=[])
        first = SimpleNamespace(message_id=1, from_user=SimpleNamespace(id=7), text="Voice goal", caption=None)
        second = SimpleNamespace(message_id=2, from_user=SimpleNamespace(id=7), text="Quick question", caption=None)
        task = asyncio.create_task(owners["command_bot"](first, context, has_command=False))
        await started.wait()
        await owners["command_bot"](second, context, has_command=False)
        self.assertEqual(prepared, [("Quick question", "source-2")])
        release.set()
        await task
        self.assertEqual(prepared[-1], ("Voice goal", "source-1"))
        self.assertNotEqual(retained[0]["input"]["preparationId"], retained[1]["input"]["preparationId"])

    async def test_transcription_presentation_race_keeps_the_owned_text(self):
        stale = type("Stale", (Exception,), {})
        async def presentation(*_args, **_kwargs):
            raise stale()
        owners = load_bot_owners("_resolve_prepared_voice_input", "_prepared_voice_text",
            _StaleTelegramSourceOrder=stale,
            _with_source_ordered_context_bot=presentation,
            _finish_telegram_preparation=AsyncMock(),
        )
        guard = SimpleNamespace(is_current=AsyncMock(return_value=True))
        result = await owners["_resolve_prepared_voice_input"](
            object(), guard, message=None, voice_text="Original transcribed goal", voice_error_text=None,
        )
        self.assertEqual(result, ("Original transcribed goal", False))

    async def test_typed_no_speech_cancels_preparation_without_authored_input(self):
        from TelegramVivBot.utils.scripts import TelegramTranscriptionResult
        finished = AsyncMock()
        owners = load_bot_owners("_resolve_prepared_voice_input", "_resolve_voice_input_message",
            "_prepared_voice_text", _finish_telegram_preparation=finished,
            _with_source_ordered_context_bot=lambda context, _guard, operation, **_: operation(context))
        guard = SimpleNamespace(is_current=AsyncMock(return_value=True))
        context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
        notice = TelegramTranscriptionResult(error_text="No speech was detected.", error_code="no_speech")
        result = await owners["_resolve_prepared_voice_input"](context, guard,
            chatid=8, messageid=42, message_thread_id=None,
            message=None, voice_text=None, voice_error_text=notice.error_text)
        self.assertEqual(result, (None, True))
        finished.assert_awaited_once_with(guard, "cancelled", "no_speech")
        context.bot.send_message.assert_awaited_once()

    async def test_plain_notice_words_do_not_determine_preparation_status(self):
        finished = AsyncMock()
        owners = load_bot_owners("_resolve_prepared_voice_input", "_resolve_voice_input_message",
            "_prepared_voice_text", _finish_telegram_preparation=finished,
            _with_source_ordered_context_bot=lambda context, _guard, operation, **_: operation(context))
        guard = SimpleNamespace(is_current=AsyncMock(return_value=True))
        context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
        await owners["_resolve_prepared_voice_input"](context, guard,
            chatid=8, messageid=42, message_thread_id=None,
            message=None, voice_text=None, voice_error_text="No speech was detected.")
        finished.assert_awaited_once_with(guard, "failed", "transcription_failed")

    async def test_caption_and_successful_speech_both_reach_main(self):
        owners = load_bot_owners("_resolve_voice_input_message", "_prepared_voice_text")
        context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
        result = await owners["_resolve_voice_input_message"](context,
            chatid=8, messageid=42, message_thread_id=None,
            message="Compare the attached options.", voice_text="Use total ownership cost over five years.",
            voice_error_text=None)
        self.assertEqual(result, ("Compare the attached options.\n\nUse total ownership cost over five years.", False))
        context.bot.send_message.assert_not_called()

    async def test_partial_media_notice_keeps_preparation_and_uses_current_source(self):
        from TelegramVivBot.utils.scripts import TelegramTranscriptionNotice

        finished = AsyncMock()
        owners = load_bot_owners("_resolve_prepared_voice_input", "_resolve_voice_input_message",
            "_prepared_voice_text", _finish_telegram_preparation=finished,
            _with_source_ordered_context_bot=lambda context, _guard, operation, **_: operation(context))
        notice = TelegramTranscriptionNotice("Frames unavailable.", "video_frames_timeout", continues=True)
        for is_current in (True, False):
            with self.subTest(is_current=is_current):
                guard = SimpleNamespace(is_current=AsyncMock(return_value=is_current))
                context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
                result = await owners["_resolve_prepared_voice_input"](context, guard,
                    chatid=8, messageid=42, message_thread_id=None,
                    message=None, voice_text="Exact spoken input.", voice_error_text=notice)
                self.assertEqual(result, ("Exact spoken input.", False))
                self.assertEqual(context.bot.send_message.await_count, int(is_current))
        finished.assert_not_awaited()

    async def test_retained_text_uses_core_merge_and_settles_empty_command(self):
        forwarded = AsyncMock()
        finished = AsyncMock()
        context = SimpleNamespace(args=[], job_queue=SimpleNamespace(run_once=lambda *a, **k: None))
        guard = SimpleNamespace(input_claim={"sourceEventId": "original"}, robot=None)
        message = SimpleNamespace(chat=SimpleNamespace(type="private"), voice=None, video_note=None)
        owners = load_bot_owners("_command_bot_prepared",
            stop_event=SimpleNamespace(clear=lambda: None),
            _preflight_captioned_transcription_failure=AsyncMock(return_value=(None, False)),
            _queue_media_group_update=AsyncMock(return_value=False),
            _unpack_message_info=lambda value: value,
            time=time, timedelta=timedelta, RESET_TIME=60,
            _tg_timing_log=lambda *a: None, _tg_deep_enabled=lambda: False,
            _tg_deep_log=lambda *a, **k: None,
            get_robot=lambda *_: (object(), None, None, None),
            _finish_telegram_preparation=finished,
            _resolve_prepared_voice_input=AsyncMock(), is_emoji=lambda _: True,
            config=SimpleNamespace(NICK=None, VIVENTIUM_TELEGRAM_FILE_TEXT_FALLBACK=False,
                                   VIVENTIUM_TELEGRAM_BACKEND="librechat"),
            Users=SimpleNamespace(get_config=lambda *_: True),
            remove_job_if_exists=lambda *a: None, scheduled_function=object(),
            _telegram_reply_context_v1=lambda *a: None,
            getViventiumResponse=forwarded,
        )
        # A legacy buffer must never be consulted for a retained source. This namespace has
        # no local buffer or lock; its existing Core owner receives each original independently.
        for text in ("First complete goal", "👍"):
            info = (text, text, None, 8, 42, None, message, None, "8:7", None,
                    None, None, None, [], [])
            owners["GetMesageInfo"] = AsyncMock(return_value=info)
            owners["_resolve_prepared_voice_input"].return_value = (text, False)
            await owners["_command_bot_prepared"](SimpleNamespace(update_id=10), context, "", False, guard)
            self.assertEqual(forwarded.call_args.args[4], text)
        self.assertEqual(forwarded.await_count, 2)
        finished.assert_not_called()
        owners["GetMesageInfo"].return_value = (None, None, None, 8, 42, None, message, None,
                                               "8:7", None, None, None, None, [], [])
        owners["_resolve_prepared_voice_input"].return_value = (None, False)
        await owners["_command_bot_prepared"](SimpleNamespace(update_id=10), context, "", False, guard)
        finished.assert_awaited_once_with(guard, "cancelled")
        self.assertEqual(forwarded.await_count, 2)

    async def test_uncaptioned_video_file_keeps_grid_after_partial_transcription_failure(self):
        from TelegramVivBot.utils.scripts import TelegramTranscriptionNotice

        notice = TelegramTranscriptionNotice("Use the frames.", "transcription_failed", continues=True)
        message = SimpleNamespace(chat=SimpleNamespace(type="private"), message_id=42, from_user=None)
        context = SimpleNamespace(bot=object())
        files = [{"filename": "video-frames.jpg"}]
        info = (None, None, None, 8, 42, None, message, None, "8:7", None,
                None, None, notice, files, [])
        prepared = AsyncMock(return_value=(None, False))
        send = AsyncMock()
        owners = load_bot_owners("_handle_file_prepared",
            _queue_media_group_update=AsyncMock(return_value=False),
            _unpack_message_info=lambda value: value, GetMesageInfo=AsyncMock(return_value=info),
            _resolve_prepared_voice_input=prepared, getViventiumResponse=send,
            get_robot=lambda *_: (object(), None, None, None),
            Users=SimpleNamespace(get_config=lambda *_: None),
            config=SimpleNamespace(VIVENTIUM_TELEGRAM_FILE_TEXT_FALLBACK=False),
            _telegram_reply_context_v1=lambda *a: None,
        )
        await owners["_handle_file_prepared"](SimpleNamespace(update_id=10), context, SimpleNamespace())
        self.assertIs(prepared.call_args.kwargs["voice_error_text"], notice)
        self.assertIs(send.call_args.kwargs["files"], files)

    async def test_video_album_keeps_caption_and_transcripts_in_upload_order(self):
        def album_item(sequence, caption, transcript):
            message = SimpleNamespace(message_id=sequence, chat=SimpleNamespace(type="private"),
                                      from_user=None)
            update = SimpleNamespace(update_id=sequence, message=message)
            guard = SimpleNamespace(source_sequence=sequence, input_claim={"sourceSequence": sequence})
            info = (caption, caption, None, 8, sequence, None, message, None, "8:7", None,
                    None, transcript, None, [{"filename": f"{sequence}-frames.jpg"}], [])
            return {"update": update, "context": SimpleNamespace(bot=object()), "ingress_guard": guard}, info

        first, first_info = album_item(41, None, "First video.")
        second, second_info = album_item(42, "Compare these clips.", "Second video.")
        send = AsyncMock()
        owners = load_bot_owners("_process_media_group_entries", "_prepared_voice_text",
            _telegram_update_message=lambda update: update.message,
            _unpack_message_info=lambda value: value,
            GetMesageInfo=AsyncMock(side_effect=[first_info, second_info]),
            get_robot=lambda *_: (object(), None, None, None),
            getViventiumResponse=send, _telegram_reply_context_v1=lambda *a: None,
        )
        await owners["_process_media_group_entries"](("8", "", "7", "group"), [second, first])
        self.assertEqual(send.await_count, 1)
        self.assertEqual(send.call_args.args[4], "Compare these clips.\n\nFirst video.\n\nSecond video.")
        self.assertEqual(send.call_args.kwargs["files"], first_info[13] + [
            {**second_info[13][0], "caption": "Compare these clips."},
        ])

    async def test_ready_recovery_uses_retained_stream_without_preparing_or_starting_another_turn(self):
        message = SimpleNamespace(message_id=42, message_thread_id=None, voice=None, video_note=None)
        update = SimpleNamespace(update_id=10)
        context = SimpleNamespace(args=None)
        application = SimpleNamespace(bot=object(), context_types=SimpleNamespace(
            context=SimpleNamespace(from_update=lambda *_: context)))
        robot = SimpleNamespace(capture_conversation_state=lambda _: {"generation": "a" * 64})
        claim = {"preparation": {"command": {}}, "telegramChatId": "8", "telegramUserId": "7",
                 "conversationGeneration": "a" * 64, "state": "ready", "sourceSequence": 42,
                 "text": "Prepared original goal"}
        render = AsyncMock()
        async def run(_guards, operation):
            return await operation()
        owners = load_bot_owners("_resume_telegram_input",
            restore_telegram_preparation=lambda *_: update, _telegram_update_message=lambda _: message,
            _observe_telegram_update_ingress=AsyncMock(return_value=object()),
            _run_with_telegram_input_claims=run, getViventiumResponse=render,
            handle_file=AsyncMock(side_effect=AssertionError("Must not prepare again")),
            command_bot=AsyncMock(side_effect=AssertionError("Must not prepare again")),
        )
        await owners["_resume_telegram_input"](application, robot, claim)
        self.assertEqual(render.await_count, 1)
        self.assertIs(render.call_args.kwargs["_input_recovery"], claim)

    async def test_explicit_reset_cancels_old_preparation_without_rebinding(self):
        update = SimpleNamespace(update_id=10)
        robot = SimpleNamespace(capture_conversation_state=lambda _: {"generation": "b" * 64},
                                input_status=AsyncMock())
        claim = {"preparation": {}, "telegramChatId": "8", "telegramUserId": "7",
                 "conversationGeneration": "a" * 64, "state": "preparing"}
        owners = load_bot_owners("_resume_telegram_input",
            restore_telegram_preparation=lambda *_: update, _telegram_update_message=lambda _: None)
        await owners["_resume_telegram_input"](SimpleNamespace(bot=object()), robot, claim)
        robot.input_status.assert_awaited_once_with(claim, "cancelled")

    async def test_album_keeps_distinct_verbatim_captions_bound_to_original_files(self):
        cases = [
            (["Compare the red option.", "Use the blue option's warranty."],
             "Attachment 1 (same.jpg):\nCompare the red option.\n\nAttachment 2 (same.jpg):\nUse the blue option's warranty."),
            (["Same request.", "Same request."], "Same request."),
            ([None, None], ""),
            (["Only caption.", None], "Only caption."),
            ([None, "Later caption."], "Later caption."),
            (["  Exact caption: café 17 + 23\nSecond line.  ", "Exact second instruction."],
             "Attachment 1 (same.jpg):\n  Exact caption: café 17 + 23\nSecond line.  \n\nAttachment 2 (same.jpg):\nExact second instruction."),
        ]
        for captions, expected in cases:
            for with_transcripts in (False, True):
                with self.subTest(captions=captions, with_transcripts=with_transcripts):
                    infos, entries, originals = [], [], []
                    for index, caption in enumerate(captions):
                        sequence = 41 + index
                        message = SimpleNamespace(message_id=sequence, chat=SimpleNamespace(type="private"),
                                                  from_user=None)
                        update = SimpleNamespace(update_id=sequence, message=message)
                        guard = SimpleNamespace(source_sequence=sequence, input_claim={"sourceSequence": sequence})
                        attachment = {"filename": "same.jpg", "data": f"original-{sequence}"}
                        originals.append(attachment.copy())
                        transcript = f"Transcript {index + 1}." if with_transcripts else None
                        infos.append((caption, caption, None, 8, sequence, None, message, None, "8:7", None,
                                      None, transcript, None, [attachment], []))
                        entries.append({"update": update, "context": SimpleNamespace(bot=object()),
                                        "ingress_guard": guard})
                    send = AsyncMock()
                    owners = load_bot_owners("_process_media_group_entries", "_prepared_voice_text",
                        _telegram_update_message=lambda update: update.message,
                        _unpack_message_info=lambda value: value,
                        GetMesageInfo=AsyncMock(side_effect=infos),
                        get_robot=lambda *_: (object(), None, None, None),
                        getViventiumResponse=send, _telegram_reply_context_v1=lambda *a: None,
                    )
                    await owners["_process_media_group_entries"](("8", "", "7", "group"), list(reversed(entries)))
                    self.assertEqual(send.await_count, 1)
                    actual_text = expected
                    if with_transcripts:
                        actual_text = (actual_text + "\n\n" if actual_text else "") + "Transcript 1.\n\nTranscript 2."
                    self.assertEqual(send.call_args.args[4], actual_text)
                    expected_files = [{**original, **({"caption": caption} if caption else {})}
                                      for original, caption in zip(originals, captions)]
                    self.assertEqual(send.call_args.kwargs["files"], expected_files)
                    self.assertEqual([info[13][0] for info in infos], originals)
                    self.assertEqual(send.call_args.kwargs["_source_guard"].input_claims,
                                     [{"sourceSequence": 41}, {"sourceSequence": 42}])


if __name__ == "__main__":
    unittest.main()
