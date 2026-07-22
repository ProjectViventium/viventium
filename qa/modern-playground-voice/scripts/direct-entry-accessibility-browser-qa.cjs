#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const HEADED = process.argv.includes('--headed');
const CLIENT_BASE = (process.env.VIVENTIUM_QA_CLIENT_BASE || '').replace(/\/$/, '');
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const PLAYWRIGHT_ROOT = path.resolve(
  process.env.VIVENTIUM_QA_PLAYWRIGHT_ROOT ||
    path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat'),
);

function fail(message) {
  throw new Error(message);
}

function assertSafeInputs() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    fail('Direct-entry browser QA is local-only and forbidden in CI/production');
  }
  if (!CLIENT_BASE) {
    fail('Set VIVENTIUM_QA_CLIENT_BASE to the isolated loopback playground');
  }
  const target = new URL(CLIENT_BASE);
  if (!new Set(['127.0.0.1', 'localhost', '::1']).has(target.hostname)) {
    fail('Direct-entry browser QA accepts loopback targets only');
  }
  if (!fs.existsSync(path.join(PLAYWRIGHT_ROOT, 'node_modules', 'playwright'))) {
    fail('Playwright must already exist in VIVENTIUM_QA_PLAYWRIGHT_ROOT');
  }
}

function outputDirectory() {
  const configured = (process.env.VIVENTIUM_QA_PRIVATE_EVIDENCE_DIR || '').trim();
  if (configured) {
    const resolved = path.resolve(configured);
    fs.mkdirSync(resolved, { recursive: true, mode: 0o700 });
    return resolved;
  }
  return fs.mkdtempSync(path.join(os.tmpdir(), 'viventium-modern-browser-qa-'));
}

async function main() {
  assertSafeInputs();
  const { chromium } = require(path.join(PLAYWRIGHT_ROOT, 'node_modules', 'playwright'));
  const evidenceDirectory = outputDirectory();
  const browser = await chromium.launch({ headless: !HEADED });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    forcedColors: 'active',
    reducedMotion: 'reduce',
    serviceWorkers: 'block',
  });
  const page = await context.newPage();
  const consoleProblems = [];
  const failedResponses = [];
  const externalRequests = [];

  page.on('console', (message) => {
    if (message.type() === 'error' || message.type() === 'warning') {
      consoleProblems.push(`${message.type()}: ${message.text().slice(0, 240)}`);
    }
  });
  page.on('response', (response) => {
    if (response.status() >= 400) {
      failedResponses.push({ status: response.status(), path: new URL(response.url()).pathname });
    }
  });
  await context.route('**/*', async (route) => {
    const requestUrl = new URL(route.request().url());
    if (!new Set(['127.0.0.1', 'localhost', '::1']).has(requestUrl.hostname)) {
      externalRequests.push(requestUrl.hostname);
      await route.abort('blockedbyclient');
      return;
    }
    await route.continue();
  });

  try {
    await page.goto(CLIENT_BASE, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.getByText('Chat live with Viventium', { exact: true }).waitFor({ state: 'visible' });
    const directEntryButton = page.getByRole('button', { name: 'Open from Viventium' });
    if (!(await directEntryButton.isDisabled())) {
      fail('Direct entry did not fail closed before a Viventium conversation handoff');
    }
    await page
      .getByText(
        'Open Voice from a Viventium conversation. This page joins that conversation securely.',
        { exact: true },
      )
      .waitFor({ state: 'visible' });

    const focusStops = [];
    for (let index = 0; index < 16; index += 1) {
      await page.keyboard.press('Tab');
      const focused = await page.evaluate(() => {
        const element = document.activeElement;
        if (!(element instanceof HTMLElement) || element === document.body) {
          return null;
        }
        const name =
          element.getAttribute('aria-label') ||
          element.getAttribute('title') ||
          element.textContent?.trim() ||
          element.getAttribute('href') ||
          element.tagName;
        return `${element.tagName.toLowerCase()}:${name.slice(0, 100)}`;
      });
      if (focused && !focusStops.includes(focused)) {
        focusStops.push(focused);
      }
    }
    if (focusStops.length < 3) {
      fail(`Expected at least three named keyboard stops; found ${focusStops.length}`);
    }

    await page.setViewportSize({ width: 320, height: 760 });
    const layout = await page.evaluate(() => {
      const graphic = document.querySelector('svg');
      const graphicBox = graphic?.getBoundingClientRect();
      return {
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight,
        graphicY: graphicBox?.y ?? null,
      };
    });
    if (layout.scrollWidth > layout.clientWidth) {
      fail(`Narrow layout overflowed by ${layout.scrollWidth - layout.clientWidth}px`);
    }
    if (layout.graphicY === null || layout.graphicY < 0) {
      fail('The first setup graphic is clipped above the narrow viewport');
    }

    const retainedMotion = await page.evaluate(() => {
      const parse = (value) =>
        value.split(',').map((entry) => {
          const normalized = entry.trim();
          if (normalized.endsWith('ms')) {
            return Number.parseFloat(normalized) || 0;
          }
          if (normalized.endsWith('s')) {
            return (Number.parseFloat(normalized) || 0) * 1000;
          }
          return 0;
        });
      return [...document.querySelectorAll('*')].filter((element) => {
        const style = getComputedStyle(element);
        return [...parse(style.animationDuration), ...parse(style.transitionDuration)].some(
          (duration) => duration > 0,
        );
      }).length;
    });
    if (retainedMotion !== 0) {
      fail(`Reduce Motion left ${retainedMotion} elements with non-zero duration`);
    }

    await page.screenshot({
      path: path.join(evidenceDirectory, 'modern-direct-entry-320x760.png'),
      fullPage: true,
    });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.getByText('Chat live with Viventium', { exact: true }).waitFor({ state: 'visible' });

    if (externalRequests.length > 0 || failedResponses.length > 0 || consoleProblems.length > 0) {
      fail(
        `Browser ledger was not clean (external=${externalRequests.length}, http=${failedResponses.length}, console=${consoleProblems.length})`,
      );
    }

    const result = {
      result: 'PASS',
      headed: HEADED,
      directEntryFailClosed: true,
      focusStops: focusStops.length,
      narrowLayout: layout,
      retainedMotion,
      reload: 'PASS',
      externalRequests: 0,
      failedResponses: 0,
      consoleProblems: 0,
      evidenceDirectory: process.env.VIVENTIUM_QA_PRIVATE_EVIDENCE_DIR ? '<private>' : '<temp>',
    };
    fs.writeFileSync(path.join(evidenceDirectory, 'result.json'), `${JSON.stringify(result, null, 2)}\n`, {
      mode: 0o600,
    });
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ result: 'FAIL', error: error.message }, null, 2));
  process.exitCode = 1;
});
