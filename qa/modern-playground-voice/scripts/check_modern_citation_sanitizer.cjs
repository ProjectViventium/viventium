#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const repoRoot = path.resolve(__dirname, '../../..');
const appRoot = path.join(repoRoot, 'viventium_v0_4', 'agent-starter-react');
const ts = require(path.join(appRoot, 'node_modules', 'typescript'));

const source = fs.readFileSync(path.join(appRoot, 'lib', 'citations.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2019,
  },
}).outputText;

const mod = { exports: {} };
vm.runInNewContext(compiled, { module: mod, exports: mod.exports, require, console });

const { stripCitations } = mod.exports;
if (typeof stripCitations !== 'function') {
  throw new Error('stripCitations export not found');
}

const stripCases = [
  ['split bare id', 'Persian. turn0search4 If you mean coolest', 'Persian. If you mean coolest'],
  ['bracketed source shell', 'Answer 【turn0search4†source】 continues', 'Answer continues'],
  ['concatenated ids', 'Answer turn0search1turn0news2turn0file3 done', 'Answer done'],
  ['numeric punctuation', 'Answer [1]. Next [23], done', 'Answer. Next, done'],
  ['escaped marker citation', 'Hello \\ue202turn0search0 world', 'Hello world'],
  ['split source tail', 'Answer †source】 continues', 'Answer continues'],
  ['orphan opening bracket', 'Answer 【 next', 'Answer next'],
  ['orphan closing bracket', 'Answer 】 next', 'Answer next'],
];

const unchangedCases = [
  'Saturn5rocket2 launches today',
  'The return0value1 was set',
  'An overturn3case4 ruling',
  'A nocturne is playing',
  'Take turn 4 now',
  'Use 【important】 note',
];

for (const [name, input, expected] of stripCases) {
  const actual = stripCitations(input).trim();
  if (actual !== expected) {
    throw new Error(`${name} failed: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

for (const input of unchangedCases) {
  const actual = stripCitations(input);
  if (actual !== input) {
    throw new Error(`unchanged case failed: expected ${JSON.stringify(input)}, got ${JSON.stringify(actual)}`);
  }
}

process.stdout.write(
  JSON.stringify(
    {
      ok: true,
      stripCases: stripCases.length,
      unchangedCases: unchangedCases.length,
    },
    null,
    2,
  ) + '\n',
);
