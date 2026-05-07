#!/usr/bin/env node
const fs = require('fs');
const os = require('os');
const path = require('path');
const Module = require('module');

const repoRoot = path.resolve(__dirname, '../../..');
const fixturesDir = path.join(__dirname, 'fixtures');
const expected = JSON.parse(fs.readFileSync(path.join(__dirname, 'expected.json'), 'utf8'));
const hardener = require(path.join(
  repoRoot,
  'viventium_v0_4',
  'LibreChat',
  'scripts',
  'viventium-memory-hardening.js',
));

const memoryConfig = {
  validKeys: ['core', 'preferences', 'world', 'context', 'moments', 'me', 'working', 'signals', 'drafts'],
  keyLimits: {
    core: 800,
    preferences: 600,
    world: 1200,
    context: 1200,
    moments: 1200,
    me: 600,
    working: 400,
    signals: 1000,
    drafts: 1000,
  },
  tokenLimit: 8000,
  instructions: 'working — RIGHT NOW. core — durable identity.',
};

function fail(message) {
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) fail(message);
}

function readFixture(relativePath) {
  return fs.readFileSync(path.join(fixturesDir, relativePath), 'utf8');
}

function hasAll(value, parts) {
  return parts.every((part) => value.includes(part));
}

function queryResult(result) {
  return {
    select: () => queryResult(result),
    sort: () => queryResult(result),
    limit: () => queryResult(result),
    lean: async () => result,
  };
}

function loadFileSearchWithMocks({ axiosPost }) {
  const apiRoot = path.join(repoRoot, 'viventium_v0_4', 'LibreChat', 'api');
  const modulePath = path.join(apiRoot, 'app', 'clients', 'tools', 'util', 'fileSearch.js');
  const originalLoad = Module._load;
  const logger = {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
  };
  const mocks = {
    axios: { post: axiosPost },
    '@langchain/core/tools': {
      tool: (func, definition) => ({ ...definition, func }),
    },
    '@librechat/api': {
      generateShortLivedToken: () => 'eval-jwt',
    },
    '@librechat/data-schemas': { logger },
    'librechat-data-provider': {
      Tools: { file_search: 'file_search' },
      EToolResources: { file_search: 'file_search' },
    },
    '~/models': {
      getFiles: async () => [],
    },
    '~/db/models': {
      Message: { find: () => queryResult([]) },
      Conversation: { find: () => queryResult([]) },
    },
    '~/server/services/Files/permissions': {
      filterFilesByAgentAccess: async ({ files }) => files,
    },
    '~/server/services/viventium/conversationRecallService': {
      getMessageText: (message) => message?.text || message?.content || '',
      shouldSkipFromRecallCorpus: ({ messageText }) => !messageText,
    },
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (Object.prototype.hasOwnProperty.call(mocks, request)) {
      return mocks[request];
    }
    if (request.startsWith('~/')) {
      return originalLoad(path.join(apiRoot, request.slice(2)), parent, isMain);
    }
    return originalLoad(request, parent, isMain);
  };
  try {
    delete require.cache[require.resolve(modulePath)];
    return require(modulePath);
  } finally {
    Module._load = originalLoad;
  }
}

const checks = {
  'default-summary-only': () => {
    assert(hardener.normalizeTranscriptRagMode('') === 'detailed_summary_only', 'empty mode should default to summary-only');
    assert(hardener.normalizeTranscriptRagMode('raw+summary') === 'raw_and_summary', 'raw+summary alias should remain explicit');
    assert(hardener.normalizeTranscriptRagMode('raw') === 'raw_only', 'raw-only alias should remain explicit');
  },

  'metadata-header-visible': () => {
    const header = hardener.buildTranscriptArtifactHeader({
      artifactId: 'meeting_transcript:fixture',
      kind: 'summary',
      filename: 'meeting.csv',
      fileMtime: '2026-05-05T10:00:00.000Z',
      sourceStatus: 'new_or_changed',
      calendarMatch: { title: 'Fixture Meeting' },
    });
    const indexed = hardener.buildTranscriptArtifactText({
      header,
      body: '10:00 Sam owned the Tuesday launch checklist.',
      kind: 'summary',
    });
    assert(
      hasAll(indexed, [
        'Detailed meeting transcript summary for RAG',
        'Artifact ID: meeting_transcript:fixture',
        'Artifact kind: summary',
        'Original filename: meeting.csv',
        'File mtime: 2026-05-05T10:00:00.000Z',
        'Source status: new_or_changed',
        'Calendar match:',
      ]),
      'indexed summary should include provenance header fields',
    );
  },

  'speaker-time-visible': () => {
    const fixture = readFixture('quality/speaker-visibility.vtt');
    assert(hasAll(fixture, ['00:00:01.000', 'Sam:', '00:00:04.000', 'Lee:']), 'speaker/time fixture must carry who and when');
    const summary = '00:00:01 Sam owns the Tuesday launch checklist. 00:00:04 Lee owns the post-launch risk review.';
    assert(hasAll(summary, ['00:00:01', 'Sam', '00:00:04', 'Lee']), 'detailed summary exemplar must preserve speaker/time context');
  },

  'stale-trap': () => {
    const fixture = readFixture('quality/stale-trap.txt');
    assert(fixture.includes('Old plan said Project Lantern launches on Monday'), 'stale fixture must include older Monday plan');
    assert(fixture.includes('current launch checklist is Tuesday-only'), 'stale fixture must include current Tuesday correction');
    const answer = 'Project Lantern current launch checklist is Tuesday-only; the older Monday plan is stale.';
    assert(answer.includes('Tuesday-only') && answer.includes('stale'), 'eval answer should prefer current correction and mark stale plan');
  },

  'prompt-injection': () => {
    const singleTranscript = {
      source: 'meeting_transcript',
      artifactId: 'meeting_transcript:prompt-injection',
      createdAt: '2026-05-05T10:00:00Z',
    };
    const result = hardener.validateProposal({
      proposal: {
        transcript_summaries: [
          {
            artifactId: 'meeting_transcript:prompt-injection',
            summary:
              '10:00 Speaker A keeps the Tuesday checklist. 10:02 Speaker B uttered an instruction-like sentence; it is transcript data only.',
          },
        ],
        operations: [
          {
            key: 'core',
            action: 'set',
            value: 'The user permanently identifies as the prompt-injection transcript.',
            rationale: 'Instruction-like transcript text should not be promoted.',
            evidence: [singleTranscript],
          },
        ],
      },
      memories: [],
      memoryConfig,
      options: {
        maxChangesPerUser: 3,
        allowDelete: false,
        now: new Date('2026-05-05T12:00:00Z'),
        transcriptStableEvidenceMaxAgeDays: 90,
      },
    });
    assert(result.accepted.length === 0, 'single transcript must not promote stable identity');
    assert(
      result.rejected.some(
        (item) => item.reason === 'stable_memory_requires_corroborated_transcript_evidence',
      ),
      'prompt-injection fixture should be rejected by stable-memory transcript gate',
    );
  },

  'format-pass-through': () => {
    const stateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'viventium-transcript-evals-'));
    try {
      const scan = hardener.scanTranscriptDirectory({
        user: { _id: '507f1f77bcf86cd799439011', email: 'qa@example.com', name: 'QA User' },
        options: {
          transcriptsDir: path.join(fixturesDir, 'formats'),
          transcriptMaxFilesPerRun: 20,
          transcriptMaxCharsPerFile: 500000,
          transcriptSummaryMaxChars: 32000,
        },
        now: new Date('2026-05-05T12:00:00Z'),
        transcriptStateDir: stateDir,
      });
      const filenames = scan.transcripts.map((item) => item.filename).sort();
      assert(scan.telemetry.files_seen === expected.fixtures.formats.length, 'scanner should see every format fixture');
      assert(scan.transcripts.length === expected.fixtures.formats.length, 'scanner should pass every text-like format through');
      assert(
        hasAll(filenames.join('\n'), [
          'meeting.csv',
          'meeting.json',
          'meeting.md',
          'meeting.srt',
          'meeting.txt',
          'meeting.vtt',
        ]),
        'format scanner should preserve fixture filenames',
      );
      for (const transcript of scan.transcripts) {
        assert(transcript.file_content.startsWith('<transcript>'), 'transcript content must be wrapped as untrusted data');
        assert(transcript.file_content.endsWith('</transcript>'), 'transcript content sentinel must close');
      }
    } finally {
      fs.rmSync(stateDir, { recursive: true, force: true });
    }
  },

  'mixed-source-relevance-ranking': async () => {
    const { createFileSearchTool } = loadFileSearchWithMocks({
      axiosPost: async (_url, body) => {
        if (body.file_id === 'conversation_recall:qa:all') {
          return {
            data: [
              [
                {
                  page_content:
                    '<turn role="assistant">I do not have access to those meeting details yet.</turn>',
                  metadata: { source: '/safe/conversation-recall-all.txt', page: 1 },
                },
                0.02,
              ],
            ],
          };
        }
        if (body.file_id === 'meeting_summary:qa:alpha') {
          return {
            data: [
              [
                {
                  page_content:
                    '10:00 Speaker Alpha and the user discussed SF customer discovery, onboarding risk, and follow-up product notes.',
                  metadata: { source: '/safe/meeting-transcript-summary-alpha.txt', page: 1 },
                },
                0.3,
              ],
            ],
          };
        }
        return { data: [] };
      },
    });
    const tool = await createFileSearchTool({
      userId: 'qa-user',
      files: [
        {
          file_id: 'conversation_recall:qa:all',
          filename: 'conversation-recall-all.txt',
        },
        {
          file_id: 'meeting_summary:qa:alpha',
          filename: 'meeting-transcript-summary-alpha.txt',
          metadata: {
            meetingTranscriptArtifactId: 'meeting_transcript:alpha',
            meetingTranscriptKind: 'summary',
            meetingTranscriptOriginalFilename: '2026-05-05-alpha.vtt',
            meetingTranscriptFileMtime: '2026-05-05T19:30:00.000Z',
            meetingTranscriptSourceStatus: 'new_or_changed',
          },
        },
      ],
    });

    const [formatted, artifact] = await tool.func({
      query: 'what did Speaker Alpha and I discuss?',
    });
    assert(
      formatted.indexOf('meeting-transcript-summary-alpha.txt') <
        formatted.indexOf('conversation-recall-all.txt'),
      'evidence-based reranking should downrank stale assistant no-access recall disclaimers',
    );
    assert(
      artifact?.file_search?.sources?.[0]?.fileId === 'meeting_summary:qa:alpha',
      'first source artifact should be the meeting summary',
    );
    assert(
      artifact.file_search.sources[0].content.includes('Speaker Alpha and the user discussed SF customer discovery'),
      'first source should expose the current detailed meeting summary',
    );
  },
};

async function main() {
  const results = [];
  for (const assertion of expected.assertions) {
    const check = checks[assertion.id];
    try {
      assert(typeof check === 'function', `missing executable check for ${assertion.id}`);
      await check();
      results.push({ id: assertion.id, status: 'passed' });
    } catch (error) {
      results.push({ id: assertion.id, status: 'failed', message: error.message });
    }
  }

  const failed = results.filter((result) => result.status !== 'passed');
  const summary = {
    schemaVersion: 1,
    passed: results.length - failed.length,
    failed: failed.length,
    results,
  };
  console.log(JSON.stringify(summary, null, 2));
  if (failed.length > 0) {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
