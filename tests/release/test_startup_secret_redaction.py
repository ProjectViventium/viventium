from pathlib import Path


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
