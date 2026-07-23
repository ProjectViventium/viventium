#!/usr/bin/env node
/* Verify that the exact bundled default agent exists in the Native MongoDB. */
'use strict';

const fs = require('fs');
const path = require('path');
const {createRequire} = require('module');

async function run() {
  const [librechatRoot, mongoUri, bundlePath, adminUserId, baselinePath] = process.argv.slice(2);
  if (
    !librechatRoot ||
    !mongoUri ||
    !bundlePath ||
    !/^[a-f0-9]{24}$/i.test(adminUserId || '') ||
    !path.isAbsolute(baselinePath || '')
  ) {
    throw new Error('Native default-agent verification arguments are incomplete');
  }
  const requireFromLibreChat = createRequire(path.join(librechatRoot, 'package.json'));
  const {MongoClient, ObjectId} = requireFromLibreChat('mongodb');
  const yaml = requireFromLibreChat('js-yaml');
  const bundle = yaml.load(fs.readFileSync(bundlePath, 'utf8'), {schema: yaml.JSON_SCHEMA});
  const expectedAgents = [bundle?.mainAgent, ...(bundle?.backgroundAgents || [])]
    .filter(agent => agent && !agent.missing)
    .map(agent => String(agent.id || ''))
    .filter(Boolean);
  const agentId = String(bundle?.meta?.mainAgentId || bundle?.mainAgent?.id || '');
  if (!agentId || expectedAgents.length === 0 || new Set(expectedAgents).size !== expectedAgents.length) {
    throw new Error('Native default-agent bundle has no main agent ID');
  }
  const baselineMetadata = fs.lstatSync(baselinePath);
  if (
    !baselineMetadata.isFile() ||
    baselineMetadata.isSymbolicLink() ||
    baselineMetadata.uid !== process.getuid() ||
    (baselineMetadata.mode & 0o777) !== 0o600
  ) {
    throw new Error('Native managed agent baseline is unsafe');
  }
  const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  if (
    baseline?.schema_version !== 1 ||
    !/^[a-f0-9]{64}$/.test(String(baseline.bundle_sha256 || '')) ||
    expectedAgents.some(id => !baseline.agents?.[id]?.fields)
  ) {
    throw new Error('Native managed agent baseline does not cover the shipped bundle');
  }
  const client = new MongoClient(mongoUri, {serverSelectionTimeoutMS: 5000});
  try {
    await client.connect();
    const db = client.db();
    const administrator = await db.collection('users').findOne(
      {
        _id: new ObjectId(adminUserId),
        role: 'ADMIN',
        email: {$ne: 'viventium-system@example.com'},
      },
      {projection: {_id: 1, email: 1}},
    );
    if (!administrator || String(administrator._id) !== adminUserId) {
      throw new Error(
        'Native built-in owner is not the verified local administrator. Restore or promote the recorded administrator from the latest Viventium backup, then restart; protected owner state was not changed.',
      );
    }
    const agents = await db
      .collection('agents')
      .find({id: {$in: expectedAgents}}, {projection: {_id: 1, id: 1, author: 1}})
      .toArray();
    if (agents.length !== expectedAgents.length) {
      throw new Error(`Native built-in agent count is ${agents.length}, expected ${expectedAgents.length}`);
    }
    for (const agent of agents) {
      if (String(agent.author) !== adminUserId) {
        throw new Error(`Native built-in agent ${agent.id} is not owned by the verified administrator`);
      }
    }
    const ownerRoles = await db
      .collection('accessroles')
      .find({accessRoleId: {$in: ['agent_owner', 'remoteAgent_owner']}}, {projection: {_id: 1, resourceType: 1}})
      .toArray();
    const ownerRoleByType = new Map(ownerRoles.map(role => [role.resourceType, String(role._id)]));
    if (!ownerRoleByType.has('agent') || !ownerRoleByType.has('remoteAgent')) {
      throw new Error('Native built-in owner roles are unavailable');
    }
    const aclEntries = await db
      .collection('aclentries')
      .find({
        principalType: 'user',
        principalId: administrator._id,
        resourceId: {$in: agents.map(agent => agent._id)},
        resourceType: {$in: ['agent', 'remoteAgent']},
      })
      .toArray();
    for (const agent of agents) {
      for (const resourceType of ['agent', 'remoteAgent']) {
        const valid = aclEntries.some(entry =>
          String(entry.resourceId) === String(agent._id) &&
          entry.resourceType === resourceType &&
          String(entry.roleId) === ownerRoleByType.get(resourceType),
        );
        if (!valid) {
          throw new Error(`Native built-in agent ${agent.id} lacks administrator ${resourceType} ownership`);
        }
      }
    }
    process.stdout.write(`${JSON.stringify({
      agent_id: agentId,
      count: agents.length,
      owner: adminUserId,
      managed_bundle_sha256: baseline.bundle_sha256,
      preserved_user_field_count: Array.isArray(baseline.unresolved_user_fields)
        ? baseline.unresolved_user_fields.length
        : 0,
      status: 'ok',
    })}\n`);
  } finally {
    await client.close();
  }
}

run().catch(error => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
