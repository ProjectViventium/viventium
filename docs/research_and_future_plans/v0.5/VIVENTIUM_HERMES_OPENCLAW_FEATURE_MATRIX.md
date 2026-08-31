# Viventium vs Hermes vs OpenClaw

**Status:** UNAUDITED RESEARCH INVENTORY — not product truth, requirements, acceptance evidence,
or a release scorecard.

**As of:** 2026-08-29. This draft has no pinned Hermes or OpenClaw source revision and no
cell-level evidence. Treat every cell as an author hypothesis that requires fresh verification
against the named project's official source and version before it informs design or comparison.
Viventium's current behavior and commitments come only from the owning requirement documents and
QA catalogs, not this matrix.

**Legend:** `✅` means “the draft author believed this capability existed or was intended”; `❌`
means “the draft author believed it was absent or not intended.” Neither symbol means verified.
“Viventium at full” and “Viventium upcoming polished installer” are aspirational planning views,
not statements about the installed or released product. Until sources, revisions, and evidence are
added, this file is useful only as a research-question inventory.

| Feature / option | Viventium at full | Viventium upcoming polished installer | Hermes | OpenClaw |
| --- | :---: | :---: | :---: | :---: |
| Install — Native macOS app | ✅ | ✅ | ✅ | ✅ |
| Install — Native Windows app | ❌ | ❌ | ✅ | ✅ |
| Install — Native Linux app | ❌ | ❌ | ✅ | ✅ |
| Install — Public one-click desktop installer | ❌ | ✅ | ✅ | ✅ |
| Install — Signed and notarized macOS DMG | ❌ | ✅ | ✅ | ✅ |
| Install — Apple Silicon support | ✅ | ✅ | ✅ | ✅ |
| Install — Apple Silicon-first release | ❌ | ✅ | ❌ | ❌ |
| Install — One-line terminal installer | ✅ | ❌ | ✅ | ✅ |
| Install — No terminal needed | ❌ | ✅ | ✅ | ✅ |
| Install — Command-line app | ✅ | ✅ | ✅ | ✅ |
| Install — Full-screen terminal app | ❌ | ❌ | ✅ | ✅ |
| Install — Browser control app | ✅ | ✅ | ✅ | ✅ |
| Install — Native desktop chat window | ❌ | ❌ | ✅ | ✅ |
| Install — Menu bar or system tray control | ✅ | ✅ | ✅ | ✅ |
| Install — Global quick-chat shortcut | ❌ | ❌ | ✅ | ✅ |
| Install — Built-in setup and repair agent | ❌ | ❌ | ❌ | ✅ |
| Install — Desktop can connect without a local runtime | ❌ | ❌ | ✅ | ✅ |
| Install — Guided first-run setup | ✅ | ✅ | ✅ | ✅ |
| Install — First answer without editing a config file | ❌ | ✅ | ✅ | ✅ |
| Install — First answer without Docker | ✅ | ✅ | ✅ | ✅ |
| Install — First answer without developer tools | ❌ | ✅ | ✅ | ✅ |
| Install — First answer without a source build | ❌ | ✅ | ✅ | ✅ |
| Install — First answer without a package manager | ❌ | ✅ | ✅ | ✅ |
| Install — Provider connection during setup | ✅ | ✅ | ✅ | ✅ |
| Install — Subscription-account sign-in | ✅ | ✅ | ✅ | ✅ |
| Install — Advanced API-key setup | ✅ | ✅ | ✅ | ✅ |
| Install — Advanced custom-endpoint setup | ✅ | ✅ | ✅ | ✅ |
| Install — Local-model setup | ✅ | ✅ | ✅ | ✅ |
| Install — Provider and model picker | ✅ | ✅ | ✅ | ✅ |
| Install — First-party free product plan | ❌ | ❌ | ✅ | ❌ |
| Install — First-party paid product plans | ❌ | ❌ | ✅ | ❌ |
| Install — Integrated credits and billing | ❌ | ❌ | ✅ | ❌ |
| Install — One-click managed cloud deployment | ❌ | ❌ | ✅ | ❌ |
| Install — Self-hosted server deployment | ✅ | ❌ | ✅ | ✅ |
| Install — Always-on local service | ✅ | ✅ | ✅ | ✅ |
| Install — Start at login | ✅ | ✅ | ✅ | ✅ |
| Install — Background service supervision | ✅ | ✅ | ✅ | ✅ |
| Install — Offline-built runtime payload | ❌ | ✅ | ❌ | ❌ |
| Install — Exact version-pinned runtime payload | ✅ | ✅ | ❌ | ✅ |
| Install — One version lock across all components | ❌ | ✅ | ❌ | ❌ |
| Install — One user-facing lifecycle owner | ❌ | ✅ | ✅ | ✅ |
| Install — Typed component health graph | ❌ | ✅ | ❌ | ❌ |
| Install — Restart only the failed component | ❌ | ✅ | ❌ | ❌ |
| Install — Setup progress UI | ✅ | ✅ | ✅ | ✅ |
| Install — Setup retry UI | ✅ | ✅ | ✅ | ✅ |
| Install — Live readiness states | ✅ | ✅ | ✅ | ✅ |
| Install — Health and status command | ✅ | ✅ | ✅ | ✅ |
| Install — Doctor command | ✅ | ✅ | ✅ | ✅ |
| Install — Guided repair | ✅ | ✅ | ✅ | ✅ |
| Install — Diagnostics and logs | ✅ | ✅ | ✅ | ✅ |
| Install — In-app update | ✅ | ✅ | ✅ | ✅ |
| Install — Command-line update | ✅ | ✅ | ✅ | ✅ |
| Install — Automatic update checks | ✅ | ✅ | ✅ | ✅ |
| Install — Stable, beta, and development update channels | ❌ | ❌ | ❌ | ✅ |
| Install — Update preview or changelog | ✅ | ✅ | ✅ | ✅ |
| Install — Automatic pre-update backup | ✅ | ✅ | ✅ | ❌ |
| Install — Transactional update | ✅ | ✅ | ✅ | ❌ |
| Install — Failed-update rollback | ✅ | ✅ | ✅ | ✅ |
| Install — User-data backup | ✅ | ✅ | ✅ | ✅ |
| Install — Full user-data restore | ❌ | ✅ | ✅ | ✅ |
| Install — Existing-install migration | ❌ | ✅ | ✅ | ✅ |
| Install — Preserve-data uninstall | ✅ | ✅ | ✅ | ✅ |
| Install — Import from OpenClaw | ❌ | ❌ | ✅ | ❌ |
| Install — Import from Hermes | ❌ | ❌ | ❌ | ✅ |
| Install — Import Claude Code or Codex memory | ❌ | ❌ | ❌ | ✅ |
| Install — Component license notices | ✅ | ✅ | ✅ | ✅ |
| Install — Software bill of materials | ❌ | ✅ | ❌ | ❌ |
| Install — Signed release manifest | ❌ | ✅ | ❌ | ❌ |
| Install — Installed-build identity check | ✅ | ✅ | ✅ | ✅ |
| Install — Version-skew detection | ✅ | ✅ | ✅ | ✅ |
| Chat — Branded chat app | ✅ | ✅ | ✅ | ✅ |
| Chat — Persistent conversations | ✅ | ✅ | ✅ | ✅ |
| Chat — Conversation resume after restart | ✅ | ✅ | ✅ | ✅ |
| Chat — Streaming answers | ✅ | ✅ | ✅ | ✅ |
| Chat — Live tool activity | ✅ | ✅ | ✅ | ✅ |
| Chat — Structured tool rows | ✅ | ✅ | ✅ | ✅ |
| Chat — Stop a running answer | ✅ | ✅ | ✅ | ✅ |
| Chat — Redirect a running answer | ✅ | ✅ | ✅ | ✅ |
| Chat — Edit and resend a message | ✅ | ✅ | ❌ | ❌ |
| Chat — Regenerate an answer | ✅ | ✅ | ❌ | ❌ |
| Chat — Branch a conversation | ✅ | ✅ | ❌ | ✅ |
| Chat — Multiple simultaneous conversations | ✅ | ✅ | ✅ | ✅ |
| Chat — Rename a conversation | ✅ | ✅ | ✅ | ✅ |
| Chat — Archive a conversation | ✅ | ✅ | ✅ | ✅ |
| Chat — Pin a conversation | ✅ | ✅ | ✅ | ✅ |
| Chat — Group conversations | ❌ | ❌ | ❌ | ✅ |
| Chat — Mark conversations read or unread | ❌ | ❌ | ✅ | ✅ |
| Chat — Persistent multi-pane chat layout | ❌ | ❌ | ✅ | ✅ |
| Chat — Upload files | ✅ | ✅ | ✅ | ✅ |
| Chat — Send and receive images | ✅ | ✅ | ✅ | ✅ |
| Chat — Send and receive audio | ✅ | ✅ | ✅ | ✅ |
| Chat — Send and receive video | ✅ | ✅ | ✅ | ✅ |
| Chat — Send and receive documents | ✅ | ✅ | ✅ | ✅ |
| Chat — Multi-file messages | ✅ | ✅ | ✅ | ✅ |
| Chat — Generated artifact previews | ✅ | ✅ | ✅ | ✅ |
| Chat — Side-by-side artifact preview | ✅ | ✅ | ✅ | ✅ |
| Chat — File browser | ✅ | ✅ | ✅ | ✅ |
| Chat — Edit project files in the chat app | ❌ | ❌ | ✅ | ✅ |
| Chat — File-edit conflict detection | ❌ | ❌ | ❌ | ✅ |
| Chat — Embedded remote-browser panel | ❌ | ❌ | ✅ | ✅ |
| Chat — Embedded terminal panel | ❌ | ❌ | ✅ | ✅ |
| Chat — Agent-generated dashboard widgets | ❌ | ❌ | ✅ | ✅ |
| Chat — A2UI interactive canvas | ❌ | ❌ | ❌ | ✅ |
| Chat — Live run-progress rail | ✅ | ✅ | ✅ | ✅ |
| Chat — Read-only companion thread during a run | ❌ | ❌ | ❌ | ✅ |
| Chat — Code interpreter | ✅ | ✅ | ✅ | ✅ |
| Chat — Search citations | ✅ | ✅ | ✅ | ✅ |
| Chat — Message bookmarks | ✅ | ✅ | ❌ | ❌ |
| Chat — Saved prompt library | ✅ | ✅ | ❌ | ❌ |
| Chat — Prompt templates | ✅ | ✅ | ✅ | ✅ |
| Chat — Conversation search | ✅ | ✅ | ✅ | ✅ |
| Chat — Full-text message search | ✅ | ✅ | ✅ | ✅ |
| Chat — Private scoped search index | ✅ | ✅ | ✅ | ✅ |
| Chat — Search-index refresh and rebuild | ✅ | ✅ | ✅ | ✅ |
| Chat — Search-result jump to message | ✅ | ✅ | ✅ | ✅ |
| Chat — Model switching | ✅ | ✅ | ✅ | ✅ |
| Chat — Provider fallback | ✅ | ✅ | ✅ | ✅ |
| Chat — Visible model and provider identity | ✅ | ✅ | ✅ | ✅ |
| Chat — Token and usage display | ✅ | ✅ | ✅ | ✅ |
| Chat — Cost or credit display | ✅ | ✅ | ✅ | ✅ |
| Chat — Provider failure states | ✅ | ✅ | ✅ | ✅ |
| Chat — Draft preserved through sign-in | ✅ | ✅ | ✅ | ✅ |
| Chat — Draft preserved through failure and retry | ✅ | ✅ | ❌ | ❌ |
| Chat — Cross-surface conversation continuity | ✅ | ✅ | ✅ | ✅ |
| Chat — Same Main identity on every surface | ✅ | ✅ | ❌ | ✅ |
| Chat — Multi-user local accounts | ✅ | ✅ | ❌ | ❌ |
| Chat — Local sign-up and sign-in | ✅ | ✅ | ❌ | ❌ |
| Chat — Password reset | ✅ | ✅ | ❌ | ❌ |
| Chat — Role-based user access | ✅ | ✅ | ✅ | ✅ |
| Chat — Intentional no-response | ✅ | ✅ | ✅ | ✅ |
| Chat — Listen-only conversation mode | ✅ | ✅ | ❌ | ❌ |
| Chat — Agent can follow up later | ✅ | ✅ | ✅ | ✅ |
| Chat — Background completion notification | ✅ | ✅ | ✅ | ✅ |
| Providers — OpenAI API | ✅ | ✅ | ✅ | ✅ |
| Providers — OpenAI Codex subscription sign-in | ✅ | ✅ | ✅ | ✅ |
| Providers — Anthropic API | ✅ | ✅ | ✅ | ✅ |
| Providers — Claude subscription sign-in | ✅ | ❌ | ✅ | ✅ |
| Providers — Google Gemini | ✅ | ✅ | ✅ | ✅ |
| Providers — xAI | ✅ | ✅ | ✅ | ✅ |
| Providers — OpenRouter | ✅ | ✅ | ✅ | ✅ |
| Providers — DeepSeek | ✅ | ✅ | ✅ | ✅ |
| Providers — Groq | ✅ | ✅ | ✅ | ✅ |
| Providers — Mistral | ✅ | ✅ | ✅ | ✅ |
| Providers — Azure OpenAI or Azure Foundry | ✅ | ✅ | ✅ | ✅ |
| Providers — Amazon Bedrock | ✅ | ✅ | ✅ | ✅ |
| Providers — Google Vertex AI | ✅ | ✅ | ✅ | ✅ |
| Providers — Ollama | ✅ | ✅ | ✅ | ✅ |
| Providers — LM Studio | ✅ | ✅ | ✅ | ✅ |
| Providers — vLLM or SGLang | ✅ | ✅ | ✅ | ✅ |
| Providers — Any OpenAI-compatible endpoint | ✅ | ✅ | ✅ | ✅ |
| Providers — Multiple saved provider accounts | ✅ | ✅ | ✅ | ✅ |
| Providers — Per-agent provider and model pin | ✅ | ✅ | ✅ | ✅ |
| Providers — Provider auth profiles and failover | ✅ | ✅ | ✅ | ✅ |
| Providers — No silent switch from subscription to paid API | ✅ | ✅ | ❌ | ❌ |
| Agents — Visual agent builder | ✅ | ✅ | ✅ | ❌ |
| Agents — Built-in ready-made agents | ✅ | ✅ | ✅ | ✅ |
| Agents — Create multiple named agents | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent name, role, and description | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent avatar | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent instructions or personality | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent-specific model | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent-specific files | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent-specific tools | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent-specific skills | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent-specific MCP servers | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent-specific actions | ✅ | ✅ | ❌ | ❌ |
| Agents — Agent chains | ✅ | ✅ | ❌ | ❌ |
| Agents — Agent permissions | ✅ | ✅ | ✅ | ✅ |
| Agents — Clone or duplicate an agent | ✅ | ✅ | ✅ | ✅ |
| Agents — Import and export an agent | ✅ | ✅ | ✅ | ✅ |
| Agents — Versioned portable agent package | ❌ | ❌ | ❌ | ✅ |
| Agents — Dry-run agent-package install plan | ❌ | ❌ | ❌ | ✅ |
| Agents — Hide or archive an agent | ✅ | ✅ | ✅ | ✅ |
| Agents — Delete an agent | ✅ | ✅ | ✅ | ✅ |
| Agents — Persistent agent profile | ✅ | ✅ | ✅ | ✅ |
| Agents — Isolated agent memory | ✅ | ✅ | ✅ | ✅ |
| Agents — Isolated agent credentials | ✅ | ✅ | ✅ | ✅ |
| Agents — Isolated agent workspace | ✅ | ✅ | ✅ | ✅ |
| Agents — Multi-agent routing | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent-to-agent direct messages | ✅ | ✅ | ✅ | ✅ |
| Agents — Agent group chats | ❌ | ❌ | ✅ | ❌ |
| Agents — Cross-machine agent group chats | ❌ | ❌ | ✅ | ❌ |
| Agents — Agent presence and unread state | ✅ | ✅ | ✅ | ✅ |
| Agents — Short-lived subagents | ✅ | ✅ | ✅ | ✅ |
| Agents — Parallel subagents | ✅ | ❌ | ✅ | ✅ |
| Agents — Durable named worker agents | ✅ | ✅ | ✅ | ✅ |
| Agents — Human steering during agent work | ✅ | ✅ | ✅ | ✅ |
| Agents — Main agent writes the final answer | ✅ | ✅ | ❌ | ❌ |
| Agents — Immutable per-turn configuration snapshot | ✅ | ✅ | ❌ | ❌ |
| Agents — Provider fallback keeps the same identity | ✅ | ✅ | ❌ | ❌ |
| Agents — Provider paths pass the same quality gate | ✅ | ✅ | ❌ | ❌ |
| Memory — User-saved memory | ✅ | ✅ | ✅ | ✅ |
| Memory — Automatic memory capture | ✅ | ✅ | ✅ | ✅ |
| Memory — Cross-session recall | ✅ | ✅ | ✅ | ✅ |
| Memory — Full-text memory search | ✅ | ✅ | ✅ | ✅ |
| Memory — Meaning-based memory search | ✅ | ✅ | ✅ | ✅ |
| Memory — Conversation RAG | ✅ | ✅ | ✅ | ✅ |
| Memory — Deep personal memory | ✅ | ✅ | ✅ | ✅ |
| Memory — Persistent user profile | ✅ | ✅ | ✅ | ✅ |
| Memory — Conversation summarization | ✅ | ✅ | ✅ | ✅ |
| Memory — Transcript ingestion | ✅ | ✅ | ✅ | ✅ |
| Memory — Memory deduplication and hardening | ✅ | ✅ | ✅ | ✅ |
| Memory — Governed memory proposals | ✅ | ✅ | ✅ | ❌ |
| Memory — Memory backup and restore | ✅ | ✅ | ✅ | ✅ |
| Memory — Structured Life folder | ✅ | ✅ | ❌ | ❌ |
| Memory — First-run Life bootstrap | ✅ | ✅ | ❌ | ❌ |
| Memory — Project context files | ✅ | ✅ | ✅ | ✅ |
| Memory — Global personality file | ✅ | ✅ | ✅ | ✅ |
| Memory — User-modeling engine | ✅ | ✅ | ✅ | ✅ |
| Memory — Agent creates new skills from experience | ❌ | ❌ | ✅ | ✅ |
| Memory — Agent improves existing skills | ❌ | ❌ | ✅ | ✅ |
| Memory — Automatic skill curation | ❌ | ❌ | ✅ | ❌ |
| Memory — Provenance-rich memory wiki | ❌ | ❌ | ❌ | ✅ |
| Memory — Memory contradiction and freshness tracking | ❌ | ❌ | ❌ | ✅ |
| Memory — Memory dreams or diary | ❌ | ❌ | ✅ | ✅ |
| Character — Dedicated character surface | ✅ | ✅ | ❌ | ❌ |
| Character — Feelings dashboard | ✅ | ✅ | ❌ | ❌ |
| Character — Persistent feeling state | ✅ | ✅ | ❌ | ❌ |
| Character — Current mood and stable nature | ✅ | ✅ | ❌ | ❌ |
| Character — Feeling ranges and decay | ✅ | ✅ | ❌ | ❌ |
| Character — Emotional Reaction Cortex | ✅ | ✅ | ❌ | ❌ |
| Character — Emotional Resonance | ✅ | ✅ | ❌ | ❌ |
| Character — Feeling state shapes replies | ✅ | ✅ | ❌ | ❌ |
| Character — Trace showing emotional influence | ✅ | ✅ | ❌ | ❌ |
| Character — Emotional voice expression | ✅ | ✅ | ❌ | ❌ |
| Work — Durable background worker plane | ✅ | ✅ | ✅ | ✅ |
| Work — Long work does not block Main chat | ✅ | ✅ | ✅ | ✅ |
| Work — Persistent worker projects | ✅ | ✅ | ✅ | ✅ |
| Work — Persistent worker workspaces | ✅ | ✅ | ✅ | ✅ |
| Work — Durable task board | ✅ | ❌ | ✅ | ✅ |
| Work — Multiple isolated project boards | ✅ | ❌ | ✅ | ✅ |
| Work — Task queue with clear states | ✅ | ❌ | ✅ | ✅ |
| Work — Task dependencies | ✅ | ❌ | ✅ | ✅ |
| Work — Task comments and handoffs | ✅ | ❌ | ✅ | ✅ |
| Work — Human unblock and review | ✅ | ❌ | ✅ | ✅ |
| Work — Durable task audit trail | ✅ | ❌ | ✅ | ✅ |
| Work — Task file attachments | ✅ | ✅ | ✅ | ✅ |
| Work — Durable task artifacts | ✅ | ✅ | ✅ | ✅ |
| Work — Completion callbacks | ✅ | ✅ | ✅ | ✅ |
| Work — Worker evidence ledger | ✅ | ✅ | ✅ | ✅ |
| Work — Worker result receipts | ✅ | ✅ | ✅ | ✅ |
| Work — Host-native workers | ✅ | ✅ | ✅ | ✅ |
| Work — Docker workers | ✅ | ✅ | ✅ | ✅ |
| Work — Podman workers | ❌ | ❌ | ❌ | ✅ |
| Work — SSH worker backend | ❌ | ❌ | ✅ | ✅ |
| Work — Singularity worker backend | ❌ | ❌ | ✅ | ❌ |
| Work — Modal serverless worker backend | ❌ | ❌ | ✅ | ❌ |
| Work — Daytona worker backend | ❌ | ❌ | ✅ | ✅ |
| Work — OpenShell worker backend | ❌ | ❌ | ❌ | ✅ |
| Work — Enterprise cloud VM workers | ✅ | ✅ | ✅ | ✅ |
| Work — App-owned restricted workspace | ✅ | ✅ | ✅ | ✅ |
| Work — Per-run capability grants | ✅ | ✅ | ❌ | ✅ |
| Work — Capability revocation | ✅ | ✅ | ❌ | ✅ |
| Work — Live worker watch view | ✅ | ✅ | ✅ | ✅ |
| Work — Send instructions during a run | ✅ | ✅ | ✅ | ✅ |
| Work — Pause a run | ✅ | ✅ | ✅ | ✅ |
| Work — Resume a run | ✅ | ✅ | ✅ | ✅ |
| Work — Interrupt a run | ✅ | ✅ | ✅ | ✅ |
| Work — Terminate a run | ✅ | ✅ | ✅ | ✅ |
| Work — Retry a failed run | ✅ | ✅ | ✅ | ✅ |
| Work — Dismiss a finished run | ✅ | ✅ | ✅ | ✅ |
| Work — User desktop takeover | ✅ | ✅ | ❌ | ❌ |
| Work — Crash recovery and task reclaim | ✅ | ✅ | ✅ | ✅ |
| Work — Durable worker leases | ✅ | ✅ | ✅ | ✅ |
| Work — Worker resource admission control | ✅ | ✅ | ✅ | ✅ |
| Work — Multiple simultaneous missions | ✅ | ❌ | ✅ | ✅ |
| Work — Parallel isolated workers | ✅ | ❌ | ✅ | ✅ |
| Work — Deep-research workflow | ✅ | ✅ | ✅ | ✅ |
| Work — PDF and report workflow | ✅ | ✅ | ✅ | ✅ |
| Work — Coding workflow | ✅ | ✅ | ✅ | ✅ |
| Work — Test and verification workflow | ✅ | ✅ | ✅ | ✅ |
| Work — Built-in standard QA workflow | ✅ | ✅ | ❌ | ❌ |
| Work — Built-in self-healing workflow | ✅ | ✅ | ❌ | ❌ |
| Work — Built-in feature-request workflow | ✅ | ✅ | ❌ | ❌ |
| Work — Built-in bug-report workflow | ✅ | ✅ | ❌ | ❌ |
| Work — Built-in reviewer stage | ✅ | ✅ | ✅ | ✅ |
| Work — Git worktree isolation | ✅ | ✅ | ✅ | ✅ |
| Work — Multi-project tenant separation | ✅ | ✅ | ✅ | ✅ |
| Work — Scale-to-zero workspaces | ❌ | ❌ | ✅ | ✅ |
| Work — Visual Kanban board | ✅ | ❌ | ✅ | ✅ |
| Work — Durable multi-step task flow | ✅ | ❌ | ✅ | ✅ |
| Work — Background-task activity ledger | ✅ | ✅ | ✅ | ✅ |
| Work — Persistent session goal | ❌ | ❌ | ✅ | ✅ |
| Work — Restricted cloud-worker role | ✅ | ✅ | ❌ | ✅ |
| Work — Reverse-SSH cloud-worker tunnel | ❌ | ❌ | ❌ | ✅ |
| Work — Managed worktree task suggestion | ✅ | ✅ | ❌ | ✅ |
| Work — Codex and Claude thread viewer | ✅ | ✅ | ❌ | ✅ |
| Work — Codex worker profile | ✅ | ✅ | ❌ | ✅ |
| Work — Claude Code worker profile | ✅ | ✅ | ❌ | ✅ |
| Work — OpenClaw worker profile | ✅ | ✅ | ❌ | ✅ |
| Work — Agent body can be replaced without replacing chat | ✅ | ✅ | ❌ | ✅ |
| Work — Worker body uses its own official sign-in | ✅ | ✅ | ❌ | ✅ |
| Tools — Terminal execution | ✅ | ✅ | ✅ | ✅ |
| Tools — Process control | ✅ | ✅ | ✅ | ✅ |
| Tools — File read and write | ✅ | ✅ | ✅ | ✅ |
| Tools — Browser automation | ✅ | ✅ | ✅ | ✅ |
| Tools — Full computer use | ✅ | ✅ | ✅ | ✅ |
| Tools — Web search | ✅ | ✅ | ✅ | ✅ |
| Tools — Local open-source web search | ✅ | ✅ | ✅ | ✅ |
| Tools — SearXNG search | ✅ | ✅ | ✅ | ✅ |
| Tools — Web page extraction and crawling | ✅ | ✅ | ✅ | ✅ |
| Tools — Firecrawl | ✅ | ✅ | ✅ | ✅ |
| Tools — Skyvern browser worker | ✅ | ✅ | ❌ | ❌ |
| Tools — Vision and image understanding | ✅ | ✅ | ✅ | ✅ |
| Tools — Image generation | ✅ | ✅ | ✅ | ✅ |
| Tools — Video generation | ❌ | ❌ | ✅ | ✅ |
| Tools — Music generation | ❌ | ❌ | ❌ | ✅ |
| Tools — Text to speech | ✅ | ✅ | ✅ | ✅ |
| Tools — Speech to text | ✅ | ✅ | ✅ | ✅ |
| Tools — OCR | ✅ | ✅ | ✅ | ✅ |
| Tools — Document creation | ✅ | ✅ | ✅ | ✅ |
| Tools — Spreadsheet creation | ✅ | ✅ | ✅ | ✅ |
| Tools — Slide creation | ✅ | ✅ | ✅ | ✅ |
| Tools — PDF creation | ✅ | ✅ | ✅ | ✅ |
| Tools — MCP client | ✅ | ✅ | ✅ | ✅ |
| Tools — MCP server support | ✅ | ✅ | ✅ | ✅ |
| Tools — MCP catalog UI | ✅ | ✅ | ✅ | ✅ |
| Tools — One-click MCP install | ✅ | ✅ | ✅ | ✅ |
| Tools — Remote MCP over HTTP | ✅ | ✅ | ✅ | ✅ |
| Tools — MCP OAuth | ✅ | ✅ | ✅ | ✅ |
| Tools — Per-agent MCP selection | ✅ | ✅ | ✅ | ✅ |
| Tools — General plugin system | ❌ | ❌ | ✅ | ✅ |
| Tools — Plugin manager UI | ❌ | ❌ | ✅ | ✅ |
| Tools — Public plugin marketplace | ❌ | ❌ | ✅ | ✅ |
| Tools — Installable skills | ✅ | ✅ | ✅ | ✅ |
| Tools — Skills catalog UI | ✅ | ✅ | ✅ | ✅ |
| Tools — Public skills hub | ❌ | ❌ | ✅ | ✅ |
| Tools — Skill security checks | ❌ | ❌ | ✅ | ✅ |
| Tools — Lazy tool loading and search | ✅ | ✅ | ✅ | ✅ |
| Tools — Programmatic multi-tool code mode | ✅ | ✅ | ✅ | ✅ |
| Tools — Provider plugins | ❌ | ❌ | ✅ | ✅ |
| Tools — Channel plugins | ❌ | ❌ | ✅ | ✅ |
| Tools — Webhooks | ✅ | ✅ | ✅ | ✅ |
| Tools — External event hooks | ✅ | ✅ | ✅ | ✅ |
| Tools — Google Workspace connection | ✅ | ✅ | ✅ | ✅ |
| Tools — Microsoft 365 connection | ✅ | ✅ | ✅ | ✅ |
| Tools — Multiple connected accounts | ✅ | ✅ | ✅ | ✅ |
| Tools — Spotify integration | ❌ | ❌ | ✅ | ✅ |
| Tools — Home Assistant tools | ❌ | ❌ | ✅ | ✅ |
| Tools — Health and wearable data | ✅ | ✅ | ❌ | ✅ |
| Tools — WHOOP connection | ✅ | ✅ | ❌ | ❌ |
| Tools — Apple Health daily summary | ❌ | ❌ | ❌ | ✅ |
| Tools — Health-data archive | ✅ | ✅ | ❌ | ❌ |
| Tools — Chrome browser extension | ❌ | ❌ | ❌ | ✅ |
| Tools — Gmail event trigger | ✅ | ✅ | ✅ | ✅ |
| Tools — Teams meeting guest | ❌ | ❌ | ❌ | ✅ |
| Tools — Zoom meeting guest | ❌ | ❌ | ❌ | ✅ |
| Tools — Google Meet guest | ❌ | ❌ | ✅ | ✅ |
| Automation — Scheduled jobs | ✅ | ✅ | ✅ | ✅ |
| Automation — Create a schedule in plain language | ✅ | ✅ | ✅ | ✅ |
| Automation — Schedule management UI | ✅ | ✅ | ✅ | ✅ |
| Automation — Recurring jobs | ✅ | ✅ | ✅ | ✅ |
| Automation — Time zones and daylight-saving handling | ✅ | ✅ | ✅ | ✅ |
| Automation — Active-hour windows | ✅ | ✅ | ✅ | ✅ |
| Automation — Missed-run catch-up | ✅ | ✅ | ✅ | ✅ |
| Automation — Run history ledger | ✅ | ✅ | ✅ | ✅ |
| Automation — Delivery history ledger | ✅ | ✅ | ✅ | ✅ |
| Automation — Completion callback delivery | ✅ | ✅ | ✅ | ✅ |
| Automation — Script-only jobs without an AI call | ✅ | ✅ | ✅ | ✅ |
| Automation — Reusable automation blueprints | ❌ | ❌ | ✅ | ✅ |
| Automation — Agent-specific routines | ✅ | ✅ | ✅ | ✅ |
| Automation — Nightly reflection | ✅ | ✅ | ✅ | ✅ |
| Automation — Nightly memory hardening | ✅ | ✅ | ✅ | ✅ |
| Automation — Scheduled research | ✅ | ✅ | ✅ | ✅ |
| Automation — Heartbeat loop | ✅ | ✅ | ✅ | ✅ |
| Automation — Standing orders | ✅ | ✅ | ✅ | ✅ |
| Automation — Durable task flows | ✅ | ❌ | ✅ | ✅ |
| Automation — Event-triggered jobs | ✅ | ✅ | ✅ | ✅ |
| Automation — Inbound email triggers | ✅ | ✅ | ✅ | ✅ |
| Cognition — Background specialist agents | ✅ | ✅ | ✅ | ✅ |
| Cognition — Background cortex system | ✅ | ✅ | ❌ | ❌ |
| Cognition — Anti-sycophancy reality check | ✅ | ✅ | ❌ | ❌ |
| Cognition — Red Team Cortex | ✅ | ✅ | ❌ | ❌ |
| Cognition — Periphery nightly insights | ✅ | ✅ | ❌ | ❌ |
| Cognition — Automatic risk discovery | ✅ | ✅ | ❌ | ❌ |
| Cognition — Automatic opportunity discovery | ✅ | ✅ | ❌ | ❌ |
| Cognition — Automatic blind-spot discovery | ✅ | ✅ | ❌ | ❌ |
| Cognition — Health-adjusted workload advice | ✅ | ✅ | ❌ | ❌ |
| Cognition — Follow-up and silence judgment | ✅ | ✅ | ✅ | ✅ |
| Workbench — Dedicated Prompt Workbench | ✅ | ✅ | ❌ | ❌ |
| Workbench — Visual prompt editor | ✅ | ✅ | ❌ | ❌ |
| Workbench — Factory prompt view | ✅ | ✅ | ❌ | ❌ |
| Workbench — User prompt overrides | ✅ | ✅ | ❌ | ❌ |
| Workbench — Compiled live prompt view | ✅ | ✅ | ❌ | ❌ |
| Workbench — Prompt lineage | ✅ | ✅ | ❌ | ❌ |
| Workbench — Live prompt drift detection | ✅ | ✅ | ❌ | ❌ |
| Workbench — Prompt drafts | ✅ | ✅ | ❌ | ❌ |
| Workbench — Exact-model prompt comparisons | ✅ | ✅ | ❌ | ❌ |
| Workbench — Prompt evaluation UI | ✅ | ✅ | ❌ | ❌ |
| Workbench — Scheduled prompt runs | ✅ | ✅ | ❌ | ❌ |
| Workbench — Prompt traces | ✅ | ✅ | ❌ | ❌ |
| Workbench — Prompt version history | ✅ | ✅ | ❌ | ❌ |
| Workbench — Developer source sync | ✅ | ✅ | ❌ | ❌ |
| Voice — Voice messages | ✅ | ✅ | ✅ | ✅ |
| Voice — Voice-message transcription | ✅ | ✅ | ✅ | ✅ |
| Voice — Spoken replies | ✅ | ✅ | ✅ | ✅ |
| Voice — Desktop push-to-talk | ✅ | ✅ | ✅ | ✅ |
| Voice — Real-time voice conversation | ✅ | ✅ | ✅ | ✅ |
| Voice — Discord voice-channel mode | ❌ | ❌ | ✅ | ✅ |
| Voice — Telephone-call plugin | ❌ | ❌ | ❌ | ✅ |
| Voice — First-class live call product | ✅ | ✅ | ❌ | ✅ |
| Voice — Dedicated call UI | ✅ | ✅ | ❌ | ❌ |
| Voice — Microphone permission flow | ✅ | ✅ | ✅ | ✅ |
| Voice — Full-duplex speech | ✅ | ✅ | ✅ | ✅ |
| Voice — Interruption and barge-in | ✅ | ✅ | ✅ | ✅ |
| Voice — Call continuity through reconnect | ✅ | ✅ | ❌ | ✅ |
| Voice — Multiple simultaneous calls | ✅ | ✅ | ❌ | ✅ |
| Voice — Call mode | ✅ | ✅ | ❌ | ❌ |
| Voice — Wing mode | ✅ | ✅ | ❌ | ❌ |
| Voice — Listen-only mode | ✅ | ✅ | ❌ | ❌ |
| Voice — Multi-speaker support | ✅ | ✅ | ❌ | ✅ |
| Voice — Speaker segmentation | ✅ | ✅ | ❌ | ❌ |
| Voice — Call-linked agent tasks | ✅ | ✅ | ❌ | ❌ |
| Voice — Call tool and source display | ✅ | ✅ | ❌ | ❌ |
| Voice — Secure single-use call link | ✅ | ✅ | ❌ | ❌ |
| Voice — Post-call memory ingestion | ✅ | ✅ | ❌ | ✅ |
| Voice — LiveKit call transport | ✅ | ✅ | ❌ | ❌ |
| Voice — Operator diagnostics playground | ✅ | ✅ | ❌ | ❌ |
| Voice — Call setup and smoke test | ✅ | ✅ | ❌ | ✅ |
| Voice — Call status, logs, and latency report | ✅ | ✅ | ❌ | ✅ |
| Voice — Inbound phone calls | ❌ | ❌ | ❌ | ✅ |
| Voice — Outbound phone calls | ❌ | ❌ | ❌ | ✅ |
| Voice — Twilio phone provider | ❌ | ❌ | ❌ | ✅ |
| Voice — Telnyx phone provider | ❌ | ❌ | ❌ | ✅ |
| Voice — Plivo phone provider | ❌ | ❌ | ❌ | ✅ |
| Voice — Per-phone-number agent routing | ❌ | ❌ | ❌ | ✅ |
| Voice — Audible endurance QA | ✅ | ✅ | ❌ | ❌ |
| Voice — Use calls remotely | ✅ | ✅ | ❌ | ✅ |
| Channels — Web chat | ✅ | ✅ | ✅ | ✅ |
| Channels — Telegram | ✅ | ✅ | ✅ | ✅ |
| Channels — Discord | ❌ | ❌ | ✅ | ✅ |
| Channels — Slack | ❌ | ❌ | ✅ | ✅ |
| Channels — WhatsApp | ❌ | ❌ | ✅ | ✅ |
| Channels — Signal | ❌ | ❌ | ✅ | ✅ |
| Channels — Email | ❌ | ❌ | ✅ | ❌ |
| Channels — Microsoft Teams | ❌ | ❌ | ✅ | ✅ |
| Channels — Google Chat | ❌ | ❌ | ✅ | ✅ |
| Channels — iMessage or BlueBubbles | ❌ | ❌ | ✅ | ✅ |
| Channels — Matrix | ❌ | ❌ | ✅ | ✅ |
| Channels — Mattermost | ❌ | ❌ | ✅ | ✅ |
| Channels — IRC | ❌ | ❌ | ✅ | ✅ |
| Channels — LINE | ❌ | ❌ | ✅ | ✅ |
| Channels — Feishu | ❌ | ❌ | ✅ | ✅ |
| Channels — QQ Bot | ❌ | ❌ | ✅ | ✅ |
| Channels — SMS | ❌ | ❌ | ✅ | ✅ |
| Channels — Home Assistant | ❌ | ❌ | ✅ | ❌ |
| Channels — Nextcloud Talk | ❌ | ❌ | ❌ | ✅ |
| Channels — Nostr | ❌ | ❌ | ❌ | ✅ |
| Channels — Twitch | ❌ | ❌ | ❌ | ✅ |
| Channels — Zalo | ❌ | ❌ | ❌ | ✅ |
| Channels — Synology Chat | ❌ | ❌ | ❌ | ✅ |
| Channels — Tlon or Urbit | ❌ | ❌ | ❌ | ✅ |
| Channels — Raft | ❌ | ❌ | ✅ | ✅ |
| Channels — Buzz | ❌ | ❌ | ✅ | ✅ |
| Channels — Reef | ❌ | ❌ | ❌ | ✅ |
| Channels — ClickClack | ❌ | ❌ | ❌ | ✅ |
| Channels — WeChat or Weixin | ❌ | ❌ | ✅ | ✅ |
| Channels — WeCom | ❌ | ❌ | ✅ | ✅ |
| Channels — DingTalk | ❌ | ❌ | ✅ | ❌ |
| Channels — Yuanbao | ❌ | ❌ | ✅ | ✅ |
| Channels — SimpleX | ❌ | ❌ | ✅ | ❌ |
| Channels — Ntfy | ❌ | ❌ | ✅ | ❌ |
| Channels — A2A agent channel | ❌ | ❌ | ✅ | ✅ |
| Channels — Generic webhook channel | ✅ | ✅ | ✅ | ✅ |
| Channels — Generic API chat channel | ✅ | ✅ | ✅ | ✅ |
| Channels — Multiple channels at once | ✅ | ✅ | ✅ | ✅ |
| Channels — Multiple accounts on one channel | ❌ | ❌ | ✅ | ✅ |
| Channels — DM pairing and allowlists | ✅ | ✅ | ✅ | ✅ |
| Channels — Group-chat mention rules | ✅ | ✅ | ✅ | ✅ |
| Channels — Rich-media channel replies | ✅ | ✅ | ✅ | ✅ |
| Channels — Channel-specific message formatting | ✅ | ✅ | ✅ | ✅ |
| Channels — Scheduled delivery to channels | ✅ | ✅ | ✅ | ✅ |
| Channels — Same Main continuity across channels | ✅ | ✅ | ❌ | ✅ |
| Channels — Telegram photos and albums | ✅ | ✅ | ✅ | ✅ |
| Channels — Telegram documents | ✅ | ✅ | ✅ | ✅ |
| Channels — Telegram voice replies | ✅ | ✅ | ✅ | ✅ |
| Channels — Start a live call from Telegram | ✅ | ✅ | ❌ | ✅ |
| Remote — Local-only default | ✅ | ✅ | ✅ | ✅ |
| Remote — Remote gateway access | ✅ | ✅ | ✅ | ✅ |
| Remote — Private Tailscale access | ✅ | ✅ | ✅ | ✅ |
| Remote — Tailscale setup inside the product | ✅ | ✅ | ❌ | ✅ |
| Remote — NetBird mode | ✅ | ✅ | ❌ | ❌ |
| Remote — Cloudflare quick-tunnel mode | ✅ | ✅ | ❌ | ❌ |
| Remote — Custom-domain mode | ✅ | ✅ | ✅ | ✅ |
| Remote — SSH remote control | ❌ | ❌ | ✅ | ✅ |
| Remote — LAN gateway discovery | ❌ | ❌ | ❌ | ✅ |
| Remote — QR device pairing | ❌ | ❌ | ❌ | ✅ |
| Remote — Device revocation | ✅ | ✅ | ✅ | ✅ |
| Remote — Several gateways in one desktop | ❌ | ❌ | ✅ | ✅ |
| Remote — Cross-machine agent roster | ❌ | ❌ | ✅ | ❌ |
| Remote — Public browser access | ✅ | ✅ | ✅ | ✅ |
| Remote — Managed hosted gateway | ❌ | ❌ | ✅ | ❌ |
| Platforms — iPhone app | ❌ | ❌ | ❌ | ✅ |
| Platforms — Android app | ❌ | ❌ | ❌ | ✅ |
| Platforms — Android Termux install | ❌ | ❌ | ✅ | ✅ |
| Platforms — Apple Watch app | ❌ | ❌ | ❌ | ✅ |
| Platforms — Wear OS app | ❌ | ❌ | ❌ | ✅ |
| Platforms — ChromeOS support | ❌ | ❌ | ✅ | ✅ |
| Platforms — Raspberry Pi support | ❌ | ❌ | ✅ | ✅ |
| Platforms — Docker deployment | ✅ | ❌ | ✅ | ✅ |
| Platforms — Podman deployment | ❌ | ❌ | ❌ | ✅ |
| Platforms — Nix or NixOS install | ❌ | ❌ | ✅ | ✅ |
| Platforms — Kubernetes deployment | ❌ | ❌ | ✅ | ✅ |
| Platforms — Cloudflare container deployment | ❌ | ❌ | ❌ | ✅ |
| Platforms — Scale-to-zero gateway mode | ❌ | ❌ | ❌ | ✅ |
| Platforms — VPS deployment guides | ✅ | ❌ | ✅ | ✅ |
| Platforms — Cloud VM deployment | ✅ | ✅ | ✅ | ✅ |
| Platforms — Serverless deployment | ❌ | ❌ | ✅ | ✅ |
| Platforms — Mobile camera node | ❌ | ❌ | ❌ | ✅ |
| Platforms — Mobile screen-recording node | ❌ | ❌ | ❌ | ✅ |
| Platforms — Mobile location node | ❌ | ❌ | ❌ | ✅ |
| Platforms — Mobile HealthKit node | ❌ | ❌ | ❌ | ✅ |
| Platforms — Direct Apple Watch node | ❌ | ❌ | ❌ | ✅ |
| Platforms — Remote desktop device commands | ✅ | ✅ | ✅ | ✅ |
| Platforms — Isolated browser-profile import | ❌ | ❌ | ❌ | ✅ |
| Platforms — Browser-cookie sync | ❌ | ❌ | ❌ | ✅ |
| Reliability — Loopback-only local services by default | ✅ | ✅ | ✅ | ✅ |
| Reliability — Encrypted secret storage | ✅ | ✅ | ❌ | ✅ |
| Reliability — macOS Keychain | ✅ | ✅ | ❌ | ✅ |
| Reliability — OAuth state and PKCE | ✅ | ✅ | ✅ | ✅ |
| Reliability — User pairing | ✅ | ✅ | ✅ | ✅ |
| Reliability — User and channel allowlists | ✅ | ✅ | ✅ | ✅ |
| Reliability — Tool approval prompts | ✅ | ✅ | ✅ | ✅ |
| Reliability — Per-agent tool policy | ✅ | ✅ | ✅ | ✅ |
| Reliability — Per-agent provider credentials | ✅ | ✅ | ✅ | ✅ |
| Reliability — Default least-privilege worker | ❌ | ✅ | ❌ | ❌ |
| Reliability — Container or VM isolation | ✅ | ✅ | ✅ | ✅ |
| Reliability — Signed per-run capability grants | ✅ | ✅ | ❌ | ✅ |
| Reliability — Credential broker hides raw secrets from workers | ✅ | ✅ | ❌ | ✅ |
| Reliability — Sensitive-data redaction | ✅ | ✅ | ✅ | ✅ |
| Reliability — Audit logs | ✅ | ✅ | ✅ | ✅ |
| Reliability — Durable evidence receipts | ✅ | ✅ | ✅ | ✅ |
| Reliability — Live health checks | ✅ | ✅ | ✅ | ✅ |
| Reliability — Detailed failure categories | ✅ | ✅ | ✅ | ✅ |
| Reliability — Quota and rate-limit handling | ✅ | ✅ | ✅ | ✅ |
| Reliability — Foreground chat protected from background quota use | ✅ | ✅ | ❌ | ❌ |
| Reliability — No silent paid-provider fallback | ✅ | ✅ | ❌ | ❌ |
| Reliability — Automatic service restart | ✅ | ✅ | ✅ | ✅ |
| Reliability — Worker crash recovery | ✅ | ✅ | ✅ | ✅ |
| Reliability — Idempotent delivery callbacks | ✅ | ✅ | ✅ | ✅ |
| Reliability — Failed-delivery queue | ✅ | ✅ | ✅ | ✅ |
| Reliability — Plugin install policy | ❌ | ❌ | ✅ | ✅ |
| Reliability — Plugin compatibility checks | ❌ | ❌ | ✅ | ✅ |
| Reliability — Public capability maturity scorecard | ❌ | ❌ | ❌ | ✅ |
| Reliability — Feature-to-QA release ledger | ✅ | ✅ | ❌ | ❌ |
| Reliability — Clean-machine release gate | ✅ | ✅ | ❌ | ❌ |
| Reliability — Real-browser acceptance gate | ✅ | ✅ | ❌ | ❌ |
| Reliability — Exact-model behavior evaluation gate | ✅ | ✅ | ❌ | ❌ |
| Reliability — Audible voice acceptance gate | ✅ | ✅ | ❌ | ❌ |
| Reliability — Rollback-safe data migration gate | ✅ | ✅ | ❌ | ❌ |
| Reliability — Public and private data boundary | ✅ | ✅ | ✅ | ✅ |
| Reliability — Multi-user access control | ✅ | ✅ | ✅ | ✅ |
| Reliability — Multi-agent access isolation | ✅ | ✅ | ✅ | ✅ |
| Reliability — Metrics and tracing | ✅ | ✅ | ✅ | ✅ |
| Reliability — Language-model observability integration | ✅ | ✅ | ✅ | ✅ |
| Reliability — Device-scoped credentials | ✅ | ✅ | ✅ | ✅ |
| Reliability — Secret references without plaintext config | ✅ | ✅ | ❌ | ✅ |
| Reliability — Short-lived one-time dashboard link | ✅ | ✅ | ❌ | ✅ |
| Reliability — Plugin provenance and trust pinning | ❌ | ❌ | ✅ | ✅ |
| Reliability — N-1 device-protocol compatibility | ❌ | ❌ | ❌ | ✅ |
| Research — Batch agent runs | ✅ | ✅ | ✅ | ✅ |
| Research — Trajectory export | ❌ | ❌ | ✅ | ✅ |
| Research — Reinforcement-learning training support | ❌ | ❌ | ✅ | ❌ |
| Research — Exact-model comparison runs | ✅ | ✅ | ❌ | ❌ |
