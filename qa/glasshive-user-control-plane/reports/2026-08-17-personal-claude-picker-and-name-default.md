# Hosted personal-Claude picker and account-name default — 2026-08-17

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

## Automated evidence

- UI/BFF focused provider-picker, default-name, missing-CLI, platform, and actionable-error slice:
  6 passed.
- Runtime native setup support/resolver slice: 2 passed.
- Parent enterprise compiler configuration case: 1 passed.
- JavaScript syntax checks for `control-plane.js` and `app.js`: passed.

## Remaining boundary

A real personal Claude setup, mission, reconnect/forget lifecycle, contention, and two-owner
isolation remain separate acceptance work. This report proves the deployed setup is now honestly
available and low-friction; it does not upgrade those broader items from PARTIAL.
