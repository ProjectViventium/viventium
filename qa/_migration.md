# QA Legacy Migration Backlog

This backlog exists so the new QA folder standard is not paper-only. Legacy folders can keep their
current links, but the next meaningful change to a feature must migrate or explicitly update the
entry here.

Target shape:

- `qa/<feature>/README.md`
- `qa/<feature>/cases.md`
- `qa/<feature>/reports/YYYY-MM-DD-<topic>.md` for new dated reports

## Current Legacy Gaps

| Feature | Current Gap | Migration Trigger |
| --- | --- | --- |
| `agent-config-continuity` | Missing `cases.md` and `reports/`; flat `report.md` only | Next continuity QA change |
| `background_agents` | Has `cases.md` bridge, but dated reports are still flat files | Next background-agent report cleanup |
| `config-compiler-memory` | Missing `cases.md` and `reports/`; flat `report.md` only | Next compiler-memory QA change |
| `config-compiler-xai-models` | Missing `cases.md` and `reports/`; flat `report.md` only | Next model/compiler QA change |
| `continuity-ops` | Missing `cases.md` and `reports/`; flat `report.md` only | Next continuity ops QA change |
| `conversation-recall-rag` | Missing `cases.md` and `reports/`; flat `report.md` only | Next recall/RAG QA change |
| `glasshive_host_workers` | Missing `cases.md` and `reports/` | Next GlassHive host-worker QA change |
| `glasshive_steer` | Missing `cases.md` and `reports/` | Next GlassHive steer QA change |
| `glasshive_watch_desktop` | Missing `cases.md` and `reports/` | Next GlassHive watch QA change |
| `glasshive_workspaces` | Missing `cases.md` and `reports/` | Next GlassHive workspace QA change |
| `installer-piped-bootstrap` | Missing `cases.md` and `reports/`; flat `report.md` only | Next installer bootstrap QA change |
| `installer-resilience` | Missing `cases.md` and `reports/`; flat `plan.md`/`report.md` | Next installer resilience QA change |
| `installer-wait-taglines` | Missing `cases.md` and `reports/`; flat `report.md` only | Next installer UX QA change |
| `listen-only-mode` | Missing `cases.md` and `reports/`; flat `report.md` only | Next listen-only QA change |
| `mcp-oauth` | Missing `README.md`, `cases.md`, and `reports/` | Next MCP OAuth QA change |
| `meeting-transcript-memory` | Missing `cases.md` and `reports/`; has eval subfolder | Next transcript-memory QA change |
| `memory-continuity` | Missing `cases.md` and `reports/`; flat `report.md` only | Next memory continuity QA change |
| `memory-hardening` | Missing `cases.md` and `reports/`; flat `report.md` only | Next memory hardening QA change |
| `modern-playground-voice` | Missing `cases.md` and `reports/`; flat `report.md` only | Next playground voice QA change |
| `prompt-architecture` | Missing `cases.md`; has `evals/` and `reports/` | Next prompt-architecture QA change |
| `remote-access` | Missing `cases.md` and `reports/`; flat `report.md` only | Next remote access QA change |
| `telegram-detached-api-stability` | Missing `cases.md` and `reports/`; flat `report.md` only | Next Telegram API QA change |
| `telegram-document-attachments` | Missing `cases.md` and `reports/`; flat `report.md` only | Next document attachment QA change |
| `telegram-local-bot-api` | Missing `cases.md` and `reports/`; flat `report.md` only | Next local bot API QA change |
| `telegram-media-downloads` | Missing `cases.md` and `reports/`; flat `report.md` only | Next media downloads QA change |
| `telegram-media-prereqs` | Missing `cases.md` and `reports/`; flat `report.md` only | Next media prereq QA change |
| `telegram-settings-latency` | Missing `cases.md` and `reports/`; flat `report.md` only | Next settings latency QA change |
| `telegram-voice-replies` | Missing `cases.md` and `reports/` | Next Telegram voice reply QA change |
| `voice-call-hardening` | Missing `cases.md` and `reports/`; flat dated reports | Next voice hardening QA change |
| `voice-streaming-first` | Missing `cases.md` and `reports/`; flat `report.md` only | Next voice streaming QA change |
| `voice-turn-taking` | Missing `cases.md` and `reports/` | Next voice turn-taking QA change |
| `web-search-telegram` | Missing `cases.md` and `reports/`; flat `report.md` only | Next web-search Telegram QA change |
