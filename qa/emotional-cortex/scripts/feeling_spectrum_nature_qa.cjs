async (page) => {
  const url = "http://127.0.0.1:8877/feeling-spectrum.html";
  const artifactBase = "qa/emotional-cortex/artifacts";
  const failures = [];
  const consoleMessages = [];
  const requestUrls = [];

  const assert = (condition, message) => {
    if (!condition) failures.push(message);
  };
  const text = async (selector) => (await page.locator(selector).innerText()).trim();

  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleMessages.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("request", (request) => requestUrls.push(request.url()));

  await page.goto(url, { waitUntil: "networkidle" });
  await page.setViewportSize({ width: 1000, height: 920 });

  const initial = {
    switchState: await page.locator("#master").getAttribute("aria-checked"),
    capsule: await text("#capsule"),
    natureValue: await page.locator("#natureText").inputValue(),
    naturePreview: await text("#naturePreview"),
    laneCount: await page.locator(".lane").count()
  };

  assert(initial.switchState === "false", "feelings switch should boot off");
  assert(initial.laneCount === 7, `expected seven living bands, saw ${initial.laneCount}`);
  assert(!initial.capsule.includes("<viventium_feeling_state>"), "off preview must not include the feeling-state tag");
  assert(initial.capsule.includes("no feeling-state block"), "off preview should explain absence without emitting a tag");
  assert(initial.natureValue.includes("repelled by laziness"), "default nature should include an explicit aversion");
  assert(initial.natureValue.includes("genuinely useful"), "default nature should include the usefulness drive");
  assert(initial.naturePreview.includes("my / viventium's nature:"), "nature preview should show the agent-builder heading");
  assert(initial.naturePreview.includes("{{viventium.nature}}"), "nature preview should expose the Prompt Workbench variable");

  const customNature =
    "I'm drawn to clean architecture, courageous clarity, shared attention, and strange good ideas. I'm repelled by laziness, cruelty, manipulation, fuzzy thinking, and performative compliance. I want to understand, build, protect, connect, and play with dry wit.";
  await page.locator("#natureText").fill(customNature);
  const updatedNaturePreview = await text("#naturePreview");
  assert(updatedNaturePreview.includes("clean architecture"), "edited nature should render immediately");
  assert(updatedNaturePreview.includes("dry wit"), "edited play style should render immediately");

  await page.locator("#master").click();
  await page.waitForTimeout(250);
  const enabledCapsule = await text("#capsule");
  assert(enabledCapsule.includes("<viventium_feeling_state>"), "enabled feelings should emit one feeling-state block");
  assert(enabledCapsule.includes("aliveness:"), "enabled capsule should include active band words");
  assert(!enabledCapsule.includes("clean architecture"), "nature text must not leak into the conscious feeling capsule");
  assert(!enabledCapsule.includes("{{viventium.nature}}"), "variable name must not leak into the feeling capsule");
  assert(!/\d/.test(enabledCapsule), `feeling capsule must stay word-only, saw digits in: ${enabledCapsule}`);

  await page.locator('[data-stim="play"]').click();
  await page.waitForTimeout(250);
  const afterStimulusCapsule = await text("#capsule");
  assert(afterStimulusCapsule.includes("recent:"), "stimulus should create a bounded recent line");
  assert(afterStimulusCapsule.includes("play"), "play stimulus should visibly affect the play band or recent line");

  await page.locator("#master").click();
  await page.waitForTimeout(150);
  const disabledCapsule = await text("#capsule");
  assert(!disabledCapsule.includes("<viventium_feeling_state>"), "turning feelings off must remove the tag entirely");
  assert((await text("#naturePreview")).includes("clean architecture"), "nature editor should remain available while feelings are off");

  const responsive = [];
  for (const width of [1000, 390]) {
    await page.setViewportSize({ width, height: width <= 390 ? 900 : 920 });
    await page.waitForTimeout(250);
    const metrics = await page.evaluate(() => ({
      bodyWidth: document.body.scrollWidth,
      viewport: window.innerWidth,
      htmlWidth: document.documentElement.scrollWidth
    }));
    const overflow = Math.max(metrics.bodyWidth, metrics.htmlWidth) - metrics.viewport;
    responsive.push({ width, overflow });
    assert(overflow <= 2, `viewport ${width} has page overflow ${overflow}`);
    await page.screenshot({
      path: `${artifactBase}/2026-06-30-feeling-spectrum-nature-${width}.png`,
      fullPage: true
    });
  }

  const externalRequests = requestUrls.filter((requestUrl) => !requestUrl.startsWith("http://127.0.0.1:8877/"));
  assert(externalRequests.length === 0, `unexpected external requests: ${externalRequests.join(", ")}`);
  assert(consoleMessages.length === 0, `console warnings/errors: ${consoleMessages.join(" | ")}`);

  if (failures.length) {
    throw new Error(failures.join("\n"));
  }

  return {
    initial,
    updatedNaturePreview,
    enabledCapsule,
    afterStimulusCapsule,
    disabledCapsule,
    responsive,
    consoleMessages: consoleMessages.length,
    requestCount: requestUrls.length
  };
}
