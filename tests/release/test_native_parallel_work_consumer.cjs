const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const repoRoot = path.resolve(__dirname, '../..');
const librechatRoot = path.join(repoRoot, 'viventium_v0_4/LibreChat');
const ts = require(path.join(librechatRoot, 'node_modules/typescript'));
const source = fs.readFileSync(path.join(librechatRoot, 'packages/api/src/glasshive/orchestrationMode.ts'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const proof = { contractVersion: 1, localQa: true, candidateDigest: `sha256:${'a'.repeat(64)}`,
  installedArtifactDigest: `sha256:${'b'.repeat(64)}`, runtimeOwnerBindingHash: `sha256:${'c'.repeat(64)}` };

function fixture({ native = true, operational = true, response = proof, duringQuery, text = code, manifest = {} } = {}) {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'native-parallel-consumer-')));
  const root = path.join(base, 'release');
  const support = path.join(base, 'support');
  for (const dir of ['runtime/node/bin']) fs.mkdirSync(path.join(root, dir), { recursive: true });
  for (const dir of ['state', 'runtime']) fs.mkdirSync(path.join(support, dir), { recursive: true });
  const executable = path.join(root, 'runtime/node/bin/node');
  fs.writeFileSync(executable, 'synthetic selected runtime');
  fs.writeFileSync(path.join(root, '.viventium-manifest.json'), JSON.stringify(manifest), { mode: 0o444 });
  fs.writeFileSync(path.join(support, 'state/native-runtime.json'), JSON.stringify({ release_root: root }), { mode: 0o600 });
  fs.writeFileSync(path.join(support, 'state/native-first-admin.json'), '{}', { mode: 0o600 });
  for (const service of ['librechat', 'glasshive', 'glasshive-mcp', 'redis']) {
    fs.writeFileSync(path.join(support, 'runtime', `${service}.process.json`),
      JSON.stringify({ release_root: root, pid: process.pid }), { mode: 0o600 });
  }
  let calls = 0;
  const exports = {};
  const childProcess = { execFileSync() { throw Error('unexpected source process'); },
    execFile(binary, argv, options, callback) {
      calls++;
      assert.equal(binary, path.join(root, 'runtime/python/bin/python3'));
      assert.equal(argv[4], 'parallel-work-identity');
      assert.equal(options.env.PATH, '/usr/bin:/bin');
      duringQuery?.({ support, root });
      callback(null, JSON.stringify(response));
    } };
  const env = { NODE_ENV: 'test', HOME: base };
  if (native) Object.assign(env, { VIVENTIUM_INSTALL_MODE: 'native', VIVENTIUM_NATIVE_RELEASE_ROOT: root, VIVENTIUM_APP_SUPPORT_DIR: support });
  const testProcess = { env, execPath: executable, getuid: () => process.getuid(), kill: process.kill.bind(process) };
  vm.runInNewContext(text, { exports, require: (name) => name === 'child_process' ? childProcess : require(name),
    process: testProcess, Buffer, setTimeout, clearTimeout, setInterval, Date, __filename: __filename });
  exports.configureOrchestrationMode({ orchestrationReadinessSnapshot: () => ({ available: operational }),
    orchestrationDeploymentReadinessSnapshot: () => ({ available: operational }) });
  return { api: exports, calls: () => calls, support, root, cleanup: () => fs.rmSync(base, { recursive: true }) };
}

test('native local QA preserves operational checks, emits trace, and reuses current proof', async () => {
  const f = fixture();
  try {
    assert.equal(await f.api.parallelWorkDeploymentAvailableAsync(), true);
    assert.equal(await f.api.parallelWorkDeploymentAvailableAsync(), true);
    assert.equal(f.calls(), 1);
    const gate = await f.api.parallelWorkReleaseGateSnapshotAsync();
    assert.equal(gate.releaseReady, false);
    assert.equal(gate.label, 'PRE-GATE / NOT READY');
    assert.equal(f.api.orchestrationRuntimeTraceBinding().candidateDigest, proof.candidateDigest);
  } finally { f.cleanup(); }
});

test('stable native provenance is not release acceptance', async () => {
  const f = fixture({ response: { ...proof, localQa: false } });
  try {
    assert.equal(await f.api.parallelWorkDeploymentAvailableAsync(), false);
    assert.equal((await f.api.parallelWorkReleaseGateSnapshotAsync()).blockers[0], 'native_release_evidence_missing');
  } finally { f.cleanup(); }
});

test('unready native durable transport cannot be exposed by a local QA manifest', async () => {
  const f = fixture({ operational: false });
  try { assert.equal(await f.api.parallelWorkDeploymentAvailableAsync(), false); assert.equal(f.calls(), 0); }
  finally { f.cleanup(); }
});

for (const change of ['other_install', 'unsafe_owner', 'dead_service', 'during_query']) {
  test(`native rejects ${change}`, async () => {
    const mutate = ({ support, root }) => {
      const file = path.join(support, 'runtime/redis.process.json');
      if (change === 'unsafe_owner') fs.chmodSync(file, 0o644);
      else fs.writeFileSync(file, JSON.stringify({ release_root: change === 'other_install' ? `${root}-other` : root,
        pid: change === 'dead_service' ? 2147483647 : process.pid, changed: true }));
    };
    const f = fixture({ duringQuery: change === 'during_query' ? mutate : undefined });
    try { if (change !== 'during_query') mutate(f); assert.equal(await f.api.parallelWorkDeploymentAvailableAsync(), false); }
    finally { f.cleanup(); }
  });
}

test('source missing-claim behavior stays unchanged', async () => {
  const after = fixture({ native: false });
  try {
    assert.equal(await after.api.parallelWorkDeploymentAvailableAsync(), false);
    assert.equal(after.api.parallelWorkReleaseGateSnapshot().blockers.join(','), 'release_snapshot_unavailable');
    assert.equal(after.calls(), 0);
  } finally { after.cleanup(); }
});


test('full dependency inventory reaches the installed identity verifier', async () => {
  const manifest = { files: Array.from({ length: 16000 }, (_, index) => ({
    path: `app/node_modules/package-${index}/runtime.js`, sha256: '0'.repeat(64), size: 1, mode: 420,
  })) };
  assert.ok(Buffer.byteLength(JSON.stringify(manifest)) > 2 * 1024 * 1024);
  const f = fixture({ manifest });
  try {
    assert.equal(await f.api.parallelWorkDeploymentAvailableAsync(), true);
    assert.equal(f.calls(), 1);
  } finally { f.cleanup(); }
});

test('oversized installed manifest is rejected before the identity query', async () => {
  const f = fixture();
  try {
    const manifest = path.join(f.root, '.viventium-manifest.json');
    fs.chmodSync(manifest, 0o644);
    fs.truncateSync(manifest, 64 * 1024 * 1024 + 1);
    fs.chmodSync(manifest, 0o444);
    assert.equal(await f.api.parallelWorkDeploymentAvailableAsync(), false);
    assert.equal(f.calls(), 0);
  } finally { f.cleanup(); }
});
