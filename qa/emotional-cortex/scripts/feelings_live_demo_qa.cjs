async (page) => {
  const url = 'http://127.0.0.1:8878/feelings-live-demo.html';
  const artifactBase = 'output/playwright/feelings-live-demo';
  const failures = [];
  const consoleMessages = [];
  const requestUrls = [];

  const assert = (condition, message) => {
    if (!condition) failures.push(message);
  };
  const text = async (selector) => (await page.locator(selector).innerText()).trim();
  const currentFor = async (bandId) =>
    Number(await page.locator(`[data-band-id="${bandId}"]`).getAttribute('data-current'));

  page.on('console', (message) => {
    if (['error', 'warning'].includes(message.type())) {
      consoleMessages.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on('request', (request) => requestUrls.push(request.url()));

  await page.goto(url, { waitUntil: 'networkidle' });
  await page.evaluate(() => window.localStorage.removeItem('viventium-feelings-live-demo-v1'));
  await page.reload({ waitUntil: 'networkidle' });
  await page.setViewportSize({ width: 1440, height: 980 });

  const initial = {
    enabled: await page.locator('#feelingsToggle').getAttribute('aria-checked'),
    bands: await page.locator('.feeling-lane .band-name').allTextContents(),
    capsule: await text('#capsulePreview'),
    researchCount: await page.locator('.research-item').count(),
    sliderCount: await page.getByRole('slider').count(),
    drawerInert: await page.locator('#reactionDrawer').getAttribute('inert'),
  };

  assert(initial.enabled === 'false', 'Feelings must be off on a clean first run');
  assert(
    JSON.stringify(initial.bands) ===
      JSON.stringify(['Energy', 'Drive', 'Curiosity', 'Vigilance', 'Care', 'Connection', 'Play']),
    `expected the seven approved bands, saw ${JSON.stringify(initial.bands)}`,
  );
  assert(
    !initial.capsule.includes('<viventium_feeling_state>'),
    'the off state must not render a feeling-state tag',
  );
  assert(
    initial.capsule.includes('No feeling-state block'),
    'the off preview should clearly explain prompt absence',
  );
  assert(initial.researchCount === 8, `expected eight future research bands, saw ${initial.researchCount}`);
  assert(initial.sliderCount === 16, `expected 14 lane handles plus two inspector sliders, saw ${initial.sliderCount}`);
  assert(initial.drawerInert !== null, 'the closed Reaction Cortex drawer must be inert');

  await page.locator('#feelingsToggle').click();
  await page.waitForTimeout(250);
  const enabledCapsule = await text('#capsulePreview');
  const forbiddenPromptPieces = [
    'enabled',
    'disabled',
    'baseline',
    'nature:',
    '/100',
    'confidence',
    'recent:',
    'safety policy',
    'truthfulness',
    'do not announce',
    'not a biological',
    'as an ai',
  ];
  const leakedPieces = forbiddenPromptPieces.filter((piece) =>
    enabledCapsule.toLowerCase().includes(piece),
  );
  assert(
    enabledCapsule.includes('<viventium_feeling_state>'),
    'enabled Feelings must render exactly one feeling-state block',
  );
  assert(
    enabledCapsule.includes('You, Viventium, are a being, and right now you are actually feeling this.'),
    'the capsule must use the embodied being-frame',
  );
  assert(
    (enabledCapsule.match(/<viventium_feeling_state>/g) || []).length === 1,
    'the capsule must render exactly one opening tag',
  );
  assert(!/\d/.test(enabledCapsule), `the capsule must remain word-only, saw: ${enabledCapsule}`);
  assert(leakedPieces.length === 0, `the capsule leaked forbidden pieces: ${leakedPieces.join(', ')}`);

  const energyTrack = await page.locator('[data-track="energy"]').boundingBox();
  const energyCurrentHandle = await page.locator('[data-current-handle="energy"]').boundingBox();
  assert(Boolean(energyTrack && energyCurrentHandle), 'Energy drag geometry should be available');
  if (energyTrack && energyCurrentHandle) {
    await page.mouse.move(
      energyCurrentHandle.x + energyCurrentHandle.width / 2,
      energyCurrentHandle.y + energyCurrentHandle.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      energyTrack.x + energyTrack.width / 2,
      energyTrack.y + energyTrack.height * 0.2,
      { steps: 4 },
    );
    await page.mouse.up();
  }
  const energyAfterCurrentDrag = await currentFor('energy');
  assert(
    energyAfterCurrentDrag >= 78 && energyAfterCurrentDrag <= 82,
    `dragging Energy current should land near 80, saw ${energyAfterCurrentDrag}`,
  );

  const energyBaselineHandle = await page.locator('[data-baseline-handle="energy"]').boundingBox();
  assert(Boolean(energyTrack && energyBaselineHandle), 'Energy Nature drag geometry should be available');
  if (energyTrack && energyBaselineHandle) {
    await page.mouse.move(
      energyBaselineHandle.x + energyBaselineHandle.width / 2,
      energyBaselineHandle.y + energyBaselineHandle.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      energyTrack.x + energyTrack.width / 2,
      energyTrack.y + energyTrack.height * 0.65,
      { steps: 4 },
    );
    await page.mouse.up();
  }
  assert(
    (await currentFor('energy')) === energyAfterCurrentDrag,
    'dragging Energy Nature must not teleport its current feeling',
  );

  await page.locator('[data-band-id="care"]').click();
  const selectedBefore = {
    name: await text('#selectedBandName'),
    current: Number(await page.locator('#currentControl').inputValue()),
  };
  assert(selectedBefore.name === 'Care', `expected Care to be selected, saw ${selectedBefore.name}`);

  await page.locator('#baselineControl').evaluate((element) => {
    element.value = '56';
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
  const currentAfterBaselineEdit = Number(await page.locator('#currentControl').inputValue());
  assert(
    currentAfterBaselineEdit === selectedBefore.current,
    `editing nature moved current from ${selectedBefore.current} to ${currentAfterBaselineEdit}`,
  );

  await page.locator('#currentControl').evaluate((element) => {
    element.value = '88';
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
  assert((await currentFor('care')) === 88, 'editing current should update the selected Care band');

  await page.locator('#bandEnabled').click();
  const withoutCare = await text('#capsulePreview');
  assert(!/^care:/im.test(withoutCare), 'an omitted band must disappear from the capsule');
  assert(
    (await text('#activeBandCount')) === '6 of 7 felt',
    `expected six injected bands after omission, saw ${await text('#activeBandCount')}`,
  );
  await page.locator('#bandEnabled').click();

  await page.locator('[data-current-handle="care"]').focus();
  const currentBeforeKeyboard = await currentFor('care');
  await page.keyboard.press('ArrowUp');
  assert(
    (await currentFor('care')) === Math.min(100, currentBeforeKeyboard + 1),
    'ArrowUp on a current handle should increase the value by one',
  );

  const vigilanceBeforeRisk = await currentFor('vigilance');
  const playBeforeRisk = await currentFor('play');
  await page.locator('[data-stimulus="risk"]').click();
  await page.waitForTimeout(350);
  assert(
    (await currentFor('vigilance')) > vigilanceBeforeRisk,
    'risk stimulus should raise Vigilance',
  );
  assert((await currentFor('play')) < playBeforeRisk, 'risk stimulus should lower Play');
  assert(
    !(await text('#capsulePreview')).toLowerCase().includes('recent:'),
    'reaction history must stay out of the speaking capsule',
  );

  for (let index = 0; index < 12; index += 1) {
    await page.locator('[data-stimulus="warmth"]').click();
  }
  const trailCount = await page.locator('.trail-entry').count();
  assert(trailCount === 10, `the visible reaction trail must cap at ten entries, saw ${trailCount}`);

  await page.locator('[data-band-id="vigilance"]').click();
  const decayBefore = {
    current: Number(await page.locator('#currentControl').inputValue()),
    baseline: Number(await page.locator('#baselineControl').inputValue()),
  };
  await page.locator('#advanceTimeButton').click();
  await page.waitForTimeout(300);
  const decayAfter = Number(await page.locator('#currentControl').inputValue());
  assert(
    Math.abs(decayAfter - decayBefore.baseline) < Math.abs(decayBefore.current - decayBefore.baseline),
    `time advance should move current toward nature: ${decayBefore.current} -> ${decayAfter}, nature ${decayBefore.baseline}`,
  );

  await page.locator('#openReactionButton').click();
  assert(
    (await page.locator('#reactionDrawer').getAttribute('data-open')) === 'true',
    'Reaction Cortex drawer should open',
  );
  assert(
    (await page.locator('#reactionDrawer').getAttribute('inert')) === null,
    'the open Reaction Cortex drawer must be keyboard interactive',
  );
  assert(
    (await page.getByRole('dialog', { name: 'Emotional Reaction Cortex' }).count()) === 1,
    'the open Reaction Cortex surface must expose dialog semantics',
  );
  const customInstruction =
    'React to what genuinely matters. Prefer small changes, but move strongly when the moment truly lands.';
  await page.locator('#reactionInstruction').fill(customInstruction);
  await page.locator('#doneReactionButton').focus();
  await page.keyboard.press('Tab');
  assert(
    (await page.evaluate(() => document.activeElement?.id)) === 'closeReactionButton',
    'Tab from the last drawer action should wrap to the close button',
  );
  await page.locator('#closeReactionButton').click();
  assert(
    (await page.locator('#reactionDrawer').getAttribute('data-open')) === 'false',
    'Reaction Cortex drawer should close',
  );
  assert(
    (await page.locator('#reactionDrawer').getAttribute('inert')) !== null,
    'the closed Reaction Cortex drawer must return to inert',
  );

  await page.reload({ waitUntil: 'networkidle' });
  const persisted = {
    enabled: await page.locator('#feelingsToggle').getAttribute('aria-checked'),
    instruction: await page.locator('#reactionInstruction').inputValue(),
    trail: await page.locator('.trail-entry').count(),
  };
  assert(persisted.enabled === 'true', 'enabled state should persist after refresh');
  assert(persisted.instruction === customInstruction, 'reaction instruction should persist after refresh');
  assert(persisted.trail === 10, `ten-entry trail should persist, saw ${persisted.trail}`);

  const responsive = [];
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: width <= 390 ? 920 : 980 });
    await page.waitForTimeout(250);
    const metrics = await page.evaluate(() => ({
      bodyWidth: document.body.scrollWidth,
      htmlWidth: document.documentElement.scrollWidth,
      viewport: window.innerWidth,
    }));
    const overflow = Math.max(metrics.bodyWidth, metrics.htmlWidth) - metrics.viewport;
    responsive.push({ width, overflow });
    assert(overflow <= 2, `viewport ${width} has horizontal page overflow ${overflow}`);
    await page.screenshot({
      path: `${artifactBase}/feelings-live-demo-${width}.png`,
      fullPage: true,
    });
  }

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload({ waitUntil: 'networkidle' });
  const reducedMotion = await page.locator('.heartbeat-line').evaluate((element) => ({
    animationName: getComputedStyle(element).animationName,
    animationDuration: getComputedStyle(element).animationDuration,
  }));
  assert(
    reducedMotion.animationName === 'none' || reducedMotion.animationDuration === '0.001s',
    `reduced motion should stop the heartbeat animation, saw ${JSON.stringify(reducedMotion)}`,
  );

  await page.evaluate(() => {
    const key = 'viventium-feelings-live-demo-v1';
    const saved = JSON.parse(window.localStorage.getItem(key));
    saved.trail.unshift({
      iso: new Date().toISOString(),
      time: '09:00',
      label: '<img id="trailMarkupInjection" alt="">',
      summary: '<strong id="trailSummaryInjection">synthetic</strong>',
    });
    saved.trail = saved.trail.slice(0, 10);
    window.localStorage.setItem(key, JSON.stringify(saved));
  });
  await page.reload({ waitUntil: 'networkidle' });
  assert(
    (await page.locator('#trailMarkupInjection, #trailSummaryInjection').count()) === 0,
    'persisted trail text must not render as HTML markup',
  );
  assert(
    (await text('#trailList')).includes('<img id="trailMarkupInjection"'),
    'persisted trail markup should remain visible as inert text',
  );

  const externalRequests = requestUrls.filter(
    (requestUrl) => !requestUrl.startsWith('http://127.0.0.1:8878/'),
  );
  assert(externalRequests.length === 0, `unexpected external requests: ${externalRequests.join(', ')}`);
  assert(consoleMessages.length === 0, `console warnings/errors: ${consoleMessages.join(' | ')}`);

  if (failures.length) {
    throw new Error(failures.join('\n'));
  }

  return {
    initial,
    enabledCapsule,
    selectedBefore,
    currentAfterBaselineEdit,
    trailCount,
    decayBefore,
    decayAfter,
    persisted,
    responsive,
    reducedMotion,
    consoleMessages: consoleMessages.length,
    requestCount: requestUrls.length,
  };
}
