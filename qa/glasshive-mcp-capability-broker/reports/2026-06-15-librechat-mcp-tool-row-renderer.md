<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# LibreChat MCP Tool Row Renderer Regression

Date: 2026-06-15
Result: PASS/PARTIAL

## Scope

- Feature: LibreChat-visible GlassHive MCP/tool-call rows.
- Requirement: `GH-MCP-BROKER-019` and `GH-MCP-UC-004`.
- User outcome: when GlassHive is used from chat, the user sees a concise completed tool row and can expand it for safe task/status details. Raw MCP invocation code, internal IDs, and acknowledgement guidance stay hidden.

## RCA

- The owner-reported chat had a persisted `tool_call` content part for a GlassHive launch/delegation row while the visible chat showed only assistant text.
- The visible UI did not show that row because the frontend content filter treated routine GlassHive orchestration as disposable whenever assistant text was present.
- Original/upstream LibreChat behavior renders MCP tool calls as message parts with expandable details; our fork drifted by filtering the row away.
- A second renderer gap was found during browser QA: GlassHive outputs can arrive as MCP text-content arrays wrapping JSON, while the summary code only handled direct JSON.
- ClaudeViv review noted that Git `HEAD` only showed the older delegate-only filter, while the active dirty worktree inspected before this fix had already drifted to a broader orchestration filter including workspace launch. To cover both histories, the final QA includes browser evidence for both `workspace_launch` and `worker_delegate_once`.

## Fix

- Removed the frontend filter that hid routine GlassHive orchestration tool-call parts.
- Kept existing protections that sanitize raw leaked tool transcripts from assistant text and dedupe streamed tool snapshots.
- Updated GlassHive tool summaries to parse direct JSON and MCP text-wrapped JSON.
- Expanded details now show safe `Task`, `Status`, `View / Steer`, and artifact summaries when present, while hiding internal follow-up IDs and acknowledgement guidance.
- Preserved plain-text GlassHive output in the expanded summary instead of replacing unrecognized output with a generic stub.

## Evidence

- Code inspected:
  - `client/src/components/Chat/Messages/Content/contentPartUtils.ts`
  - `client/src/components/Chat/Messages/Content/ToolCall.tsx`
  - upstream/v0.8.3 `ToolCall.tsx` for MCP row behavior
- DB inspected:
  - sanitized owner-reported conversation shape confirmed persisted `tool_call` content existed while the UI previously showed only assistant text.
  - synthetic QA conversation stored one GlassHive MCP tool-call part plus public-safe assistant text.
- Browser QA:
  - authenticated local LibreChat QA account opened the synthetic conversation.
  - visible chat showed `Ran GlassHive workspace` above the human answer.
  - expanded panel showed `Task: Open a public profile and report the follower count.` and `Status: dispatched`.
  - expanded panel did not show `worker_id`, `run_id`, acknowledgement guidance, or raw invocation code.
  - a second synthetic conversation with the older `worker_delegate_once` dispatch shape showed `Ran GlassHive delegate`, expanded `Task: Delegate a browser check and report the result.`, and `Status: dispatched`, while hiding internal IDs and acknowledgement guidance.
- Automated tests:
  - `npm run test:client -- src/components/Chat/Messages/Content/__tests__/contentParts.test.ts src/components/Chat/Messages/Content/__tests__/ToolCall.test.tsx src/components/Chat/Messages/Content/__tests__/ToolCallInfo.test.tsx --runInBand`
  - Result: 3 suites passed, 69 tests passed.
- Client-wide typecheck:
  - `npm run typecheck` from the LibreChat client workspace was attempted.
  - Result: failed on broad pre-existing client/test-fixture type errors outside this fix path; the focused renderer implementation was still covered by the passing Jest suite and browser QA.

## Visual Evaluation

- Before: the chat looked like a plain assistant answer with no evidence that GlassHive/MCP had been invoked.
- After: the row is compact and user-readable, using the product label rather than raw function names.
- The expanded detail is useful without being developer-noisy: it gives the task and status, not internal JSON blobs.
- The answer remains prominent and readable; the tool row does not crowd the conversation.

## ClaudeViv Review

- ClaudeViv agreed the user-facing direction is sound: visible product-language rows plus hidden raw plumbing.
- ClaudeViv challenged the initial RCA because Git `HEAD` only contained a delegate-only filter. Codex reconciled this with the active pre-fix dirty worktree inspection and added a `worker_delegate_once` browser replay so the old delegate filter and the broader active orchestration filter are both covered.
- ClaudeViv found a valid plain-text-output masking risk; that was fixed and covered by a new focused test.

## Remaining Gap

- This pass covered the LibreChat browser surface and renderer tests.
- Telegram bridge rerun remains a broader-suite follow-up for the same raw-tool-transcript safety boundary.
- No private screenshots or raw DB dumps are stored in this public repo.
