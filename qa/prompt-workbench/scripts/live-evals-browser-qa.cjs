#!/usr/bin/env node
"use strict";

/**
 * Real Prompt Workbench browser acceptance for activation and Feelings evals.
 * Detailed artifacts remain in private App Support; stdout is counts/hashes only.
 */

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const WORKBENCH_STATE = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
  "state",
  "prompt-workbench",
  "state.json",
);
const PRIVATE_WORKBENCH_ROOT = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
  "private-user-data",
  "prompt-workbench",
);
const HEADED = process.argv.includes("--headed");
const FEELINGS_MAX_CASES = Math.max(
  1,
  Number.parseInt(
    process.env.VIVENTIUM_WORKBENCH_FEELINGS_MAX_CASES || "3",
    10,
  ) || 3,
);
const FEELINGS_RUN_TIMEOUT_MS = Math.max(
  15 * 60_000,
  FEELINGS_MAX_CASES * 420_000,
);
const REQUIRED_ESCAPED_FEELINGS_CASES = [
  "feelings_escaped_mixed_state_high_play_is_unmistakable",
  "feelings_escaped_mixed_state_low_play_contrast",
  "feelings_voice_xai_escaped_mixed_state_high_play",
  "feelings_active_range_custom_addition_changes_high_play",
  "feelings_inactive_range_custom_addition_stays_out",
];

function shortHash(value) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, 12);
}

function safeError(value) {
  return String(value || "workbench_browser_qa_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(/workbench_token=[^&\s]+/gi, "workbench_token=<redacted>")
    .replace(/\s+/g, " ")
    .slice(0, 320);
}

function readWorkbenchState() {
  if (!fs.existsSync(WORKBENCH_STATE)) {
    throw new Error(
      "Prompt Workbench state is missing; start it before browser QA",
    );
  }
  const state = JSON.parse(fs.readFileSync(WORKBENCH_STATE, "utf8"));
  const authUrl = String(state.authUrl || "");
  const parsed = new URL(authUrl);
  if (!["127.0.0.1", "localhost"].includes(parsed.hostname)) {
    throw new Error("Prompt Workbench QA refuses a non-loopback URL");
  }
  if (!parsed.searchParams.get("workbench_token")) {
    throw new Error("Prompt Workbench launch token is missing");
  }
  return { authUrl, port: Number(state.port || parsed.port || 8781) };
}

async function readRuns(page) {
  return page.evaluate(async () => {
    const token =
      localStorage.getItem("viventium.promptWorkbench.launchToken") || "";
    const response = await fetch("/api/evals/runs", {
      headers: { "x-viventium-workbench-token": token },
      cache: "no-store",
    });
    const body = await response.json();
    return { ok: response.ok, runs: body.runs || [] };
  });
}

async function openEvals(page) {
  const tab = page
    .locator(".flexlayout__tab_button")
    .filter({ hasText: /^Evals$/ })
    .first();
  await tab.waitFor({ state: "visible", timeout: 30_000 });
  await tab.click();
  await page.getByText("Run Eval Cases", { exact: true }).waitFor();
}

async function configureFamily(page, { family, maxCases, live, caseIds = [] }) {
  const designer = page.locator(".eval-designer");
  const linkedOnlyToggle = designer
    .locator("label")
    .filter({ hasText: "show only cases linked to this prompt" })
    .locator('input[type="checkbox"]');
  if (await linkedOnlyToggle.isChecked()) await linkedOnlyToggle.click();
  await designer
    .locator("label")
    .filter({ hasText: /^Family/ })
    .locator("select")
    .selectOption(family);
  await designer
    .locator("label")
    .filter({ hasText: /^Cases/ })
    .locator("input")
    .fill(String(maxCases));
  const liveToggle = designer
    .locator("label")
    .filter({ hasText: "live exact-model run" })
    .locator('input[type="checkbox"]');
  if ((await liveToggle.isChecked()) !== live) await liveToggle.click();
  const clearSelection = designer.getByRole("button", {
    name: "Clear",
    exact: true,
  });
  if (await clearSelection.isVisible().catch(() => false)) {
    await clearSelection.click();
  }
  for (const caseId of caseIds) {
    await designer
      .getByRole("checkbox", { name: `Include ${caseId}`, exact: true })
      .check();
  }
}

async function runUiEval(page, { family, maxCases, live, timeoutMs, caseIds = [] }) {
  console.log(JSON.stringify({ step: "eval_started", family, live, maxCases }));
  await configureFamily(page, { family, maxCases, live, caseIds });
  const button = page.locator(".eval-designer").getByRole("button", {
    name: live ? "Run live eval" : "Run preview",
    exact: true,
  });
  const responsePromise = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/evals/run" &&
      response.request().method() === "POST",
    { timeout: timeoutMs },
  );
  await button.click();
  const response = await responsePromise;
  const run = await response.json();
  if (!response.ok()) {
    throw new Error(
      `Workbench ${family} run failed with HTTP ${response.status()}`,
    );
  }
  if (run.family !== family || run.live !== live) {
    throw new Error(`Workbench returned the wrong ${family} run identity`);
  }
  await page
    .getByText(run.id, { exact: true })
    .first()
    .waitFor({ timeout: 30_000 });
  console.log(
    JSON.stringify({
      step: "eval_finished",
      family,
      live,
      returnCode: run.returnCode,
    }),
  );
  return run;
}

async function openRunLineage(page, run) {
  const row = page
    .locator(".run-row")
    .filter({ has: page.getByText(run.id, { exact: true }) })
    .first();
  await row.scrollIntoViewIfNeeded();
  const disclosure = row.getByText("Prompt and runtime context dependencies", {
    exact: true,
  });
  const details = row.locator("details");
  if (!(await details.evaluate((element) => element.open)))
    await disclosure.click();
  const visibleText = await row.innerText();
  return {
    feelingsContextVisible: visibleText.includes("<viventium_feeling_state>"),
    privateValuePolicyVisible: visibleText.includes(
      "private value not recorded",
    ),
    promptDependencyCount: run.lineageManifest?.promptDependencies?.length ?? 0,
    runtimeContextDependencyCount:
      run.lineageManifest?.runtimeContextDependencies?.length ?? 0,
  };
}

function privateRunDir(run) {
  return path.join(
    PRIVATE_WORKBENCH_ROOT,
    "eval-runs",
    run.artifactName || run.id,
  );
}

function activationEvidence(run) {
  const filePath = path.join(privateRunDir(run), "activation-model-eval.json");
  if (!fs.existsSync(filePath))
    throw new Error("Activation eval evidence is missing");
  const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const summary = payload.summary || {};
  return {
    status: summary.status,
    resultCount: Number(summary.resultCount || 0),
    passCount: Number(summary.passCount || 0),
    unavailableCount: Number(summary.unavailableCount || 0),
    fallbacksEnabled: summary.fallbacksEnabled === true,
    qaUserContextEnabled: summary.qaUserContext?.enabled === true,
  };
}

function feelingsEvidence(run) {
  const filePath = path.join(privateRunDir(run), "exact-model-eval.json");
  if (!fs.existsSync(filePath))
    throw new Error("Feelings exact-model evidence is missing");
  const payload = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const summary = payload.summary || {};
  return {
    selectedCount: Number(summary.selectedCaseCount || 0),
    completedCount: Number(summary.completedCount || 0),
    failedCount: Number(summary.failedCount || 0),
    semanticPassedCount: Number(summary.semanticPassedCount || 0),
    semanticFailedCount: Number(summary.semanticFailedCount || 0),
    semanticJudgeUnavailableCount: Number(
      summary.semanticJudgeUnavailableCount || 0,
    ),
    duplicateCount: (summary.duplicateResponseQualityFailures || []).length,
    unresolvedAsyncCount: (summary.unresolvedAsyncQualityFailures || []).length,
  };
}

async function main() {
  const state = readWorkbenchState();
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const outputDir = path.join(PRIVATE_WORKBENCH_ROOT, "browser-evals", stamp);
  fs.mkdirSync(outputDir, { recursive: true });
  const result = {
    source: "local-dev-runtime",
    checks: {},
    metrics: {},
    artifacts: [],
  };
  const { chromium } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
  );
  const browser = await chromium.launch({
    channel: "chrome",
    headless: !HEADED,
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1512, height: 1050 },
    });
    await context.addInitScript(() => {
      localStorage.removeItem("viventium.promptWorkbench.dockLayout.v5");
    });
    const page = await context.newPage();
    page.setDefaultTimeout(30_000);
    const consoleErrors = [];
    const failedRequests = [];
    const httpErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error")
        consoleErrors.push(shortHash(message.text()));
    });
    page.on("requestfailed", (request) => {
      if (
        !/ERR_ABORTED|NS_BINDING_ABORTED/i.test(
          request.failure()?.errorText || "",
        )
      ) {
        failedRequests.push(shortHash(new URL(request.url()).pathname));
      }
    });
    page.on("response", (response) => {
      if (
        response.status() >= 400 &&
        new URL(response.url()).pathname.startsWith("/api/")
      ) {
        httpErrors.push(
          `${new URL(response.url()).pathname} ${response.status()}`,
        );
      }
    });

    await page.goto(state.authUrl, { waitUntil: "domcontentloaded" });
    await page
      .getByText("Viventium Prompt Workbench", { exact: false })
      .first()
      .waitFor();
    await openEvals(page);

    const preview = await runUiEval(page, {
      family: "background_activation_routing",
      maxCases: 1,
      live: false,
      timeoutMs: 60_000,
    });
    const activationRun = await runUiEval(page, {
      family: "background_activation_routing",
      maxCases: 1,
      live: true,
      timeoutMs: 10 * 60_000,
    });
    const activation = activationEvidence(activationRun);
    const activationShot = path.join(outputDir, "activation-live-result.png");
    await page.screenshot({ path: activationShot, fullPage: true });
    result.artifacts.push(path.basename(activationShot));

    const feelingsRun = await runUiEval(page, {
      family: "feelings_embodiment_and_reaction",
      maxCases: FEELINGS_MAX_CASES,
      live: true,
      timeoutMs: FEELINGS_RUN_TIMEOUT_MS,
      caseIds: REQUIRED_ESCAPED_FEELINGS_CASES,
    });
    const feelings = feelingsEvidence(feelingsRun);
    const feelingsLineage = await openRunLineage(page, feelingsRun);
    const feelingsShot = path.join(outputDir, "feelings-live-result.png");
    await page.screenshot({ path: feelingsShot, fullPage: true });
    result.artifacts.push(path.basename(feelingsShot));

    await page.reload({ waitUntil: "domcontentloaded" });
    await openEvals(page);
    const activationVisibleAfterReload = await page
      .getByText(activationRun.id, { exact: true })
      .isVisible()
      .catch(() => false);
    const feelingsVisibleAfterReload = await page
      .getByText(feelingsRun.id, { exact: true })
      .isVisible()
      .catch(() => false);

    result.metrics = {
      workbenchPort: state.port,
      previewReturnCode: preview.returnCode,
      activationReturnCode: activationRun.returnCode,
      activationResultCount: activation.resultCount,
      activationPassCount: activation.passCount,
      activationUnavailableCount: activation.unavailableCount,
      feelingsReturnCode: feelingsRun.returnCode,
      feelingsSelectedCount: feelings.selectedCount,
      feelingsCompletedCount: feelings.completedCount,
      feelingsSemanticPassedCount: feelings.semanticPassedCount,
      feelingsPromptDependencyCount: feelingsLineage.promptDependencyCount,
      feelingsRuntimeContextDependencyCount:
        feelingsLineage.runtimeContextDependencyCount,
      escapedFeelingsCaseCount: REQUIRED_ESCAPED_FEELINGS_CASES.filter(
        (caseId) => feelingsRun.selectedCaseIds?.includes(caseId),
      ).length,
      consoleErrorCount: consoleErrors.length,
      failedRequestCount: failedRequests.length,
      httpErrorCount: httpErrors.length,
    };
    result.checks = {
      previewNoModelPass: preview.returnCode === 0 && preview.live === false,
      activationUsedGuardedQaContext: activation.qaUserContextEnabled,
      activationUsedFallbackChain: activation.fallbacksEnabled,
      activationSubsetPass:
        activationRun.returnCode === 0 &&
        activation.resultCount === 11 &&
        activation.passCount === 11 &&
        activation.unavailableCount === 0,
      feelingsSubsetPass:
        feelingsRun.returnCode === 0 &&
        feelings.selectedCount === FEELINGS_MAX_CASES &&
        feelings.completedCount === FEELINGS_MAX_CASES &&
        feelings.failedCount === 0 &&
        feelings.semanticPassedCount === FEELINGS_MAX_CASES &&
        feelings.semanticFailedCount === 0 &&
        feelings.semanticJudgeUnavailableCount === 0 &&
        feelings.duplicateCount === 0 &&
        feelings.unresolvedAsyncCount === 0,
      feelingsLineageVisible:
        feelingsLineage.feelingsContextVisible &&
        feelingsLineage.privateValuePolicyVisible &&
        feelingsLineage.promptDependencyCount > 0 &&
        feelingsLineage.runtimeContextDependencyCount === 1,
      escapedFeelingsCasesSelected: REQUIRED_ESCAPED_FEELINGS_CASES.every(
        (caseId) => feelingsRun.selectedCaseIds?.includes(caseId),
      ),
      activationHistoryPersists: activationVisibleAfterReload,
      feelingsHistoryPersists: feelingsVisibleAfterReload,
      noConsoleErrors: consoleErrors.length === 0,
      noFailedRequests: failedRequests.length === 0,
      noHttpErrors: httpErrors.length === 0,
    };
    result.pass = Object.values(result.checks).every(Boolean);
    fs.writeFileSync(
      path.join(outputDir, "result.json"),
      `${JSON.stringify(result, null, 2)}\n`,
    );
    console.log(JSON.stringify(result, null, 2));
    if (!result.pass) process.exitCode = 1;
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      pass: false,
      errorClass: shortHash(error?.message),
      error: safeError(error?.message),
    }),
  );
  process.exitCode = 1;
});
