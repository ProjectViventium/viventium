from pathlib import Path
import json
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def test_startup_output_never_prints_secret_values_or_prefixes() -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")

    forbidden = (
        "${LIVEKIT_API_KEY}${NC}",
        "_secret_mask=",
        "${_secret_mask}${NC}",
        "${OPENAI_API_KEY:0:",
        "${ELEVEN_API_KEY_FINAL:0:",
        "${XAI_API_KEY:0:",
        "${CARTESIA_API_KEY:0:",
        "${ELEVEN_API_KEY:0:",
    )
    for fragment in forbidden:
        assert fragment not in source

    for label in (
        "LiveKit API Key",
        "Call Secret",
        "OpenAI API Key",
        "ElevenLabs API Key",
        "xAI API Key",
        "Cartesia API Key",
    ):
        assert f"{label}:" in source
        assert "Configured" in source


def test_voice_worker_receives_connection_settings_without_secret_arguments(tmp_path: Path) -> None:
    source = START_SCRIPT.read_text(encoding="utf-8")
    voice_start = source[source.index("# Voice Gateway worker") : source.index("# Wait for services to start")]
    start = voice_start.index('exec "$voice_python" worker.py start \\\n')
    command = voice_start[start : voice_start.index("\n      )", start)]
    (tmp_path / "worker.py").write_text(
        "import json, os, sys\n"
        "print(json.dumps({'args': sys.argv[1:], 'connection': "
        "{name: os.environ.get(name) for name in "
        "('LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET')}}))\n",
        encoding="utf-8",
    )
    connection = {
        "LIVEKIT_URL": "ws://synthetic.invalid",
        "LIVEKIT_API_KEY": "synthetic-key",
        "LIVEKIT_API_SECRET": "synthetic-secret",
    }
    result = subprocess.run(
        ["bash", "-c", command], cwd=tmp_path,
        env={**os.environ, **connection, "voice_python": sys.executable,
             "VIVENTIUM_VOICE_GATEWAY_LOG_LEVEL": "info"},
        check=True, capture_output=True, text=True,
    )
    received = json.loads(result.stdout)
    assert received["args"] == ["start", "--log-level=info"]
    assert received["connection"] == connection
