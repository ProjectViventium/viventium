from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from prompt_workbench import frames  # noqa: E402


REPO_ROOT = BACKEND_ROOT.parents[2]
TELEMETRY_MODULE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "promptFrameTelemetry.js"
)
CORE_FORMATTER_MODULE = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "api" / "config" / "parsers.js"
LIBRECHAT_ROOT = REPO_ROOT / "viventium_v0_4" / "LibreChat"


def _trace(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": 1,
        "time": "2026-08-26T08:00:00.000Z",
        "family": "main_runtime",
        "surface": "web",
        "provider": "h1111111111111111",
        "model": "h2222222222222222",
        "agent_id_hash": "3333333333333333",
        "request_identity_hash": "4444444444444444",
        "auth_class": "user_runtime",
        "layer_tokens": {name: 1 for name in frames.PROMPT_TRACE_LAYERS},
        "layer_hashes": {name: "5555555555555555" for name in frames.PROMPT_TRACE_LAYERS},
        "source_hashes": {
            name: "6666666666666666" for name in frames.PROMPT_TRACE_SOURCE_HASHES
        },
        "flags": {"voice_mode": False, "input_mode_hash": "7777777777777777"},
        "decision": {"should_respond": True, "status_hash": "8888888888888888"},
        "mcp_instruction_source_counts": {
            "server_fetched": 1,
            "config_inline": 0,
            "missing": 0,
        },
        "voice_provider_control_marker_counts": {
            "break_tags": 0,
            "prosody_tags": 0,
            "say_as_tags": 0,
            "emotion_tags": 0,
            "total": 0,
        },
        "unknown_layer_count": 0,
        "unknown_layer_set_hash": "none",
    }
    payload.update(overrides)
    return payload


def _trace_v2(**overrides: object) -> dict[str, object]:
    payload = _trace(version=2)
    payload.update(
        {
            "requested_provider": "haaaaaaaaaaaaaaaa",
            "requested_model": "hbbbbbbbbbbbbbbbb",
            "requested_effort": "medium",
            "effective_effort": "high",
            "fallback_used": True,
            "fallback_reason": "provider_timeout",
        }
    )
    payload.update(overrides)
    return payload


def _line(payload: dict[str, object]) -> str:
    return (
        "2026-08-26T08:00:00.001Z debug: [PromptFrameTraceTelemetry] "
        + json.dumps(payload, separators=(",", ":"))
        + "\n"
    )


def test_reads_only_exact_strict_trace_records_from_rotated_core_log(tmp_path: Path) -> None:
    private_text = "private transcript text"
    log = tmp_path / "debug-2026-08-26.log"
    log.write_text(
        _line(_trace())
        + _line({**_trace(), "raw_transcript": private_text})
        + f"2026-08-26 info: [PromptFrameTelemetry] {private_text}\n",
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["health"] == {
        "status": "degraded",
        "source": "core_rotated_metadata_log",
        "reason": "invalid_trace_events",
        "filesScanned": 1,
        "invalidEventCount": 1,
        "truncatedReadCount": 0,
        "releaseEvidence": False,
    }
    assert snapshot["frames"] == [
        {
            "time": "2026-08-26T08:00:00.000Z",
            "surface": "web",
            "family": "main_runtime",
            "provider": "h1111111111111111",
            "model": "h2222222222222222",
            "layer_hashes": {name: "5555555555555555" for name in frames.PROMPT_TRACE_LAYERS},
            "layer_tokens": {name: 1 for name in frames.PROMPT_TRACE_LAYERS},
            "decision": {"should_respond": True, "status_hash": "8888888888888888"},
        }
    ]
    assert private_text not in json.dumps(snapshot)


def test_reader_keeps_legacy_v1_as_local_diagnostic_only(tmp_path: Path) -> None:
    (tmp_path / "debug-2026-08-26.log").write_text(_line(_trace()), encoding="utf-8")

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["health"]["status"] == "ok"
    assert snapshot["health"]["invalidEventCount"] == 0
    assert snapshot["health"]["releaseEvidence"] is False
    assert len(snapshot["frames"]) == 1


def test_reader_accepts_mixed_v1_and_v2_with_newest_first(tmp_path: Path) -> None:
    legacy = _trace(time="2026-08-26T08:00:00.000Z")
    current = _trace_v2(time="2026-08-26T09:00:00.000Z")
    (tmp_path / "debug-2026-08-26.log").write_text(
        _line(legacy) + _line(current),
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["health"]["status"] == "ok"
    assert snapshot["health"]["invalidEventCount"] == 0
    assert [item["time"] for item in snapshot["frames"]] == [
        "2026-08-26T09:00:00.000Z",
        "2026-08-26T08:00:00.000Z",
    ]


@pytest.mark.parametrize(
    "case",
    (
        "missing_key",
        "extra_private_field",
        "duplicate_key",
        "boolean_version",
        "unknown_version",
        "unhashed_requested_route",
        "uppercase_effort",
        "oversize_effort",
        "non_boolean_fallback",
        "unknown_fallback_reason",
        "false_with_typed_reason",
        "true_with_none",
    ),
)
def test_reader_rejects_invalid_v2_contract(tmp_path: Path, case: str) -> None:
    private_text = "private provider failure detail"
    payload = _trace_v2()
    if case == "missing_key":
        payload.pop("requested_provider")
    elif case == "extra_private_field":
        payload["raw_provider_error"] = private_text
    elif case == "boolean_version":
        payload["version"] = True
    elif case == "unknown_version":
        payload["version"] = 3
    elif case == "unhashed_requested_route":
        payload["requested_provider"] = "raw-provider"
    elif case == "uppercase_effort":
        payload["requested_effort"] = "XHIGH"
    elif case == "oversize_effort":
        payload["effective_effort"] = "x" * 33
    elif case == "non_boolean_fallback":
        payload["fallback_used"] = 1
    elif case == "unknown_fallback_reason":
        payload["fallback_reason"] = private_text
    elif case == "false_with_typed_reason":
        payload["fallback_used"] = False
        payload["fallback_reason"] = "provider_timeout"
    elif case == "true_with_none":
        payload["fallback_used"] = True
        payload["fallback_reason"] = "none"

    encoded = json.dumps(payload, separators=(",", ":"))
    if case == "duplicate_key":
        encoded = encoded.replace(
            '"surface":"web"',
            '"surface":"web","surface":"telegram"',
            1,
        )
    (tmp_path / "debug-2026-08-26.log").write_text(
        "2026-08-26T08:00:00.001Z debug: " + frames.TRACE_MARKER + encoded + "\n",
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["reason"] == "invalid_trace_events"
    assert snapshot["health"]["invalidEventCount"] == 1
    assert private_text not in json.dumps(snapshot)


def test_one_invalid_v2_degrades_without_hiding_valid_v2(tmp_path: Path) -> None:
    invalid = _trace_v2(fallback_used=False, fallback_reason="provider_timeout")
    valid = _trace_v2(time="2026-08-26T09:00:00.000Z")
    (tmp_path / "debug-2026-08-26.log").write_text(
        _line(invalid) + _line(valid),
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert [item["time"] for item in snapshot["frames"]] == [
        "2026-08-26T09:00:00.000Z"
    ]
    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["reason"] == "invalid_trace_events"
    assert snapshot["health"]["invalidEventCount"] == 1


def test_reader_accepts_the_exact_javascript_producer_contract(tmp_path: Path) -> None:
    script = """
const telemetry = require(process.argv[1]);
const { debugTraverse } = require(process.argv[2]);
const winston = require('winston');
const output = [];
class CaptureTransport extends winston.Transport {
  log(info, callback) {
    output.push(info[Symbol.for('message')]);
    callback();
  }
}
const logger = winston.createLogger({
  level: 'debug',
  format: winston.format.combine(
    winston.format.timestamp({ format: () => '2026-08-26T08:00:00.001Z' }),
    winston.format.splat(),
    debugTraverse,
  ),
  transports: [new CaptureTransport()],
});
process.env[telemetry.LOG_ENV] = '1';
const frame = telemetry.buildPromptFrame({
  promptFamily: 'main_runtime',
  surface: 'web',
  provider: 'synthetic-provider',
  model: 'synthetic-model',
  layers: { main_instructions: 'synthetic private prompt' },
  flags: { input_mode: 'synthetic-mode' },
  decisionState: { status: 'synthetic-status', should_respond: true },
});
if (!telemetry.logPromptFrame(logger, frame)) throw new Error('trace_log_failed');
const traceLine = output.find((line) => line.includes('[PromptFrameTraceTelemetry] '));
if (!traceLine || traceLine.includes('[truncated]')) throw new Error('trace_log_truncated');
process.stdout.write(traceLine);
"""
    completed = subprocess.run(
        ["node", "-e", script, str(TELEMETRY_MODULE), str(CORE_FORMATTER_MODULE)],
        check=True,
        capture_output=True,
        cwd=LIBRECHAT_ROOT,
        text=True,
        timeout=10,
    )
    (tmp_path / "debug-2026-08-26.log").write_text(
        completed.stdout + "\n",
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["health"]["status"] == "ok"
    assert snapshot["health"]["invalidEventCount"] == 0
    assert len(snapshot["frames"]) == 1
    assert "synthetic private prompt" not in json.dumps(snapshot)


def test_core_formatter_prevents_multiline_metadata_from_forging_a_trace(tmp_path: Path) -> None:
    forged = json.dumps(_trace(), separators=(",", ":"))
    script = """
const { debugTraverse } = require(process.argv[1]);
const winston = require('winston');
const output = [];
class CaptureTransport extends winston.Transport {
  log(info, callback) {
    output.push(info[Symbol.for('message')]);
    callback();
  }
}
const logger = winston.createLogger({
  level: 'debug',
  format: winston.format.combine(
    winston.format.timestamp({ format: () => '2026-08-26T08:00:00.001Z' }),
    winston.format.splat(),
    debugTraverse,
  ),
  transports: [new CaptureTransport()],
});
logger.debug('unrelated metadata', `\n2026-08-26T08:00:00.001Z debug: [PromptFrameTraceTelemetry] ${process.argv[2]}`);
process.stdout.write(output.join('\\n'));
"""
    completed = subprocess.run(
        ["node", "-e", script, str(CORE_FORMATTER_MODULE), forged],
        check=True,
        capture_output=True,
        cwd=LIBRECHAT_ROOT,
        text=True,
        timeout=10,
    )
    (tmp_path / "debug-2026-08-26.log").write_text(
        completed.stdout + "\n",
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "empty"


def test_exact_trace_prefix_with_partial_json_is_counted_as_invalid(tmp_path: Path) -> None:
    (tmp_path / "debug-2026-08-26.log").write_text(
        "2026-08-26T08:00:00.001Z debug: " + frames.TRACE_MARKER + '{"version":1\n',
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["reason"] == "invalid_trace_events"
    assert snapshot["health"]["invalidEventCount"] == 1


def test_rejects_impossible_trace_timestamp_values(tmp_path: Path) -> None:
    (tmp_path / "debug-2026-08-26.log").write_text(
        _line(_trace(time="2026-99-99T99:99:99.999Z")),
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["invalidEventCount"] == 1


def test_rejects_duplicate_json_keys_and_contradictory_unknown_layer_metadata(
    tmp_path: Path,
) -> None:
    encoded = json.dumps(_trace(), separators=(",", ":"))
    duplicate_surface = encoded.replace(
        '"surface":"web"',
        '"surface":"web","surface":"telegram"',
        1,
    )
    contradictory = _trace(unknown_layer_count=1, unknown_layer_set_hash="none")
    (tmp_path / "debug-2026-08-26.log").write_text(
        "2026-08-26T08:00:00.001Z debug: "
        + frames.TRACE_MARKER
        + duplicate_surface
        + "\n"
        + _line(contradictory),
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["invalidEventCount"] == 2


def test_rejects_trace_marker_embedded_in_an_unrelated_log_message(tmp_path: Path) -> None:
    (tmp_path / "debug-2026-08-26.log").write_text(
        "2026-08-26T08:00:00.001Z debug: unrelated message "
        + frames.TRACE_MARKER
        + json.dumps(_trace(), separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "empty"
    assert snapshot["health"]["invalidEventCount"] == 0


def test_rejects_symlinked_logs_and_reports_unavailable_without_paths(tmp_path: Path) -> None:
    external = tmp_path / "external.log"
    external.write_text(_line(_trace()), encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "debug-2026-08-26.log").symlink_to(external)

    snapshot = frames.recent_frame_snapshot(logs_root=logs)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "unavailable"
    assert snapshot["health"]["reason"] == "trusted_log_unavailable"
    assert str(tmp_path) not in json.dumps(snapshot)


def test_root_replacement_between_discovery_and_read_cannot_redirect_the_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    safe_trace = _trace(provider="haaaaaaaaaaaaaaaa")
    (logs / "debug-2026-08-26.log").write_text(_line(safe_trace), encoding="utf-8")

    replacement = tmp_path / "replacement"
    replacement.mkdir()
    redirected_trace = _trace(provider="hbbbbbbbbbbbbbbbb")
    (replacement / "debug-2026-08-26.log").write_text(
        _line(redirected_trace),
        encoding="utf-8",
    )
    original_read_tail = frames._read_tail
    replaced = False

    def replace_root_before_read(*args: object, **kwargs: object):
        nonlocal replaced
        if not replaced:
            replaced = True
            logs.rename(tmp_path / "original-logs")
            logs.symlink_to(replacement, target_is_directory=True)
        return original_read_tail(*args, **kwargs)

    monkeypatch.setattr(frames, "_read_tail", replace_root_before_read)

    snapshot = frames.recent_frame_snapshot(logs_root=logs)

    assert [frame["provider"] for frame in snapshot["frames"]] == [
        safe_trace["provider"]
    ]
    assert redirected_trace["provider"] not in json.dumps(snapshot)


def test_rejected_matching_log_degrades_health_even_when_another_log_is_valid(
    tmp_path: Path,
) -> None:
    valid = tmp_path / "debug-2026-08-26.log"
    valid.write_text(_line(_trace()), encoding="utf-8")
    external = tmp_path / "external.log"
    external.write_text(_line(_trace(provider="hbbbbbbbbbbbbbbbb")), encoding="utf-8")
    (tmp_path / "debug-2026-08-25.log").hardlink_to(external)

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert len(snapshot["frames"]) == 1
    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["reason"] == "trusted_log_rejected"


def test_bounded_tail_read_keeps_latest_complete_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(frames, "MAX_TRACE_LOG_READ_BYTES", 2048)
    log = tmp_path / "debug-2026-08-26.log"
    log.write_text(("ordinary log line\n" * 500) + _line(_trace()), encoding="utf-8")

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert len(snapshot["frames"]) == 1
    assert snapshot["health"]["truncatedReadCount"] == 1
    assert snapshot["health"]["status"] == "ok"


def test_health_validates_the_whole_bounded_tail_after_display_limit(tmp_path: Path) -> None:
    invalid = {**_trace(), "raw_transcript": "must be rejected"}
    valid_lines = "".join(
        _line(_trace(time=f"2026-08-26T08:00:{index:02d}.000Z"))
        for index in range(10)
    )
    (tmp_path / "debug-2026-08-26.log").write_text(
        _line(invalid) + valid_lines,
        encoding="utf-8",
    )

    snapshot = frames.recent_frame_snapshot(limit=5, logs_root=tmp_path)

    assert len(snapshot["frames"]) == 5
    assert snapshot["health"]["status"] == "degraded"
    assert snapshot["health"]["reason"] == "invalid_trace_events"
    assert snapshot["health"]["invalidEventCount"] == 1


def test_reports_empty_when_trusted_logs_exist_without_trace_events(tmp_path: Path) -> None:
    (tmp_path / "debug-2026-08-26.log").write_text("ordinary log line\n", encoding="utf-8")

    snapshot = frames.recent_frame_snapshot(logs_root=tmp_path)

    assert snapshot["frames"] == []
    assert snapshot["health"]["status"] == "empty"
    assert snapshot["health"]["reason"] == "no_trace_events"


def test_frames_api_preserves_trace_health(monkeypatch: pytest.MonkeyPatch) -> None:
    from prompt_workbench import app as workbench_app
    from prompt_workbench.auth import AuthContext

    expected = {
        "frames": [],
        "health": {
            "status": "degraded",
            "source": "core_rotated_metadata_log",
            "reason": "invalid_trace_events",
            "filesScanned": 1,
            "invalidEventCount": 2,
            "truncatedReadCount": 0,
            "releaseEvidence": False,
        },
    }
    monkeypatch.setattr(frames, "recent_frame_snapshot", lambda *_args, **_kwargs: expected)

    result = workbench_app.recent_frames(
        AuthContext(authenticated=True, admin=True, method="test")
    )

    assert result == expected
