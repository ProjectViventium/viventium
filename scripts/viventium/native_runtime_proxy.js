#!/usr/bin/env node
/* Relocatable loopback proxy preserving Viventium's public web port. */
'use strict';

const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {execFile} = require('child_process');

const listenPort = Number(process.env.VIVENTIUM_NATIVE_PROXY_LISTEN_PORT || '3190');
if (!Number.isInteger(listenPort) || listenPort < 1 || listenPort > 65535) {
  throw new Error('invalid Native proxy port policy');
}
const sandpackListenPort = Number(process.env.VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT || '3191');
if (
  !Number.isInteger(sandpackListenPort) ||
  sandpackListenPort < 1 ||
  sandpackListenPort > 65535 ||
  sandpackListenPort === listenPort
) {
  throw new Error('invalid Native isolated artifact port policy');
}
const releaseId = process.env.VIVENTIUM_NATIVE_RELEASE_ID || '';
const releaseRoot = process.env.VIVENTIUM_NATIVE_RELEASE_ROOT || '';
const sandpackRoot = process.env.VIVENTIUM_NATIVE_SANDPACK_ROOT || '';
const firstAdminState = process.env.VIVENTIUM_NATIVE_FIRST_ADMIN_STATE || '';
const registrationCloseHook = process.env.VIVENTIUM_NATIVE_REGISTRATION_CLOSE_HOOK || '';
const appSupportDir = process.env.VIVENTIUM_APP_SUPPORT_DIR || '';
const targetSocket = process.env.VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET || '';
const allowedOrigin = 'http://127.0.0.1:3190';
const allowedHost = `127.0.0.1:${listenPort}`;
const expectedSandpackIndexSha256 = process.env.VIVENTIUM_NATIVE_SANDPACK_INDEX_SHA256 || '';
const expectedOnPremBootstrap = 'window._env_=Object.assign({},window._env_,{IS_ONPREM:"true"})';
const firstAdminCookieName = 'viventium_native_first_admin';
if (!registrationCloseHook.startsWith('/') || !appSupportDir.startsWith('/')) {
  throw new Error('Native first-admin close hook policy is unavailable');
}
const expectedTargetSocket = path.join(appSupportDir, 'runtime', 'librechat-api.sock');
if (
  targetSocket !== targetSocket.trim() ||
  targetSocket.includes('\0') ||
  !path.isAbsolute(targetSocket) ||
  path.resolve(targetSocket) !== path.resolve(expectedTargetSocket)
) {
  throw new Error('Native API socket policy is unavailable');
}
const expectedSandpackRoot = path.join(
  releaseRoot,
  'runtime',
  'librechat',
  'client',
  'dist',
  'sandpack-bundler',
);
if (
  !path.isAbsolute(releaseRoot) ||
  !path.isAbsolute(sandpackRoot) ||
  releaseRoot.includes('\0') ||
  sandpackRoot.includes('\0') ||
  path.resolve(sandpackRoot) !== path.resolve(expectedSandpackRoot)
) {
  throw new Error('Native isolated artifact root policy is unavailable');
}
if (!/^[a-f0-9]{64}$/.test(expectedSandpackIndexSha256)) {
  throw new Error('Native isolated artifact identity policy is unavailable');
}
const sandpackRootMetadata = fs.lstatSync(sandpackRoot);
const sandpackRealRoot = fs.realpathSync(sandpackRoot);
const sandpackIndexPath = path.join(sandpackRoot, 'index.html');
const sandpackIndexMetadata = fs.lstatSync(sandpackIndexPath);
const sandpackIndex = fs.readFileSync(sandpackIndexPath);
if (
  !sandpackRootMetadata.isDirectory() ||
  sandpackRootMetadata.isSymbolicLink() ||
  sandpackRootMetadata.uid !== process.getuid() ||
  !sandpackIndexMetadata.isFile() ||
  sandpackIndexMetadata.isSymbolicLink() ||
  sandpackIndexMetadata.uid !== process.getuid() ||
  crypto.createHash('sha256').update(sandpackIndex).digest('hex') !== expectedSandpackIndexSha256 ||
  !sandpackIndex.toString('utf8').includes(expectedOnPremBootstrap)
) {
  throw new Error('Native isolated artifact release identity is invalid');
}
const targetSocketMetadata = fs.lstatSync(targetSocket);
if (
  !targetSocketMetadata.isSocket() ||
  targetSocketMetadata.uid !== process.getuid() ||
  (targetSocketMetadata.mode & 0o777) !== 0o600
) {
  throw new Error('Native API socket is unsafe');
}
const hookMetadata = fs.lstatSync(registrationCloseHook);
if (!hookMetadata.isFile() || (hookMetadata.mode & 0o111) === 0) {
  throw new Error('Native first-admin close hook is not executable');
}

function readFirstAdmin() {
  const value = JSON.parse(fs.readFileSync(firstAdminState, 'utf8'));
  if (value.schema_version !== 1 || !['open', 'pending', 'closed'].includes(value.status)) {
    throw new Error('invalid first-admin state');
  }
  return value;
}

function tokenMatches(actual, expected) {
  if (typeof actual !== 'string' || typeof expected !== 'string') return false;
  const one = Buffer.from(actual, 'utf8');
  const two = Buffer.from(expected, 'utf8');
  return one.length === two.length && crypto.timingSafeEqual(one, two);
}

function firstAdminCookie(request) {
  const header = String(request.headers.cookie || '');
  for (const item of header.split(';')) {
    const [name, ...rest] = item.trim().split('=');
    if (name === firstAdminCookieName) return rest.join('=');
  }
  return '';
}

function firstAdminCookieHeader(token, maximumAge = 900) {
  return `${firstAdminCookieName}=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${maximumAge}`;
}

function writeFirstAdmin(value) {
  const encoded = `${JSON.stringify(value)}\n`;
  const temporary = `${firstAdminState}.${process.pid}.${crypto.randomBytes(8).toString('hex')}.tmp`;
  fs.writeFileSync(temporary, encoded, {encoding: 'utf8', mode: 0o600, flag: 'wx'});
  fs.renameSync(temporary, firstAdminState);
}

function closeFirstAdmin() {
  writeFirstAdmin({schema_version: 1, status: 'closed', admin_created_at: Math.floor(Date.now() / 1000)});
}

function reloadClosedRegistration(response, statusCode, contentType, responseBody) {
  closeFirstAdmin();
  execFile(
    registrationCloseHook,
    ['--app-support-dir', appSupportDir],
    {timeout: 120000, windowsHide: true},
    error => {
      if (error) {
        response.writeHead(503, {'content-type': 'text/plain', 'cache-control': 'no-store'});
        response.end('Admin was created, but the local service could not close registration safely. Restart Viventium before signing in.\n');
        return;
      }
      response.writeHead(statusCode, {
        'content-type': contentType,
        'cache-control': 'no-store',
        'set-cookie': firstAdminCookieHeader('', 0),
      });
      response.end(responseBody);
    },
  );
}

function firstAdminPage(request, response, queryToken) {
  const state = readFirstAdmin();
  if (state.status === 'open' && tokenMatches(queryToken, state.token)) {
    response.writeHead(303, {
      location: '/__viventium_native_first_admin',
      'cache-control': 'no-store',
      'referrer-policy': 'no-referrer',
      'set-cookie': firstAdminCookieHeader(state.token),
    });
    response.end();
    return;
  }
  const token = firstAdminCookie(request);
  if (state.status !== 'open' || !tokenMatches(token, state.token)) {
    response.writeHead(403, {
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'no-store',
      'set-cookie': firstAdminCookieHeader('', 0),
    });
    response.end('This first-admin link is invalid or has already been used.\n');
    return;
  }
  response.writeHead(200, {
    'content-type': 'text/html; charset=utf-8',
    'cache-control': 'no-store',
    'referrer-policy': 'no-referrer',
    'content-security-policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; base-uri 'none'",
  });
  response.end(`<!doctype html><meta charset="utf-8"><title>Create Viventium admin</title>
<style>body{font:16px system-ui;max-width:32rem;margin:8vh auto;padding:1rem}label{display:block;margin:1rem 0}input{display:block;width:100%;padding:.65rem}button{padding:.7rem 1rem}</style>
<h1>Create your local admin</h1><p>This one-time page works only on this Mac.</p>
<form id="f"><label>Name<input name="name" required></label><label>Email<input name="email" type="email" required></label><label>Password<input name="password" type="password" minlength="8" required></label><label>Confirm password<input name="confirm_password" type="password" minlength="8" required></label><button>Create admin</button></form><p id="m" role="status" aria-live="polite"></p>
<script>f.onsubmit=(e)=>{e.preventDefault();const x=Object.fromEntries(new FormData(f));if(x.password!==x.confirm_password){m.textContent='The passwords do not match.';return}m.textContent='Creating your local admin…';x.username=x.email;fetch('/__viventium_native_first_admin',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(x)}).then(async(r)=>{if(r.ok){m.textContent='Admin created. Continue by signing in and adding your provider API key.';location.href='/login?redirect_to=%2Fc%2Fnew%3Fsetup%3Daccounts'}else{m.textContent=await r.text()}}).catch(() => {m.textContent='Account setup could not reach the local service. Check that Viventium is running, then try again.'})}</script>`);
}

function createFirstAdmin(request, response) {
  if (request.headers.origin !== allowedOrigin || request.headers['content-type']?.split(';')[0] !== 'application/json') {
    response.writeHead(403, {'content-type': 'text/plain'});
    response.end('First-admin request origin was rejected.\n');
    return;
  }
  let body = Buffer.alloc(0);
  request.on('data', chunk => {
    body = Buffer.concat([body, chunk]);
    if (body.length > 65536) request.destroy();
  });
  request.on('end', () => {
    try {
      const state = readFirstAdmin();
      const submitted = JSON.parse(body.toString('utf8'));
      if (
        typeof submitted.name !== 'string' ||
        typeof submitted.email !== 'string' ||
        typeof submitted.password !== 'string' ||
        typeof submitted.confirm_password !== 'string' ||
        submitted.confirm_password !== submitted.password
      ) {
        response.writeHead(400, {'content-type': 'text/plain', 'cache-control': 'no-store'});
        response.end('Name, email, and matching passwords are required.\n');
        return;
      }
      if (state.status !== 'open' || !tokenMatches(firstAdminCookie(request), state.token)) {
        response.writeHead(409, {'content-type': 'text/plain'});
        response.end('This first-admin link has already been used or is invalid.\n');
        return;
      }
      writeFirstAdmin({schema_version: 1, status: 'pending', token: state.token, claimed_at: Math.floor(Date.now() / 1000)});
      const upstreamBody = JSON.stringify({
        email: submitted.email,
        password: submitted.password,
        confirm_password: submitted.confirm_password,
        name: submitted.name,
        username: submitted.username || submitted.email,
      });
      const upstream = http.request({socketPath: targetSocket, method: 'POST', path: '/api/auth/register', headers: {'content-type': 'application/json', 'content-length': Buffer.byteLength(upstreamBody)}}, upstreamResponse => {
        const chunks = [];
        upstreamResponse.on('data', chunk => chunks.push(chunk));
        upstreamResponse.on('end', () => {
          const statusCode = upstreamResponse.statusCode || 502;
          const responseBody = Buffer.concat(chunks);
          if (statusCode < 300) {
            reloadClosedRegistration(
              response,
              statusCode,
              upstreamResponse.headers['content-type'] || 'application/json',
              responseBody,
            );
            return;
          }
          writeFirstAdmin(state);
          response.writeHead(statusCode, {'content-type': upstreamResponse.headers['content-type'] || 'application/json', 'cache-control': 'no-store'});
          response.end(responseBody);
        });
      });
      upstream.on('error', () => {
        writeFirstAdmin(state);
        response.writeHead(502, {'content-type': 'text/plain', 'cache-control': 'no-store'});
        response.end('Account setup could not reach the local service. Retry this same one-time page.\n');
      });
      upstream.end(upstreamBody);
    } catch (_) {
      response.writeHead(400, {'content-type': 'text/plain'});
      response.end('First-admin request was invalid.\n');
    }
  });
}

const server = http.createServer((request, response) => {
  if (request.headers.host !== allowedHost) {
    response.writeHead(421, {'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store'});
    response.end('Native proxy host was rejected.\n');
    return;
  }
  const requestURL = new URL(request.url, allowedOrigin);
  if (requestURL.pathname === '/__viventium_native_health') {
    response.writeHead(200, {'content-type': 'application/json', 'cache-control': 'no-store'});
    response.end(`${JSON.stringify({release: releaseId, status: 'ok'})}\n`);
    return;
  }
  if (requestURL.pathname === '/__viventium_native_first_admin') {
    if (request.method === 'GET') firstAdminPage(request, response, requestURL.searchParams.get('token'));
    else if (request.method === 'POST') createFirstAdmin(request, response);
    else { response.writeHead(405); response.end(); }
    return;
  }
  if (requestURL.pathname === '/register' && request.method === 'GET') {
    const state = readFirstAdmin();
    if (state.status === 'open') {
      response.writeHead(403, {
        'content-type': 'text/plain; charset=utf-8',
        'cache-control': 'no-store',
        'referrer-policy': 'no-referrer',
      });
      response.end('Return to the Viventium installer to finish creating the first local admin.\n');
      return;
    } else {
      response.writeHead(303, {
        location: '/login?registration=closed',
        'cache-control': 'no-store',
        'set-cookie': firstAdminCookieHeader('', 0),
      });
    }
    response.end();
    return;
  }
  if (requestURL.pathname === '/api/auth/register') {
    response.writeHead(403, {'content-type': 'text/plain', 'cache-control': 'no-store'});
    response.end('Registration is available only through the one-time local first-admin page.\n');
    return;
  }
  const upstream = http.request({
    socketPath: targetSocket,
    method: request.method,
    path: request.url,
    headers: request.headers,
  }, (upstreamResponse) => {
    response.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
    upstreamResponse.pipe(response);
  });
  upstream.on('error', () => {
    if (!response.headersSent) response.writeHead(502, {'content-type': 'text/plain'});
    response.end('Viventium is starting.\n');
  });
  request.pipe(upstream);
});

const sandpackContentTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.webmanifest', 'application/manifest+json; charset=utf-8'],
  ['.svg', 'image/svg+xml'],
  ['.png', 'image/png'],
  ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'],
  ['.ico', 'image/x-icon'],
  ['.woff', 'font/woff'],
  ['.ttf', 'font/ttf'],
  ['.txt', 'text/plain; charset=utf-8'],
]);

function sandpackHeaders(contentType) {
  return {
    'content-type': contentType,
    'cache-control': 'no-store',
    'content-security-policy': `frame-ancestors ${allowedOrigin}`,
    'cross-origin-resource-policy': 'same-site',
    'referrer-policy': 'no-referrer',
    'x-content-type-options': 'nosniff',
  };
}

const sandpackServer = http.createServer((request, response) => {
  if (request.headers.host !== `127.0.0.1:${sandpackListenPort}`) {
    response.writeHead(421, sandpackHeaders('text/plain; charset=utf-8'));
    response.end('Isolated artifact host was rejected.\n');
    return;
  }
  if (!['GET', 'HEAD'].includes(request.method || '')) {
    response.writeHead(405, {...sandpackHeaders('text/plain; charset=utf-8'), allow: 'GET, HEAD'});
    response.end('Method not allowed.\n');
    return;
  }
  let requestPath;
  try {
    requestPath = decodeURIComponent(new URL(request.url, `http://127.0.0.1:${sandpackListenPort}`).pathname);
  } catch (_) {
    response.writeHead(400, sandpackHeaders('text/plain; charset=utf-8'));
    response.end('Invalid artifact path.\n');
    return;
  }
  if (requestPath.includes('\0') || requestPath.includes('\\')) {
    response.writeHead(400, sandpackHeaders('text/plain; charset=utf-8'));
    response.end('Invalid artifact path.\n');
    return;
  }
  const relativePath = requestPath === '/' ? 'index.html' : requestPath.replace(/^\/+/, '');
  const candidate = path.resolve(sandpackRoot, relativePath);
  if (candidate !== sandpackRealRoot && !candidate.startsWith(`${sandpackRealRoot}${path.sep}`)) {
    response.writeHead(403, sandpackHeaders('text/plain; charset=utf-8'));
    response.end('Artifact path escaped its release root.\n');
    return;
  }
  let metadata;
  let realCandidate;
  try {
    metadata = fs.lstatSync(candidate);
    realCandidate = fs.realpathSync(candidate);
  } catch (_) {
    response.writeHead(404, sandpackHeaders('text/plain; charset=utf-8'));
    response.end('Artifact file was not found.\n');
    return;
  }
  if (
    !metadata.isFile() ||
    metadata.isSymbolicLink() ||
    metadata.uid !== process.getuid() ||
    (realCandidate !== sandpackRealRoot && !realCandidate.startsWith(`${sandpackRealRoot}${path.sep}`))
  ) {
    response.writeHead(403, sandpackHeaders('text/plain; charset=utf-8'));
    response.end('Artifact file is unsafe.\n');
    return;
  }
  response.writeHead(
    200,
    sandpackHeaders(sandpackContentTypes.get(path.extname(candidate).toLowerCase()) || 'application/octet-stream'),
  );
  if (request.method === 'HEAD') {
    response.end();
    return;
  }
  const stream = fs.createReadStream(candidate);
  stream.on('error', () => response.destroy());
  stream.pipe(response);
});

server.on('upgrade', (request, client, head) => {
  if (request.headers.host !== allowedHost) {
    client.end(
      'HTTP/1.1 421 Misdirected Request\r\n' +
        'Content-Type: text/plain; charset=utf-8\r\n' +
        'Cache-Control: no-store\r\n' +
        'Connection: close\r\n\r\n' +
        'Native proxy host was rejected.\n',
    );
    return;
  }
  const upstream = net.connect({path: targetSocket}, () => {
    const headers = Object.entries(request.headers)
      .map(([name, value]) => `${name}: ${value}`)
      .join('\r\n');
    upstream.write(`${request.method} ${request.url} HTTP/${request.httpVersion}\r\n${headers}\r\n\r\n`);
    if (head.length) upstream.write(head);
    upstream.pipe(client);
    client.pipe(upstream);
  });
  upstream.on('error', () => client.destroy());
});

server.listen(listenPort, '127.0.0.1');
sandpackServer.listen(sandpackListenPort, '127.0.0.1');
