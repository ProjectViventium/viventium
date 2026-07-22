#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const CLAIM_COLLECTION = '__viventium_restore_claim__';

const SAFE_COLLECTIONS = Object.freeze([
  'accessroles',
  'aclentries',
  'agents',
  'agentcategories',
  'assistants',
  'balances',
  'banners',
  'bookmarks',
  'conversationtags',
  'conversations',
  'feelingstates',
  'files',
  'groups',
  'memoryentries',
  'messages',
  'permissions',
  'presets',
  'projects',
  'promptgroups',
  'prompts',
  'roles',
  'sharedlinks',
  'transactions',
  'users',
]);

const USER_FIELDS = Object.freeze([
  '_id',
  'name',
  'username',
  'email',
  'emailVerified',
  'role',
  'provider',
  'avatar',
  'createdAt',
  'updatedAt',
  'viventiumVoiceRoute',
  'viventiumVoiceRouteState',
]);

const SENSITIVE_STRUCTURED_KEY = /^(?:api_?key|api_?hash|token|service_?token|auth_?token|bearer_?token|access_?token|refresh_?token|password|credentials?|authorization|cookie|set_?cookie|private_?key|signing_?key|secret(?:_value)?|client_?secret|call_?session_?secret)$/i;

function normalizeStructuredKey(raw) {
  return String(raw)
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1_$2')
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[^A-Za-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase();
}

function structuredKeyIsSensitive(raw) {
  const normalized = normalizeStructuredKey(raw);
  if (SENSITIVE_STRUCTURED_KEY.test(normalized)) return true;
  const parts = normalized ? normalized.split('_') : [];
  const pairs = new Set([
    'api_key', 'api_hash', 'service_token', 'auth_token', 'bearer_token',
    'access_token', 'refresh_token', 'set_cookie', 'private_key',
    'session_token', 'oauth_token', 'id_token', 'signing_key', 'client_secret',
  ]);
  for (let index = 0; index + 1 < parts.length; index += 1) {
    if (pairs.has(`${parts[index]}_${parts[index + 1]}`)) return true;
  }
  return false;
}

function isPlainObject(value) {
  if (!value || typeof value !== 'object') return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

const TOOL_PAYLOAD_KEYS = new Set(['tool_call', 'tool_calls', 'toolcall', 'toolcalls']);
const TOOL_SECRET_FIELDS = new Set(['args', 'arguments', 'output', 'result', 'results']);

function isToolPayload(value) {
  if (!isPlainObject(value)) return false;
  const normalizedType = typeof value.type === 'string' ? normalizeStructuredKey(value.type) : '';
  if (TOOL_PAYLOAD_KEYS.has(normalizedType)) return true;
  return Object.keys(value).some((key) => TOOL_PAYLOAD_KEYS.has(normalizeStructuredKey(key)));
}

function sanitizeExportValue(value, toolPayload = false) {
  if (Array.isArray(value)) return value.map((item) => sanitizeExportValue(item, toolPayload));
  if (isPlainObject(value)) {
    const currentToolPayload = toolPayload || isToolPayload(value);
    const sanitized = {};
    for (const [key, child] of Object.entries(value)) {
      const normalizedKey = normalizeStructuredKey(key);
      if (
        structuredKeyIsSensitive(key)
        || TOOL_PAYLOAD_KEYS.has(normalizedKey)
        || (currentToolPayload && TOOL_SECRET_FIELDS.has(normalizedKey))
      ) continue;
      sanitized[key] = sanitizeExportValue(
        child,
        currentToolPayload || TOOL_PAYLOAD_KEYS.has(normalizedKey),
      );
    }
    return sanitized;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        return JSON.stringify(sanitizeExportValue(JSON.parse(value), toolPayload));
      } catch {
        // Non-JSON prose is preserved; the policy is deliberately structural.
      }
    }
  }
  return value;
}

function sanitizeExportDocument(document) {
  return sanitizeExportValue(document);
}

function parseArgs(argv) {
  const args = { command: argv[2] || '' };
  for (let index = 3; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith('--') || index + 1 >= argv.length) {
      throw new Error('invalid arguments');
    }
    args[item.slice(2)] = argv[index + 1];
    index += 1;
  }
  return args;
}

function requireMongo(repoRoot) {
  const sourcePackage = path.join(repoRoot, 'viventium_v0_4', 'LibreChat', 'package.json');
  const nativePackage = path.join(repoRoot, 'runtime', 'librechat', 'package.json');
  const packageJson = fs.existsSync(sourcePackage) ? sourcePackage : nativePackage;
  const scopedRequire = createRequire(packageJson);
  const mongodb = scopedRequire('mongodb');
  const bson = scopedRequire('bson');
  return { MongoClient: mongodb.MongoClient, EJSON: bson.EJSON };
}

function validateUri(raw, socketPath = '') {
  const url = new URL(raw);
  const expectedSocket = socketPath ? path.resolve(socketPath) : '';
  const socketMatches = Boolean(expectedSocket) && decodeURIComponent(url.hostname) === expectedSocket;
  if (
    url.protocol !== 'mongodb:' ||
    url.username ||
    url.password ||
    (!socketMatches && !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) ||
    url.search ||
    url.hash
  ) {
    throw new Error('only credential-free loopback Mongo URIs are supported');
  }
  const database = url.pathname.replace(/^\//, '');
  if (!/^[A-Za-z0-9._-]{1,64}$/.test(database)) {
    throw new Error('invalid Mongo database selection');
  }
  return database;
}

function validateOutputDirectory(outputDir) {
  const metadata = fs.lstatSync(outputDir);
  if (!metadata.isDirectory() || metadata.isSymbolicLink()) {
    throw new Error('logical export directory is unsafe');
  }
}

function validateTransactionId(raw) {
  if (!/^[0-9a-f]{32}$/.test(raw || '')) {
    throw new Error('invalid restore transaction identifier');
  }
  return raw;
}

function writeJsonExclusive(outputPath, payload) {
  const descriptor = fs.openSync(outputPath, 'wx', 0o600);
  try {
    fs.writeFileSync(descriptor, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
    fs.fsyncSync(descriptor);
  } finally {
    fs.closeSync(descriptor);
  }
}

async function exportCollections(db, outputDir, EJSON) {
  validateOutputDirectory(outputDir);
  const present = new Set((await db.listCollections({}, { nameOnly: true }).toArray()).map((item) => item.name));
  const ledger = [];
  for (const name of SAFE_COLLECTIONS) {
    if (!present.has(name)) continue;
    const relative = `${String(ledger.length).padStart(3, '0')}.jsonl`;
    const outputPath = path.join(outputDir, relative);
    const descriptor = fs.openSync(outputPath, 'wx', 0o600);
    const hash = crypto.createHash('sha256');
    let documents = 0;
    try {
      const options = name === 'users'
        ? { projection: Object.fromEntries(USER_FIELDS.map((field) => [field, 1])) }
        : {};
      const cursor = db.collection(name).find({}, options).sort({ _id: 1 });
      for await (const document of cursor) {
        const line = `${EJSON.stringify(sanitizeExportDocument(document), { relaxed: false })}\n`;
        const bytes = Buffer.from(line, 'utf8');
        fs.writeSync(descriptor, bytes);
        hash.update(bytes);
        documents += 1;
      }
      fs.fsyncSync(descriptor);
    } finally {
      fs.closeSync(descriptor);
    }
    ledger.push({ name, path: relative, documents, sha256: hash.digest('hex') });
  }
  writeJsonExclusive(path.join(outputDir, 'index.json'), { schemaVersion: 1, collections: ledger });
  return ledger;
}

async function databaseEmpty(db) {
  const names = await db.listCollections({}, { nameOnly: true }).toArray();
  return names.length === 0;
}

async function estimateLogicalBytes(db) {
  const present = new Set((await db.listCollections({}, { nameOnly: true }).toArray()).map((item) => item.name));
  let estimatedBytes = 0;
  for (const name of SAFE_COLLECTIONS) {
    if (!present.has(name)) continue;
    const stats = await db.command({ collStats: name, scale: 1 });
    const size = Number(stats.size);
    if (!Number.isSafeInteger(size) || size < 0) {
      throw new Error('logical collection size estimate is invalid');
    }
    estimatedBytes += size;
    if (!Number.isSafeInteger(estimatedBytes)) {
      throw new Error('logical database size estimate is invalid');
    }
  }
  return estimatedBytes;
}

async function assertClaim(db, transactionId, { allowMissing = false } = {}) {
  const present = await db.listCollections({ name: CLAIM_COLLECTION }, { nameOnly: true }).toArray();
  if (!present.length) {
    if (allowMissing) return false;
    throw new Error('restore database claim is missing');
  }
  const claim = await db.collection(CLAIM_COLLECTION).findOne({ _id: transactionId });
  if (!claim) {
    throw new Error('restore database is claimed by another transaction');
  }
  return true;
}

async function claimDatabase(db, transactionId) {
  if (!(await databaseEmpty(db))) {
    throw new Error('target database is not empty');
  }
  await db.collection(CLAIM_COLLECTION).insertOne({
    _id: transactionId,
    schemaVersion: 1,
    createdAt: new Date(),
  });
  const names = (await db.listCollections({}, { nameOnly: true }).toArray()).map((item) => item.name);
  if (names.length !== 1 || names[0] !== CLAIM_COLLECTION) {
    await db.collection(CLAIM_COLLECTION).drop();
    throw new Error('target database changed while the restore claim was acquired');
  }
}

async function importCollections(db, inputDir, EJSON, transactionId) {
  validateOutputDirectory(inputDir);
  await assertClaim(db, transactionId);
  const initialNames = (await db.listCollections({}, { nameOnly: true }).toArray()).map((item) => item.name);
  if (initialNames.length !== 1 || initialNames[0] !== CLAIM_COLLECTION) {
    throw new Error('target database changed after the restore claim');
  }
  const index = JSON.parse(fs.readFileSync(path.join(inputDir, 'index.json'), 'utf8'));
  if (index.schemaVersion !== 1 || !Array.isArray(index.collections)) {
    throw new Error('logical export index is invalid');
  }
  for (const entry of index.collections) {
    if (
      !entry ||
      !SAFE_COLLECTIONS.includes(entry.name) ||
      !/^[0-9]{3}\.jsonl$/.test(entry.path) ||
      !Number.isSafeInteger(entry.documents) ||
      entry.documents < 0 ||
      !/^[0-9a-f]{64}$/.test(entry.sha256 || '')
    ) {
      throw new Error('logical collection entry is invalid');
    }
    const inputPath = path.join(inputDir, entry.path);
    const stream = fs.createReadStream(path.join(inputDir, entry.path), { encoding: 'utf8' });
    const lines = readline.createInterface({ input: stream, crlfDelay: Infinity });
    let batch = [];
    let count = 0;
    for await (const line of lines) {
      if (!line.trim()) continue;
      batch.push(EJSON.parse(line, { relaxed: false }));
      count += 1;
      if (batch.length >= 500) {
        await db.collection(entry.name).insertMany(batch, { ordered: true });
        batch = [];
      }
    }
    if (batch.length) {
      await db.collection(entry.name).insertMany(batch, { ordered: true });
    }
    if (count !== entry.documents) {
      throw new Error('logical collection count changed before import');
    }
    const hash = crypto.createHash('sha256');
    const hashStream = fs.createReadStream(inputPath);
    for await (const chunk of hashStream) hash.update(chunk);
    if (hash.digest('hex') !== entry.sha256) {
      throw new Error('logical collection hash changed before import');
    }
  }
  return index.collections.length;
}

async function main() {
  const args = parseArgs(process.argv);
  const repoRoot = path.resolve(args['repo-root'] || '');
  const uri = args.uri || '';
  validateUri(uri, args['socket-path'] || '');
  const { MongoClient, EJSON } = requireMongo(repoRoot);
  const client = new MongoClient(uri, { serverSelectionTimeoutMS: 5000, connectTimeoutMS: 5000 });
  try {
    await client.connect();
    const db = client.db();
    if (args.command === 'export') {
      const collections = await exportCollections(db, path.resolve(args['output-dir'] || ''), EJSON);
      process.stdout.write(`${JSON.stringify({ ok: true, collections })}\n`);
      return;
    }
    if (args.command === 'empty') {
      process.stdout.write(`${JSON.stringify({ ok: true, empty: await databaseEmpty(db) })}\n`);
      return;
    }
    if (args.command === 'estimate') {
      process.stdout.write(`${JSON.stringify({ ok: true, estimatedBytes: await estimateLogicalBytes(db) })}\n`);
      return;
    }
    if (args.command === 'claim') {
      const transactionId = validateTransactionId(args['transaction-id']);
      await claimDatabase(db, transactionId);
      process.stdout.write('{"ok":true,"claimed":true}\n');
      return;
    }
    if (args.command === 'import') {
      const transactionId = validateTransactionId(args['transaction-id']);
      const collections = await importCollections(
        db,
        path.resolve(args['input-dir'] || ''),
        EJSON,
        transactionId,
      );
      process.stdout.write(`${JSON.stringify({ ok: true, collections })}\n`);
      return;
    }
    if (args.command === 'release') {
      const transactionId = validateTransactionId(args['transaction-id']);
      await assertClaim(db, transactionId);
      await db.collection(CLAIM_COLLECTION).drop();
      process.stdout.write('{"ok":true,"released":true}\n');
      return;
    }
    if (args.command === 'drop') {
      const transactionId = validateTransactionId(args['transaction-id']);
      if (!(await assertClaim(db, transactionId, { allowMissing: true }))) {
        process.stdout.write('{"ok":true,"dropped":false}\n');
        return;
      }
      await db.dropDatabase();
      process.stdout.write('{"ok":true,"dropped":true}\n');
      return;
    }
    throw new Error('unknown continuity Mongo command');
  } finally {
    await client.close();
  }
}

if (require.main === module) {
  main().catch(() => {
    process.stderr.write('Viventium logical Mongo adapter failed.\n');
    process.exitCode = 4;
  });
}

module.exports = { estimateLogicalBytes, normalizeStructuredKey, sanitizeExportDocument };
