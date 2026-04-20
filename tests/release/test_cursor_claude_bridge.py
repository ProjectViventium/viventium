from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "cursor_bridge" / "claude_openai_compat_bridge.py"


def load_module():
    spec = importlib.util.spec_from_file_location("claude_openai_compat_bridge", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_chat_messages_merges_system_and_history() -> None:
    module = load_module()

    system_text, prompt = module._normalize_chat_messages(
        [
            {"role": "system", "content": "Follow the house style."},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "Previous answer"},
            {"role": "user", "content": [{"type": "text", "text": "Latest question"}]},
        ]
    )

    assert system_text == "Follow the house style."
    assert prompt == (
        "USER:\nFirst question\n\n"
        "ASSISTANT:\nPrevious answer\n\n"
        "USER:\nLatest question\n\n"
        "ASSISTANT:"
    )


def test_normalize_responses_input_understands_message_items() -> None:
    module = load_module()

    system_text, prompt = module._normalize_responses_input(
        {
            "instructions": "Be concise.",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Inspect this file"}],
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Sure"}],
                },
                {"type": "input_text", "text": "Now summarize it"},
            ],
        }
    )

    assert system_text == "Be concise."
    assert prompt == (
        "USER:\nInspect this file\n\n"
        "ASSISTANT:\nSure\n\n"
        "USER:\nNow summarize it\n\n"
        "ASSISTANT:"
    )


def test_content_to_text_ignores_non_text_payloads() -> None:
    module = load_module()

    text = module._content_to_text(
        [
            {"type": "text", "text": "alpha"},
            {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
            {"type": "output_text", "text": "beta"},
        ]
    )

    assert text == "alpha\n\nbeta"


def test_chat_usage_maps_claude_usage_shape() -> None:
    module = load_module()

    usage = module._chat_usage({"usage": {"input_tokens": 11, "output_tokens": 7}})

    assert usage == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }


def test_chat_usage_maps_codex_usage_shape() -> None:
    module = load_module()

    usage = module._chat_usage({"usage": {"prompt_tokens": 19, "completion_tokens": 5}})

    assert usage == {
        "prompt_tokens": 19,
        "completion_tokens": 5,
        "total_tokens": 24,
    }


def test_parse_codex_exec_output_uses_final_agent_message_and_usage() -> None:
    module = load_module()

    text, payload = module._parse_codex_exec_output(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-1"}',
                '{"type":"item.completed","item":{"id":"item-1","type":"agent_message","text":"Working"}}',
                '{"type":"item.completed","item":{"id":"item-2","type":"agent_message","text":"Finished"}}',
                '{"type":"turn.completed","usage":{"input_tokens":101,"cached_input_tokens":9,"output_tokens":17}}',
            ]
        )
    )

    assert text == "Finished"
    assert payload == {"usage": {"input_tokens": 101, "cached_input_tokens": 9, "output_tokens": 17}}


def test_compose_codex_prompt_includes_system_block() -> None:
    module = load_module()

    prompt = module._compose_codex_prompt(
        "USER:\nSummarize this.\n\nASSISTANT:",
        system_prompt="Bridge rules.",
    )

    assert prompt == "SYSTEM:\nBridge rules.\n\nUSER:\nSummarize this.\n\nASSISTANT:"


def test_select_backend_for_model_routes_custom_and_native_aliases() -> None:
    module = load_module()

    assert module._select_backend_for_model("SUBSCRIPTION OPUS") == "claude"
    assert module._select_backend_for_model("claude-opus-4-7") == "claude"
    assert module._select_backend_for_model("CODEX_SUBSCRIPTION") == "codex"
    assert module._select_backend_for_model("SUBSCRIPTION GPT 5.4 XHIGH") == "codex"
    assert module._select_backend_for_model("gpt-5.4") == "codex"
