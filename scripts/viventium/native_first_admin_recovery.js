#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {createRequire} = require('module');

const [statePath, libreChatRoot, mongoURI] = process.argv.slice(2);
if (!statePath || !libreChatRoot || !mongoURI) process.exit(2);
const libreChatRequire = createRequire(path.join(libreChatRoot, 'package.json'));
const {mongo} = libreChatRequire('mongoose');
const {MongoClient} = mongo;

function writeState(value) {
  const temporary = `${statePath}.${process.pid}.${crypto.randomBytes(8).toString('hex')}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value)}\n`, {encoding: 'utf8', mode: 0o600, flag: 'wx'});
  fs.renameSync(temporary, statePath);
}

(async () => {
  const client = new MongoClient(mongoURI, {serverSelectionTimeoutMS: 5000});
  try {
    await client.connect();
    const users = await client.db('LibreChat').collection('users').countDocuments({}, {limit: 1});
    if (users > 0) {
      writeState({schema_version: 1, status: 'closed', reconciled_at: Math.floor(Date.now() / 1000)});
    } else {
      writeState({schema_version: 1, status: 'open', token: crypto.randomBytes(32).toString('hex')});
    }
  } finally {
    await client.close();
  }
})().catch(error => {
  process.stderr.write(`first-admin reconciliation failed: ${error.message}\n`);
  process.exit(1);
});
