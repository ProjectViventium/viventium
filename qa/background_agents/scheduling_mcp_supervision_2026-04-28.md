# Scheduling MCP Supervision QA - 2026-04-28

## Scope

Investigate repeated `scheduling-cortex` MCP failures in the local Viventium stack and verify the
owning runtime fix.

## Public-Safe Evidence

- Generated LibreChat config pointed `scheduling-cortex` at the local streamable HTTP MCP URL.
- The configured MCP port had no active listener when failures occurred.
- LibreChat API logs showed repeated `scheduling-cortex` MCP `ECONNREFUSED` transport failures.
- The Scheduling Cortex SQLite DB existed, had the expected `scheduled_tasks` table, and reported
  active schedules without persisted scheduler errors.
- The MCP server log showed normal startup and an orderly shutdown, not a Python import, dependency,
  or DB crash.

## Root Cause

The launcher treated Scheduling Cortex as a fire-and-forget optional sidecar. It checked that the
process existed shortly after launch, but did not require a real `/health` probe and did not
supervise the MCP after startup. Once the MCP process exited, LibreChat continued to retry the
configured streamable HTTP URL and every tool reconnect failed with connection refused.

## Fix

- Startup now repairs an occupied-but-unhealthy Scheduling MCP port before continuing.
- Startup success now requires the Scheduling MCP `/health` endpoint to respond.
- The launcher now executes the long-lived MCP through the synced venv Python instead of using the
  `uv run` wrapper as the supervised service process.
- The launcher now starts a lightweight Scheduling MCP watchdog that restarts the local MCP if
  health checks fail while LibreChat is still running.
- Optional-start helper subshells clear inherited exit cleanup traps so a finished sidecar startup
  worker cannot accidentally run stack cleanup.

## Verification

- Shell syntax: `bash -n viventium_v0_4/viventium-librechat-start.sh`
- Release contract: `python3 -m pytest tests/release/test_scheduling_mcp_supervision.py -q`
- Live runtime QA:
  - `/health` returned `{"status":"ok"}` on the configured local port.
  - MCP initialize returned `HTTP 200` with `content-type: text/event-stream`.
  - The MCP process remained alive after initialize and a follow-up health probe.
  - LibreChat MCP reinitialize for `scheduling-cortex` returned success after the MCP was restored.
  - No new `scheduling-cortex` API error log rows appeared after live restore.
  - The SQLite schedule store still reported active schedules and no persisted scheduler errors.
