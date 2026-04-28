# Environment and Config

## Canonical User Config

The new canonical user-facing config is:

```text
~/Library/Application Support/Viventium/config.yaml
```

This file is written by:

```bash
bin/viventium install
```

Secrets should live in macOS Keychain and be referenced from `config.yaml` using `keychain://...`.

For advanced local setups that still depend on env-based LibreChat provider wiring
(for example Azure-backed local models), use `runtime.extra_env` in `config.yaml`.
Telegram local Bot API settings now have canonical config fields under
`integrations.telegram` and should not require `runtime.extra_env`.
That same canonical block now owns:
- `max_file_size_bytes`
- explicit external Bot API URLs (`bot_api_origin` / base URLs)
- the Viventium-managed same-Mac local Bot API path under `local_bot_api`

## Generated Runtime Files

The compiler renders:

- `runtime.env`
- `runtime.local.env`
- `librechat.yaml`
- service-specific env files

under:

```text
~/Library/Application Support/Viventium/runtime/
```

## Compatibility Inputs

For backwards compatibility, the legacy launcher still supports:

- root `.env`
- root `.env.local`
- root `.env.private-overlay.local`
Those files are compatibility paths only. They are not the target public install surface.
When present in advanced local runs, the compiler may import a vetted allowlist of provider values
to preserve local parity with older setups.

## Required Inputs

- one primary LLM auth mode
- `GROQ_API_KEY` for activation detection

## Common Optional Inputs

- secondary LLM provider
- `runtime.auth.allow_registration`
- `runtime.auth.allow_password_reset`
- voice provider settings
- `voice.wing_mode.default_enabled`
- `voice.wing_mode.prompt`
- Telegram bot token
- optional Telegram local Bot API server origin/base URLs for large-media downloads
- optional Viventium-managed local Telegram Bot API binary/host/port/api credentials
- canonical Telegram max media size policy for downloads/transcription
- Google Workspace auth material
- Microsoft 365 auth material
- Skyvern settings

## Advanced Reference

- `config.schema.yaml`
- `config.minimal.example.yaml`
- `config.full.example.yaml`
- `.env.example`
- `librechat.yaml.example`

## Remote Access Modes

For local installs that need phone/tablet access to the modern voice surface, the canonical config
also supports:

- `runtime.network.public_client_origin`
- `runtime.network.public_api_origin`
- `runtime.network.public_playground_origin`
- `runtime.network.public_livekit_url`
- `runtime.network.livekit_node_ip`
- `runtime.network.remote_call_mode`

Recommended local default:

- `remote_call_mode: disabled`

With `disabled`, local installs stay honest by default:

- same-device browser voice uses `localhost`
- raw `http://LAN_IP` browser origins are not treated as supported microphone/WebRTC acceptance
  surfaces
- remote-device/browser voice only becomes supported after the operator deliberately configures a
  real public `HTTPS/WSS` topology
- `cloudflare_quick_tunnel` remains an explicit experiment, not the default install story

Supported private-mesh modes:

- `tailscale_tailnet_https`
  - no manual public origins required
  - Viventium auto-publishes tailnet-only HTTPS URLs on this node's `*.ts.net` hostname
  - `LIVEKIT_NODE_IP` is derived automatically from the node's Tailscale IPv4
- `netbird_selfhosted_mesh`
  - requires explicit `public_client_origin` and `public_api_origin`
  - when voice is enabled, also requires `public_playground_origin` and `public_livekit_url`
  - `livekit_node_ip` is the explicit mesh IP override when the configured LiveKit hostname does not
    already resolve to this Mac's private mesh address during startup

Supported public-browser mode:

- `public_https_edge` / `custom_domain`
  - use this when you want Viventium and the modern playground reachable from any browser anywhere
  - requires a real public `HTTPS/WSS` path for the web app, API, playground, and LiveKit media
  - usually means your own domain plus an inbound public path to this Mac
  - if the router supports UPnP/NAT-PMP, Viventium can request and renew the needed public port
    mappings automatically while the runtime stays up
  - if the router does not support that, use manual port forwarding instead
  - if you only need your own phone or laptop and can install Tailscale, `tailscale_tailnet_https`
    is simpler than a public-edge deployment

What a normal self-hosted user should do:

- if you do not need remote access yet, leave `remote_call_mode: disabled`
- if you want access from your own devices outside the house, prefer `tailscale_tailnet_https`
- if you want access from any browser anywhere, use `custom_domain`

Runtime note:

- browser-facing public origins are separate from the local LibreChat frontend dev proxy target
- secure-origin browser URLs must not be fed back into the local Vite proxy as the backend target

See `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md` for the supported tunnel
and reverse-proxy patterns.

User guidance:

- Start from `config.minimal.example.yaml` or `config.full.example.yaml`.
- Use `bin/viventium configure` to switch modes later without hand-editing YAML.
- Keep `remote_call_mode: disabled` unless you explicitly need remote access.
- Choose `tailscale_tailnet_https` for your own enrolled devices.
- Choose `custom_domain` / `public_https_edge` only when you need public browser access.
- After startup, run `bin/viventium status` to see the exact live outside URL that Viventium
  published for this machine.

## Browser Auth Controls

The canonical config also supports browser account posture for self-hosted installs:

- `runtime.auth.allow_registration`
- `runtime.auth.allow_password_reset`

Defaults:

- `allow_registration: true`
- `allow_password_reset: false`

Wizard behavior:

- when remote access is enabled through `bin/viventium configure`, the wizard also asks whether
  browser sign-up and browser password reset should stay enabled for that install

Recommended operator posture:

- keep registration open only while you still need people to create accounts in the browser
- close registration once the real accounts already exist
- keep password reset off unless you have real email delivery configured
- for a one-time operator-issued reset link without opening the public reset endpoint, run:
  - `bin/viventium password-reset-link <email>`

Why password reset stays off by default:

- LibreChat returns reset links directly when email delivery is not configured
- that is acceptable for a local operator tool but not for a public browser endpoint

## Wing Mode

The canonical config also supports a passive companion voice behavior:

- `voice.wing_mode.default_enabled`
- `voice.wing_mode.prompt`

Legacy alias still accepted for compatibility:

- `voice.shadow_mode.default_enabled`
- `voice.shadow_mode.prompt`

These generate:

- `VIVENTIUM_WING_MODE_DEFAULT_ENABLED`
- `VIVENTIUM_WING_MODE_PROMPT`
- `VIVENTIUM_SHADOW_MODE_DEFAULT_ENABLED`
- `VIVENTIUM_SHADOW_MODE_PROMPT`

Runtime behavior:

- new live call sessions seed the persisted compatibility flag `shadowModeEnabled` from `voice.wing_mode.default_enabled`
- the modern playground exposes a single Wing Mode icon toggle to change it per call
- the persisted call-session state is the runtime source of truth for whether Wing Mode is on; do not invent separate browser-only ownership of that flag
- `voice.wing_mode.prompt` / `VIVENTIUM_WING_MODE_PROMPT` is an override, not a requirement; if omitted, runtime still injects the built-in default Wing Mode contract
- when Wing Mode is on, the injected voice-call prompt tells the selected agent to ignore TV, podcasts, songs, ads, meeting chatter, and overheard speech unless the user is clearly addressing Viventium directly
- if the model is unsure the speech is meant for Viventium, it must output exactly `{NTA}`

## Voice TTS Selection

For live voice calls, `voice.tts_provider` controls the server-side voice-gateway TTS selection.

- `browser` now keeps the user-facing config simple and resolves to a stable hosted gateway TTS in local mode
- `local_automatic` is the explicit opt-in for the local MLX Chatterbox path on supported Apple Silicon Macs
- `local_chatterbox_turbo_mlx_8bit` remains an advanced direct override rather than a hidden default

For Cartesia, `voice.tts` may declare the public Sonic-3 call options that compile into
`runtime.env`:

```yaml
voice:
  tts_provider: cartesia
  tts:
    model_id: sonic-3
    voice:
      mode: id
      id: 6ccbfb76-1fc6-48f7-b71d-91ac6298247b
```

If omitted, the compiler and launcher use `Cartesia-Version=2026-03-01`, `model_id=sonic-3`,
and the Megan voice id (`e8e5fffb-252c-436d-b842-8879b84445b6`). The modern playground exposes
Cartesia as a Sonic-3-only provider and lets users choose named voice personas such as Megan and
Lyra, without showing raw voice IDs in the picker.

This keeps the canonical config aligned with `01_Key_Principles.md`: no hidden mode switches, no misleading config values, and reliability-first defaults.

Live response timing contract:

- live calls stay end-of-turn, not talk-over-the-user; the user turn must finalize before response generation starts
- once generation starts, LibreChat streams response deltas and the voice gateway begins TTS from streamed chunks before the full assistant answer is complete
- the system must not regress to "wait for the entire LLM answer, then begin speaking" unless intentionally redesigned and documented
