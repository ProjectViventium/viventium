#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const CLIENT_BASE = (process.env.VIVENTIUM_QA_CLIENT_BASE || "").replace(/\/$/, "");
const EMAIL = process.env.VIVENTIUM_QA_EMAIL || "";
const PASSWORD = process.env.VIVENTIUM_QA_PASSWORD || "";
const REGISTER = process.argv.includes("--register");
const HEADED = process.argv.includes("--headed");

function fail(message) {
  throw new Error(message);
}

function assertSafeInputs() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    fail("Easy Install browser QA is local-only and is forbidden in CI/production");
  }
  if (!CLIENT_BASE || !EMAIL || !PASSWORD) {
    fail("Set VIVENTIUM_QA_CLIENT_BASE, VIVENTIUM_QA_EMAIL, and VIVENTIUM_QA_PASSWORD");
  }
  const target = new URL(CLIENT_BASE);
  if (!new Set(["127.0.0.1", "localhost", "::1"]).has(target.hostname)) {
    fail("Easy Install browser QA only accepts an explicit loopback target");
  }
}

async function register(page) {
  await page.goto(`${CLIENT_BASE}/register`, { waitUntil: "domcontentloaded" });
  await page.getByLabel("Full name").fill("Easy Install Native QA");
  await page.getByLabel("Username (optional)").fill(`easy-install-qa-${Date.now()}`);
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByTestId("password").fill(PASSWORD);
  await page.getByTestId("confirm_password").fill(PASSWORD);
  await page.getByLabel("Submit registration").click();
  await page.waitForURL(/\/login(?:\?|$)/, { timeout: 15_000 });
}

async function verifySignedOutFeelingsRedirect(page) {
  await page.goto(`${CLIENT_BASE}/feelings`, { waitUntil: "domcontentloaded" });
  await page.waitForURL(/\/login(?:\?|$)/, { timeout: 15_000 });
  await page.getByText("Welcome back", { exact: true }).waitFor({ state: "visible" });
}

async function login(page) {
  const destination = encodeURIComponent("/c/new?setup=accounts");
  await page.goto(`${CLIENT_BASE}/login?redirect_to=${destination}`, {
    waitUntil: "domcontentloaded",
  });
  await page.locator('input[name="email"]').fill(EMAIL);
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.locator('input[name="password"]').press("Enter");
  await page.locator("#connected-accounts-label").waitFor({
    state: "visible",
    timeout: 20_000,
  });
}

async function main() {
  assertSafeInputs();
  const { chromium } = require(path.join(LIBRECHAT_ROOT, "node_modules", "playwright"));
  const evidenceDir = fs.mkdtempSync(path.join(os.tmpdir(), "viventium-easy-install-browser-qa-"));
  const browser = await chromium.launch({ headless: !HEADED });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    serviceWorkers: "block",
  });
  const page = await context.newPage();
  const failures = [];
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failures.push({ status: response.status(), path: new URL(response.url()).pathname });
    }
  });

  try {
    await verifySignedOutFeelingsRedirect(page);
    if (REGISTER) {
      await register(page);
    }
    await login(page);
    const connectButton = page.getByRole("button", { name: "Connect OpenAI Account" });
    if (!(await connectButton.isVisible()) || page.url().includes("setup=accounts")) {
      fail("Connected Accounts handoff is not visibly ready with a clean URL");
    }
    await page.screenshot({ path: path.join(evidenceDir, "connected-accounts.png"), fullPage: true });

    const startedAt = Date.now();
    const [popup, response] = await Promise.all([
      page.waitForEvent("popup", { timeout: 10_000 }),
      page.waitForResponse(
        (candidate) => candidate.url().includes("/api/connected-accounts/openai/start"),
        { timeout: 10_000 },
      ),
      connectButton.click(),
    ]);
    const providerStart = await response.json();
    const authorizationUrl = new URL(providerStart.authUrl);
    await popup.close();
    await page.waitForTimeout(1_500);
    if (!(await connectButton.isVisible())) {
      fail("Cancelling provider sign-in did not leave an immediate retry action");
    }

    const [retryPopup, retryResponse] = await Promise.all([
      page.waitForEvent("popup", { timeout: 10_000 }),
      page.waitForResponse(
        (candidate) => candidate.url().includes("/api/connected-accounts/openai/start"),
        { timeout: 10_000 },
      ),
      connectButton.click(),
    ]);
    if (retryResponse.status() !== 200) {
      fail(`Provider retry returned HTTP ${retryResponse.status()}`);
    }
    await retryPopup.close();
    await page.waitForTimeout(1_500);
    if (!(await connectButton.isVisible())) {
      fail("A second cancelled provider attempt corrupted the retry state");
    }

    await page.getByRole("button", { name: "Close Settings" }).click();
    const feelingsLink = page.getByRole("button", { name: "Feelings" });
    if (!(await feelingsLink.isVisible())) {
      fail("Feelings is not discoverable from the ordinary right-side control panel");
    }
    await feelingsLink.click();
    await page.waitForURL(/\/feelings$/, { timeout: 10_000 });
    await page.getByText("Feeling spectrum", { exact: true }).waitFor({ state: "visible" });
    await page.screenshot({ path: path.join(evidenceDir, "feelings.png"), fullPage: true });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByText("Feeling spectrum", { exact: true }).waitFor({ state: "visible" });

    console.log(
      JSON.stringify(
        {
          result: "PASS",
          registrationRun: REGISTER,
          connectedAccounts: "visible",
          setupUrlConsumed: true,
          providerStart: {
            status: response.status(),
            elapsedMs: Date.now() - startedAt,
            flowMode: providerStart.flowMode,
            authorizationOrigin: authorizationUrl.origin,
            authorizationPath: authorizationUrl.pathname,
          },
          providerCompletion: "NOT_RUN",
          providerCancelRetry: "PASS",
          providerCancelRetryAttempts: 2,
          signedOutFeelingsRedirect: "PASS",
          feelingsControlPanelDiscovery: "PASS",
          feelingsRefresh: "PASS",
          unexpectedHttpFailures: failures,
          evidenceDirectory: "<temp>",
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ result: "FAIL", error: error.message }, null, 2));
  process.exitCode = 1;
});
