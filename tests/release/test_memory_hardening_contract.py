from __future__ import annotations

import importlib.util
import json
import plistlib
import re
import subprocess
import sys
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
    assert settings["anthropic_effort"] == "xhigh"
    assert settings["openai_reasoning_effort"] == "xhigh"
    assert settings["transcripts"]["rag_mode"] == "detailed_summary_only"
    assert settings["transcripts"]["min_files_per_run"] == 5
    assert settings["transcripts"]["max_batches_per_invocation"] == 1
    assert settings["transcripts"]["reference_memory_max_chars"] == 24000
    assert settings["transcripts"]["reference_messages_max_chars"] == 36000


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
process.env.VIVENTIUM_MEMORY_HARDENING_MODEL_FALLBACKS = 'anthropic:opus:xhigh,openai:gpt-5.5:high';
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
    assert any(candidate["model"] == "claude-opus-4-7" for candidate in payload["defaultCandidates"])
    assert any(candidate["model"] == "opus" for candidate in payload["defaultCandidates"])
    assert any(candidate["provider"] == "openai" for candidate in payload["explicitCandidates"])


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
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "gpt-5.5",
            "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL": "qa@example.com",
            "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE": "detailed_summary_only",
        },
    )

    assert command[command.index("--provider") + 1] == "openai"
    assert command[command.index("--model") + 1] == "gpt-5.5"
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
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
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
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
            "VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL": "gpt-5.5",
        },
    )

    assert command[command.index("--provider") + 1] == "openai"
    assert command[command.index("--model") + 1] == "gpt-5.5"


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
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
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
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
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
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
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
        returncode = 0
        stdout = ""
        stderr = ""

    launchctl_calls = []

    def fake_run(command, **kwargs):
        launchctl_calls.append(command)
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
    assert payload["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
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
    assert program_arguments[-4:] == ["apply", "--scheduled", "--user-email", "qa@example.com"]
    assert launchctl_calls[-1][0:2] == ["launchctl", "bootstrap"]


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
            "VIVENTIUM_MEMORY_HARDENING_MODEL": "claude-opus-4-7",
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
