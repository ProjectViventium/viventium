from __future__ import annotations

from app.session_store import SessionStore


def test_session_store_sets_project_and_thread(tmp_path):
    store = SessionStore(tmp_path / "sessions.json", "viventium_core")
    initial = store.get(123)
    assert initial.project_alias == "viventium_core"
    assert initial.thread_id is None

    updated = store.set_project(123, "private_companion_repo", clear_thread=True)
    assert updated.project_alias == "private_companion_repo"
    assert updated.thread_id is None

    resumed = store.set_thread(123, "thread-1")
    assert resumed.thread_id == "thread-1"
