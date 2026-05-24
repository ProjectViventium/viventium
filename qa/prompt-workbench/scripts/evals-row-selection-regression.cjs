#!/usr/bin/env node

const path = require('node:path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const WORKBENCH_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'prompt-workbench');
const { chromium } = require(path.join(WORKBENCH_ROOT, 'node_modules', 'playwright'));

function parseArgs(argv) {
  const args = {
    url: process.env.PROMPT_WORKBENCH_URL || 'http://127.0.0.1:8781',
    viewports: [
      { width: 1024, height: 720 },
      { width: 1280, height: 720 },
      { width: 1910, height: 997 },
    ],
  };

  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--url' && argv[index + 1]) {
      args.url = argv[index + 1];
      index += 1;
    } else if (value === '--viewports' && argv[index + 1]) {
      args.viewports = argv[index + 1].split(',').map((entry) => {
        const [width, height] = entry.split('x').map((part) => Number.parseInt(part, 10));
        if (!Number.isFinite(width) || !Number.isFinite(height)) {
          throw new Error(`Invalid viewport "${entry}". Use WIDTHxHEIGHT.`);
        }
        return { width, height };
      });
      index += 1;
    }
  }

  return args;
}

async function openEvals(page, url) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  const identityNode = page.getByText('Identity', { exact: true }).first();
  await identityNode.click({ timeout: 10_000 });

  const evalsTab = page.getByText('Evals', { exact: true }).first();
  await evalsTab.click({ timeout: 10_000 });
  await page.locator('.eval-table tbody tr').first().waitFor({ state: 'visible', timeout: 10_000 });
}

async function runViewport(browser, url, viewport) {
  const page = await browser.newPage({ viewport });
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];

  page.on('console', (message) => {
    if (['error', 'warning'].includes(message.type())) {
      consoleMessages.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`));

  await openEvals(page, url);

  const rows = page.locator('.eval-table tbody tr');
  const rowCount = await rows.count();
  if (rowCount < 3) {
    throw new Error(`Expected at least 3 eval rows, found ${rowCount}.`);
  }

  const selections = [];
  for (let index = 0; index < 3; index += 1) {
    const row = rows.nth(index);
    const family = (await row.locator('td').nth(0).innerText()).trim();
    const caseId = (await row.locator('td').nth(1).innerText()).trim();
    await row.click({ timeout: 10_000 });
    const editorTitle = (await page.locator('.eval-case-editor strong').first().innerText()).trim();
    const expectedTitle = `${family}/${caseId}`;
    if (editorTitle !== expectedTitle) {
      throw new Error(`Expected editor title "${expectedTitle}" after row ${index + 1}, got "${editorTitle}".`);
    }
    selections.push(expectedTitle);
  }

  const tableBox = await page.locator('.eval-table-wrap').boundingBox();
  const editorBox = await page.locator('.eval-case-editor').boundingBox();
  const overlapsEditor = Boolean(
    tableBox && editorBox
      && tableBox.x < editorBox.x + editorBox.width
      && tableBox.x + tableBox.width > editorBox.x
      && tableBox.y < editorBox.y + editorBox.height
      && tableBox.y + tableBox.height > editorBox.y,
  );
  if (overlapsEditor) {
    throw new Error(`Eval table overlaps editor at ${viewport.width}x${viewport.height}.`);
  }

  if (pageErrors.length || failedRequests.length || consoleMessages.length) {
    throw new Error(JSON.stringify({ pageErrors, failedRequests, consoleMessages }, null, 2));
  }

  await page.close();
  return {
    viewport: `${viewport.width}x${viewport.height}`,
    selections,
    tableBox,
    editorBox,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const viewport of args.viewports) {
      results.push(await runViewport(browser, args.url, viewport));
    }
  } finally {
    await browser.close();
  }

  console.log(JSON.stringify({ status: 'PASS', url: args.url, results }, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({ status: 'FAIL', error: error.message }, null, 2));
  process.exit(1);
});
