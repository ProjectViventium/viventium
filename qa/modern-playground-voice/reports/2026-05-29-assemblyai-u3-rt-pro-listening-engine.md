<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# MPV-017 — AssemblyAI Universal-3 Pro streaming (u3-rt-pro) in the Listening picker

- Date: 2026-05-29
- Case: `MPV-UC-016` / `MPV-017`
- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` (AssemblyAI Streaming Engine
  Selection)
- Status: **PARTIAL** — automated end-to-end plumbing PASS and **live runtime `/capabilities`
  confirmed on the restarted worker**; only the visible browser picker pixel + audible transcript
  remain.

## Evidence trail

feature -> requirement -> use case -> QA case -> expected -> actual evidence -> remaining gap

- **Feature**: Make the proven `AssemblyAI Universal-3 Pro streaming (u3-rt-pro)` engine selectable
  in the modern playground "Listening" picker and actually run it.
- **Requirement**: AssemblyAI engine selection must be real (picker -> requested route -> runtime ->
  `assemblyai.STT(model=...)`), list only plugin-valid ids, default to `u3-rt-pro`, and fail safe.
- **Use case**: `MPV-UC-016` — pick `Universal-3 Pro streaming (u3-rt-pro)`, start a call, speak.

## Root cause found during investigation

AssemblyAI was already wired as a Listening provider, but engine selection was **cosmetic**:

1. The capability catalog advertised a single variant id `universal-streaming` — which is **not a
   valid `livekit-plugins-assemblyai` model** (valid set: `universal-streaming-english`,
   `universal-streaming-multilingual`, `u3-rt-pro`, deprecated `u3-pro`).
2. `_apply_requested_voice_route` set only `stt_provider="assemblyai"` and **dropped the requested
   variant** (unlike the OpenAI / local-whisper branches that resolve and apply it).
3. `_build_assemblyai_stt_kwargs` **never passed `model`**, so every AssemblyAI call silently ran the
   plugin default (`universal-streaming-english`).

Net effect: the picker selection had no influence on the engine, and the proven `u3-rt-pro` was not
reachable. Public-safe R&D notes verified that the intended implementation shape is
`assemblyai.STT(model="u3-rt-pro", ...)`; raw R&D artifacts stay outside this repo.

## Change (public surfaces)

- `viventium_v0_4/voice-gateway/worker.py`: added `ASSEMBLYAI_STT_MODELS` catalog + normalizer/label/
  variants helpers + `Env.assemblyai_stt_model`; read `VIVENTIUM_ASSEMBLYAI_STT_MODEL` (default
  `u3-rt-pro`); list real variants in the capability catalog; resolve+apply the requested AssemblyAI
  variant; pass `model=` to the plugin.
- `viventium_v0_4/agent-starter-react/hooks/useVoiceRoute.ts`: mirrored the engine variant set in the
  pre-agent fallback capabilities.
- `scripts/viventium/config_compiler.py`: emit `VIVENTIUM_ASSEMBLYAI_STT_MODEL` from
  `voice.stt.model` (default `u3-rt-pro`).

## Automated evidence (PASS)

- `viventium_v0_4/voice-gateway/tests/test_worker_stt_assemblyai.py` — **12 passed**. Key proofs:
  - `test_build_stt_selection_passes_model_to_plugin`: `build_stt_selection(...).model == "u3-rt-pro"`
    (the model now reaches `assemblyai.STT`).
  - `test_apply_requested_route_applies_selected_variant`: requesting
    `universal-streaming-multilingual` now sets `assemblyai_stt_model` accordingly (previously
    dropped).
  - `test_apply_requested_route_normalizes_unknown_variant`: an unknown engine falls back to a valid
    catalog model (never an invalid provider string).
  - `test_catalog_lists_u3_rt_pro_and_drops_legacy_id`: catalog lists `u3-rt-pro` first and no longer
    advertises `universal-streaming`.
  - `test_default_model_is_u3_rt_pro`.
- Full voice-gateway suite: **329 passed** (incl. updated `test_worker_turn_handling.py` expectations
  for the now-always-passed `model`).
- `tests/release/test_config_compiler.py`: **106 passed** — added assertions
  `VIVENTIUM_ASSEMBLYAI_STT_MODEL=u3-rt-pro` (default path) and
  `VIVENTIUM_ASSEMBLYAI_STT_MODEL=universal-streaming-multilingual` (configured `voice.stt.model`).
- `tests/release/test_voice_playground_dispatch_contract.py`: **29 passed** — dispatch metadata
  round-trip fixtures refreshed from the now-invalid `universal-streaming` to canonical `u3-rt-pro`.
- `tests/release/test_wizard.py`: **22 passed**.

## Live runtime evidence (PASS)

The Viventium voice gateway running on this machine was confirmed to be executing this branch's code
and to advertise the new engine set:

- The running worker was restarted after the source update and advertised the variant list that only
  the new code can produce (the old code emitted exactly `['universal-streaming']`).
- Live `GET http://localhost:8301/capabilities` (the exact feed the playground uses to populate the
  Listening picker) returned the AssemblyAI STT capability with `available=True` and
  `variants=['u3-rt-pro', 'universal-streaming-english', 'universal-streaming-multilingual']`
  (`u3-rt-pro` first). `ASSEMBLYAI_API_KEY` is present in the worker environment, so the engine is
  genuinely selectable, not greyed out.

## Visible browser evidence (PASS)

Real browser drive of the modern playground (`http://localhost:3300`, "Choose how Viventium listens
and speaks"):

1. Opened the **Listening** selector → `AssemblyAI` submenu listed three engines in order:
   **`Universal-3 Pro streaming (u3-rt-pro)`**, `Universal Streaming (English)`,
   `Universal Streaming (Multilingual)` — no legacy `universal-streaming` placeholder.
2. Selected `Universal-3 Pro streaming (u3-rt-pro)`; the Listening row updated to
   `AssemblyAI` / `Universal-3 Pro streaming (u3-rt-pro)` and the badge changed from `COVERED`
   (local) to `METERED` (cloud), confirming the selection is applied in the UI.
3. Reverted to the original `Whisper.cpp Local` / `large-v3-turbo (Recommended)` to leave the
   environment as found (AssemblyAI is metered; the local route was the user's prior choice).

## Remaining gap (PARTIAL → audible transcript only)

Still not exercised: starting an actual AssemblyAI call and confirming the voice gateway logs
`connecting to AssemblyAI model=u3-rt-pro` with a real audible/transcript turn. This requires
initiating an authenticated call (via the LibreChat phone button) plus a microphone or synthetic
fake-mic WAV. The gateway is already running this branch's code with `ASSEMBLYAI_API_KEY`
configured, so this is an audio-drive only — no restart needed. Per QA discipline, automated/unit
proof, the live capabilities feed, and the visible picker are supporting evidence and do not
substitute
for the visible-UI + audible-transcript acceptance step; this case stays PARTIAL until that run is
captured here.

## Public-safety

No secrets, API keys, private transcripts, call/session ids, account identifiers, or machine-absolute
paths are included. The R&D reference is named by its repo-relative location only.
