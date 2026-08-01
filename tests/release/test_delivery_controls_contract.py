from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_ROOT = REPO_ROOT / "viventium_v0_4" / "shared"
JS_MODULE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "deliveryControls.js"
)
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from delivery_controls import (  # noqa: E402
    DELIVERY_CONTROL_VERSION,
    MESSAGE_BREAK_TOKEN,
    SKIP_VOICE_TOKEN,
    parse_delivery_controls,
    strip_delivery_controls_for_preview,
)


def _python_result(text: str) -> dict[str, object]:
    parsed = parse_delivery_controls(text)
    return {
        "contractVersion": parsed.contract_version,
        "cleanText": parsed.clean_text,
        "segments": list(parsed.segments),
        "skipVoice": parsed.skip_voice,
        "skipVoiceCount": parsed.skip_voice_count,
        "messageBreakCount": parsed.message_break_count,
        "mergedBreakCount": parsed.merged_break_count,
    }


def test_python_and_javascript_delivery_control_grammars_stay_in_parity() -> None:
    fixtures = [
        "First.\n{MSG_BREAK}\nSecond.\n{SKIP_VOICE}",
        "One.\n{MSG_BREAK}\nTwo.\n{MSG_BREAK}\nThree.\n{MSG_BREAK}\nFour.",
        "```text\n{MSG_BREAK}\n```\n> {SKIP_VOICE}",
        "A literal {MSG_BREAK} inside prose remains visible.",
        "  { skip_voice }  \nCopy-ready draft.",
    ]
    preview_fixtures = [
        "Draft ready.\n{",
        "Draft ready.\n{skip_",
        "~~~text\n{MSG_\n~~~",
        "> {SKIP_",
    ]
    script = """
const controls = require(process.argv[1]);
const fixtures = JSON.parse(process.argv[2]);
const previewFixtures = JSON.parse(process.argv[3]);
process.stdout.write(JSON.stringify({
  version: controls.DELIVERY_CONTROL_VERSION,
  skip: controls.SKIP_VOICE_TOKEN,
  messageBreak: controls.MESSAGE_BREAK_TOKEN,
  results: fixtures.map((value) => controls.parseDeliveryControls(value)),
  previews: previewFixtures.map((value) => controls.stripDeliveryControlsForPreview(value)),
}));
"""
    completed = subprocess.run(
        [
            "node",
            "-e",
            script,
            str(JS_MODULE),
            json.dumps(fixtures),
            json.dumps(preview_fixtures),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    javascript = json.loads(completed.stdout)

    assert javascript["version"] == DELIVERY_CONTROL_VERSION
    assert javascript["skip"] == SKIP_VOICE_TOKEN == "{SKIP_VOICE}"
    assert javascript["messageBreak"] == MESSAGE_BREAK_TOKEN == "{MSG_BREAK}"
    assert javascript["results"] == [_python_result(value) for value in fixtures]
    assert javascript["previews"] == [
        strip_delivery_controls_for_preview(value) for value in preview_fixtures
    ]
    assert javascript["previews"] == [
        "Draft ready.",
        "Draft ready.",
        "~~~text\n{MSG_\n~~~",
        "> {SKIP_",
    ]


def test_python_parser_matches_javascript_invalid_limit_fallback() -> None:
    source = "One.\n{MSG_BREAK}\nTwo.\n{MSG_BREAK}\nThree."
    assert parse_delivery_controls(source, max_message_breaks="invalid").segments == (
        "One.",
        "Two.",
        "Three.",
    )
    assert parse_delivery_controls(source, max_message_breaks=float("inf")).segments == (
        "One.",
        "Two.",
        "Three.",
    )
