from __future__ import annotations

import json

from app.access_control import AccessControl


def test_bootstrap_pairing_then_lock_to_first_user(tmp_path):
    access = AccessControl(
        paired_users_path=tmp_path / "paired.json",
        pending_pairs_path=tmp_path / "pending.json",
        link_ttl_minutes=15,
        bootstrap_if_empty=True,
    )

    decision = access.authorize_or_begin_pairing(
        telegram_user_id="123",
        telegram_username="primary_user",
        chat_id="999",
        base_url="http://127.0.0.1:8765",
    )
    assert decision.allowed is False
    assert decision.state == "pairing_required"
    assert decision.pairing_url.startswith("http://127.0.0.1:8765/pair/")

    token = decision.pairing_url.rsplit("/", 1)[-1]
    pending = access.get_pending_pair(token)
    assert pending is not None

    paired = access.confirm_pairing(token)
    assert paired is not None
    assert access.is_authorized("123") is True

    denied = access.authorize_or_begin_pairing(
        telegram_user_id="456",
        telegram_username="someone_else",
        chat_id="1000",
        base_url="http://127.0.0.1:8765",
    )
    assert denied.allowed is False
    assert denied.state == "denied"


def test_access_control_migrates_legacy_paired_users(tmp_path):
    legacy_path = tmp_path / "legacy" / "paired_users.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "paired_users": [
                    {
                        "telegram_user_id": "123",
                        "telegram_username": "primary_user",
                        "paired_at": "2026-03-19T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    access = AccessControl(
        paired_users_path=tmp_path / "stable" / "paired_users.json",
        paired_users_migration_sources=(legacy_path,),
        pending_pairs_path=tmp_path / "stable" / "pending.json",
        link_ttl_minutes=15,
        bootstrap_if_empty=True,
    )

    assert access.is_authorized("123") is True
    assert access.list_paired_users()[0]["telegram_username"] == "primary_user"
