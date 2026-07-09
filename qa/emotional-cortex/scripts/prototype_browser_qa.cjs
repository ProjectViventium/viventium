// LEGACY (v3): targets the prior-reference prototype emotion-mixer.html and asserts the
// superseded v3 capsule line "You, Viventium, are feeling:". Kept for history only — the
// current v4 prototype is feeling-spectrum.html and the active script is
// feeling_spectrum_nature_qa.cjs. Do not cite this script as current capsule coverage.
async (page) => {
  const url = "http://127.0.0.1:8876/emotion-mixer.html";
  const artifactBase = "qa/emotional-cortex/artifacts";
  const failures = [];
  const consoleMessages = [];
  const requestUrls = [];

  const assert = (condition, message) => {
    if (!condition) failures.push(message);
  };

  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleMessages.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("request", (request) => requestUrls.push(request.url()));

  await page.goto(url, { waitUntil: "networkidle" });
  await page.evaluate(() => window.localStorage.removeItem("viventium-feeling-console-v3"));
  await page.reload({ waitUntil: "networkidle" });

  const text = async (selector) => (await page.locator(selector).innerText()).trim();
  const promptText = async () => text("#promptState");
  const bandNames = async () =>
    page.locator(".band-name").evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()));

  const initial = {
    enabled: await page.locator("#enableToggle").isChecked(),
    prompt: await promptText(),
    lanes: await bandNames(),
    research: await page.locator(".research-chip").count()
  };
  assert(initial.enabled === false, "first-run Enable Feelings switch must be off");
  assert(
    initial.prompt === "No feeling-state block exists while the switch is off.",
    "disabled state must render absence, not an empty state block"
  );
  assert(
    JSON.stringify(initial.lanes) ===
      JSON.stringify(["Aliveness", "Drive", "Seeking", "Vigilance", "Care", "Belonging", "Play"]),
    `active lanes changed: ${JSON.stringify(initial.lanes)}`
  );
  assert(initial.research === 14, `expected 14 grey research bands, saw ${initial.research}`);

  await page.locator("#enableToggle").check({ force: true });
  await page.locator(".lane").filter({ hasText: "Care" }).click();
  await page.locator("#baselineSlider").evaluate((element) => {
    element.value = "58";
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page.locator("#currentSlider").evaluate((element) => {
    element.value = "83";
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });

  const afterEdit = {
    selected: await text("#selectedName"),
    current: await page.locator("#currentSlider").inputValue(),
    baseline: await page.locator("#baselineSlider").inputValue(),
    delta: await text("#selectedDelta")
  };
  assert(afterEdit.selected === "Care", `expected selected Care, saw ${afterEdit.selected}`);
  assert(afterEdit.current === "83", `expected current 83, saw ${afterEdit.current}`);
  assert(afterEdit.baseline === "58", `expected baseline 58, saw ${afterEdit.baseline}`);
  assert(afterEdit.delta.includes("lifted +25"), `unexpected delta text: ${afterEdit.delta}`);

  await page.locator("#includeToggle").uncheck({ force: true });
  const omittedPrompt = await promptText();
  const omittedSummary = await text("#activeBandsSummary");
  const omittedDelta = await text("#selectedDelta");
  assert(omittedPrompt.includes("<viventium_feeling_state>"), "omitting one band should leave the block for remaining bands");
  assert(!/\bcare\s*:/i.test(omittedPrompt), "omitted Care band must not have a prompt row");
  assert(!/\bcare\b/i.test(omittedPrompt), "omitted Care band must not leak through recent signal text");
  assert(omittedSummary === "6 / 7 injected", `expected 6 / 7 injected after omission, saw ${omittedSummary}`);
  assert(omittedDelta === "omitted", `expected selected delta to say omitted, saw ${omittedDelta}`);

  await page.locator("#decayButton").click();
  const omittedAfterDecayPrompt = await promptText();
  assert(!/\bcare\s*:/i.test(omittedAfterDecayPrompt), "omitted Care row must stay absent after decay");
  assert(!/\bcare\b/i.test(omittedAfterDecayPrompt), "omitted Care must not leak through recent after decay");

  await page.locator("#resetButton").click();
  const omittedAfterResetPrompt = await promptText();
  assert(!/\bcare\s*:/i.test(omittedAfterResetPrompt), "omitted Care row must stay absent after reset");
  assert(!/\bcare\b/i.test(omittedAfterResetPrompt), "omitted Care must not leak through recent after reset");

  await page.locator("#includeToggle").check({ force: true });
  let enabledPrompt = await promptText();
  const forbiddenPromptPieces = [
    "enabled",
    "disabled",
    "null",
    "n/a",
    "baseline",
    "/100",
    "confidence",
    "above nature",
    "below nature",
    "modeled internal state",
    "biological claim",
    "not a biological",
    "as an AI",
    "do not announce",
    "may never override",
    "willingness to disagree",
    "refusal requirements",
    "safety policy",
    "truthfulness",
    "joy:",
    "sadness:",
    "fear:",
    "frustration:",
    "affiliation:",
    "valence:",
    "activation:",
    "agency:",
    "guard:",
    "ease:",
    "vitality:",
    "poise:"
  ];
  const loweredPrompt = enabledPrompt.toLowerCase();
  const leakedPieces = forbiddenPromptPieces.filter((piece) => loweredPrompt.includes(piece));
  assert(enabledPrompt.includes("<viventium_feeling_state>"), "enabled prompt must include state block");
  assert(
    enabledPrompt.includes("You, Viventium, are feeling:"),
    "prompt must use minimal being-state wording"
  );
  assert(leakedPieces.length === 0, `prompt leaked forbidden pieces: ${leakedPieces.join(", ")}`);
  assert(!/\d/.test(enabledPrompt), `prompt should be word-only, saw digits in: ${enabledPrompt}`);

  for (let index = 0; index < 12; index += 1) {
    await page.locator("#stimulusButton").click();
  }
  const trailCount = await page.locator(".trail-item").count();
  assert(trailCount === 10, `recent trail must cap at 10, saw ${trailCount}`);

  const beforeDecay = Number(await page.locator("#currentSlider").inputValue());
  const baseline = Number(await page.locator("#baselineSlider").inputValue());
  await page.locator("#decayButton").click();
  const afterDecay = Number(await page.locator("#currentSlider").inputValue());
  const afterDecayPrompt = await promptText();
  assert(
    Math.abs(afterDecay - baseline) < Math.abs(beforeDecay - baseline),
    `decay must move current toward baseline: before ${beforeDecay}, after ${afterDecay}, baseline ${baseline}`
  );
  const loweredAfterDecayPrompt = afterDecayPrompt.toLowerCase();
  const afterDecayLeakedPieces = forbiddenPromptPieces.filter((piece) =>
    loweredAfterDecayPrompt.includes(piece)
  );
  assert(
    afterDecayLeakedPieces.length === 0,
    `post-decay prompt leaked forbidden pieces: ${afterDecayLeakedPieces.join(", ")}`
  );
  assert(!/\d/.test(afterDecayPrompt), `post-decay prompt should be word-only, saw digits in: ${afterDecayPrompt}`);

  await page.reload({ waitUntil: "networkidle" });
  const persisted = {
    enabled: await page.locator("#enableToggle").isChecked(),
    selected: await text("#selectedName"),
    trail: await page.locator(".trail-item").count()
  };
  assert(persisted.enabled === true, "enabled state should persist in demo storage");
  assert(persisted.selected === "Care", `selected band should persist as Care, saw ${persisted.selected}`);
  assert(persisted.trail === 10, `trail cap should persist at 10, saw ${persisted.trail}`);

  const responsive = [];
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: width <= 390 ? 900 : 920 });
    await page.waitForTimeout(200);
    const metrics = await page.evaluate(() => ({
      bodyWidth: document.body.scrollWidth,
      viewport: window.innerWidth,
      htmlWidth: document.documentElement.scrollWidth
    }));
    const overflow = Math.max(metrics.bodyWidth, metrics.htmlWidth) - metrics.viewport;
    responsive.push({ width, overflow });
    assert(overflow <= 2, `viewport ${width} has page overflow ${overflow}`);
    await page.screenshot({ path: `${artifactBase}/2026-06-25-feeling-console-${width}.png`, fullPage: true });
  }

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload({ waitUntil: "networkidle" });
  await page.locator("#enableToggle").check({ force: true });
  await page.waitForTimeout(300);
  const reducedMotion = await page.locator("#console").evaluate((element) =>
    getComputedStyle(element).getPropertyValue("--scan-opacity").trim()
  );
  assert(
    Number(reducedMotion) <= 0.18,
    `reduced motion should quiet scan opacity, saw ${reducedMotion}`
  );
  await page.screenshot({
    path: `${artifactBase}/2026-06-25-feeling-console-reduced-motion.png`,
    fullPage: true
  });

  const externalRequests = requestUrls.filter((requestUrl) => !requestUrl.startsWith("http://127.0.0.1:8876/"));
  assert(externalRequests.length === 0, `unexpected external requests: ${externalRequests.join(", ")}`);
  assert(consoleMessages.length === 0, `console warnings/errors: ${consoleMessages.join(" | ")}`);

  if (failures.length) {
    throw new Error(failures.join("\n"));
  }

  return {
    initial,
    afterEdit,
    trailCount,
    beforeDecay,
    decayCheck: {
      selected: persisted.selected,
      current: afterDecay,
      baseline,
      distance: Math.abs(afterDecay - baseline)
    },
    persisted,
    responsive,
    reducedMotion,
    consoleMessages: consoleMessages.length,
    requestCount: requestUrls.length
  };
}
