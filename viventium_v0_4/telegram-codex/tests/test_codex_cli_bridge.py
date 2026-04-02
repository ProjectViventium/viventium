from __future__ import annotations

from pathlib import Path

from app.codex_cli_bridge import CodexCliBridge
from app.config import CodexSettings


def _bridge() -> CodexCliBridge:
    return CodexCliBridge(
        CodexSettings(
            command="codex",
            model="gpt-5.4",
            sandbox="workspace-write",
            approval_policy="never",
            skip_git_repo_check=False,
        )
    )


def test_accumulate_stream_text_appends_agent_deltas():
    buffers: dict[str, str] = {}

    first = _bridge()._accumulate_stream_text(
        {"type": "agent_message_content_delta", "item_id": "item-1", "delta": "Hello"},
        buffers,
    )
    second = _bridge()._accumulate_stream_text(
        {"type": "agent_message_content_delta", "item_id": "item-1", "delta": " world"},
        buffers,
    )

    assert first == "Hello"
    assert second == "Hello world"


def test_accumulate_stream_text_uses_item_update_text():
    buffers: dict[str, str] = {}

    text = _bridge()._accumulate_stream_text(
        {
            "type": "item.updated",
            "item": {"id": "item-2", "type": "agent_message", "text": "Working on it"},
        },
        buffers,
    )

    assert text == "Working on it"
    assert buffers["item-2"] == "Working on it"


def test_build_new_turn_command_includes_images_before_exec():
    bridge = _bridge()
    command = bridge._build_new_turn_command(
        cwd=Path("/tmp/workspace"),
        relay_prompt="hi",
        image_paths=[Path("/tmp/workspace/a.png"), Path("/tmp/workspace/b.jpg")],
    )

    assert command[:5] == ["codex", "-i", "/tmp/workspace/a.png", "-i", "/tmp/workspace/b.jpg"]
    assert "--json" in command
    assert "exec" in command
    assert "hi" in command


def test_build_resume_command_uses_output_file_and_no_json():
    bridge = _bridge()
    command = bridge._build_resume_command(
        relay_prompt="resume hi",
        thread_id="thread-123",
        image_paths=[Path("/tmp/workspace/a.png")],
        output_file=Path("/tmp/codex-last-message.txt"),
    )

    assert command[:3] == ["codex", "-i", "/tmp/workspace/a.png"]
    assert command.count("--json") == 0
    assert command[-5:] == ["-o", "/tmp/codex-last-message.txt", "resume", "thread-123", "resume hi"]
    assert "-o" in command
    assert "resume" in command


def test_extract_resume_stdout_message_uses_last_non_empty_line():
    text = "\nhello\n\nworld\n"
    assert _bridge()._extract_resume_stdout_message(text) == "world"


def test_benign_stderr_detection_handles_auth_required_noise():
    assert _bridge()._is_benign_stderr_line(
        'ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when AuthRequired(AuthRequiredError { www_authenticate_header: "Bearer error=\\"invalid_token\\", error_description=\\"Authentication required\\", resource_metadata=\\"http://localhost:8111/.well-known/oauth-protected-resource\\"" })'
    )
