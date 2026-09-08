#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {createRequire} = require('node:module');
const {setTimeout: delay} = require('node:timers/promises');

const REPLICA_SET = 'vivenNative';
const [libreChatRoot, socketPath, timeoutArgument = '30'] = process.argv.slice(2);
const timeoutSeconds = Number(timeoutArgument);
let stage = 'arguments';

function ownedSocket() {
  if (!socketPath || !path.isAbsolute(socketPath)) throw new Error('unsafe socket');
  const stat = fs.lstatSync(socketPath);
  if (!stat.isSocket() || stat.isSymbolicLink() || stat.uid !== process.getuid() ||
      (stat.mode & 0o777) !== 0o600) throw new Error('unsafe socket');
  return [stat.dev, stat.ino];
}

function validateReplica(config) {
  assert.equal(config._id, REPLICA_SET);
  assert.ok(Number.isInteger(config.version) && config.version > 0);
  assert.ok(config.term === undefined || (Number.isInteger(config.term) && config.term >= -1));
  const {version, term, settings, ...topology} = config;
  assert.deepEqual(topology, {
    _id: REPLICA_SET,
    members: [{
      _id: 0,
      host: socketPath,
      arbiterOnly: false,
      buildIndexes: true,
      hidden: false,
      priority: 1,
      tags: {},
      secondaryDelaySecs: 0,
      votes: 1,
    }],
    protocolVersion: 1,
    writeConcernMajorityJournalDefault: true,
  });
  const {replicaSetId, ...options} = settings;
  assert.ok(replicaSetId != null);
  assert.deepEqual(options, {
    chainingAllowed: true,
    heartbeatIntervalMillis: 2000,
    heartbeatTimeoutSecs: 10,
    electionTimeoutMillis: 10000,
    catchUpTimeoutMillis: -1,
    catchUpTakeoverDelayMillis: 30000,
    getLastErrorModes: {},
    getLastErrorDefaults: {w: 1, wtimeout: 0},
  });
}

(async () => {
  if (!libreChatRoot || !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
    throw new Error('invalid arguments');
  }
  stage = 'owned socket verification';
  const socketIdentity = ownedSocket();
  const libreChatRequire = createRequire(path.join(path.resolve(libreChatRoot), 'package.json'));
  // Mongoose retains this driver in the pruned native payload.
  const {MongoClient} = libreChatRequire('mongoose').mongo;
  const timeoutMS = Math.ceil(timeoutSeconds * 1000);
  const deadline = Date.now() + timeoutMS;
  const client = new MongoClient(`mongodb://${encodeURIComponent(socketPath)}/admin`, {
    directConnection: true,
    serverSelectionTimeoutMS: timeoutMS,
    connectTimeoutMS: timeoutMS,
    socketTimeoutMS: timeoutMS,
  });
  try {
    stage = 'owned server connection';
    await client.connect();
    const admin = client.db('admin');
    const command = value => {
      const remaining = deadline - Date.now();
      if (remaining <= 0) throw new Error('readiness timeout');
      return admin.command({...value, maxTimeMS: remaining});
    };
    stage = 'replica configuration read';
    let configuration;
    try {
      configuration = await command({replSetGetConfig: 1});
    } catch (error) {
      if (error.code !== 94) throw error;
      stage = 'uninitialized replica initialization';
      assert.deepEqual(ownedSocket(), socketIdentity);
      await command({replSetInitiate: {
        _id: REPLICA_SET,
        members: [{_id: 0, host: socketPath}],
      }});
      configuration = await command({replSetGetConfig: 1});
    }
    stage = 'exact replica configuration verification';
    validateReplica(configuration.config);
    stage = 'writable primary readiness';
    while (true) {
      const hello = await command({hello: 1});
      if (hello.isWritablePrimary) {
        assert.equal(hello.setName, REPLICA_SET);
        assert.equal(hello.me, socketPath);
        assert.deepEqual(hello.hosts, [socketPath]);
        break;
      }
      await delay(Math.min(100, Math.max(1, deadline - Date.now())));
    }
    stage = 'final replica and socket verification';
    validateReplica((await command({replSetGetConfig: 1})).config);
    assert.deepEqual(ownedSocket(), socketIdentity);
  } finally {
    await client.close();
  }
})().catch(() => {
  // Server messages may contain private paths or connection details.
  process.stderr.write(`Native MongoDB replica readiness failed at ${stage}.\n`);
  process.exitCode = 1;
});
