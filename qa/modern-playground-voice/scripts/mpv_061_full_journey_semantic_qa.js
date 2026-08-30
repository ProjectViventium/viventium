#!/usr/bin/env node
/*
 * Fail-closed semantic verifier for the complete MPV-061 installed voice journey.
 *
 * Raw identifiers, transcript, audio, ledgers, screenshots, and artifacts stay in the selected
 * private evidence root. The result contains only candidate hashes, counts, and gate states.
 * The narrower authority-window audit in world_class_call_acceptance.js is supporting evidence;
 * authority_slice_only can never produce PASS here.
 */

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..", "..");
const CASE_ID = "MPV-061";
const EVIDENCE_SCHEMA = "viventium.voice.mpv-061.full-journey-evidence.v1";
const OBSERVATION_SCHEMA = "viventium.voice.mpv-061.observation.v1";
const RESULT_SCHEMA = "viventium.voice.mpv-061.full-journey-result.v1";
const FULL_JOURNEY_SCOPE = "full_journey";
const AUTHORITY_SLICE_SCOPE = "authority_slice_only";
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$/;
const SAFE_KIND = /^[a-z][a-z0-9_]{0,63}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const SHA_REF = /^sha256:[a-f0-9]{64}$/;
const MODES = new Set(["call", "wing", "listen_only"]);
const SESSION_MEDIA_KINDS = new Set(["voice_recording", "voice_transcript"]);
const BINARY_EVIDENCE_KINDS = new Set([
  "voice_recording",
  "input_file",
  "delivered_artifact",
]);
const MAX_MANIFEST_BYTES = 512 * 1024;
const MAX_IDENTITY_BYTES = 256 * 1024;
const MAX_EVIDENCE_FILES = 64;
const MAX_EVIDENCE_BYTES = 100 * 1024 * 1024;
const MAX_RESULT_AGE_MS = 24 * 60 * 60 * 1000;
const MAX_OBSERVATION_WINDOW_MS = 12 * 60 * 60 * 1000;
const MAX_FUTURE_SKEW_MS = 5 * 60 * 1000;
const EVIDENCE_FIELDS = Object.freeze([
  "id",
  "kind",
  "path",
  "sha256",
  "runRef",
  "sessionRefs",
  "entityRefs",
  "candidateDigest",
  "artifactDigest",
  "observedAt",
]);
const OBSERVATION_FIELDS = Object.freeze([
  "contractVersion",
  "schema",
  "kind",
  "runRef",
  "sessionRefs",
  "entityRefs",
  "candidateDigest",
  "artifactDigest",
  "observedAt",
  "observations",
]);
const TURN_ORDER = Object.freeze([
  "authorizedCallLaunch",
  "trustedWingLaunch",
  "quickConversation",
  "authorizedCallControl",
  "trustedWingControl",
  "passiveWingDenial",
  "listenOnlyDenial",
]);
const EFFECT_FIELDS = Object.freeze([
  "missionCount",
  "actionCount",
  "launchInvocationCount",
  "controlInvocationCount",
  "toolInvocationCount",
  "controllerInvocationCount",
  "cortexInvocationCount",
  "liveMemoryInvocationCount",
  "recallInvocationCount",
  "titleModelInvocationCount",
  "mainResponseCount",
  "ttsInputCount",
  "assistantAudioOutputCount",
]);
const REQUIRED_EVIDENCE_KINDS = Object.freeze({
  voice_recording: 2,
  voice_transcript: 2,
  session_ledger: 1,
  worker_ledger: 1,
  action_ledger: 1,
  upload_ledger: 1,
  capability_ledger: 1,
  callback_ledger: 1,
  delivery_ledger: 1,
  logical_turn_ledger: 1,
  linked_chat_capture: 2,
  active_work_capture: 2,
  artifact_open_capture: 2,
  input_file: 2,
  delivered_artifact: 2,
  mode_authority_ledger: 1,
  public_safety_report: 1,
});
const INSTALLED_HASH_KEYS = Object.freeze([
  "componentsLockSha256",
  "nestedRevisionsHash",
  "prebuiltSourceSha256",
  "prebuiltBinarySha256",
  "promptBundleSha256",
  "runtimeEnvSha256",
  "libreChatConfigSha256",
  "frontendBuildSha256",
  "apiBuildSha256",
  "runningServiceSha256",
  "runtimeServiceManifestSha256",
  "runtimeOwnerExecutableSha256",
  "ownerCommandContractSha256",
]);

function isRecord(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function isCount(value) {
  return Number.isSafeInteger(value) && value >= 0;
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function digestValue(value) {
  return crypto.createHash("sha256").update(canonicalJson(value)).digest("hex");
}

function exactArray(actual, expected) {
  return (
    Array.isArray(actual) &&
    actual.length === expected.length &&
    actual.every((value, index) => value === expected[index])
  );
}

function exactKeys(value, expected) {
  return (
    isRecord(value) &&
    exactArray(Object.keys(value).sort(), [...expected].sort())
  );
}

function parseTimestamp(value, code) {
  if (typeof value !== "string" || !/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) {
    throw new Error(code);
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(code);
  }
  return parsed;
}

function privateMetadataValid(metadata) {
  return (
    metadata.isFile() &&
    metadata.nlink === 1 &&
    (metadata.mode & 0o077) === 0 &&
    (typeof process.getuid !== "function" || metadata.uid === process.getuid())
  );
}

function readPrivateFile(filePath, maximumBytes, code) {
  let descriptor;
  try {
    descriptor = fs.openSync(
      filePath,
      fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW,
    );
    const before = fs.fstatSync(descriptor);
    if (
      !privateMetadataValid(before) ||
      before.size <= 0 ||
      before.size > maximumBytes
    ) {
      throw new Error(`${code}_invalid`);
    }
    const bytes = fs.readFileSync(descriptor);
    const after = fs.fstatSync(descriptor);
    if (
      bytes.length !== before.size ||
      before.dev !== after.dev ||
      before.ino !== after.ino ||
      before.size !== after.size ||
      before.mtimeMs !== after.mtimeMs ||
      before.ctimeMs !== after.ctimeMs
    ) {
      throw new Error(`${code}_changed`);
    }
    return { bytes, metadata: before };
  } catch (error) {
    if (error instanceof Error && error.message.startsWith(`${code}_`)) {
      throw error;
    }
    throw new Error(`${code}_unavailable`);
  } finally {
    if (descriptor !== undefined) {
      fs.closeSync(descriptor);
    }
  }
}

function validAudibleWav(bytes) {
  if (
    bytes.length < 44 ||
    bytes.toString("ascii", 0, 4) !== "RIFF" ||
    bytes.toString("ascii", 8, 12) !== "WAVE" ||
    bytes.readUInt32LE(4) + 8 !== bytes.length
  ) {
    return false;
  }
  let offset = 12;
  let format;
  let audio;
  while (offset + 8 <= bytes.length) {
    const chunk = bytes.toString("ascii", offset, offset + 4);
    const size = bytes.readUInt32LE(offset + 4);
    const start = offset + 8;
    const end = start + size;
    if (end > bytes.length) {
      return false;
    }
    if (chunk === "fmt ") {
      if (size < 16) {
        return false;
      }
      format = {
        codec: bytes.readUInt16LE(start),
        channels: bytes.readUInt16LE(start + 2),
        sampleRate: bytes.readUInt32LE(start + 4),
        blockAlign: bytes.readUInt16LE(start + 12),
        bits: bytes.readUInt16LE(start + 14),
      };
    } else if (chunk === "data") {
      audio = bytes.subarray(start, end);
    }
    offset = end + (size % 2);
  }
  if (
    !format ||
    !audio ||
    format.codec !== 1 ||
    format.channels < 1 ||
    format.channels > 2 ||
    format.sampleRate < 8000 ||
    format.sampleRate > 192000 ||
    format.bits !== 16 ||
    format.blockAlign !== format.channels * 2 ||
    audio.length < Math.ceil(format.sampleRate / 10) * format.blockAlign ||
    audio.length % format.blockAlign !== 0
  ) {
    return false;
  }
  for (let index = 0; index + 1 < audio.length; index += 2) {
    if (Math.abs(audio.readInt16LE(index)) >= 32) {
      return true;
    }
  }
  return false;
}

function unique(values) {
  return new Set(values).size === values.length;
}

function inside(candidate, root) {
  const relative = path.relative(root, candidate);
  return (
    relative === "" ||
    (!relative.startsWith("..") && !path.isAbsolute(relative))
  );
}

function assertOutsidePublicRepo(candidate, label) {
  if (inside(candidate, ROOT)) {
    throw new Error(`${label}_must_stay_outside_public_repo`);
  }
}

function readJsonFile(filePath, maximumBytes, code) {
  const { bytes } = readPrivateFile(filePath, maximumBytes, code);
  try {
    return JSON.parse(bytes.toString("utf8"));
  } catch {
    throw new Error(`${code}_invalid`);
  }
}

function publicArtifactIdentity(value) {
  if (!isRecord(value)) {
    return {};
  }
  const source = isRecord(value.source) ? value.source : {};
  const prebuilt = isRecord(value.prebuiltHelper) ? value.prebuiltHelper : {};
  const installed = isRecord(value.installed) ? value.installed : {};
  return {
    contractVersion: value.contractVersion,
    source: Object.fromEntries(
      ["revision", "clean", "worktreeHash", "componentsLockSha256"].map(
        (key) => [key, source[key]],
      ),
    ),
    nestedComponents: asArray(value.nestedComponents).map((item) =>
      Object.fromEntries(
        ["name", "pin", "revision", "clean", "worktreeHash"].map((key) => [
          key,
          isRecord(item) ? item[key] : undefined,
        ]),
      ),
    ),
    prebuiltHelper: Object.fromEntries(
      [
        "sourceDeclaredSha256",
        "sourceMeasuredSha256",
        "binaryDeclaredSha256",
        "binaryMeasuredSha256",
        "binaryExecutable",
      ].map((key) => [key, prebuilt[key]]),
    ),
    installed: Object.fromEntries(
      ["rootRevision", ...INSTALLED_HASH_KEYS].map((key) => [
        key,
        installed[key],
      ]),
    ),
  };
}

function validArtifactIdentity(value) {
  if (!isRecord(value) || value.contractVersion !== 1) {
    return false;
  }
  const source = value.source;
  const nested = value.nestedComponents;
  const prebuilt = value.prebuiltHelper;
  const installed = value.installed;
  const nestedNames = asArray(nested).map((item) => item?.name);
  return (
    isRecord(source) &&
    /^[a-f0-9]{40}$/.test(String(source.revision || "")) &&
    typeof source.clean === "boolean" &&
    SHA256.test(String(source.worktreeHash || "")) &&
    SHA256.test(String(source.componentsLockSha256 || "")) &&
    Array.isArray(nested) &&
    nested.length > 0 &&
    unique(nestedNames) &&
    exactArray(nestedNames, [...nestedNames].sort()) &&
    nested.every(
      (item) =>
        isRecord(item) &&
        /^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(String(item.name || "")) &&
        /^[a-f0-9]{40}$/.test(String(item.pin || "")) &&
        /^[a-f0-9]{40}$/.test(String(item.revision || "")) &&
        typeof item.clean === "boolean" &&
        SHA256.test(String(item.worktreeHash || "")),
    ) &&
    isRecord(prebuilt) &&
    [
      "sourceDeclaredSha256",
      "sourceMeasuredSha256",
      "binaryDeclaredSha256",
      "binaryMeasuredSha256",
    ].every((key) => SHA256.test(String(prebuilt[key] || ""))) &&
    typeof prebuilt.binaryExecutable === "boolean" &&
    isRecord(installed) &&
    /^[a-f0-9]{40}$/.test(String(installed.rootRevision || "")) &&
    INSTALLED_HASH_KEYS.every((key) =>
      SHA256.test(String(installed[key] || "")),
    )
  );
}

function candidateDigests(rawIdentity) {
  const identity = publicArtifactIdentity(rawIdentity);
  if (!validArtifactIdentity(identity)) {
    throw new Error("artifact_identity_invalid");
  }
  return {
    candidateDigest: digestValue({
      source: identity.source,
      nestedComponents: identity.nestedComponents,
      prebuiltHelper: identity.prebuiltHelper,
    }),
    artifactDigest: digestValue(identity.installed),
  };
}

function parseArgs(argv) {
  const args = {
    manifest: "",
    evidenceRoot: "",
    artifactIdentity: "",
    result: "",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    const next = argv[index + 1];
    if (item === "--manifest") {
      args.manifest = next || "";
      index += 1;
    } else if (item === "--evidence-root") {
      args.evidenceRoot = next || "";
      index += 1;
    } else if (item === "--artifact-identity") {
      args.artifactIdentity = next || "";
      index += 1;
    } else if (item === "--result") {
      args.result = next || "";
      index += 1;
    } else {
      throw new Error("unknown_argument");
    }
  }
  if (!Object.values(args).every(Boolean)) {
    throw new Error("required_argument_missing");
  }
  for (const key of Object.keys(args)) {
    args[key] = path.resolve(args[key]);
  }
  assertOutsidePublicRepo(args.evidenceRoot, "evidence_root");
  assertOutsidePublicRepo(args.artifactIdentity, "artifact_identity");
  let exactRoot;
  try {
    const suppliedRoot = fs.lstatSync(args.evidenceRoot);
    if (suppliedRoot.isSymbolicLink()) {
      throw new Error("evidence_root_invalid");
    }
    exactRoot = fs.realpathSync(args.evidenceRoot);
  } catch (error) {
    if (error instanceof Error && error.message === "evidence_root_invalid") {
      throw error;
    }
    throw new Error("evidence_root_unavailable");
  }
  const rootMetadata = fs.statSync(exactRoot);
  if (
    !rootMetadata.isDirectory() ||
    (rootMetadata.mode & 0o077) !== 0 ||
    (typeof process.getuid === "function" &&
      rootMetadata.uid !== process.getuid())
  ) {
    throw new Error("evidence_root_invalid");
  }
  args.evidenceRoot = exactRoot;
  for (const [label, candidate] of [
    ["manifest", args.manifest],
    ["result", args.result],
  ]) {
    if (!inside(candidate, exactRoot)) {
      throw new Error(`${label}_must_stay_inside_evidence_root`);
    }
  }
  return args;
}

function verifyEvidence(
  raw,
  evidenceRoot,
  expectedRunRef,
  allowedSessions,
  identityDigests,
  runAt,
  checkedAt = Date.now(),
) {
  if (
    !Array.isArray(raw) ||
    raw.length === 0 ||
    raw.length > MAX_EVIDENCE_FILES
  ) {
    throw new Error("evidence_catalog_invalid");
  }
  const byId = new Map();
  const realPaths = new Set();
  const sessionMediaDigests = new Set();
  const kinds = {};
  const verified = [];
  for (const item of raw) {
    if (!exactKeys(item, EVIDENCE_FIELDS)) {
      throw new Error("evidence_entry_invalid");
    }
    const evidenceId = String(item.id || "");
    const kind = String(item.kind || "");
    const relativeText = String(item.path || "");
    const relative = path.normalize(relativeText);
    if (
      !SAFE_ID.test(evidenceId) ||
      byId.has(evidenceId) ||
      !SAFE_KIND.test(kind)
    ) {
      throw new Error("evidence_metadata_invalid");
    }
    if (
      item.candidateDigest !== identityDigests.candidateDigest ||
      item.artifactDigest !== identityDigests.artifactDigest
    ) {
      throw new Error("evidence_candidate_binding_mismatch");
    }
    const observedAt = parseTimestamp(
      item.observedAt,
      "evidence_timestamp_invalid",
    );
    if (
      observedAt > checkedAt + MAX_FUTURE_SKEW_MS ||
      Math.abs(observedAt - runAt) > MAX_OBSERVATION_WINDOW_MS
    ) {
      throw new Error("evidence_timestamp_invalid");
    }
    if (
      !relativeText ||
      path.isAbsolute(relativeText) ||
      relative === ".." ||
      relative.startsWith(`..${path.sep}`)
    ) {
      throw new Error("evidence_path_invalid");
    }
    const supplied = path.join(evidenceRoot, relativeText);
    let exact;
    try {
      exact = fs.realpathSync(supplied);
    } catch {
      throw new Error("evidence_file_unavailable");
    }
    const { bytes, metadata } = readPrivateFile(
      supplied,
      MAX_EVIDENCE_BYTES,
      "evidence_file",
    );
    if (!inside(exact, evidenceRoot) || realPaths.has(exact)) {
      throw new Error("evidence_file_invalid");
    }
    const measured = crypto.createHash("sha256").update(bytes).digest("hex");
    if (!SHA256.test(String(item.sha256 || "")) || measured !== item.sha256) {
      throw new Error("evidence_digest_mismatch");
    }
    const sessionRefs = asArray(item.sessionRefs);
    const entityRefs = asArray(item.entityRefs);
    if (
      item.runRef !== expectedRunRef ||
      sessionRefs.length === 0 ||
      !unique(sessionRefs) ||
      !sessionRefs.every((value) => allowedSessions.has(value))
    ) {
      throw new Error("evidence_run_session_binding_mismatch");
    }
    if (
      entityRefs.length === 0 ||
      !unique(entityRefs) ||
      !entityRefs.every((value) => SHA_REF.test(String(value || "")))
    ) {
      throw new Error("evidence_entity_binding_invalid");
    }
    if (SESSION_MEDIA_KINDS.has(kind)) {
      if (sessionRefs.length !== 1) {
        throw new Error("session_media_binding_invalid");
      }
      const mediaDigest = `${kind}:${item.sha256}`;
      if (sessionMediaDigests.has(mediaDigest)) {
        throw new Error("duplicate_session_evidence_content");
      }
      sessionMediaDigests.add(mediaDigest);
    }
    let observations = [];
    if (BINARY_EVIDENCE_KINDS.has(kind)) {
      if (kind === "voice_recording" && !validAudibleWav(bytes)) {
        throw new Error("audio_evidence_invalid");
      }
    } else {
      let document;
      try {
        document = JSON.parse(bytes.toString("utf8"));
      } catch {
        throw new Error("evidence_semantic_invalid");
      }
      if (
        !exactKeys(document, OBSERVATION_FIELDS) ||
        document.contractVersion !== 1 ||
        document.schema !== OBSERVATION_SCHEMA ||
        document.kind !== kind ||
        document.runRef !== expectedRunRef ||
        document.candidateDigest !== identityDigests.candidateDigest ||
        document.artifactDigest !== identityDigests.artifactDigest ||
        document.observedAt !== item.observedAt ||
        !exactArray(document.sessionRefs, sessionRefs) ||
        !exactArray(document.entityRefs, entityRefs) ||
        !Array.isArray(document.observations) ||
        document.observations.length === 0 ||
        !document.observations.every(
          (observation) =>
            isRecord(observation) &&
            SAFE_KIND.test(String(observation.type || "")) &&
            !Object.hasOwn(observation, "status"),
        )
      ) {
        throw new Error("evidence_semantic_invalid");
      }
      observations = document.observations;
    }
    const normalized = {
      id: evidenceId,
      kind,
      path: path.relative(evidenceRoot, exact),
      sha256: item.sha256,
      runRef: item.runRef,
      sessionRefs,
      entityRefs,
      candidateDigest: item.candidateDigest,
      artifactDigest: item.artifactDigest,
      observedAt: item.observedAt,
      bytes: metadata.size,
      observations,
    };
    byId.set(evidenceId, normalized);
    realPaths.add(exact);
    kinds[kind] = Number(kinds[kind] || 0) + 1;
    verified.push(normalized);
  }
  for (const [kind, minimum] of Object.entries(REQUIRED_EVIDENCE_KINDS)) {
    if (Number(kinds[kind] || 0) < minimum) {
      throw new Error("required_evidence_kind_missing");
    }
  }
  return { byId, kinds, verified };
}

function baseResult() {
  return {
    schema: RESULT_SCHEMA,
    caseId: CASE_ID,
    status: "BLOCKED",
    scope: FULL_JOURNEY_SCOPE,
    fullJourneyStatus: "NOT_RUN",
    authoritySliceOnlyPassAccepted: false,
    candidateBinding: {
      matched: false,
      candidateDigest: null,
      artifactDigest: null,
    },
    counts: {
      sessions: 0,
      workers: 0,
      actions: 0,
      inputs: 0,
      deliveries: 0,
      artifactsOpened: 0,
      audiblePositiveTurns: 0,
      denialTurns: 0,
      verifiedEvidenceFiles: 0,
    },
    gates: [],
    evidenceDigest: null,
    privacy: {
      publicSafe: true,
      rawIdentifiersIncluded: false,
      rawTranscriptIncluded: false,
      localPathsIncluded: false,
    },
    failures: [],
  };
}

function gate(result, id, passed, actual, expected) {
  result.gates.push({
    id,
    status: passed ? "PASS" : "FAIL",
    actual,
    expected,
  });
}

function bindEvidence(
  value,
  evidence,
  used,
  requiredKinds = [],
  expectedSessionRef = null,
  expectedEntityRefs = [],
) {
  const refs = asArray(value);
  if (
    refs.length === 0 ||
    !unique(refs) ||
    !refs.every((id) => evidence.byId.has(id)) ||
    (expectedSessionRef &&
      !refs.every((id) =>
        evidence.byId.get(id).sessionRefs.includes(expectedSessionRef),
      )) ||
    !refs.every((id) =>
      expectedEntityRefs.every((ref) =>
        evidence.byId.get(id).entityRefs.includes(ref),
      ),
    )
  ) {
    return false;
  }
  const observedKinds = new Set(refs.map((id) => evidence.byId.get(id).kind));
  if (!requiredKinds.every((kind) => observedKinds.has(kind))) {
    return false;
  }
  refs.forEach((id) => used.add(id));
  return true;
}

function bindEvidenceKindEntities(
  value,
  evidence,
  used,
  kind,
  expectedEntityRefs,
  expectedSessionRef = null,
) {
  const refs = asArray(value).filter(
    (id) => evidence.byId.get(id)?.kind === kind,
  );
  if (
    refs.length === 0 ||
    !refs.every(
      (id) =>
        (!expectedSessionRef ||
          evidence.byId.get(id).sessionRefs.includes(expectedSessionRef)) &&
        expectedEntityRefs.every((ref) =>
          evidence.byId.get(id).entityRefs.includes(ref),
        ),
    )
  ) {
    return false;
  }
  refs.forEach((id) => used.add(id));
  return true;
}

function matchingObservation(value, evidence, kind, type, expected) {
  const ids = asArray(value).filter(
    (id) => evidence.byId.get(id)?.kind === kind,
  );
  if (ids.length === 0) {
    return false;
  }
  return ids.some((id) =>
    evidence.byId
      .get(id)
      .observations.some(
        (observation) =>
          observation.type === type &&
          Object.entries(expected).every(
            ([key, actual]) =>
              Object.hasOwn(observation, key) &&
              canonicalJson(observation[key]) === canonicalJson(actual),
          ),
      ),
  );
}

function turnObservation(turn, evidence, kind, ids = turn?.evidence) {
  if (!isRecord(turn)) {
    return false;
  }
  const expected = {
    logicalTurnRef: turn.logicalTurnRef,
    logicalRevision: turn.logicalRevision,
    sessionRef: turn.sessionRef,
    conversationRef: turn.conversationRef,
    mode: turn.mode,
    effects: turn.effects,
    assistantSpeakerRef: turn.assistantSpeakerRef,
  };
  for (const key of [
    "actorTrust",
    "directlyAddressed",
    "sideEffectAuthorityGranted",
    "action",
    "actionRef",
    "acceptedActionReceiptRef",
    "targetWorkerRef",
    "targetMissionRef",
    "targetAttemptRef",
    "nonTargetWorkerRef",
    "requestedWorkerRefs",
    "acceptedWorkerRefs",
    "acceptedLaunchReceiptRefs",
    "rejectedLaunchReceiptCount",
    "currentReply",
    "unrelatedToWorkerMissions",
    "activeWorkerRefs",
    "workerMutationCount",
    "targetActionReceiptCount",
    "nonTargetActionReceiptCount",
    "targetMutationCount",
    "nonTargetMutationCount",
    "transcriptObservationCount",
    "ambientTranscriptCount",
    "workerRef",
    "missionRef",
    "attemptRef",
    "artifactRef",
    "truthful",
    "spokenStatusOrCompletionCount",
    "duplicateSpeechCount",
    "transcriptVisible",
    "transcriptMatchedAudio",
  ]) {
    if (Object.hasOwn(turn, key)) {
      expected[key] = turn[key];
    }
  }
  for (const field of ["inputAudioEvidence", "outputAudioEvidence"]) {
    if (turn[field]) {
      const audio = evidence.byId.get(turn[field]);
      if (!audio || audio.kind !== "voice_recording") {
        return false;
      }
      expected[field.replace("Evidence", "Sha256")] = audio.sha256;
    }
  }
  return matchingObservation(ids, evidence, kind, "turn", expected);
}

function binaryEvidence(
  value,
  evidence,
  used,
  kind,
  expectedSessionRef,
  expectedRefs,
) {
  const item = evidence.byId.get(value);
  if (
    !item ||
    item.kind !== kind ||
    !item.sessionRefs.includes(expectedSessionRef) ||
    !expectedRefs.every((ref) => item.entityRefs.includes(ref))
  ) {
    return null;
  }
  used.add(value);
  return item;
}

function bindDirectEvidence(
  item,
  fields,
  evidence,
  used,
  expectedKinds,
  expectedSessionRef,
) {
  return fields.every((field, index) => {
    const id = item?.[field];
    if (id === null && expectedKinds[index] === null) {
      return true;
    }
    if (typeof id !== "string" || !evidence.byId.has(id)) {
      return false;
    }
    if (evidence.byId.get(id).kind !== expectedKinds[index]) {
      return false;
    }
    if (!evidence.byId.get(id).sessionRefs.includes(expectedSessionRef)) {
      return false;
    }
    if (!evidence.byId.get(id).entityRefs.includes(item?.logicalTurnRef)) {
      return false;
    }
    used.add(id);
    return true;
  });
}

function exactEffects(value, expected) {
  return (
    exactKeys(value, EFFECT_FIELDS) &&
    EFFECT_FIELDS.every((field) => isCount(value[field])) &&
    EFFECT_FIELDS.every(
      (field) => value[field] === Number(expected[field] || 0),
    )
  );
}

function commonTurn(turn, expected, context, evidence, used) {
  return (
    isRecord(turn) &&
    turn.ordinal === expected.ordinal &&
    turn.kind === expected.kind &&
    turn.runRef === context.runRef &&
    turn.sessionRef === context.initialSessionRef &&
    turn.conversationRef === context.conversationRef &&
    turn.mode === expected.mode &&
    MODES.has(turn.mode) &&
    turn.modeAuthoritySource === "persisted_call_session" &&
    turn.actorTrust === "owner_participant" &&
    turn.directlyAddressed === expected.directlyAddressed &&
    turn.sideEffectAuthorityGranted === expected.sideEffectAuthorityGranted &&
    SHA_REF.test(String(turn.logicalTurnRef || "")) &&
    Number.isSafeInteger(turn.logicalRevision) &&
    turn.logicalRevision > 0 &&
    turn.transcriptVisible === true &&
    turn.inputAudioCaptured === true &&
    turn.transcriptMatchedAudio === true &&
    bindDirectEvidence(
      turn,
      ["transcriptEvidence", "inputAudioEvidence", "outputAudioEvidence"],
      evidence,
      used,
      [
        "voice_transcript",
        "voice_recording",
        expected.outputAudio ? "voice_recording" : null,
      ],
      context.initialSessionRef,
    ) &&
    (expected.outputAudio
      ? turn.assistantSpeakerRef === context.queenSpeakerRef
      : turn.assistantSpeakerRef === null) &&
    bindEvidence(
      turn.evidence,
      evidence,
      used,
      expected.evidenceKinds,
      context.initialSessionRef,
      [turn.logicalTurnRef],
    ) &&
    turnObservation(turn, evidence, "voice_transcript", [
      turn.transcriptEvidence,
    ]) &&
    turnObservation(turn, evidence, "logical_turn_ledger") &&
    ["action_ledger", "mode_authority_ledger"].every((kind) => {
      const referenced = asArray(turn.evidence).some(
        (id) => evidence.byId.get(id)?.kind === kind,
      );
      return !referenced || turnObservation(turn, evidence, kind);
    })
  );
}

function evaluateManifest(manifest, identityDigests, evidence) {
  const result = baseResult();
  const usedEvidence = new Set();
  const run = isRecord(manifest.run) ? manifest.run : {};
  const voice = isRecord(manifest.voice) ? manifest.voice : {};
  const turns = isRecord(voice.turns) ? voice.turns : {};
  const wingProbe = isRecord(voice.wingProbe) ? voice.wingProbe : {};
  const workers = asArray(manifest.workers);
  const inputs = asArray(manifest.inputGroup?.ordered);
  const deliveries = asArray(manifest.deliveries);
  const context = {
    runRef: run.runRef,
    initialSessionRef: run.initialSessionRef,
    reconnectSessionRef: run.reconnectSessionRef,
    conversationRef: run.conversationRef,
    queenSpeakerRef: voice.queenSpeakerRef,
  };
  const workerA = workers.find((worker) => worker?.label === "A") || {};
  const workerB = workers.find((worker) => worker?.label === "B") || {};
  const workerRefs = [workerA.workerRef, workerB.workerRef];
  const missionRefs = [workerA.missionRef, workerB.missionRef];
  const attemptRefs = [workerA.attemptRef, workerB.attemptRef];
  const launchReceipts = [
    workerA.acceptedLaunchReceiptRef,
    workerB.acceptedLaunchReceiptRef,
  ];

  const candidateMatched =
    isRecord(manifest.candidate) &&
    manifest.candidate.candidateDigest === identityDigests.candidateDigest &&
    manifest.candidate.artifactDigest === identityDigests.artifactDigest;
  result.candidateBinding = {
    matched: candidateMatched,
    candidateDigest: identityDigests.candidateDigest,
    artifactDigest: identityDigests.artifactDigest,
  };
  gate(
    result,
    "full-journey-scope",
    manifest.scope === FULL_JOURNEY_SCOPE &&
      manifest.scope !== AUTHORITY_SLICE_SCOPE,
    manifest.scope === FULL_JOURNEY_SCOPE
      ? FULL_JOURNEY_SCOPE
      : "non_full_journey",
    FULL_JOURNEY_SCOPE,
  );
  gate(result, "candidate-binding", candidateMatched, candidateMatched, true);

  const evidenceKindsComplete = Object.entries(REQUIRED_EVIDENCE_KINDS).every(
    ([kind, minimum]) => Number(evidence.kinds[kind] || 0) >= minimum,
  );
  gate(
    result,
    "verified-private-evidence",
    evidenceKindsComplete,
    evidence.verified.length,
    Object.values(REQUIRED_EVIDENCE_KINDS).reduce(
      (total, value) => total + value,
      0,
    ),
  );

  const runEvidenceValid = bindEvidence(
    run.evidence,
    evidence,
    usedEvidence,
    ["session_ledger", "mode_authority_ledger"],
    null,
    [
      run.runRef,
      run.initialSessionRef,
      run.reconnectSessionRef,
      run.conversationRef,
    ],
  );
  const sessionValid =
    SHA_REF.test(String(run.runRef || "")) &&
    SHA_REF.test(String(run.initialSessionRef || "")) &&
    SHA_REF.test(String(run.reconnectSessionRef || "")) &&
    SHA_REF.test(String(run.conversationRef || "")) &&
    run.initialSessionRef !== run.reconnectSessionRef &&
    run.reconnectConversationRef === run.conversationRef &&
    run.initialSessionEnded === true &&
    run.reconnectExplicitlyStarted === true &&
    run.acceptedWorkCancelledByHangupCount === 0 &&
    run.unsolicitedResultCallCount === 0 &&
    run.modeAuthoritySource === "persisted_call_session" &&
    runEvidenceValid &&
    matchingObservation(run.evidence, evidence, "session_ledger", "session", {
      initialSessionRef: run.initialSessionRef,
      reconnectSessionRef: run.reconnectSessionRef,
      conversationRef: run.conversationRef,
      initialSessionEnded: run.initialSessionEnded,
      reconnectExplicitlyStarted: run.reconnectExplicitlyStarted,
      acceptedWorkCancelledByHangupCount:
        run.acceptedWorkCancelledByHangupCount,
      unsolicitedResultCallCount: run.unsolicitedResultCallCount,
    });
  gate(
    result,
    "exact-session-and-reconnect-binding",
    sessionValid,
    sessionValid,
    true,
  );

  const workerIdentitiesValid =
    workers.length === 2 &&
    workers.filter((worker) => worker?.label === "A").length === 1 &&
    workers.filter((worker) => worker?.label === "B").length === 1 &&
    [...workerRefs, ...missionRefs, ...attemptRefs, ...launchReceipts].every(
      (value) => SHA_REF.test(String(value || "")),
    ) &&
    unique(workerRefs) &&
    unique(missionRefs) &&
    unique(attemptRefs) &&
    unique(launchReceipts);
  gate(
    result,
    "two-exact-independent-workers",
    workerIdentitiesValid,
    workers.length,
    2,
  );

  const callLaunchCommon = commonTurn(
    turns.authorizedCallLaunch,
    {
      ordinal: 1,
      kind: "authorizedCallLaunch",
      mode: "call",
      directlyAddressed: true,
      sideEffectAuthorityGranted: true,
      outputAudio: true,
      evidenceKinds: [
        "voice_transcript",
        "voice_recording",
        "logical_turn_ledger",
        "worker_ledger",
        "action_ledger",
        "mode_authority_ledger",
      ],
    },
    context,
    evidence,
    usedEvidence,
  );
  const callLaunchValid =
    callLaunchCommon &&
    exactEffects(turns.authorizedCallLaunch?.effects, {
      missionCount: 2,
      launchInvocationCount: 1,
      toolInvocationCount: 1,
      controllerInvocationCount: 1,
      mainResponseCount: 1,
      ttsInputCount: 1,
      assistantAudioOutputCount: 1,
    }) &&
    exactArray(turns.authorizedCallLaunch?.requestedWorkerRefs, workerRefs) &&
    exactArray(turns.authorizedCallLaunch?.acceptedWorkerRefs, workerRefs) &&
    exactArray(
      turns.authorizedCallLaunch?.acceptedLaunchReceiptRefs,
      launchReceipts,
    ) &&
    turns.authorizedCallLaunch?.rejectedLaunchReceiptCount === 0 &&
    bindEvidenceKindEntities(
      turns.authorizedCallLaunch?.evidence,
      evidence,
      usedEvidence,
      "worker_ledger",
      [
        turns.authorizedCallLaunch?.logicalTurnRef,
        ...workerRefs,
        ...missionRefs,
        ...attemptRefs,
        ...launchReceipts,
      ],
      run.initialSessionRef,
    ) &&
    matchingObservation(
      turns.authorizedCallLaunch?.evidence,
      evidence,
      "worker_ledger",
      "launch",
      {
        logicalTurnRef: turns.authorizedCallLaunch?.logicalTurnRef,
        mode: "call",
        acceptedWorkerRefs: workerRefs,
        acceptedLaunchReceiptRefs: launchReceipts,
      },
    );
  gate(
    result,
    "authorized-call-launch",
    callLaunchValid,
    callLaunchValid,
    true,
  );

  const launchCommon = commonTurn(
    turns.trustedWingLaunch,
    {
      ordinal: 2,
      kind: "trustedWingLaunch",
      mode: "wing",
      directlyAddressed: true,
      sideEffectAuthorityGranted: true,
      outputAudio: true,
      evidenceKinds: [
        "voice_transcript",
        "voice_recording",
        "logical_turn_ledger",
        "worker_ledger",
        "action_ledger",
        "mode_authority_ledger",
      ],
    },
    context,
    evidence,
    usedEvidence,
  );
  const launchValid =
    launchCommon &&
    exactEffects(turns.trustedWingLaunch?.effects, {
      missionCount: 1,
      launchInvocationCount: 1,
      toolInvocationCount: 1,
      controllerInvocationCount: 1,
      mainResponseCount: 1,
      ttsInputCount: 1,
      assistantAudioOutputCount: 1,
    }) &&
    exactArray(turns.trustedWingLaunch?.requestedWorkerRefs, [
      wingProbe.workerRef,
    ]) &&
    exactArray(turns.trustedWingLaunch?.acceptedWorkerRefs, [
      wingProbe.workerRef,
    ]) &&
    exactArray(turns.trustedWingLaunch?.acceptedLaunchReceiptRefs, [
      wingProbe.acceptedLaunchReceiptRef,
    ]) &&
    turns.trustedWingLaunch?.rejectedLaunchReceiptCount === 0 &&
    bindEvidenceKindEntities(
      turns.trustedWingLaunch?.evidence,
      evidence,
      usedEvidence,
      "worker_ledger",
      [
        turns.trustedWingLaunch?.logicalTurnRef,
        wingProbe.workerRef,
        wingProbe.missionRef,
        wingProbe.attemptRef,
        wingProbe.acceptedLaunchReceiptRef,
      ],
      run.initialSessionRef,
    ) &&
    matchingObservation(
      turns.trustedWingLaunch?.evidence,
      evidence,
      "worker_ledger",
      "launch",
      {
        logicalTurnRef: turns.trustedWingLaunch?.logicalTurnRef,
        mode: "wing",
        acceptedWorkerRefs: [wingProbe.workerRef],
        acceptedLaunchReceiptRefs: [wingProbe.acceptedLaunchReceiptRef],
      },
    ) &&
    wingProbe.runRef === run.runRef &&
    wingProbe.sessionRef === run.initialSessionRef &&
    [
      wingProbe.workerRef,
      wingProbe.missionRef,
      wingProbe.attemptRef,
      wingProbe.acceptedLaunchReceiptRef,
      wingProbe.cleanupActionRef,
      wingProbe.cleanupReceiptRef,
    ].every((ref) => SHA_REF.test(String(ref || ""))) &&
    unique([
      wingProbe.workerRef,
      wingProbe.missionRef,
      wingProbe.attemptRef,
      wingProbe.acceptedLaunchReceiptRef,
      wingProbe.cleanupActionRef,
      wingProbe.cleanupReceiptRef,
      ...workerRefs,
      ...missionRefs,
      ...attemptRefs,
      ...launchReceipts,
    ]) &&
    wingProbe.launchTurnRef === turns.trustedWingLaunch?.logicalTurnRef &&
    wingProbe.cleanupAction === "stop" &&
    wingProbe.cleanupActionReceiptCount === 1 &&
    wingProbe.terminalState === "cancelled_confirmed" &&
    wingProbe.deliveryCount === 0 &&
    wingProbe.completedBeforeHangup === true &&
    bindEvidence(
      wingProbe.evidence,
      evidence,
      usedEvidence,
      ["worker_ledger", "action_ledger"],
      run.initialSessionRef,
      [
        wingProbe.workerRef,
        wingProbe.missionRef,
        wingProbe.attemptRef,
        wingProbe.cleanupActionRef,
        wingProbe.cleanupReceiptRef,
      ],
    ) &&
    matchingObservation(
      wingProbe.evidence,
      evidence,
      "worker_ledger",
      "wing_probe",
      {
        runRef: run.runRef,
        sessionRef: run.initialSessionRef,
        workerRef: wingProbe.workerRef,
        missionRef: wingProbe.missionRef,
        attemptRef: wingProbe.attemptRef,
        acceptedLaunchReceiptRef: wingProbe.acceptedLaunchReceiptRef,
        launchTurnRef: wingProbe.launchTurnRef,
        cleanupAction: "stop",
        cleanupActionRef: wingProbe.cleanupActionRef,
        cleanupReceiptRef: wingProbe.cleanupReceiptRef,
        cleanupActionReceiptCount: 1,
        terminalState: "cancelled_confirmed",
        deliveryCount: 0,
        completedBeforeHangup: true,
      },
    ) &&
    matchingObservation(
      wingProbe.evidence,
      evidence,
      "action_ledger",
      "probe_cleanup",
      {
        workerRef: wingProbe.workerRef,
        missionRef: wingProbe.missionRef,
        attemptRef: wingProbe.attemptRef,
        cleanupAction: "stop",
        cleanupActionRef: wingProbe.cleanupActionRef,
        cleanupReceiptRef: wingProbe.cleanupReceiptRef,
        cleanupActionReceiptCount: 1,
        terminalState: "cancelled_confirmed",
        deliveryCount: 0,
        completedBeforeHangup: true,
      },
    );
  gate(result, "trusted-direct-wing-launch", launchValid, launchValid, true);

  const quickCommon = commonTurn(
    turns.quickConversation,
    {
      ordinal: 3,
      kind: "quickConversation",
      mode: "call",
      directlyAddressed: true,
      sideEffectAuthorityGranted: true,
      outputAudio: true,
      evidenceKinds: [
        "voice_transcript",
        "voice_recording",
        "logical_turn_ledger",
      ],
    },
    context,
    evidence,
    usedEvidence,
  );
  const quickValid =
    quickCommon &&
    exactEffects(turns.quickConversation?.effects, {
      mainResponseCount: 1,
      ttsInputCount: 1,
      assistantAudioOutputCount: 1,
    }) &&
    turns.quickConversation?.currentReply === true &&
    turns.quickConversation?.unrelatedToWorkerMissions === true &&
    exactArray(turns.quickConversation?.activeWorkerRefs, workerRefs) &&
    turns.quickConversation?.workerMutationCount === 0;
  gate(result, "main-responsive-quick-turn", quickValid, quickValid, true);

  const callControlCommon = commonTurn(
    turns.authorizedCallControl,
    {
      ordinal: 4,
      kind: "authorizedCallControl",
      mode: "call",
      directlyAddressed: true,
      sideEffectAuthorityGranted: true,
      outputAudio: true,
      evidenceKinds: [
        "voice_transcript",
        "voice_recording",
        "logical_turn_ledger",
        "worker_ledger",
        "action_ledger",
        "mode_authority_ledger",
      ],
    },
    context,
    evidence,
    usedEvidence,
  );
  const callControlValid =
    callControlCommon &&
    exactEffects(turns.authorizedCallControl?.effects, {
      actionCount: 1,
      controlInvocationCount: 1,
      toolInvocationCount: 1,
      controllerInvocationCount: 1,
      mainResponseCount: 1,
      ttsInputCount: 1,
      assistantAudioOutputCount: 1,
    }) &&
    turns.authorizedCallControl?.action === "message" &&
    SHA_REF.test(String(turns.authorizedCallControl?.actionRef || "")) &&
    SHA_REF.test(
      String(turns.authorizedCallControl?.acceptedActionReceiptRef || ""),
    ) &&
    turns.authorizedCallControl?.targetWorkerRef === workerA.workerRef &&
    turns.authorizedCallControl?.targetMissionRef === workerA.missionRef &&
    turns.authorizedCallControl?.targetAttemptRef === workerA.attemptRef &&
    turns.authorizedCallControl?.nonTargetWorkerRef === workerB.workerRef &&
    turns.authorizedCallControl?.targetActionReceiptCount === 1 &&
    turns.authorizedCallControl?.nonTargetActionReceiptCount === 0 &&
    turns.authorizedCallControl?.targetMutationCount === 1 &&
    turns.authorizedCallControl?.nonTargetMutationCount === 0 &&
    unique([
      turns.authorizedCallControl?.actionRef,
      turns.authorizedCallControl?.acceptedActionReceiptRef,
      ...workerRefs,
      ...missionRefs,
      ...attemptRefs,
      ...launchReceipts,
    ]) &&
    bindEvidenceKindEntities(
      turns.authorizedCallControl?.evidence,
      evidence,
      usedEvidence,
      "action_ledger",
      [
        turns.authorizedCallControl?.logicalTurnRef,
        turns.authorizedCallControl?.actionRef,
        turns.authorizedCallControl?.acceptedActionReceiptRef,
        turns.authorizedCallControl?.targetWorkerRef,
        turns.authorizedCallControl?.targetMissionRef,
        turns.authorizedCallControl?.targetAttemptRef,
        turns.authorizedCallControl?.nonTargetWorkerRef,
      ],
      run.initialSessionRef,
    );
  gate(
    result,
    "authorized-call-control-a-only",
    callControlValid,
    callControlValid,
    true,
  );

  const controlCommon = commonTurn(
    turns.trustedWingControl,
    {
      ordinal: 5,
      kind: "trustedWingControl",
      mode: "wing",
      directlyAddressed: true,
      sideEffectAuthorityGranted: true,
      outputAudio: true,
      evidenceKinds: [
        "voice_transcript",
        "voice_recording",
        "logical_turn_ledger",
        "worker_ledger",
        "action_ledger",
        "mode_authority_ledger",
      ],
    },
    context,
    evidence,
    usedEvidence,
  );
  const controlValid =
    controlCommon &&
    exactEffects(turns.trustedWingControl?.effects, {
      actionCount: 1,
      controlInvocationCount: 1,
      toolInvocationCount: 1,
      controllerInvocationCount: 1,
      mainResponseCount: 1,
      ttsInputCount: 1,
      assistantAudioOutputCount: 1,
    }) &&
    turns.trustedWingControl?.action === "steer" &&
    SHA_REF.test(String(turns.trustedWingControl?.actionRef || "")) &&
    SHA_REF.test(
      String(turns.trustedWingControl?.acceptedActionReceiptRef || ""),
    ) &&
    turns.trustedWingControl?.targetWorkerRef === workerA.workerRef &&
    turns.trustedWingControl?.targetMissionRef === workerA.missionRef &&
    turns.trustedWingControl?.targetAttemptRef === workerA.attemptRef &&
    turns.trustedWingControl?.nonTargetWorkerRef === workerB.workerRef &&
    turns.trustedWingControl?.targetActionReceiptCount === 1 &&
    turns.trustedWingControl?.nonTargetActionReceiptCount === 0 &&
    turns.trustedWingControl?.targetMutationCount === 1 &&
    turns.trustedWingControl?.nonTargetMutationCount === 0 &&
    unique([
      turns.trustedWingControl?.actionRef,
      turns.trustedWingControl?.acceptedActionReceiptRef,
      turns.authorizedCallControl?.actionRef,
      turns.authorizedCallControl?.acceptedActionReceiptRef,
      ...workerRefs,
      ...missionRefs,
      ...attemptRefs,
      ...launchReceipts,
    ]) &&
    bindEvidenceKindEntities(
      turns.trustedWingControl?.evidence,
      evidence,
      usedEvidence,
      "action_ledger",
      [
        turns.trustedWingControl?.logicalTurnRef,
        turns.trustedWingControl?.actionRef,
        turns.trustedWingControl?.acceptedActionReceiptRef,
        turns.trustedWingControl?.targetWorkerRef,
        turns.trustedWingControl?.targetMissionRef,
        turns.trustedWingControl?.targetAttemptRef,
        turns.trustedWingControl?.nonTargetWorkerRef,
      ],
      run.initialSessionRef,
    );
  gate(
    result,
    "trusted-direct-wing-steer-a-only",
    controlValid,
    controlValid,
    true,
  );

  const passiveCommon = commonTurn(
    turns.passiveWingDenial,
    {
      ordinal: 6,
      kind: "passiveWingDenial",
      mode: "wing",
      directlyAddressed: false,
      sideEffectAuthorityGranted: false,
      outputAudio: false,
      evidenceKinds: [
        "voice_transcript",
        "voice_recording",
        "logical_turn_ledger",
        "mode_authority_ledger",
        "action_ledger",
      ],
    },
    context,
    evidence,
    usedEvidence,
  );
  const passiveValid =
    passiveCommon &&
    turns.passiveWingDenial?.transcriptObservationCount >= 1 &&
    exactEffects(turns.passiveWingDenial?.effects, {});
  gate(result, "passive-wing-zero-authority", passiveValid, passiveValid, true);

  const listenOnlyCommon = commonTurn(
    turns.listenOnlyDenial,
    {
      ordinal: 7,
      kind: "listenOnlyDenial",
      mode: "listen_only",
      directlyAddressed: true,
      sideEffectAuthorityGranted: false,
      outputAudio: false,
      evidenceKinds: [
        "voice_transcript",
        "voice_recording",
        "logical_turn_ledger",
        "mode_authority_ledger",
        "action_ledger",
      ],
    },
    context,
    evidence,
    usedEvidence,
  );
  const listenOnlyValid =
    listenOnlyCommon &&
    turns.listenOnlyDenial?.ambientTranscriptCount >= 1 &&
    exactEffects(turns.listenOnlyDenial?.effects, {});
  gate(
    result,
    "listen-only-zero-authority",
    listenOnlyValid,
    listenOnlyValid,
    true,
  );

  const inputEvidenceValid = bindEvidence(
    manifest.inputGroup?.evidence,
    evidence,
    usedEvidence,
    ["upload_ledger"],
    run.initialSessionRef,
    inputs.flatMap((item) => [item?.uploadRef, item?.targetWorkerRef]),
  );
  const orderedInputValid =
    ["linked_chat", "telegram"].includes(manifest.inputGroup?.ingressSurface) &&
    inputs.length >= 2 &&
    inputs.every((item, index) => {
      if (
        !isRecord(item) ||
        item.ordinal !== index + 1 ||
        !SHA_REF.test(String(item.uploadRef || "")) ||
        !SHA256.test(String(item.sha256 || "")) ||
        !Number.isSafeInteger(item.bytes) ||
        item.bytes <= 0 ||
        !workerRefs.includes(item.targetWorkerRef)
      ) {
        return false;
      }
      const source = binaryEvidence(
        item.sourceEvidence,
        evidence,
        usedEvidence,
        "input_file",
        run.initialSessionRef,
        [item.uploadRef, item.targetWorkerRef],
      );
      return (
        source !== null &&
        source.sha256 === item.sha256 &&
        source.bytes === item.bytes &&
        matchingObservation(
          manifest.inputGroup?.evidence,
          evidence,
          "upload_ledger",
          "input",
          {
            ordinal: item.ordinal,
            uploadRef: item.uploadRef,
            sha256: item.sha256,
            bytes: item.bytes,
            targetWorkerRef: item.targetWorkerRef,
            sourceEvidence: item.sourceEvidence,
          },
        )
      );
    }) &&
    unique(inputs.map((item) => item.uploadRef)) &&
    manifest.inputGroup?.crossWorkerLeakCount === 0 &&
    inputEvidenceValid;
  const workerInputsValid = workers.every((worker) => {
    const expectedInputs = inputs
      .filter((item) => item.targetWorkerRef === worker.workerRef)
      .map((item) => item.uploadRef);
    return (
      expectedInputs.length > 0 &&
      exactArray(worker.inputRefs, expectedInputs) &&
      exactArray(worker.observedInputRefs, expectedInputs) &&
      matchingObservation(
        worker.evidence,
        evidence,
        "worker_ledger",
        "worker",
        {
          workerRef: worker.workerRef,
          missionRef: worker.missionRef,
          attemptRef: worker.attemptRef,
          inputRefs: expectedInputs,
          observedInputRefs: expectedInputs,
        },
      )
    );
  });
  gate(
    result,
    "exact-ordered-file-binding",
    orderedInputValid && workerInputsValid,
    inputs.length,
    ">=2_exact",
  );

  const workersValid = workers.every((worker) => {
    const evidenceValid = bindEvidence(
      worker.evidence,
      evidence,
      usedEvidence,
      [
        "worker_ledger",
        "capability_ledger",
        "callback_ledger",
        "delivery_ledger",
        "artifact_open_capture",
      ],
    );
    const exactEvidenceValid = [
      [
        "worker_ledger",
        [
          worker.workerRef,
          worker.missionRef,
          worker.attemptRef,
          worker.acceptedLaunchReceiptRef,
          worker.artifactRef,
        ],
      ],
      ["capability_ledger", [worker.workerRef, worker.missionRef]],
      [
        "callback_ledger",
        [
          worker.workerRef,
          worker.missionRef,
          worker.attemptRef,
          worker.artifactRef,
        ],
      ],
      [
        "delivery_ledger",
        [
          worker.workerRef,
          worker.missionRef,
          worker.attemptRef,
          worker.artifactRef,
        ],
      ],
      [
        "artifact_open_capture",
        [
          worker.workerRef,
          worker.missionRef,
          worker.attemptRef,
          worker.artifactRef,
        ],
      ],
    ].every(([kind, refs]) =>
      bindEvidenceKindEntities(
        worker.evidence,
        evidence,
        usedEvidence,
        kind,
        refs,
      ),
    );
    const launchTurn = turns.authorizedCallLaunch;
    const observedWorkerValid = matchingObservation(
      worker.evidence,
      evidence,
      "worker_ledger",
      "worker",
      {
        workerRef: worker.workerRef,
        missionRef: worker.missionRef,
        attemptRef: worker.attemptRef,
        acceptedLaunchReceiptRef: worker.acceptedLaunchReceiptRef,
        launchTurnRef: worker.launchTurnRef,
        launchMode: worker.launchMode,
        accepted: worker.accepted,
        independent: worker.independent,
        inputRefs: worker.inputRefs,
        observedInputRefs: worker.observedInputRefs,
        activeAtHangup: worker.activeAtHangup,
        cancelledByHangup: worker.cancelledByHangup,
        reconnectMissionRef: worker.reconnectMissionRef,
        terminalState: worker.terminalState,
        attemptCount: worker.attemptCount,
        callbackCount: worker.callbackCount,
        deliveryCount: worker.deliveryCount,
        artifactRef: worker.artifactRef,
        spokenCompletionCount: worker.spokenCompletionCount,
      },
    );
    const observedCapabilitiesValid = matchingObservation(
      worker.evidence,
      evidence,
      "capability_ledger",
      "capability",
      {
        workerRef: worker.workerRef,
        missionRef: worker.missionRef,
        contextBindingMatched: worker.contextBindingMatched,
        requiredCapabilitiesPreserved: worker.requiredCapabilitiesPreserved,
        fallbackCapabilityLossCount: worker.fallbackCapabilityLossCount,
        memoryRecallReceiptCount: worker.memoryRecallReceiptCount,
        connectedToolReceiptCount: worker.connectedToolReceiptCount,
      },
    );
    return (
      worker.runRef === run.runRef &&
      worker.launchSessionRef === run.initialSessionRef &&
      worker.launchTurnRef === launchTurn?.logicalTurnRef &&
      worker.launchMode === launchTurn?.mode &&
      worker.accepted === true &&
      worker.independent === true &&
      worker.contextBindingMatched === true &&
      worker.requiredCapabilitiesPreserved === true &&
      worker.fallbackCapabilityLossCount === 0 &&
      isCount(worker.memoryRecallReceiptCount) &&
      isCount(worker.connectedToolReceiptCount) &&
      worker.activeAtHangup === true &&
      worker.cancelledByHangup === false &&
      worker.reconnectMissionRef === worker.missionRef &&
      worker.terminalState === "completed" &&
      worker.attemptCount === 1 &&
      worker.callbackCount === 1 &&
      worker.deliveryCount === 1 &&
      SHA_REF.test(String(worker.artifactRef || "")) &&
      worker.spokenCompletionCount === 1 &&
      evidenceValid &&
      exactEvidenceValid &&
      observedWorkerValid &&
      observedCapabilitiesValid
    );
  });
  const capabilityValid =
    workersValid &&
    workers.reduce((sum, worker) => sum + worker.memoryRecallReceiptCount, 0) >=
      1 &&
    workers.reduce(
      (sum, worker) => sum + worker.connectedToolReceiptCount,
      0,
    ) >= 1;
  gate(
    result,
    "worker-context-capability-parity",
    capabilityValid,
    capabilityValid,
    true,
  );

  const deliveryWorkers = new Map(
    deliveries.map((item) => [item?.workerRef, item]),
  );
  const deliveriesValid =
    deliveries.length === 2 &&
    unique(deliveries.map((item) => item?.artifactRef)) &&
    unique(deliveries.map((item) => item?.artifactSha256)) &&
    workers.every((worker) => {
      const delivery = deliveryWorkers.get(worker.workerRef);
      const evidenceValid = bindEvidence(
        delivery?.evidence,
        evidence,
        usedEvidence,
        [
          "callback_ledger",
          "delivery_ledger",
          "linked_chat_capture",
          "active_work_capture",
          "artifact_open_capture",
        ],
        run.reconnectSessionRef,
      );
      const deliveryEntityRefs = [
        worker.workerRef,
        worker.missionRef,
        worker.attemptRef,
        worker.artifactRef,
      ];
      const exactEvidenceValid = [
        ["callback_ledger", deliveryEntityRefs],
        ["delivery_ledger", deliveryEntityRefs],
        ["linked_chat_capture", [worker.workerRef, worker.artifactRef]],
        ["active_work_capture", [worker.workerRef, worker.artifactRef]],
        ["artifact_open_capture", deliveryEntityRefs],
      ].every(([kind, refs]) =>
        bindEvidenceKindEntities(
          delivery?.evidence,
          evidence,
          usedEvidence,
          kind,
          refs,
          run.reconnectSessionRef,
        ),
      );
      const artifact = binaryEvidence(
        delivery?.artifactEvidence,
        evidence,
        usedEvidence,
        "delivered_artifact",
        run.reconnectSessionRef,
        deliveryEntityRefs,
      );
      const deliveryObservation = {
        workerRef: worker.workerRef,
        missionRef: worker.missionRef,
        attemptRef: worker.attemptRef,
        artifactRef: worker.artifactRef,
        artifactSha256: delivery?.artifactSha256,
        artifactEvidence: delivery?.artifactEvidence,
        callbackCount: delivery?.callbackCount,
        linkedChatDeliveryCount: delivery?.linkedChatDeliveryCount,
        activeWorkDeliveryCount: delivery?.activeWorkDeliveryCount,
        duplicateDeliveryCount: delivery?.duplicateDeliveryCount,
        deliveredAfterHangup: delivery?.deliveredAfterHangup,
        reconnectSessionRef: delivery?.reconnectSessionRef,
        opened: delivery?.opened,
        openOrDownloadActionWorked: delivery?.openOrDownloadActionWorked,
      };
      const observedDeliveryValid = [
        "callback_ledger",
        "delivery_ledger",
      ].every((kind) =>
        matchingObservation(
          delivery?.evidence,
          evidence,
          kind,
          "delivery",
          deliveryObservation,
        ),
      );
      const observedOpenValid = matchingObservation(
        delivery?.evidence,
        evidence,
        "artifact_open_capture",
        "artifact_open",
        {
          workerRef: worker.workerRef,
          missionRef: worker.missionRef,
          attemptRef: worker.attemptRef,
          artifactRef: worker.artifactRef,
          artifactSha256: delivery?.artifactSha256,
          artifactEvidence: delivery?.artifactEvidence,
          opened: true,
          openOrDownloadActionWorked: true,
        },
      );
      return (
        isRecord(delivery) &&
        delivery.runRef === run.runRef &&
        delivery.missionRef === worker.missionRef &&
        delivery.attemptRef === worker.attemptRef &&
        delivery.artifactRef === worker.artifactRef &&
        SHA256.test(String(delivery.artifactSha256 || "")) &&
        artifact !== null &&
        artifact.sha256 === delivery.artifactSha256 &&
        delivery.callbackCount === 1 &&
        delivery.linkedChatDeliveryCount === 1 &&
        delivery.activeWorkDeliveryCount === 1 &&
        delivery.duplicateDeliveryCount === 0 &&
        delivery.deliveredAfterHangup === true &&
        delivery.reconnectSessionRef === run.reconnectSessionRef &&
        delivery.opened === true &&
        delivery.openOrDownloadActionWorked === true &&
        evidenceValid &&
        exactEvidenceValid &&
        observedDeliveryValid &&
        observedOpenValid
      );
    });
  gate(
    result,
    "callback-delivery-and-artifact-once",
    deliveriesValid,
    deliveries.length,
    2,
  );

  const completionTurns = asArray(voice.completionTurns);
  const completionValid =
    completionTurns.length === 2 &&
    completionTurns.every((turn, index) => {
      const worker = workers[index];
      const directEvidenceValid = bindDirectEvidence(
        turn,
        ["transcriptEvidence", "outputAudioEvidence"],
        evidence,
        usedEvidence,
        ["voice_transcript", "voice_recording"],
        run.reconnectSessionRef,
      );
      const listedEvidenceValid = bindEvidence(
        turn.evidence,
        evidence,
        usedEvidence,
        [
          "voice_transcript",
          "voice_recording",
          "logical_turn_ledger",
          "delivery_ledger",
        ],
        run.reconnectSessionRef,
        [turn.logicalTurnRef],
      );
      const exactDeliveryEvidenceValid = bindEvidenceKindEntities(
        turn.evidence,
        evidence,
        usedEvidence,
        "delivery_ledger",
        [
          turn.logicalTurnRef,
          turn.workerRef,
          turn.missionRef,
          turn.attemptRef,
          turn.artifactRef,
        ],
        run.reconnectSessionRef,
      );
      return (
        isRecord(turn) &&
        turn.ordinal === index + 8 &&
        turn.kind === "workerCompletion" &&
        turn.runRef === run.runRef &&
        turn.sessionRef === run.reconnectSessionRef &&
        turn.conversationRef === run.conversationRef &&
        turn.mode === "call" &&
        SHA_REF.test(String(turn.logicalTurnRef || "")) &&
        Number.isSafeInteger(turn.logicalRevision) &&
        turn.logicalRevision > 0 &&
        turn.workerRef === worker.workerRef &&
        turn.missionRef === worker.missionRef &&
        turn.attemptRef === worker.attemptRef &&
        turn.artifactRef === worker.artifactRef &&
        turn.truthful === true &&
        turn.spokenStatusOrCompletionCount === 1 &&
        turn.duplicateSpeechCount === 0 &&
        turn.transcriptVisible === true &&
        turn.transcriptMatchedAudio === true &&
        turn.assistantSpeakerRef === voice.queenSpeakerRef &&
        exactEffects(turn.effects, {
          mainResponseCount: 1,
          ttsInputCount: 1,
          assistantAudioOutputCount: 1,
        }) &&
        directEvidenceValid &&
        listedEvidenceValid &&
        exactDeliveryEvidenceValid &&
        turnObservation(turn, evidence, "voice_transcript", [
          turn.transcriptEvidence,
        ]) &&
        turnObservation(turn, evidence, "logical_turn_ledger") &&
        turnObservation(turn, evidence, "delivery_ledger")
      );
    });
  const soleSpeakerValid =
    SHA_REF.test(String(voice.queenSpeakerRef || "")) &&
    exactArray(voice.observedAssistantSpeakerRefs, [voice.queenSpeakerRef]) &&
    [
      turns.authorizedCallLaunch,
      turns.trustedWingLaunch,
      turns.quickConversation,
      turns.authorizedCallControl,
      turns.trustedWingControl,
    ]
      .filter(Boolean)
      .every((turn) => turn.assistantSpeakerRef === voice.queenSpeakerRef) &&
    completionValid;
  gate(
    result,
    "audible-transcript-audio-and-sole-queen",
    soleSpeakerValid,
    soleSpeakerValid,
    true,
  );

  const surface = isRecord(manifest.surfaceContinuity)
    ? manifest.surfaceContinuity
    : {};
  const surfaceEvidenceValid = bindEvidence(
    surface.evidence,
    evidence,
    usedEvidence,
    ["linked_chat_capture", "active_work_capture"],
    null,
    workerRefs,
  );
  const surfaceObservationsValid = [
    ["linked_chat", "before_hangup", []],
    [
      "linked_chat",
      "after_reconnect",
      workers.map((worker) => worker.artifactRef),
    ],
    ["active_work", "before_hangup", []],
    [
      "active_work",
      "after_reconnect",
      workers.map((worker) => worker.artifactRef),
    ],
  ].every(([surfaceName, phase, artifactRefs]) =>
    matchingObservation(
      surface.evidence,
      evidence,
      surfaceName === "linked_chat"
        ? "linked_chat_capture"
        : "active_work_capture",
      "surface",
      {
        surface: surfaceName,
        phase,
        workerRefs,
        artifactRefs,
      },
    ),
  );
  const surfaceValid =
    exactArray(surface.linkedChatBeforeHangupWorkerRefs, workerRefs) &&
    exactArray(surface.linkedChatAfterReconnectWorkerRefs, workerRefs) &&
    exactArray(surface.activeWorkBeforeHangupWorkerRefs, workerRefs) &&
    exactArray(surface.activeWorkAfterReconnectWorkerRefs, workerRefs) &&
    surfaceEvidenceValid &&
    surfaceObservationsValid;
  const hangupValid =
    sessionValid &&
    workers.every(
      (worker) =>
        worker.activeAtHangup === true &&
        worker.cancelledByHangup === false &&
        worker.reconnectMissionRef === worker.missionRef,
    ) &&
    deliveries.every((delivery) => delivery.deliveredAfterHangup === true) &&
    surfaceValid;
  gate(
    result,
    "hangup-reconnect-surface-continuity",
    hangupValid,
    hangupValid,
    true,
  );

  const resilience = isRecord(manifest.resilience) ? manifest.resilience : {};
  const fallback = isRecord(resilience.fallback) ? resilience.fallback : {};
  const fallbackRequired = fallback.required === true;
  const fallbackValid =
    fallbackRequired &&
    fallback.observed === true &&
    SHA_REF.test(String(fallback.controlReceiptRef || "")) &&
    fallback.controlReceiptCount === 1 &&
    fallback.failure === "provider_temporarily_unavailable" &&
    fallback.preModel === true &&
    typeof fallback.primaryProvider === "string" &&
    fallback.primaryProvider.length > 0 &&
    typeof fallback.primaryModel === "string" &&
    fallback.primaryModel.length > 0 &&
    fallback.primaryStartedCount === 0 &&
    fallback.primaryCompletedCount === 0 &&
    fallback.providerHealthMutationCount === 0 &&
    fallback.providerHealthSuppressed === false &&
    typeof fallback.fallbackProvider === "string" &&
    fallback.fallbackProvider.length > 0 &&
    typeof fallback.fallbackModel === "string" &&
    fallback.fallbackModel.length > 0 &&
    fallback.fallbackStartedCount === 1 &&
    fallback.fallbackCompletedCount === 1 &&
    fallback.providerFallbackCompletedCount === 1 &&
    SHA_REF.test(String(fallback.primaryAttemptRef || "")) &&
    SHA_REF.test(String(fallback.fallbackAttemptRef || "")) &&
    fallback.primaryAttemptRef !== fallback.fallbackAttemptRef &&
    exactArray(fallback.workerRefs, workerRefs) &&
    exactArray(fallback.missionRefs, missionRefs) &&
    fallback.requiredCapabilitiesPreserved === true &&
    fallback.mainAvailable === true &&
    fallback.duplicateLaunchReceiptCount === 0 &&
    bindEvidence(
      fallback.evidence,
      evidence,
      usedEvidence,
      ["capability_ledger", "worker_ledger"],
      run.initialSessionRef,
      [...workerRefs, ...missionRefs],
    ) &&
    bindEvidenceKindEntities(
      fallback.evidence,
      evidence,
      usedEvidence,
      "capability_ledger",
      [
        fallback.controlReceiptRef,
        fallback.primaryAttemptRef,
        fallback.fallbackAttemptRef,
        ...workerRefs,
      ],
      run.initialSessionRef,
    ) &&
    matchingObservation(
      fallback.evidence,
      evidence,
      "capability_ledger",
      "fallback",
      {
        required: true,
        observed: true,
        controlReceiptRef: fallback.controlReceiptRef,
        controlReceiptCount: 1,
        failure: "provider_temporarily_unavailable",
        preModel: true,
        primaryProvider: fallback.primaryProvider,
        primaryModel: fallback.primaryModel,
        primaryStartedCount: 0,
        primaryCompletedCount: 0,
        providerHealthMutationCount: 0,
        providerHealthSuppressed: false,
        fallbackProvider: fallback.fallbackProvider,
        fallbackModel: fallback.fallbackModel,
        fallbackStartedCount: 1,
        fallbackCompletedCount: 1,
        providerFallbackCompletedCount: 1,
        primaryAttemptRef: fallback.primaryAttemptRef,
        fallbackAttemptRef: fallback.fallbackAttemptRef,
        workerRefs,
        missionRefs,
        requiredCapabilitiesPreserved: true,
        mainAvailable: true,
        duplicateLaunchReceiptCount: 0,
      },
    );
  gate(
    result,
    "required-fallback-capability-parity",
    fallbackValid,
    fallbackValid,
    true,
  );

  const restart = isRecord(resilience.restart) ? resilience.restart : {};
  const restartValid =
    restart.required === true &&
    restart.observed === true &&
    SHA_REF.test(String(restart.beforeRuntimeRef || "")) &&
    SHA_REF.test(String(restart.afterRuntimeRef || "")) &&
    restart.beforeRuntimeRef !== restart.afterRuntimeRef &&
    exactArray(restart.workerRefs, workerRefs) &&
    exactArray(restart.missionRefs, missionRefs) &&
    restart.mainAvailableBefore === true &&
    restart.mainAvailableAfter === true &&
    restart.lostMissionCount === 0 &&
    restart.duplicateLaunchReceiptCount === 0 &&
    bindEvidence(
      restart.evidence,
      evidence,
      usedEvidence,
      ["session_ledger", "worker_ledger"],
      null,
      workerRefs,
    ) &&
    bindEvidenceKindEntities(
      restart.evidence,
      evidence,
      usedEvidence,
      "session_ledger",
      [restart.beforeRuntimeRef, restart.afterRuntimeRef, ...workerRefs],
    ) &&
    matchingObservation(
      restart.evidence,
      evidence,
      "session_ledger",
      "restart",
      {
        required: true,
        observed: true,
        beforeRuntimeRef: restart.beforeRuntimeRef,
        afterRuntimeRef: restart.afterRuntimeRef,
        workerRefs,
        missionRefs,
        mainAvailableBefore: true,
        mainAvailableAfter: true,
        lostMissionCount: 0,
        duplicateLaunchReceiptCount: 0,
      },
    );
  gate(
    result,
    "required-restart-main-availability",
    restartValid,
    restartValid,
    true,
  );

  const safety = isRecord(manifest.publicSafety) ? manifest.publicSafety : {};
  const safetyEvidenceValid = bindEvidence(
    safety.evidence,
    evidence,
    usedEvidence,
    ["public_safety_report"],
    null,
    [run.runRef, run.initialSessionRef, run.reconnectSessionRef],
  );
  const safetyValid =
    safety.rawEvidencePrivate === true &&
    safety.publicReportContentFree === true &&
    safety.reviewed === true &&
    safetyEvidenceValid &&
    matchingObservation(
      safety.evidence,
      evidence,
      "public_safety_report",
      "public_safety",
      {
        rawEvidencePrivate: true,
        publicReportContentFree: true,
        reviewed: true,
      },
    );
  gate(result, "public-safe-report-boundary", safetyValid, safetyValid, true);

  const orderedTurns = [
    ...TURN_ORDER.map((key) => turns[key]),
    ...completionTurns,
  ];
  const logicalTurnRefs = orderedTurns.map((turn) => turn?.logicalTurnRef);
  const turnOrderValid =
    exactArray(voice.turnOrder, TURN_ORDER) &&
    orderedTurns.length === TURN_ORDER.length + 2 &&
    orderedTurns.every(
      (turn, index) =>
        isRecord(turn) &&
        turn.ordinal === index + 1 &&
        SHA_REF.test(String(turn.logicalTurnRef || "")) &&
        Number.isSafeInteger(turn.logicalRevision) &&
        turn.logicalRevision > 0 &&
        (index === 0 ||
          turn.logicalRevision > orderedTurns[index - 1].logicalRevision),
    ) &&
    new Set(logicalTurnRefs).size === logicalTurnRefs.length;
  gate(
    result,
    "ordered-logical-turn-revisions",
    turnOrderValid,
    turnOrderValid,
    true,
  );

  const evidenceBindingValid =
    usedEvidence.size === evidence.byId.size &&
    [...evidence.byId.keys()].every((id) => usedEvidence.has(id));
  gate(
    result,
    "all-evidence-bound-to-full-journey",
    evidenceBindingValid,
    usedEvidence.size,
    evidence.byId.size,
  );

  result.counts = {
    sessions: sessionValid ? 2 : 0,
    workers: workers.length,
    actions: [turns.authorizedCallControl, turns.trustedWingControl].filter(
      isRecord,
    ).length,
    inputs: inputs.length,
    deliveries: deliveries.length,
    artifactsOpened: deliveries.filter((item) => item?.opened === true).length,
    audiblePositiveTurns:
      [
        turns.authorizedCallLaunch,
        turns.trustedWingLaunch,
        turns.quickConversation,
        turns.authorizedCallControl,
        turns.trustedWingControl,
      ].filter((turn) => turn?.effects?.assistantAudioOutputCount === 1)
        .length +
      completionTurns.filter(
        (turn) => turn?.effects?.assistantAudioOutputCount === 1,
      ).length,
    denialTurns: [turns.passiveWingDenial, turns.listenOnlyDenial].filter(
      (turn) => turn?.effects?.assistantAudioOutputCount === 0,
    ).length,
    verifiedEvidenceFiles: evidence.verified.length,
  };
  result.evidenceDigest = digestValue({
    evidence: evidence.verified,
    gates: result.gates.map(({ id, status }) => ({ id, status })),
  });
  result.status = result.gates.every((item) => item.status === "PASS")
    ? "PASS"
    : "FAIL";
  result.fullJourneyStatus = result.status;
  result.failures = result.gates
    .filter((item) => item.status !== "PASS")
    .map((item) => ({ code: item.id.replace(/-/g, "_") }));
  return result;
}

function assertSanitizedResult(result) {
  const serialized = JSON.stringify(result);
  const forbidden = [
    ROOT,
    os.homedir(),
    "sha256:",
    "transcriptText",
    "http://",
    "https://",
  ];
  if (forbidden.some((value) => value && serialized.includes(value))) {
    throw new Error("sanitized_result_leak");
  }
}

function writeJson(filePath, value, evidenceRoot) {
  const parent = path.dirname(filePath);
  const parentMetadata = fs.lstatSync(parent);
  const exactParent = fs.realpathSync(parent);
  if (
    parentMetadata.isSymbolicLink() ||
    !parentMetadata.isDirectory() ||
    !inside(exactParent, evidenceRoot)
  ) {
    throw new Error("result_parent_invalid");
  }
  if (fs.existsSync(filePath)) {
    const metadata = fs.lstatSync(filePath);
    if (
      metadata.isSymbolicLink() ||
      !metadata.isFile() ||
      metadata.nlink !== 1
    ) {
      throw new Error("result_path_invalid");
    }
  }
  const flags =
    fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_NOFOLLOW;
  const descriptor = fs.openSync(filePath, flags, 0o600);
  try {
    const metadata = fs.fstatSync(descriptor);
    if (!metadata.isFile() || metadata.nlink !== 1) {
      throw new Error("result_path_invalid");
    }
    fs.fchmodSync(descriptor, 0o600);
    fs.ftruncateSync(descriptor, 0);
    fs.writeFileSync(descriptor, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  } finally {
    fs.closeSync(descriptor);
  }
}

function blockedResult(code) {
  const result = baseResult();
  result.failures = [{ code: SAFE_KIND.test(code) ? code : "runner_blocked" }];
  return result;
}

function assessManifest(
  manifest,
  {
    evidenceRoot,
    identityDigests,
    checkedAt = Date.now(),
    installedOwnerProven = true,
  },
) {
  if (isRecord(manifest) && Object.hasOwn(manifest, "status")) {
    throw new Error("caller_declared_pass_forbidden");
  }
  if (
    !isRecord(manifest) ||
    manifest.schema !== EVIDENCE_SCHEMA ||
    manifest.caseId !== CASE_ID ||
    !isRecord(manifest.run) ||
    !SHA_REF.test(String(manifest.run.runRef || "")) ||
    !SHA_REF.test(String(manifest.run.initialSessionRef || "")) ||
    !SHA_REF.test(String(manifest.run.reconnectSessionRef || ""))
  ) {
    throw new Error("manifest_schema_invalid");
  }
  if (
    installedOwnerProven !== true ||
    !isRecord(identityDigests) ||
    !SHA256.test(String(identityDigests.candidateDigest || "")) ||
    !SHA256.test(String(identityDigests.artifactDigest || ""))
  ) {
    throw new Error("installed_candidate_unproven");
  }
  const runAt = parseTimestamp(manifest.runAt, "run_timestamp_invalid");
  if (
    runAt > checkedAt + MAX_FUTURE_SKEW_MS ||
    checkedAt - runAt > MAX_RESULT_AGE_MS
  ) {
    throw new Error("run_timestamp_invalid");
  }
  const evidence = verifyEvidence(
    manifest.evidence,
    evidenceRoot,
    manifest.run.runRef,
    new Set([manifest.run.initialSessionRef, manifest.run.reconnectSessionRef]),
    identityDigests,
    runAt,
    checkedAt,
  );
  return {
    result: evaluateManifest(manifest, identityDigests, evidence),
    evidence,
    runAt: new Date(runAt).toISOString(),
  };
}

function run(args) {
  const manifest = readJsonFile(args.manifest, MAX_MANIFEST_BYTES, "manifest");
  const rawIdentity = readJsonFile(
    args.artifactIdentity,
    MAX_IDENTITY_BYTES,
    "artifact_identity",
  );
  const identityDigests = candidateDigests(rawIdentity);
  return assessManifest(manifest, {
    evidenceRoot: args.evidenceRoot,
    identityDigests,
  }).result;
}

function main() {
  let args;
  let result;
  try {
    args = parseArgs(process.argv.slice(2));
    result = run(args);
  } catch (error) {
    const code = /^[a-z0-9_]{1,80}$/.test(String(error?.message || ""))
      ? String(error.message)
      : "runner_blocked";
    result = blockedResult(code);
  }
  try {
    assertSanitizedResult(result);
    if (args?.result) {
      writeJson(args.result, result, args.evidenceRoot);
    }
  } catch {
    process.stderr.write("result_write_failed\n");
    process.exitCode = 2;
    return;
  }
  process.stdout.write(`${result.status}\n`);
  process.exitCode =
    result.status === "PASS" ? 0 : result.status === "FAIL" ? 1 : 2;
}

if (require.main === module) {
  main();
}

module.exports = {
  AUTHORITY_SLICE_SCOPE,
  FULL_JOURNEY_SCOPE,
  assessManifest,
  baseResult,
  candidateDigests,
  evaluateManifest,
  parseArgs,
  run,
  verifyEvidence,
};
