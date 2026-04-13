from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OVERRIDE_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "rag_api_overrides"
    / "app"
    / "routes"
    / "document_routes.py"
)


def test_rag_override_uses_config_compatibility_fallback_for_embedding_chunk_size() -> None:
    source = OVERRIDE_PATH.read_text(encoding="utf-8")
    import_block = source.split("from app.config import (", 1)[1].split(")\n", 1)[0]

    assert "import app.config as rag_config" in source
    assert "EMBEDDINGS_CHUNK_SIZE = getattr(" in source
    assert '"EMBEDDINGS_CHUNK_SIZE"' in source
    assert '"EMBEDDING_BATCH_SIZE"' in source
    assert "EMBEDDINGS_CHUNK_SIZE" not in import_block
