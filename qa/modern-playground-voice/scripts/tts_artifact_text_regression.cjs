#!/usr/bin/env node
'use strict';

const assert = require('assert');
const {
  ARTIFACT_CONDITIONS,
  ARTIFACT_CONTRACT_VERSION,
  DEFAULT_TTS_FORBIDDEN_ARTIFACT_KEYS,
  SYNTHETIC_FORBIDDEN_ARTIFACT_CASES,
  artifactCounts,
  stripProtectedTextRanges,
  sumForbiddenArtifacts,
} = require('./voice_artifact_contract.cjs');

const protectedExamples = [
  'The assistant quoted: "no no no no no no" and then explained why.',
  'The assistant quoted: “go go go go go go” and then explained why.',
  ['The assistant quoted:', '> wait wait wait wait wait wait', 'Then summarized.'].join('\n'),
  'The inline sample was `echo echo echo echo`, not speech corruption.',
  ['The fixture was:', '```', 'ping ping ping ping', '```'].join('\n'),
];

for (const text of protectedExamples) {
  assert.strictEqual(
    artifactCounts(text).adjacentDuplicateWord,
    0,
    `protected repetition should not count as adjacent duplicate: ${stripProtectedTextRanges(text)}`,
  );
}

for (const { key, text } of SYNTHETIC_FORBIDDEN_ARTIFACT_CASES) {
  assert.strictEqual(
    artifactCounts(text)[key],
    1,
    `expected ${key} to be detected for synthetic wildcard: ${text}`,
  );
}

assert.strictEqual(
  artifactCounts('hahaha!').adjacentDuplicateWord,
  0,
  'legitimate repeated incremental output should not count as duplicate corruption',
);

for (const text of ['I had had enough.', 'The data is is consistent.', 'That that exists is odd.']) {
  assert.strictEqual(
    artifactCounts(text).adjacentDuplicateWord,
    0,
    `legitimate adjacent duplicate should not count as corruption: ${text}`,
  );
}

assert.strictEqual(
  artifactCounts('Five times three is 5 * 3.').markdownEmphasis,
  0,
  'math asterisk should not count as markdown emphasis',
);

assert.strictEqual(
  artifactCounts('The marker {NTA} should never be visible.').internalNoResponseMarker,
  1,
  'internal no-response marker should still count even near prose',
);

assert.strictEqual(
  sumForbiddenArtifacts(artifactCounts(''), DEFAULT_TTS_FORBIDDEN_ARTIFACT_KEYS),
  0,
  'empty text should have zero artifact count',
);

const conditionKeys = new Set(ARTIFACT_CONDITIONS.map((condition) => condition.key));
for (const key of DEFAULT_TTS_FORBIDDEN_ARTIFACT_KEYS) {
  assert.ok(conditionKeys.has(key), `forbidden key must be documented in contract: ${key}`);
}

process.stdout.write(
  `tts artifact text regression PASS contract=${ARTIFACT_CONTRACT_VERSION} cases=${SYNTHETIC_FORBIDDEN_ARTIFACT_CASES.length}\n`,
);
