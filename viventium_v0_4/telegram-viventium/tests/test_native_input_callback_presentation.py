"""Native answers preserve the question instead of opening unrelated work."""

import ast
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


def run_callback(*, native_input=None, data="PW:A:owned", replay=False, error=None,
                 from_roster=False):
    source = Path(os.environ.get("VIVENTIUM_TEST_BOT_SOURCE", ""))
    if not source.is_file():
        source = Path(__file__).parents[1] / "TelegramVivBot/bot.py"
    node = next(item for item in ast.parse(source.read_text()).body
                if isinstance(item, ast.AsyncFunctionDef)
                and item.name == "_handle_parallel_work_callback")
    output = {}
    original = "Which shape should I draw? Blue circle; Green square."
    target = SimpleNamespace(action="resume" if native_input else "pause",
                             native_input=native_input, work_ref="work-current",
                             native_prompt_text=original if native_input and not from_roster else None)
    reservation = SimpleNamespace(target=target, replay=replay)
    store = SimpleNamespace(reserve_action=lambda *args, **kwargs: reservation)

    class ActionError(Exception):
        indeterminate = False

    async def snapshot(*args, **kwargs):
        return SimpleNamespace(items=["current", "unrelated-private-work"])

    async def execute(**kwargs):
        output["reservation"] = kwargs["reservation"]
        if error:
            raise ActionError(error)
        return await snapshot()

    def roster(*args, **kwargs):
        output["roster_opened"] = True
        return "All work including unrelated-private-work", "roster-controls"

    async def edit(*args, **kwargs):
        output.update(text=kwargs["text"], markup=kwargs["reply_markup"])

    scope = {
        "_get_parallel_work_client": lambda: SimpleNamespace(get_snapshot=snapshot),
        "_get_parallel_work_callback_store": lambda: store,
        "_execute_parallel_work_action": execute,
        "_active_work_view": roster,
        "_edit_parallel_work_view": edit,
        "CONFIRM_ACTIONS": {"stop"}, "INSTRUCTION_ACTIONS": {"queue", "message", "steer"},
        "OrchestrationLinkRequired": type("LinkError", (Exception,), {}),
        "OrchestrationError": ActionError,
        "_parallel_work_unavailable_view": lambda reason: (reason, "retry-controls"),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
    update = SimpleNamespace(effective_user=SimpleNamespace(id="owner"),
                             effective_chat=SimpleNamespace(id="chat"))
    callback = SimpleNamespace(message=SimpleNamespace(
        text="Confirmation is pending; retry the same action." if replay else original,
        message_thread_id=7))
    asyncio.run(scope["_handle_parallel_work_callback"](update, None, callback, data))
    return output, reservation, original


@pytest.mark.parametrize("kind,replay", [("question", False), ("permission", False),
                                         ("question", True), ("permission", True)])
def test_native_ack_preserves_question_without_roster_or_new_controls(kind, replay):
    output, reservation, original = run_callback(native_input={"kind": kind}, replay=replay)
    assert output["reservation"] is reservation
    assert output["text"] == original
    assert output["markup"] is None
    assert "roster_opened" not in output
    assert "unrelated-private-work" not in output["text"]


def test_explicit_roster_and_ordinary_work_action_keep_existing_view():
    for data in ["PW:L", "PW:A:owned"]:
        output, _, _ = run_callback(data=data)
        assert output["roster_opened"]
        assert output["markup"] == "roster-controls"
    output, _, _ = run_callback(native_input={"kind": "question"}, from_roster=True)
    assert output["roster_opened"]
    assert output["markup"] == "roster-controls"


def test_failed_native_answer_keeps_honest_recovery():
    output, _, _ = run_callback(native_input={"kind": "question"}, error="Question is no longer current")
    assert output["text"] == "Question is no longer current"
    assert output["markup"] == "retry-controls"
    assert "roster_opened" not in output


def test_native_prompt_survives_restart_and_uncertain_replay_without_entering_authority(tmp_path):
    from TelegramVivBot.utils import orchestration
    from test_parallel_work_native_input import permission_payload

    store = orchestration.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3", action_lease_s=5)
    body = orchestration._parse_native_permission(permission_payload()).response("allow_once")
    original = "Allow this one file to be saved?"
    token = store.issue_actions(telegram_user_id="owner", chat_id="chat", message_thread_id="7",
        targets=[("work-current", "resume")], native_input=body, native_prompt_text=original,
        expires_at=110, now=100)[0].token
    first = store.reserve_action(token, telegram_user_id="owner", chat_id="chat",
                                 message_thread_id="7", now=101)
    store.complete_action(first, succeeded=False, definitive=False, now=102)
    resumed = orchestration.CallbackCapabilityStore(store.path, action_lease_s=5)
    retry = resumed.reserve_action(token, telegram_user_id="owner", chat_id="chat",
                                   message_thread_id="7", now=103)
    assert retry.replay and retry.operation_id == first.operation_id
    assert retry.target.native_prompt_text == original
    assert retry.target.native_input == body
    assert "native_prompt_text" not in retry.target.native_input
    assert resumed.reserve_action(token, telegram_user_id="other", chat_id="chat",
                                  message_thread_id="7", now=103) is None


@pytest.mark.parametrize("value", ["", " ", 9, "x" * 4097])
def test_invalid_native_presentation_is_not_saved(tmp_path, value):
    from TelegramVivBot.utils import orchestration
    from test_parallel_work_native_input import permission_payload

    store = orchestration.CallbackCapabilityStore(tmp_path / "callbacks.sqlite3")
    body = orchestration._parse_native_permission(permission_payload()).response("allow_once")
    with pytest.raises(ValueError, match="presentation"):
        store.issue_actions(telegram_user_id="owner", chat_id="chat",
            targets=[("work-current", "resume")], native_input=body, native_prompt_text=value)


def test_missing_control_message_recovery_stays_in_original_topic(monkeypatch):
    import sys

    class BadRequest(Exception):
        pass

    monkeypatch.setitem(sys.modules, "telegram", SimpleNamespace(error=SimpleNamespace(BadRequest=BadRequest)))
    source = Path(__file__).parents[1] / "TelegramVivBot/bot.py"
    node = next(item for item in ast.parse(source.read_text()).body
                if isinstance(item, ast.AsyncFunctionDef) and item.name == "_edit_parallel_work_view")
    scope = {"logger": SimpleNamespace(warning=lambda *args: None)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
    observed = {}

    async def edit(**kwargs):
        raise BadRequest("Message to edit not found")

    async def send(**kwargs):
        observed.update(kwargs)

    callback = SimpleNamespace(message=SimpleNamespace(message_thread_id=7), edit_message_text=edit)
    update = SimpleNamespace(effective_chat=SimpleNamespace(id="chat"))
    context = SimpleNamespace(bot=SimpleNamespace(send_message=send))
    asyncio.run(scope["_edit_parallel_work_view"](callback, context, text="Original question",
                                                  reply_markup=None, update=update))
    assert observed["message_thread_id"] == 7
    assert observed["text"] == "Original question"
    assert observed["reply_markup"] is None


@pytest.mark.parametrize("pending_message", ["", "x" * 8000])
def test_buttons_retain_supplied_visible_prompt_not_optional_raw_message(pending_message):
    source = Path(__file__).parents[1] / "TelegramVivBot/bot.py"
    node = next(item for item in ast.parse(source.read_text()).body
                if isinstance(item, ast.FunctionDef) and item.name == "_native_permission_buttons")
    captured = []

    def issue(**kwargs):
        captured.append(kwargs)
        return [SimpleNamespace(token="current-token")]

    scope = {"_get_parallel_work_callback_store": lambda: SimpleNamespace(issue_actions=issue),
             "InlineKeyboardButton": lambda label, **kwargs: (label, kwargs),
             "action_callback_data": lambda token: token}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
    pending = SimpleNamespace(message=pending_message, options=[("allow_once", "Yes")],
                              expires_at=110, response=lambda option: {"optionId": option})
    item = SimpleNamespace(pending_native_input=pending, work_ref="work-current")
    scope["_native_permission_buttons"](item, telegram_user_id="owner", chat_id="chat",
                                       native_prompt_text="Rendered current question")
    assert captured[0]["native_prompt_text"] == "Rendered current question"
    assert captured[0]["native_input"] == {"optionId": "allow_once"}
