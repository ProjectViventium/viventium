from __future__ import annotations

from aiohttp import web

from app.access_control import AccessControl


def _is_local_request(request: web.Request) -> bool:
    remote = request.remote or ""
    return remote in {"127.0.0.1", "::1", "localhost"}


class PairingServer:
    def __init__(
        self,
        *,
        access_control: AccessControl,
        host: str,
        port: int,
        on_pair_confirmed=None,
    ) -> None:
        self._access_control = access_control
        self._host = host
        self._port = port
        self._on_pair_confirmed = on_pair_confirmed
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/health", self._health)
        app.router.add_get("/pair/{token}", self._show_pairing_page)
        app.router.add_post("/pair/{token}/confirm", self._confirm_pairing)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _show_pairing_page(self, request: web.Request) -> web.Response:
        if not _is_local_request(request):
            return web.Response(status=403, text="Local access only.")
        token = request.match_info.get("token", "")
        pending = self._access_control.get_pending_pair(token)
        if pending is None:
            return web.Response(status=404, text=self._render_result("Link expired", "This pairing link is invalid or expired."))
        body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Pair telegram_codex</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; line-height: 1.5; }}
      .card {{ max-width: 44rem; border: 1px solid #ddd; border-radius: 12px; padding: 1.25rem; }}
      button {{ padding: 0.75rem 1rem; border-radius: 8px; border: none; background: #111; color: #fff; cursor: pointer; }}
      code {{ background: #f4f4f4; padding: 0.125rem 0.35rem; border-radius: 6px; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Approve Telegram account</h2>
      <p>This page is only served on <code>127.0.0.1</code>.</p>
      <p>Approve <strong>{pending.telegram_username or pending.telegram_user_id}</strong> for this laptop.</p>
      <p>Once approved, this bot will accept messages only from that Telegram user id.</p>
      <form method="post" action="/pair/{pending.token}/confirm">
        <button type="submit">Approve This Telegram Account</button>
      </form>
    </div>
  </body>
</html>"""
        return web.Response(text=body, content_type="text/html")

    async def _confirm_pairing(self, request: web.Request) -> web.Response:
        if not _is_local_request(request):
            return web.Response(status=403, text="Local access only.")
        token = request.match_info.get("token", "")
        paired = self._access_control.confirm_pairing(token)
        if paired is None:
            return web.Response(status=404, text=self._render_result("Link expired", "This pairing link is invalid or expired."))
        if self._on_pair_confirmed is not None:
            await self._on_pair_confirmed(paired)
        return web.Response(
            text=self._render_result(
                "Pairing complete",
                "This laptop is now paired to the approved Telegram account. You can return to Telegram.",
            ),
            content_type="text/html",
        )

    @staticmethod
    def _render_result(title: str, message: str) -> str:
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
  </head>
  <body>
    <h2>{title}</h2>
    <p>{message}</p>
  </body>
</html>"""

