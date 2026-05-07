import assert from 'node:assert/strict';
import { dedupeMessagesById } from '../../viventium_v0_4/agent-starter-react/lib/session-message-utils.ts';

const sameIdMessages = [
  { id: 'stream-1', message: 'first copy' },
  { id: 'stream-1', message: 'duplicate copy' },
  { id: 'stream-2', message: 'next stream' },
];
assert.deepEqual(
  dedupeMessagesById(sameIdMessages).map((message) => message.message),
  ['first copy', 'next stream']
);

const repeatedHumanPhraseMessages = [
  { id: 'stream-a', message: 'okay' },
  { id: 'stream-b', message: 'okay' },
];
assert.deepEqual(
  dedupeMessagesById(repeatedHumanPhraseMessages).map((message) => message.id),
  ['stream-a', 'stream-b']
);

const sameTranscriptionSegmentMessages = [
  {
    id: 'stream-a',
    type: 'userTranscript',
    message: 'partial phrase',
    from: { identity: 'speaker-1' },
    streamInfo: { attributes: { 'lk.segment_id': 'segment-1' } },
  },
  {
    id: 'stream-b',
    type: 'userTranscript',
    message: 'final phrase',
    from: { identity: 'speaker-1' },
    streamInfo: { attributes: { 'lk.segment_id': 'segment-1' } },
  },
];
assert.deepEqual(
  dedupeMessagesById(sameTranscriptionSegmentMessages).map((message) => message.message),
  ['final phrase']
);

const sameSegmentDifferentSpeakerMessages = [
  {
    id: 'stream-a',
    type: 'userTranscript',
    message: 'speaker one',
    from: { identity: 'speaker-1' },
    streamInfo: { attributes: { 'lk.segment_id': 'shared-segment-id' } },
  },
  {
    id: 'stream-b',
    type: 'userTranscript',
    message: 'speaker two',
    from: { identity: 'speaker-2' },
    streamInfo: { attributes: { 'lk.segment_id': 'shared-segment-id' } },
  },
];
assert.deepEqual(
  dedupeMessagesById(sameSegmentDifferentSpeakerMessages).map((message) => message.message),
  ['speaker one', 'speaker two']
);

console.log('session-message-utils tests passed');
