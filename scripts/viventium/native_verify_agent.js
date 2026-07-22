#!/usr/bin/env node
/* Verify that the exact bundled default agent exists in the Native MongoDB. */
'use strict';

const fs = require('fs');
const path = require('path');
const {createRequire} = require('module');

async function run() {
  const [librechatRoot, mongoUri, bundlePath] = process.argv.slice(2);
  if (!librechatRoot || !mongoUri || !bundlePath) {
    throw new Error('Native default-agent verification arguments are incomplete');
  }
  const requireFromLibreChat = createRequire(path.join(librechatRoot, 'package.json'));
  const {MongoClient} = requireFromLibreChat('mongodb');
  const yaml = requireFromLibreChat('js-yaml');
  const bundle = yaml.load(fs.readFileSync(bundlePath, 'utf8'), {schema: yaml.JSON_SCHEMA});
  const agentId = String(bundle?.meta?.mainAgentId || bundle?.mainAgent?.id || '');
  if (!agentId) {
    throw new Error('Native default-agent bundle has no main agent ID');
  }
  const client = new MongoClient(mongoUri, {serverSelectionTimeoutMS: 5000});
  try {
    await client.connect();
    const count = await client.db().collection('agents').countDocuments({id: agentId}, {limit: 2});
    if (count !== 1) {
      throw new Error(`Native default agent count is ${count}, expected 1`);
    }
    process.stdout.write(`${JSON.stringify({agent_id: agentId, count, status: 'ok'})}\n`);
  } finally {
    await client.close();
  }
}

run().catch(error => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
