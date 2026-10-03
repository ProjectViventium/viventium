# === VIVENTIUM START ===
"""Compatibility import for the shared Voice/Telegram Silero configuration."""
from pathlib import Path
import sys

_shared = Path(__file__).resolve().parent.parent
if str(_shared) not in sys.path:
    sys.path.insert(0, str(_shared))

# Load by the existing shared package name to avoid importing this shim again.
from shared.silero_vad_config import *  # noqa: F403
from shared.silero_vad_config import __all__
# === VIVENTIUM END ===
