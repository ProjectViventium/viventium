# Hosted personal-Claude picker and account-name default — 2026-08-17

## Summary

- Result: PASS for the installed provider picker and prefilled editable account name.
- Build/source under test: exact release and source revisions recorded below.
- Runtime/artifact under test: installed three-service hosted canary.
- Environment: authenticated Microsoft Edge browser and installed GlassHive.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-007` | PASS | Claude Code appeared beside Codex; the provider name was prefilled and a custom name survived switching | No provider authorization was submitted in this run |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: personal provider-account creation UX.
- Requirement: `GH-UCP-005`.
- Use case: choose a supported AI and connect it without first inventing a name.
- QA case: `GHUCP-007`.
- Expected result: only supported providers appear; the name is useful by default and editable.
- Actual evidence: installed Edge picker, default/custom-name transitions, refresh, and focused tests.
- Remaining gap or fix: real authorization and mission were separate later cases.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement, docs, and nested docs | Requirement 55 and `GHUCP-007` define the path |
| Code, scripts, and automated harness | UI/BFF picker, runtime support resolver, and compiler tests |
| Local/external prerequisite state | Installed runtime advertised both reviewed provider setup routes |
| Logs, DB/state/persistence | Three services were healthy; refresh restored the default form state |
| Generated/shipped artifact | Exact installed release and source identities recorded below |
| Real user path and visual comparison | Edge Connections picker/default/edit/refresh matched expected behavior |
| Not run / blocked | Authorization, mission, and two-owner lifecycle were not run in this report |

## User-Grade Evidence

- Surface exercised: installed GlassHive Connections in Microsoft Edge.
- Real user path: expand account creation -> choose Claude Code -> edit name -> switch provider -> refresh.
- Visible outcome: exactly supported providers appeared and the field was prefilled but editable.
- Expanded/detail state: the account-creation disclosure showed the correct provider-specific action.
- Persistence/reload result: refresh restored the useful default and retained existing account cards.
- Backend/log/DB confirmation: runtime health advertised Codex and Claude setup support on the exact canary.
- Final model/runtime wording check: unavailable providers were omitted rather than shown as false choices.
- Substitution check: tests and runtime health support but do not replace the installed Edge inspection above.

## Scope

This run covers only the requested Connections behavior:

- show Claude Code beside Codex when the deployment explicitly enables isolated native setup and
  the runtime can execute the corresponding setup CLI;
- prefill a useful provider-specific account name while keeping the field editable;
- keep unsupported deployments fail-closed instead of advertising a setup that cannot run.

It does not claim that a real personal Claude login or worker mission completed.

## Installed candidate

- release: `glasshive-20260817-personal-claude-31`
- parent revision: `0576c4f12b7d237dcababf805883923b43244775`
- GlassHive revision: `f1cce82a952453550328d9a07661c2376a0e3499`

The three next services reported this exact triplet and HTTP 200 health. Runtime health reported
native setup support for both Codex and Claude. The effective service environment enabled Claude
consumer auth and allowed `codex-cli,claude-code`; only the runtime process received the native
Claude binary path. The activation journal was committed after explicit browser acceptance.

## Real browser result

Run in an already authenticated Microsoft Edge profile against the installed hosted dev canary:

1. Hard refresh and reopen **Connections**.
2. Confirm the prior generic server error is absent and existing Codex/Claude account cards render.
3. Expand **Connect another account**.
4. Confirm the initial AI is Codex and **Name** is already `Personal Codex`.
5. Open the AI picker and confirm exactly the supported choices `Codex` and `Claude Code` appear.
6. Select Claude Code and confirm **Name** automatically becomes `Personal Claude` and the primary
   action becomes **Connect Claude Code**.
7. Replace the name with `My reusable AI`, switch back to Codex, and confirm the custom name remains.
8. Restore the clean default, hard refresh, reopen Connections, and confirm `Personal Codex` is
   prefilled again and the Claude account/picker remain visible.

Result: **PASS** for the requested provider choice and editable prefilled name. No Connect or
Reconnect action was submitted, so no OAuth grant or provider credential was created during this
UI acceptance run.

## Automated Evidence

- UI/BFF focused provider-picker, default-name, missing-CLI, platform, and actionable-error slice:
  6 passed.
- Runtime native setup support/resolver slice: 2 passed.
- Parent enterprise compiler configuration case: 1 passed.
- JavaScript syntax checks for `control-plane.js` and `app.js`: passed.

## Remaining boundary

A real personal Claude setup, mission, reconnect/forget lifecycle, contention, and two-owner
isolation remain separate acceptance work. This report proves the deployed setup is now honestly
available and low-friction; it does not upgrade those broader items from PARTIAL.

## Findings

- The provider picker and default-name behavior matched the intended low-friction path.
- No defect remained in this scoped run; broader provider lifecycle evidence stayed separate.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers, or customer data.
- [x] No conversation, message, session/call, provider-request, or database identifiers.
- [x] No local absolute paths, hostnames, machine names, private stack traces, exports, or runtime dumps.
- [x] Private observations are summarized only as sanitized outcomes and counts.
