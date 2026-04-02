from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from app.access_control import AccessControl
from app.codex_cli_bridge import CodexCliBridge
from app.config import load_config
from app.pairing_server import PairingServer
from app.project_registry import ProjectRegistry
from app.session_store import SessionStore
from app.telegram_bot import TelegramCodexBot
from app.transcribe_local import LocalWhisperTranscriber


def configure_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "telegram_codex.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


async def _run() -> None:
    config = load_config()
    configure_logging(config.runtime.logs_dir)

    project_registry = ProjectRegistry.from_file(config.runtime.project_registry_path)
    access_control = AccessControl(
        paired_users_path=config.runtime.paired_users_path,
        paired_users_migration_sources=config.runtime.paired_users_migration_sources,
        pending_pairs_path=config.runtime.pending_pairs_path,
        link_ttl_minutes=config.pairing.link_ttl_minutes,
        bootstrap_if_empty=config.pairing.bootstrap_if_empty,
    )
    session_store = SessionStore(config.runtime.sessions_path, project_registry.default_alias)
    codex_bridge = CodexCliBridge(config.codex)
    transcriber = LocalWhisperTranscriber(config.transcription)
    bot = TelegramCodexBot(
        token=config.bot.token,
        bot_username=config.bot.username,
        private_chat_only=config.bot.private_chat_only,
        pairing_base_url=config.pairing.base_url,
        access_control=access_control,
        session_store=session_store,
        project_registry=project_registry,
        codex_bridge=codex_bridge,
        transcriber=transcriber,
    )
    pairing_server = PairingServer(
        access_control=access_control,
        host=config.pairing.host,
        port=config.pairing.port,
        on_pair_confirmed=bot.notify_pair_confirmed,
    )

    await pairing_server.start()
    await bot.start()

    try:
        await asyncio.Event().wait()
    finally:
        with contextlib.suppress(Exception):
            await bot.stop()
        with contextlib.suppress(Exception):
            await pairing_server.stop()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
