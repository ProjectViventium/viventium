#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const CLIENT_BASE = (
  process.env.VIVENTIUM_QA_CLIENT_BASE || "http://localhost:3190"
).replace(/\/$/, "");
const API_BASE = (
  process.env.VIVENTIUM_QA_API_BASE || "http://localhost:3180"
).replace(/\/$/, "");
const PRIVATE_ROOT =
  process.env.VIVENTIUM_QA_PRIVATE_DIR ||
  path.join(
    os.homedir(),
    "Library",
    "Application Support",
    "Viventium",
    "private-user-data",
  );
const RESET_QA_STATE = process.env.VIVENTIUM_FEELINGS_QA_RESET === "1";
const EXPECT_EXISTING_STATE =
  process.env.VIVENTIUM_FEELINGS_QA_EXPECT_EXISTING === "1";
const PREPARE_RESTART_STATE =
  process.env.VIVENTIUM_FEELINGS_QA_PREPARE_RESTART === "1";
const configuredVisibleReplyTimeout = Number(
  process.env.VIVENTIUM_FEELINGS_QA_VISIBLE_REPLY_TIMEOUT_MS || 150_000,
);
const VISIBLE_ASSISTANT_REPLY_TIMEOUT_MS = Number.isFinite(
  configuredVisibleReplyTimeout,
)
  ? Math.min(240_000, Math.max(30_000, configuredVisibleReplyTimeout))
  : 150_000;
const HEADED = process.argv.includes("--headed");

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) return values;
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function loadLocalEnv() {
  const candidates = [
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "runtime",
      "runtime.env",
    ),
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "runtime",
      "runtime.local.env",
    ),
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "runtime",
      "service-env",
      "librechat.env",
    ),
    path.join(LIBRECHAT_ROOT, ".env"),
  ];
  return candidates.reduce(
    (all, filePath) => Object.assign(all, parseEnvFile(filePath)),
    {
      ...process.env,
    },
  );
}

function shortHash(value) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, 12);
}

function progress(step) {
  console.log(JSON.stringify({ step }));
}

async function bounded(task, timeoutMs = 5000) {
  return Promise.race([
    task,
    new Promise((resolve) => setTimeout(() => resolve("timeout"), timeoutMs)),
  ]);
}

function requireLocalQaOptIn() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error(
      "Local Feelings browser QA is forbidden in CI and production",
    );
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw new Error(
      "Set VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 for this local-only QA harness",
    );
  }
  if (!process.env.VIVENTIUM_QA_EMAIL && !process.env.VIVENTIUM_QA_USER_NAME) {
    throw new Error("Set VIVENTIUM_QA_EMAIL or VIVENTIUM_QA_USER_NAME");
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { textHash: shortHash(text) };
  }
  return { ok: response.ok, status: response.status, body };
}

async function createQaAuth(env) {
  const { MongoClient, ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const jwt = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"),
  );
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error("Missing local QA auth prerequisites");
  }
  const client = new MongoClient(env.MONGO_URI, {
    serverSelectionTimeoutMS: 5000,
  });
  await client.connect();
  const dbName =
    new URL(env.MONGO_URI).pathname.replace(/^\//, "") || "LibreChatViventium";
  const db = client.db(dbName);
  const selector = process.env.VIVENTIUM_QA_EMAIL
    ? { email: process.env.VIVENTIUM_QA_EMAIL.trim().toLowerCase() }
    : { name: process.env.VIVENTIUM_QA_USER_NAME.trim() };
  const user = await db.collection("users").findOne(selector);
  if (!user?._id) {
    await client.close();
    throw new Error("Configured QA user not found");
  }
  const accessToken = jwt.sign(
    {
      id: user._id.toString(),
      username: user.username,
      provider: user.provider,
      email: user.email,
    },
    env.JWT_SECRET,
    { expiresIn: "2h" },
  );
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: user._id.toString(), sessionId: sessionId.toString() },
    env.JWT_REFRESH_SECRET,
    { expiresIn: 7200 },
  );
  await db.collection("sessions").insertOne({
    _id: sessionId,
    user: user._id,
    expiration,
    refreshTokenHash: crypto
      .createHash("sha256")
      .update(refreshToken)
      .digest("hex"),
  });
  return {
    accessToken,
    client,
    db,
    refreshToken,
    sessionId,
    user,
    userHash: shortHash(user._id),
  };
}

function authHeaders(auth, body = false) {
  return {
    Authorization: `Bearer ${auth.accessToken}`,
    ...(body ? { "Content-Type": "application/json" } : {}),
  };
}

function authCookies(auth) {
  return [API_BASE, CLIENT_BASE].flatMap((url) => [
    {
      name: "refreshToken",
      value: auth.refreshToken,
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires: Math.floor(Date.now() / 1000) + 7200,
    },
    {
      name: "token_provider",
      value: "librechat",
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires: Math.floor(Date.now() / 1000) + 7200,
    },
  ]);
}

async function readFeelings(auth) {
  const response = await fetchJson(`${API_BASE}/api/viventium/feelings`, {
    headers: authHeaders(auth),
  });
  if (!response.ok)
    throw new Error(`Feelings read failed with HTTP ${response.status}`);
  return response.body;
}

async function deleteFeelings(auth) {
  const current = await readFeelings(auth);
  const response = await fetchJson(`${API_BASE}/api/viventium/feelings`, {
    method: "DELETE",
    headers: authHeaders(auth, true),
    body: JSON.stringify({ expectedVersion: current.state.version }),
  });
  if (!response.ok)
    throw new Error(`Feelings reset failed with HTTP ${response.status}`);
}

async function waitForReaction(auth, version, timeoutMs = 45_000) {
  const startedAt = Date.now();
  let latest = null;
  while (Date.now() - startedAt < timeoutMs) {
    latest = await readFeelings(auth);
    const health = latest.state.reactionHealth;
    if (
      health.status !== "running" &&
      health.status !== "never" &&
      (latest.state.version > version ||
        health.status === "degraded" ||
        health.status === "skipped")
    ) {
      return { payload: latest, elapsedMs: Date.now() - startedAt };
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return { payload: latest, elapsedMs: Date.now() - startedAt, timedOut: true };
}

async function waitForConversation(auth, chatPage, stimulus, sentAt) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 30_000) {
    const urlConversationId =
      chatPage.url().match(/\/c\/([^/?#]+)/)?.[1] || null;
    if (urlConversationId && urlConversationId !== "new") {
      return urlConversationId;
    }
    const userMessage = await auth.db.collection("messages").findOne(
      {
        user: String(auth.user._id),
        isCreatedByUser: true,
        text: stimulus,
        createdAt: { $gte: new Date(sentAt - 5000) },
      },
      { sort: { createdAt: -1 }, projection: { conversationId: 1 } },
    );
    if (userMessage?.conversationId) return userMessage.conversationId;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("Synthetic QA conversation was not persisted");
}

async function waitForVisibleAssistantReply(
  auth,
  chatPage,
  conversationId,
  sentAt,
  failureScreenshotPath,
) {
  const startedAt = Date.now();
  let persistedMessage = null;
  while (Date.now() - startedAt < VISIBLE_ASSISTANT_REPLY_TIMEOUT_MS) {
    const assistantMessage = await auth.db.collection("messages").findOne(
      {
        conversationId,
        isCreatedByUser: false,
        text: { $type: "string", $ne: "" },
        createdAt: { $gte: new Date(sentAt - 5000) },
      },
      { sort: { createdAt: -1 }, projection: { messageId: 1 } },
    );
    if (assistantMessage?.messageId) {
      persistedMessage = assistantMessage;
      const visibleMessage = chatPage.locator(
        `[id="${assistantMessage.messageId}"]`,
      );
      if (await visibleMessage.isVisible().catch(() => false)) {
        await visibleMessage.evaluate((element) => {
          if (!element.innerText.trim()) {
            throw new Error("Visible assistant reply is empty");
          }
        });
        return assistantMessage;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (failureScreenshotPath) {
    await chatPage
      .screenshot({ path: failureScreenshotPath, fullPage: true })
      .catch(() => undefined);
  }
  throw new Error(
    persistedMessage
      ? "Synthetic QA assistant reply was persisted but not visible"
      : "Synthetic QA assistant reply was not persisted",
  );
}

async function main() {
  requireLocalQaOptIn();
  const env = loadLocalEnv();
  const auth = await createQaAuth(env);
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const outputDir = path.join(PRIVATE_ROOT, "emotional-cortex", stamp);
  fs.mkdirSync(outputDir, { recursive: true });
  const result = {
    userHash: auth.userHash,
    source: "local-dev-runtime",
    checks: {},
    metrics: {},
    artifacts: [],
  };
  const pendingConversationCleanup = new Set();
  let browser;
  try {
    progress("auth_ready");
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
    if (EXPECT_EXISTING_STATE) {
      const existing = await readFeelings(auth);
      browser = await chromium.launch({ channel: "chrome", headless: !HEADED });
      const persistenceContext = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
      });
      await persistenceContext.addCookies(authCookies(auth));
      const persistencePage = await persistenceContext.newPage();
      await persistencePage.goto(`${CLIENT_BASE}/feelings`, {
        waitUntil: "domcontentloaded",
      });
      await persistencePage
        .getByRole("heading", { name: "Feeling spectrum" })
        .waitFor();
      result.checks.postRestartApiState =
        existing.state.enabled === true &&
        existing.state.version >= 1 &&
        existing.state.innerState?.text?.length > 0;
      result.checks.postRestartUiState =
        (await persistencePage
          .getByRole("switch", { name: "Feelings on" })
          .isVisible()) &&
        (await persistencePage.getByText("Last felt sense", { exact: false }).isVisible()) &&
        (await persistencePage.getByText(existing.state.innerState.text, { exact: true }).isVisible());
      const restartPath = path.join(outputDir, "feelings-post-restart.png");
      await persistencePage.screenshot({ path: restartPath, fullPage: true });
      result.artifacts.push(path.basename(restartPath));
      await bounded(browser.close());
      browser = undefined;
      await bounded(
        auth.db.collection("sessions").deleteOne({ _id: auth.sessionId }),
      );
      await bounded(auth.client.close(true));
      Object.assign(auth, await createQaAuth(env));
      progress("post_restart_state_verified");
    }
    if (RESET_QA_STATE) await deleteFeelings(auth);
    const firstRead = await readFeelings(auth);
    result.checks.defaultOff =
      firstRead.state.enabled === false && !firstRead.state.capsule;
    result.checks.canonicalBands =
      firstRead.definitions.map((band) => band.id).join(",") ===
      "energy,mood,drive,curiosity,vigilance,care,connection,openness,play";
    result.config = firstRead.config;
    progress("default_state_verified");

    browser = await chromium.launch({ channel: "chrome", headless: !HEADED });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
    });
    await context.addCookies(authCookies(auth));
    const page = await context.newPage();
    page.setDefaultTimeout(30_000);
    page.setDefaultNavigationTimeout(30_000);
    const consoleErrors = [];
    const failedRequests = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(shortHash(message.text()));
      }
    });
    page.on("requestfailed", (request) => {
      failedRequests.push({
        resourceType: request.resourceType(),
        urlClass: new URL(request.url()).pathname,
        errorClass: request.failure()?.errorText || "unknown",
      });
    });

    await page.goto(`${CLIENT_BASE}/feelings`, {
      waitUntil: "domcontentloaded",
    });
    await page.getByRole("heading", { name: "Feeling spectrum" }).waitFor();
    progress("feelings_page_loaded");
    result.checks.polesExplainDirection =
      (await page.getByText("energetic", { exact: true }).isVisible()) &&
      (await page.getByText("tired", { exact: true }).isVisible());
    result.checks.currentNatureVisuallyNamed =
      (await page.getByText(/NOW 56/).count()) >= 1 &&
      (await page.getByText(/NATURE 56/).count()) >= 1;
    result.checks.offStateVisible = await page
      .getByText("Feelings are off", { exact: true })
      .isVisible();
    const beforePath = path.join(outputDir, "feelings-default-off.png");
    await page.screenshot({ path: beforePath, fullPage: true });
    result.artifacts.push(path.basename(beforePath));

    const enableResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/viventium/feelings/profile") &&
        response.request().method() === "PATCH",
    );
    await page.getByRole("switch", { name: "Enable Feelings" }).click();
    result.checks.enableHttp = (await enableResponse).status() === 200;
    await page.getByText("Feelings are awake.", { exact: true }).waitFor();
    result.checks.innerStateWaitingTruthful = await page
      .getByText("The next reaction will put this state into Viv’s own words.", {
        exact: true,
      })
      .isVisible();
    progress("feelings_enabled");

    await page.getByRole("button", { name: /^Select Energy:/ }).click();
    const currentSlider = page.getByRole("slider", {
      name: "Current feeling",
      exact: true,
    });
    await currentSlider.fill("71");
    await page.waitForTimeout(50);
    await currentSlider.dispatchEvent("pointerup");
    await page.getByText("Energy moved.", { exact: true }).waitFor();
    const afterCurrent = await readFeelings(auth);
    const baselineBefore = afterCurrent.state.bands.energy.baseline;

    const natureSlider = page.getByRole("slider", {
      name: "Nature / resting point",
      exact: true,
    });
    await natureSlider.fill("43");
    await page.waitForTimeout(50);
    await natureSlider.dispatchEvent("pointerup");
    await page.getByText("Energy nature changed.", { exact: true }).waitFor();
    await page
      .getByRole("combobox", { name: "Return speed" })
      .selectOption("240");
    await page
      .getByText("Energy return speed changed.", { exact: true })
      .waitFor();
    const afterManual = await readFeelings(auth);
    result.checks.currentNatureIndependent =
      afterManual.state.bands.energy.current > 69 &&
      afterManual.state.bands.energy.baseline === 43 &&
      baselineBefore !== 43;
    result.checks.returnSpeedPersisted =
      afterManual.state.bands.energy.halfLifeMinutes === 240;
    result.manualVersion = afterManual.state.version;
    const natureBeforeReaction = Object.fromEntries(
      Object.entries(afterManual.state.bands).map(([bandId, band]) => [
        bandId,
        band.baseline,
      ]),
    );
    const laneCurrent = page.getByRole("slider", {
      name: "Energy current feeling",
    });
    const laneValueBefore = Number(
      await laneCurrent.getAttribute("aria-valuenow"),
    );
    await laneCurrent.press("ArrowUp");
    await page.getByText("Energy moved.", { exact: true }).waitFor();
    const afterLaneKeyboard = await readFeelings(auth);
    result.checks.laneKeyboardControl =
      Math.round(afterLaneKeyboard.state.bands.energy.current) ===
      laneValueBefore + 1;
    result.snapshotHashBeforeChat = afterLaneKeyboard.state.snapshotHash;
    progress("manual_controls_verified");

    const reactionButton = page.getByRole("button", {
      name: "Reaction Cortex",
    });
    await reactionButton.click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    const reactionRouteText = await dialog
      .locator(".feelings-drawer-status small")
      .innerText();
    result.checks.reactionDrawer =
      reactionRouteText.includes("Primary: gpt-5.6-terra · Fast") &&
      reactionRouteText.includes("Fallback: claude-opus-4-8") &&
      (await dialog
        .getByRole("combobox", { name: "When should it activate?" })
        .inputValue()) === "always";
    await page.keyboard.press("Escape");
    result.checks.dialogEscapeAndFocusRestore =
      !(await dialog.isVisible()) &&
      (await reactionButton.evaluate(
        (element) => element === document.activeElement,
      ));
    progress("reaction_drawer_verified");

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Feeling spectrum" }).waitFor();
    await page.getByRole("button", { name: /^Select Energy:/ }).click();
    await page.getByRole("heading", { name: "Energy" }).waitFor();
    await page.waitForFunction(
      () =>
        document.querySelector("#feeling-nature")?.value === "43" &&
        document.querySelector("#feeling-return")?.value === "240",
    );
    result.checks.refreshPersistence =
      (await page
        .getByRole("slider", {
          name: "Nature / resting point",
          exact: true,
        })
        .inputValue()) === "43" &&
      (await page
        .getByRole("combobox", { name: "Return speed" })
        .inputValue()) === "240";
    progress("refresh_persistence_verified");

    const responsiveResults = [];
    for (const width of [320, 390, 768, 1024, 1440]) {
      const height = width <= 390 ? 844 : width <= 1024 ? 900 : 1000;
      await page.setViewportSize({ width, height });
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      );
      const actionBoxes = await Promise.all([
        page.getByRole("button", { name: "Reaction Cortex" }).boundingBox(),
        page.getByRole("switch", { name: "Feelings on" }).boundingBox(),
      ]);
      const primaryActionsVisible = actionBoxes.every(
        (box) =>
          box &&
          box.x >= 0 &&
          box.y >= 0 &&
          box.x + box.width <= width &&
          box.y + box.height <= height,
      );
      responsiveResults.push({ width, overflow, primaryActionsVisible });
      const responsivePath = path.join(outputDir, `feelings-responsive-${width}.png`);
      await page.screenshot({ path: responsivePath, fullPage: true });
      result.artifacts.push(path.basename(responsivePath));
    }
    result.responsive = responsiveResults;
    result.checks.responsiveNoHorizontalOverflow = responsiveResults.every(
      (entry) => entry.overflow <= 1,
    );
    result.checks.responsivePrimaryActionsVisible = responsiveResults.every(
      (entry) => entry.primaryActionsVisible,
    );
    progress("responsive_views_verified");

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.evaluate(() => {
      window.__feelingsTransitionCaptures = [];
      document
        .querySelectorAll(".feelings-current-marker")
        .forEach((marker) => {
          marker.addEventListener("transitionrun", (event) => {
            if (event.propertyName !== "bottom") return;
            const capture = {
              label: marker.getAttribute("aria-label"),
              startedAt: performance.now(),
              endedAt: null,
              positions: [marker.getBoundingClientRect().y],
            };
            window.__feelingsTransitionCaptures.push(capture);
            for (const delay of [150, 350, 650, 1050]) {
              setTimeout(() => {
                capture.positions.push(marker.getBoundingClientRect().y);
              }, delay);
            }
          });
          marker.addEventListener("transitionend", (event) => {
            if (event.propertyName !== "bottom") return;
            const capture = [...window.__feelingsTransitionCaptures]
              .reverse()
              .find(
                (entry) =>
                  entry.label === marker.getAttribute("aria-label") &&
                  entry.endedAt == null,
              );
            if (capture) {
              capture.endedAt = performance.now();
              capture.positions.push(marker.getBoundingClientRect().y);
            }
          });
        });
    });
    const chatPage = await context.newPage();
    await chatPage.goto(`${CLIENT_BASE}/c/new`, {
      waitUntil: "domcontentloaded",
    });
    let input = chatPage.getByPlaceholder(/Message Viventium/i);
    if ((await input.count()) === 0)
      input = chatPage.getByRole("textbox", { name: "Message input" });
    await input.waitFor({ timeout: 30_000 });
    progress("chat_ready");
    const syntheticStimulus =
      "Synthetic QA moment: imagine I'm giggling with you because the tiny bug finally cracked. Give me one short celebratory line.";
    await input.fill(syntheticStimulus);
    const titleResponse = chatPage
      .waitForResponse(
        (response) => response.url().includes("/api/convos/gen_title/"),
        { timeout: 30_000 },
      )
      .catch(() => null);
    const sentAt = Date.now();
    await chatPage.getByRole("button", { name: "Send message" }).click();
    const conversationId = await waitForConversation(
      auth,
      chatPage,
      syntheticStimulus,
      sentAt,
    );
    pendingConversationCleanup.add(conversationId);
    let preparedConversationId = null;
    await waitForVisibleAssistantReply(
      auth,
      chatPage,
      conversationId,
      sentAt,
      path.join(outputDir, "chat-visible-reply-timeout-primary.png"),
    );
    result.metrics.visibleReplyMs = Date.now() - sentAt;
    result.checks.visibleReply = true;
    result.conversationHash = conversationId ? shortHash(conversationId) : null;
    progress("visible_reply_complete");

    const reaction = await waitForReaction(
      auth,
      afterLaneKeyboard.state.version,
    );
    result.metrics.reactionObservedMs = reaction.elapsedMs;
    result.checks.reactionCompleted =
      reaction.payload?.state?.reactionHealth?.status === "healthy";
    result.checks.reactionChangedState =
      reaction.payload?.state?.version > afterLaneKeyboard.state.version;
    const innerState = reaction.payload?.state?.innerState;
    result.checks.innerStateGenerated =
      typeof innerState?.text === "string" &&
      innerState.text.length > 0 &&
      innerState.text.length <= 280 &&
      !/[\r\n]/u.test(innerState.text) &&
      Number.isFinite(new Date(innerState.generatedAt).getTime());
    result.reactionHealth = reaction.payload?.state?.reactionHealth || null;
    result.finalVersion = reaction.payload?.state?.version ?? null;
    result.finalSnapshotHash = reaction.payload?.state?.snapshotHash || null;
    result.trailLength = reaction.payload?.state?.trail?.length ?? null;
    result.checks.reactionNatureUnchanged = Object.entries(
      reaction.payload?.state?.bands || {},
    ).every(
      ([bandId, band]) =>
        Math.abs(Number(band.baseline) - Number(natureBeforeReaction[bandId])) <
        0.001,
    );
    await titleResponse;
    progress("detached_reaction_observed");

    const reactionEntry = [...(reaction.payload?.state?.trail || [])]
      .reverse()
      .find((entry) => entry.sourceType === "user_turn");
    if (reactionEntry) {
      const bandDefinition = reaction.payload.definitions.find(
        (entry) => entry.id === reactionEntry.band,
      );
      const markerName = `${bandDefinition.name} current feeling`;
      const natureName = `${bandDefinition.name} nature`;
      const marker = page.getByRole("slider", { name: markerName });
      const natureMarker = page.getByRole("slider", { name: natureName });
      const readNaturePosition = (element) => {
        const track = element.closest(".feelings-track");
        if (!(track instanceof HTMLElement)) return null;
        const markerBox = element.getBoundingClientRect();
        const trackBox = track.getBoundingClientRect();
        return {
          ariaValue: element.getAttribute("aria-valuenow"),
          bottomStyle: element.style.bottom,
          offsetFromTrackBottom: trackBox.bottom - markerBox.bottom,
        };
      };
      const natureBeforePosition = await natureMarker.evaluate(readNaturePosition);
      await page.waitForFunction(
        ({ label, value }) =>
          document
            .querySelector(`[aria-label="${label}"]`)
            ?.getAttribute("aria-valuenow") === String(value),
        {
          label: markerName,
          value: Math.round(reactionEntry.after),
        },
        { timeout: 20_000 },
      );
      await page.waitForTimeout(1200);
      const transitionCapture = await page.evaluate((label) => {
        return [...(window.__feelingsTransitionCaptures || [])]
          .reverse()
          .find((entry) => entry.label === label) || null;
      }, markerName);
      const transitionPositions = transitionCapture?.positions || [];
      const distinctPositions = new Set(
        transitionPositions
          .filter((value) => value != null)
          .map((value) => Number(value).toFixed(1)),
      );
      const natureAfterPosition = await natureMarker.evaluate(readNaturePosition);
      result.transitionPositions = transitionPositions;
      result.transitionDurationMs = transitionCapture?.endedAt
        ? transitionCapture.endedAt - transitionCapture.startedAt
        : null;
      result.checks.reactionTransitionAnimated =
        distinctPositions.size >= 3 && result.transitionDurationMs >= 800;
      result.checks.natureMarkerStayedFixedDuringReaction =
        natureBeforePosition &&
        natureAfterPosition &&
        natureBeforePosition.ariaValue === natureAfterPosition.ariaValue &&
        natureBeforePosition.bottomStyle === natureAfterPosition.bottomStyle &&
        Math.abs(
          natureBeforePosition.offsetFromTrackBottom -
            natureAfterPosition.offsetFromTrackBottom,
        ) < 1;
      result.checks.reactionCauseVisible = await page
        .getByText(
          /Playful exchange|Pull toward connection|Progress|Surprise|Something new/,
        )
        .first()
        .isVisible();
      result.checks.motionTailVisible =
        (await page.getByTestId(`feelings-motion-tail-${reactionEntry.band}`).count()) === 1;
      await page.emulateMedia({ reducedMotion: "reduce" });
      const reducedStyles = await page.evaluate((label) => {
        const marker = document.querySelector(`[aria-label="${label}"]`);
        const lane = marker?.closest(".feelings-lane");
        const tail = lane?.querySelector(".feelings-motion-tail-core");
        const heartbeat = document.querySelector(".feelings-heartbeat");
        const readSeconds = (value) =>
          Math.max(
            ...String(value || "0s")
              .split(",")
              .map((part) =>
                part.trim().endsWith("ms")
                  ? Number.parseFloat(part) / 1000
                  : Number.parseFloat(part),
              )
              .filter(Number.isFinite),
            0,
          );
        return {
          laneIsReacting: lane?.classList.contains("is-reacting") === true,
          markerTransitionSeconds: readSeconds(
            marker ? getComputedStyle(marker).transitionDuration : "1s",
          ),
          tailAnimationSeconds: readSeconds(
            tail ? getComputedStyle(tail).animationDuration : "1s",
          ),
          heartbeatAnimationSeconds: readSeconds(
            heartbeat ? getComputedStyle(heartbeat).animationDuration : "1s",
          ),
        };
      }, markerName);
      result.reducedMotionStyles = reducedStyles;
      result.checks.reducedMotionHonored =
        reducedStyles.markerTransitionSeconds <= 0.01 &&
        reducedStyles.tailAnimationSeconds <= 0.01 &&
        reducedStyles.heartbeatAnimationSeconds <= 0.01;
      const reducedMotionPath = path.join(outputDir, "feelings-reduced-motion.png");
      await page.screenshot({ path: reducedMotionPath, fullPage: true });
      result.artifacts.push(path.basename(reducedMotionPath));
      await page.emulateMedia({ reducedMotion: "no-preference" });
    } else {
      result.checks.reactionTransitionAnimated = false;
      result.checks.natureMarkerStayedFixedDuringReaction = false;
      result.checks.reactionCauseVisible = false;
      result.checks.motionTailVisible = false;
      result.checks.reducedMotionHonored = false;
    }
    result.checks.innerStateVisible =
      Boolean(innerState?.text) &&
      (await page.getByText(innerState.text, { exact: true }).isVisible()) &&
      (await page.getByText("Last felt sense", { exact: false }).isVisible());
    const finalPath = path.join(outputDir, "feelings-after-reaction.png");
    await page.screenshot({ path: finalPath, fullPage: true });
    result.artifacts.push(path.basename(finalPath));
    const trailPath = path.join(outputDir, "feelings-reaction-trail.png");
    await page.locator(".feelings-trail").screenshot({ path: trailPath });
    result.artifacts.push(path.basename(trailPath));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator(".feelings-inspector-header").scrollIntoViewIfNeeded();
    const mobileInspectorPath = path.join(
      outputDir,
      "feelings-mobile-inspector-after-reaction.png",
    );
    await page.screenshot({ path: mobileInspectorPath });
    result.artifacts.push(path.basename(mobileInspectorPath));
    result.checks.healthVisible = reaction.payload?.state?.reactionHealth
      ?.status
      ? await page
          .getByText(/Ready · .*last reaction|Needs attention|last skipped/i)
          .isVisible()
      : false;
    await page.getByRole("button", { name: "Reaction Cortex" }).click();
    const postReactionDialog = page.getByRole("dialog");
    await postReactionDialog.waitFor();
    const postReactionRouteText = await postReactionDialog
      .locator(".feelings-drawer-status small")
      .innerText();
    const actualHealth = reaction.payload?.state?.reactionHealth;
    result.checks.actualRouteVisible =
      Boolean(actualHealth?.lastUsedModel) &&
      postReactionRouteText.includes(`Last route: ${actualHealth.lastUsedModel}`) &&
      (!actualHealth.lastUsedServiceTier ||
        postReactionRouteText.includes(actualHealth.lastUsedServiceTier));
    await page.keyboard.press("Escape");

    const collectionNames = (await auth.db.listCollections().toArray()).map(
      (entry) => entry.name,
    );
    const feelingCollection = collectionNames.find(
      (name) => name.toLowerCase() === "feelingstates",
    );
    const dbState = feelingCollection
      ? await auth.db
          .collection(feelingCollection)
          .findOne({ userId: auth.user._id })
      : null;
    result.checks.dbConfirmed =
      Boolean(dbState) &&
      dbState.version === reaction.payload?.state?.version &&
      dbState.trail.length <= 90 &&
      dbState.processedStimulusKeys?.length >= 1 &&
      dbState.processedStimulusKeys.every((key) => /^[a-f0-9]{24}$/.test(key)) &&
      dbState.innerState?.text === innerState?.text &&
      !dbState.innerState.text.includes(syntheticStimulus);
    result.db = dbState
      ? {
          version: dbState.version,
          enabled: dbState.enabled,
          trailLength: dbState.trail.length,
          processedStimulusCount: dbState.processedStimulusKeys.length,
          healthStatus: dbState.reactionHealth?.status,
          hasInnerState: Boolean(dbState.innerState?.text),
          innerStateLength: dbState.innerState?.text?.length || 0,
        }
      : null;

    const reducedSlider = page.getByRole("slider", {
      name: "Current feeling",
      exact: true,
    });
    const reducedBefore = Number(await reducedSlider.inputValue());
    const reducedAfter = reducedBefore >= 100 ? reducedBefore - 1 : reducedBefore + 1;
    const reducedWrite = page.waitForResponse(
      (response) =>
        response.url().includes("/api/viventium/feelings/bands/") &&
        response.request().method() === "PATCH",
    );
    await reducedSlider.fill(String(reducedAfter));
    await reducedSlider.dispatchEvent("pointerup");
    result.checks.reducedMotionWriteHttp = (await reducedWrite).status() === 200;
    const afterManualClear = await readFeelings(auth);
    result.postManualVersion = afterManualClear.state.version;
    result.checks.manualEditClearsInnerState =
      afterManualClear.state.innerState == null &&
      (await page
        .getByText("The next reaction will put this state into Viv’s own words.", {
          exact: true,
        })
        .isVisible());
    const manualClearPath = path.join(outputDir, "feelings-after-manual-clear.png");
    await page.screenshot({ path: manualClearPath, fullPage: true });
    result.artifacts.push(path.basename(manualClearPath));

    if (PREPARE_RESTART_STATE) {
      await chatPage.goto(`${CLIENT_BASE}/c/new`, {
        waitUntil: "domcontentloaded",
      });
      let prepareInput = chatPage.getByPlaceholder(/Message Viventium/i);
      if ((await prepareInput.count()) === 0)
        prepareInput = chatPage.getByRole("textbox", { name: "Message input" });
      await prepareInput.waitFor({ timeout: 30_000 });
      const prepareStimulus =
        "Synthetic QA persistence moment: the careful fix held after a refresh. Give me one short grounded response.";
      await prepareInput.fill(prepareStimulus);
      const prepareSentAt = Date.now();
      await chatPage.getByRole("button", { name: "Send message" }).click();
      preparedConversationId = await waitForConversation(
        auth,
        chatPage,
        prepareStimulus,
        prepareSentAt,
      );
      pendingConversationCleanup.add(preparedConversationId);
      await waitForVisibleAssistantReply(
        auth,
        chatPage,
        preparedConversationId,
        prepareSentAt,
        path.join(outputDir, "chat-visible-reply-timeout-restart.png"),
      );
      const preparedReaction = await waitForReaction(
        auth,
        afterManualClear.state.version,
      );
      result.checks.restartStatePrepared =
        preparedReaction.payload?.state?.reactionHealth?.status === "healthy" &&
        preparedReaction.payload?.state?.version > afterManualClear.state.version &&
        typeof preparedReaction.payload?.state?.innerState?.text === "string" &&
        preparedReaction.payload.state.innerState.text.length > 0;
      result.restartPreparedVersion =
        preparedReaction.payload?.state?.version ?? null;
      progress("restart_state_prepared");
    }

    result.consoleErrorHashes = [...new Set(consoleErrors)];
    result.failedRequests = failedRequests;
    result.checks.noBrowserConsoleErrors = consoleErrors.length === 0;
    result.checks.noFeatureRequestFailures = !failedRequests.some((request) =>
      request.urlClass.includes("/api/viventium/feelings"),
    );
    const conversationIds = [conversationId, preparedConversationId].filter(Boolean);
    if (conversationIds.length > 0) {
      const messageCleanup = await auth.db
        .collection("messages")
        .deleteMany({ conversationId: { $in: conversationIds } });
      const conversationCleanup = await auth.db
        .collection("conversations")
        .deleteMany({ conversationId: { $in: conversationIds } });
      result.checks.syntheticConversationCleaned =
        messageCleanup.deletedCount >= conversationIds.length * 2 &&
        conversationCleanup.deletedCount === conversationIds.length;
      conversationIds.forEach((id) => pendingConversationCleanup.delete(id));
    } else {
      result.checks.syntheticConversationCleaned = false;
    }
  } finally {
    if (browser) await bounded(browser.close());
    if (pendingConversationCleanup.size > 0) {
      const conversationIds = [...pendingConversationCleanup];
      await bounded(
        auth.db
          .collection("messages")
          .deleteMany({ conversationId: { $in: conversationIds } }),
      );
      await bounded(
        auth.db
          .collection("conversations")
          .deleteMany({ conversationId: { $in: conversationIds } }),
      );
    }
    await bounded(
      auth.db.collection("sessions").deleteOne({ _id: auth.sessionId }),
    );
    await bounded(auth.client.close(true));
  }
  const resultPath = path.join(outputDir, "result.json");
  fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, {
    mode: 0o600,
  });
  console.log(
    JSON.stringify(
      { ...result, privateOutput: path.basename(outputDir) },
      null,
      2,
    ),
  );
  if (Object.values(result.checks).some((value) => value !== true))
    process.exitCode = 1;
}

main().catch((error) => {
  console.error(
    JSON.stringify({ error: error.message, errorClass: error.name }),
  );
  process.exitCode = 1;
});
