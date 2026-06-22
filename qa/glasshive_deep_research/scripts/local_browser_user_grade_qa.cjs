#!/usr/bin/env node
'use strict';

const childProcess = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const FIXTURE_SCRIPT = path.join(__dirname, 'local_user_grade_fixture.py');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'playwright', 'glasshive-deep-research');
const PUBLIC_MARKER = 'GLASSHIVE_BROWSER_QA_MARKER';
const INPUT_MARKER = 'GLASSHIVE_INPUT_QA_MARKER';
const ACTIVE_RUN_MARKER = 'GLASSHIVE_BROWSER_QA_ACTIVE_RUN';
const TERMINATE_RUN_MARKER = 'GLASSHIVE_BROWSER_QA_TERMINATE_RUN';

const DEFAULT_TIMEOUT_MS = 45_000;
const EXPECTED_ARTIFACTS = [
  'answer.md',
  'output/data.csv',
  'output/input-summary.md',
  'reports/report.html',
  'artifacts/report.pdf',
  'artifacts/book.xlsx',
  'artifacts/brief.docx',
  'artifacts/deck.pptx',
];

const SIGNED_QUERY_KEYS = ['token', 'sig', 'exp', 'kind'].map((name) => `gh_${name}`);
const FORBIDDEN_PUBLIC_TEXT = [
  ...SIGNED_QUERY_KEYS.map((key) => [`${key} query`, new RegExp(`(?:\\?|&|\\b)${key}=`, 'i')]),
  ['raw signed-link route', new RegExp('/v1/' + 'signed-links/', 'i')],
  ['fixture signing secret', /public-safe-signed-link-secret/i],
  ['local home path', /\/Users\/[A-Za-z0-9._-]+/],
];

function parseArgs(argv) {
  const args = {
    headed: false,
    python: process.env.GLASSHIVE_QA_PYTHON || '',
    stateRoot: '',
    timeoutMs: DEFAULT_TIMEOUT_MS,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === '--headed') {
      args.headed = true;
    } else if (item === '--python') {
      args.python = argv[++index] || '';
    } else if (item === '--state-root') {
      args.stateRoot = argv[++index] || '';
    } else if (item === '--timeout-ms') {
      args.timeoutMs = Number(argv[++index] || DEFAULT_TIMEOUT_MS);
    } else if (item === '--help' || item === '-h') {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${item}`);
    }
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs < 5_000) {
    throw new Error('--timeout-ms must be at least 5000');
  }
  return args;
}

function printHelp() {
  console.log(`Usage: node qa/glasshive_deep_research/scripts/local_browser_user_grade_qa.cjs [options]

Starts the existing public-safe GlassHive fixture and drives the browser-visible
project, worker, artifact short-link, download, /w/{ref}, refresh, and active-run
pause/resume/interrupt paths with Playwright for Node.

Options:
  --headed            Run Chromium headed.
  --python PATH       Python executable for local_user_grade_fixture.py.
  --state-root PATH   Fixture state root. Defaults to a temporary directory.
  --timeout-ms N      Per-wait timeout. Defaults to ${DEFAULT_TIMEOUT_MS}.
`);
}

function findPython(explicitPython) {
  if (explicitPython) {
    return explicitPython;
  }
  const venvPython = path.join(
    REPO_ROOT,
    'viventium_v0_4',
    'GlassHive',
    'runtime_phase1',
    '.venv',
    'bin',
    'python',
  );
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return 'python3';
}

function loadPlaywright() {
  const candidates = [
    process.env.PLAYWRIGHT_MODULE_PATH || '',
    path.join(REPO_ROOT, 'viventium_v0_4', 'prompt-workbench', 'node_modules', 'playwright'),
    path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat', 'node_modules', 'playwright'),
    'playwright',
  ].filter(Boolean);
  const errors = [];
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch (error) {
      errors.push(`${candidate}: ${error.message}`);
    }
  }
  throw new Error(
    [
      'Unable to load Playwright for Node.',
      'Install the existing repo app dependencies or set PLAYWRIGHT_MODULE_PATH to a Playwright module directory.',
      ...errors.map((line) => `- ${line}`),
    ].join('\n'),
  );
}

function startFixture({ python, stateRoot, timeoutMs }) {
  if (!fs.existsSync(FIXTURE_SCRIPT)) {
    throw new Error(`Missing fixture script: ${path.relative(REPO_ROOT, FIXTURE_SCRIPT)}`);
  }
  fs.mkdirSync(stateRoot, { recursive: true });
  const child = childProcess.spawn(
    python,
    [FIXTURE_SCRIPT, '--fresh', '--state-root', stateRoot],
    {
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
  let stdout = '';
  let stderr = '';
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`Fixture did not start within ${timeoutMs} ms.\n${stderr || stdout}`));
    }, timeoutMs);

    function finish(payload) {
      clearTimeout(timer);
      resolve({ child, fixture: payload, stderr: () => stderr });
    }

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
      for (const line of stdout.split(/\r?\n/)) {
        if (!line.startsWith('GLASSHIVE_QA_SERVER ')) {
          continue;
        }
        try {
          finish(JSON.parse(line.slice('GLASSHIVE_QA_SERVER '.length)));
        } catch (error) {
          reject(new Error(`Fixture emitted invalid JSON: ${error.message}`));
        }
      }
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });
    child.on('exit', (code, signal) => {
      clearTimeout(timer);
      reject(new Error(`Fixture exited before ready: code=${code} signal=${signal}\n${stderr || stdout}`));
    });
    child.on('error', (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
}

async function stopFixture(child) {
  if (!child || child.killed || child.exitCode !== null) {
    return;
  }
  await new Promise((resolve) => {
    const timer = setTimeout(() => {
      try {
        child.kill('SIGKILL');
      } catch {
        // Already gone.
      }
      resolve();
    }, 5_000);
    child.once('exit', () => {
      clearTimeout(timer);
      resolve();
    });
    child.kill('SIGTERM');
  });
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function waitFor(fn, label, timeoutMs = DEFAULT_TIMEOUT_MS, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const result = await fn();
      if (result) {
        return result;
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(`Timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ''}`);
}

function absoluteUrl(baseUrl, value) {
  return new URL(value, baseUrl).toString();
}

function shortUrlForEvidence(rawUrl, fixture) {
  try {
    const url = new URL(rawUrl);
    let pathname = url.pathname
      .replace(/ghr_[A-Za-z0-9_-]+/g, 'ghr_<ref>')
      .replaceAll(fixture.worker.worker_id, '<worker>')
      .replaceAll(fixture.project.project_id, '<project>');
    return `${url.origin}${pathname}`;
  } catch {
    return String(rawUrl || '')
      .replace(/ghr_[A-Za-z0-9_-]+/g, 'ghr_<ref>')
      .replaceAll(fixture.worker.worker_id, '<worker>')
      .replaceAll(fixture.project.project_id, '<project>');
  }
}

async function topLevelSnapshot(page) {
  return page.evaluate(() => ({
    url: window.location.href,
    text: document.body ? document.body.innerText : '',
    hrefs: Array.from(document.querySelectorAll('a[href]')).map((node) => node.getAttribute('href') || ''),
    buttons: Array.from(document.querySelectorAll('button')).map((node) => node.innerText || ''),
  }));
}

function assertNoForbiddenPublicText(snapshot, label, { workerId = '', projectId = '', forbidRawIds = false } = {}) {
  const combined = [snapshot.url, snapshot.text, ...(snapshot.hrefs || [])].join('\n');
  for (const [name, pattern] of FORBIDDEN_PUBLIC_TEXT) {
    assert(!pattern.test(combined), `${label} leaked ${name}`);
  }
  if (forbidRawIds) {
    assert(!combined.includes(workerId), `${label} leaked raw worker id`);
    assert(!combined.includes(projectId), `${label} leaked raw project id`);
  }
}

async function waitForFrameText(page, expectedText, timeoutMs) {
  return waitFor(
    async () => {
      for (const frame of page.frames()) {
        try {
          const bodyText = await frame.locator('body').innerText({ timeout: 250 });
          if (bodyText.includes(expectedText)) {
            return true;
          }
        } catch {
          // Frame is still loading or cross-origin; keep polling.
        }
      }
      return false;
    },
    `frame text ${expectedText}`,
    timeoutMs,
  );
}

async function apiJson(request, url, options = {}) {
  const response = await request.fetch(url, options);
  assert(response.ok(), `${options.method || 'GET'} ${url} failed with ${response.status()}`);
  return response.json();
}

async function waitForWorkerState(request, baseUrl, workerId, expectedStates, timeoutMs) {
  const allowed = new Set(Array.isArray(expectedStates) ? expectedStates : [expectedStates]);
  return waitFor(
    async () => {
      const live = await apiJson(request, absoluteUrl(baseUrl, `/v1/workers/${workerId}/live`));
      const state = String((live.worker || {}).state || '');
      return allowed.has(state) ? live : false;
    },
    `worker state ${Array.from(allowed).join('/')}`,
    timeoutMs,
  );
}

async function waitForRunState(request, baseUrl, runId, expectedStates, timeoutMs) {
  const allowed = new Set(Array.isArray(expectedStates) ? expectedStates : [expectedStates]);
  return waitFor(
    async () => {
      const run = await apiJson(request, absoluteUrl(baseUrl, `/v1/runs/${runId}`));
      return allowed.has(String(run.state || '')) ? run : false;
    },
    `run state ${Array.from(allowed).join('/')}`,
    timeoutMs,
  );
}

function assertShortRefPath(value, expectedPrefix, label) {
  const pathname = new URL(value, 'http://example.test').pathname;
  const escaped = expectedPrefix.replace(/\//g, '\\/');
  assert(new RegExp(`^${escaped}ghr_[A-Za-z0-9_-]+$`).test(pathname), `${label} did not use ${expectedPrefix} short ref: ${value}`);
}

function validateDownloadedArtifact(relativePath, buffer) {
  const ext = path.extname(relativePath).toLowerCase();
  const text = buffer.toString('utf8');
  if (['.md', '.csv', '.html'].includes(ext)) {
    assert(text.includes(PUBLIC_MARKER), `${relativePath} download missed public marker`);
    return;
  }
  if (ext === '.pdf') {
    assert(buffer.slice(0, 5).toString('ascii') === '%PDF-', `${relativePath} is not a PDF`);
    assert(buffer.includes(Buffer.from('%%EOF')), `${relativePath} is missing PDF EOF marker`);
    return;
  }
  if (ext === '.xlsx') {
    assert(buffer.slice(0, 2).toString('ascii') === 'PK', `${relativePath} is not a ZIP package`);
    assert(buffer.includes(Buffer.from('xl/workbook.xml')), `${relativePath} is missing workbook member`);
    return;
  }
  if (ext === '.docx') {
    assert(buffer.slice(0, 2).toString('ascii') === 'PK', `${relativePath} is not a ZIP package`);
    assert(buffer.includes(Buffer.from('word/document.xml')), `${relativePath} is missing document member`);
    return;
  }
  if (ext === '.pptx') {
    assert(buffer.slice(0, 2).toString('ascii') === 'PK', `${relativePath} is not a ZIP package`);
    assert(buffer.includes(Buffer.from('ppt/presentation.xml')), `${relativePath} is missing presentation member`);
    return;
  }
  throw new Error(`No artifact validator for ${relativePath}`);
}

async function openAndDownloadArtifact(page, item, fixture, outputDir, timeoutMs) {
  const baseUrl = fixture.base_url;
  const openUrl = absoluteUrl(baseUrl, item.open_url);
  await page.goto(openUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('h1').waitFor({ timeout: timeoutMs });
  const snapshot = await topLevelSnapshot(page);
  assertNoForbiddenPublicText(snapshot, `artifact preview ${item.path}`);
  assertShortRefPath(page.url(), '/v1/link-refs/', `artifact preview URL for ${item.path}`);

  const title = await page.locator('h1').innerText();
  assert(title.includes(path.basename(item.path)), `artifact preview did not show filename for ${item.path}`);

  const ext = path.extname(item.path).toLowerCase();
  if (['.md', '.csv', '.html'].includes(ext)) {
    const previewText = await page.locator('.artifact-preview').innerText({ timeout: timeoutMs });
    assert(previewText.includes(PUBLIC_MARKER), `artifact preview missed marker for ${item.path}`);
  } else {
    const readyText = await page.locator('.no-preview').innerText({ timeout: timeoutMs });
    assert(readyText.includes('File is ready'), `binary artifact landing page did not render for ${item.path}`);
  }

  const downloadHref = await page.getByRole('link', { name: 'Download file' }).getAttribute('href');
  const workspaceHref = await page.getByRole('link', { name: 'View workspace' }).getAttribute('href');
  assertShortRefPath(downloadHref || '', '/v1/link-refs/', `download link for ${item.path}`);
  assertShortRefPath(workspaceHref || '', '/w/', `workspace link for ${item.path}`);

  const downloadPromise = page.waitForEvent('download', { timeout: timeoutMs });
  await page.getByRole('link', { name: 'Download file' }).click();
  const download = await downloadPromise;
  const safeName = item.path.replace(/[^A-Za-z0-9_.-]+/g, '__');
  const savedPath = path.join(outputDir, 'downloads', safeName);
  fs.mkdirSync(path.dirname(savedPath), { recursive: true });
  await download.saveAs(savedPath);
  validateDownloadedArtifact(item.path, fs.readFileSync(savedPath));

  return {
    path: item.path,
    preview: ['.md', '.csv', '.html'].includes(ext) ? 'text' : 'landing',
    downloaded: true,
  };
}

async function runBrowserQa({ chromium, fixture, headed, timeoutMs }) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: !headed });
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  const consoleIssues = [];
  const requestFailures = [];
  page.on('console', (message) => {
    if (['warning', 'error'].includes(message.type())) {
      consoleIssues.push({ type: message.type(), text: message.text().slice(0, 200) });
    }
  });
  page.on('pageerror', (error) => {
    consoleIssues.push({ type: 'pageerror', text: error.message.slice(0, 200) });
  });
  page.on('requestfailed', (request) => {
    const failure = request.failure();
    if (
      request.url().includes('/v1/link-refs/') &&
      failure &&
      /(?:net::ERR_ABORTED|NS_BINDING_ABORTED)/i.test(failure.errorText || '')
    ) {
      return;
    }
    requestFailures.push(shortUrlForEvidence(request.url(), fixture));
  });

  const request = context.request;
  const baseUrl = fixture.base_url;
  const workerId = fixture.worker.worker_id;
  const projectId = fixture.project.project_id;

  try {
    await page.goto(fixture.project_url, { waitUntil: 'domcontentloaded' });
    await page.locator('h1').filter({ hasText: 'Public-safe local browser QA' }).waitFor({ timeout: timeoutMs });
    assert((await page.locator('#selected-worker-profile').innerText()).includes('codex-cli'), 'project page did not show Codex profile');
    assert((await page.locator('#selected-worker-execution').innerText()).includes('docker'), 'project page did not show docker execution');
    assert((await page.locator('#latest-output').innerText()).includes(PUBLIC_MARKER), 'project latest output missed marker');
    assert((await page.locator('#latest-output').innerText()).includes(INPUT_MARKER), 'project latest output missed input marker');
    await waitForFrameText(page, PUBLIC_MARKER, timeoutMs);

    await page.goto(fixture.worker_url, { waitUntil: 'domcontentloaded' });
    await page.locator('h1').filter({ hasText: 'Codex fixture worker' }).waitFor({ timeout: timeoutMs });
    const workspaceText = await page.locator('#workspace-items').innerText({ timeout: timeoutMs });
    for (const expected of EXPECTED_ARTIFACTS) {
      assert(workspaceText.includes(expected), `worker console did not list ${expected}`);
    }

    await page.goto(fixture.view_url, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Pause', exact: true }).waitFor({ timeout: timeoutMs });
    await waitForFrameText(page, PUBLIC_MARKER, timeoutMs);

    const live = await apiJson(request, absoluteUrl(baseUrl, `/v1/workers/${workerId}/live`));
    const artifacts = (live.artifacts && live.artifacts.items) || [];
    const byPath = new Map(artifacts.map((item) => [String(item.path || ''), item]));
    for (const expected of EXPECTED_ARTIFACTS) {
      assert(byPath.has(expected), `live artifact list missed ${expected}`);
      const item = byPath.get(expected);
      assertShortRefPath(String(item.open_url || ''), '/v1/link-refs/', `open_url for ${expected}`);
      assertShortRefPath(String(item.download_url || ''), '/v1/link-refs/', `download_url for ${expected}`);
      assertNoForbiddenPublicText(
        { url: '', text: `${item.open_url}\n${item.download_url}`, hrefs: [] },
        `artifact action URLs for ${expected}`,
      );
    }

    const artifactResults = [];
    for (const expected of EXPECTED_ARTIFACTS) {
      artifactResults.push(await openAndDownloadArtifact(page, byPath.get(expected), fixture, OUTPUT_DIR, timeoutMs));
    }
    const inputSummaryResult = artifactResults.find((result) => result.path === 'output/input-summary.md');
    assert(inputSummaryResult && inputSummaryResult.downloaded, 'input summary artifact was not downloaded');

    await page.goto(absoluteUrl(baseUrl, byPath.get('answer.md').open_url), { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'View workspace' }).click();
    await page.waitForURL(/\/w\/ghr_[A-Za-z0-9_-]+$/, { timeout: timeoutMs });
    let snapshot = await topLevelSnapshot(page);
    assertNoForbiddenPublicText(snapshot, 'member workspace view', { workerId, projectId, forbidRawIds: true });
    await waitForFrameText(page, PUBLIC_MARKER, timeoutMs);
    const workspaceUrl = page.url();
    await page.reload({ waitUntil: 'domcontentloaded' });
    assert(page.url() === workspaceUrl, 'workspace short-ref URL changed after refresh');
    snapshot = await topLevelSnapshot(page);
    assertNoForbiddenPublicText(snapshot, 'member workspace view after refresh', {
      workerId,
      projectId,
      forbidRawIds: true,
    });
    await waitForFrameText(page, PUBLIC_MARKER, timeoutMs);

    const invalidRef = await request.get(absoluteUrl(baseUrl, '/w/ghr_invalidlocalbrowserqa0000'));
    assert([401, 403, 404].includes(invalidRef.status()), `invalid /w ref returned ${invalidRef.status()}`);

    const active = await apiJson(request, absoluteUrl(baseUrl, `/v1/workers/${workerId}/assign`), {
      method: 'POST',
      data: {
        instruction: `GH_QA_SLEEP ${ACTIVE_RUN_MARKER}: keep this synthetic run active until the browser QA interrupts it.`,
      },
    });
    await waitForRunState(request, baseUrl, active.run_id, 'running', timeoutMs);
    await page.goto(workspaceUrl, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    await waitForWorkerState(request, baseUrl, workerId, 'paused', timeoutMs);
    await page.getByRole('button', { name: 'Resume', exact: true }).click();
    await waitForWorkerState(request, baseUrl, workerId, ['running', 'ready'], timeoutMs);
    await page.getByRole('button', { name: 'Interrupt', exact: true }).click();
    await waitForRunState(request, baseUrl, active.run_id, 'interrupted', timeoutMs);
    await waitForWorkerState(request, baseUrl, workerId, 'ready', timeoutMs);

    const terminating = await apiJson(request, absoluteUrl(baseUrl, `/v1/workers/${workerId}/assign`), {
      method: 'POST',
      data: {
        instruction: `GH_QA_SLEEP ${TERMINATE_RUN_MARKER}: keep this synthetic run active until the browser QA terminates it.`,
      },
    });
    await waitForRunState(request, baseUrl, terminating.run_id, 'running', timeoutMs);
    await page.goto(workspaceUrl, { waitUntil: 'domcontentloaded' });
    const terminateResponsePromise = page.waitForResponse(
      (response) => response.url().includes('/actions/terminate') && response.request().method() === 'POST',
      { timeout: timeoutMs },
    );
    await page.getByRole('button', { name: 'Terminate', exact: true }).click();
    const terminateResponse = await terminateResponsePromise;
    assert(terminateResponse.ok(), `terminate action returned ${terminateResponse.status()}: ${await terminateResponse.text()}`);
    await waitForWorkerState(request, baseUrl, workerId, 'terminated', timeoutMs);

    await page.goto(fixture.worker_url, { waitUntil: 'domcontentloaded' });
    await waitFor(
      async () => {
        const events = await page.locator('#event-list').innerText({ timeout: 500 });
        return (
          events.includes('worker.paused') &&
          events.includes('worker.resumed') &&
          events.includes('worker.interrupted') &&
          events.includes('worker.terminated')
        );
      },
      'worker console lifecycle events',
      timeoutMs,
    );

    const screenshotPath = path.join(OUTPUT_DIR, 'local-browser-user-grade-qa.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });

    assert(consoleIssues.length === 0, `browser console warnings/errors: ${JSON.stringify(consoleIssues)}`);
    assert(requestFailures.length === 0, `browser request failures: ${JSON.stringify(requestFailures)}`);

    const summary = {
      schema: 'glasshive.local-browser-user-grade-qa.v1',
      fixture: 'local_user_grade_fixture.py',
      result: 'pass',
      project_page: 'pass',
      worker_console: 'pass',
      watch_workspace_short_ref: 'pass',
      refresh_persistence: 'pass',
      active_run_degraded_path: 'pause_resume_interrupt_terminate_pass',
      input_materialization: 'inline_and_source_path_pass',
      redaction: {
        signed_query_fields: 'absent',
        raw_signed_link_routes: 'absent',
        raw_worker_ids_on_member_workspace: 'absent',
        invalid_workspace_ref_rejected: true,
      },
      artifacts: artifactResults,
      browser: {
        console_issue_count: consoleIssues.length,
        request_failure_count: requestFailures.length,
      },
      local_outputs: {
        summary: 'output/playwright/glasshive-deep-research/local-browser-user-grade-qa.json',
        screenshot: 'output/playwright/glasshive-deep-research/local-browser-user-grade-qa.png',
        downloads: 'output/playwright/glasshive-deep-research/downloads/',
      },
    };
    const summaryPath = path.join(OUTPUT_DIR, 'local-browser-user-grade-qa.json');
    fs.writeFileSync(summaryPath, `${JSON.stringify(summary, null, 2)}\n`);
    return summary;
  } finally {
    await browser.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const stateRoot =
    args.stateRoot ||
    path.join(os.tmpdir(), `glasshive-local-browser-user-grade-${process.pid}-${Date.now()}`);
  const python = findPython(args.python);
  const { chromium } = loadPlaywright();
  let fixtureProcess;
  try {
    const started = await startFixture({ python, stateRoot, timeoutMs: args.timeoutMs });
    fixtureProcess = started.child;
    const summary = await runBrowserQa({
      chromium,
      fixture: started.fixture,
      headed: args.headed,
      timeoutMs: args.timeoutMs,
    });
    console.log(JSON.stringify(summary, null, 2));
  } finally {
    await stopFixture(fixtureProcess);
  }
}

main().catch((error) => {
  console.error(`local_browser_user_grade_qa failed: ${error.stack || error.message}`);
  process.exit(1);
});
