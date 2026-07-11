from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_COMPILER_SPEC = importlib.util.spec_from_file_location(
    "viventium_config_compiler",
    ROOT / "scripts/viventium/config_compiler.py",
)
assert CONFIG_COMPILER_SPEC and CONFIG_COMPILER_SPEC.loader
config_compiler = importlib.util.module_from_spec(CONFIG_COMPILER_SPEC)
CONFIG_COMPILER_SPEC.loader.exec_module(config_compiler)

MEMORY_HARDEN_SPEC = importlib.util.spec_from_file_location(
    "viventium_memory_harden",
    ROOT / "scripts/viventium/memory_harden.py",
)
assert MEMORY_HARDEN_SPEC and MEMORY_HARDEN_SPEC.loader
memory_harden = importlib.util.module_from_spec(MEMORY_HARDEN_SPEC)
MEMORY_HARDEN_SPEC.loader.exec_module(memory_harden)


def _prompt_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n.*?\n---\n(?P<body>.*)\Z", text, re.DOTALL)
    assert match, f"Prompt file missing frontmatter: {path}"
    return match.group("body").strip()


def _frontmatter_version(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(?P<meta>.*?)\n---\n", text, re.DOTALL)
    assert match, f"Prompt file missing frontmatter: {path}"
    version = re.search(r"^version:\s*(\d+)\s*$", match.group("meta"), re.MULTILINE)
    assert version, f"Prompt file missing version: {path}"
    return int(version.group(1))


def _fallback_template(script: str, function_name: str) -> str:
    match = re.search(
        rf"function {function_name}\b[\s\S]*?\n  const fallback = `(?P<body>[\s\S]*?)`;\n\n  return getPromptText",
        script,
    )
    assert match, f"Missing fallback template in {function_name}"
    return (
        match.group("body")
        .replace("${maxChanges}", "{{max_changes}}")
        .replace("${liveMemoryInstructions}", "{{live_memory_instructions}}")
        .replace("${localWorkpackJson}", "{{local_workpack_json}}")
        .replace("${createdAt}", "{{created_at}}")
        .replace("${maxChars}", "{{max_chars}}")
        .replace("${transcriptEnvelopeJson}", "{{transcript_envelope_json}}")
        .strip()
    )


def _fallback_transcript_caveat(script: str) -> str:
    match = re.search(
        r"const FALLBACK_TRANSCRIPT_CAVEAT_PROMPT =\n  (?P<literal>\"(?:[^\"\\]|\\.)*\");",
        script,
    )
    assert match, "Missing fallback transcript caveat prompt"
    return json.loads(match.group("literal"))


def _transcript_prompt_version_constant(script: str) -> int:
    match = re.search(r"const TRANSCRIPT_PROMPT_VERSION = (\d+);", script)
    assert match, "Missing transcript prompt version constant"
    return int(match.group(1))


def test_memory_hardening_defaults_are_launch_ready_and_opt_in() -> None:
    settings = config_compiler.resolve_memory_hardening_settings({})

    assert settings["enabled"] is False
    assert settings["schedule"] == "0 3 * * *"
    assert settings["lookback_days"] == 7
    assert settings["min_user_idle_minutes"] == 60
    assert settings["max_changes_per_user"] == 3
    assert settings["max_input_chars"] == 500000
    assert settings["require_full_lookback"] is True
    assert settings["min_apply_interval_seconds"] == 300
    assert settings["provider_profile"] == "launch_ready_only"
    assert settings["anthropic_model"] in config_compiler.MEMORY_HARDENING_LAUNCH_READY_MODELS["anthropic"]
    assert settings["openai_model"] in config_compiler.MEMORY_HARDENING_LAUNCH_READY_MODELS["openai"]
    assert settings["openai_model"] == "gpt-5.6-sol"
    assert settings["anthropic_effort"] == "xhigh"
    assert settings["openai_reasoning_effort"] == "xhigh"
    assert settings["transcripts"]["rag_mode"] == "detailed_summary_only"
    assert settings["transcripts"]["min_files_per_run"] == 5
    assert settings["transcripts"]["max_batches_per_invocation"] == 1
    assert settings["transcripts"]["reference_memory_max_chars"] == 24000
    assert settings["transcripts"]["reference_messages_max_chars"] == 36000


def test_memory_hardening_model_timeout_matches_large_overnight_workload() -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
process.stdout.write(String(hardener.DEFAULT_MEMORY_HARDENING_MODEL_TIMEOUT_MS));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )

    assert int(result.stdout) == 30 * 60 * 1000


def test_memory_hardening_apply_transcript_batch_floor_is_node_authoritative() -> None:
    script = """
process.env.VIVENTIUM_MEMORY_TRANSCRIPTS_MIN_FILES_PER_RUN = '5';
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const options = hardener.parseArgs([
  '--mode', 'apply',
  '--transcripts-only',
  '--transcript-max-files-per-run', '1'
]);
process.stdout.write(JSON.stringify({
  maxFiles: options.transcriptMaxFilesPerRun,
  minFiles: options.transcriptMinFilesPerRun
}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload == {"maxFiles": 5, "minFiles": 5}


def test_memory_hardening_node_cooldown_blocks_repeat_apply_without_power_override_bypass(
    tmp_path: Path,
) -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const paths = { stateDir: process.argv[1] };
hardener.writeEfficiencyMarker(paths, {
  status: 'finished',
  run_id: 'previous',
  mode: 'apply',
  started_at: '2026-05-27T10:00:00.000Z',
  finished_at: '2026-05-27T10:00:00.000Z',
  min_apply_interval_seconds: 300,
  transcript_max_files_per_run: 5,
  transcript_min_files_per_run: 5,
  transcripts_only: true
});
process.env.VIVENTIUM_MEMORY_HARDENING_ALLOW_POWER_OVERRIDE = '1';
const decision = hardener.modelApplyCooldownDecision(
  {
    mode: 'apply',
    transcriptsOnly: true,
    minApplyIntervalSeconds: 300,
    ignoreEfficiencyGate: true
  },
  paths,
  new Date('2026-05-27T10:01:00.000Z')
);
process.stdout.write(JSON.stringify(decision));
"""
    result = subprocess.run(
        ["node", "-e", script, str(tmp_path / "state")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["allowed"] is False
    assert payload["reason"] == "maintenance_cooldown"
    assert payload["nextAllowedAt"] == "2026-05-27T10:05:00.000Z"


def test_memory_hardening_node_cooldown_blocks_repeat_dry_run(tmp_path: Path) -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const paths = { stateDir: process.argv[1] };
hardener.writeEfficiencyMarker(paths, {
  status: 'finished',
  run_id: 'previous',
  mode: 'apply',
  started_at: '2026-05-27T10:00:00.000Z',
  finished_at: '2026-05-27T10:00:00.000Z',
  min_apply_interval_seconds: 300,
  transcripts_only: false
});
const decision = hardener.modelApplyCooldownDecision(
  { mode: 'dry-run', minApplyIntervalSeconds: 300 },
  paths,
  new Date('2026-05-27T10:01:00.000Z')
);
process.stdout.write(JSON.stringify(decision));
"""
    result = subprocess.run(
        ["node", "-e", script, str(tmp_path / "state")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["allowed"] is False
    assert payload["reason"] == "maintenance_cooldown"


def test_memory_hardening_efficiency_override_requires_flag_and_env(tmp_path: Path) -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const paths = { stateDir: process.argv[1] };
hardener.writeEfficiencyMarker(paths, {
  status: 'finished',
  run_id: 'previous',
  mode: 'apply',
  started_at: '2026-05-27T10:00:00.000Z',
  finished_at: '2026-05-27T10:00:00.000Z',
  min_apply_interval_seconds: 300,
  transcripts_only: true
});
process.env.VIVENTIUM_MEMORY_HARDENING_ALLOW_EFFICIENCY_OVERRIDE = '1';
const envOnly = hardener.modelApplyCooldownDecision(
  { mode: 'apply', transcriptsOnly: true, minApplyIntervalSeconds: 300 },
  paths,
  new Date('2026-05-27T10:01:00.000Z')
);
const flagAndEnv = hardener.modelApplyCooldownDecision(
  {
    mode: 'apply',
    transcriptsOnly: true,
    minApplyIntervalSeconds: 300,
    ignoreEfficiencyGate: true
  },
  paths,
  new Date('2026-05-27T10:01:00.000Z')
);
process.stdout.write(JSON.stringify({envOnly, flagAndEnv}));
"""
    result = subprocess.run(
        ["node", "-e", script, str(tmp_path / "state")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["envOnly"]["allowed"] is False
    assert payload["envOnly"]["reason"] == "maintenance_cooldown"
    assert payload["flagAndEnv"]["allowed"] is True
    assert payload["flagAndEnv"]["reason"] == "efficiency_override"
    assert payload["flagAndEnv"]["bypassed"] is True


def test_memory_hardening_existing_run_apply_is_not_model_cooldown_gated() -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
process.stdout.write(JSON.stringify({
  freshApply: hardener.isCooldownGatedModelRun({ mode: 'apply' }),
  dryRun: hardener.isCooldownGatedModelRun({ mode: 'dry-run' }),
  existingRunApply: hardener.isCooldownGatedModelRun({ mode: 'apply', runId: 'existing' })
}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload == {"freshApply": True, "dryRun": True, "existingRunApply": False}


def test_memory_hardening_interactive_maintenance_bypasses_cooldown_only(tmp_path: Path) -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const paths = { stateDir: process.argv[1] };
hardener.writeEfficiencyMarker(paths, {
  status: 'finished',
  run_id: 'previous',
  mode: 'apply',
  started_at: '2026-05-27T10:00:00.000Z',
  finished_at: '2026-05-27T10:00:00.000Z',
  min_apply_interval_seconds: 300,
  transcripts_only: true
});
const decision = hardener.modelApplyCooldownDecision(
  {
    mode: 'apply',
    transcriptsOnly: true,
    minApplyIntervalSeconds: 300,
    interactiveMaintenance: true
  },
  paths,
  new Date('2026-05-27T10:01:00.000Z')
);
process.stdout.write(JSON.stringify(decision));
"""
    result = subprocess.run(
        ["node", "-e", script, str(tmp_path / "state")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["allowed"] is True
    assert payload["reason"] == "interactive_maintenance"
    assert payload["bypassed"] is True


def test_memory_hardening_default_fallbacks_respect_provider_boundary() -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
process.env.VIVENTIUM_PRIMARY_PROVIDER = 'anthropic';
process.env.VIVENTIUM_SECONDARY_PROVIDER = '';
process.env.VIVENTIUM_MEMORY_HARDENING_PROVIDER = 'anthropic';
process.env.VIVENTIUM_MEMORY_HARDENING_MODEL = '';
process.env.VIVENTIUM_MEMORY_HARDENING_MODEL_FALLBACKS = '';
const defaultCandidates = hardener.resolveProvider({}).candidates;
process.env.VIVENTIUM_MEMORY_HARDENING_MODEL_FALLBACKS = 'anthropic:opus:xhigh,openai:gpt-5.6-sol:xhigh';
const explicitCandidates = hardener.resolveProvider({}).candidates;
process.stdout.write(JSON.stringify({ defaultCandidates, explicitCandidates }));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert {candidate["provider"] for candidate in payload["defaultCandidates"]} == {"anthropic"}
    assert any(candidate["model"] == "claude-opus-4-8" for candidate in payload["defaultCandidates"])
    assert any(candidate["model"] == "opus" for candidate in payload["defaultCandidates"])
    assert any(candidate["provider"] == "openai" for candidate in payload["explicitCandidates"])


def test_memory_hardening_prefers_sol_xhigh_when_both_providers_are_available() -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
process.env.VIVENTIUM_PRIMARY_PROVIDER = 'openai';
process.env.VIVENTIUM_SECONDARY_PROVIDER = 'anthropic';
delete process.env.VIVENTIUM_MEMORY_HARDENING_PROVIDER;
delete process.env.VIVENTIUM_MEMORY_HARDENING_MODEL;
delete process.env.VIVENTIUM_MEMORY_HARDENING_MODEL_FALLBACKS;
const selected = hardener.resolveProvider({});
process.stdout.write(JSON.stringify(selected));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["effort"] == "xhigh"


def test_memory_hardening_vector_presence_failures_are_not_model_failures() -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const timeout = Object.assign(new Error('timed out'), { code: 'ETIMEDOUT' });
const unavailable = Object.assign(new Error('connect ECONNREFUSED'), { code: 'ECONNREFUSED' });
process.stdout.write(JSON.stringify({
  modelTimeout: hardener.classifyModelCallFailure(timeout),
  vectorTimeout: hardener.classifyVectorPresenceFailure(timeout),
  vectorUnavailable: hardener.classifyVectorPresenceFailure(unavailable)
}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["modelTimeout"] == "model_call_timeout"
    assert payload["vectorTimeout"] == "vector_presence_timeout"
    assert payload["vectorUnavailable"] == "vector_presence_unavailable"


def test_memory_hardening_codex_output_schema_matches_openai_structured_subset() -> None:
    script = """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const proposal = hardener.codexOutputSchema(hardener.proposalSchema());
const transcriptSummary = hardener.codexOutputSchema(hardener.transcriptSummarySchema(32000));
const transcriptItem = proposal.properties.transcript_summaries.items;
const operationItem = proposal.properties.operations.items;
const evidenceItem = operationItem.properties.evidence.items;
process.stdout.write(JSON.stringify({
  transcriptSummaryRequired: transcriptSummary.required,
  transcriptItemRequired: transcriptItem.required,
  operationRequired: operationItem.required,
  evidenceHasOneOf: Object.prototype.hasOwnProperty.call(evidenceItem, 'oneOf'),
  evidenceAnyOfCount: Array.isArray(evidenceItem.anyOf) ? evidenceItem.anyOf.length : 0,
  evidenceBranchRequired: evidenceItem.anyOf.map((branch) => branch.required)
}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["transcriptSummaryRequired"] == [
        "summary",
        "displayTitle",
        "oneLineSummary",
        "meetingDatetime",
        "participants",
        "createdAt",
    ]
    assert payload["transcriptItemRequired"] == ["artifactId", "summary", "createdAt"]
    assert payload["operationRequired"] == ["key", "action", "value", "rationale", "evidence"]
    assert payload["evidenceHasOneOf"] is False
    assert payload["evidenceAnyOfCount"] == 3
    assert payload["evidenceBranchRequired"] == [
        ["source", "messageId", "createdAt"],
        ["messageId", "createdAt"],
        ["source", "artifactId", "createdAt"],
    ]


def test_memory_hardening_rollback_records_public_safe_summary(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    run_dir = state_dir / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    script = """
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');

const runDir = process.argv[1];
const stateDir = process.argv[2];
fs.writeFileSync(
  path.join(runDir, 'summary.json'),
  JSON.stringify({
    schemaVersion: 1,
    run_id: 'run-1',
    mode: 'apply',
    status: 'success',
    finished_at: '2026-06-02T18:54:39.253Z',
  }) + '\\n',
);
fs.writeFileSync(path.join(runDir, 'run-log.redacted.jsonl'), '');

hardener.recordRollbackResult({
  runDir,
  runId: 'run-1',
  result: {
    schemaVersion: 1,
    run_id: 'run-1',
    restored: ['private-user-hash'],
    rolled_back_at: '2026-06-02T18:09:54.770Z',
  },
});

const summaryText = fs.readFileSync(path.join(runDir, 'summary.json'), 'utf8');
const logText = fs.readFileSync(path.join(runDir, 'run-log.redacted.jsonl'), 'utf8');
const privateText = fs.readFileSync(path.join(runDir, 'rollback-summary.json'), 'utf8');
const summary = JSON.parse(summaryText);
const logRows = logText.trim().split('\\n').filter(Boolean).map((line) => JSON.parse(line));
const status = hardener.status({stateDir});

assert.strictEqual(summary.rolled_back_at, '2026-06-02T18:09:54.770Z');
assert.strictEqual(summary.rollback_summary_file, 'rollback-summary.json');
assert.strictEqual(summary.rollback_restored_count, 1);
assert.strictEqual(status.latest_run.applied_at, '2026-06-02T18:54:39.253Z');
assert.strictEqual(status.latest_run.rolled_back_at, '2026-06-02T18:09:54.770Z');
assert.strictEqual(status.latest_run.rollback_summary_file, 'rollback-summary.json');
assert.strictEqual(status.latest_run.rollback_restored_count, 1);
assert(!summaryText.includes('private-user-hash'));
assert.strictEqual(logRows.length, 1);
assert.strictEqual(logRows[0].event, 'rollback_run');
assert.strictEqual(logRows[0].restored_user_count, 1);
assert(!logText.includes('private-user-hash'));
assert(privateText.includes('private-user-hash'));
"""
    subprocess.run(["node", "-e", script, str(run_dir), str(state_dir)], cwd=ROOT, check=True)


def test_memory_hardening_status_reports_scheduled_trigger_health(tmp_path: Path) -> None:
    state_dir = tmp_path / "state" / "memory-hardening"
    events_dir = state_dir / "schedule-events"
    events_dir.mkdir(parents=True)
    (events_dir / "launchd-old.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "status": "success",
                "trigger_source": "launchd",
                "scheduled_invocation": True,
                "fired_at_utc": "2020-01-01T08:00:00.000Z",
                "fired_at_local": "2020-01-01T03:00:00.000-05:00",
                "finished_at_utc": "2020-01-01T08:01:00.000Z",
                "exit_code": 0,
                "run_id": "old-run",
                "run_status": "success",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    script = """
const assert = require('assert');
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const status = hardener.status({stateDir: process.argv[1]});
assert.strictEqual(status.schedule_health.schedule, '0 3 * * *');
assert.strictEqual(status.schedule_health.timezone, 'America/Toronto');
assert.strictEqual(status.schedule_health.latest_scheduled_trigger.run_id, 'old-run');
assert.strictEqual(status.schedule_health.missed_expected_window, true);
assert(!JSON.stringify(status.schedule_health).includes(process.argv[2]));
"""
    subprocess.run(
        ["node", "-e", script, str(state_dir), str(tmp_path)],
        cwd=ROOT,
        check=True,
        env={
            **os.environ,
            "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": "0 3 * * *",
            "VIVENTIUM_MEMORY_HARDENING_TIMEZONE": "America/Toronto",
        },
    )


def test_memory_hardening_status_does_not_flag_fresh_scheduled_trigger_as_missed(tmp_path: Path) -> None:
    state_dir = tmp_path / "state" / "memory-hardening"
    events_dir = state_dir / "schedule-events"
    events_dir.mkdir(parents=True)
    script = """
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const stateDir = process.argv[1];
const eventsDir = path.join(stateDir, 'schedule-events');
fs.writeFileSync(path.join(eventsDir, 'launchd-now.json'), JSON.stringify({
  schemaVersion: 1,
  status: 'success',
  trigger_source: 'launchd',
  scheduled_invocation: true,
  fired_at_utc: new Date().toISOString(),
  fired_at_local: new Date().toISOString(),
  exit_code: 0,
  run_id: 'fresh-run',
  run_status: 'success',
}) + '\\n');
const status = hardener.status({stateDir});
assert.strictEqual(status.schedule_health.latest_scheduled_trigger.run_id, 'fresh-run');
assert.strictEqual(status.schedule_health.missed_expected_window, false);
"""
    subprocess.run(
        ["node", "-e", script, str(state_dir)],
        cwd=ROOT,
        check=True,
        env={
            **os.environ,
            "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": "0 3 * * *",
            "VIVENTIUM_MEMORY_HARDENING_TIMEZONE": "America/Toronto",
        },
    )


def test_memory_hardening_runtime_uses_registry_prompts_when_available(tmp_path: Path) -> None:
    bundle_path = tmp_path / "prompt-bundle.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "prompt_count": 3,
                "prompts": {
                    "memory.transcript_summarizer": {
                        "metadata": {"version": 9, "strict_variables": True},
                        "body": "REGISTRY TRANSCRIPT {{created_at}} {{max_chars}} {{transcript_envelope_json}}",
                    },
                    "memory.hardener_consolidation": {
                        "metadata": {"version": 4, "strict_variables": True},
                        "body": "REGISTRY HARDENER {{max_changes}} {{live_memory_instructions}} {{local_workpack_json}}",
                    },
                    "memory.transcript_caveat": {
                        "metadata": {"version": 1},
                        "body": "REGISTRY CAVEAT",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    script = """
process.env.VIVENTIUM_PROMPT_BUNDLE_PATH = process.argv[1];
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const { resetPromptRegistryForTests } = require('./viventium_v0_4/LibreChat/api/server/services/viventium/promptRegistry');
resetPromptRegistryForTests();
const transcript = {
  artifactId: 'meeting_transcript:synthetic',
  filename: 'synthetic.txt',
  file_mtime: '2026-05-21T10:00:00.000Z',
  today_date: '2026-05-21',
  source_status: 'new_or_changed',
  user_identity: { display_names: ['QA User'] },
  calendar_match: null,
  transcript_caveat_prompt: hardener.transcriptCaveatPrompt(),
  raw_char_count: 18,
  raw_byte_count: 18,
  supplied_char_count: 18,
  input_complete: true,
  file_content: '<transcript>synthetic</transcript>'
};
const prompt = hardener.buildTranscriptSummaryPrompt({
  transcript,
  now: new Date('2026-05-21T12:00:00.000Z'),
  maxChars: 123
});
const hardenerPrompt = hardener.buildHardenerPrompt({
  user: { _id: '507f1f77bcf86cd799439011' },
  memoryConfig: {
    validKeys: ['context'],
    keyLimits: { context: 1200 },
    tokenLimit: 8000,
    instructions: 'live instructions'
  },
  memories: [],
  messages: [],
  meetingTranscripts: [],
  now: new Date('2026-05-21T12:00:00.000Z'),
  lookbackDays: 7,
  maxChanges: 2
});
process.stdout.write(JSON.stringify({
  prompt,
  hardenerPrompt,
  caveat: hardener.transcriptCaveatPrompt(),
  transcriptPromptVersion: hardener.transcriptPromptVersion()
}));
"""
    result = subprocess.run(
        ["node", "-e", script, str(bundle_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["prompt"].startswith("REGISTRY TRANSCRIPT 2026-05-21T12:00:00.000Z 123")
    assert '"artifactId":"meeting_transcript:synthetic"' in payload["prompt"]
    assert payload["hardenerPrompt"].startswith("REGISTRY HARDENER 2 live instructions")
    assert payload["caveat"] == "REGISTRY CAVEAT"
    assert payload["transcriptPromptVersion"] == 9


def test_memory_hardening_inline_fallbacks_match_registry_prompt_sources() -> None:
    script = (ROOT / "viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js").read_text(encoding="utf-8")

    expected = {
        "memory.hardener_consolidation": _prompt_body(
            ROOT / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/memory/hardener_consolidation.md"
        ),
        "memory.transcript_summarizer": _prompt_body(
            ROOT / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/memory/transcript_summarizer.md"
        ),
        "memory.transcript_caveat": _prompt_body(
            ROOT / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/memory/transcript_caveat.md"
        ),
    }

    assert _fallback_template(script, "buildHardenerPrompt") == expected["memory.hardener_consolidation"]
    assert _fallback_template(script, "buildTranscriptSummaryPrompt") == expected["memory.transcript_summarizer"]
    assert _fallback_transcript_caveat(script) == expected["memory.transcript_caveat"]
    assert _frontmatter_version(
        ROOT / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/memory/transcript_summarizer.md"
    ) == _transcript_prompt_version_constant(script)


def test_memory_hardening_wrapper_passes_compiled_model_tuple() -> None:
    class Args:
        repo_root = ROOT
        app_support_dir = ROOT / ".tmp-app-support"
        runtime_dir = ROOT / ".tmp-runtime"
        command = "dry-run"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        json = False

    command = memory_harden.node_command(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "openai",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "gpt-5.6-sol",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "qa@example.com",
            "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE": "detailed_summary_only",
        },
    )

    assert command[command.index("--provider") + 1] == "openai"
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"
    assert command[command.index("--user-email") + 1] == "qa@example.com"
    assert command[command.index("--transcript-rag-mode") + 1] == "detailed_summary_only"


def test_memory_hardening_wrapper_loads_canonical_runtime_env_stack(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    librechat_dir = tmp_path / "LibreChat"
    service_env_dir = runtime_dir / "service-env"
    service_env_dir.mkdir(parents=True)
    librechat_dir.mkdir(parents=True)

    (librechat_dir / ".env").write_text(
        "MONGO_URI=mongodb://legacy-repo\n"
        "LEGACY_ONLY=repo\n",
        encoding="utf-8",
    )
    (runtime_dir / "local.env").write_text(
        "MONGO_URI=mongodb://legacy-local\n"
        "LEGACY_LOCAL=1\n",
        encoding="utf-8",
    )
    (runtime_dir / "librechat.env").write_text(
        "CONFIG_PATH=/legacy/librechat.yaml\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.env").write_text(
        "MONGO_URI=mongodb://runtime\n"
        "CONFIG_PATH=/runtime/librechat.yaml\n"
        "VIVENTIUM_MEMORY_HARDENING_PROVIDER=anthropic\n",
        encoding="utf-8",
    )
    (runtime_dir / "runtime.local.env").write_text(
        "MONGO_URI=mongodb://runtime-local\n"
        "LOCAL_ONLY=1\n",
        encoding="utf-8",
    )
    (service_env_dir / "librechat.env").write_text(
        "CONFIG_PATH=/service/librechat.yaml\n"
        "MONGO_URI=''\n"
        "SERVICE_ONLY=1\n",
        encoding="utf-8",
    )

    env = memory_harden.load_runtime_env(runtime_dir, librechat_dir)

    assert [path.relative_to(tmp_path).as_posix() for path in memory_harden.runtime_env_candidates(runtime_dir, librechat_dir)] == [
        "LibreChat/.env",
        "runtime/local.env",
        "runtime/librechat.env",
        "runtime/runtime.env",
        "runtime/runtime.local.env",
        "runtime/service-env/librechat.env",
    ]
    assert env["MONGO_URI"] == "mongodb://runtime-local"
    assert env["CONFIG_PATH"] == "/service/librechat.yaml"
    assert env["LEGACY_ONLY"] == "repo"
    assert env["LEGACY_LOCAL"] == "1"
    assert env["LOCAL_ONLY"] == "1"
    assert env["SERVICE_ONLY"] == "1"


def test_memory_hardening_wrapper_prefers_compiled_runtime_over_ambient_shell_env(
    monkeypatch, tmp_path: Path
) -> None:
    class Args:
        repo_root = ROOT
        command = "status"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        transcripts_dir = None
        transcript_max_files_per_run = None
        transcript_max_chars_per_file = None
        transcript_summary_max_chars = None
        transcript_rag_mode = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        scheduled = False
        json = False

    Args.app_support_dir = tmp_path / "app-support"
    Args.runtime_dir = tmp_path / "app-support" / "runtime"

    class Completed:
        returncode = 0
        stdout = "{}"
        stderr = ""

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setenv("RAG_API_URL", "http://stale-shell-rag")
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)

    status = memory_harden.run_node(
        Args(),
        {
            "RAG_API_URL": "http://compiled-rag",
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-8",
        },
    )

    assert status == 0
    assert calls[0][1]["env"]["RAG_API_URL"] == "http://compiled-rag"


def test_memory_hardening_wrapper_uses_provider_specific_model_for_override() -> None:
    class Args:
        repo_root = ROOT
        app_support_dir = ROOT / ".tmp-app-support"
        runtime_dir = ROOT / ".tmp-runtime"
        command = "dry-run"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = "openai"
        model = None
        proposal_file = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        json = False

    command = memory_harden.node_command(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-8",
            "VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL": "gpt-5.6-sol",
        },
    )

    assert command[command.index("--provider") + 1] == "openai"
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"


def test_memory_hardening_cli_user_email_overrides_compiled_operator_scope() -> None:
    class Args:
        repo_root = ROOT
        app_support_dir = ROOT / ".tmp-app-support"
        runtime_dir = ROOT / ".tmp-runtime"
        command = "dry-run"
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = "explicit@example.com"
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        json = False

    command = memory_harden.node_command(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-8",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "compiled@example.com",
        },
    )

    assert command[command.index("--user-email") + 1] == "explicit@example.com"


def test_ingest_transcripts_defaults_to_zero_saved_memory_changes() -> None:
    class Args:
        repo_root = ROOT
        app_support_dir = ROOT / ".tmp-app-support"
        runtime_dir = ROOT / ".tmp-runtime"
        command = "ingest-transcripts"
        apply = True
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        transcripts_dir = None
        transcript_max_files_per_run = None
        transcript_max_chars_per_file = None
        transcript_summary_max_chars = None
        transcript_reference_memory_max_chars = None
        transcript_reference_messages_max_chars = None
        transcript_rag_mode = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        scheduled = False
        json = False

    command = memory_harden.node_command(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-8",
        },
    )

    assert "--transcripts-only" in command
    assert command[command.index("--max-changes-per-user") + 1] == "0"


class MemoryHardenArgs:
    repo_root = ROOT
    app_support_dir = ROOT
    runtime_dir = ROOT
    command = "ingest-transcripts"
    apply = True
    until_caught_up = False
    mongo_uri = None
    config_path = None
    run_id = None
    user_email = None
    user_id = None
    lookback_days = None
    min_user_idle_minutes = None
    max_changes_per_user = None
    max_input_chars = None
    provider = None
    model = None
    proposal_file = None
    transcripts_dir = None
    transcript_max_files_per_run = None
    transcript_max_chars_per_file = None
    transcript_summary_max_chars = None
    transcript_reference_memory_max_chars = None
    transcript_reference_messages_max_chars = None
    transcript_rag_mode = None
    allow_delete = False
    ignore_idle_gate = False
    ignore_power_gate = False
    ignore_efficiency_gate = False
    interactive_maintenance = False
    skip_model_probe = False
    allow_partial_lookback = False
    scheduled = False
    trigger = None
    json = True


def make_memory_harden_args(**overrides):
    class Args:
        pass

    args = Args()
    for key, value in MemoryHardenArgs.__dict__.items():
        if not key.startswith("__"):
            setattr(args, key, value)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_memory_hardening_power_gate_skips_model_work_on_battery(monkeypatch, capsys) -> None:
    args = make_memory_harden_args()

    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: True)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    monkeypatch.setattr(
        memory_harden,
        "run_node_once",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("model work should not run")),
    )

    status = memory_harden.run_node(args, {})

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert status == 0
    assert payload["status"] == "skipped"
    assert payload["reason"] == "on_battery_power"
    assert payload["users"][0]["status"] == "skipped"


def test_memory_hardening_power_gate_requires_override_env_with_flag(monkeypatch, capsys) -> None:
    args = make_memory_harden_args(ignore_power_gate=True, json=True)

    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: True)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)

    status = memory_harden.run_node(args, {})

    assert status == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "on_battery_power"


def test_memory_hardening_power_gate_allows_explicit_override(monkeypatch) -> None:
    args = make_memory_harden_args(ignore_power_gate=True, json=False)

    class Completed:
        returncode = 0

    calls = []
    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: True)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    monkeypatch.setattr(memory_harden.subprocess, "run", lambda command, **kwargs: calls.append(command) or Completed())

    status = memory_harden.run_node(args, {"VIVENTIUM_MEMORY_HARDENING_ALLOW_POWER_OVERRIDE": "1"})

    assert status == 0
    assert calls
    assert "--transcripts-only" in calls[0]


def test_memory_hardening_efficiency_override_is_separate_from_power_override() -> None:
    args = make_memory_harden_args(ignore_efficiency_gate=True, interactive_maintenance=True)

    command = memory_harden.node_command(
        args,
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-8",
        },
    )

    assert "--ignore-efficiency-gate" in command
    assert "--interactive-maintenance" in command
    assert "--ignore-power-gate" not in command


def test_memory_hardening_ignore_idle_gate_does_not_bypass_power_gate(monkeypatch, capsys) -> None:
    args = make_memory_harden_args(ignore_idle_gate=True)

    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: True)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)

    status = memory_harden.run_node(args, {})

    assert status == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "on_battery_power"


def test_memory_hardening_power_gate_skips_on_thermal_warning(monkeypatch, capsys) -> None:
    args = make_memory_harden_args()

    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: False)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: True)

    status = memory_harden.run_node(args, {})

    assert status == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "thermal_or_performance_warning"


def test_memory_hardening_power_gate_env_can_disable_gate(monkeypatch) -> None:
    args = make_memory_harden_args(json=False)

    class Completed:
        returncode = 0

    calls = []
    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: True)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    monkeypatch.setattr(memory_harden.subprocess, "run", lambda command, **kwargs: calls.append(command) or Completed())

    status = memory_harden.run_node(args, {"VIVENTIUM_MEMORY_HARDENING_POWER_GATE": "off"})

    assert status == 0
    assert calls


def test_ingest_transcripts_until_caught_up_requires_apply() -> None:
    class Args:
        apply = False
        max_batches = 2

    try:
        memory_harden.run_transcript_backfill_until_caught_up(Args(), {}, {})
    except SystemExit as exc:
        assert "--until-caught-up requires --apply" in str(exc)
    else:
        raise AssertionError("expected --until-caught-up dry-run to fail closed")


def test_ingest_transcripts_until_caught_up_defaults_to_single_batch(monkeypatch, capsys) -> None:
    args = make_memory_harden_args(until_caught_up=True, json=True)

    class Completed:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "schemaVersion": 1,
                "run_id": "batch-1",
                "users": [{"transcript_ingest": {"files_skipped_by_cap": 9}}],
                "apply_results": [],
            }
        )

    calls = []
    monkeypatch.setattr(memory_harden, "run_node_once", lambda *_args: calls.append(1) or Completed())

    status = memory_harden.run_transcript_backfill_until_caught_up(args, {}, {})

    assert status == memory_harden.PARTIAL_BACKFILL_EXIT
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "max_batches_reached"


def test_memory_harden_status_does_not_take_global_cli_lock() -> None:
    text = (ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    section = text.split("\n  memory-harden)", 1)[1].split(";;", 1)[0]

    assert 'memory_harden_subcommand="${1:-}"' in section
    assert 'if [[ "$memory_harden_subcommand" != "status" ]]; then' in section
    assert 'acquire_cli_lock "$COMMAND"' in section
    assert 'compile_config >/dev/null' in section


def test_ingest_transcripts_until_caught_up_stops_when_batches_drain(monkeypatch) -> None:
    class Args:
        repo_root = ROOT
        apply = True
        max_batches = 3

    class Completed:
        def __init__(self, skipped: int):
            self.returncode = 0
            self.stderr = ""
            self.stdout = json.dumps(
                {
                    "schemaVersion": 1,
                    "run_id": f"run-{skipped}",
                    "users": [
                        {
                            "transcript_ingest": {
                                "files_skipped_by_cap": skipped,
                            }
                        }
                    ],
                }
            )

    calls: list[int] = []

    def fake_run_once(args, runtime_env, env):
        skipped = [2, 0][len(calls)]
        calls.append(skipped)
        return Completed(skipped)

    monkeypatch.setattr(memory_harden, "run_node_once", fake_run_once)

    assert memory_harden.run_transcript_backfill_until_caught_up(Args(), {}, {}) == 0
    assert calls == [2, 0]


def test_ingest_transcripts_until_caught_up_json_outputs_final_aggregate(monkeypatch, capsys) -> None:
    class Args:
        repo_root = ROOT
        apply = True
        max_batches = 3
        json = True

    class Completed:
        def __init__(self, skipped: int):
            self.returncode = 0
            self.stderr = ""
            self.stdout = json.dumps(
                {
                    "schemaVersion": 1,
                    "run_id": f"run-{skipped}",
                    "users": [
                        {
                            "status": "proposed",
                            "transcript_ingest": {
                                "files_seen": 2,
                                "files_skipped_by_cap": skipped,
                            },
                        }
                    ],
                    "apply_results": [{"transcript_vectors": {"uploaded": 1}}],
                }
            )

    calls: list[int] = []

    def fake_run_once(args, runtime_env, env):
        skipped = [2, 0][len(calls)]
        calls.append(skipped)
        return Completed(skipped)

    monkeypatch.setattr(memory_harden, "run_node_once", fake_run_once)

    assert memory_harden.run_transcript_backfill_until_caught_up(Args(), {}, {}) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "complete"
    assert payload["batches_run"] == 2
    assert payload["batch_run_ids"] == ["run-2", "run-0"]
    assert payload["users"][0]["transcript_ingest"]["files_skipped_by_cap"] == 0
    assert payload["apply_results"][0]["transcript_vectors"]["uploaded"] == 1


def test_ingest_transcripts_until_caught_up_stops_on_no_progress(monkeypatch, capsys) -> None:
    class Args:
        repo_root = ROOT
        apply = True
        max_batches = 4

    class Completed:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "schemaVersion": 1,
                "run_id": "same",
                "users": [{"transcript_ingest": {"files_skipped_by_cap": 3}}],
            }
        )

    calls = 0

    def fake_run_once(args, runtime_env, env):
        nonlocal calls
        calls += 1
        return Completed()

    monkeypatch.setattr(memory_harden, "run_node_once", fake_run_once)

    assert (
        memory_harden.run_transcript_backfill_until_caught_up(Args(), {}, {})
        == memory_harden.PARTIAL_BACKFILL_EXIT
    )
    assert calls == 2
    assert "no_batch_progress" in capsys.readouterr().out


def test_ingest_transcripts_until_caught_up_exits_partial_on_max_batches(monkeypatch, capsys) -> None:
    class Args:
        repo_root = ROOT
        apply = True
        max_batches = 2

    class Completed:
        def __init__(self, skipped: int):
            self.stdout = json.dumps(
                {
                    "schemaVersion": 1,
                    "run_id": f"still-pending-{skipped}",
                    "users": [{"transcript_ingest": {"files_skipped_by_cap": skipped}}],
                }
            )

        returncode = 0
        stderr = ""

    calls = 0

    def fake_run_once(args, runtime_env, env):
        nonlocal calls
        skipped = [3, 2][calls]
        calls += 1
        return Completed(skipped)

    monkeypatch.setattr(memory_harden, "run_node_once", fake_run_once)

    assert (
        memory_harden.run_transcript_backfill_until_caught_up(Args(), {}, {})
        == memory_harden.PARTIAL_BACKFILL_EXIT
    )
    assert calls == 2
    assert "max_batches_reached" in capsys.readouterr().out


def test_memory_hardening_schedule_runs_wrapper_directly_without_cli_lock(tmp_path, monkeypatch) -> None:
    plist_path = tmp_path / "ai.viventium.memory-harden.plist"
    app_support_dir = tmp_path / "app-support"
    runtime_dir = app_support_dir / "runtime"

    class Args:
        pass

    args = Args()
    args.repo_root = ROOT
    args.app_support_dir = app_support_dir
    args.runtime_dir = runtime_dir
    args.schedule = None
    args.user_email = None

    class Completed:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    launchctl_calls = []
    launchd = {"loaded": False}

    def fake_run(command, **kwargs):
        launchctl_calls.append(command)
        if command[0:2] == ["launchctl", "print"]:
            return Completed(0 if launchd["loaded"] else 113)
        if command[0:2] == ["launchctl", "bootstrap"]:
            launchd["loaded"] = True
        elif command[0:2] == ["launchctl", "bootout"]:
            launchd["loaded"] = False
        return Completed()

    monkeypatch.setattr(memory_harden, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)
    monkeypatch.setattr(memory_harden.sys, "platform", "darwin")

    result = memory_harden.install_schedule(
        args,
        {
            "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": "0 3 * * *",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "qa@example.com",
        },
    )
    payload = plistlib.loads(plist_path.read_bytes())
    program_arguments = payload["ProgramArguments"]

    assert result["schedule"] == "0 3 * * *"
    assert result["action"] == "install"
    assert result["changed"] is True
    assert result["loaded"] is True
    assert payload["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
    assert "StartInterval" not in payload
    assert payload["WorkingDirectory"] == str(app_support_dir)
    assert program_arguments[0:2] == ["/usr/bin/env", "-i"]
    assert "/bin/bash" not in program_arguments
    assert "-lc" not in program_arguments
    assert any(
        f"PATH={Path.home()}/.local/bin:{Path.home()}/.codex/bin:" in item
        for item in program_arguments
    )
    assert any(item == "/Applications/Codex.app/Contents/Resources" or "/Applications/Codex.app/Contents/Resources" in item for item in program_arguments)
    assert any("/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" in item for item in program_arguments)
    assert "bin/viventium" not in " ".join(program_arguments)
    assert str(ROOT / "scripts" / "viventium" / "memory_harden.py") in program_arguments
    assert "--runtime-dir" in program_arguments
    assert program_arguments[program_arguments.index("--user-email") + 1] == "qa@example.com"
    assert program_arguments[-6:] == [
        "apply",
        "--scheduled",
        "--trigger",
        "launchd",
        "--user-email",
        "qa@example.com",
    ]
    assert [call[0:2] for call in launchctl_calls].count(["launchctl", "bootstrap"]) == 1
    assert launchctl_calls[-1][0:2] == ["launchctl", "print"]

    launchctl_calls.clear()
    second = memory_harden.install_schedule(
        args,
        {
            "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": "0 3 * * *",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "qa@example.com",
        },
    )
    assert second["action"] == "noop"
    assert second["changed"] is False
    assert [call[0:2] for call in launchctl_calls] == [["launchctl", "print"]]

    receipts = sorted(memory_harden.schedule_lifecycle_events_dir(app_support_dir).glob("event-*.json"))
    assert len(receipts) == 2
    receipt = json.loads(receipts[-1].read_text(encoding="utf-8"))
    assert receipt["action"] == "noop"
    assert receipt["status"] == "success"
    assert receipt["loaded_verified"] is True
    assert receipt["generation_hash"]
    public_blob = json.dumps(receipt)
    assert str(tmp_path) not in public_blob
    assert "qa@example.com" not in public_blob


def test_memory_hardening_schedule_repairs_drift_once_and_verifies_reload(tmp_path, monkeypatch) -> None:
    plist_path = tmp_path / "ai.viventium.memory-harden.plist"
    app_support_dir = tmp_path / "app-support"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=app_support_dir / "runtime",
        command="install-schedule",
        json=True,
    )
    args.schedule = "0 4 * * *"
    args.user_email = None
    plist_path.write_bytes(
        plistlib.dumps(
            {
                "Label": memory_harden.LAUNCH_AGENT_LABEL,
                "ProgramArguments": ["stale"],
                "StartCalendarInterval": {"Hour": 3, "Minute": 0},
                "StartInterval": 3600,
            }
        )
    )
    launchd = {"loaded": True}
    calls = []

    class Completed:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, **_kwargs):
        calls.append(command)
        if command[0:2] == ["launchctl", "print"]:
            return Completed(0 if launchd["loaded"] else 113)
        if command[0:2] == ["launchctl", "bootout"]:
            launchd["loaded"] = False
        if command[0:2] == ["launchctl", "bootstrap"]:
            launchd["loaded"] = True
        return Completed()

    monkeypatch.setattr(memory_harden, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)
    monkeypatch.setattr(memory_harden.sys, "platform", "darwin")

    result = memory_harden.install_schedule(args, {})

    payload = plistlib.loads(plist_path.read_bytes())
    assert result["action"] == "reinstall"
    assert payload["StartCalendarInterval"] == {"Hour": 4, "Minute": 0}
    assert "StartInterval" not in payload
    assert [call[0:2] for call in calls].count(["launchctl", "bootout"]) == 1
    assert [call[0:2] for call in calls].count(["launchctl", "bootstrap"]) == 1


def test_memory_hardening_schedule_bootstraps_matching_unloaded_agent_without_bootout(
    tmp_path, monkeypatch
) -> None:
    plist_path = tmp_path / "ai.viventium.memory-harden.plist"
    app_support_dir = tmp_path / "app-support"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=app_support_dir / "runtime",
        command="install-schedule",
        json=True,
    )
    args.schedule = "0 3 * * *"
    args.user_email = None
    desired = memory_harden.desired_launch_agent_payload(args, {}, args.schedule)
    plist_path.write_bytes(plistlib.dumps(desired))
    launchd = {"loaded": False}
    calls = []

    class Completed:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, **_kwargs):
        calls.append(command)
        if command[0:2] == ["launchctl", "print"]:
            return Completed(0 if launchd["loaded"] else 113)
        if command[0:2] == ["launchctl", "bootstrap"]:
            launchd["loaded"] = True
        return Completed()

    monkeypatch.setattr(memory_harden, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)
    monkeypatch.setattr(memory_harden.sys, "platform", "darwin")

    result = memory_harden.install_schedule(args, {})

    assert result["action"] == "bootstrap"
    assert [call[0:2] for call in calls].count(["launchctl", "bootout"]) == 0
    assert [call[0:2] for call in calls].count(["launchctl", "bootstrap"]) == 1


def test_memory_hardening_schedule_records_failed_post_bootstrap_verification(
    tmp_path, monkeypatch
) -> None:
    plist_path = tmp_path / "ai.viventium.memory-harden.plist"
    app_support_dir = tmp_path / "app-support"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=app_support_dir / "runtime",
        command="install-schedule",
        json=True,
    )
    args.schedule = "0 3 * * *"
    args.user_email = None

    class Completed:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, **_kwargs):
        if command[0:2] == ["launchctl", "print"]:
            return Completed(113)
        return Completed()

    monkeypatch.setattr(memory_harden, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)
    monkeypatch.setattr(memory_harden.sys, "platform", "darwin")

    try:
        memory_harden.install_schedule(args, {})
        raise AssertionError("expected failed post-bootstrap verification")
    except SystemExit as exc:
        assert "failed to install" in str(exc)

    receipt = json.loads(
        (memory_harden.schedule_lifecycle_events_dir(app_support_dir) / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["status"] == "failed"
    assert receipt["error_class"] == "launchctl_verify_failed"
    assert receipt["loaded_verified"] is False


def test_memory_hardening_schedule_records_failed_bootout(tmp_path, monkeypatch) -> None:
    plist_path = tmp_path / "ai.viventium.memory-harden.plist"
    app_support_dir = tmp_path / "app-support"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=app_support_dir / "runtime",
        command="install-schedule",
        json=True,
    )
    args.schedule = "0 4 * * *"
    args.user_email = None
    plist_path.write_bytes(
        plistlib.dumps(
            {
                "Label": memory_harden.LAUNCH_AGENT_LABEL,
                "ProgramArguments": ["stale"],
                "StartCalendarInterval": {"Hour": 3, "Minute": 0},
            }
        )
    )

    class Completed:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, **_kwargs):
        if command[0:2] == ["launchctl", "print"]:
            return Completed(0)
        if command[0:2] == ["launchctl", "bootout"]:
            return Completed(1, stderr="synthetic bootout failure")
        return Completed()

    monkeypatch.setattr(memory_harden, "launch_agent_path", lambda: plist_path)
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)
    monkeypatch.setattr(memory_harden.sys, "platform", "darwin")

    try:
        memory_harden.install_schedule(args, {})
        raise AssertionError("expected bootout failure")
    except SystemExit as exc:
        assert "failed to unload" in str(exc)

    receipt = json.loads(
        (memory_harden.schedule_lifecycle_events_dir(app_support_dir) / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["status"] == "failed"
    assert receipt["error_class"] == "launchctl_bootout_failed"
    assert receipt["bootout_returncode"] == 1


def test_memory_hardening_schedule_loader_lock_serializes_processes(tmp_path) -> None:
    if memory_harden.fcntl is None:
        return
    app_support_dir = tmp_path / "app-support"
    ready_path = tmp_path / "child-ready"
    acquired_path = tmp_path / "child-acquired"
    child = """
from pathlib import Path
import sys
from scripts.viventium import memory_harden

app_support = Path(sys.argv[1])
Path(sys.argv[2]).write_text("ready", encoding="utf-8")
with memory_harden.schedule_loader_lock(app_support):
    Path(sys.argv[3]).write_text("acquired", encoding="utf-8")
"""
    process = None
    with memory_harden.schedule_loader_lock(app_support_dir):
        process = subprocess.Popen(
            [sys.executable, "-c", child, str(app_support_dir), str(ready_path), str(acquired_path)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 5
        while not ready_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready_path.exists()
        time.sleep(0.1)
        assert not acquired_path.exists()

    assert process is not None
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stderr or stdout
    assert acquired_path.exists()


def test_memory_hardening_config_sync_uninstalls_only_explicit_false() -> None:
    source = (ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    block = source.split("sync_memory_hardening_schedule() {", 1)[1].split(
        "\n}\n\napply_default_nightly_routines()", 1
    )[0]

    assert 'elif [[ "$enabled" == "false" && -f "$plist_path" ]]' in block
    assert 'elif [[ -f "$plist_path" ]]' not in block
    assert "preserving the existing LaunchAgent" in block


def test_memory_hardening_status_process_is_not_niced() -> None:
    kwargs = memory_harden.model_subprocess_kwargs(
        capture_output=True,
        lower_priority=False,
    )

    assert kwargs == {"text": True, "capture_output": True}


def test_memory_hardening_scheduled_trigger_writes_public_safe_receipt(tmp_path, monkeypatch) -> None:
    app_support_dir = tmp_path / "app-support"
    runtime_dir = app_support_dir / "runtime"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=runtime_dir,
        command="apply",
        scheduled=True,
        trigger="launchd",
        json=False,
    )

    class Completed:
        returncode = 0

    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: False)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    monkeypatch.setattr(memory_harden.subprocess, "run", lambda *_args, **_kwargs: Completed())

    status = memory_harden.run_node(
        args,
        {
            "VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST": "false",
            "VIVENTIUM_MEMORY_HARDENING_SCHEDULE": "0 3 * * *",
            "VIVENTIUM_MEMORY_HARDENING_TIMEZONE": "America/Toronto",
        },
    )

    events = list(memory_harden.trigger_events_dir(app_support_dir).glob("*.json"))
    assert status == 0
    assert len(events) == 1
    payload = json.loads(events[0].read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == memory_harden.TRIGGER_EVENT_SCHEMA_VERSION
    assert payload["status"] == "success"
    assert payload["trigger_source"] == "launchd"
    assert payload["scheduled_invocation"] is True
    assert payload["schedule_label"] == memory_harden.LAUNCH_AGENT_LABEL
    assert payload["schedule"]["hour"] == 3
    assert payload["schedule"]["minute"] == 0
    assert payload["timezone_at_fire"]
    assert payload["exit_code"] == 0
    assert "repo_root_hash" in payload
    assert "runtime_dir_hash" in payload
    public_blob = json.dumps(payload)
    assert str(tmp_path) not in public_blob
    assert "qa@example.com" not in public_blob


def test_memory_hardening_manual_run_does_not_write_scheduled_trigger_receipt(tmp_path, monkeypatch) -> None:
    app_support_dir = tmp_path / "app-support"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=app_support_dir / "runtime",
        command="apply",
        scheduled=False,
        trigger=None,
        json=False,
    )

    class Completed:
        returncode = 0

    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: False)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    monkeypatch.setattr(memory_harden.subprocess, "run", lambda *_args, **_kwargs: Completed())

    status = memory_harden.run_node(
        args,
        {"VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST": "false"},
    )

    assert status == 0
    assert not memory_harden.trigger_events_dir(app_support_dir).exists()


def test_memory_hardening_scheduled_power_skip_finalizes_trigger_receipt(tmp_path, monkeypatch) -> None:
    app_support_dir = tmp_path / "app-support"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=app_support_dir / "runtime",
        command="apply",
        scheduled=True,
        trigger="launchd",
        json=True,
    )

    calls = []
    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: True)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    monkeypatch.setattr(memory_harden.subprocess, "run", lambda *_args, **_kwargs: calls.append(1))

    status = memory_harden.run_node(args, {})

    events = list(memory_harden.trigger_events_dir(app_support_dir).glob("*.json"))
    assert status == 0
    assert calls == []
    assert len(events) == 1
    payload = json.loads(events[0].read_text(encoding="utf-8"))
    assert payload["status"] == "skipped"
    assert payload["reason"] == "on_battery_power"
    assert payload["trigger_source"] == "launchd"


def test_memory_hardening_dry_run_first_receipt_records_executed_command(tmp_path, monkeypatch) -> None:
    app_support_dir = tmp_path / "app-support"
    args = make_memory_harden_args(
        repo_root=ROOT,
        app_support_dir=app_support_dir,
        runtime_dir=app_support_dir / "runtime",
        command="apply",
        scheduled=True,
        trigger="launchd",
        json=False,
    )

    class Completed:
        returncode = 0

    calls = []
    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: False)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    def fake_run(command, **kwargs):
        calls.append(command)
        return Completed()

    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)

    status = memory_harden.run_node(args, {"VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST": "true"})

    events = list(memory_harden.trigger_events_dir(app_support_dir).glob("*.json"))
    assert status == 0
    assert len(events) == 1
    assert calls and "--mode" in calls[0]
    assert calls[0][calls[0].index("--mode") + 1] == "dry-run"
    payload = json.loads(events[0].read_text(encoding="utf-8"))
    assert payload["command"] == "apply"
    assert payload["executed_command"] == "dry-run"


def test_memory_hardening_cli_reexecs_active_runtime_checkout() -> None:
    text = (ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    reexec_section = text.split("maybe_reexec_active_runtime_checkout() {", 1)[1].split(
        "yaml_file_has_unique_mapping_keys()",
        1,
    )[0]

    for command in [
        "start",
        "launch",
        "stop",
        "install-helper",
        "uninstall-helper",
        "status-bar",
        "memory-harden",
        "transcripts",
    ]:
        assert command in reexec_section


def test_scheduled_transcript_ingest_honors_dry_run_first_marker(tmp_path, monkeypatch) -> None:
    class Args:
        repo_root = ROOT
        command = "ingest-transcripts"
        apply = True
        mongo_uri = None
        config_path = None
        run_id = None
        user_email = None
        user_id = None
        lookback_days = None
        min_user_idle_minutes = None
        max_changes_per_user = None
        max_input_chars = None
        provider = None
        model = None
        proposal_file = None
        transcripts_dir = None
        transcript_max_files_per_run = None
        transcript_max_chars_per_file = None
        transcript_summary_max_chars = None
        transcript_rag_mode = None
        allow_delete = False
        ignore_idle_gate = False
        skip_model_probe = False
        allow_partial_lookback = False
        scheduled = True
        json = False

    Args.app_support_dir = tmp_path / "app-support"
    Args.runtime_dir = tmp_path / "app-support" / "runtime"

    class Completed:
        returncode = 0

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return Completed()

    monkeypatch.setattr(memory_harden, "running_on_battery_power", lambda: False)
    monkeypatch.setattr(memory_harden, "thermal_state_constrained", lambda: False)
    monkeypatch.setattr(memory_harden.subprocess, "run", fake_run)

    status = memory_harden.run_node(
        Args(),
        {
            "VIVENTIUM_MEMORY_HARDENING_PROVIDER": "anthropic",
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-8",
            "VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST": "true",
        },
    )

    marker = Args.app_support_dir / "state" / "memory-hardening" / "dry-run-first-complete"
    assert status == 0
    assert marker.exists()
    assert calls and calls[0][calls[0].index("--mode") + 1] == "dry-run"
    assert "--transcripts-only" in calls[0]


def test_memory_hardening_public_audit_contract_has_no_raw_path_field() -> None:
    script = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    text = script.read_text(encoding="utf-8")

    assert "raw_proposal_path" not in text
    assert "private_proposal_file" in text
    assert re.search(r"proposal\.private\.json", text)
    assert re.search(r"rollback\.private\.json", text)


def test_memory_unique_index_migration_is_dry_run_first_and_non_destructive() -> None:
    launcher = (ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    migration = (
        ROOT
        / "viventium_v0_4"
        / "LibreChat"
        / "scripts"
        / "viventium-memory-dedupe.js"
    ).read_text(encoding="utf-8")

    assert "ensure_memory_unique_indexes_if_clean()" in launcher
    section = launcher.split("ensure_memory_unique_indexes_if_clean()", 1)[1].split("\n}\n", 1)[0]
    assert "--dry-run" in section
    assert "--apply" in section
    assert "--create-indexes" in section
    assert section.index("--dry-run") < section.index("--apply")
    assert "duplicateGroups" in section
    assert "autoIndex: false" in migration


def test_memory_hardening_treats_listen_only_as_soft_transcript_evidence() -> None:
    script = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    text = script.read_text(encoding="utf-8")

    assert "type === 'listen_only_transcript'" in text
    assert "role \"ambient_transcript\"" in text
    assert "listen_only_memory_requires_user_conversation_corroboration" in text
    assert "stable_memory_requires_user_conversation_corroboration" in text
    assert "identity_memory_requires_conversation_corroboration" in text
    assert "listenOnlyConversationSourceIds" in text


def test_transcript_identity_memory_requires_chat_corroboration() -> None:
    script = ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    source = script.read_text(encoding="utf-8")
    memory_doc = (ROOT / "docs/requirements_and_learnings/20_Memory_System.md").read_text(encoding="utf-8")
    cases = (ROOT / "qa/meeting-transcript-memory/cases.md").read_text(encoding="utf-8")
    hardener_prompt = (
        ROOT / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/memory/hardener_consolidation.md"
    ).read_text(encoding="utf-8")
    summarizer_prompt = (
        ROOT / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/memory/transcript_summarizer.md"
    ).read_text(encoding="utf-8")

    assert "const TRANSCRIPT_IDENTITY_MEMORY_KEYS = new Set(['core', 'me']);" in source
    assert "identity_memory_requires_conversation_corroboration" in source
    assert "stable_memory_requires_user_conversation_corroboration" in source
    assert "validUserConversationMessageIds" in source
    assert "assistant restatements do not count as corroboration" in hardener_prompt
    assert "not enough for durable memory" in hardener_prompt
    assert "speaker attribution is unreliable" in summarizer_prompt
    assert "Stable durable keys (`core`, `me`, `preferences`," in memory_doc
    assert "user-authored chat/conversation corroboration" in memory_doc
    assert "Other stable keys such as `preferences`, `world`, and `signals` may use two recent" not in memory_doc
    assert "MTM-015" in cases


def test_memory_hardening_docs_keep_private_artifacts_out_of_public_qa() -> None:
    boundary_doc = ROOT / "docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md"
    qa_readme = ROOT / "qa/memory-hardening/README.md"

    boundary_text = boundary_doc.read_text(encoding="utf-8")
    qa_text = qa_readme.read_text(encoding="utf-8")

    assert "proposal.private.json" in boundary_text
    assert "rollback.private.json" in boundary_text
    assert "Raw proposals and rollback snapshots stay under local App Support state" in qa_text


def test_meeting_transcript_eval_fixtures_are_executable() -> None:
    subprocess.run(
        [sys.executable, "-c", "import shutil, sys; sys.exit(0 if shutil.which('node') else 1)"],
        check=True,
    )
    subprocess.run(
        ["node", str(ROOT / "qa/meeting-transcript-memory/evals/run-evals.cjs")],
        check=True,
        cwd=ROOT,
    )


def test_meeting_transcript_recall_dist_bundle_contains_runtime_hooks() -> None:
    dist = ROOT / "viventium_v0_4" / "LibreChat" / "packages" / "api" / "dist" / "index.js"
    text = dist.read_text(encoding="utf-8")

    assert "viventiumMeetingTranscriptRecall: true" in text
    assert "FileContext.meeting_transcript" in text
    assert "metadata.meetingTranscriptSourcePathHash" in text
    assert "metadata.meetingTranscriptKind" in text
    assert "Meeting transcript recall configured but no artifacts for active user" in text
