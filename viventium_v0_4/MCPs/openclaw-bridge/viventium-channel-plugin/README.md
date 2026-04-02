# Viventium Channel Bridge Plugin (Gateway v2)

OpenClaw plugin that routes inbound channel messages to LibreChat through the generic Viventium gateway contract.

## Flow

1. `message_received` hook captures channel inbound message metadata.
2. Plugin calls `POST /api/viventium/gateway/chat`.
3. Plugin subscribes to `GET /api/viventium/gateway/stream/:streamId`.
4. Plugin sends text + attachments back with OpenClaw `message` tool actions.

## Required Config

Set via `openclaw.plugin.json` config entry or environment variables.

| Key | Env fallback | Description |
|---|---|---|
| `librechatUrl` | `VIVENTIUM_LIBRECHAT_URL` | LibreChat base URL |
| `gatewaySecret` | `VIVENTIUM_GATEWAY_SECRET` | Shared secret for gateway auth/signature |
| `gatewayHmacSecret` | `VIVENTIUM_GATEWAY_HMAC_SECRET` | Optional HMAC secret override |
| `agentId` | `VIVENTIUM_AGENT_ID` | Optional forced LibreChat agent |
| `requestTimeoutMs` | `VIVENTIUM_GATEWAY_REQUEST_TIMEOUT_MS` | HTTP timeout |

The plugin also needs the local OpenClaw gateway token (for `POST /tools/invoke`):

- `OPENCLAW_GATEWAY_TOKEN` or `gateway.auth.token` in OpenClaw config.

## Notes

- Supports gateway link flow: when LibreChat returns `linkRequired`, plugin sends link URL back to the user.
- Preserves reply/thread context when metadata includes message/thread identifiers.
- Delivers generated files via `sendAttachment` after downloading from gateway file endpoints.
