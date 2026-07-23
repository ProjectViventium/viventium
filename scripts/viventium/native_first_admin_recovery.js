#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {createRequire} = require('module');

const [statePath, libreChatRoot, mongoURI, shippedBundlePath] = process.argv.slice(2);
if (!statePath || !libreChatRoot || !mongoURI) process.exit(2);
const libreChatRequire = createRequire(path.join(libreChatRoot, 'package.json'));
const {mongo} = libreChatRequire('mongoose');
const {MongoClient, ObjectId} = mongo;
const PLACEHOLDER_OWNER_EMAIL = 'viventium-system@example.com';
const OWNER_RECOVERY_GUIDANCE =
  'Restore the Native first-admin state and administrator from the latest Viventium backup, then restart; protected owner state was not changed.';

function writeState(value) {
  const temporary = `${statePath}.${process.pid}.${crypto.randomBytes(8).toString('hex')}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value)}\n`, {encoding: 'utf8', mode: 0o600, flag: 'wx'});
  fs.renameSync(temporary, statePath);
}

function readOwnerState() {
  if (!fs.existsSync(statePath)) return null;
  const metadata = fs.lstatSync(statePath);
  if (
    !metadata.isFile() ||
    metadata.isSymbolicLink() ||
    metadata.uid !== process.getuid() ||
    (metadata.mode & 0o777) !== 0o600
  ) {
    throw new Error('first-admin state must be a regular, owner-owned mode 0600 file');
  }
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  if (state?.schema_version !== 1 || !['open', 'closed'].includes(state?.status)) {
    throw new Error(`first-admin state is invalid. ${OWNER_RECOVERY_GUIDANCE}`);
  }
  let ownerId = null;
  if (state.status === 'closed' && state.admin_user_id != null) {
    ownerId = String(state.admin_user_id);
    if (!/^[a-f0-9]{24}$/i.test(ownerId)) {
      throw new Error(
        `stored first administrator has an invalid user id. ${OWNER_RECOVERY_GUIDANCE}`,
      );
    }
  }
  return {state, ownerId};
}

function readShippedMainAgentId() {
  const bundlePath =
    shippedBundlePath ||
    path.resolve(libreChatRoot, '..', 'defaults', 'viventium-agents.yaml');
  if (!fs.existsSync(bundlePath)) return null;
  const metadata = fs.lstatSync(bundlePath);
  if (
    !metadata.isFile() ||
    metadata.isSymbolicLink() ||
    metadata.size > 10 * 1024 * 1024
  ) {
    throw new Error(`shipped agent bundle is unsafe. ${OWNER_RECOVERY_GUIDANCE}`);
  }
  const yaml = libreChatRequire('js-yaml');
  const bundle = yaml.load(fs.readFileSync(bundlePath, 'utf8'), {
    schema: yaml.JSON_SCHEMA,
  });
  const mainAgentId = String(
    bundle?.meta?.mainAgentId || bundle?.mainAgent?.id || '',
  ).trim();
  if (!mainAgentId || mainAgentId.length > 256) {
    throw new Error(
      `shipped agent bundle has no valid main agent id. ${OWNER_RECOVERY_GUIDANCE}`,
    );
  }
  return mainAgentId;
}

async function resolveLegacyClosedOwner(db, users) {
  const mainAgentId = readShippedMainAgentId();
  if (!mainAgentId) return null;
  const mainAgent = await db
    .collection('agents')
    .findOne({id: mainAgentId}, {projection: {_id: 0, author: 1}});
  if (!mainAgent) return null;
  const ownerId = String(mainAgent.author || '');
  if (!/^[a-f0-9]{24}$/i.test(ownerId)) {
    throw new Error(`shipped main agent owner is invalid. ${OWNER_RECOVERY_GUIDANCE}`);
  }
  const owner = await users.findOne(
    {
      _id: new ObjectId(ownerId),
      role: 'ADMIN',
      email: {$ne: PLACEHOLDER_OWNER_EMAIL},
    },
    {projection: {_id: 1}},
  );
  if (!owner || String(owner._id) !== ownerId) {
    throw new Error(
      `shipped main agent owner is no longer a valid local administrator. ${OWNER_RECOVERY_GUIDANCE}`,
    );
  }
  return ownerId;
}

function writeClosedOwner(ownerState, ownerId) {
  const retained =
    ownerState?.state?.status === 'closed' ? ownerState.state : {};
  writeState({
    ...retained,
    schema_version: 1,
    status: 'closed',
    admin_user_id: ownerId,
    reconciled_at: Math.floor(Date.now() / 1000),
  });
}

(async () => {
  const client = new MongoClient(mongoURI, {serverSelectionTimeoutMS: 5000});
  try {
    await client.connect();
    const db = client.db('LibreChat');
    const users = db.collection('users');
    const ownerState = readOwnerState();
    const closedOwnerId = ownerState?.ownerId || null;
    if (closedOwnerId) {
      const owner = await users.findOne(
        {
          _id: new ObjectId(closedOwnerId),
          role: 'ADMIN',
          email: {$ne: PLACEHOLDER_OWNER_EMAIL},
        },
        {projection: {_id: 1}},
      );
      if (!owner || String(owner._id) !== closedOwnerId) {
        throw new Error(
          `stored first administrator is no longer a valid local administrator. ${OWNER_RECOVERY_GUIDANCE}`,
        );
      }
      return;
    }
    if (ownerState?.state?.status === 'closed') {
      const recoveredOwnerId = await resolveLegacyClosedOwner(db, users);
      if (recoveredOwnerId) {
        writeClosedOwner(ownerState, recoveredOwnerId);
        return;
      }
    }
    const totalUsers = await users.countDocuments({}, {limit: 1});
    if (totalUsers === 0) {
      writeState({schema_version: 1, status: 'open', token: crypto.randomBytes(32).toString('hex')});
      return;
    }

    const administrators = await users
      .find(
        {
          role: 'ADMIN',
          email: {$ne: PLACEHOLDER_OWNER_EMAIL},
        },
        {projection: {_id: 1}},
      )
      .limit(2)
      .toArray();
    if (administrators.length !== 1) {
      throw new Error(
        `expected exactly one non-placeholder local administrator, found ${administrators.length}`,
      );
    }
    const adminUserId = String(administrators[0]._id || '');
    if (!/^[a-f0-9]{24}$/i.test(adminUserId)) {
      throw new Error('resolved first administrator has an invalid user id');
    }
    writeClosedOwner(ownerState, adminUserId);
  } finally {
    await client.close();
  }
})().catch(error => {
  process.stderr.write(`first-admin reconciliation failed: ${error.message}\n`);
  process.exit(1);
});
