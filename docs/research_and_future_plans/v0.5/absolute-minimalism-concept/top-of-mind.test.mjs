import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('./top-of-mind.js', import.meta.url), 'utf8');
const context = { window: {} };
vm.runInNewContext(source, context);

const {
  TOP_OF_MIND_ITEMS,
  formatTopOfMindLabel,
  mountTopOfMind,
  nextTopOfMindIndex,
} = context.window.ViventiumTopOfMind;

test('keeps priorities, thoughts, and updates in the visible note rotation', () => {
  const kinds = new Set(TOP_OF_MIND_ITEMS.map(({ kind }) => kind));

  assert.equal(TOP_OF_MIND_ITEMS.length, 5);
  assert.ok(kinds.has('Priority'));
  assert.ok(kinds.has('Thought'));
  assert.ok(kinds.has('Update'));
});

test('moves forward and backward through the note stack without dead ends', () => {
  assert.equal(nextTopOfMindIndex(0, 5, 1), 1);
  assert.equal(nextTopOfMindIndex(4, 5, 1), 0);
  assert.equal(nextTopOfMindIndex(0, 5, -1), 4);
});

test('gives every note a complete accessible label', () => {
  const label = formatTopOfMindLabel(TOP_OF_MIND_ITEMS[0], 0, TOP_OF_MIND_ITEMS.length);

  assert.match(label, /Priority/);
  assert.match(label, /1 of 5/);
  assert.match(label, /Show next note/);
});

test('exposes one reusable Top of mind controller', () => {
  assert.equal(typeof mountTopOfMind, 'function');
});

test('uses a synthetic public-safe identity in the public concept', () => {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');

  assert.match(html, />Example User</);
  assert.match(html, />user@example\.com</);
  assert.match(html, /account-avatar[^>]*>EU</);
  assert.equal((html.match(/>EU</g) || []).length, 2);
});

test('keeps automatic note turns out of the conversation live region', () => {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');

  assert.match(html, /class="top-of-mind"[\s\S]*?aria-live="off"/);
});

test('keeps the breathing animation alive after a card turn', () => {
  assert.doesNotMatch(source, /incoming\.getAnimations\(\)/);
  assert.match(source, /incomingAnimation\.cancel\(\)/);
});

test('lets an explicit Resume command override temporary hover and focus holds', () => {
  assert.match(source, /if \(autoPlaying\) \{[\s\S]*?holds\.delete\('focus'\);[\s\S]*?holds\.delete\('pointer'\);/);
});
