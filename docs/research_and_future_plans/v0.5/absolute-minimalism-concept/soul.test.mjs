import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('./soul.js', import.meta.url), 'utf8');
const context = { window: {} };
vm.runInNewContext(source, context);

const {
  SOUL_MODES,
  createSoulPath,
  deriveSoulMetrics,
  mountSoul,
  resolveSoulMode,
} = context.window.ViventiumSoul;

const low = [
  ['energy', 0],
  ['mood', 0],
  ['drive', 0],
  ['curiosity', 0],
  ['vigilance', 0],
  ['care', 0],
  ['connection', 0],
  ['openness', 0],
  ['play', 0],
].map(([id, current]) => ({ id, current, enabled: true }));

const high = low.map((band) => ({ ...band, current: 100 }));

test('maps the nine feeling bands to distinct soul motion qualities', () => {
  const quiet = deriveSoulMetrics(low);
  const vivid = deriveSoulMetrics(high);

  assert.ok(vivid.breathHz > quiet.breathHz, 'energy must quicken the breath');
  assert.ok(vivid.breathDepth > quiet.breathDepth, 'energy must deepen the breath');
  assert.ok(vivid.aura > quiet.aura, 'care must strengthen the aura');
  assert.ok(vivid.auraSpread > quiet.auraSpread, 'openness must widen the aura');
  assert.ok(vivid.reach > quiet.reach, 'curiosity must extend the form');
  assert.ok(vivid.edgeTension > quiet.edgeTension, 'vigilance must tighten the edge');
  assert.ok(vivid.irregularity > quiet.irregularity, 'play must loosen the silhouette');
});

test('system state takes precedence over expressive motion', () => {
  assert.equal(resolveSoulMode({ power: false, paused: false }), 'off');
  assert.equal(resolveSoulMode({ power: true, paused: true, replyPending: true }), 'paused');
  assert.equal(resolveSoulMode({ power: true, paused: false, replyPending: true }), 'thinking');
  assert.equal(resolveSoulMode({ power: true, paused: false, callActive: true, callMuted: false }), 'attending');
  assert.equal(resolveSoulMode({ power: true, paused: false, callActive: true, callMuted: true }), 'resting');
});

test('defines every visible lifecycle state', () => {
  assert.deepEqual(
    Array.from(SOUL_MODES),
    ['resting', 'attending', 'thinking', 'reacting', 'settling', 'paused', 'off'],
  );
});

test('exposes one reusable renderer for compact and close-up souls', () => {
  assert.equal(typeof mountSoul, 'function');
});

test('creates a closed organic path that responds to state and feeling', () => {
  const quiet = deriveSoulMetrics(low);
  const vivid = deriveSoulMetrics(high);
  const restingPath = createSoulPath(quiet, 1200, 'resting', 0.4);
  const reactingPath = createSoulPath(vivid, 1200, 'reacting', 0.4);

  assert.match(restingPath, /^M\s/);
  assert.match(restingPath, /Z$/);
  assert.notEqual(restingPath, reactingPath);
  assert.equal(restingPath.includes('NaN'), false);
});
