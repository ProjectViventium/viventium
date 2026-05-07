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

const firstSeenMsById = new Map([
  ['stream-local-a', 1000],
  ['stream-local-b', 1300],
  ['stream-local-c', 4000],
  ['stream-remote-a', 1100],
  ['stream-chat-a', 1450],
]);

const sameLocalTranscriptAcrossStreams = [
  {
    id: 'stream-local-a',
    type: 'userTranscript',
    message: 'Hello   Mom',
    timestamp: 1000,
    from: { identity: 'local-speaker', isLocal: true },
  },
  {
    id: 'stream-local-b',
    type: 'userTranscript',
    message: 'hello mom',
    timestamp: 1300,
    from: { identity: 'local-speaker', isLocal: true },
  },
];
assert.deepEqual(
  dedupeMessagesById(sameLocalTranscriptAcrossStreams, { firstSeenMsById }).map(
    (message) => message.id
  ),
  ['stream-local-b']
);

const sameLocalTranscriptOutsideWindow = [
  {
    id: 'stream-local-a',
    type: 'userTranscript',
    message: 'hello mom',
    timestamp: 1000,
    from: { identity: 'local-speaker', isLocal: true },
  },
  {
    id: 'stream-local-c',
    type: 'userTranscript',
    message: 'hello mom',
    timestamp: 4000,
    from: { identity: 'local-speaker', isLocal: true },
  },
];
assert.deepEqual(
  dedupeMessagesById(sameLocalTranscriptOutsideWindow, { firstSeenMsById }).map(
    (message) => message.id
  ),
  ['stream-local-a', 'stream-local-c']
);

const sameTextDifferentSpeakerNoSegment = [
  {
    id: 'stream-local-a',
    type: 'userTranscript',
    message: 'hello mom',
    timestamp: 1000,
    from: { identity: 'local-speaker', isLocal: true },
  },
  {
    id: 'stream-remote-a',
    type: 'userTranscript',
    message: 'hello mom',
    timestamp: 1100,
    from: { identity: 'remote-speaker', isLocal: false },
  },
];
assert.deepEqual(
  dedupeMessagesById(sameTextDifferentSpeakerNoSegment, { firstSeenMsById }).map(
    (message) => message.id
  ),
  ['stream-local-a', 'stream-remote-a']
);

const sameLocalTranscriptAndChatEcho = [
  {
    id: 'stream-local-b',
    type: 'userTranscript',
    message: 'same line',
    timestamp: 1300,
    from: { identity: 'local-speaker', isLocal: true },
  },
  {
    id: 'stream-chat-a',
    type: 'chatMessage',
    message: 'same line',
    timestamp: 1450,
    from: { identity: 'local-speaker', isLocal: true },
  },
];
assert.deepEqual(
  dedupeMessagesById(sameLocalTranscriptAndChatEcho, { firstSeenMsById }).map(
    (message) => message.id
  ),
  ['stream-chat-a']
);

console.log('session-message-utils tests passed');
