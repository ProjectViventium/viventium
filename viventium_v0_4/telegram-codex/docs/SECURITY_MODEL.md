# Security Model

## What the current design guarantees

- The pairing page is served only on `127.0.0.1` by default.
- Only the first locally approved Telegram user id is authorized.
- All later unauthorized Telegram user ids are rejected.
- Runtime state is local and untracked.
- The allowlist is stored in a durable machine-local path scoped to the bot identity, so restarts and runtime-profile changes do not silently drop the pairing.

## What the design does not guarantee

- It cannot distinguish Telegram Desktop vs Telegram Web vs Telegram Mobile for the same Telegram account.
- It cannot cryptographically prove that every later message came from one exact physical laptop.

That limitation comes from Telegram Bot API identity signals, not from the local implementation.

## Recommended operating mode

- Pair only a Telegram account you control
- Keep the allowlist to one user id unless you have a reason not to
- Keep the bot in private chats only
- Test only against bots or safe chats
- Prefer `workspace-write` unless you explicitly need broader filesystem power
- If you rotate the bot token or change the bot username, expect a new bot-scoped pairing file unless you intentionally migrate it
