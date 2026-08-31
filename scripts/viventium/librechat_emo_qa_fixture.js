#!/usr/bin/env node
/* === VIVENTIUM START ===
 * Feature: EMO-UC-048 installed synthetic fixture lifecycle.
 * Purpose: Use installed LibreChat models to create, inspect, and remove one exact fixture.
 * Safety: Raw scope enters through an inherited owner-only file descriptor and never enters output or errors.
 * === VIVENTIUM END === */

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { createRequire } = require("module");
const { TextDecoder } = require("util");

const CASE_ID = "EMO-UC-048";
const FIXTURE_CASE_ID = "emo_uc_048";
const FIXTURE_TAG = "viventium:local-qa:emo_uc_048";
const FIXTURE_PROVIDER = "viventium_local_qa_fixture";
const ACTIONS = new Set(["provision", "inspect", "destroy"]);
const MAX_INPUT_BYTES = 8 * 1024;
const HASH_PATTERN = /^sha256:[a-f0-9]{64}$/;
const OWNER_PATTERN = /^[a-f0-9]{24}$/;
const NAMESPACE_PATTERN = /^[a-f0-9]{32}$/;
const FIXTURE_REF_PATTERN = /^emo048_fixture_[a-f0-9]{24}$/;
const ISO_MILLIS_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$/;
const FIXTURE_KEYS = new Set([
  "caseTokenHash",
  "componentArtifactDigest",
  "conversationId",
  "conversationScopeHash",
  "email",
  "expiresAt",
  "ownerId",
  "ownerScopeHash",
  "parentMessageId",
  "parentScopeHash",
]);

function fail() {
  const error = new Error("fixture_operation_failed");
  error.code = "fixture_operation_failed";
  throw error;
}

function exactKeys(value, expected) {
  return (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === expected.size &&
    Object.keys(value).every((key) => expected.has(key))
  );
}

function parseArgs(argv) {
  const action = String(argv[0] || "");
  if (!ACTIONS.has(action)) fail();
  let scopeFd;
  let jsonSeen = false;
  for (let index = 1; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--json" && !jsonSeen) {
      jsonSeen = true;
      continue;
    }
    if (argument === "--scope-fd" && scopeFd === undefined) {
      if (index + 1 >= argv.length) fail();
      scopeFd = Number(argv[++index]);
      continue;
    }
    fail();
  }
  if (!Number.isSafeInteger(scopeFd) || scopeFd < 3 || scopeFd > 1024) fail();
  return { action, scopeFd };
}

function parseStrictJson(text) {
  let index = 0;

  function whitespace() {
    while (
      index < text.length &&
      /[\u0009\u000a\u000d\u0020]/.test(text[index])
    )
      index += 1;
  }

  function stringToken() {
    if (text[index] !== '"') fail();
    const start = index++;
    while (index < text.length) {
      const character = text[index++];
      if (character === '"') {
        try {
          return JSON.parse(text.slice(start, index));
        } catch {
          fail();
        }
      }
      if (character === "\\") {
        if (index >= text.length) fail();
        const escape = text[index++];
        if (escape === "u") {
          const digits = text.slice(index, index + 4);
          if (!/^[0-9a-fA-F]{4}$/.test(digits)) fail();
          index += 4;
        } else if (!'"\\/bfnrt'.includes(escape)) {
          fail();
        }
      } else if (character.charCodeAt(0) < 0x20) {
        fail();
      }
    }
    fail();
  }

  function value() {
    whitespace();
    if (text[index] === "{") return object();
    if (text[index] === "[") return array();
    if (text[index] === '"') {
      stringToken();
      return;
    }
    const token = text
      .slice(index)
      .match(
        /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/,
      );
    if (!token) fail();
    index += token[0].length;
  }

  function object() {
    index += 1;
    const keys = new Set();
    whitespace();
    if (text[index] === "}") {
      index += 1;
      return;
    }
    while (index < text.length) {
      whitespace();
      const key = stringToken();
      if (keys.has(key)) fail();
      keys.add(key);
      whitespace();
      if (text[index++] !== ":") fail();
      value();
      whitespace();
      const delimiter = text[index++];
      if (delimiter === "}") return;
      if (delimiter !== ",") fail();
    }
    fail();
  }

  function array() {
    index += 1;
    whitespace();
    if (text[index] === "]") {
      index += 1;
      return;
    }
    while (index < text.length) {
      value();
      whitespace();
      const delimiter = text[index++];
      if (delimiter === "]") return;
      if (delimiter !== ",") fail();
    }
    fail();
  }

  value();
  whitespace();
  if (index !== text.length) fail();
  try {
    return JSON.parse(text);
  } catch {
    fail();
  }
}

function digest(label, value) {
  return `sha256:${crypto.createHash("sha256").update(`${label}\0${value}`).digest("hex")}`;
}

function parseDocument(document) {
  if (
    !exactKeys(document, new Set(["fixture", "fixtureRef", "schemaVersion"])) ||
    document.schemaVersion !== 1 ||
    !FIXTURE_REF_PATTERN.test(String(document.fixtureRef || "")) ||
    !exactKeys(document.fixture, FIXTURE_KEYS)
  ) {
    fail();
  }
  const fixture = Object.fromEntries(
    Object.entries(document.fixture).map(([key, value]) => [
      key,
      String(value || "").trim(),
    ]),
  );
  const namespace = fixture.conversationId.replace(
    /^emo_uc_048_conversation_/,
    "",
  );
  const expiry = new Date(fixture.expiresAt);
  const canonicalExpiry = Number.isFinite(expiry.getTime())
    ? expiry.toISOString().replace(/Z$/, "+00:00")
    : "";
  if (
    !OWNER_PATTERN.test(fixture.ownerId) ||
    !NAMESPACE_PATTERN.test(namespace) ||
    fixture.parentMessageId !== `emo_uc_048_parent_${namespace}` ||
    fixture.email !== `emo-uc-048-${namespace}@local-qa.invalid` ||
    !Number.isFinite(expiry.getTime()) ||
    !ISO_MILLIS_PATTERN.test(fixture.expiresAt) ||
    fixture.expiresAt !== canonicalExpiry ||
    !HASH_PATTERN.test(fixture.componentArtifactDigest) ||
    !HASH_PATTERN.test(fixture.caseTokenHash) ||
    fixture.ownerScopeHash !== digest("owner", fixture.ownerId) ||
    fixture.conversationScopeHash !==
      digest("conversation", fixture.conversationId) ||
    fixture.parentScopeHash !== digest("parent", fixture.parentMessageId)
  ) {
    fail();
  }
  return { fixture, fixtureRef: document.fixtureRef, expiry };
}

function readDocument(scopeFd) {
  let before;
  try {
    before = fs.fstatSync(scopeFd);
  } catch {
    fail();
  }
  if (
    !before.isFile() ||
    (typeof process.getuid === "function" && before.uid !== process.getuid()) ||
    (before.mode & 0o777) !== 0o600 ||
    before.nlink !== 1 ||
    before.size < 1 ||
    before.size > MAX_INPUT_BYTES
  ) {
    fail();
  }
  let raw;
  let after;
  try {
    raw = fs.readFileSync(scopeFd);
    after = fs.fstatSync(scopeFd);
  } catch {
    fail();
  }
  if (
    raw.length < 1 ||
    raw.length > MAX_INPUT_BYTES ||
    before.dev !== after.dev ||
    before.ino !== after.ino ||
    before.size !== after.size ||
    raw.length !== after.size
  ) {
    fail();
  }
  try {
    const content = new TextDecoder("utf-8", { fatal: true }).decode(raw);
    return parseDocument(parseStrictJson(content));
  } catch (error) {
    if (error?.code === "fixture_operation_failed") throw error;
    fail();
  }
}

function resolveInstalledRoot() {
  const configured = String(process.env.VIVENTIUM_LIBRECHAT_ROOT || "").trim();
  if (!configured) fail();
  let root;
  try {
    root = fs.realpathSync(configured);
  } catch {
    fail();
  }
  if (
    !fs.statSync(root).isDirectory() ||
    !fs.statSync(path.join(root, "package.json")).isFile()
  ) {
    fail();
  }
  return root;
}

function installedModels(root) {
  const installedRequire = createRequire(path.join(root, "package.json"));
  const mongoose = installedRequire("mongoose");
  const { createModels } = installedRequire("@librechat/data-schemas");
  if (typeof createModels !== "function") fail();
  return { mongoose, models: createModels(mongoose) };
}

function fixtureMetadata(fixture, expiry) {
  return {
    schemaVersion: 1,
    caseId: FIXTURE_CASE_ID,
    componentArtifactDigest: fixture.componentArtifactDigest,
    caseTokenHash: fixture.caseTokenHash,
    ownerScopeHash: fixture.ownerScopeHash,
    conversationScopeHash: fixture.conversationScopeHash,
    parentScopeHash: fixture.parentScopeHash,
    expiresAt: expiry,
  };
}

function sameDate(left, right) {
  const leftDate = new Date(left);
  const rightDate = new Date(right);
  return (
    Number.isFinite(leftDate.getTime()) &&
    leftDate.getTime() === rightDate.getTime()
  );
}

function exactMetadata(value, expected) {
  if (!exactKeys(value, new Set(Object.keys(expected)))) return false;
  return Object.entries(expected).every(([key, expectedValue]) =>
    key === "expiresAt"
      ? sameDate(value[key], expectedValue)
      : value[key] === expectedValue,
  );
}

function exactUser(row, fixture, expiry) {
  return Boolean(
    row &&
    String(row._id) === fixture.ownerId &&
    row.provider === FIXTURE_PROVIDER &&
    row.email === fixture.email &&
    row.idOnTheSource === `${FIXTURE_TAG}:${fixture.caseTokenHash}` &&
    sameDate(row.expiresAt, expiry),
  );
}

function exactConversation(row, fixture, expiry) {
  const tags = Array.isArray(row?.tags) ? [...row.tags].sort() : [];
  const expectedTags = [FIXTURE_TAG, fixture.caseTokenHash].sort();
  return Boolean(
    row &&
    String(row.user) === fixture.ownerId &&
    row.conversationId === fixture.conversationId &&
    tags.length === 2 &&
    tags.every((tag, index) => tag === expectedTags[index]) &&
    sameDate(row.expiredAt, expiry),
  );
}

function exactMessage(row, fixture, expiry) {
  const metadata = row?.metadata?.viventium?.localQaFixture;
  return Boolean(
    row &&
    String(row.user) === fixture.ownerId &&
    row.conversationId === fixture.conversationId &&
    row.messageId === fixture.parentMessageId &&
    row.isCreatedByUser === false &&
    sameDate(row.expiredAt, expiry) &&
    exactMetadata(metadata, fixtureMetadata(fixture, expiry)),
  );
}

async function readRows(models, fixture) {
  const [owners, conversations, parents] = await Promise.all([
    models.User.find({
      $or: [{ _id: fixture.ownerId }, { email: fixture.email }],
    })
      .limit(2)
      .lean(),
    models.Conversation.find({ conversationId: fixture.conversationId })
      .limit(2)
      .lean(),
    models.Message.find({ messageId: fixture.parentMessageId }).limit(2).lean(),
  ]);
  if (
    !Array.isArray(owners) ||
    !Array.isArray(conversations) ||
    !Array.isArray(parents) ||
    owners.length > 1 ||
    conversations.length > 1 ||
    parents.length > 1
  ) {
    fail();
  }
  return {
    owner: owners[0] || null,
    conversation: conversations[0] || null,
    parent: parents[0] || null,
  };
}

function assertRowsExact(rows, fixture, expiry) {
  if (
    (rows.owner && !exactUser(rows.owner, fixture, expiry)) ||
    (rows.conversation &&
      !exactConversation(rows.conversation, fixture, expiry)) ||
    (rows.parent && !exactMessage(rows.parent, fixture, expiry))
  ) {
    fail();
  }
}

function rowCounts(rows) {
  return {
    conversation: rows.conversation ? 1 : 0,
    message: rows.parent ? 1 : 0,
    user: rows.owner ? 1 : 0,
  };
}

async function provision(models, fixture, expiry) {
  let rows = await readRows(models, fixture);
  assertRowsExact(rows, fixture, expiry);
  if (!rows.owner) {
    await models.User.create({
      _id: fixture.ownerId,
      email: fixture.email,
      emailVerified: false,
      idOnTheSource: `${FIXTURE_TAG}:${fixture.caseTokenHash}`,
      name: "EMO-UC-048 synthetic fixture",
      provider: FIXTURE_PROVIDER,
      expiresAt: expiry,
    });
  }
  if (!rows.conversation) {
    await models.Conversation.create({
      conversationId: fixture.conversationId,
      expiredAt: expiry,
      tags: [FIXTURE_TAG, fixture.caseTokenHash],
      title: "EMO-UC-048 synthetic fixture",
      user: fixture.ownerId,
    });
  }
  if (!rows.parent) {
    await models.Message.create({
      conversationId: fixture.conversationId,
      expiredAt: expiry,
      isCreatedByUser: false,
      messageId: fixture.parentMessageId,
      metadata: {
        viventium: { localQaFixture: fixtureMetadata(fixture, expiry) },
      },
      sender: "Viventium local QA fixture",
      text: "Synthetic EMO-UC-048 parent fixture.",
      user: fixture.ownerId,
    });
  }
  rows = await readRows(models, fixture);
  assertRowsExact(rows, fixture, expiry);
  const counts = rowCounts(rows);
  if (Object.values(counts).some((count) => count !== 1)) fail();
  return counts;
}

async function inspect(models, fixture, expiry) {
  const rows = await readRows(models, fixture);
  assertRowsExact(rows, fixture, expiry);
  return rowCounts(rows);
}

function userDeleteFilter(row, fixture, expiry) {
  return {
    _id: row._id,
    email: fixture.email,
    expiresAt: expiry,
    idOnTheSource: `${FIXTURE_TAG}:${fixture.caseTokenHash}`,
    provider: FIXTURE_PROVIDER,
  };
}

function conversationDeleteFilter(row, fixture, expiry) {
  return {
    _id: row._id,
    conversationId: fixture.conversationId,
    expiredAt: expiry,
    tags: [FIXTURE_TAG, fixture.caseTokenHash],
    user: fixture.ownerId,
  };
}

function messageDeleteFilter(row, fixture, expiry) {
  return {
    _id: row._id,
    conversationId: fixture.conversationId,
    expiredAt: expiry,
    isCreatedByUser: false,
    messageId: fixture.parentMessageId,
    "metadata.viventium.localQaFixture": fixtureMetadata(fixture, expiry),
    user: fixture.ownerId,
  };
}

async function deleteExact(model, filter) {
  const result = await model.deleteOne(filter);
  if (Number(result?.deletedCount || 0) !== 1) fail();
}

async function destroy(models, fixture, expiry) {
  const rows = await readRows(models, fixture);
  assertRowsExact(rows, fixture, expiry);
  const activeControls = await models.LocalQaCortexFaultControl.countDocuments({
    caseTokenHash: fixture.caseTokenHash,
    conversationScopeHash: fixture.conversationScopeHash,
    ownerScopeHash: fixture.ownerScopeHash,
    parentScopeHash: fixture.parentScopeHash,
    state: "armed",
    syntheticScope: true,
  });
  if (activeControls !== 0) fail();
  if (rows.parent) {
    await deleteExact(
      models.Message,
      messageDeleteFilter(rows.parent, fixture, expiry),
    );
  }
  if (rows.conversation) {
    await deleteExact(
      models.Conversation,
      conversationDeleteFilter(rows.conversation, fixture, expiry),
    );
  }
  if (rows.owner) {
    await deleteExact(
      models.User,
      userDeleteFilter(rows.owner, fixture, expiry),
    );
  }
  const remaining = await readRows(models, fixture);
  assertRowsExact(remaining, fixture, expiry);
  const counts = rowCounts(remaining);
  if (Object.values(counts).some((count) => count !== 0)) fail();
  return counts;
}

function redacted(action, fixtureRef, fixture, rows) {
  return {
    action,
    caseId: CASE_ID,
    fixtureRef,
    hashes: {
      caseTokenHash: fixture.caseTokenHash,
      conversationScopeHash: fixture.conversationScopeHash,
      ownerScopeHash: fixture.ownerScopeHash,
      parentScopeHash: fixture.parentScopeHash,
    },
    rows,
    schemaVersion: 1,
  };
}

async function main(argv = process.argv.slice(2)) {
  if (argv.length === 1 && (argv[0] === "--help" || argv[0] === "-h")) {
    process.stdout.write(
      "Usage: node librechat_emo_qa_fixture.js <provision|inspect|destroy> " +
        "--scope-fd <private-fd> [--json]\n",
    );
    return 0;
  }
  const { action, scopeFd } = parseArgs(argv);
  const { fixture, fixtureRef, expiry } = readDocument(scopeFd);
  if (action !== "destroy" && expiry.getTime() <= Date.now()) fail();
  const componentArtifactDigest = String(
    process.env.VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST || "",
  ).trim();
  if (
    !HASH_PATTERN.test(componentArtifactDigest) ||
    componentArtifactDigest !== fixture.componentArtifactDigest
  ) {
    fail();
  }
  const root = resolveInstalledRoot();
  const { mongoose, models } = installedModels(root);
  const mongoUri = String(process.env.MONGO_URI || "").trim();
  if (!mongoUri) fail();
  try {
    await mongoose.connect(mongoUri);
    let rows;
    if (action === "provision") rows = await provision(models, fixture, expiry);
    else if (action === "inspect")
      rows = await inspect(models, fixture, expiry);
    else rows = await destroy(models, fixture, expiry);
    process.stdout.write(
      `${JSON.stringify(redacted(action, fixtureRef, fixture, rows))}\n`,
    );
    return 0;
  } finally {
    await mongoose.disconnect();
  }
}

if (require.main === module) {
  main().catch(() => {
    process.stderr.write(
      `${JSON.stringify({ ok: false, error: "fixture_operation_failed" })}\n`,
    );
    process.exitCode = 1;
  });
}

module.exports = {
  conversationDeleteFilter,
  exactConversation,
  exactMessage,
  exactUser,
  main,
  messageDeleteFilter,
  parseArgs,
  parseDocument,
  parseStrictJson,
  readDocument,
  redacted,
  userDeleteFilter,
};
