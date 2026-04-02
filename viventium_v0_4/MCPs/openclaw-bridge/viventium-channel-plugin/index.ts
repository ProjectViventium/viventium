/**
 * VIVENTIUM CHANNEL BRIDGE — OpenClaw Plugin (Gateway v2)
 *
 * Routes incoming channel messages through LibreChat's generic gateway contract:
 * - POST /api/viventium/gateway/chat
 * - GET  /api/viventium/gateway/stream/:streamId
 *
 * Security:
 * - Shared secret: X-VIVENTIUM-GATEWAY-SECRET
 * - HMAC signature headers:
 *   - x-viventium-gateway-timestamp
 *   - x-viventium-gateway-nonce
 *   - x-viventium-gateway-signature
 *
 * Delivery back to channel uses OpenClaw message tool via POST /tools/invoke.
 */

import crypto from 'node:crypto';

interface PluginLogger {
  debug?: (message: string) => void;
  info: (message: string) => void;
  warn: (message: string) => void;
  error: (message: string) => void;
}

interface OpenClawPluginApi {
  id: string;
  name: string;
  config: Record<string, unknown>;
  pluginConfig?: Record<string, unknown>;
  logger: PluginLogger;
  on: (hookName: string, handler: (...args: unknown[]) => void | Promise<void>) => void;
}

interface MessageReceivedEvent {
  from: string;
  content: string;
  timestamp?: number;
  metadata?: Record<string, unknown>;
}

interface MessageContext {
  channelId: string;
  accountId?: string;
  conversationId?: string;
}

interface GatewayStartEvent {
  port: number;
}

type BridgeIdentity = {
  channel: string;
  accountId: string;
  externalUserId: string;
  externalChatId: string;
  externalMessageId: string;
  externalUpdateId: string;
  externalThreadId: string;
  externalUsername: string;
};

type ConversationState = {
  conversationId: string;
  parentMessageId: string;
};

let LIBRECHAT_URL = 'http://localhost:3080';
let GATEWAY_SECRET = '';
let GATEWAY_HMAC_SECRET = '';
let AGENT_ID = '';
let GATEWAY_PORT = 18789;
let GATEWAY_TOKEN = '';
let REQUEST_TIMEOUT_MS = 120000;

const CONVERSATIONS_BY_SCOPE = new Map<string, ConversationState>();
const SCOPE_QUEUES = new Map<string, Promise<void>>();
const LINK_NOTICE_AT = new Map<string, number>();

const LINK_NOTICE_COOLDOWN_MS = 5 * 60 * 1000;

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function normalizeChannel(value: unknown): string {
  return normalizeString(value).toLowerCase();
}

function normalizeAccountId(value: unknown): string {
  const normalized = normalizeString(value);
  return normalized || 'default';
}

function parseIntEnv(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(1000, Math.trunc(value));
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return Math.max(1000, parsed);
    }
  }
  return fallback;
}

function resolveConfig(api: OpenClawPluginApi): void {
  const pc = api.pluginConfig || {};

  LIBRECHAT_URL =
    normalizeString(pc.librechatUrl) ||
    normalizeString(process.env.VIVENTIUM_LIBRECHAT_URL) ||
    normalizeString(process.env.LIBRECHAT_URL) ||
    'http://localhost:3080';

  GATEWAY_SECRET =
    normalizeString(pc.gatewaySecret) || normalizeString(process.env.VIVENTIUM_GATEWAY_SECRET);

  GATEWAY_HMAC_SECRET =
    normalizeString(pc.gatewayHmacSecret) ||
    normalizeString(process.env.VIVENTIUM_GATEWAY_HMAC_SECRET) ||
    GATEWAY_SECRET;

  AGENT_ID =
    normalizeString(pc.agentId) ||
    normalizeString(process.env.VIVENTIUM_AGENT_ID) ||
    normalizeString(process.env.LIBRECHAT_AGENT_ID);

  REQUEST_TIMEOUT_MS = parseIntEnv(
    pc.requestTimeoutMs ?? process.env.VIVENTIUM_GATEWAY_REQUEST_TIMEOUT_MS,
    120000,
  );

  const gw = (api.config?.gateway || {}) as Record<string, unknown>;
  const auth = (gw.auth || {}) as Record<string, unknown>;
  GATEWAY_TOKEN = normalizeString(auth.token) || normalizeString(process.env.OPENCLAW_GATEWAY_TOKEN);
  GATEWAY_PORT =
    (typeof gw.port === 'number' && Number.isFinite(gw.port) ? gw.port : undefined) || 18789;
}

function buildScopeKey(identity: BridgeIdentity): string {
  return [
    identity.channel,
    identity.accountId,
    identity.externalChatId || identity.externalUserId,
    identity.externalThreadId || 'main',
  ].join('|');
}

function makeIdentity(event: MessageReceivedEvent, context: MessageContext): BridgeIdentity {
  const metadata = isObject(event.metadata) ? event.metadata : {};

  const externalUserId = normalizeString(event.from);
  const externalChatId =
    normalizeString(metadata.originatingTo) ||
    normalizeString(metadata.to) ||
    normalizeString(metadata.chatId) ||
    normalizeString(context.conversationId) ||
    externalUserId;

  const externalMessageId =
    normalizeString(metadata.messageId) ||
    normalizeString(metadata.message_id) ||
    normalizeString(metadata.id) ||
    normalizeString(metadata.messageSidFull) ||
    normalizeString(metadata.messageSid) ||
    '';

  const externalUpdateId =
    normalizeString(metadata.updateId) || normalizeString(metadata.update_id) || '';

  const externalThreadId =
    normalizeString(metadata.threadId) ||
    normalizeString(metadata.messageThreadId) ||
    normalizeString(metadata.message_thread_id) ||
    normalizeString(metadata.thread_ts) ||
    '';

  const externalUsername =
    normalizeString(metadata.senderUsername) ||
    normalizeString(metadata.senderName) ||
    normalizeString(metadata.username) ||
    '';

  return {
    channel: normalizeChannel(context.channelId),
    accountId: normalizeAccountId(context.accountId),
    externalUserId,
    externalChatId,
    externalMessageId,
    externalUpdateId,
    externalThreadId,
    externalUsername,
  };
}

function detectInputMode(event: MessageReceivedEvent): string {
  const metadata = isObject(event.metadata) ? event.metadata : {};
  const mediaType =
    normalizeString(metadata.mediaType) ||
    normalizeString(metadata.messageType) ||
    normalizeString(metadata.type) ||
    '';
  const isVoiceFlag = Boolean(metadata.voice === true || metadata.isVoice === true);

  if (isVoiceFlag || /voice|audio|ptt/i.test(mediaType)) {
    return 'voice';
  }
  return 'text';
}

function extractInboundAttachments(event: MessageReceivedEvent): Array<Record<string, unknown>> {
  const metadata = isObject(event.metadata) ? event.metadata : {};
  const rawAttachments: unknown[] = [];

  if (Array.isArray(metadata.attachments)) {
    rawAttachments.push(...metadata.attachments);
  }
  if (Array.isArray(metadata.media)) {
    rawAttachments.push(...metadata.media);
  }

  const attachments: Array<Record<string, unknown>> = [];
  for (const entry of rawAttachments) {
    if (!isObject(entry)) {
      continue;
    }
    const base64 =
      normalizeString(entry.data) ||
      normalizeString(entry.base64) ||
      normalizeString(entry.buffer) ||
      normalizeString(entry.bufferBase64) ||
      '';
    if (!base64) {
      continue;
    }

    attachments.push({
      data: base64,
      filename: normalizeString(entry.filename) || normalizeString(entry.name) || 'attachment',
      mime_type:
        normalizeString(entry.mime_type) ||
        normalizeString(entry.mimeType) ||
        normalizeString(entry.contentType) ||
        'application/octet-stream',
    });
  }

  return attachments;
}

function sha256Hex(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

function hmacHex(secret: string, input: string): string {
  return crypto.createHmac('sha256', secret).update(input).digest('hex');
}

function buildGatewayHeaders(params: {
  method: string;
  path: string;
  body?: Record<string, unknown>;
}): Record<string, string> {
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const nonce = crypto.randomUUID();
  const bodyHash = sha256Hex(JSON.stringify(params.body ?? {}));
  const canonical = [timestamp, nonce, params.method.toUpperCase(), params.path, bodyHash].join('.');
  const signature = hmacHex(GATEWAY_HMAC_SECRET || GATEWAY_SECRET, canonical);

  return {
    'Content-Type': 'application/json',
    'X-VIVENTIUM-GATEWAY-SECRET': GATEWAY_SECRET,
    'x-viventium-gateway-timestamp': timestamp,
    'x-viventium-gateway-nonce': nonce,
    'x-viventium-gateway-signature': signature,
  };
}

async function fetchWithTimeout(url: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function invokeMessageTool(action: string, args: Record<string, unknown>): Promise<void> {
  const url = `http://127.0.0.1:${GATEWAY_PORT}/tools/invoke`;
  const body = {
    tool: 'message',
    args: {
      action,
      ...args,
    },
  };

  const response = await fetchWithTimeout(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${GATEWAY_TOKEN}`,
    },
    body: JSON.stringify(body),
  });

  const text = await response.text().catch(() => '');
  if (!response.ok) {
    throw new Error(`Gateway message action failed (${response.status}): ${text.slice(0, 200)}`);
  }

  if (!text) {
    return;
  }

  try {
    const parsed = JSON.parse(text) as { ok?: boolean; error?: { message?: string } };
    if (parsed?.ok === false) {
      throw new Error(parsed.error?.message || 'Unknown message tool error');
    }
  } catch (err) {
    if (err instanceof SyntaxError) {
      return;
    }
    if (err instanceof Error) {
      throw err;
    }
  }
}

function resolveDeliveryTarget(identity: BridgeIdentity): string {
  return identity.externalChatId || identity.externalUserId;
}

async function sendTextReply(params: {
  identity: BridgeIdentity;
  text: string;
}): Promise<void> {
  const text = params.text.trim();
  if (!text) {
    return;
  }

  const args: Record<string, unknown> = {
    channel: params.identity.channel,
    accountId: params.identity.accountId,
    to: resolveDeliveryTarget(params.identity),
    message: text,
  };

  if (params.identity.externalThreadId) {
    args.threadId = params.identity.externalThreadId;
  }
  if (params.identity.externalMessageId) {
    args.replyTo = params.identity.externalMessageId;
  }

  await invokeMessageTool('send', args);
}

function extractCodeDownloadPath(rawPath: string): string {
  const match = rawPath.match(
    /\/api\/(?:viventium\/gateway\/files\/code\/download|viventium\/telegram\/files\/code\/download|files\/code\/download)\/([A-Za-z0-9_-]{21})\/([A-Za-z0-9_-]{21})/,
  );
  if (!match) {
    return '';
  }
  return `/api/viventium/gateway/files/code/download/${match[1]}/${match[2]}`;
}

function resolveGatewayAttachmentPath(attachment: Record<string, unknown>): string {
  const fileId = normalizeString(attachment.file_id);
  if (fileId) {
    return `/api/viventium/gateway/files/download/${encodeURIComponent(fileId)}`;
  }

  const filePath = normalizeString(attachment.filepath);
  if (!filePath) {
    return '';
  }

  const codePath = extractCodeDownloadPath(filePath);
  if (codePath) {
    return codePath;
  }

  return '';
}

function parseFilenameFromDisposition(disposition: string): string {
  const match = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
  if (!match) {
    return '';
  }
  return decodeURIComponent(match[1] || match[2] || '').trim();
}

async function downloadGatewayAttachment(params: {
  identity: BridgeIdentity;
  attachment: Record<string, unknown>;
}): Promise<{ filename: string; contentType: string; base64: string }> {
  const path = resolveGatewayAttachmentPath(params.attachment);
  if (!path) {
    throw new Error('Attachment missing downloadable path/file_id');
  }

  const query = new URLSearchParams({
    channel: params.identity.channel,
    accountId: params.identity.accountId,
    externalUserId: params.identity.externalUserId,
  });

  if (params.identity.externalChatId) {
    query.set('externalChatId', params.identity.externalChatId);
  }

  const url = `${LIBRECHAT_URL}${path}?${query.toString()}`;
  const headers = buildGatewayHeaders({ method: 'GET', path, body: {} });
  delete headers['Content-Type'];

  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => '');
    throw new Error(`Attachment download failed (${response.status}): ${errText.slice(0, 200)}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  const fallbackFilename =
    normalizeString(params.attachment.filename) ||
    normalizeString(params.attachment.file_id) ||
    'attachment';

  const disposition = response.headers.get('content-disposition') || '';
  const filename = parseFilenameFromDisposition(disposition) || fallbackFilename;
  const contentType =
    response.headers.get('content-type') ||
    normalizeString(params.attachment.type) ||
    'application/octet-stream';

  return {
    filename,
    contentType,
    base64: buffer.toString('base64'),
  };
}

async function sendAttachmentReply(params: {
  identity: BridgeIdentity;
  attachment: Record<string, unknown>;
}): Promise<void> {
  const downloaded = await downloadGatewayAttachment(params);

  const args: Record<string, unknown> = {
    channel: params.identity.channel,
    accountId: params.identity.accountId,
    to: resolveDeliveryTarget(params.identity),
    buffer: downloaded.base64,
    filename: downloaded.filename,
    contentType: downloaded.contentType,
    caption: '',
  };

  if (params.identity.externalThreadId) {
    args.threadId = params.identity.externalThreadId;
  }
  if (params.identity.externalMessageId) {
    args.replyTo = params.identity.externalMessageId;
  }

  await invokeMessageTool('sendAttachment', args);
}

type SseEvent = {
  event: string;
  data: unknown;
};

async function* iterateSseEvents(response: Response): AsyncGenerator<SseEvent> {
  const stream = response.body;
  if (!stream) {
    return;
  }

  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    while (true) {
      const separator = buffer.indexOf('\n\n');
      if (separator < 0) {
        break;
      }
      const block = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);

      let eventName = 'message';
      const dataLines: string[] = [];
      for (const rawLine of block.split(/\r?\n/)) {
        if (!rawLine) {
          continue;
        }
        if (rawLine.startsWith('event:')) {
          eventName = rawLine.slice('event:'.length).trim() || 'message';
          continue;
        }
        if (rawLine.startsWith('data:')) {
          dataLines.push(rawLine.slice('data:'.length).trimStart());
        }
      }

      if (dataLines.length === 0) {
        continue;
      }

      const payloadText = dataLines.join('\n');
      let data: unknown = payloadText;
      try {
        data = JSON.parse(payloadText);
      } catch {
        data = payloadText;
      }
      yield { event: eventName, data };
    }
  }
}

async function startGatewayChat(params: {
  identity: BridgeIdentity;
  text: string;
  inputMode: string;
  conversationId: string;
  parentMessageId: string;
  attachments: Array<Record<string, unknown>>;
}): Promise<
  | {
      kind: 'ok';
      streamId: string;
      conversationId: string;
      parentMessageId: string;
    }
  | {
      kind: 'duplicate';
    }
  | {
      kind: 'link_required';
      linkUrl: string;
      message: string;
    }
> {
  const path = '/api/viventium/gateway/chat';
  const body: Record<string, unknown> = {
    channel: params.identity.channel,
    accountId: params.identity.accountId,
    externalUserId: params.identity.externalUserId,
    externalChatId: params.identity.externalChatId,
    externalMessageId: params.identity.externalMessageId,
    externalUpdateId: params.identity.externalUpdateId,
    externalThreadId: params.identity.externalThreadId,
    externalUsername: params.identity.externalUsername,
    text: params.text,
    conversationId: params.conversationId || 'new',
    inputMode: params.inputMode || 'text',
  };

  if (params.parentMessageId) {
    body.parentMessageId = params.parentMessageId;
  }
  if (AGENT_ID) {
    body.agent_id = AGENT_ID;
  }
  if (params.attachments.length > 0) {
    body.attachments = params.attachments;
  }

  const response = await fetchWithTimeout(`${LIBRECHAT_URL}${path}`, {
    method: 'POST',
    headers: buildGatewayHeaders({ method: 'POST', path, body }),
    body: JSON.stringify(body),
  });

  const rawText = await response.text().catch(() => '');
  let payload: unknown = null;
  if (rawText) {
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = rawText;
    }
  }

  if (response.status === 401 && isObject(payload) && payload.linkRequired) {
    return {
      kind: 'link_required',
      linkUrl: normalizeString(payload.linkUrl),
      message:
        normalizeString(payload.message) ||
        normalizeString(payload.error) ||
        'Link your account to continue.',
    };
  }

  if (!response.ok) {
    const errText = typeof payload === 'string' ? payload : rawText;
    throw new Error(`Gateway chat failed (${response.status}): ${errText.slice(0, 200)}`);
  }

  if (!isObject(payload)) {
    throw new Error('Gateway chat returned invalid payload');
  }

  if (payload.duplicate === true) {
    return { kind: 'duplicate' };
  }

  const streamId = normalizeString(payload.streamId);
  const conversationId = normalizeString(payload.conversationId);
  const parentMessageId = normalizeString(payload.parentMessageId);

  if (!streamId) {
    throw new Error('Gateway chat response missing streamId');
  }

  return {
    kind: 'ok',
    streamId,
    conversationId,
    parentMessageId,
  };
}

async function consumeGatewayStream(params: {
  identity: BridgeIdentity;
  streamId: string;
}): Promise<{ text: string; attachments: Array<Record<string, unknown>>; messageId: string; error: string }> {
  const path = `/api/viventium/gateway/stream/${encodeURIComponent(params.streamId)}`;
  const query = new URLSearchParams({
    channel: params.identity.channel,
    accountId: params.identity.accountId,
    externalUserId: params.identity.externalUserId,
  });
  if (params.identity.externalChatId) {
    query.set('externalChatId', params.identity.externalChatId);
  }

  const response = await fetchWithTimeout(`${LIBRECHAT_URL}${path}?${query.toString()}`, {
    method: 'GET',
    headers: (() => {
      const headers = buildGatewayHeaders({ method: 'GET', path, body: {} });
      delete headers['Content-Type'];
      return headers;
    })(),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => '');
    throw new Error(`Gateway stream failed (${response.status}): ${errText.slice(0, 200)}`);
  }

  const deltas: string[] = [];
  let finalText = '';
  let messageId = '';
  let streamError = '';
  const attachments: Array<Record<string, unknown>> = [];

  for await (const sse of iterateSseEvents(response)) {
    if (sse.event === 'message') {
      if (!isObject(sse.data)) {
        continue;
      }
      const type = normalizeString(sse.data.type);
      const text = normalizeString(sse.data.text);
      if (type === 'delta' && text) {
        deltas.push(text);
      } else if (type === 'final') {
        if (text) {
          finalText = text;
        }
        messageId = normalizeString(sse.data.messageId) || messageId;
      } else if (text) {
        deltas.push(text);
      }
      continue;
    }

    if (sse.event === 'attachment') {
      if (isObject(sse.data)) {
        attachments.push(sse.data);
      }
      continue;
    }

    if (sse.event === 'error') {
      if (isObject(sse.data)) {
        streamError = normalizeString(sse.data.error) || streamError;
      } else {
        streamError = normalizeString(sse.data) || streamError;
      }
      continue;
    }

    if (sse.event === 'done') {
      if (isObject(sse.data)) {
        messageId = normalizeString(sse.data.messageId) || messageId;
      }
      break;
    }
  }

  const text = deltas.length > 0 ? deltas.join('') : finalText;
  return {
    text,
    attachments,
    messageId,
    error: streamError,
  };
}

function enqueueScopeTask(scopeKey: string, task: () => Promise<void>): void {
  const previous = SCOPE_QUEUES.get(scopeKey) || Promise.resolve();
  const next = previous
    .catch(() => undefined)
    .then(task)
    .catch(() => undefined);

  SCOPE_QUEUES.set(scopeKey, next.finally(() => {
    if (SCOPE_QUEUES.get(scopeKey) === next) {
      SCOPE_QUEUES.delete(scopeKey);
    }
  }));
}

async function maybeSendLinkNotice(api: OpenClawPluginApi, identity: BridgeIdentity, linkUrl: string): Promise<void> {
  if (!linkUrl) {
    return;
  }

  const scopeKey = buildScopeKey(identity);
  const now = Date.now();
  const lastSent = LINK_NOTICE_AT.get(scopeKey) || 0;
  if (now - lastSent < LINK_NOTICE_COOLDOWN_MS) {
    return;
  }

  LINK_NOTICE_AT.set(scopeKey, now);

  const notice = `Link your Viventium account to continue: ${linkUrl}`;
  try {
    await sendTextReply({ identity, text: notice });
  } catch (err) {
    api.logger.warn(
      `[viventium-channel-bridge] Failed to deliver link notice: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
}

async function handleInboundMessage(
  api: OpenClawPluginApi,
  event: MessageReceivedEvent,
  context: MessageContext,
): Promise<void> {
  const identity = makeIdentity(event, context);
  if (!identity.channel || !identity.externalUserId) {
    return;
  }

  const text = normalizeString(event.content);
  const attachments = extractInboundAttachments(event);
  if (!text && attachments.length === 0) {
    return;
  }

  const scopeKey = buildScopeKey(identity);
  enqueueScopeTask(scopeKey, async () => {
    const state = CONVERSATIONS_BY_SCOPE.get(scopeKey) || {
      conversationId: 'new',
      parentMessageId: '',
    };

    api.logger.info(
      `[viventium-channel-bridge] Routing ${identity.channel}:${identity.externalUserId} -> gateway (scope=${scopeKey})`,
    );

    const inputMode = detectInputMode(event);

    let startResult;
    try {
      startResult = await startGatewayChat({
        identity,
        text,
        inputMode,
        conversationId: state.conversationId || 'new',
        parentMessageId: state.parentMessageId,
        attachments,
      });
    } catch (err) {
      api.logger.error(
        `[viventium-channel-bridge] Chat request failed: ${err instanceof Error ? err.message : String(err)}`,
      );
      await sendTextReply({
        identity,
        text: 'Connection error. Please retry.',
      }).catch(() => undefined);
      return;
    }

    if (startResult.kind === 'duplicate') {
      return;
    }

    if (startResult.kind === 'link_required') {
      await maybeSendLinkNotice(api, identity, startResult.linkUrl);
      return;
    }

    const nextState: ConversationState = {
      conversationId: startResult.conversationId || state.conversationId || 'new',
      parentMessageId: startResult.parentMessageId || state.parentMessageId || '',
    };
    CONVERSATIONS_BY_SCOPE.set(scopeKey, nextState);

    let stream;
    try {
      stream = await consumeGatewayStream({
        identity,
        streamId: startResult.streamId,
      });
    } catch (err) {
      api.logger.error(
        `[viventium-channel-bridge] Stream failed: ${err instanceof Error ? err.message : String(err)}`,
      );
      await sendTextReply({
        identity,
        text: 'Connection error. Please retry.',
      }).catch(() => undefined);
      return;
    }

    if (stream.messageId) {
      nextState.parentMessageId = stream.messageId;
      CONVERSATIONS_BY_SCOPE.set(scopeKey, nextState);
    }

    if (stream.text) {
      await sendTextReply({ identity, text: stream.text }).catch((err) => {
        api.logger.error(
          `[viventium-channel-bridge] Failed to send text reply: ${err instanceof Error ? err.message : String(err)}`,
        );
      });
    }

    for (const attachment of stream.attachments) {
      await sendAttachmentReply({ identity, attachment }).catch((err) => {
        api.logger.error(
          `[viventium-channel-bridge] Failed to send attachment: ${err instanceof Error ? err.message : String(err)}`,
        );
      });
    }

    if (!stream.text && stream.attachments.length === 0 && stream.error) {
      await sendTextReply({
        identity,
        text: 'Connection error. Please retry.',
      }).catch(() => undefined);
    }
  });
}

const plugin = {
  id: 'viventium-channel-bridge',
  name: 'Viventium Channel Bridge',
  description: 'Routes OpenClaw channel messages to Viventium LibreChat gateway',
  version: '0.2.0',

  register(api: OpenClawPluginApi): void {
    resolveConfig(api);

    if (!GATEWAY_SECRET) {
      api.logger.warn(
        '[viventium-channel-bridge] Missing gateway secret. Set gatewaySecret or VIVENTIUM_GATEWAY_SECRET.',
      );
      return;
    }

    if (!GATEWAY_TOKEN) {
      api.logger.warn(
        '[viventium-channel-bridge] Missing OpenClaw gateway token. Channel delivery may fail.',
      );
    }

    api.on('gateway_start', (event: unknown) => {
      const e = event as GatewayStartEvent;
      GATEWAY_PORT = e.port;
      api.logger.info(
        `[viventium-channel-bridge] Active on port ${e.port}. Routing to ${LIBRECHAT_URL} (agent: ${AGENT_ID || 'default'}).`,
      );
    });

    api.on('message_received', async (event: unknown, context: unknown) => {
      const message = event as MessageReceivedEvent;
      const ctx = context as MessageContext;

      if (!normalizeString(message?.content) && extractInboundAttachments(message).length === 0) {
        return;
      }

      try {
        await handleInboundMessage(api, message, ctx);
      } catch (err) {
        api.logger.error(
          `[viventium-channel-bridge] Unhandled error: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    });

    api.logger.info('[viventium-channel-bridge] Plugin registered (gateway v2).');
  },
};

export default plugin;
