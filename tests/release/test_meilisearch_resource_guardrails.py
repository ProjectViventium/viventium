from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MONGO_MEILI = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "packages"
    / "data-schemas"
    / "src"
    / "models"
    / "plugins"
    / "mongoMeili.ts"
)
INDEX_SYNC = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "api" / "db" / "indexSync.js"
LOCAL_SEARCH_SYNC = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-sync-local-search.js"
)


def test_mongo_meili_does_not_enqueue_filterable_settings_update_on_every_load() -> None:
    source = MONGO_MEILI.read_text(encoding="utf-8")

    assert "Feature: Meili settings churn guard." in source
    assert "Feature: Stable Meili document ids." in source
    assert "ensureUserFilterableAttribute" in source
    assert "already has 'user' configured as filterable" in source
    assert "const meiliDocumentIdField = '_meiliId';" in source
    assert "object[meiliDocumentIdField] = getMeiliDocumentId(object[primaryKey]);" in source
    assert "Meilisearch task ${task.taskUid} failed" in source
    assert "filterableAttributes: [...current, 'user']" in source
    assert "filterableAttributes: ['user']" not in source


def test_librechat_background_index_sync_gates_on_recent_failed_meili_tasks() -> None:
    source = INDEX_SYNC.read_text(encoding="utf-8")

    assert "Feature: Meili task-health gate." in source
    assert "assertMeiliTaskHealth(client)" in source
    assert "ensureSearchIndexSchemas(client)" in source
    assert "client.getTasks({ statuses: ['failed'], limit: lookback })" in source
    assert "expectedMeiliPrimaryKey = '_meiliId'" in source
    assert "refusing to enqueue more local search sync work" in source
    assert "filterableAttributes: nextSettings.filterableAttributes" in source
    assert "filterableAttributes: ['user']" not in source


def test_startup_local_search_backfill_gates_on_recent_failed_meili_tasks() -> None:
    source = LOCAL_SEARCH_SYNC.read_text(encoding="utf-8")

    assert "assertMeiliTaskHealth(client)" in source
    assert "ensureSearchIndexSchemas(client)" in source
    assert "client.getTasks({ statuses: ['failed'], limit: lookback })" in source
    assert "expectedMeiliPrimaryKey = '_meiliId'" in source
    assert "refusing to enqueue more local search sync work" in source
