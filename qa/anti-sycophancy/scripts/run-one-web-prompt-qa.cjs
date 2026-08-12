#!/usr/bin/env node
"use strict";

/**
 * Public-safe launcher for one real local Viventium Web prompt.
 *
 * The raw prompt, transcript, screenshots, identifiers, and database records are written only to
 * the explicitly supplied private directory outside this repository. Stdout contains hashes,
 * counts, structural part ordering, and terminal-state facts only. The conversation is deliberately
 * preserved. Cleanup is limited to the inserted auth session and, only for the explicit Scheduling
 * gate, the exact QA-owner/nonce task through its supported MCP delete tool.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const LOCAL_JWT_ALLOW_ENV = "VIVENTIUM_QA_ALLOW_LOCAL_JWT";
const OWNER_EMAIL_ENV = "VIVENTIUM_QA_OWNER_EMAIL";
const SCHEDULING_CREATE_TOOL = "schedule_create_mcp_scheduling-cortex";
const DEFAULT_TIMEOUT_MS = 300_000;
const DEFAULT_SETTLE_MS = 5_000;
const TERMINAL_STATUSES = new Set([
  "aborted",
  "canceled",
  "cancelled",
  "complete",
  "completed",
  "did_not_activate",
  "error",
  "failed",
  "skipped",
  "stopped",
  "success",
  "timed_out",
  "timeout",
]);
const ACTIVE_STATUSES = new Set([
  "activating",
  "brewing",
  "in_progress",
  "pending",
  "processing",
  "queued",
  "running",
  "streaming",
]);
const TERMINAL_ERROR_STATUSES = new Set([
  "aborted",
  "canceled",
  "cancelled",
  "error",
  "failed",
  "stopped",
  "timed_out",
  "timeout",
]);
const TRANSFER_TOOL_PREFIX = "lc_transfer_to_";

function hashValue(value, length = 16) {
  return crypto
    .createHash("sha256")
    .update(String(value ?? ""))
    .digest("hex")
    .slice(0, length);
}

function normalizeEmail(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
}

function uniqueRunId(caseId, date = new Date()) {
  return `${caseId}-${timestampSlug(date)}-${crypto.randomBytes(6).toString("hex")}`.slice(
    0,
    128,
  );
}

function parseArgs(argv) {
  const values = {};
  let headless = true;
  let timeoutMs = DEFAULT_TIMEOUT_MS;
  let settleMs = DEFAULT_SETTLE_MS;

  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--headed") {
      headless = false;
      continue;
    }
    if (item === "--headless") {
      headless = true;
      continue;
    }
    if (item === "--help" || item === "-h") {
      return { help: true };
    }
    if (!item.startsWith("--")) {
      throw new Error(`unknown_argument_${item}`);
    }
    const equalsIndex = item.indexOf("=");
    const key = item.slice(2, equalsIndex === -1 ? undefined : equalsIndex);
    const value =
      equalsIndex === -1 ? argv[++index] : item.slice(equalsIndex + 1);
    if (value == null || value === "") {
      throw new Error(`missing_value_${key}`);
    }
    if (key === "timeout-ms") {
      timeoutMs = Number.parseInt(value, 10);
    } else if (key === "settle-ms") {
      settleMs = Number.parseInt(value, 10);
    } else if (
      [
        "client",
        "api",
        "qa-email",
        "agent",
        "prompt",
        "case",
        "output",
        "runtime-root",
        "reopen-conversation",
        "expect-tool",
        "expect-schedule-nonce",
      ].includes(key)
    ) {
      values[key] = value;
    } else {
      throw new Error(`unknown_argument_${key}`);
    }
  }

  for (const key of [
    "client",
    "api",
    "qa-email",
    "agent",
    "prompt",
    "case",
    "output",
    "runtime-root",
  ]) {
    if (!String(values[key] || "").trim()) {
      throw new Error(`missing_required_argument_${key.replaceAll("-", "_")}`);
    }
  }
  if (!/^[A-Za-z0-9_.:-]{1,64}$/.test(values.case)) {
    throw new Error("case_must_be_a_public_safe_identifier");
  }
  const reopenConversationId = String(
    values["reopen-conversation"] || "",
  ).trim();
  if (
    reopenConversationId &&
    !/^[A-Za-z0-9_-]{1,128}$/.test(reopenConversationId)
  ) {
    throw new Error("reopen_conversation_must_be_a_safe_identifier");
  }
  const expectedToolName = String(values["expect-tool"] || "").trim();
  if (expectedToolName && !/^[A-Za-z0-9_.:-]{1,160}$/.test(expectedToolName)) {
    throw new Error("expect_tool_must_be_a_structured_tool_name");
  }
  const expectedScheduleNonce = String(
    values["expect-schedule-nonce"] || "",
  ).trim();
  if (
    expectedScheduleNonce &&
    !/^[A-Za-z0-9_-]{12,96}$/.test(expectedScheduleNonce)
  ) {
    throw new Error("expect_schedule_nonce_must_be_a_safe_identifier");
  }
  if (expectedToolName === SCHEDULING_CREATE_TOOL && !expectedScheduleNonce) {
    throw new Error("expect_schedule_nonce_required_for_scheduling_gate");
  }
  if (expectedScheduleNonce && expectedToolName !== SCHEDULING_CREATE_TOOL) {
    throw new Error("expect_schedule_nonce_requires_scheduling_create_tool");
  }
  if (
    expectedScheduleNonce &&
    !String(values.prompt).includes(expectedScheduleNonce)
  ) {
    throw new Error("expect_schedule_nonce_not_present_in_prompt");
  }
  if (reopenConversationId && expectedToolName) {
    throw new Error("expect_tool_not_supported_in_reopen_mode");
  }
  if (!Number.isFinite(timeoutMs) || timeoutMs < 5_000) {
    throw new Error("timeout_ms_must_be_at_least_5000");
  }
  if (!Number.isFinite(settleMs) || settleMs < 0 || settleMs > timeoutMs) {
    throw new Error("settle_ms_must_be_between_0_and_timeout");
  }

  return {
    apiBase: String(values.api).replace(/\/$/, ""),
    clientBase: String(values.client).replace(/\/$/, ""),
    qaEmail: normalizeEmail(values["qa-email"]),
    agentId: String(values.agent).trim(),
    prompt: String(values.prompt),
    caseId: String(values.case),
    outputDir: path.resolve(String(values.output)),
    runtimeRoot: path.resolve(String(values["runtime-root"])),
    headless,
    timeoutMs,
    settleMs,
    qaRunId: uniqueRunId(String(values.case)),
    runMode: reopenConversationId ? "reopen" : "submit",
    reopenConversationId,
    expectedToolName,
    expectedScheduleNonce,
  };
}

function printHelp() {
  process.stdout.write(`Usage:
  VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 VIVENTIUM_QA_OWNER_EMAIL=owner@example.com \\
    node qa/anti-sycophancy/scripts/run-one-web-prompt-qa.cjs \\
      --client=http://localhost:3190 --api=http://localhost:3180 \\
      --qa-email=qa@example.com --agent=agent_synthetic_main \\
      --prompt="One arbitrary synthetic prompt" --case=ANTI-003 \\
      --output=/private/path/outside/the/repository \\
      --runtime-root=/private/qa-dev-env/runtime [--headed] \\
      [--expect-tool=one_exact_configured_tool_name] \\
      [--expect-schedule-nonce=same_safe_nonce_present_in_prompt] \\
      [--reopen-conversation=existing-conversation-id]

Required inputs: client, api, qa-email, agent, prompt, case, output, runtime-root.
The output directory must be outside this repository and empty or absent.
This harness preserves the exact QA conversation and deletes only its inserted auth session.
Reopen mode submits no prompt; it verifies one existing selected-user/selected-agent conversation.
The Scheduling create expectation also requires expect-schedule-nonce. It gates one causal tool
call, one exact isolated-runtime row, supported MCP cleanup, zero residue, and stable protected rows.
`);
}

function isLocalHostname(hostname) {
  const normalized = String(hostname || "").toLowerCase();
  return (
    normalized === "localhost" ||
    normalized.endsWith(".localhost") ||
    normalized === "127.0.0.1" ||
    normalized === "::1" ||
    normalized === "[::1]"
  );
}

function assertLocalUrl(value, label) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`${label}_must_be_a_valid_local_url`);
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    !isLocalHostname(parsed.hostname)
  ) {
    throw new Error(`${label}_must_be_localhost`);
  }
}

function canonicalTarget(targetPath) {
  let ancestor = path.resolve(targetPath);
  const remainder = [];
  while (!fs.existsSync(ancestor)) {
    const parent = path.dirname(ancestor);
    if (parent === ancestor) {
      break;
    }
    remainder.unshift(path.basename(ancestor));
    ancestor = parent;
  }
  const canonicalAncestor = fs.realpathSync(ancestor);
  return path.join(canonicalAncestor, ...remainder);
}

function isWithin(parentPath, childPath) {
  const relative = path.relative(parentPath, childPath);
  return (
    relative === "" ||
    (!relative.startsWith("..") && !path.isAbsolute(relative))
  );
}

function assertHarnessSafety({
  args,
  env,
  selectedUser = null,
  repoRoot = REPO_ROOT,
}) {
  if (env.CI || env.NODE_ENV === "production") {
    throw new Error("local_qa_jwt_forbidden_in_ci_or_production");
  }
  if (env[LOCAL_JWT_ALLOW_ENV] !== "1") {
    throw new Error(`local_qa_jwt_requires_${LOCAL_JWT_ALLOW_ENV}`);
  }
  const ownerEmail = normalizeEmail(env[OWNER_EMAIL_ENV]);
  if (!ownerEmail) {
    throw new Error("missing_owner_email_guard");
  }
  if (normalizeEmail(args.qaEmail) === ownerEmail) {
    throw new Error("qa_email_matches_owner_refused");
  }
  if (selectedUser) {
    if (normalizeEmail(selectedUser.email) === ownerEmail) {
      throw new Error("selected_owner_account_refused");
    }
    if (normalizeEmail(selectedUser.email) !== normalizeEmail(args.qaEmail)) {
      throw new Error("selected_qa_identity_mismatch");
    }
    if (
      String(selectedUser.role || "")
        .trim()
        .toUpperCase() === "ADMIN"
    ) {
      throw new Error("selected_admin_account_refused");
    }
  }
  assertLocalUrl(args.clientBase, "client");
  assertLocalUrl(args.apiBase, "api");
  const canonicalRepo = fs.realpathSync(repoRoot);
  const canonicalOutput = canonicalTarget(args.outputDir);
  if (isWithin(canonicalRepo, canonicalOutput)) {
    throw new Error("private_output_must_be_outside_repo");
  }
  if (fs.existsSync(args.outputDir)) {
    if (!fs.statSync(args.outputDir).isDirectory()) {
      throw new Error("private_output_must_be_a_directory");
    }
    if (fs.readdirSync(args.outputDir).length > 0) {
      throw new Error("private_output_must_be_empty_or_absent");
    }
  }
  return true;
}

function withQaRequestMetadata(body, qaRunId) {
  const normalized = String(qaRunId || "")
    .trim()
    .slice(0, 128);
  if (!normalized) {
    throw new Error("missing_qa_run_id");
  }
  return {
    ...(body && typeof body === "object" ? body : {}),
    viventiumQaRun: true,
    viventiumQaRunId: normalized,
  };
}

function partAgentNames(part) {
  const names = new Set();
  for (const key of ["agent_name", "agentName", "cortex_name", "cortexName"]) {
    const value = String(part?.[key] || "")
      .replace(/\s+/g, " ")
      .trim();
    if (value) names.add(value);
  }
  return [...names];
}

function partAgentId(part) {
  return String(part?.agentId || part?.agent_id || "").trim();
}

function textFromPart(part) {
  if (part?.type !== "text") return "";
  if (typeof part.text === "string") return part.text.trim();
  if (typeof part.text?.value === "string") return part.text.value.trim();
  return "";
}

function isNonPlaceholderAnswer(value) {
  const text = String(value || "").trim();
  return (
    text.length > 0 &&
    text !== "{NTA}" &&
    !/^(?:generation in progress|generation interrupted before completion)\.?$/i.test(
      text,
    )
  );
}

function transferTargetFromPart(part) {
  const name = String(part?.tool_call?.name || "").trim();
  if (part?.type !== "tool_call" || !name.startsWith(TRANSFER_TOOL_PREFIX))
    return "";
  return name.slice(TRANSFER_TOOL_PREFIX.length).trim();
}

function structuredOutputParts(output) {
  const candidates = [];
  if (Array.isArray(output)) {
    candidates.push(...output);
  } else if (output && typeof output === "object") {
    candidates.push(output);
  } else if (typeof output === "string") {
    for (const line of output.split(/\r?\n/)) {
      const start = line.indexOf("{");
      if (start === -1) continue;
      try {
        const parsed = JSON.parse(line.slice(start));
        if (parsed && typeof parsed === "object") candidates.push(parsed);
      } catch {
        // Consolidated handoff labels are human-facing; only structured JSON parts are evidence.
      }
    }
  }
  return candidates;
}

function toolOutputShowsSuccess(output, depth = 0) {
  if (depth > 5 || output == null) return false;
  if (Array.isArray(output)) {
    return output.some((item) => toolOutputShowsSuccess(item, depth + 1));
  }
  if (typeof output === "object") {
    if (
      output.success === true ||
      output?.structuredContent?.success === true
    ) {
      return true;
    }
    return Object.values(output).some((item) =>
      toolOutputShowsSuccess(item, depth + 1),
    );
  }
  if (typeof output !== "string") return false;
  const value = output.trim();
  if (!value) return false;
  const starts = [value.indexOf("{"), value.indexOf("[")].filter(
    (index) => index >= 0,
  );
  if (starts.length === 0) return false;
  try {
    return toolOutputShowsSuccess(
      JSON.parse(value.slice(Math.min(...starts))),
      depth + 1,
    );
  } catch {
    return false;
  }
}

function publicConnectedToolTask(value) {
  let candidate = String(value || "").trim();
  if (!candidate) return "connected operation";
  if (candidate.includes("_mcp_")) {
    candidate = candidate.split("_mcp_", 1)[0];
  }
  for (const delimiter of ["__", "/", ":"]) {
    if (candidate.includes(delimiter)) {
      candidate = candidate.slice(
        candidate.lastIndexOf(delimiter) + delimiter.length,
      );
    }
  }
  candidate = candidate
    .replace(/[^A-Za-z0-9]+/g, " ")
    .trim()
    .toLowerCase();
  return candidate.slice(0, 80).trim() || "connected operation";
}

function brokerToolTerminalReceiptCounts(turnMessages, expectedToolName) {
  const task = publicConnectedToolTask(expectedToolName);
  const completed = `connected tool completed: ${task}.`;
  const failed = new Set([
    `connected tool failed: ${task}.`,
    `connected tool cancelled: ${task}.`,
  ]);
  let successfulCallCount = 0;
  let failedCallCount = 0;
  for (const message of turnMessages) {
    for (const part of Array.isArray(message?.content) ? message.content : []) {
      if (part?.type !== "harness_activity") continue;
      const lines = String(part?.harness_activity?.summary || "")
        .split(/\r?\n/)
        .map((line) => line.replace(/\s+/g, " ").trim().toLowerCase())
        .filter(Boolean);
      successfulCallCount += lines.filter((line) => line === completed).length;
      failedCallCount += lines.filter((line) => failed.has(line)).length;
    }
  }
  return { successfulCallCount, failedCallCount };
}

function evaluateExactlyOnceToolExecution({
  messages,
  originatingUserMessageId,
  expectedToolName,
}) {
  const expected = String(expectedToolName || "").trim();
  if (!expected) {
    return {
      required: false,
      pass: true,
      callCount: 0,
      successfulCallCount: 0,
      failedCallCount: 0,
    };
  }

  const origin = String(originatingUserMessageId || "").trim();
  const turnMessageIds = new Set(origin ? [origin] : []);
  let remaining = (Array.isArray(messages) ? messages : []).filter(
    (message) => message?.isCreatedByUser !== true,
  );
  const turnMessages = [];
  let foundDescendant = true;
  while (origin && foundDescendant && remaining.length > 0) {
    foundDescendant = false;
    const stillRemaining = [];
    for (const message of remaining) {
      if (!turnMessageIds.has(String(message?.parentMessageId || ""))) {
        stillRemaining.push(message);
        continue;
      }
      turnMessages.push(message);
      const messageId = String(message?.messageId || message?._id || "").trim();
      if (messageId) turnMessageIds.add(messageId);
      foundDescendant = true;
    }
    remaining = stillRemaining;
  }

  const calls = turnMessages.flatMap((message) =>
    (Array.isArray(message?.content) ? message.content : []).filter(
      (part) =>
        part?.type === "tool_call" &&
        String(part?.tool_call?.name || "").trim() === expected,
    ),
  );
  const successfulCallCount = calls.filter(
    (part) =>
      !partTerminalError(part) &&
      toolOutputShowsSuccess(part?.tool_call?.output),
  ).length;
  const directFailedCallCount = calls.length - successfulCallCount;
  const brokerReceipts = brokerToolTerminalReceiptCounts(
    turnMessages,
    expected,
  );
  const totalSuccessfulCallCount =
    successfulCallCount + brokerReceipts.successfulCallCount;
  const failedCallCount =
    directFailedCallCount + brokerReceipts.failedCallCount;
  const callCount = totalSuccessfulCallCount + failedCallCount;
  return {
    required: true,
    pass:
      callCount === 1 &&
      totalSuccessfulCallCount === 1 &&
      failedCallCount === 0,
    callCount,
    successfulCallCount: totalSuccessfulCallCount,
    failedCallCount,
  };
}

function transferOutputEvidence(part) {
  const outputParts = structuredOutputParts(part?.tool_call?.output);
  const texts = [];
  let authored = false;
  for (const outputPart of outputParts) {
    const type = String(outputPart?.type || "").trim();
    if (type === "text") {
      const text =
        typeof outputPart.text === "string"
          ? outputPart.text.trim()
          : typeof outputPart.text?.value === "string"
            ? outputPart.text.value.trim()
            : "";
      if (isNonPlaceholderAnswer(text)) {
        authored = true;
        texts.push(text);
      }
    } else if (
      (type === "think" && String(outputPart?.think || "").trim()) ||
      (type === "tool_call" &&
        outputPart?.tool_call &&
        typeof outputPart.tool_call === "object")
    ) {
      authored = true;
    }
  }
  return { authored, texts };
}

function partTerminalError(part) {
  const status = String(part?.status || part?.tool_call?.status || "")
    .trim()
    .toLowerCase();
  return TERMINAL_ERROR_STATUSES.has(status);
}

function partShowsAgentActivity(part) {
  if (isNonPlaceholderAnswer(textFromPart(part))) return true;
  if (part?.type === "think" && String(part?.think || "").trim()) return true;
  return (
    part?.type === "tool_call" &&
    part?.tool_call &&
    typeof part.tool_call === "object"
  );
}

function summarizeMessages(messages) {
  return (Array.isArray(messages) ? messages : []).map(
    (message, messageOrder) => {
      const messageUnfinished = message?.unfinished === true;
      const parts = (
        Array.isArray(message?.content) ? message.content : []
      ).map((part, partOrder) => {
        const status = String(part?.status || "")
          .trim()
          .toLowerCase();
        const statusIsTerminal = TERMINAL_STATUSES.has(status);
        const statusIsActive = ACTIVE_STATUSES.has(status);
        const unfinished =
          part?.unfinished === true ||
          (!statusIsTerminal &&
            (statusIsActive || (status === "" && messageUnfinished)));
        return {
          partOrder,
          type: String(part?.type || "unknown"),
          status,
          agentId: partAgentId(part),
          terminal: statusIsTerminal || (!unfinished && !messageUnfinished),
          unfinished,
          agentNames: partAgentNames(part),
        };
      });
      const messageNames = new Set(parts.flatMap((part) => part.agentNames));
      if (message?.isCreatedByUser !== true) {
        for (const value of [message?.agentName, message?.sender]) {
          const name = String(value || "")
            .replace(/\s+/g, " ")
            .trim();
          if (name) messageNames.add(name);
        }
      }
      return {
        messageOrder,
        messageIdHash: hashValue(message?.messageId || message?._id || ""),
        role: message?.isCreatedByUser === true ? "user" : "assistant",
        createdAt:
          message?.createdAt instanceof Date
            ? message.createdAt.toISOString()
            : String(message?.createdAt || ""),
        unfinished: messageUnfinished,
        terminal: !messageUnfinished && parts.every((part) => part.terminal),
        agentNames: [...messageNames],
        parts,
      };
    },
  );
}

function analyzePersistedTurn({
  messages,
  conversation,
  selectedAgentId,
  originatingUserMessageId = "",
}) {
  const selected = String(selectedAgentId || "").trim();
  const graphAgentOrder = selected ? [selected] : [];
  const answerCandidates = [];
  const transferEvents = [];
  let hasStructuredAgentIds = false;
  let eventPosition = 0;
  let activeAgentId = selected;
  const allMessages = Array.isArray(messages) ? messages : [];
  const requestedOriginatingUserMessageId = String(
    originatingUserMessageId || "",
  ).trim();
  const originatingUserMessage = requestedOriginatingUserMessageId
    ? allMessages.find(
        (message) =>
          message?.isCreatedByUser === true &&
          String(message?.messageId || message?._id || "") ===
            requestedOriginatingUserMessageId,
      )
    : [...allMessages]
        .reverse()
        .find((message) => message?.isCreatedByUser === true);
  const resolvedOriginatingUserMessageId = String(
    originatingUserMessage?.messageId || originatingUserMessage?._id || "",
  );
  const turnMessageIds = new Set(
    resolvedOriginatingUserMessageId ? [resolvedOriginatingUserMessageId] : [],
  );
  const directAssistantMessages = [];
  let remainingAssistantMessages = allMessages.filter(
    (message) => message?.isCreatedByUser !== true,
  );
  if (!resolvedOriginatingUserMessageId && !requestedOriginatingUserMessageId) {
    directAssistantMessages.push(...remainingAssistantMessages);
  } else if (resolvedOriginatingUserMessageId) {
    let foundDescendant = true;
    while (foundDescendant && remainingAssistantMessages.length > 0) {
      foundDescendant = false;
      const stillRemaining = [];
      for (const message of remainingAssistantMessages) {
        const parentMessageId = String(message?.parentMessageId || "");
        if (!turnMessageIds.has(parentMessageId)) {
          stillRemaining.push(message);
          continue;
        }
        directAssistantMessages.push(message);
        const messageId = String(message?.messageId || message?._id || "");
        if (messageId) turnMessageIds.add(messageId);
        foundDescendant = true;
      }
      remainingAssistantMessages = stillRemaining;
    }
  }

  const appendGraphAgent = (agentId) => {
    if (agentId && graphAgentOrder.at(-1) !== agentId)
      graphAgentOrder.push(agentId);
  };
  const markLatestTransferResolved = (agentId, position, resolution) => {
    if (!agentId) return;
    const event = [...transferEvents]
      .reverse()
      .find(
        (candidate) =>
          candidate.targetAgentId === agentId && !candidate.resolved,
      );
    if (!event) return;
    event.resolved = true;
    event.resolution = resolution;
    event.resolvedPosition = position;
  };

  for (const message of directAssistantMessages) {
    const messageId = String(message?.messageId || message?._id || "").trim();
    const messageAgentId = String(
      message?.agent_id || message?.agentId || "",
    ).trim();
    if (messageAgentId) {
      hasStructuredAgentIds = true;
      appendGraphAgent(messageAgentId);
      activeAgentId = messageAgentId;
    }
    const content = Array.isArray(message?.content) ? message.content : [];
    for (const part of content) {
      eventPosition += 1;
      const explicitAgentId = partAgentId(part);
      const agentId = explicitAgentId || messageAgentId || activeAgentId;
      if (explicitAgentId) {
        hasStructuredAgentIds = true;
        appendGraphAgent(explicitAgentId);
        activeAgentId = explicitAgentId;
      }

      const transferTargetAgentId = transferTargetFromPart(part);
      if (transferTargetAgentId) {
        markLatestTransferResolved(agentId, eventPosition, "return_transfer");
        const terminalError = partTerminalError(part);
        const outputEvidence = transferOutputEvidence(part);
        const transferEvent = {
          order: transferEvents.length,
          sourceAgentId: agentId,
          targetAgentId: transferTargetAgentId,
          position: eventPosition,
          resolved: terminalError || outputEvidence.authored,
          resolution: terminalError
            ? "terminal_error"
            : outputEvidence.authored
              ? "target_output"
              : "",
          resolvedPosition:
            terminalError || outputEvidence.authored
              ? eventPosition + 0.5
              : null,
          terminalError,
        };
        transferEvents.push(transferEvent);
        appendGraphAgent(transferTargetAgentId);
        activeAgentId = transferTargetAgentId;
        outputEvidence.texts.forEach((text, index) => {
          answerCandidates.push({
            text,
            agentId: transferTargetAgentId,
            messageId,
            position:
              eventPosition + (index + 1) / (outputEvidence.texts.length + 1),
          });
        });
        continue;
      }

      if (partShowsAgentActivity(part)) {
        markLatestTransferResolved(agentId, eventPosition, "target_activity");
      }
      const text = textFromPart(part);
      if (isNonPlaceholderAnswer(text)) {
        answerCandidates.push({
          text,
          agentId,
          messageId,
          position: eventPosition,
        });
      }
    }
    if (content.length === 0 && isNonPlaceholderAnswer(message?.text)) {
      eventPosition += 1;
      const agentId = messageAgentId || activeAgentId;
      if (messageAgentId) {
        appendGraphAgent(messageAgentId);
        activeAgentId = messageAgentId;
      }
      markLatestTransferResolved(agentId, eventPosition, "target_activity");
      answerCandidates.push({
        text: String(message.text).trim(),
        agentId,
        messageId,
        position: eventPosition,
      });
    }
  }

  const finalAnswer = answerCandidates.at(-1) || {
    text: "",
    agentId: "",
    messageId: "",
    position: -1,
  };
  const conversationAgentId = String(conversation?.agent_id || "").trim();
  const conversationAgentMatches =
    Boolean(selected) && conversationAgentId === selected;
  const finalAuthorAgentId =
    finalAnswer.agentId || (!hasStructuredAgentIds ? conversationAgentId : "");
  const incompleteTransferCount = transferEvents.filter(
    (event) => !event.resolved,
  ).length;
  const allTransfersResolved = incompleteTransferCount === 0;
  const lastTransferPosition = transferEvents.at(-1)?.position ?? -1;
  const finalMainAfterLastTransfer =
    transferEvents.length === 0 ||
    (finalAuthorAgentId === selected &&
      finalAnswer.position > lastTransferPosition);
  const hasHandoff =
    transferEvents.length > 0 ||
    graphAgentOrder.some((agentId) => agentId !== selected);
  return {
    graphAgentOrder,
    transferEvents,
    transferCount: transferEvents.length,
    incompleteTransferCount,
    allTransfersResolved,
    finalMainAfterLastTransfer,
    directAssistantMessageCount: directAssistantMessages.length,
    hasStructuredAgentIds,
    hasHandoff,
    finalText: finalAnswer.text,
    finalTextHash: hashValue(finalAnswer.text),
    finalTextLength: finalAnswer.text.length,
    finalAuthorAgentId,
    finalAuthorAgentIdHash: hashValue(finalAuthorAgentId),
    finalMessageId: finalAnswer.messageId,
    originatingUserMessageMatched:
      !requestedOriginatingUserMessageId || Boolean(originatingUserMessage),
    conversationAgentId,
    conversationAgentMatches,
    hasNonPlaceholderAnswer: isNonPlaceholderAnswer(finalAnswer.text),
    mainLast:
      conversationAgentMatches &&
      isNonPlaceholderAnswer(finalAnswer.text) &&
      finalAuthorAgentId === selected &&
      allTransfersResolved &&
      finalMainAfterLastTransfer,
  };
}

function evaluateAcceptance(state) {
  const checks = [
    [state.requestInjectionCount === 1, "agent_chat_post_count_not_one"],
    [state.agentApiAccessPass === true, "selected_agent_not_api_accessible"],
    [
      state.selectedAgentVisibleBefore === true,
      "selected_agent_not_visible_before_submit",
    ],
    [
      state.expectedConversationPathVisible === true,
      "expected_conversation_path_not_visible",
    ],
    [state.expandedAnswerVisible === true, "expanded_answer_not_visible"],
    [state.refreshAnswerVisible === true, "refresh_answer_not_visible"],
    [state.detailExpansionPass === true, "visible_detail_not_expanded"],
    [state.detailRefreshPass === true, "expanded_detail_not_durable"],
    [
      state.visibleProgressSettlementPass === true,
      "visible_progress_not_settled",
    ],
    [state.databaseTerminal === true, "database_turn_not_terminal"],
    [state.conversationAgentMatches === true, "conversation_agent_mismatch"],
    [state.allTransfersResolved === true, "transfer_target_unresolved"],
    [
      state.finalMainAfterLastTransfer === true,
      "main_answer_not_after_last_transfer",
    ],
    [state.mainLast === true, "selected_agent_not_final_author"],
    [
      state.expectedToolExecutionRequired !== true ||
        state.expectedToolExecutionPass === true,
      "expected_tool_execution_not_exactly_once",
    ],
    [
      state.expectedScheduleLifecycleRequired !== true ||
        state.expectedScheduleLifecyclePass === true,
      "expected_schedule_lifecycle_not_clean",
    ],
    [state.conversationPreserved === true, "conversation_not_proven_preserved"],
    [state.screenshotCount === 3, "required_screenshot_count_not_three"],
    [state.sessionDeleteCount === 1, "inserted_auth_session_not_deleted"],
    [!state.error, "run_error_present"],
  ];
  const failures = checks
    .filter(([passed]) => !passed)
    .map(([, failure]) => failure);
  return { pass: failures.length === 0, failures };
}

function evaluateReopenAcceptance(state) {
  const databaseLineageFailure =
    state.databaseLineageStable === false
      ? "database_lineage_changed_during_reopen"
      : "database_lineage_not_revalidated_after_reopen";
  const checks = [
    [state.agentChatPostCount === 0, "reopen_agent_chat_post_detected"],
    [state.agentApiAccessPass === true, "selected_agent_not_api_accessible"],
    [
      state.expectedConversationPathVisible === true,
      "expected_conversation_path_not_visible",
    ],
    [state.expandedAnswerVisible === true, "expanded_answer_not_visible"],
    [state.refreshAnswerVisible === true, "refresh_answer_not_visible"],
    [state.detailExpansionPass === true, "visible_detail_not_expanded"],
    [state.detailRefreshPass === true, "expanded_detail_not_durable"],
    [
      state.visibleProgressSettlementPass === true,
      "visible_progress_not_settled",
    ],
    [state.databaseTerminal === true, "database_turn_not_terminal"],
    [state.conversationAgentMatches === true, "conversation_agent_mismatch"],
    [
      state.originatingUserMessageMatched === true,
      "originating_user_message_not_matched",
    ],
    [state.allTransfersResolved === true, "transfer_target_unresolved"],
    [
      state.finalMainAfterLastTransfer === true,
      "main_answer_not_after_last_transfer",
    ],
    [state.mainLast === true, "selected_agent_not_final_author"],
    [
      state.databaseLineageStable === true,
      databaseLineageFailure,
    ],
    [state.conversationPreserved === true, "conversation_not_proven_preserved"],
    [state.screenshotCount === 2, "required_screenshot_count_not_two"],
    [state.sessionDeleteCount === 1, "inserted_auth_session_not_deleted"],
    [!state.error, "run_error_present"],
  ];
  const failures = checks
    .filter(([passed]) => !passed)
    .map(([, failure]) => failure);
  return { pass: failures.length === 0, failures };
}

function deriveConversationPreserved({
  agentChatPostCount,
  databaseLineageStable,
}) {
  return agentChatPostCount === 0 && databaseLineageStable === true;
}

function deriveSubmitConversationPreserved({
  requestInjectionCount,
  beforeRefreshState,
  afterRefreshState,
  postCleanupState,
}) {
  const states = [beforeRefreshState, afterRefreshState, postCleanupState];
  if (
    requestInjectionCount !== 1 ||
    states.some(
      (state) =>
        state?.identityVerified !== true ||
        state?.turnTerminal !== true ||
        state?.turnAnalysis?.conversationAgentMatches !== true ||
        state?.turnAnalysis?.originatingUserMessageMatched !== true,
    )
  ) {
    return false;
  }
  const fingerprints = states.map((state) => reopenLineageFingerprint(state));
  return fingerprints.every((fingerprint) => fingerprint === fingerprints[0]);
}

function isTurnTerminal(messageSummary) {
  const assistantMessages = messageSummary.filter(
    (message) => message.role === "assistant",
  );
  return (
    assistantMessages.length > 0 &&
    assistantMessages.every((message) => message.terminal)
  );
}

function validateReopenPersistedConversation({
  conversation,
  messages,
  userId,
  selectedAgentId,
  expectedConversationId = "",
  originatingUserMessageId: requestedOriginatingUserMessageId = "",
}) {
  if (!conversation) throw new Error("reopen_conversation_not_found");
  if (String(conversation.user || "") !== String(userId || "")) {
    throw new Error("reopen_conversation_not_owned_by_selected_qa_user");
  }
  if (
    expectedConversationId &&
    String(conversation.conversationId || "") !== String(expectedConversationId)
  ) {
    throw new Error("reopen_conversation_identifier_mismatch");
  }
  if (String(conversation.agent_id || "") !== String(selectedAgentId || "")) {
    throw new Error("reopen_conversation_agent_mismatch");
  }
  const selectedMessages = Array.isArray(messages) ? messages : [];
  if (
    selectedMessages.some(
      (message) =>
        message?.user != null && String(message.user) !== String(userId || ""),
    )
  ) {
    throw new Error("reopen_conversation_contains_foreign_message");
  }
  const requestedOrigin = String(requestedOriginatingUserMessageId || "");
  const originatingUserMessage = requestedOrigin
    ? selectedMessages.find(
        (message) =>
          message?.isCreatedByUser === true &&
          String(message.messageId || message._id || "") === requestedOrigin,
      )
    : [...selectedMessages]
        .reverse()
        .find((message) => message?.isCreatedByUser === true);
  if (!originatingUserMessage) {
    throw new Error("reopen_conversation_missing_user_turn");
  }
  const originatingUserMessageId = String(
    originatingUserMessage.messageId || originatingUserMessage._id || "",
  );
  if (!originatingUserMessageId) {
    throw new Error("reopen_conversation_user_turn_missing_identifier");
  }
  const messageSummary = summarizeMessages(selectedMessages);
  const turnTerminal = isTurnTerminal(messageSummary);
  if (!turnTerminal) {
    throw new Error("reopen_conversation_turn_not_terminal");
  }
  const turnAnalysis = analyzePersistedTurn({
    messages: selectedMessages,
    conversation,
    selectedAgentId,
    originatingUserMessageId,
  });
  if (!turnAnalysis.originatingUserMessageMatched) {
    throw new Error("reopen_conversation_causal_lineage_unresolved");
  }
  return {
    identityVerified: true,
    conversation,
    messages: selectedMessages,
    messageSummary,
    turnTerminal,
    turnAnalysis,
    originatingUserMessageId,
  };
}

function buildPublicSummary({
  args,
  conversationId = "",
  visibleAgentNames = [],
  messageSummary = [],
  turnTerminal = false,
  screenshotCount = 0,
  sessionDeleteCount = 0,
  requestInjectionCount = 0,
  agentChatPostCount = requestInjectionCount,
  conversationPreserved = false,
  runtimeIdentity = "",
  correlationSource = "",
  turnAnalysis = {},
  ui = {},
  timing = {},
  expectedToolExecution = {},
  expectedScheduleLifecycle = {},
  acceptance = { pass: false, failures: [] },
  error = "",
}) {
  const parts = messageSummary.flatMap((message) => message.parts || []);
  return {
    schemaVersion: 1,
    runMode: args.runMode === "reopen" ? "reopen" : "submit",
    caseId: args.caseId,
    qaRunId: args.qaRunId,
    qaEmailHash: hashValue(args.qaEmail),
    agentIdHash: hashValue(args.agentId),
    promptHash: hashValue(args.prompt),
    outputDirHash: hashValue(args.outputDir),
    runtimeIdentityHash: hashValue(runtimeIdentity),
    conversationIdHash: hashValue(conversationId),
    correlationSource,
    visibleAgentCount: visibleAgentNames.length,
    visibleAgentNameHashes: visibleAgentNames.map((name) => hashValue(name)),
    messageCount: messageSummary.length,
    unfinishedMessageCount: messageSummary.filter(
      (message) => message.unfinished,
    ).length,
    partTypeOrder: parts.map((part) => part.type),
    unfinishedPartCount: parts.filter((part) => part.unfinished).length,
    graphAgentOrderHashes: (turnAnalysis.graphAgentOrder || []).map((agentId) =>
      hashValue(agentId),
    ),
    finalTextHash: turnAnalysis.finalTextHash || hashValue(""),
    finalTextLength: turnAnalysis.finalTextLength || 0,
    finalAuthorAgentIdHash:
      turnAnalysis.finalAuthorAgentIdHash || hashValue(""),
    hasHandoff: turnAnalysis.hasHandoff === true,
    transferCount: turnAnalysis.transferCount || 0,
    incompleteTransferCount: turnAnalysis.incompleteTransferCount || 0,
    transferTargetOrderHashes: (turnAnalysis.transferEvents || []).map(
      (event) => hashValue(event.targetAgentId),
    ),
    allTransfersResolved: turnAnalysis.allTransfersResolved === true,
    finalMainAfterLastTransfer:
      turnAnalysis.finalMainAfterLastTransfer === true,
    conversationAgentMatches: turnAnalysis.conversationAgentMatches === true,
    originatingUserMessageMatched:
      turnAnalysis.originatingUserMessageMatched === true,
    mainLast: turnAnalysis.mainLast === true,
    agentApiAccessPass: ui.agentApiAccessPass === true,
    selectedAgentVisibleBefore: ui.selectedAgentVisibleBefore === true,
    expectedConversationPathVisible:
      ui.expectedConversationPathVisible === true,
    expandedAnswerVisible: ui.expandedAnswerVisible === true,
    refreshAnswerVisible: ui.refreshAnswerVisible === true,
    detailExpansionPass: ui.detailExpansionPass === true,
    detailRefreshPass: ui.detailRefreshPass === true,
    visibleProgressSettlementPass: ui.visibleProgressSettlementPass === true,
    firstVisibleMainPaintObserved:
      timing.publicMetrics?.firstVisibleMainPaintObserved === true,
    firstVisibleMainPaintCorrelated:
      timing.publicMetrics?.firstVisibleMainPaintCorrelated === true,
    firstVisibleMainPaintMs: Number.isFinite(
      timing.publicMetrics?.firstVisibleMainPaintMs,
    )
      ? timing.publicMetrics.firstVisibleMainPaintMs
      : null,
    firstVisibleMainPaintCorrelationCount:
      timing.publicMetrics?.firstVisibleMainPaintCorrelationCount === 1 ? 1 : 0,
    expectedToolExecutionRequired: expectedToolExecution.required === true,
    expectedToolExecutionPass:
      expectedToolExecution.required !== true ||
      expectedToolExecution.pass === true,
    expectedToolCallCount: Number(expectedToolExecution.callCount || 0),
    expectedToolSuccessfulCallCount: Number(
      expectedToolExecution.successfulCallCount || 0,
    ),
    expectedToolFailedCallCount: Number(
      expectedToolExecution.failedCallCount || 0,
    ),
    expectedScheduleLifecycleRequired:
      expectedScheduleLifecycle.required === true,
    expectedScheduleLifecyclePass:
      expectedScheduleLifecycle.required !== true ||
      expectedScheduleLifecycle.pass === true,
    expectedSchedulePreflightRowCount: Number(
      expectedScheduleLifecycle.preflightMatchingRowCount ?? 0,
    ),
    expectedSchedulePostRunRowCount: Number(
      expectedScheduleLifecycle.postRunMatchingRowCount ?? 0,
    ),
    expectedScheduleCleanupAttemptCount: Number(
      expectedScheduleLifecycle.cleanupAttemptCount ?? 0,
    ),
    expectedScheduleCleanupSuccessCount: Number(
      expectedScheduleLifecycle.cleanupSuccessCount ?? 0,
    ),
    expectedSchedulePostCleanupRowCount: Number(
      expectedScheduleLifecycle.postCleanupMatchingRowCount ?? 0,
    ),
    expectedScheduleProtectedBaselineStable:
      expectedScheduleLifecycle.required !== true ||
      expectedScheduleLifecycle.protectedBaselineStable === true,
    expectedScheduleHealthCheckCount: Number(
      expectedScheduleLifecycle.schedulingHealthCheckCount || 0,
    ),
    expectedScheduleHealthSuccessCount: Number(
      expectedScheduleLifecycle.schedulingHealthSuccessCount || 0,
    ),
    expectedSchedulePreflightHealthVerified:
      expectedScheduleLifecycle.required !== true ||
      expectedScheduleLifecycle.schedulingPreflightHealthVerified === true,
    expectedScheduleCleanupHealthVerified:
      expectedScheduleLifecycle.required !== true ||
      expectedScheduleLifecycle.schedulingCleanupHealthVerified === true,
    expectedScheduleDbPathSha256:
      expectedScheduleLifecycle.required === true
        ? String(expectedScheduleLifecycle.schedulingDbPathSha256 || "")
        : "",
    turnTerminal: Boolean(turnTerminal),
    screenshotCount,
    requestInjectionCount,
    agentChatPostCount,
    conversationPreserved: conversationPreserved === true,
    authSessionDeleted: sessionDeleteCount === 1,
    pass: acceptance.pass === true,
    failureCodes: acceptance.failures || [],
    ...(error ? { error: safeError(error) } : {}),
  };
}

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const result = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const separator = line.indexOf("=");
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    result[key] = value;
  }
  return result;
}

function urlPort(value) {
  const parsed = new URL(value);
  if (parsed.port) return Number.parseInt(parsed.port, 10);
  return parsed.protocol === "https:" ? 443 : 80;
}

function isAgentChatSubmissionPath(pathname) {
  return (
    pathname === "/api/agents/chat" || pathname === "/api/agents/chat/agents"
  );
}

function createAgentChatPostObserver(page) {
  let agentChatPostCount = 0;
  const listener = (request) => {
    try {
      if (
        request.method() === "POST" &&
        isAgentChatSubmissionPath(new URL(request.url()).pathname)
      ) {
        agentChatPostCount += 1;
      }
    } catch {
      // A malformed browser request cannot be counted as a valid agent chat POST.
    }
  };
  page.on("request", listener);
  return {
    count: () => agentChatPostCount,
    stop: () => page.off("request", listener),
  };
}

async function installReopenChatPostGuard(page) {
  await page.route("**/api/agents/chat**", async (route) => {
    const request = route.request();
    if (
      request.method() === "POST" &&
      isAgentChatSubmissionPath(new URL(request.url()).pathname)
    ) {
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
}

function selectedRuntimeLocalMongo(runtimeEnv) {
  const rawPort = String(runtimeEnv.VIVENTIUM_LOCAL_MONGO_PORT || "").trim();
  const database = String(runtimeEnv.VIVENTIUM_LOCAL_MONGO_DB || "").trim();
  if (!/^\d{1,5}$/.test(rawPort)) {
    throw new Error("selected_runtime_missing_mongo_uri");
  }
  const port = Number.parseInt(rawPort, 10);
  if (port < 1 || port > 65_535) {
    throw new Error("selected_runtime_invalid_local_mongo_port");
  }
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(database)) {
    throw new Error("selected_runtime_invalid_local_mongo_database");
  }
  return {
    uri: `mongodb://127.0.0.1:${port}/${database}`,
    port,
    database,
  };
}

function parseMongoBinding(value) {
  try {
    const parsed = new URL(String(value || "").trim());
    if (parsed.protocol !== "mongodb:") return null;
    const hostname = String(parsed.hostname || "").toLowerCase();
    const port = Number.parseInt(parsed.port || "27017", 10);
    const database = decodeURIComponent(parsed.pathname.replace(/^\//, ""));
    if (!hostname || !Number.isFinite(port) || !database) return null;
    return {
      hostname: isLocalHostname(hostname) ? "loopback" : hostname,
      port,
      database,
    };
  } catch {
    return null;
  }
}

function sameMongoBinding(left, right) {
  const leftBinding = parseMongoBinding(left);
  const rightBinding = parseMongoBinding(right);
  return (
    Boolean(leftBinding) &&
    Boolean(rightBinding) &&
    leftBinding.hostname === rightBinding.hostname &&
    leftBinding.port === rightBinding.port &&
    leftBinding.database === rightBinding.database
  );
}

function serviceMongoMatchesSelectedIsolatedRuntime(
  serviceMongoUri,
  selectedLocalMongo,
) {
  const binding = parseMongoBinding(serviceMongoUri);
  return (
    Boolean(binding) &&
    binding.hostname === "loopback" &&
    binding.port === selectedLocalMongo.port &&
    binding.database === selectedLocalMongo.database
  );
}

function configuredSharedJwtSecret(value) {
  const secret = String(value || "").trim();
  return secret && !secret.startsWith("CHANGE_ME_GENERATE_") ? secret : "";
}

function selectedSchedulingRuntimeEnv(overlays) {
  const declarations = overlays.map((overlay) => ({
    url: String(overlay.SCHEDULING_MCP_URL || "").trim(),
    port: String(overlay.VIVENTIUM_SCHEDULING_MCP_PORT || "").trim(),
  }));
  if (
    declarations.some(
      (declaration) => Boolean(declaration.url) !== Boolean(declaration.port),
    )
  ) {
    throw new Error("selected_runtime_scheduling_mcp_binding_missing");
  }
  const completeDeclarations = declarations.filter(
    (declaration) => declaration.url && declaration.port,
  );
  const distinctDeclarations = [
    ...new Map(
      completeDeclarations.map((declaration) => [
        `${declaration.url}\0${declaration.port}`,
        declaration,
      ]),
    ).values(),
  ];
  if (distinctDeclarations.length > 1) {
    throw new Error("selected_runtime_scheduling_mcp_binding_conflict");
  }
  if (distinctDeclarations.length === 0) {
    throw new Error("selected_runtime_scheduling_mcp_binding_missing");
  }
  const selected = {
    SCHEDULING_MCP_URL: distinctDeclarations[0].url,
    VIVENTIUM_SCHEDULING_MCP_PORT: distinctDeclarations[0].port,
  };
  for (const key of ["VIVENTIUM_STATE_ROOT", "SCHEDULING_DB_PATH"]) {
    const values = [
      ...new Set(
        overlays
          .map((overlay) => String(overlay[key] || "").trim())
          .filter(Boolean),
      ),
    ];
    if (values.length > 1) {
      throw new Error("selected_runtime_scheduling_mcp_binding_conflict");
    }
    if (values.length === 1) selected[key] = values[0];
  }
  return selected;
}

function resolveSelectedSchedulingRuntimeBinding({
  env,
  runtimeRoot,
  repoRoot = REPO_ROOT,
}) {
  const selectedRuntimeRoot = canonicalTarget(runtimeRoot);
  const selectedEnvironmentRoot = fs.realpathSync(
    path.dirname(selectedRuntimeRoot),
  );
  const configuredStateRoot = String(env.VIVENTIUM_STATE_ROOT || "").trim();
  const configuredDbPath = String(env.SCHEDULING_DB_PATH || "").trim();
  const stateRoot = canonicalTarget(
    path.join(selectedEnvironmentRoot, "state", "runtime", "isolated"),
  );
  if (!isWithin(selectedEnvironmentRoot, stateRoot)) {
    throw new Error("selected_runtime_scheduling_state_root_escape");
  }
  const dbPath = canonicalTarget(
    path.join(stateRoot, "scheduling", "schedules.db"),
  );
  if (!isWithin(stateRoot, dbPath)) {
    throw new Error("selected_runtime_scheduling_db_path_escape");
  }
  if (
    (configuredStateRoot &&
      (!path.isAbsolute(configuredStateRoot) ||
        canonicalTarget(configuredStateRoot) !== stateRoot)) ||
    (configuredDbPath &&
      (!path.isAbsolute(configuredDbPath) ||
        canonicalTarget(configuredDbPath) !== dbPath)) ||
    isWithin(fs.realpathSync(repoRoot), dbPath)
  ) {
    throw new Error("selected_runtime_scheduling_db_binding_mismatch");
  }
  if (!fs.existsSync(dbPath) || !fs.statSync(dbPath).isFile()) {
    throw new Error("selected_runtime_scheduling_db_missing");
  }

  let parsedMcpUrl;
  try {
    parsedMcpUrl = new URL(String(env.SCHEDULING_MCP_URL || "").trim());
  } catch {
    throw new Error("selected_runtime_scheduling_mcp_url_invalid");
  }
  const port = Number.parseInt(
    String(env.VIVENTIUM_SCHEDULING_MCP_PORT || ""),
    10,
  );
  if (
    parsedMcpUrl.protocol !== "http:" ||
    !isLocalHostname(parsedMcpUrl.hostname) ||
    parsedMcpUrl.pathname !== "/mcp" ||
    parsedMcpUrl.username ||
    parsedMcpUrl.password ||
    parsedMcpUrl.search ||
    parsedMcpUrl.hash ||
    !Number.isInteger(port) ||
    port < 1 ||
    port > 65_535 ||
    urlPort(parsedMcpUrl.toString()) !== port
  ) {
    throw new Error("selected_runtime_scheduling_mcp_binding_mismatch");
  }
  return {
    dbPath,
    mcpUrl: parsedMcpUrl.toString(),
    stateRoot,
    port,
  };
}

async function verifySchedulingMcpHealth(
  { mcpUrl, dbPath },
  { fetchImpl = fetch, timeoutMs = 3_000 } = {},
) {
  let mcp;
  try {
    mcp = new URL(String(mcpUrl || ""));
  } catch {
    throw new Error("selected_scheduling_mcp_health_url_invalid");
  }
  if (
    mcp.protocol !== "http:" ||
    !isLocalHostname(mcp.hostname) ||
    mcp.pathname !== "/mcp" ||
    mcp.username ||
    mcp.password ||
    mcp.search ||
    mcp.hash
  ) {
    throw new Error("selected_scheduling_mcp_health_url_invalid");
  }
  const canonicalDbPath = canonicalTarget(dbPath);
  const expectedDbPathSha256 = crypto
    .createHash("sha256")
    .update(canonicalDbPath)
    .digest("hex");
  const healthUrl = new URL("/health", mcp.origin).toString();
  let response = null;
  let payload = null;
  let failure = "";
  try {
    response = await fetchWithTimeout(fetchImpl, healthUrl, timeoutMs, {
      redirect: "error",
      headers: { accept: "application/json" },
    });
    if (response.ok) payload = await response.json();
  } catch (error) {
    failure = safeError(error);
  }
  const actualDbPathSha256 = /^[a-f0-9]{64}$/.test(
    String(payload?.db_path_sha256 || ""),
  )
    ? String(payload.db_path_sha256)
    : "";
  const reachable = response !== null;
  const httpOk = response?.ok === true;
  const statusOk = payload?.status === "ok";
  const serviceMatch = payload?.service === "scheduling-cortex";
  const dbPathMatch = actualDbPathSha256 === expectedDbPathSha256;
  const pass = reachable && httpOk && statusOk && serviceMatch && dbPathMatch;
  return {
    publicMetrics: {
      checkCount: 1,
      pass,
      reachable,
      httpOk,
      statusOk,
      serviceMatch,
      dbPathMatch,
      dbPathSha256: expectedDbPathSha256,
    },
    privateReceipt: {
      healthUrlSha256: crypto
        .createHash("sha256")
        .update(healthUrl)
        .digest("hex"),
      expectedDbPathSha256,
      actualDbPathSha256,
      httpStatus: Number(response?.status || 0),
      ...(failure ? { failure } : {}),
    },
  };
}

function stableRowFingerprint(rows) {
  const canonical = rows.map((row) =>
    Object.fromEntries(
      Object.keys(row)
        .sort()
        .map((key) => [key, row[key]]),
    ),
  );
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(canonical))
    .digest("hex");
}

function readSchedulingState({ dbPath, userId, nonce, databaseFactory } = {}) {
  const selectedUserId = String(userId || "").trim();
  const selectedNonce = String(nonce || "").trim();
  if (!selectedUserId || !selectedNonce) {
    throw new Error("scheduling_state_identity_and_nonce_required");
  }
  const openDatabase =
    databaseFactory ||
    ((selectedPath) => {
      const { DatabaseSync } = require("node:sqlite");
      return new DatabaseSync(selectedPath, { readOnly: true });
    });
  const database = openDatabase(dbPath);
  try {
    const rows = database
      .prepare("SELECT * FROM scheduled_tasks ORDER BY id")
      .all();
    const matchingRows = rows.filter((row) => {
      if (String(row.user_id || "") !== selectedUserId) return false;
      return [row.prompt, row.metadata_json].some((value) =>
        String(value || "").includes(selectedNonce),
      );
    });
    const matchingIds = new Set(matchingRows.map((row) => String(row.id)));
    const protectedRows = rows.filter(
      (row) => !matchingIds.has(String(row.id)),
    );
    return {
      matchingRowCount: matchingRows.length,
      activeMatchingRowCount: matchingRows.filter(
        (row) => Number(row.active) === 1,
      ).length,
      matchingTaskIds: matchingRows.map((row) => String(row.id)),
      protectedRowCount: protectedRows.length,
      protectedFingerprint: stableRowFingerprint(protectedRows),
    };
  } finally {
    database.close();
  }
}

async function deleteScheduleThroughMcp(
  { mcpUrl, dbPath, userId, agentId, taskId },
  {
    clientFactory,
    transportFactory,
    verifyHealth = verifySchedulingMcpHealth,
  } = {},
) {
  const url = new URL(String(mcpUrl || ""));
  if (
    url.protocol !== "http:" ||
    !isLocalHostname(url.hostname) ||
    url.pathname !== "/mcp"
  ) {
    throw new Error("scheduling_cleanup_mcp_must_be_loopback");
  }
  for (const [label, value] of Object.entries({
    dbPath,
    userId,
    agentId,
    taskId,
  })) {
    if (!String(value || "").trim()) {
      throw new Error(`scheduling_cleanup_${label}_required`);
    }
  }
  const health = await verifyHealth({ mcpUrl: url.toString(), dbPath });
  if (health?.publicMetrics?.pass !== true) {
    return { pass: false, health };
  }

  let createClient = clientFactory;
  let createTransport = transportFactory;
  if (!createClient || !createTransport) {
    const { Client } = require(
      path.join(
        LIBRECHAT_ROOT,
        "node_modules",
        "@modelcontextprotocol",
        "sdk",
        "dist",
        "cjs",
        "client",
        "index.js",
      ),
    );
    const { StreamableHTTPClientTransport } = require(
      path.join(
        LIBRECHAT_ROOT,
        "node_modules",
        "@modelcontextprotocol",
        "sdk",
        "dist",
        "cjs",
        "client",
        "streamableHttp.js",
      ),
    );
    createClient = () =>
      new Client({ name: "viventium-anti-012-qa-cleanup", version: "1.0.0" });
    createTransport = (selectedUrl, options) =>
      new StreamableHTTPClientTransport(selectedUrl, options);
  }

  const transport = createTransport(url, {
    requestInit: {
      headers: {
        "x-viventium-user-id": String(userId),
        "x-viventium-agent-id": String(agentId),
      },
    },
  });
  const client = createClient();
  try {
    await client.connect(transport);
    const result = await client.callTool({
      name: "schedule_delete",
      arguments: { args: { task_id: String(taskId) } },
    });
    return { pass: toolOutputShowsSuccess(result), health };
  } finally {
    await Promise.resolve(client.close()).catch(() => {});
  }
}

async function prepareExpectedScheduleLifecycle(
  { binding, userId, nonce },
  {
    readState = readSchedulingState,
    verifyHealth = verifySchedulingMcpHealth,
  } = {},
) {
  const health = await verifyHealth(binding);
  if (health?.publicMetrics?.pass !== true) {
    const error = new Error("selected_scheduling_mcp_health_mismatch");
    error.schedulingHealth = health;
    throw error;
  }
  const baseline = readState({ dbPath: binding.dbPath, userId, nonce });
  if (baseline.matchingRowCount !== 0) {
    const error = new Error("expected_schedule_nonce_not_clean_before_submit");
    error.schedulingHealth = health;
    error.schedulingBaseline = baseline;
    throw error;
  }
  return { ...baseline, health };
}

async function finalizeExpectedScheduleLifecycle(
  { baseline, binding, userId, agentId, nonce },
  {
    readState = readSchedulingState,
    deleteSchedule = deleteScheduleThroughMcp,
  } = {},
) {
  let postRun = null;
  let postCleanup = null;
  const cleanupReceipts = [];
  let error = "";
  try {
    postRun = readState({ dbPath: binding.dbPath, userId, nonce });
    for (const taskId of postRun.matchingTaskIds || []) {
      try {
        const result = await deleteSchedule({
          mcpUrl: binding.mcpUrl,
          dbPath: binding.dbPath,
          userId,
          agentId,
          taskId,
        });
        cleanupReceipts.push({
          taskId,
          pass:
            result?.pass === true &&
            result?.health?.publicMetrics?.pass === true,
          health: result?.health || null,
        });
      } catch (cleanupError) {
        cleanupReceipts.push({ taskId, pass: false });
        error ||= safeError(cleanupError);
      }
    }
  } catch (inspectionError) {
    error = safeError(inspectionError);
  }
  try {
    postCleanup = readState({ dbPath: binding.dbPath, userId, nonce });
  } catch (inspectionError) {
    error ||= safeError(inspectionError);
  }

  const protectedBaselineStable =
    Boolean(postRun) &&
    Boolean(postCleanup) &&
    postRun.protectedRowCount === baseline.protectedRowCount &&
    postRun.protectedFingerprint === baseline.protectedFingerprint &&
    postCleanup.protectedRowCount === baseline.protectedRowCount &&
    postCleanup.protectedFingerprint === baseline.protectedFingerprint;
  const preflightHealth = baseline.health?.publicMetrics || {};
  const cleanupHealthReceipts = cleanupReceipts
    .map((receipt) => receipt.health?.publicMetrics)
    .filter(Boolean);
  const healthCheckCount =
    Number(preflightHealth.checkCount || 0) +
    cleanupHealthReceipts.reduce(
      (count, receipt) => count + Number(receipt.checkCount || 0),
      0,
    );
  const healthSuccessCount =
    (preflightHealth.pass === true ? 1 : 0) +
    cleanupHealthReceipts.filter((receipt) => receipt.pass === true).length;
  const cleanupHealthVerified =
    cleanupHealthReceipts.length === 1 &&
    cleanupHealthReceipts[0].pass === true;
  const publicMetrics = {
    required: true,
    pass:
      !error &&
      baseline.matchingRowCount === 0 &&
      postRun?.matchingRowCount === 1 &&
      postRun?.activeMatchingRowCount === 1 &&
      cleanupReceipts.length === 1 &&
      cleanupReceipts[0].pass === true &&
      preflightHealth.pass === true &&
      cleanupHealthVerified &&
      postCleanup?.matchingRowCount === 0 &&
      protectedBaselineStable,
    preflightMatchingRowCount: Number(baseline.matchingRowCount ?? -1),
    postRunMatchingRowCount: Number(postRun?.matchingRowCount ?? -1),
    cleanupAttemptCount: cleanupReceipts.length,
    cleanupSuccessCount: cleanupReceipts.filter((receipt) => receipt.pass)
      .length,
    postCleanupMatchingRowCount: Number(postCleanup?.matchingRowCount ?? -1),
    protectedBaselineStable,
    schedulingHealthCheckCount: healthCheckCount,
    schedulingHealthSuccessCount: healthSuccessCount,
    schedulingPreflightHealthVerified: preflightHealth.pass === true,
    schedulingCleanupHealthVerified: cleanupHealthVerified,
    schedulingDbPathSha256: String(preflightHealth.dbPathSha256 || ""),
  };
  return {
    publicMetrics,
    privateReceipt: {
      postRun,
      postCleanup,
      cleanupReceipts,
      ...(error ? { error } : {}),
    },
  };
}

function loadSelectedRuntimeEnv(
  args,
  {
    processEnv = process.env,
    sharedEnvPath = path.join(LIBRECHAT_ROOT, ".env"),
    repoRoot = REPO_ROOT,
  } = {},
) {
  const runtimeRoot = canonicalTarget(args.runtimeRoot);
  const canonicalRepo = fs.realpathSync(repoRoot);
  if (isWithin(canonicalRepo, runtimeRoot)) {
    throw new Error("selected_runtime_root_must_be_outside_repo");
  }
  const runtimeEnvPath = path.join(runtimeRoot, "runtime.env");
  const runtimeLocalEnvPath = path.join(runtimeRoot, "runtime.local.env");
  const serviceEnvPath = path.join(runtimeRoot, "service-env", "librechat.env");
  if (!fs.existsSync(runtimeEnvPath) || !fs.existsSync(serviceEnvPath)) {
    throw new Error("selected_runtime_compiled_env_missing");
  }
  const sharedEnv = parseEnvFile(sharedEnvPath);
  const runtimeEnv = parseEnvFile(runtimeEnvPath);
  const runtimeLocalEnv = parseEnvFile(runtimeLocalEnvPath);
  const serviceEnv = parseEnvFile(serviceEnvPath);
  const runtimeIdentity = String(
    runtimeEnv.VIVENTIUM_DEV_ENV_NAME || "",
  ).trim();
  const runtimeEnabled =
    String(runtimeEnv.VIVENTIUM_DEV_ENV_ENABLED || "").toLowerCase() === "true";
  if (!runtimeEnabled || !runtimeIdentity) {
    throw new Error("selected_runtime_is_not_an_explicit_dev_qa_runtime");
  }
  if (
    String(runtimeEnv.VIVENTIUM_RUNTIME_PROFILE || "").trim() !== "isolated"
  ) {
    throw new Error("selected_runtime_profile_not_isolated");
  }
  const expectedRootName = path.basename(path.dirname(runtimeRoot));
  if (
    path.basename(runtimeRoot) !== "runtime" ||
    expectedRootName !== runtimeIdentity
  ) {
    throw new Error("selected_runtime_identity_mismatch");
  }
  const apiPort = Number.parseInt(runtimeEnv.VIVENTIUM_LC_API_PORT || "", 10);
  const clientPort = Number.parseInt(
    runtimeEnv.VIVENTIUM_LC_FRONTEND_PORT || "",
    10,
  );
  if (!Number.isFinite(apiPort) || urlPort(args.apiBase) !== apiPort) {
    throw new Error("selected_runtime_api_port_mismatch");
  }
  if (!Number.isFinite(clientPort) || urlPort(args.clientBase) !== clientPort) {
    throw new Error("selected_runtime_client_port_mismatch");
  }

  const selectedLocalMongo = selectedRuntimeLocalMongo(runtimeEnv);
  const explicitServiceMongoUri = String(serviceEnv.MONGO_URI || "").trim();
  const sharedMongoUri = String(sharedEnv.MONGO_URI || "").trim();
  if (
    explicitServiceMongoUri &&
    sharedMongoUri &&
    (explicitServiceMongoUri === sharedMongoUri ||
      sameMongoBinding(explicitServiceMongoUri, sharedMongoUri))
  ) {
    throw new Error("selected_runtime_service_mongo_matches_shared");
  }
  if (
    explicitServiceMongoUri &&
    !serviceMongoMatchesSelectedIsolatedRuntime(
      explicitServiceMongoUri,
      selectedLocalMongo,
    )
  ) {
    throw new Error("selected_runtime_service_mongo_outside_isolated_runtime");
  }
  const selectedMongoUri = explicitServiceMongoUri || selectedLocalMongo.uri;
  const mongoSource = explicitServiceMongoUri
    ? "selected_runtime_service_env"
    : "selected_runtime_local_fields";

  const sharedJwtSecret = configuredSharedJwtSecret(sharedEnv.JWT_SECRET);
  const sharedJwtRefreshSecret = configuredSharedJwtSecret(
    sharedEnv.JWT_REFRESH_SECRET,
  );
  if (!sharedJwtSecret || !sharedJwtRefreshSecret) {
    throw new Error("selected_runtime_missing_shared_jwt_secrets");
  }
  for (const overlay of [runtimeEnv, runtimeLocalEnv, serviceEnv]) {
    for (const [key, selectedSecret] of [
      ["JWT_SECRET", sharedJwtSecret],
      ["JWT_REFRESH_SECRET", sharedJwtRefreshSecret],
    ]) {
      const declared = String(overlay[key] || "").trim();
      if (declared && declared !== selectedSecret) {
        throw new Error("selected_runtime_jwt_binding_conflict");
      }
    }
  }

  const env = {
    ...sharedEnv,
    ...processEnv,
    ...runtimeEnv,
    ...runtimeLocalEnv,
    ...serviceEnv,
    MONGO_URI: selectedMongoUri,
    JWT_SECRET: sharedJwtSecret,
    JWT_REFRESH_SECRET: sharedJwtRefreshSecret,
  };
  for (const guard of [
    LOCAL_JWT_ALLOW_ENV,
    OWNER_EMAIL_ENV,
    "CI",
    "NODE_ENV",
  ]) {
    if (Object.prototype.hasOwnProperty.call(processEnv, guard))
      env[guard] = processEnv[guard];
    else delete env[guard];
  }
  if (env.MONGO_URI !== selectedMongoUri) {
    throw new Error("selected_runtime_mongo_binding_lost");
  }
  const scheduling =
    args.expectedToolName === SCHEDULING_CREATE_TOOL
      ? resolveSelectedSchedulingRuntimeBinding({
          env: selectedSchedulingRuntimeEnv([
            runtimeEnv,
            runtimeLocalEnv,
            serviceEnv,
          ]),
          runtimeRoot,
          repoRoot,
        })
      : null;
  return {
    env,
    runtimeRoot,
    runtimeIdentity,
    apiPort,
    clientPort,
    mongoSource,
    mongoPort: selectedLocalMongo.port,
    mongoDatabase: selectedLocalMongo.database,
    scheduling,
  };
}

async function fetchWithTimeout(
  fetchImpl,
  url,
  timeoutMs = 10_000,
  options = {},
) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetchImpl(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function preflightSelectedRuntime({ args, runtime, fetchImpl = fetch }) {
  const health = await fetchWithTimeout(fetchImpl, `${args.apiBase}/health`);
  const config = await fetchWithTimeout(
    fetchImpl,
    `${args.apiBase}/api/config`,
  );
  const client = await fetchWithTimeout(fetchImpl, args.clientBase);
  let configBody = {};
  try {
    configBody = await config.json();
  } catch {
    configBody = {};
  }
  const appTitle = String(configBody?.appTitle || "");
  const pass =
    health.ok &&
    config.ok &&
    client.ok &&
    appTitle === "Viventium" &&
    urlPort(args.apiBase) === runtime.apiPort &&
    urlPort(args.clientBase) === runtime.clientPort;
  const receipt = {
    pass,
    healthStatus: health.status,
    configStatus: config.status,
    clientStatus: client.status,
    appTitle,
    runtimeIdentity: runtime.runtimeIdentity,
    apiPort: runtime.apiPort,
    clientPort: runtime.clientPort,
  };
  if (!pass) throw new Error("selected_runtime_http_identity_preflight_failed");
  return receipt;
}

function safeError(value) {
  return String(value?.message || value || "qa_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/mongodb(?:\+srv)?:\/\/[^\s)]+/gi, "mongodb://<redacted>")
    .replace(
      /(?:\/Users|\/home|\/private\/var|\/var\/folders|\/tmp)\/[^\s)]+/g,
      "<path>",
    )
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer <redacted>")
    .replace(/(token|secret|password|api[_-]?key)=[^\s]+/gi, "$1=<redacted>")
    .replace(/\s+/g, " ")
    .slice(0, 240);
}

function ensurePrivateOutput(outputDir) {
  fs.mkdirSync(outputDir, { recursive: true, mode: 0o700 });
  fs.chmodSync(outputDir, 0o700);
}

function writePrivateJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
  fs.chmodSync(filePath, 0o600);
}

async function createLocalQaAuth({ args, env }) {
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error("missing_local_qa_auth_prerequisites");
  }
  const { MongoClient, ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const jwt = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"),
  );
  const client = new MongoClient(env.MONGO_URI);
  try {
    await client.connect();
    const dbName =
      new URL(env.MONGO_URI).pathname.replace(/^\//, "") ||
      "LibreChatViventium";
    const db = client.db(dbName);
    const user = await db.collection("users").findOne({ email: args.qaEmail });
    if (!user?._id) throw new Error("configured_qa_user_not_found");
    assertHarnessSafety({ args, env, selectedUser: user });

    const agent = await db.collection("agents").findOne(
      { id: args.agentId },
      {
        projection: {
          _id: 0,
          id: 1,
          name: 1,
          provider: 1,
          model: 1,
          updatedAt: 1,
        },
      },
    );
    if (!agent?.id) throw new Error("configured_agent_not_found");

    const userId = String(user._id);
    const sessionId = new ObjectId();
    const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const refreshToken = jwt.sign(
      { id: userId, sessionId: String(sessionId) },
      env.JWT_REFRESH_SECRET,
      { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
    );
    const accessToken = jwt.sign(
      {
        id: userId,
        username: user.username,
        provider: user.provider,
        email: user.email,
      },
      env.JWT_SECRET,
      { expiresIn: "2h" },
    );
    await db.collection("sessions").insertOne({
      _id: sessionId,
      user: user._id,
      expiration,
      refreshTokenHash: crypto
        .createHash("sha256")
        .update(refreshToken)
        .digest("hex"),
    });

    return {
      client,
      db,
      user,
      userId,
      agent,
      sessionId,
      refreshToken,
      accessToken,
    };
  } catch (error) {
    await client.close().catch(() => {});
    throw error;
  }
}

async function deleteInsertedAuthSession(db, sessionId) {
  if (!db || !sessionId) return 0;
  const deleted = await db.collection("sessions").deleteOne({ _id: sessionId });
  return deleted.deletedCount || 0;
}

async function attachAuthCookies({ context, args, auth }) {
  const expires = Math.floor(Date.now() / 1000) + 7200;
  const cookies = [args.apiBase, args.clientBase].flatMap((url) => [
    {
      name: "refreshToken",
      value: auth.refreshToken,
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires,
    },
    {
      name: "token_provider",
      value: "librechat",
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires,
    },
  ]);
  await context.addCookies(cookies);
}

async function installAccessToken(page, fallbackAccessToken) {
  const result = await page.evaluate(async () => {
    const response = await fetch("/api/auth/refresh", { method: "POST" });
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    return {
      ok: response.ok,
      token: typeof payload.token === "string" ? payload.token : "",
    };
  });
  const token = result.ok && result.token ? result.token : fallbackAccessToken;
  if (!token) throw new Error("local_qa_auth_refresh_failed");
  await page.evaluate((value) => {
    window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: value }));
  }, token);
  await page.waitForTimeout(250);
  return token;
}

async function verifyAgentApiAccess(page, expectedAgent, accessToken) {
  return page.evaluate(
    async ({ agent, accessToken: token }) => {
      const response = await fetch(
        `/api/agents/${encodeURIComponent(agent.id)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      let body = {};
      try {
        body = await response.json();
      } catch {
        body = {};
      }
      return {
        status: response.status,
        pass: response.ok && body?.id === agent.id && body?.name === agent.name,
        returnedId: typeof body?.id === "string" ? body.id : "",
        returnedName: typeof body?.name === "string" ? body.name : "",
      };
    },
    {
      agent: { id: expectedAgent.id, name: expectedAgent.name },
      accessToken,
    },
  );
}

async function findCorrelatedQaUserMessage({
  db,
  userId,
  qaRunId,
  requestReceipt,
}) {
  const messages = db.collection("messages");
  const receiptMessage = await messages.findOne(
    {
      user: userId,
      isCreatedByUser: true,
      "metadata.viventium.qaRunId": qaRunId,
    },
    { projection: { messageId: 1, parentMessageId: 1, conversationId: 1 } },
  );
  if (receiptMessage)
    return { message: receiptMessage, source: "persisted_qa_receipt" };

  const messageId = String(requestReceipt?.messageId || "").trim();
  if (!messageId) return null;
  const candidates = await messages
    .find({ user: userId, messageId, isCreatedByUser: true })
    .limit(2)
    .toArray();
  if (candidates.length > 1) {
    throw new Error("exact_submitted_message_correlation_ambiguous");
  }
  const message = candidates[0];
  if (!message) return null;

  const responseConversationId = String(
    requestReceipt?.responseConversationId || "",
  ).trim();
  const requestConversationId = String(
    requestReceipt?.requestConversationId || "",
  ).trim();
  const expectedConversationId =
    responseConversationId ||
    (requestConversationId && requestConversationId !== "new"
      ? requestConversationId
      : "");
  if (
    expectedConversationId &&
    String(message.conversationId || "") !== expectedConversationId
  ) {
    throw new Error("exact_submitted_message_conversation_mismatch");
  }
  const expectedParentMessageId = String(
    requestReceipt?.parentMessageId || "",
  ).trim();
  if (
    expectedParentMessageId &&
    String(message.parentMessageId || "") !== expectedParentMessageId
  ) {
    throw new Error("exact_submitted_message_parent_mismatch");
  }
  return { message, source: "exact_submitted_message" };
}

async function waitForPersistedTurn({ db, userId, args, requestReceipt }) {
  const deadline = Date.now() + args.timeoutMs;
  let conversationId = "";
  let originatingUserMessageId = "";
  let correlationSource = "";
  let messages = [];
  let summary = [];
  let stableSignature = "";
  let stableSince = 0;

  while (Date.now() < deadline) {
    if (!conversationId) {
      const correlated = await findCorrelatedQaUserMessage({
        db,
        userId,
        qaRunId: args.qaRunId,
        requestReceipt,
      });
      conversationId = String(correlated?.message?.conversationId || "");
      originatingUserMessageId = String(correlated?.message?.messageId || "");
      correlationSource = correlated?.source || "";
    }
    if (conversationId) {
      messages = await db
        .collection("messages")
        .find({ user: userId, conversationId })
        .sort({ createdAt: 1, _id: 1 })
        .toArray();
      summary = summarizeMessages(messages);
      if (isTurnTerminal(summary)) {
        const signature = hashValue(JSON.stringify(messages), 32);
        if (signature !== stableSignature) {
          stableSignature = signature;
          stableSince = Date.now();
        }
        if (Date.now() - stableSince >= args.settleMs) {
          return {
            conversationId,
            originatingUserMessageId,
            correlationSource,
            messages,
            summary,
            timedOut: false,
          };
        }
      } else {
        stableSignature = "";
        stableSince = 0;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 750));
  }
  if (!conversationId) throw new Error("qa_run_message_not_persisted");
  return {
    conversationId,
    originatingUserMessageId,
    correlationSource,
    messages,
    summary,
    timedOut: true,
  };
}

async function armFirstVisibleMainPaintObserver(page, prompt, selectedAgentId) {
  return page.evaluate(
    ({ submittedPrompt, selectedAgentId: expectedMainAgentId }) => {
      const key = "__viventiumFirstVisibleMainPaint";
      const prior = window[key];
      prior?.observer?.disconnect?.();
      const normalize = (value) =>
        String(value || "")
          .replace(/\s+/g, " ")
          .trim();
      const promptText = normalize(submittedPrompt);
      const mainAgentId = normalize(expectedMainAgentId);
      const state = {
        interactionStartedAtMs: performance.timeOrigin + performance.now(),
        paintedAtMs: null,
        userMessageId: "",
        assistantMessageId: "",
        assistantPartId: "",
        assistantPartAgentId: "",
        observer: null,
        framePending: false,
      };
      const visibleText = (element) => {
        if (!element || !normalize(element.textContent)) return false;
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          Number(style.opacity || 1) !== 0 &&
          rect.width > 0 &&
          rect.height > 0
        );
      };
      const inspectAfterPaint = () => {
        state.framePending = false;
        if (state.paintedAtMs != null) return;
        const messages = [...document.querySelectorAll(".message-render")];
        const userIndex = messages.findLastIndex((message) => {
          if (!message.querySelector(".user-turn")) return false;
          const contents = [...message.querySelectorAll(".message-content")];
          return contents.some(
            (content) => normalize(content.textContent) === promptText,
          );
        });
        if (userIndex < 0) return;
        let assistant = null;
        let mainTextPart = null;
        for (const candidateMessage of messages.slice(userIndex + 1)) {
          if (!candidateMessage.querySelector(".agent-turn")) continue;
          const candidatePart = [
            ...candidateMessage.querySelectorAll(".message-content"),
          ].find(
            (part) =>
              visibleText(part) &&
              normalize(part.dataset?.viventiumAgentId) === mainAgentId &&
              normalize(part.dataset?.viventiumPartId) !== "",
          );
          if (!candidatePart) continue;
          assistant = candidateMessage;
          mainTextPart = candidatePart;
          break;
        }
        if (!assistant || !mainTextPart) return;
        state.userMessageId = String(messages[userIndex].id || "");
        state.assistantMessageId = String(assistant.id || "");
        state.assistantPartId = normalize(
          mainTextPart.dataset?.viventiumPartId,
        );
        state.assistantPartAgentId = normalize(
          mainTextPart.dataset?.viventiumAgentId,
        );
        state.paintedAtMs = performance.timeOrigin + performance.now();
        state.observer?.disconnect?.();
      };
      const scheduleInspection = () => {
        if (state.paintedAtMs != null || state.framePending) return;
        state.framePending = true;
        requestAnimationFrame(inspectAfterPaint);
      };
      state.observer = new MutationObserver(scheduleInspection);
      state.observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
      });
      window[key] = state;
      scheduleInspection();
      return state.interactionStartedAtMs;
    },
    { submittedPrompt: prompt, selectedAgentId },
  );
}

async function readFirstVisibleMainPaintObserver(page) {
  return page.evaluate(() => {
    const state = window.__viventiumFirstVisibleMainPaint;
    if (!state) return null;
    return {
      interactionStartedAtMs: state.interactionStartedAtMs,
      paintedAtMs: state.paintedAtMs,
      userMessageId: state.userMessageId,
      assistantMessageId: state.assistantMessageId,
      assistantPartId: state.assistantPartId,
      assistantPartAgentId: state.assistantPartAgentId,
    };
  });
}

function correlateFirstVisibleMainPaint({
  receipt,
  messages,
  originatingUserMessageId,
  selectedAgentId,
}) {
  const observed = Number.isFinite(receipt?.paintedAtMs);
  const interactionStartedAtMs = Number(receipt?.interactionStartedAtMs);
  const paintedAtMs = Number(receipt?.paintedAtMs);
  const expectedUserId = String(originatingUserMessageId || "");
  const receiptUserId = String(receipt?.userMessageId || "");
  const receiptAssistantId = String(receipt?.assistantMessageId || "");
  const assistantPartId = String(receipt?.assistantPartId || "").trim();
  const assistantPartAgentId = String(
    receipt?.assistantPartAgentId || "",
  ).trim();
  const expectedMainAgentId = String(selectedAgentId || "").trim();
  const assistant = (Array.isArray(messages) ? messages : []).find(
    (message) =>
      message?.isCreatedByUser !== true &&
      String(message?.messageId || message?._id || "") === receiptAssistantId,
  );
  const content = Array.isArray(assistant?.content) ? assistant.content : [];
  const hasStructuredPartAuthors = content.some(
    (part) => partAgentId(part).length > 0,
  );
  const sourcePartIndexText = assistantPartId.startsWith("content:")
    ? assistantPartId.slice("content:".length)
    : "";
  const sourcePartIndices = sourcePartIndexText
    ? sourcePartIndexText.split(",").map((value) => Number(value))
    : [];
  const hasCanonicalSourceIdentity =
    sourcePartIndices.length > 0 &&
    sourcePartIndices.every(
      (index, position) =>
        Number.isInteger(index) &&
        index >= 0 &&
        sourcePartIndices.indexOf(index) === position,
    ) &&
    assistantPartId === `content:${sourcePartIndices.join(",")}`;
  const exactTextParts = hasCanonicalSourceIdentity
    ? sourcePartIndices.map((index) => {
        const stablePartId = `content:${index}`;
        const stableMatches = content.filter(
          (part) =>
            String(part?.viventium_render_part_id || "").trim() ===
            stablePartId,
        );
        if (stableMatches.length === 1) return stableMatches[0];
        const indexedPart = content[index];
        return String(indexedPart?.viventium_render_part_id || "").trim()
          ? undefined
          : indexedPart;
      })
    : [];
  const exactTextPartsHaveVisibleContent =
    exactTextParts.length > 0 &&
    exactTextParts.some((part) => isNonPlaceholderAnswer(textFromPart(part)));
  const exactTextPartsAreMain =
    exactTextParts.length > 0 &&
    exactTextParts.every((part) => {
      if (part?.type !== "text") return false;
      const structuredAuthorId = partAgentId(part);
      const authorId =
        structuredAuthorId ||
        (!hasStructuredPartAuthors
          ? String(assistant?.agent_id || assistant?.agentId || "").trim()
          : "");
      return authorId === expectedMainAgentId;
    });
  const fallbackTextSelected =
    content.length === 0 &&
    assistantPartId === "message-text" &&
    isNonPlaceholderAnswer(assistant?.text);
  const fallbackTextIsMain =
    fallbackTextSelected &&
    String(assistant?.agent_id || assistant?.agentId || "").trim() ===
      expectedMainAgentId;
  const correlated =
    observed &&
    receiptUserId !== "" &&
    receiptUserId === expectedUserId &&
    receiptAssistantId !== "" &&
    String(assistant?.parentMessageId || "") === expectedUserId &&
    assistantPartAgentId === expectedMainAgentId &&
    ((exactTextPartsHaveVisibleContent && exactTextPartsAreMain) ||
      fallbackTextIsMain) &&
    Number.isFinite(interactionStartedAtMs) &&
    paintedAtMs >= interactionStartedAtMs;
  return {
    privateReceipt: receipt || null,
    publicMetrics: {
      firstVisibleMainPaintObserved: observed,
      firstVisibleMainPaintCorrelated: correlated,
      firstVisibleMainPaintMs: correlated
        ? Math.max(0, Math.round(paintedAtMs - interactionStartedAtMs))
        : null,
      firstVisibleMainPaintCorrelationCount: correlated ? 1 : 0,
    },
  };
}

async function collectVisibleState(
  page,
  candidateAgentNames = [],
  answerTarget = {},
) {
  return page.evaluate(
    ({ candidates, answerTarget: target }) => {
      const clean = (value) =>
        String(value || "")
          .replace(/\s+/g, " ")
          .trim();
      const bodyText = document.body?.innerText || "";
      const cardLabels = Array.from(
        document.querySelectorAll(".progress-text-wrapper button"),
      )
        .filter(
          (element) =>
            element instanceof HTMLElement && element.offsetParent !== null,
        )
        .map((element) => clean(element.textContent))
        .filter(Boolean);
      const handoffLabels = Array.from(document.querySelectorAll("div.my-3"))
        .filter((element) => /transferred to/i.test(element.textContent || ""))
        .map((element) => clean(element.textContent))
        .filter(Boolean);
      const expandedCardLabels = Array.from(
        document.querySelectorAll(
          '.progress-text-wrapper button[aria-expanded="true"]',
        ),
      )
        .filter(
          (element) =>
            element instanceof HTMLElement && element.offsetParent !== null,
        )
        .map((element) => clean(element.textContent))
        .filter(Boolean);
      const handoffDetailTexts = Array.from(
        document.querySelectorAll("div.my-3 pre"),
      )
        .filter(
          (element) =>
            element instanceof HTMLElement && element.offsetParent !== null,
        )
        .map((element) => clean(element.textContent))
        .filter(Boolean);
      const harnessActivityLabels = Array.from(
        document.querySelectorAll(
          'details[data-viventium-harness-activity="true"] > summary',
        ),
      )
        .filter(
          (element) =>
            element instanceof HTMLElement && element.offsetParent !== null,
        )
        .map((element) => clean(element.textContent))
        .filter(Boolean);
      const harnessActivityDetailTexts = Array.from(
        document.querySelectorAll(
          'details[data-viventium-harness-activity="true"][open] ol > li',
        ),
      )
        .filter(
          (element) =>
            element instanceof HTMLElement && element.offsetParent !== null,
        )
        .map((element) => clean(element.textContent))
        .filter(Boolean);
      const visibleAgentNames = candidates.filter((name) =>
        bodyText.includes(name),
      );
      const targetMessageId = clean(target?.messageId);
      const targetAgentId = clean(target?.agentId);
      const assistantMessage = Array.from(
        document.querySelectorAll(".message-render"),
      ).find(
        (message) =>
          clean(message.id) === targetMessageId &&
          message.querySelector(".agent-turn"),
      );
      const answerContainerParts = assistantMessage
        ? Array.from(
            assistantMessage.querySelectorAll(".message-content"),
          ).filter(
            (part) =>
              !targetAgentId ||
              clean(part.dataset?.viventiumAgentId) === targetAgentId,
          )
        : [];
      const answerContainerText = answerContainerParts
        .map((part) => clean(part.textContent))
        .filter(Boolean)
        .join(" ");
      return {
        url: window.location.href,
        bodyText,
        cardLabels,
        handoffLabels,
        expandedCardLabels,
        handoffDetailTexts,
        harnessActivityLabels,
        harnessActivityDetailTexts,
        visibleAgentNames,
        answerContainerMatched:
          targetMessageId.length > 0 && answerContainerParts.length > 0,
        answerContainerText,
      };
    },
    {
      candidates: [...new Set(candidateAgentNames.filter(Boolean))],
      answerTarget: {
        messageId: String(answerTarget?.messageId || ""),
        agentId: String(answerTarget?.agentId || ""),
      },
    },
  );
}

async function waitForVisibleBackgroundSettlement(page, timeoutMs = 15_000) {
  try {
    await page.waitForFunction(
      () =>
        Array.from(
          document.querySelectorAll(".progress-text-wrapper .shimmer"),
        ).every(
          (element) =>
            !(element instanceof HTMLElement) || element.offsetParent === null,
        ),
      undefined,
      { timeout: timeoutMs },
    );
    return true;
  } catch {
    return false;
  }
}

function didVisibleProgressSettle(beforeExpansion, afterRefresh) {
  return beforeExpansion === true && afterRefresh === true;
}

async function expandVisibleDetails(page) {
  const progressButtons = page.locator(
    '.progress-text-wrapper button[aria-expanded="false"]',
  );
  const progressExpandableCount = await progressButtons.count();
  let progressClickedCount = 0;
  let clickFailureCount = 0;
  for (let index = 0; index < progressExpandableCount; index += 1) {
    try {
      await progressButtons.nth(0).click({ timeout: 5_000 });
      progressClickedCount += 1;
    } catch {
      clickFailureCount += 1;
    }
  }
  const handoffRows = page.locator("div.my-3 > .cursor-pointer");
  const handoffExpandableCount = await handoffRows.count();
  let handoffClickedCount = 0;
  for (let index = 0; index < handoffExpandableCount; index += 1) {
    try {
      await handoffRows.nth(index).click({ timeout: 2_000 });
      handoffClickedCount += 1;
    } catch {
      clickFailureCount += 1;
    }
  }
  const harnessActivityDetails = page.locator(
    'details[data-viventium-harness-activity="true"]:not([open])',
  );
  const harnessActivityExpandableCount = await harnessActivityDetails.count();
  let harnessActivityClickedCount = 0;
  for (let index = 0; index < harnessActivityExpandableCount; index += 1) {
    try {
      await harnessActivityDetails.nth(0).locator("summary").click({
        timeout: 2_000,
      });
      harnessActivityClickedCount += 1;
    } catch {
      clickFailureCount += 1;
    }
  }
  await page.waitForTimeout(500);
  const progressExpandedCount = await page
    .locator('.progress-text-wrapper button[aria-expanded="true"]')
    .count();
  const handoffDetailCount = await page.locator("div.my-3 pre").count();
  const harnessActivityExpandedCount = await page
    .locator('details[data-viventium-harness-activity="true"][open]')
    .count();
  const harnessActivityDetailCount = await page
    .locator('details[data-viventium-harness-activity="true"][open] ol > li')
    .count();
  const detailApplicable =
    progressExpandableCount +
      handoffExpandableCount +
      harnessActivityExpandableCount >
    0;
  return {
    detailApplicable,
    progressExpandableCount,
    progressClickedCount,
    progressExpandedCount,
    handoffExpandableCount,
    handoffClickedCount,
    handoffDetailCount,
    harnessActivityExpandableCount,
    harnessActivityClickedCount,
    harnessActivityExpandedCount,
    harnessActivityDetailCount,
    clickFailureCount,
    pass:
      clickFailureCount === 0 &&
      progressClickedCount === progressExpandableCount &&
      progressExpandedCount >= progressExpandableCount &&
      handoffClickedCount === handoffExpandableCount &&
      handoffDetailCount >= handoffExpandableCount &&
      harnessActivityClickedCount === harnessActivityExpandableCount &&
      harnessActivityExpandedCount >= harnessActivityExpandableCount &&
      harnessActivityDetailCount >= harnessActivityExpandableCount,
  };
}

function normalizeVisibleText(value) {
  return String(value || "")
    .replace(/!?\[([^\]]+)\]\((?:\\.|[^()]|\([^()]*\))*\)/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/[`*_#>\\]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function visibleAnswerTokens(value) {
  return (
    normalizeVisibleText(value)
      .normalize("NFKC")
      .toLowerCase()
      .match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu) || []
  );
}

function containsTokenSequence(haystack, needle) {
  if (needle.length === 0 || haystack.length < needle.length) return false;
  for (let start = 0; start <= haystack.length - needle.length; start += 1) {
    if (needle.every((token, index) => haystack[start + index] === token)) {
      return true;
    }
  }
  return false;
}

function bodyContainsAnswer(bodyText, answerText) {
  const answer = visibleAnswerTokens(answerText);
  if (answer.length === 0) return false;
  const body = visibleAnswerTokens(bodyText);
  return containsTokenSequence(body, answer);
}

function detailFingerprint(state) {
  return hashValue(
    JSON.stringify({
      expandedCardLabels: state?.expandedCardLabels || [],
      handoffDetailTexts: state?.handoffDetailTexts || [],
      harnessActivityLabels: state?.harnessActivityLabels || [],
      harnessActivityDetailTexts: state?.harnessActivityDetailTexts || [],
    }),
    24,
  );
}

function buildReopenUiReceipt({
  agentApiAccess,
  backgroundSettledBeforeExpansion,
  backgroundSettledAfterRefresh,
  expandedReceipt,
  expanded,
  refreshExpandedReceipt,
  afterRefresh,
  turnAnalysis,
}) {
  const initialHandoffLabels = expanded?.handoffLabels || [];
  const refreshHandoffLabels = afterRefresh?.handoffLabels || [];
  const initialDetailCount =
    (expanded?.expandedCardLabels || []).length +
    (expanded?.handoffDetailTexts || []).length +
    (expanded?.harnessActivityDetailTexts || []).length;
  const refreshDetailCount =
    (afterRefresh?.expandedCardLabels || []).length +
    (afterRefresh?.handoffDetailTexts || []).length +
    (afterRefresh?.harnessActivityDetailTexts || []).length;
  const detailApplicable = expandedReceipt?.detailApplicable === true;
  const refreshDetailApplicable =
    refreshExpandedReceipt?.detailApplicable === true;
  const hasHandoff =
    turnAnalysis?.hasHandoff === true ||
    initialHandoffLabels.length > 0 ||
    refreshHandoffLabels.length > 0;
  const handoffVisible = !hasHandoff || initialHandoffLabels.length > 0;
  const handoffDurable =
    !hasHandoff ||
    (refreshHandoffLabels.length > 0 &&
      JSON.stringify(initialHandoffLabels) ===
        JSON.stringify(refreshHandoffLabels));
  return {
    agentApiAccessPass: agentApiAccess?.pass === true,
    expectedConversationPathVisible:
      expanded?.expectedConversationPath === true &&
      afterRefresh?.expectedConversationPath === true,
    expandedAnswerVisible: expanded?.answerVisible === true,
    refreshAnswerVisible: afterRefresh?.answerVisible === true,
    detailExpansionPass:
      expandedReceipt?.pass === true &&
      handoffVisible &&
      (hasHandoff
        ? detailApplicable && initialDetailCount > 0
        : !detailApplicable || initialDetailCount > 0),
    detailRefreshPass:
      refreshExpandedReceipt?.pass === true &&
      handoffDurable &&
      (hasHandoff
        ? detailApplicable &&
          refreshDetailApplicable &&
          initialDetailCount > 0 &&
          refreshDetailCount > 0 &&
          expanded?.detailFingerprint === afterRefresh?.detailFingerprint
        : !detailApplicable ||
          (refreshDetailCount > 0 &&
            expanded?.detailFingerprint === afterRefresh?.detailFingerprint)),
    visibleProgressSettlementPass: didVisibleProgressSettle(
      backgroundSettledBeforeExpansion,
      backgroundSettledAfterRefresh,
    ),
  };
}

function reopenLineageFingerprint(state) {
  return hashValue(
    JSON.stringify({
      originatingUserMessageId: String(state?.originatingUserMessageId || ""),
      messageSummary: (state?.messageSummary || []).map((message) => ({
        messageIdHash: message.messageIdHash,
        role: message.role,
        terminal: message.terminal,
        unfinished: message.unfinished,
        parts: (message.parts || []).map((part) => ({
          type: part.type,
          status: part.status,
          agentIdHash: hashValue(part.agentId || ""),
          terminal: part.terminal,
          unfinished: part.unfinished,
        })),
      })),
      finalTextHash: state?.turnAnalysis?.finalTextHash || "",
      finalAuthorAgentIdHash: state?.turnAnalysis?.finalAuthorAgentIdHash || "",
      graphAgentOrderHashes: (state?.turnAnalysis?.graphAgentOrder || []).map(
        (agentId) => hashValue(agentId),
      ),
      allTransfersResolved: state?.turnAnalysis?.allTransfersResolved === true,
      finalMainAfterLastTransfer:
        state?.turnAnalysis?.finalMainAfterLastTransfer === true,
      mainLast: state?.turnAnalysis?.mainLast === true,
    }),
    32,
  );
}

async function revalidateReopenLineage({ beforeState, loadAfterState }) {
  if (!beforeState) {
    return { afterState: null, lineageStable: null };
  }
  const afterState = await loadAfterState();
  return {
    afterState,
    lineageStable:
      reopenLineageFingerprint(beforeState) ===
      reopenLineageFingerprint(afterState),
  };
}

async function captureScreenshot(page, outputDir, name) {
  const screenshotPath = path.join(outputDir, name);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  fs.chmodSync(screenshotPath, 0o600);
}

async function loadReopenConversationState({ db, userId, args }) {
  const conversation = await db.collection("conversations").findOne({
    conversationId: args.reopenConversationId,
  });
  if (!conversation) throw new Error("reopen_conversation_not_found");
  if (String(conversation.user || "") !== String(userId || "")) {
    throw new Error("reopen_conversation_not_owned_by_selected_qa_user");
  }
  if (String(conversation.agent_id || "") !== String(args.agentId || "")) {
    throw new Error("reopen_conversation_agent_mismatch");
  }
  const messages = await db
    .collection("messages")
    .find({
      conversationId: args.reopenConversationId,
    })
    .sort({ createdAt: 1, _id: 1 })
    .toArray();
  return validateReopenPersistedConversation({
    conversation,
    messages,
    userId,
    selectedAgentId: args.agentId,
    expectedConversationId: args.reopenConversationId,
  });
}

async function loadSubmitConversationState({
  db,
  userId,
  args,
  conversationId,
  originatingUserMessageId,
}) {
  const conversation = await db.collection("conversations").findOne({
    conversationId,
  });
  const messages = await db
    .collection("messages")
    .find({ conversationId })
    .sort({ createdAt: 1, _id: 1 })
    .toArray();
  return validateReopenPersistedConversation({
    conversation,
    messages,
    userId,
    selectedAgentId: args.agentId,
    expectedConversationId: conversationId,
    originatingUserMessageId,
  });
}

function scrollTerminalMessageViewportInDocument(
  root = document,
  getStyle = (element) => window.getComputedStyle(element),
) {
  const terminal = root.getElementById("messages-end");
  let viewport = terminal?.parentElement || null;
  while (viewport) {
    const overflowY = String(getStyle(viewport)?.overflowY || "").toLowerCase();
    if (overflowY === "auto" || overflowY === "scroll") break;
    viewport = viewport.parentElement;
  }
  if (!terminal || !viewport) {
    return {
      found: false,
      atBottom: false,
      scrollHeight: 0,
      clientHeight: 0,
    };
  }
  terminal.scrollIntoView?.({ block: "end", inline: "nearest" });
  const scrollHeight = Number(viewport.scrollHeight || 0);
  if (typeof viewport.scrollTo === "function") {
    viewport.scrollTo({ top: scrollHeight, behavior: "auto" });
  } else {
    viewport.scrollTop = scrollHeight;
  }
  const settledScrollHeight = Number(viewport.scrollHeight || 0);
  const settledClientHeight = Number(viewport.clientHeight || 0);
  const atBottom =
    settledScrollHeight <= settledClientHeight ||
    settledScrollHeight -
        settledClientHeight -
        Number(viewport.scrollTop || 0) <=
      8;
  return {
    found: true,
    atBottom,
    scrollHeight: settledScrollHeight,
    clientHeight: settledClientHeight,
  };
}

function correlatedVisibleAnswerInDocument(expected, root = document) {
  const normalize = (value) =>
    String(value || "")
      .replace(/!?\[([^\]]+)\]\((?:\\.|[^()]|\([^()]*\))*\)/g, "$1")
      .replace(/<[^>]+>/g, " ")
      .replace(/[`*_#>\\]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .normalize("NFKC")
      .toLowerCase();
  const tokens = (value) =>
    normalize(value).match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu) || [];
  const containsSequence = (haystack, needle) => {
    if (needle.length === 0 || haystack.length < needle.length) return false;
    for (let start = 0; start <= haystack.length - needle.length; start += 1) {
      if (needle.every((token, index) => haystack[start + index] === token)) return true;
    }
    return false;
  };
  const messageId = String(expected?.messageId || "").trim();
  const agentId = String(expected?.agentId || "").trim();
  const answerTokens = tokens(expected?.answerText);
  if (!messageId || !agentId || answerTokens.length === 0) return false;
  const assistantMessage = Array.from(root.querySelectorAll(".message-render")).find(
    (message) =>
      String(message.id || "").trim() === messageId &&
      message.querySelector(".agent-turn"),
  );
  if (!assistantMessage) return false;
  return Array.from(assistantMessage.querySelectorAll(".message-content"))
    .filter(
      (part) =>
        String(part.dataset?.viventiumAgentId || "").trim() === agentId,
    )
    .some((part) => containsSequence(tokens(part.textContent), answerTokens));
}

async function waitForCorrelatedVisibleAnswer(page, answerTarget, timeoutMs) {
  if (visibleAnswerTokens(answerTarget?.answerText).length === 0) {
    throw new Error("reopen_conversation_has_no_visible_answer");
  }
  if (!String(answerTarget?.messageId || "").trim()) {
    throw new Error("correlated_answer_missing_message_identifier");
  }
  if (!String(answerTarget?.agentId || "").trim()) {
    throw new Error("correlated_answer_missing_agent_identifier");
  }
  const scrollTimeoutMs = Math.min(timeoutMs, 15_000);
  await page.locator("#messages-end").waitFor({
    state: "attached",
    timeout: scrollTimeoutMs,
  });
  const expected = {
    messageId: String(answerTarget.messageId),
    agentId: String(answerTarget.agentId),
    answerText: String(answerTarget.answerText),
  };
  const deadline = Date.now() + scrollTimeoutMs;
  let scrollReceipt = null;
  do {
    scrollReceipt = await page.evaluate(
      scrollTerminalMessageViewportInDocument,
    );
    const correlatedAnswerVisible = await page.evaluate(
      correlatedVisibleAnswerInDocument,
      expected,
    );
    if (
      scrollReceipt?.found === true &&
      scrollReceipt.atBottom === true &&
      correlatedAnswerVisible === true
    ) {
      return scrollReceipt;
    }
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) break;
    await page.waitForTimeout(Math.min(100, remainingMs));
  } while (Date.now() < deadline);
  throw new Error(
    scrollReceipt?.found === true
      ? "terminal_message_viewport_not_settled"
      : "terminal_message_viewport_not_found",
  );
}

async function runReopenHarness(args, runtime) {
  const { env } = runtime;
  const evidence = {
    schemaVersion: 1,
    run: {
      mode: "reopen",
      caseId: args.caseId,
      qaRunId: args.qaRunId,
      startedAt: new Date().toISOString(),
      clientBase: args.clientBase,
      apiBase: args.apiBase,
      qaEmail: args.qaEmail,
      agentId: args.agentId,
      prompt: args.prompt,
      reopenConversationId: args.reopenConversationId,
      runtimeRoot: runtime.runtimeRoot,
      runtimeIdentity: runtime.runtimeIdentity,
      conversationPreserved: false,
      promptSubmitted: false,
      cleanupPolicy:
        args.expectedToolName === SCHEDULING_CREATE_TOOL
          ? "inserted_auth_session_plus_exact_scheduling_mcp_effect"
          : "inserted_auth_session_only",
    },
    runtime: {
      identity: runtime.runtimeIdentity,
      apiPort: runtime.apiPort,
      clientPort: runtime.clientPort,
      mongoSource: runtime.mongoSource,
      mongoPort: runtime.mongoPort,
      mongoDatabase: runtime.mongoDatabase,
      preflight: null,
    },
    browser: {
      agentApiAccess: null,
      expandedReceipt: null,
      expanded: null,
      refreshExpandedReceipt: null,
      afterRefresh: null,
    },
    database: {
      agent: null,
      graphAgents: [],
      beforeRefresh: null,
      afterRefresh: null,
      lineageStable: null,
      lineageValidationError: "",
    },
    agentChatPostCount: 0,
    requestInjectionCount: 0,
    conversationPreserved: false,
    screenshots: [],
    sessionCleanup: { attempted: false, deletedCount: 0 },
    acceptance: null,
    error: "",
  };
  let auth;
  let browser;
  let postObserver;
  let beforeState;
  let afterState;

  try {
    evidence.runtime.preflight = await preflightSelectedRuntime({
      args,
      runtime,
    });
    auth = await createLocalQaAuth({ args, env });
    evidence.database.agent = auth.agent;
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
    browser = await chromium.launch({
      channel: "chrome",
      headless: args.headless,
    });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1100 },
    });
    await attachAuthCookies({ context, args, auth });
    const page = await context.newPage();
    await installReopenChatPostGuard(page);
    postObserver = createAgentChatPostObserver(page);

    await page.goto(args.clientBase, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    let browserAccessToken = await installAccessToken(page, auth.accessToken);
    evidence.browser.agentApiAccess = await verifyAgentApiAccess(
      page,
      auth.agent,
      browserAccessToken,
    );
    if (evidence.browser.agentApiAccess.pass !== true) {
      throw new Error("selected_agent_not_api_accessible");
    }

    beforeState = await loadReopenConversationState({
      db: auth.db,
      userId: auth.userId,
      args,
    });
    evidence.database.beforeRefresh = beforeState;
    const graphAgentIds = [
      args.agentId,
      ...beforeState.turnAnalysis.graphAgentOrder,
    ].filter((value, index, all) => value && all.indexOf(value) === index);
    evidence.database.graphAgents = await auth.db
      .collection("agents")
      .find(
        { id: { $in: graphAgentIds } },
        { projection: { _id: 0, id: 1, name: 1 } },
      )
      .toArray();
    const agentNames = [
      auth.agent.name,
      ...evidence.database.graphAgents.map((agent) => agent.name),
      ...beforeState.messageSummary.flatMap(
        (message) => message.agentNames || [],
      ),
    ].filter((value, index, all) => value && all.indexOf(value) === index);

    const expectedPath = `/c/${args.reopenConversationId}`;
    await page.goto(`${args.clientBase}${expectedPath}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    browserAccessToken = await installAccessToken(page, auth.accessToken);
    if (new URL(page.url()).pathname !== expectedPath) {
      throw new Error("reopen_conversation_path_mismatch");
    }
    await waitForCorrelatedVisibleAnswer(
      page,
      {
        messageId: beforeState.turnAnalysis.finalMessageId,
        agentId: beforeState.turnAnalysis.finalAuthorAgentId,
        answerText: beforeState.turnAnalysis.finalText,
      },
      args.timeoutMs,
    );
    evidence.browser.backgroundSettledBeforeExpansion =
      await waitForVisibleBackgroundSettlement(page);
    evidence.browser.expandedReceipt = await expandVisibleDetails(page);
    evidence.browser.expanded = await collectVisibleState(page, agentNames, {
      messageId: beforeState.turnAnalysis.finalMessageId,
      agentId: beforeState.turnAnalysis.finalAuthorAgentId,
    });
    evidence.browser.expanded.expectedConversationPath =
      new URL(page.url()).pathname === expectedPath;
    evidence.browser.expanded.answerVisible = bodyContainsAnswer(
      evidence.browser.expanded.answerContainerText,
      beforeState.turnAnalysis.finalText,
    );
    evidence.browser.expanded.detailFingerprint = detailFingerprint(
      evidence.browser.expanded,
    );
    await captureScreenshot(page, args.outputDir, "01-reopened-expanded.png");
    evidence.screenshots.push("01-reopened-expanded.png");

    await page.reload({ waitUntil: "domcontentloaded", timeout: 60_000 });
    await installAccessToken(page, browserAccessToken);
    if (new URL(page.url()).pathname !== expectedPath) {
      throw new Error("reopen_conversation_refresh_path_mismatch");
    }
    await waitForCorrelatedVisibleAnswer(
      page,
      {
        messageId: beforeState.turnAnalysis.finalMessageId,
        agentId: beforeState.turnAnalysis.finalAuthorAgentId,
        answerText: beforeState.turnAnalysis.finalText,
      },
      args.timeoutMs,
    );
    evidence.browser.backgroundSettledAfterRefresh =
      await waitForVisibleBackgroundSettlement(page);
    evidence.browser.refreshExpandedReceipt = await expandVisibleDetails(page);
    evidence.browser.afterRefresh = await collectVisibleState(
      page,
      agentNames,
      {
        messageId: beforeState.turnAnalysis.finalMessageId,
        agentId: beforeState.turnAnalysis.finalAuthorAgentId,
      },
    );
    evidence.browser.afterRefresh.expectedConversationPath =
      new URL(page.url()).pathname === expectedPath;
    evidence.browser.afterRefresh.answerVisible = bodyContainsAnswer(
      evidence.browser.afterRefresh.answerContainerText,
      beforeState.turnAnalysis.finalText,
    );
    evidence.browser.afterRefresh.detailFingerprint = detailFingerprint(
      evidence.browser.afterRefresh,
    );
    await captureScreenshot(
      page,
      args.outputDir,
      "02-reopened-after-refresh.png",
    );
    evidence.screenshots.push("02-reopened-after-refresh.png");

    const lineageValidation = await revalidateReopenLineage({
      beforeState,
      loadAfterState: () =>
        loadReopenConversationState({
          db: auth.db,
          userId: auth.userId,
          args,
        }),
    });
    afterState = lineageValidation.afterState;
    evidence.database.afterRefresh = afterState;
    evidence.database.lineageStable = lineageValidation.lineageStable;
    evidence.agentChatPostCount = postObserver.count();
  } catch (error) {
    evidence.error = error?.stack || error?.message || String(error);
  } finally {
    if (postObserver) {
      evidence.agentChatPostCount = postObserver.count();
      postObserver.stop();
    }
    if (browser) await browser.close().catch(() => {});
    if (auth?.db && beforeState && !afterState) {
      try {
        const lineageValidation = await revalidateReopenLineage({
          beforeState,
          loadAfterState: () =>
            loadReopenConversationState({
              db: auth.db,
              userId: auth.userId,
              args,
            }),
        });
        afterState = lineageValidation.afterState;
        evidence.database.afterRefresh = afterState;
        evidence.database.lineageStable = lineageValidation.lineageStable;
      } catch (lineageError) {
        evidence.database.afterRefresh = null;
        evidence.database.lineageStable = null;
        evidence.database.lineageValidationError =
          lineageError?.stack || lineageError?.message || String(lineageError);
      }
    }
    if (auth?.db && auth?.sessionId) {
      evidence.sessionCleanup.attempted = true;
      evidence.sessionCleanup.deletedCount = await deleteInsertedAuthSession(
        auth.db,
        auth.sessionId,
      ).catch(() => 0);
    }
    if (auth?.client) await auth.client.close().catch(() => {});
    evidence.run.finishedAt = new Date().toISOString();
  }

  const activeState = afterState || beforeState || {};
  const turnAnalysis = activeState.turnAnalysis || {};
  evidence.conversationPreserved = deriveConversationPreserved({
    agentChatPostCount: evidence.agentChatPostCount,
    databaseLineageStable: evidence.database.lineageStable,
  });
  evidence.run.conversationPreserved = evidence.conversationPreserved;
  const ui = buildReopenUiReceipt({
    agentApiAccess: evidence.browser.agentApiAccess,
    backgroundSettledBeforeExpansion:
      evidence.browser.backgroundSettledBeforeExpansion,
    backgroundSettledAfterRefresh:
      evidence.browser.backgroundSettledAfterRefresh,
    expandedReceipt: evidence.browser.expandedReceipt,
    expanded: evidence.browser.expanded,
    refreshExpandedReceipt: evidence.browser.refreshExpandedReceipt,
    afterRefresh: evidence.browser.afterRefresh,
    turnAnalysis,
  });
  evidence.acceptance = evaluateReopenAcceptance({
    agentChatPostCount: evidence.agentChatPostCount,
    ...ui,
    databaseTerminal: activeState.turnTerminal === true,
    conversationAgentMatches: turnAnalysis.conversationAgentMatches === true,
    originatingUserMessageMatched:
      turnAnalysis.originatingUserMessageMatched === true,
    allTransfersResolved: turnAnalysis.allTransfersResolved === true,
    finalMainAfterLastTransfer:
      turnAnalysis.finalMainAfterLastTransfer === true,
    mainLast: turnAnalysis.mainLast === true,
    databaseLineageStable: evidence.database.lineageStable,
    conversationPreserved: evidence.conversationPreserved,
    screenshotCount: evidence.screenshots.length,
    sessionDeleteCount: evidence.sessionCleanup.deletedCount,
    error: evidence.error,
  });
  writePrivateJson(
    path.join(args.outputDir, "evidence.private.json"),
    evidence,
  );
  const visibleAgentNames = [
    ...(evidence.browser.expanded?.visibleAgentNames || []),
    ...(evidence.browser.afterRefresh?.visibleAgentNames || []),
  ].filter((value, index, all) => all.indexOf(value) === index);
  const publicSummary = buildPublicSummary({
    args,
    conversationId: args.reopenConversationId,
    visibleAgentNames,
    messageSummary: activeState.messageSummary || [],
    turnTerminal: activeState.turnTerminal === true,
    screenshotCount: evidence.screenshots.length,
    sessionDeleteCount: evidence.sessionCleanup.deletedCount,
    requestInjectionCount: 0,
    agentChatPostCount: evidence.agentChatPostCount,
    conversationPreserved: evidence.conversationPreserved,
    runtimeIdentity: runtime.runtimeIdentity,
    correlationSource: "persisted_reopen_causal_lineage",
    turnAnalysis,
    ui,
    acceptance: evidence.acceptance,
    error: evidence.error ? safeError(evidence.error) : "",
  });
  writePrivateJson(
    path.join(args.outputDir, "summary.public-safe.json"),
    publicSummary,
  );
  return publicSummary;
}

async function runHarness(args) {
  const runtime = loadSelectedRuntimeEnv(args);
  const { env } = runtime;
  assertHarnessSafety({ args, env });
  ensurePrivateOutput(args.outputDir);

  if (args.runMode === "reopen") {
    return runReopenHarness(args, runtime);
  }

  const evidence = {
    schemaVersion: 1,
    run: {
      caseId: args.caseId,
      qaRunId: args.qaRunId,
      startedAt: new Date().toISOString(),
      clientBase: args.clientBase,
      apiBase: args.apiBase,
      qaEmail: args.qaEmail,
      agentId: args.agentId,
      runtimeRoot: runtime.runtimeRoot,
      runtimeIdentity: runtime.runtimeIdentity,
      prompt: args.prompt,
      conversationPreserved: false,
      cleanupPolicy: "inserted_auth_session_only",
    },
    runtime: {
      identity: runtime.runtimeIdentity,
      apiPort: runtime.apiPort,
      clientPort: runtime.clientPort,
      mongoSource: runtime.mongoSource,
      mongoPort: runtime.mongoPort,
      mongoDatabase: runtime.mongoDatabase,
      preflight: null,
    },
    browser: {
      agentApiAccess: null,
      before: null,
      firstVisibleMainPaint: null,
      expanded: null,
      expandedReceipt: null,
      afterRefresh: null,
      refreshExpandedReceipt: null,
    },
    database: {
      agent: null,
      graphAgents: [],
      conversation: null,
      messages: [],
      messageSummary: [],
      turnAnalysis: null,
      expectedToolExecution: null,
      expectedScheduleLifecycle: null,
      originatingUserMessageId: "",
      correlationSource: "",
      beforeRefreshState: null,
      afterRefreshState: null,
      postCleanupState: null,
      preservationError: "",
    },
    request: {
      messageId: "",
      parentMessageId: "",
      requestConversationId: "",
      responseConversationId: "",
    },
    requestInjectionCount: 0,
    conversationPreserved: false,
    screenshots: [],
    turnTerminal: false,
    timedOut: false,
    sessionCleanup: { attempted: false, deletedCount: 0 },
    acceptance: null,
    error: "",
  };
  let auth;
  let browser;
  let conversationId = "";
  let beforeRefreshState;
  let afterRefreshState;
  let postCleanupState;
  let schedulingBaseline = null;

  try {
    evidence.runtime.preflight = await preflightSelectedRuntime({
      args,
      runtime,
    });
    auth = await createLocalQaAuth({ args, env });
    evidence.database.agent = auth.agent;
    if (runtime.scheduling) {
      schedulingBaseline = await prepareExpectedScheduleLifecycle({
        binding: runtime.scheduling,
        userId: auth.userId,
        nonce: args.expectedScheduleNonce,
      });
      evidence.database.expectedScheduleLifecycle = {
        baseline: schedulingBaseline,
        bindingVerified: true,
      };
    }
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
    browser = await chromium.launch({
      channel: "chrome",
      headless: args.headless,
    });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1100 },
    });
    await attachAuthCookies({ context, args, auth });
    const page = await context.newPage();
    page.on("response", async (response) => {
      try {
        const request = response.request();
        if (
          request.method() !== "POST" ||
          !isAgentChatSubmissionPath(new URL(request.url()).pathname)
        ) {
          return;
        }
        const body = request.postDataJSON();
        if (
          !evidence.request.messageId ||
          String(body?.messageId || "") !== evidence.request.messageId
        ) {
          return;
        }
        const responseBody = await response.json();
        const responseConversationId = String(
          responseBody?.conversationId || "",
        ).trim();
        if (responseConversationId) {
          evidence.request.responseConversationId = responseConversationId;
        }
      } catch {
        // The exact client message ID remains the fail-closed correlation seam.
      }
    });
    await page.route("**/api/agents/chat**", async (route) => {
      const request = route.request();
      if (
        request.method() !== "POST" ||
        !isAgentChatSubmissionPath(new URL(request.url()).pathname)
      ) {
        await route.continue();
        return;
      }
      let body;
      try {
        body = request.postDataJSON();
      } catch {
        evidence.requestInjectionError = "agent_chat_request_was_not_json";
        await route.abort("blockedbyclient");
        return;
      }
      const headers = {
        ...request.headers(),
        "content-type": "application/json",
      };
      delete headers["content-length"];
      evidence.requestInjectionCount += 1;
      const messageId = String(body?.messageId || "").trim();
      if (!messageId) {
        evidence.requestInjectionError =
          "agent_chat_request_missing_message_id";
        await route.abort("blockedbyclient");
        return;
      }
      evidence.request.messageId = messageId;
      evidence.request.parentMessageId = String(
        body?.parentMessageId || "",
      ).trim();
      evidence.request.requestConversationId = String(
        body?.conversationId || "",
      ).trim();
      await route.continue({
        headers,
        postData: JSON.stringify(withQaRequestMetadata(body, args.qaRunId)),
      });
    });

    await page.goto(args.clientBase, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    let browserAccessToken = await installAccessToken(page, auth.accessToken);
    const agentUrl = `${args.clientBase}/c/new?agent_id=${encodeURIComponent(args.agentId)}`;
    await page.goto(agentUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    browserAccessToken = await installAccessToken(page, auth.accessToken);
    evidence.browser.agentApiAccess = await verifyAgentApiAccess(
      page,
      auth.agent,
      browserAccessToken,
    );
    const input = page
      .getByLabel("Message input")
      .or(page.getByPlaceholder(/^Message/))
      .last();
    await input.waitFor({ state: "visible", timeout: 60_000 });
    await input.fill(args.prompt);
    evidence.browser.before = await collectVisibleState(page, [
      auth.agent.name,
    ]);
    evidence.browser.before.selectedAgentVisible =
      evidence.browser.before.bodyText.includes(auth.agent.name) &&
      evidence.browser.agentApiAccess.pass === true;
    await captureScreenshot(page, args.outputDir, "01-before-submit.png");
    evidence.screenshots.push("01-before-submit.png");

    await armFirstVisibleMainPaintObserver(page, args.prompt, args.agentId);
    await page.getByTestId("send-button").last().click({ timeout: 30_000 });
    const persisted = await waitForPersistedTurn({
      db: auth.db,
      userId: auth.userId,
      args,
      requestReceipt: evidence.request,
    });
    conversationId = persisted.conversationId;
    evidence.database.originatingUserMessageId =
      persisted.originatingUserMessageId;
    evidence.database.correlationSource = persisted.correlationSource;
    evidence.database.messages = persisted.messages;
    evidence.database.messageSummary = persisted.summary;
    evidence.browser.firstVisibleMainPaint = correlateFirstVisibleMainPaint({
      receipt: await readFirstVisibleMainPaintObserver(page),
      messages: persisted.messages,
      originatingUserMessageId: persisted.originatingUserMessageId,
      selectedAgentId: args.agentId,
    });
    evidence.turnTerminal = isTurnTerminal(persisted.summary);
    evidence.timedOut = persisted.timedOut;
    evidence.database.conversation = await auth.db
      .collection("conversations")
      .findOne({
        conversationId,
      });
    beforeRefreshState = validateReopenPersistedConversation({
      messages: persisted.messages,
      conversation: evidence.database.conversation,
      userId: auth.userId,
      selectedAgentId: args.agentId,
      expectedConversationId: conversationId,
      originatingUserMessageId: persisted.originatingUserMessageId,
    });
    evidence.database.beforeRefreshState = beforeRefreshState;
    evidence.database.messageSummary = beforeRefreshState.messageSummary;
    evidence.database.turnAnalysis = beforeRefreshState.turnAnalysis;
    evidence.turnTerminal = beforeRefreshState.turnTerminal;
    const graphAgentIds = [
      args.agentId,
      ...evidence.database.turnAnalysis.graphAgentOrder,
    ].filter((value, index, all) => value && all.indexOf(value) === index);
    evidence.database.graphAgents = await auth.db
      .collection("agents")
      .find(
        { id: { $in: graphAgentIds } },
        { projection: { _id: 0, id: 1, name: 1 } },
      )
      .toArray();
    const agentNames = [
      auth.agent.name,
      ...evidence.database.graphAgents.map((agent) => agent.name),
      ...persisted.summary.flatMap((message) => message.agentNames || []),
    ].filter((value, index, all) => value && all.indexOf(value) === index);

    const expectedPath = `/c/${conversationId}`;
    if (new URL(page.url()).pathname !== expectedPath) {
      await page
        .waitForFunction(
          (pathname) => window.location.pathname === pathname,
          expectedPath,
          {
            timeout: 30_000,
          },
        )
        .catch(() => {});
    }
    if (new URL(page.url()).pathname !== expectedPath) {
      await page.goto(`${args.clientBase}${expectedPath}`, {
        waitUntil: "domcontentloaded",
        timeout: 60_000,
      });
      await installAccessToken(page, auth.accessToken);
    }
    await waitForCorrelatedVisibleAnswer(
      page,
      {
        messageId: evidence.database.turnAnalysis.finalMessageId,
        agentId: evidence.database.turnAnalysis.finalAuthorAgentId,
        answerText: evidence.database.turnAnalysis.finalText,
      },
      args.timeoutMs,
    );
    evidence.browser.backgroundSettledBeforeExpansion =
      await waitForVisibleBackgroundSettlement(page);
    evidence.browser.expandedReceipt = await expandVisibleDetails(
      page,
      agentNames,
    );
    evidence.browser.expanded = await collectVisibleState(page, agentNames, {
      messageId: evidence.database.turnAnalysis.finalMessageId,
      agentId: evidence.database.turnAnalysis.finalAuthorAgentId,
    });
    evidence.browser.expanded.expectedConversationPath =
      new URL(page.url()).pathname === expectedPath;
    evidence.browser.expanded.answerVisible = bodyContainsAnswer(
      evidence.browser.expanded.answerContainerText,
      evidence.database.turnAnalysis.finalText,
    );
    evidence.browser.expanded.detailFingerprint = detailFingerprint(
      evidence.browser.expanded,
    );
    await captureScreenshot(page, args.outputDir, "02-expanded.png");
    evidence.screenshots.push("02-expanded.png");

    await page.reload({ waitUntil: "domcontentloaded", timeout: 60_000 });
    await installAccessToken(page, auth.accessToken);
    await waitForCorrelatedVisibleAnswer(
      page,
      {
        messageId: evidence.database.turnAnalysis.finalMessageId,
        agentId: evidence.database.turnAnalysis.finalAuthorAgentId,
        answerText: evidence.database.turnAnalysis.finalText,
      },
      args.timeoutMs,
    );
    evidence.browser.backgroundSettledAfterRefresh =
      await waitForVisibleBackgroundSettlement(page);
    evidence.browser.refreshExpandedReceipt = await expandVisibleDetails(
      page,
      agentNames,
    );
    evidence.browser.afterRefresh = await collectVisibleState(
      page,
      agentNames,
      {
        messageId: evidence.database.turnAnalysis.finalMessageId,
        agentId: evidence.database.turnAnalysis.finalAuthorAgentId,
      },
    );
    evidence.browser.afterRefresh.expectedConversationPath =
      new URL(page.url()).pathname === expectedPath;
    evidence.browser.afterRefresh.answerVisible = bodyContainsAnswer(
      evidence.browser.afterRefresh.answerContainerText,
      evidence.database.turnAnalysis.finalText,
    );
    evidence.browser.afterRefresh.detailFingerprint = detailFingerprint(
      evidence.browser.afterRefresh,
    );
    await captureScreenshot(page, args.outputDir, "03-after-refresh.png");
    evidence.screenshots.push("03-after-refresh.png");

    afterRefreshState = await loadSubmitConversationState({
      db: auth.db,
      userId: auth.userId,
      args,
      conversationId,
      originatingUserMessageId: evidence.database.originatingUserMessageId,
    });
    evidence.database.afterRefreshState = afterRefreshState;
    evidence.database.messages = afterRefreshState.messages;
    evidence.database.messageSummary = afterRefreshState.messageSummary;
    evidence.database.conversation = afterRefreshState.conversation;
    evidence.database.turnAnalysis = afterRefreshState.turnAnalysis;
    evidence.turnTerminal = afterRefreshState.turnTerminal;
  } catch (error) {
    if (error?.schedulingHealth) {
      const health = error.schedulingHealth;
      const rejectedBaseline = error.schedulingBaseline || null;
      evidence.database.expectedScheduleLifecycle = {
        publicMetrics: {
          required: true,
          pass: false,
          preflightMatchingRowCount: Number(
            rejectedBaseline?.matchingRowCount ?? -1,
          ),
          postRunMatchingRowCount: -1,
          cleanupAttemptCount: 0,
          cleanupSuccessCount: 0,
          postCleanupMatchingRowCount: -1,
          protectedBaselineStable: false,
          schedulingHealthCheckCount: Number(
            health.publicMetrics?.checkCount || 0,
          ),
          schedulingHealthSuccessCount:
            health.publicMetrics?.pass === true ? 1 : 0,
          schedulingPreflightHealthVerified:
            health.publicMetrics?.pass === true,
          schedulingCleanupHealthVerified: false,
          schedulingDbPathSha256: String(
            health.publicMetrics?.dbPathSha256 || "",
          ),
        },
        privateReceipt: {
          preflightHealth: health.privateReceipt || null,
          rejectedBaseline,
        },
      };
    }
    evidence.error = error?.stack || error?.message || String(error);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (runtime.scheduling && auth?.userId && schedulingBaseline) {
      const lifecycle = await finalizeExpectedScheduleLifecycle({
        baseline: schedulingBaseline,
        binding: runtime.scheduling,
        userId: auth.userId,
        agentId: args.agentId,
        nonce: args.expectedScheduleNonce,
      }).catch((cleanupError) => ({
        publicMetrics: {
          required: true,
          pass: false,
          preflightMatchingRowCount: schedulingBaseline.matchingRowCount,
          postRunMatchingRowCount: -1,
          cleanupAttemptCount: 0,
          cleanupSuccessCount: 0,
          postCleanupMatchingRowCount: -1,
          protectedBaselineStable: false,
          schedulingHealthCheckCount: Number(
            schedulingBaseline.health?.publicMetrics?.checkCount || 0,
          ),
          schedulingHealthSuccessCount:
            schedulingBaseline.health?.publicMetrics?.pass === true ? 1 : 0,
          schedulingPreflightHealthVerified:
            schedulingBaseline.health?.publicMetrics?.pass === true,
          schedulingCleanupHealthVerified: false,
          schedulingDbPathSha256: String(
            schedulingBaseline.health?.publicMetrics?.dbPathSha256 || "",
          ),
        },
        privateReceipt: { error: safeError(cleanupError) },
      }));
      evidence.database.expectedScheduleLifecycle = {
        baseline: schedulingBaseline,
        bindingVerified: true,
        ...lifecycle,
      };
    }
    if (auth?.db && auth?.sessionId) {
      evidence.sessionCleanup.attempted = true;
      evidence.sessionCleanup.deletedCount = await deleteInsertedAuthSession(
        auth.db,
        auth.sessionId,
      ).catch(() => 0);
    }
    if (
      auth?.db &&
      conversationId &&
      evidence.database.originatingUserMessageId
    ) {
      try {
        postCleanupState = await loadSubmitConversationState({
          db: auth.db,
          userId: auth.userId,
          args,
          conversationId,
          originatingUserMessageId: evidence.database.originatingUserMessageId,
        });
        evidence.database.postCleanupState = postCleanupState;
      } catch (preservationError) {
        evidence.database.preservationError = safeError(preservationError);
      }
    }
    if (auth?.client) await auth.client.close().catch(() => {});
    evidence.run.finishedAt = new Date().toISOString();
  }

  evidence.conversationPreserved = deriveSubmitConversationPreserved({
    requestInjectionCount: evidence.requestInjectionCount,
    beforeRefreshState,
    afterRefreshState,
    postCleanupState,
  });
  evidence.run.conversationPreserved = evidence.conversationPreserved;

  const visibleAgentNames = [
    ...(evidence.browser.expanded?.visibleAgentNames || []),
    ...(evidence.browser.afterRefresh?.visibleAgentNames || []),
  ].filter((value, index, all) => all.indexOf(value) === index);
  const turnAnalysis = evidence.database.turnAnalysis || {};
  evidence.database.expectedToolExecution = evaluateExactlyOnceToolExecution({
    messages: evidence.database.messages,
    originatingUserMessageId: evidence.database.originatingUserMessageId,
    expectedToolName: args.expectedToolName,
  });
  const scheduleLifecycleRequired =
    args.expectedToolName === SCHEDULING_CREATE_TOOL;
  const expectedScheduleLifecycle = evidence.database.expectedScheduleLifecycle
    ?.publicMetrics || {
    required: scheduleLifecycleRequired,
    pass: !scheduleLifecycleRequired,
    preflightMatchingRowCount: 0,
    postRunMatchingRowCount: 0,
    cleanupAttemptCount: 0,
    cleanupSuccessCount: 0,
    postCleanupMatchingRowCount: 0,
    protectedBaselineStable: !scheduleLifecycleRequired,
    schedulingHealthCheckCount: 0,
    schedulingHealthSuccessCount: 0,
    schedulingPreflightHealthVerified: !scheduleLifecycleRequired,
    schedulingCleanupHealthVerified: !scheduleLifecycleRequired,
    schedulingDbPathSha256: "",
  };
  const initialHandoffLabels = evidence.browser.expanded?.handoffLabels || [];
  const refreshHandoffLabels =
    evidence.browser.afterRefresh?.handoffLabels || [];
  const initialDetailCount =
    (evidence.browser.expanded?.expandedCardLabels || []).length +
    (evidence.browser.expanded?.handoffDetailTexts || []).length +
    (evidence.browser.expanded?.harnessActivityDetailTexts || []).length;
  const refreshDetailCount =
    (evidence.browser.afterRefresh?.expandedCardLabels || []).length +
    (evidence.browser.afterRefresh?.handoffDetailTexts || []).length +
    (evidence.browser.afterRefresh?.harnessActivityDetailTexts || []).length;
  const detailApplicable =
    evidence.browser.expandedReceipt?.detailApplicable === true;
  const handoffVisible =
    !turnAnalysis.hasHandoff || initialHandoffLabels.length > 0;
  const handoffDurable =
    !turnAnalysis.hasHandoff ||
    (refreshHandoffLabels.length > 0 &&
      JSON.stringify(initialHandoffLabels) ===
        JSON.stringify(refreshHandoffLabels));
  const ui = {
    agentApiAccessPass: evidence.browser.agentApiAccess?.pass === true,
    selectedAgentVisibleBefore:
      evidence.browser.before?.selectedAgentVisible === true,
    expectedConversationPathVisible:
      evidence.browser.expanded?.expectedConversationPath === true &&
      evidence.browser.afterRefresh?.expectedConversationPath === true,
    expandedAnswerVisible: evidence.browser.expanded?.answerVisible === true,
    refreshAnswerVisible: evidence.browser.afterRefresh?.answerVisible === true,
    detailExpansionPass:
      evidence.browser.expandedReceipt?.pass === true &&
      handoffVisible &&
      (!detailApplicable || initialDetailCount > 0),
    detailRefreshPass:
      evidence.browser.refreshExpandedReceipt?.pass === true &&
      handoffDurable &&
      (!detailApplicable ||
        (refreshDetailCount > 0 &&
          evidence.browser.expanded?.detailFingerprint ===
            evidence.browser.afterRefresh?.detailFingerprint)),
    visibleProgressSettlementPass: didVisibleProgressSettle(
      evidence.browser.backgroundSettledBeforeExpansion,
      evidence.browser.backgroundSettledAfterRefresh,
    ),
  };
  evidence.acceptance = evaluateAcceptance({
    requestInjectionCount: evidence.requestInjectionCount,
    conversationPreserved: evidence.run.conversationPreserved === true,
    ...ui,
    databaseTerminal: evidence.turnTerminal,
    conversationAgentMatches: turnAnalysis.conversationAgentMatches === true,
    allTransfersResolved: turnAnalysis.allTransfersResolved === true,
    finalMainAfterLastTransfer:
      turnAnalysis.finalMainAfterLastTransfer === true,
    mainLast: turnAnalysis.mainLast === true,
    expectedToolExecutionRequired:
      evidence.database.expectedToolExecution.required === true,
    expectedToolExecutionPass:
      evidence.database.expectedToolExecution.pass === true,
    expectedScheduleLifecycleRequired:
      expectedScheduleLifecycle.required === true,
    expectedScheduleLifecyclePass: expectedScheduleLifecycle.pass === true,
    screenshotCount: evidence.screenshots.length,
    sessionDeleteCount: evidence.sessionCleanup.deletedCount,
    error: evidence.error || evidence.requestInjectionError || "",
  });
  writePrivateJson(
    path.join(args.outputDir, "evidence.private.json"),
    evidence,
  );
  const publicSummary = buildPublicSummary({
    args,
    conversationId,
    visibleAgentNames,
    messageSummary: evidence.database.messageSummary,
    turnTerminal: evidence.turnTerminal,
    screenshotCount: evidence.screenshots.length,
    sessionDeleteCount: evidence.sessionCleanup.deletedCount,
    requestInjectionCount: evidence.requestInjectionCount,
    conversationPreserved: evidence.conversationPreserved,
    runtimeIdentity: runtime.runtimeIdentity,
    correlationSource: evidence.database.correlationSource,
    turnAnalysis,
    ui,
    timing: evidence.browser.firstVisibleMainPaint || {},
    expectedToolExecution: evidence.database.expectedToolExecution,
    expectedScheduleLifecycle,
    acceptance: evidence.acceptance,
    error:
      evidence.error || evidence.requestInjectionError
        ? safeError(evidence.error || evidence.requestInjectionError)
        : "",
  });
  writePrivateJson(
    path.join(args.outputDir, "summary.public-safe.json"),
    publicSummary,
  );
  return publicSummary;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return;
  }
  const summary = await runHarness(args);
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  process.exitCode = summary.pass ? 0 : 1;
}

module.exports = {
  analyzePersistedTurn,
  armFirstVisibleMainPaintObserver,
  assertHarnessSafety,
  bodyContainsAnswer,
  buildPublicSummary,
  buildReopenUiReceipt,
  correlatedVisibleAnswerInDocument,
  correlateFirstVisibleMainPaint,
  collectVisibleState,
  createAgentChatPostObserver,
  deleteInsertedAuthSession,
  deleteScheduleThroughMcp,
  deriveConversationPreserved,
  deriveSubmitConversationPreserved,
  didVisibleProgressSettle,
  evaluateAcceptance,
  evaluateExactlyOnceToolExecution,
  evaluateReopenAcceptance,
  expandVisibleDetails,
  finalizeExpectedScheduleLifecycle,
  findCorrelatedQaUserMessage,
  installAccessToken,
  installReopenChatPostGuard,
  isAgentChatSubmissionPath,
  isTurnTerminal,
  loadSelectedRuntimeEnv,
  parseArgs,
  preflightSelectedRuntime,
  prepareExpectedScheduleLifecycle,
  readSchedulingState,
  reopenLineageFingerprint,
  revalidateReopenLineage,
  scrollTerminalMessageViewportInDocument,
  resolveSelectedSchedulingRuntimeBinding,
  readFirstVisibleMainPaintObserver,
  runHarness,
  safeError,
  summarizeMessages,
  validateReopenPersistedConversation,
  verifyAgentApiAccess,
  verifySchedulingMcpHealth,
  waitForCorrelatedVisibleAnswer,
  waitForVisibleBackgroundSettlement,
  withQaRequestMetadata,
};

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${safeError(error)}\n`);
    process.exitCode = 1;
  });
}
