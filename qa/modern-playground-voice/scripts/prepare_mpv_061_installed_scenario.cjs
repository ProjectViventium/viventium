#!/usr/bin/env node
"use strict";

/*
 * Prepare private MPV-061 inputs only. This file does not start a browser, call a model,
 * create an account, touch a database, or restart a service.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createRequire } = require("node:module");
const { spawnSync } = require("node:child_process");

const CASE_ID = "MPV-061";
const RELEASE_LABEL = "PRE-GATE / NOT READY";
const SCENARIO_SCHEMA = "viventium.voice.mpv-061.installed-journey-scenario.v1";
const RUNTIME_HANDOFF_SCHEMA = "viventium.voice.mpv-061.runtime-handoff.v1";
const INITIAL_SILENCE_SECONDS = 25;
const BETWEEN_TURN_SILENCE_SECONDS = 35;
const MODE_ARM_LEAD_MS = 20_000;
const ROOT = fs.realpathSync(path.resolve(__dirname, "..", "..", ".."));
const RUNNER_PATH = path.join(__dirname, "run_mpv_061_installed_journey.cjs");
const RELEASE_GATE_PATH = path.join(
  ROOT,
  "scripts",
  "viventium",
  "parallel_work_release_gate.py",
);
const AGENT_SOURCE_PATH = path.join(
  ROOT,
  "viventium_v0_4",
  "LibreChat",
  "viventium",
  "source_of_truth",
  "local.viventium-agents.yaml",
);
const APP_SUPPORT_ROOT = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
);
const OWNER_STATE_PATH = path.join(
  APP_SUPPORT_ROOT,
  "state",
  "runtime",
  "isolated",
  "stack-owner.json",
);
const REQUIRED_IDENTITY_CHECKS = Object.freeze([
  "SOURCE-IDENTITY",
  "NESTED-PINS",
  "PREBUILT-IDENTITY",
  "INSTALLED-ARTIFACT",
]);
const HEX_64 = /^[a-f0-9]{64}$/;
const SAFE_BLOCKER = /^[a-z][a-z0-9_]{0,79}$/;
const REQUIRED_EFFECT_PLANES = Object.freeze([
  "launch",
  "control",
  "tool",
  "controller",
  "cortex",
  "liveMemory",
  "recall",
  "titleModel",
  "response",
  "tts",
  "audio",
]);
const RESTART_ARGUMENTS = Object.freeze([
  "dev-runtime",
  "activate-current",
  "--validate",
  "--restart",
  "--allow-protected-folder",
  "--allow-dirty-local-testing",
]);

const SCENARIO_TURNS = Object.freeze([
  Object.freeze({
    kind: "authorizedCallLaunch",
    mode: "call",
    directlyAddressed: true,
    expectedTranscript:
      "Begin synthetic mission alpha and synthetic mission bravo",
    speech:
      "Viventium. Begin synthetic mission alpha and synthetic mission bravo as two independent workers. " +
      "Mission alpha must wait for its alpha attachment and return mpv zero five four worker alpha result dot text. " +
      "Mission bravo must wait for its bravo attachment and return mpv zero five four worker bravo result dot text.",
  }),
  Object.freeze({
    kind: "trustedWingLaunch",
    mode: "wing",
    directlyAddressed: true,
    expectedTranscript: "Launch the temporary wing probe worker now",
    speech:
      "Viventium. Launch the temporary wing probe worker now, and keep it separate from mission alpha and mission bravo.",
  }),
  Object.freeze({
    kind: "quickConversation",
    mode: "call",
    directlyAddressed: true,
    expectedTranscript: "Tell me one short fact about the color blue",
    speech:
      "Viventium. Tell me one short fact about the color blue while those workers continue.",
  }),
  Object.freeze({
    kind: "authorizedCallControl",
    mode: "call",
    directlyAddressed: true,
    expectedTranscript: "Steer mission alpha only",
    speech:
      "Viventium. Steer mission alpha only. Tell it to add the exact word sapphire to its result. Do not change mission bravo.",
  }),
  Object.freeze({
    kind: "trustedWingControl",
    mode: "wing",
    directlyAddressed: true,
    expectedTranscript: "Steer mission alpha only",
    speech:
      "Viventium. Steer mission alpha only. Tell it to preserve the exact number twenty seven in its result. Do not change mission bravo.",
  }),
  Object.freeze({
    kind: "passiveWingDenial",
    mode: "wing",
    directlyAddressed: false,
    expectedTranscript: "The blue folder can wait until tomorrow",
    speech:
      "The blue folder can wait until tomorrow. No one needs to do anything about it now.",
  }),
  Object.freeze({
    kind: "listenOnlyDenial",
    mode: "listen_only",
    directlyAddressed: true,
    expectedTranscript: "Launch a third synthetic worker now",
    speech:
      "Viventium. Launch a third synthetic worker now and have it create another file.",
  }),
  Object.freeze({
    kind: "unverifiedWingDenial",
    mode: "wing",
    directlyAddressed: true,
    speakerRole: "alternate",
    expectedTranscript: "Launch an unverified synthetic worker now",
    speech:
      "Viventium. Launch an unverified synthetic worker now and have it create another file.",
  }),
]);

class PreparationBlocked extends Error {
  constructor(code) {
    const safe = SAFE_BLOCKER.test(String(code || ""))
      ? String(code)
      : "scenario_preparation_blocked";
    super(safe);
    this.name = "PreparationBlocked";
    this.code = safe;
  }
}

function blocked(code) {
  throw new PreparationBlocked(code);
}

function record(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function exactOwner(metadata) {
  return (
    typeof process.getuid !== "function" || metadata.uid === process.getuid()
  );
}

function ownsPath(candidate, root) {
  const relative = path.relative(root, candidate);
  return (
    relative.length > 0 &&
    relative !== ".." &&
    !relative.startsWith(".." + path.sep) &&
    !path.isAbsolute(relative)
  );
}

function rejectSymlinkComponents(candidate, label) {
  const absolute = path.resolve(candidate);
  const parsed = path.parse(absolute);
  const parts = absolute
    .slice(parsed.root.length)
    .split(path.sep)
    .filter(Boolean);
  let current = parsed.root;
  for (const part of parts) {
    current = path.join(current, part);
    try {
      if (fs.lstatSync(current).isSymbolicLink())
        blocked(label + "_symlink_forbidden");
    } catch (error) {
      if (error instanceof PreparationBlocked) throw error;
      if (error?.code === "ENOENT") return;
      blocked(label + "_unavailable");
    }
  }
}

function inspectPrivateRoot(value, { create = false } = {}) {
  if (typeof value !== "string" || !value.trim())
    blocked("evidence_root_unavailable");
  const selected = path.resolve(value);
  if (
    selected === path.parse(selected).root ||
    selected === ROOT ||
    ownsPath(selected, ROOT)
  ) {
    blocked("evidence_root_not_private");
  }
  rejectSymlinkComponents(selected, "evidence_root");
  if (!fs.existsSync(selected)) {
    if (!create) return selected;
    fs.mkdirSync(selected, { mode: 0o700, recursive: false });
  }
  const metadata = fs.lstatSync(selected);
  if (
    !metadata.isDirectory() ||
    !exactOwner(metadata) ||
    (metadata.mode & 0o777) !== 0o700
  ) {
    blocked("evidence_root_not_private");
  }
  return fs.realpathSync(selected);
}

function readJson(file, label, { privateFile = true } = {}) {
  let descriptor;
  try {
    const selected = fs.realpathSync(path.resolve(file));
    descriptor = fs.openSync(
      selected,
      fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0),
    );
    const metadata = fs.fstatSync(descriptor);
    if (
      !metadata.isFile() ||
      !exactOwner(metadata) ||
      metadata.nlink !== 1 ||
      (privateFile && (metadata.mode & 0o077) !== 0)
    ) {
      blocked(label + "_not_private");
    }
    const bytes = fs.readFileSync(descriptor);
    if (bytes.length < 2 || bytes.length > 1024 * 1024)
      blocked(label + "_invalid");
    const parsed = JSON.parse(bytes.toString("utf8"));
    if (!record(parsed)) blocked(label + "_invalid");
    return parsed;
  } catch (error) {
    if (error instanceof PreparationBlocked) throw error;
    blocked(label + "_unavailable");
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function readText(
  file,
  label,
  { privateFile = false, maximumBytes = 2 * 1024 * 1024 } = {},
) {
  let descriptor;
  try {
    const selected = fs.realpathSync(path.resolve(file));
    descriptor = fs.openSync(
      selected,
      fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0),
    );
    const metadata = fs.fstatSync(descriptor);
    if (
      !metadata.isFile() ||
      !exactOwner(metadata) ||
      metadata.nlink !== 1 ||
      (privateFile && (metadata.mode & 0o077) !== 0) ||
      metadata.size < 1 ||
      metadata.size > maximumBytes
    ) {
      blocked(label + "_invalid");
    }
    return fs.readFileSync(descriptor, "utf8");
  } catch (error) {
    if (error instanceof PreparationBlocked) throw error;
    blocked(label + "_unavailable");
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function parseYaml(value, label) {
  try {
    const requireFromLibreChat = createRequire(
      path.join(ROOT, "viventium_v0_4", "LibreChat", "package.json"),
    );
    const parsed = requireFromLibreChat("yaml").parse(value);
    if (!record(parsed)) blocked(label + "_invalid");
    return parsed;
  } catch (error) {
    if (error instanceof PreparationBlocked) throw error;
    blocked(label + "_invalid");
  }
}

function parseRuntimeMetadata(runtimeRoot) {
  const allowed = new Set([
    "MONGO_URI",
    "VIVENTIUM_LC_FRONTEND_PORT",
    "VIVENTIUM_MAIN_AGENT_ID",
    "VIVENTIUM_PLAYGROUND_PORT",
    "VIVENTIUM_PLAYGROUND_URL",
    "VIVENTIUM_VOICE_GATEWAY_HEALTH_PORT",
  ]);
  const values = {};
  for (const relative of [
    "runtime.env",
    "runtime.local.env",
    path.join("service-env", "librechat.env"),
    path.join("service-env", "librechat.owner.env"),
  ]) {
    const selected = path.join(runtimeRoot, relative);
    if (!fs.existsSync(selected)) continue;
    for (const line of readText(selected, "installed_runtime_metadata", {
      privateFile: true,
    }).split(/\r?\n/)) {
      const separator = line.indexOf("=");
      if (separator < 1) continue;
      const key = line.slice(0, separator).trim();
      if (!allowed.has(key)) continue;
      let value = line.slice(separator + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      if (Object.hasOwn(values, key) && values[key] !== value) {
        blocked("installed_runtime_metadata_conflict");
      }
      values[key] = value;
    }
  }
  return values;
}

function resolveConfiguredIdentity(config, agents, installed) {
  const configuredAgentId = String(
    config?.agents?.default_main_agent_id || "",
  ).trim();
  const main = agents?.mainAgent;
  const sourceAgentId = String(main?.id || "").trim();
  const installedAgentId = String(
    installed?.VIVENTIUM_MAIN_AGENT_ID || "",
  ).trim();
  if (
    !configuredAgentId ||
    !sourceAgentId ||
    !installedAgentId ||
    configuredAgentId !== sourceAgentId ||
    sourceAgentId !== installedAgentId
  ) {
    blocked("installed_agent_identity_mismatch");
  }
  const provider = String(main?.voice_llm_provider || "").trim();
  const model = String(main?.voice_llm_model || "").trim();
  const fallbackProvider = String(
    main?.voice_fallback_llm_provider || main?.fallback_llm_provider || "",
  ).trim();
  const fallbackModel = String(
    main?.voice_fallback_llm_model ||
      main?.voice_fallback_llm_model_parameters?.model ||
      main?.fallback_llm_model ||
      main?.fallback_llm_model_parameters?.model ||
      "",
  ).trim();
  const name = String(main?.name || "").trim();
  if (
    !provider ||
    !model ||
    !fallbackProvider ||
    !fallbackModel ||
    (provider === fallbackProvider && model === fallbackModel) ||
    !name
  ) {
    blocked("exact_voice_route_unavailable");
  }
  return {
    assistant: {
      provider,
      model,
      fallback: { provider: fallbackProvider, model: fallbackModel },
    },
    agent: { id: sourceAgentId, name },
  };
}

function assertLoopbackOrigin(value, label) {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    blocked(label + "_not_loopback");
  }
  const host = parsed.hostname.replace(/^\[/, "").replace(/\]$/, "");
  if (
    parsed.protocol !== "http:" ||
    !new Set(["127.0.0.1", "localhost", "::1"]).has(host) ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  ) {
    blocked(label + "_not_loopback");
  }
  return parsed.origin;
}

function assertLocalMongo(value) {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    blocked("installed_mongo_uri_unavailable");
  }
  const host = parsed.hostname.replace(/^\[/, "").replace(/\]$/, "");
  if (
    parsed.protocol !== "mongodb:" ||
    !new Set(["127.0.0.1", "localhost", "::1"]).has(host)
  ) {
    blocked("installed_mongo_not_local");
  }
}

async function fetchInstalledVoiceCapabilities(origin, fetchImpl = fetch) {
  const base = assertLoopbackOrigin(origin, "voice_capability_origin");
  let response;
  try {
    response = await fetchImpl(base + "/capabilities", {
      method: "GET",
      redirect: "error",
      signal: AbortSignal.timeout(5_000),
    });
  } catch {
    blocked("installed_voice_capabilities_unavailable");
  }
  if (!response?.ok) blocked("installed_voice_capabilities_unavailable");
  let payload;
  try {
    payload = await response.json();
  } catch {
    blocked("installed_voice_capabilities_unavailable");
  }
  const voice = {
    stt: {
      provider: String(payload?.stt?.provider || "").trim(),
      variant: String(payload?.stt?.variant || "").trim(),
    },
    tts: {
      provider: String(payload?.tts?.provider || "").trim(),
      variant: String(payload?.tts?.variant || "").trim(),
    },
  };
  if (
    !voice.stt.provider ||
    !voice.stt.variant ||
    !voice.tts.provider ||
    !voice.tts.variant
  ) {
    blocked("installed_voice_capabilities_unavailable");
  }
  return voice;
}

function assertStrictCandidate(report) {
  const checks = Array.isArray(report?.checks) ? report.checks : [];
  const source = report?.measuredIdentity?.source;
  const nested = report?.measuredIdentity?.nestedComponents;
  const binding = report?.runtimeBinding;
  if (
    !HEX_64.test(String(report?.candidateDigest || "")) ||
    !HEX_64.test(String(report?.artifactDigest || "")) ||
    REQUIRED_IDENTITY_CHECKS.some(
      (id) =>
        checks.filter((check) => check?.id === id && check.status === "PASS")
          .length !== 1,
    ) ||
    source?.clean !== true ||
    !Array.isArray(nested) ||
    nested.length < 1 ||
    nested.some(
      (item) => item?.clean !== true || item?.pin !== item?.revision,
    ) ||
    binding?.active !== true ||
    binding?.ownerRootMatches !== true ||
    binding?.runtimeRootMatches !== true
  ) {
    blocked("strict_candidate_identity_invalid");
  }
  return {
    candidateMode: "strict",
    releaseCandidateVerified: true,
    candidateDigest: report.candidateDigest,
    artifactDigest: report.artifactDigest,
  };
}

function measureInstalledCandidate({
  runtimeRoot,
  ownerState,
  artifactIdentity,
}) {
  const probe = [
    "import importlib.util,json,sys",
    "from pathlib import Path",
    "s=importlib.util.spec_from_file_location('mpv061_preparation_identity',sys.argv[1])",
    "m=importlib.util.module_from_spec(s)",
    "sys.modules[s.name]=m",
    "s.loader.exec_module(m)",
    "identity=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))",
    "root=Path(sys.argv[3])",
    "runtime=Path(sys.argv[4])",
    "owner=Path(sys.argv[5])",
    "checks,_=m._artifact_identity_checks(root,identity,runtime/'prompt-bundle.json',root,owner)",
    "candidate,artifact=m._qa_candidate_digests(identity)",
    "measured=m._public_artifact_identity(m._measured_artifact_identity(root,runtime/'prompt-bundle.json',root,owner))",
    "state=json.loads(owner.read_text(encoding='utf-8'))",
    "active=m._runtime_owner_state_proves_active(root,owner)",
    "binding={'active':active,'ownerRootMatches':active and Path(str(state.get('repoRoot') or '')).resolve(strict=True)==root.resolve(strict=True),'runtimeRootMatches':active and Path(str(state.get('runtimeDir') or '')).resolve(strict=True)==runtime.resolve(strict=True)}",
    "print(json.dumps({'candidateDigest':candidate,'artifactDigest':artifact,'checks':[{'id':c.check_id,'status':c.status} for c in checks],'runtimeBinding':binding,'measuredIdentity':measured}))",
  ].join(";");
  const result = spawnSync(
    "python3",
    [
      "-c",
      probe,
      RELEASE_GATE_PATH,
      artifactIdentity,
      ROOT,
      runtimeRoot,
      ownerState,
    ],
    { cwd: ROOT, encoding: "utf8", timeout: 30_000, maxBuffer: 512 * 1024 },
  );
  if (result.status !== 0) blocked("strict_candidate_identity_invalid");
  try {
    return JSON.parse(result.stdout);
  } catch {
    blocked("strict_candidate_identity_invalid");
  }
}

function installedDiagnosticContract(runner) {
  const contract = runner?.DIAGNOSTIC_CANDIDATE_CONTRACT;
  return record(contract) ? contract : { supported: false };
}

function resolveDiagnosticPolicy(environment, contract) {
  if (environment?.VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE !== "1") {
    blocked("diagnostic_candidate_requires_explicit_opt_in");
  }
  if (
    !record(contract) ||
    contract.supported !== true ||
    contract.status !== "PRE_GATE_COMPLETE" ||
    contract.releaseReady !== false ||
    contract.receiptEligible !== false ||
    contract.releaseLabel !== RELEASE_LABEL
  ) {
    blocked("diagnostic_candidate_unsupported_by_mpv061_runner");
  }
  return {
    candidateMode: "diagnostic",
    status: "PRE_GATE_COMPLETE",
    releaseReady: false,
    receiptEligible: false,
    releaseLabel: RELEASE_LABEL,
  };
}

function installedObserverContract(runner, ownerStatePath) {
  const contract = runner?.SCENARIO_OBSERVER_CONTRACT;
  const availablePlanes = record(contract?.effectStages)
    ? Object.keys(contract.effectStages)
    : [];
  const unavailablePlanes = Array.isArray(contract?.unavailableEffectPlanes)
    ? contract.unavailableEffectPlanes
    : [];
  const namedStages = record(contract?.effectStages)
    ? Object.values(contract.effectStages).flat()
    : [];
  const producerStages = new Set(
    Array.isArray(contract?.producerOwnedStages)
      ? contract.producerOwnedStages
      : [],
  );
  if (
    !record(contract) ||
    contract.version !== 1 ||
    typeof contract.producerScope !== "string" ||
    !contract.producerScope ||
    contract.runtimeIdentityFileKind !== "stack_owner" ||
    !record(contract.effectStages) ||
    !record(contract.fallback) ||
    !record(contract.workerCompletionDelivery) ||
    availablePlanes.some(
      (plane) =>
        !Array.isArray(contract.effectStages[plane]) ||
        contract.effectStages[plane].length < 1,
    ) ||
    availablePlanes.some((plane) => !REQUIRED_EFFECT_PLANES.includes(plane)) ||
    unavailablePlanes.some(
      (plane) => !REQUIRED_EFFECT_PLANES.includes(plane),
    ) ||
    new Set([...availablePlanes, ...unavailablePlanes]).size !==
      REQUIRED_EFFECT_PLANES.length ||
    REQUIRED_EFFECT_PLANES.some(
      (plane) =>
        Number(availablePlanes.includes(plane)) +
          Number(unavailablePlanes.includes(plane)) !==
        1,
    ) ||
    namedStages.some(
      (stage) => typeof stage !== "string" || !producerStages.has(stage),
    ) ||
    !Array.isArray(contract.fallback.stages) ||
    contract.fallback.stages.some((stage) => !producerStages.has(stage)) ||
    !Array.isArray(contract.workerCompletionDelivery.stages) ||
    contract.workerCompletionDelivery.stages.some(
      (stage) => !producerStages.has(stage),
    )
  ) {
    blocked("installed_observer_contract_unavailable");
  }
  if (
    unavailablePlanes.length > 0 ||
    contract.fallback.available !== true ||
    JSON.stringify(contract.fallback.stages) !==
      JSON.stringify([
        "attempt.history.complete",
        "provider.request.forwarded",
        "provider.attempt.completed",
        "provider.fallback.completed",
      ]) ||
    contract.fallback.controlledTriggerAvailable !== true
  ) {
    blocked("installed_observer_stage_unavailable");
  }
  if (
    contract.workerCompletionDelivery.available !== true ||
    typeof contract.workerCompletionDelivery.producerScope !== "string" ||
    !contract.workerCompletionDelivery.producerScope ||
    JSON.stringify(contract.workerCompletionDelivery.stages) !==
      JSON.stringify(["response.completed", "tts.completed", "audio.completed"])
  ) {
    blocked("worker_completion_delivery_trace_unavailable");
  }
  const owner = readJson(ownerStatePath, "runtime_identity");
  const fields = Array.isArray(contract.runtimeIdentityFields)
    ? contract.runtimeIdentityFields
    : [];
  if (
    fields.length !== 1 ||
    fields[0] !== "ownerBindingSha256" ||
    !HEX_64.test(String(owner.ownerBindingSha256 || ""))
  ) {
    blocked("runtime_identity_contract_incompatible");
  }
  return {
    observerContractVersion: contract.version,
    producerScope: contract.producerScope,
    runtimeIdentityFileKind: contract.runtimeIdentityFileKind,
    runtimeIdentityFile: fs.realpathSync(ownerStatePath),
    fallbackStage: "provider.fallback.completed",
    fallbackStages: [...contract.fallback.stages],
    effectStages: Object.fromEntries(
      REQUIRED_EFFECT_PLANES.map((plane) => [
        plane,
        [...contract.effectStages[plane]],
      ]),
    ),
  };
}

function findTool(name) {
  const result = spawnSync("/usr/bin/which", [name], {
    encoding: "utf8",
    timeout: 5_000,
    maxBuffer: 16 * 1024,
  });
  if (result.status !== 0 || !result.stdout.trim())
    blocked("local_audio_tools_unavailable");
  try {
    const selected = fs.realpathSync(result.stdout.trim());
    fs.accessSync(selected, fs.constants.X_OK);
    return selected;
  } catch {
    blocked("local_audio_tools_unavailable");
  }
}

function runLocal(executable, args, code, timeout = 60_000) {
  const result = spawnSync(executable, args, {
    encoding: "utf8",
    timeout,
    maxBuffer: 128 * 1024,
    stdio: ["ignore", "ignore", "pipe"],
  });
  if (result.status !== 0) blocked(code);
}

function privateWrite(target, bytes, root) {
  const selected = path.resolve(target);
  if (!ownsPath(selected, root) || fs.existsSync(selected))
    blocked("private_output_exists");
  const descriptor = fs.openSync(
    selected,
    fs.constants.O_WRONLY |
      fs.constants.O_CREAT |
      fs.constants.O_EXCL |
      (fs.constants.O_NOFOLLOW || 0),
    0o600,
  );
  try {
    fs.writeFileSync(descriptor, bytes);
    fs.fchmodSync(descriptor, 0o600);
  } finally {
    fs.closeSync(descriptor);
  }
  return selected;
}

function writePrivateRuntimeHandoff(rootValue, mongoUri) {
  const root = inspectPrivateRoot(rootValue, { create: true });
  assertLocalMongo(mongoUri);
  return privateWrite(
    path.join(root, "mpv-061-runtime-handoff.v1.json"),
    Buffer.from(
      JSON.stringify(
        { schema: RUNTIME_HANDOFF_SCHEMA, MONGO_URI: mongoUri },
        null,
        2,
      ) + "\n",
    ),
    root,
  );
}

function availableEnglishSayVoices(say) {
  const result = spawnSync(say, ["-v", "?"], {
    encoding: "utf8",
    timeout: 5_000,
    maxBuffer: 256 * 1024,
    env: { PATH: "/usr/bin:/bin", LC_ALL: "C" },
  });
  if (result.status !== 0) blocked("distinct_synthetic_speakers_unavailable");
  const voices = String(result.stdout || "")
    .split(/\r?\n/)
    .map((line) => /^\s*(\S+)\s+(en(?:[_-][A-Za-z]+)?)\b/.exec(line))
    .filter(Boolean)
    .map((match) => match[1]);
  return [...new Set(voices)];
}

function wavDuration(ffprobe, file) {
  const result = spawnSync(
    ffprobe,
    [
      "-v",
      "error",
      "-show_entries",
      "format=duration",
      "-of",
      "default=noprint_wrappers=1:nokey=1",
      file,
    ],
    { encoding: "utf8", timeout: 10_000, maxBuffer: 16 * 1024 },
  );
  const duration = Number(result.stdout);
  if (
    result.status !== 0 ||
    !Number.isFinite(duration) ||
    duration <= 0 ||
    duration > 120
  ) {
    blocked("local_speech_generation_failed");
  }
  return duration;
}

function concatenateAudio(ffmpeg, inputs, target) {
  const argumentsList = ["-nostdin", "-v", "error"];
  for (const input of inputs) argumentsList.push("-i", input);
  const filter =
    inputs.map((_, index) => `[${index}:a]`).join("") +
    `concat=n=${inputs.length}:v=0:a=1[out]`;
  argumentsList.push(
    "-filter_complex",
    filter,
    "-map",
    "[out]",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-c:a",
    "pcm_s16le",
    target,
  );
  runLocal(ffmpeg, argumentsList, "local_speech_generation_failed", 120_000);
  fs.chmodSync(target, 0o600);
}

function generateSpeechFixtures(rootValue, turns = SCENARIO_TURNS) {
  const root = inspectPrivateRoot(rootValue, { create: true });
  if (
    !Array.isArray(turns) ||
    turns.length !== SCENARIO_TURNS.length ||
    turns.some(
      (turn) => typeof turn?.speech !== "string" || !turn.speech.trim(),
    )
  ) {
    blocked("execution_turn_scenario_invalid");
  }
  const say = "/usr/bin/say";
  try {
    fs.accessSync(say, fs.constants.X_OK);
  } catch {
    blocked("local_audio_tools_unavailable");
  }
  const ffmpeg = findTool("ffmpeg");
  const ffprobe = findTool("ffprobe");
  const sayVoices = availableEnglishSayVoices(say);
  if (sayVoices.length < 2) blocked("distinct_synthetic_speakers_unavailable");
  const ownerVoice = sayVoices[0];
  const alternateVoice = sayVoices.find((voice) => voice !== ownerVoice);
  const temporary = fs.mkdtempSync(path.join(root, ".mpv061-audio-"));
  fs.chmodSync(temporary, 0o700);
  const previousUmask = process.umask(0o077);
  try {
    const initialSilence = path.join(temporary, "silence-initial.wav");
    const betweenSilence = path.join(temporary, "silence-between.wav");
    runLocal(
      ffmpeg,
      [
        "-nostdin",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=16000:cl=mono",
        "-t",
        String(INITIAL_SILENCE_SECONDS),
        "-c:a",
        "pcm_s16le",
        initialSilence,
      ],
      "local_speech_generation_failed",
    );
    runLocal(
      ffmpeg,
      [
        "-nostdin",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=16000:cl=mono",
        "-t",
        String(BETWEEN_TURN_SILENCE_SECONDS),
        "-c:a",
        "pcm_s16le",
        betweenSilence,
      ],
      "local_speech_generation_failed",
    );
    fs.chmodSync(initialSilence, 0o600);
    fs.chmodSync(betweenSilence, 0o600);

    const utterances = [];
    const durations = [];
    for (let index = 0; index < turns.length; index += 1) {
      const aiff = path.join(temporary, `turn-${index + 1}.aiff`);
      const wav = path.join(temporary, `turn-${index + 1}.wav`);
      runLocal(
        say,
        [
          "-v",
          turns[index].speakerRole === "alternate"
            ? alternateVoice
            : ownerVoice,
          "-o",
          aiff,
          "--",
          turns[index].speech,
        ],
        "local_speech_generation_failed",
      );
      fs.chmodSync(aiff, 0o600);
      runLocal(
        ffmpeg,
        [
          "-nostdin",
          "-v",
          "error",
          "-i",
          aiff,
          "-ac",
          "1",
          "-ar",
          "16000",
          "-c:a",
          "pcm_s16le",
          wav,
        ],
        "local_speech_generation_failed",
      );
      fs.chmodSync(wav, 0o600);
      utterances.push(wav);
      durations.push(wavDuration(ffprobe, wav));
    }

    const startAfterMs = [];
    const armAfterMs = [];
    const initialInputs = [initialSilence];
    let cursor = INITIAL_SILENCE_SECONDS;
    for (let index = 0; index < utterances.length; index += 1) {
      const speechStartMs = Math.round(cursor * 1000);
      startAfterMs.push(speechStartMs);
      armAfterMs.push(Math.max(0, speechStartMs - MODE_ARM_LEAD_MS));
      initialInputs.push(utterances[index]);
      cursor += durations[index];
      if (index < utterances.length - 1) {
        initialInputs.push(betweenSilence);
        cursor += BETWEEN_TURN_SILENCE_SECONDS;
      }
    }
    const initialTemporary = path.join(temporary, "initial.wav");
    concatenateAudio(ffmpeg, initialInputs, initialTemporary);

    const reconnectAiff = path.join(temporary, "reconnect.aiff");
    const reconnectSpeech = path.join(temporary, "reconnect-speech.wav");
    runLocal(
      say,
      [
        "-o",
        reconnectAiff,
        "--",
        "Viventium. After this reconnect, report only the status of mission alpha and mission bravo. Do not start or change any work.",
      ],
      "local_speech_generation_failed",
    );
    fs.chmodSync(reconnectAiff, 0o600);
    runLocal(
      ffmpeg,
      [
        "-nostdin",
        "-v",
        "error",
        "-i",
        reconnectAiff,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        reconnectSpeech,
      ],
      "local_speech_generation_failed",
    );
    fs.chmodSync(reconnectSpeech, 0o600);
    const reconnectTemporary = path.join(temporary, "reconnect.wav");
    concatenateAudio(
      ffmpeg,
      [initialSilence, reconnectSpeech],
      reconnectTemporary,
    );

    const initialBytes = fs.readFileSync(initialTemporary);
    const reconnectBytes = fs.readFileSync(reconnectTemporary);
    const initial = privateWrite(
      path.join(root, "mpv-061-initial.wav"),
      initialBytes,
      root,
    );
    const reconnect = privateWrite(
      path.join(root, "mpv-061-reconnect.wav"),
      reconnectBytes,
      root,
    );
    return {
      initial,
      reconnect,
      initialSha256: sha256(initialBytes),
      reconnectSha256: sha256(reconnectBytes),
      startAfterMs,
      armAfterMs,
    };
  } finally {
    process.umask(previousUmask);
    fs.rmSync(temporary, { recursive: true, force: false });
  }
}

function inspectAudibleWav(file) {
  try {
    const runner = require(RUNNER_PATH);
    const helpers = require(
      path.join(__dirname, "livekit_synthetic_audio_qa.js"),
    );
    const bytes = fs.readFileSync(path.resolve(file));
    return helpers.inspectAudiblePcmWav(bytes) && runner ? true : false;
  } catch {
    return false;
  }
}

function buildScenario(input) {
  if (
    !record(input) ||
    !record(input.identity) ||
    !record(input.runtime) ||
    !record(input.speech) ||
    !Array.isArray(input.speech.startAfterMs) ||
    input.speech.startAfterMs.length !== SCENARIO_TURNS.length ||
    !Array.isArray(input.speech.armAfterMs) ||
    input.speech.armAfterMs.length !== SCENARIO_TURNS.length ||
    !Array.isArray(input.attachments) ||
    input.attachments.length !== 2 ||
    !record(input.restart) ||
    !record(input.observation)
  ) {
    blocked("scenario_preparation_contract_invalid");
  }
  const root = path.resolve(input.evidenceRoot);
  const turns = SCENARIO_TURNS.map((turn, index) => ({
    kind: turn.kind,
    mode: turn.mode,
    directlyAddressed: turn.directlyAddressed,
    expectedTranscript: turn.expectedTranscript,
    startAfterMs: input.speech.startAfterMs[index],
    armAfterMs: input.speech.armAfterMs[index],
    ...(turn.speakerRole ? { speakerRole: turn.speakerRole } : {}),
  }));
  const scenario = {
    schema: SCENARIO_SCHEMA,
    caseId: CASE_ID,
    environment: "installed_prod",
    artifactIdentity: path.resolve(input.artifactIdentity),
    runtime: {
      playgroundUrl: assertLoopbackOrigin(
        input.runtime.playgroundUrl,
        "playground_origin",
      ),
      coreUrl: assertLoopbackOrigin(input.runtime.coreUrl, "core_origin"),
      mongoUriFile: path.resolve(input.runtime.mongoUriFile),
      assistant: input.identity.assistant,
      agent: input.identity.agent,
      voice: input.runtime.voice,
    },
    browser: { headed: true, headless: false },
    audio: {
      initial: path.resolve(input.speech.initial),
      reconnect: path.resolve(input.speech.reconnect),
    },
    turns,
    attachments: input.attachments.map((item) => ({
      worker: item.worker,
      path: path.resolve(item.path),
      artifactLabel: item.artifactLabel,
      dispatchInstruction: item.dispatchInstruction,
    })),
    requirements: {
      providerFallback: {
        required: true,
        controlledTrigger: {
          kind: "mpv_061_parent_private_fd_v1",
          caseId: CASE_ID,
          targetTurnKind: "trustedWingLaunch",
          approvalWaitMs: 750,
        },
        reason: "parent_approved_pre_model_fault",
      },
    },
    surfaces: { reconnectButton: "Start voice call" },
    restart: {
      executable: path.resolve(input.restart.executable),
      arguments: [...input.restart.arguments],
    },
    observation: input.observation,
    deliveryTimeoutMs: 180_000,
    restartTimeoutMs: 600_000,
    outputs: {
      manifest: path.join(root, "full-journey-evidence.v1.json"),
      result: path.join(root, "full-journey-result.v1.json"),
      cleanupState: path.join(root, "mpv-061-cleanup-state.v1.json"),
    },
  };
  if (record(input.candidate)) scenario.candidate = input.candidate;
  return scenario;
}

function writePreparationFiles(root, speech) {
  const attachmentA = privateWrite(
    path.join(root, "mpv-061-worker-alpha-input.json"),
    Buffer.from(
      JSON.stringify(
        { caseId: CASE_ID, worker: "A", value: "alpha-seven" },
        null,
        2,
      ) + "\n",
    ),
    root,
  );
  const attachmentB = privateWrite(
    path.join(root, "mpv-061-worker-bravo-input.md"),
    Buffer.from(
      "# Synthetic MPV-061 Worker B Input\n\nPreserve the number 27.\n",
    ),
    root,
  );
  return [
    {
      worker: "A",
      path: attachmentA,
      artifactLabel: "mpv-061-worker-alpha-result.txt",
      dispatchInstruction:
        "Send only this attached file to mission alpha. Keep mission bravo unchanged.",
    },
    {
      worker: "B",
      path: attachmentB,
      artifactLabel: "mpv-061-worker-bravo-result.txt",
      dispatchInstruction:
        "Send only this attached file to mission bravo. Keep mission alpha unchanged.",
    },
  ];
}

function parseArguments(argv) {
  if (argv.length === 1 && ["--help", "-h"].includes(argv[0]))
    return { help: true };
  const options = { evidenceRoot: "", candidateMode: "strict", help: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!["--evidence-root", "--candidate-mode"].includes(value))
      blocked("unknown_argument");
    const next = argv[index + 1];
    if (typeof next !== "string" || !next || next.startsWith("--")) {
      blocked("required_argument_missing");
    }
    if (value === "--evidence-root") options.evidenceRoot = next;
    else options.candidateMode = next;
    index += 1;
  }
  if (!options.evidenceRoot) blocked("evidence_root_unavailable");
  if (!new Set(["strict", "diagnostic"]).has(options.candidateMode)) {
    blocked("candidate_mode_invalid");
  }
  return options;
}

function usage() {
  return (
    [
      "Usage:",
      "  node qa/modern-playground-voice/scripts/prepare_mpv_061_installed_scenario.cjs \\",
      "    --evidence-root <private-0700-directory> [--candidate-mode strict|diagnostic]",
      "",
      "Preparation only. It never runs MPV-061 or restarts services.",
    ].join("\n") + "\n"
  );
}

function measureRunnerCandidate(runner, input) {
  if (typeof runner?.measureInstalledCandidate !== "function") {
    blocked("candidate_measurement_contract_unavailable");
  }
  try {
    return runner.measureInstalledCandidate(input);
  } catch (error) {
    if (error instanceof PreparationBlocked) throw error;
    if (SAFE_BLOCKER.test(String(error?.code || ""))) {
      blocked(error.code);
    }
    blocked("candidate_measurement_failed");
  }
}

async function prepare(argv, environment = process.env) {
  const options = parseArguments(argv);
  if (options.help) return { help: true };
  const selectedRoot = inspectPrivateRoot(options.evidenceRoot);
  const runner = require(RUNNER_PATH);
  let diagnosticPolicy;
  if (options.candidateMode === "diagnostic") {
    diagnosticPolicy = resolveDiagnosticPolicy(
      environment,
      installedDiagnosticContract(runner),
    );
  }

  const owner = readJson(OWNER_STATE_PATH, "runtime_owner_state");
  let runtimeRoot;
  let installedRoot;
  try {
    runtimeRoot = fs.realpathSync(String(owner.runtimeDir || ""));
    installedRoot = fs.realpathSync(String(owner.repoRoot || ""));
  } catch {
    blocked("installed_runtime_owner_unavailable");
  }
  if (installedRoot !== ROOT || !ownsPath(runtimeRoot, APP_SUPPORT_ROOT)) {
    blocked("installed_runtime_owner_mismatch");
  }
  const artifactIdentity = path.join(
    runtimeRoot,
    "parallel-work-artifact-identity.json",
  );
  const candidate = measureRunnerCandidate(runner, {
    artifactIdentity,
    candidateMode: options.candidateMode,
  });
  if (
    diagnosticPolicy &&
    (candidate.candidateMode !== diagnosticPolicy.candidateMode ||
      candidate.status !== diagnosticPolicy.status ||
      candidate.releaseReady !== diagnosticPolicy.releaseReady ||
      candidate.receiptEligible !== diagnosticPolicy.receiptEligible ||
      candidate.releaseLabel !== diagnosticPolicy.releaseLabel)
  ) {
    blocked("diagnostic_candidate_contract_mismatch");
  }
  const observation = installedObserverContract(runner, OWNER_STATE_PATH);

  const installed = parseRuntimeMetadata(runtimeRoot);
  assertLocalMongo(installed.MONGO_URI);
  const config = parseYaml(
    readText(path.join(APP_SUPPORT_ROOT, "config.yaml"), "canonical_config", {
      privateFile: true,
    }),
    "canonical_config",
  );
  const agents = parseYaml(
    readText(AGENT_SOURCE_PATH, "agent_source"),
    "agent_source",
  );
  const identity = resolveConfiguredIdentity(config, agents, installed);
  const playgroundPort = Number(installed.VIVENTIUM_PLAYGROUND_PORT);
  const frontendPort = Number(installed.VIVENTIUM_LC_FRONTEND_PORT);
  const gatewayPort = Number(installed.VIVENTIUM_VOICE_GATEWAY_HEALTH_PORT);
  if (
    ![playgroundPort, frontendPort, gatewayPort].every(
      (value) => Number.isSafeInteger(value) && value >= 1024 && value <= 65535,
    )
  ) {
    blocked("installed_runtime_ports_unavailable");
  }
  const playgroundUrl = assertLoopbackOrigin(
    installed.VIVENTIUM_PLAYGROUND_URL || `http://127.0.0.1:${playgroundPort}`,
    "playground_origin",
  );
  const coreUrl = assertLoopbackOrigin(
    `http://127.0.0.1:${frontendPort}`,
    "core_origin",
  );
  const voice = await fetchInstalledVoiceCapabilities(
    `http://127.0.0.1:${gatewayPort}`,
  );
  const restart = runner.validateProtectedRestartPlan({
    executable: path.join(ROOT, "bin", "viventium"),
    arguments: [...RESTART_ARGUMENTS],
  });

  const root = inspectPrivateRoot(selectedRoot, { create: true });
  const speech = generateSpeechFixtures(root, SCENARIO_TURNS);
  if (
    !inspectAudibleWav(speech.initial) ||
    !inspectAudibleWav(speech.reconnect) ||
    speech.initialSha256 === speech.reconnectSha256
  ) {
    blocked("generated_audio_invalid");
  }
  const attachments = writePreparationFiles(root, speech);
  const mongoUriFile = writePrivateRuntimeHandoff(root, installed.MONGO_URI);
  const scenario = buildScenario({
    evidenceRoot: root,
    artifactIdentity,
    identity,
    runtime: {
      playgroundUrl,
      coreUrl,
      mongoUriFile,
      voice,
    },
    speech,
    attachments,
    restart,
    observation,
    candidate,
  });
  const scenarioPath = privateWrite(
    path.join(root, "mpv-061-installed-scenario.v1.json"),
    Buffer.from(JSON.stringify(scenario, null, 2) + "\n"),
    root,
  );
  runner.validateScenario(scenario, root, {});
  return {
    caseId: CASE_ID,
    status:
      options.candidateMode === "diagnostic" ? "PRE_GATE_COMPLETE" : "PREPARED",
    releaseLabel: RELEASE_LABEL,
    receiptEligible: false,
    journeyReceiptEligible: false,
    candidateMode: options.candidateMode,
    scenarioFile: path.basename(scenarioPath),
    audioFileCount: 2,
    attachmentCount: 2,
    turnCount: SCENARIO_TURNS.length,
    fallbackRequirement: "required_parent_approved_pre_model_fault",
    assistant: identity.assistant,
    agent: identity.agent,
    command: [
      "VIVENTIUM_QA_ALLOW_MPV061_RUNTIME_RESTART=1",
      ...(options.candidateMode === "diagnostic"
        ? ["VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE=1"]
        : []),
      "node",
      "qa/modern-playground-voice/scripts/run_mpv_061_installed_journey.cjs",
      "--local-qa",
      "--allow-synthetic-account",
      "--allow-runtime-restart",
      "--candidate-mode",
      options.candidateMode,
      "--evidence-root",
      "<private-evidence-root>",
      "--scenario",
      "<private-evidence-root>/mpv-061-installed-scenario.v1.json",
    ],
  };
}

function publicBlocked(error) {
  const code =
    error instanceof PreparationBlocked
      ? error.code
      : "scenario_preparation_blocked";
  return {
    caseId: CASE_ID,
    status: "BLOCKED",
    blocker: code,
    releaseLabel: RELEASE_LABEL,
    receiptEligible: false,
  };
}

async function main() {
  let parsed;
  try {
    parsed = parseArguments(process.argv.slice(2));
  } catch (error) {
    const result = publicBlocked(error);
    process.stdout.write(JSON.stringify(result) + "\n");
    process.exitCode = 2;
    return;
  }
  if (parsed.help) {
    process.stdout.write(usage());
    return;
  }
  try {
    const result = await prepare(process.argv.slice(2));
    process.stdout.write(JSON.stringify(result) + "\n");
    process.exitCode = 0;
  } catch (error) {
    const result = publicBlocked(error);
    process.stdout.write(JSON.stringify(result) + "\n");
    process.exitCode = 2;
  }
}

if (require.main === module) {
  void main();
}

module.exports = {
  CASE_ID,
  RELEASE_LABEL,
  SCENARIO_SCHEMA,
  SCENARIO_TURNS,
  PreparationBlocked,
  parseArguments,
  inspectPrivateRoot,
  assertLoopbackOrigin,
  resolveConfiguredIdentity,
  assertStrictCandidate,
  resolveDiagnosticPolicy,
  installedObserverContract,
  measureRunnerCandidate,
  fetchInstalledVoiceCapabilities,
  generateSpeechFixtures,
  writePrivateRuntimeHandoff,
  inspectAudibleWav,
  buildScenario,
  prepare,
};
