# Telegram-Viventium Bridge

A Telegram bot interface that connects to the Viventium AI agent via LibreChat (default) or LiveKit (legacy).

## Architecture

```
Telegram User → Telegram Bot → LibreChat Agents → Viventium Agent → Tools/MCPs/LLMs
```

All chat messages route through the LibreChat Agents pipeline (same brain as the web UI), which handles model selection, API routing, tools, and background cortices.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- LibreChat API running (for default LibreChat backend)
- Docker + LiveKit (only if using legacy LiveKit backend)

### Setup

1. **Clone and navigate to the directory**:
   ```bash
   cd interfaces/telegram-viventium
   ```

2. **Create configuration file**:
   ```bash
   cp config.env.example config.env
   ```

3. **Edit `config.env`** with your credentials:
   ```bash
   # Required: LibreChat backend + auth
   VIVENTIUM_TELEGRAM_BACKEND=librechat
   VIVENTIUM_LIBRECHAT_ORIGIN=http://localhost:3180
   VIVENTIUM_TELEGRAM_SECRET=your_shared_secret
   VIVENTIUM_TELEGRAM_USER_ID=your_librechat_user_id
   VIVENTIUM_TELEGRAM_AGENT_ID=agent_viventium_main_95aeb3
   
   # Required: Telegram bot token
   BOT_TOKEN=your_telegram_bot_token
   
   # Optional: For voice transcription and image processing
   API_KEY=your_openai_api_key
   ```

4. **Start LiveKit server** (only if `VIVENTIUM_TELEGRAM_BACKEND=livekit`):
   ```bash
   docker run -d --name livekit-server \
     -p 7880:7880 -p 7881:7881 -p 7882:7882/udp \
     livekit/livekit-server --dev --bind 0.0.0.0
   ```

5. **Start Viventium V1 agent** (only if `VIVENTIUM_TELEGRAM_BACKEND=livekit`):
   ```bash
   cd ../../viventium_v0_3_py/viventium_v1/backend/brain/frontal-cortex
   uv run frontal_cortex/agent.py start
   ```

6. **Start Telegram bot**:
   ```bash
   cd interfaces/telegram-viventium
   ./start_telegram_viv.sh
   ```

## Configuration

### Required Environment Variables (LibreChat backend)

- `VIVENTIUM_TELEGRAM_BACKEND=librechat`
- `VIVENTIUM_LIBRECHAT_ORIGIN` - LibreChat API base URL
- `VIVENTIUM_TELEGRAM_SECRET` - Shared secret with LibreChat server
- `VIVENTIUM_TELEGRAM_USER_ID` - LibreChat userId to impersonate
- `VIVENTIUM_TELEGRAM_USER_EMAIL` - Optional fallback (resolve user by email)
- `BOT_TOKEN` - Telegram bot token from @BotFather

### Required Environment Variables (LiveKit backend)

- `VIVENTIUM_TELEGRAM_BACKEND=livekit`
- `LIVEKIT_URL` - LiveKit server WebSocket URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_API_SECRET` - LiveKit API secret
- `LIVEKIT_AGENT_NAME` - Agent dispatch name (defaults to `viventium`, must match the agent worker)
- `BOT_TOKEN` - Telegram bot token from @BotFather

### Optional Environment Variables

- `API_KEY` - OpenAI API key (for Whisper transcription and image processing)
- `ELEVENLABS_API_KEY` - For text-to-speech responses
- `MODEL` - Default model name (for UI display only, Viventium chooses actual model)
- `CUSTOM_MODELS` - Model list for UI (for display only)
- `VIVENTIUM_TELEGRAM_CONNECTION_LOST_MESSAGE` - Message to show on LiveKit disconnect
- `VIVENTIUM_TELEGRAM_RECONNECT_GRACE_S` - Grace period for reconnects before surfacing notice
- `VIVENTIUM_TELEGRAM_HOLDING_TAIL_TIMEOUT_S` - Wait for follow-up after holding/placeholder responses
- `VIVENTIUM_TELEGRAM_TAIL_TIMEOUT_S` - Tail wait after normal responses
- `VIVENTIUM_TELEGRAM_SSE_MAX_RETRIES` - SSE reconnect attempts (LibreChat backend)
- `VIVENTIUM_TELEGRAM_SSE_RETRY_DELAY_S` - Delay between retries (LibreChat backend)
- `VIVENTIUM_TELEGRAM_CHAT_TIMEOUT_S` - POST timeout for /chat (LibreChat backend)
- `VIVENTIUM_TELEGRAM_INCLUDE_CORTEX_INSIGHTS` - Send background insights as separate Telegram messages
- `VIVENTIUM_TELEGRAM_INSIGHT_GRACE_S` - Seconds to wait for background insights after the main response
- `VIVENTIUM_TELEGRAM_INSIGHT_MAX_S` - Maximum seconds to keep insight listener alive
- `VIVENTIUM_TELEGRAM_USER_EMAIL` - Resolve LibreChat user by email if userId is not set

See `config.env.example` for all available options.

## Features

- ✅ **Text Chat**: Send messages via Telegram, receive responses from Viventium
- ✅ **Voice Notes**: Transcribe voice messages and send to Viventium
- ✅ **Image Support**: Send images, extract text, and process with Viventium
- ✅ **Document Processing**: Extract text from PDFs and documents
- ✅ **Multi-user Support**: Each Telegram user gets their own LiveKit room
- ✅ **Proactive Messages**: Receive messages from Viventium even when not actively chatting

## Architecture Notes

### LibreChat Bridge Mode (Default)

This bot uses **LibreChat Agents**, meaning:
- Same system prompts, tools, MCPs, and capabilities as the web UI
- Consistent behavior across Telegram and LibreChat
- No LiveKit dependency for text chat

### LiveKit Bridge Mode (Legacy)

Uses the v1 LiveKit agent and is kept for backward compatibility.

### Residual API Usage

Some features still use direct API calls for preprocessing:
- **Voice Transcription**: Converts voice notes to text (uses OpenAI Whisper)
- **Image/Document Extraction**: Extracts text from files before sending to Viventium

These are legitimate preprocessing steps that happen before data reaches Viventium.

## Troubleshooting

See [docs/TELEGRAM_VIVENTIUM_INTEGRATION.md](docs/TELEGRAM_VIVENTIUM_INTEGRATION.md) for detailed troubleshooting guide.

Common issues:
- **"thinking 💭" forever**: Check if Viventium agent is running
- **No response**: Verify LiveKit server is running and agent is connected
- **Connection errors**: Check `LIVEKIT_URL` matches your LiveKit server

## Testing

Run unit tests:
```bash
cd interfaces/telegram-viventium
uv run pytest tests/ -v
```

## Documentation

- [Integration Guide](docs/TELEGRAM_VIVENTIUM_INTEGRATION.md) - Complete implementation details
- [Performance Validation](docs/PERFORMANCE_VALIDATION.md) - Latency analysis
- [Residual API Usage](docs/RESIDUAL_API_USAGE.md) - What still uses direct APIs
- [Pre-Production Checklist](docs/PRE_PRODUCTION_CHECKLIST.md) - Security and cleanup guide

## License

[Your License Here]

## Contributing

[Contributing Guidelines Here]
