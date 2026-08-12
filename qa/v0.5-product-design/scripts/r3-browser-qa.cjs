const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const evidence = path.join(root, 'evidence');
const url = 'http://127.0.0.1:8765/viventium-v0.5-sources-wireframe.html';
const brandUrl = 'http://127.0.0.1:8765/viventium-v0.5-brand-ui-kit.html';
fs.mkdirSync(evidence, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function captureWholeView(page, filename) {
  const viewport = page.viewportSize();
  const firstHeight = await page.evaluate(() => Math.ceil(document.documentElement.scrollHeight));
  await page.setViewportSize({ width: viewport.width, height: Math.min(5200, Math.max(viewport.height, firstHeight)) });
  const settledHeight = await page.evaluate(() => Math.ceil(document.documentElement.scrollHeight));
  if (settledHeight !== firstHeight) {
    await page.setViewportSize({ width: viewport.width, height: Math.min(5200, Math.max(viewport.height, settledHeight)) });
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(evidence, filename) });
  await page.setViewportSize(viewport);
}

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const consoleProblems = [];
  const results = [];
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'dark' });
  const page = await context.newPage();
  page.on('console', (message) => {
    if (message.type() === 'error' || message.type() === 'warning') consoleProblems.push(`${message.type()}: ${message.text()}`);
  });
  page.on('pageerror', (error) => consoleProblems.push(`pageerror: ${error.message}`));
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.evaluate(() => localStorage.removeItem('viventium-v05-living-mind-r3'));
  await page.reload({ waitUntil: 'networkidle' });

  assert(await page.getByRole('heading', { name: 'Here with you.' }).isVisible(), 'MIND did not load');
  assert(await page.locator('.channel-switch').count() === 0, 'Obsolete channel switch is present');
  assert(await page.locator('.mind-trail-row').count() === 2, 'MIND compact Emotion Trail is incomplete');
  const replyReceipt = page.locator('.reply-receipt');
  assert(await replyReceipt.isVisible(), 'Behind this reply is not visibly anchored to the response');
  assert(await replyReceipt.getAttribute('open') === null, 'Cortex and Memory detail should begin quietly collapsed');
  assert((await replyReceipt.locator('summary').textContent()).trim().endsWith('Show'), 'Collapsed receipt does not expose one truthful Show action');
  assert(await page.locator('#presenceDock').evaluate((element) => element.parentElement.classList.contains('conversation')), 'Full MIND presence is not in the conversation flow');
  const desktopDockOverlap = await page.evaluate(() => {
    const presence = document.querySelector('#presenceDock').getBoundingClientRect();
    const composer = document.querySelector('#composer').getBoundingClientRect();
    return !(presence.right <= composer.left || presence.left >= composer.right || presence.bottom <= composer.top || presence.top >= composer.bottom);
  });
  assert(!desktopDockOverlap, 'Full MIND presence covers the desktop composer');
  assert((await replyReceipt.locator('summary').textContent()).includes('3 context sources · 1 Cortex active'), 'Collapsed Cortex and Memory status is incomplete');
  await replyReceipt.locator('summary').click();
  await page.waitForFunction(() => document.querySelector('#receiptAction')?.textContent === 'Hide');
  assert(await replyReceipt.getAttribute('open') !== null, 'Behind this reply did not expand');
  assert((await replyReceipt.locator('summary').textContent()).trim().endsWith('Hide'), 'Expanded receipt does not expose one truthful Hide action');
  assert(await page.locator('.receipt-stage').count() === 3, 'The Memory → Cortex → change receipt is incomplete');
  assert(await page.getByText('Context & Memory', { exact: true }).isVisible(), 'Memory stage is not named clearly');
  assert(await page.getByText('Cortices', { exact: true }).isVisible(), 'Cortex stage is not named clearly');
  assert(await page.locator('.memory-stage button').count() === 3, 'The response does not expose the three context sources');
  assert(await page.getByText(/Conversation Recall · the decision still open/).isVisible(), 'Conversation Recall is conflated with saved memory');
  assert(await page.locator('.cortex-stage.active').count() === 1, 'The active Cortex is not visible');
  assert(await page.getByText(/Returned · one source unavailable/).isVisible(), 'Completed/degraded Cortex state is missing');
  assert(await page.getByText('Values checked · nothing added', { exact: true }).isVisible(), 'Silent Cortex completion is missing');
  assert(await page.getByText('No saved memory changed', { exact: true }).isVisible(), 'Saved-memory write truth is missing');
  await page.getByRole('button', { name: 'See work', exact: true }).click();
  assert(await page.getByText(/No result has shaped this reply yet/).isVisible(), 'Active Cortex work detail did not open');
  assert(await page.getByText('Why it woke up', { exact: true }).isVisible(), 'Cortex activation definition is missing');
  assert(await page.getByText('What it cannot do', { exact: true }).isVisible(), 'Cortex capability boundary is missing');
  assert(await page.getByText('Quality check', { exact: true }).isVisible(), 'Cortex evaluation contract is missing');
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  assert(await page.getByText('Stopped by you', { exact: true }).isVisible(), 'Cortex cancellation state is missing');
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  assert(await page.getByText('Checking', { exact: true }).isVisible(), 'Cortex retry did not return to checking');
  assert(await page.locator('#presenceDock').evaluate((element) => element.classList.contains('is-compact')), 'Presence did not make room while Cortex and Memory detail was open');
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
  await page.waitForTimeout(200);
  await page.locator('.skip-link').evaluate((element) => { element.style.display = 'none'; });
  await captureWholeView(page, 'r3-mind-dark.png');
  await page.locator('.skip-link').evaluate((element) => { element.style.removeProperty('display'); });
  await replyReceipt.locator('summary').click();
  await page.waitForFunction(() => !document.querySelector('#presenceDock').classList.contains('is-compact'));
  assert(await page.locator('#presenceDock').evaluate((element) => !element.classList.contains('is-compact')), 'Full voice island did not return after closing the receipt');
  assert(await page.locator('#presenceDock').evaluate((element) => element.parentElement.classList.contains('conversation')), 'Full voice island did not return to conversation flow');
  await page.locator('[data-presence-mode="wing"]').click();
  assert(await page.locator('[data-presence-mode="wing"]').evaluate((element) => element.classList.contains('active')), 'Only when useful did not activate');
  await page.getByRole('button', { name: 'Mute microphone' }).click();
  assert(await page.getByRole('button', { name: 'Mute microphone' }).getAttribute('aria-pressed') === 'true', 'Mute did not persist its state');
  results.push('MIND conversation + turn-anchored Memory/Cortex receipt + Emotion Trail');

  await page.getByRole('button', { name: 'Connect', exact: true }).click();
  assert(await page.locator('#presenceDock').evaluate((element) => element.classList.contains('is-compact')), 'Presence did not compact outside MIND');
  assert(await page.locator('#muteButton').getAttribute('aria-pressed') === 'true', 'Presence state did not follow navigation');
  assert((await page.locator('#aiReadiness').textContent()).includes('0 of 2 ready'), 'CONNECT first run is pretending accounts are ready');
  assert(await page.locator('[data-source-id="email"] .account-row').count() === 0, 'Email should begin without fabricated accounts');
  assert(await page.getByRole('button', { name: /Find everything/ }).isVisible(), 'Find everything is missing');
  await page.getByRole('button', { name: /Find everything/ }).click();
  assert(await page.getByText(/Nothing is connected without your review/).isVisible(), 'Discovery consent copy is missing');
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  assert(await page.locator('#discoveryStrip').isHidden(), 'Discovery did not stop');
  assert(await page.getByText('Discovery stopped').isVisible(), 'Discovery stop feedback is missing');
  await page.getByRole('button', { name: /Find everything/ }).click();
  await page.waitForTimeout(2500);
  assert(await page.getByRole('heading', { name: '7 accounts and apps' }).isVisible(), 'Discovery review did not appear');
  assert(await page.getByText(/Sample discovery/).isVisible(), 'Discovery findings are not labeled Sample');
  assert(await page.locator('#detectedList input:checked').count() === 7, 'Detected-account review count is wrong');
  await page.locator('#detectedList [data-detected-source="telegram"]').uncheck();
  await page.screenshot({ path: path.join(evidence, 'r3-connect-discovery-dark.png'), fullPage: true });
  await page.getByRole('button', { name: 'Connect selected' }).click();
  assert((await page.locator('#aiReadiness').textContent()).includes('2 of 2 ready'), 'Thinking readiness did not become complete');
  assert((await page.locator('[data-source-id="telegram"] .connection-account').textContent()).includes('Off'), 'Unchecked discovery result was connected anyway');
  const emailItem = page.locator('[data-source-id="email"]');
  if ((await emailItem.getAttribute('class') || '').includes('expanded') === false) {
    await emailItem.locator('[data-source-expand="email"]').first().click();
  }
  assert(await emailItem.locator('.account-row').count() === 2, 'Email does not expose separate accounts');
  assert(await emailItem.getByRole('button', { name: /Add another email/ }).isVisible(), 'Add another email is missing');
  await emailItem.getByRole('button', { name: /Add another email/ }).click();
  assert(await page.getByLabel('Email address').isVisible(), 'All-in-one email field is missing');
  assert(await page.locator('.method-row').count() === 4, 'Email connection methods are incomplete');
  await page.screenshot({ path: path.join(evidence, 'r3-email-all-in-one-dark.png') });
  await page.getByRole('button', { name: 'Close' }).click();
  await page.reload({ waitUntil: 'networkidle' });
  assert((await page.locator('#aiReadiness').textContent()).includes('2 of 2 ready'), 'Connected accounts did not survive reload');
  assert(await page.locator('[data-source-id="email"] .account-row').count() === 2, 'Multiple email accounts did not survive reload');
  results.push('GlassHive discovery + review + multi-account CONNECT');

  await page.getByRole('button', { name: 'Character', exact: true }).click();
  await page.waitForTimeout(300);
  assert(await page.locator('#feelingsEnabled').isChecked(), 'The illustrative review state should open with the instrument active');
  assert(await page.getByText(/Illustrative preview/).isVisible(), 'Illustrative Feeling data is not labeled');
  await page.locator('#voicePicker').click();
  assert(await page.locator('#voiceMenu [role="option"]').count() === 4, 'Speaking voice choices are incomplete');
  await page.locator('#voiceMenu [data-voice="river"]').click();
  assert((await page.locator('#voiceProvider').textContent()).includes('OpenAI'), 'Speaking voice choice did not update');
  assert(await page.locator('.spectrum-band').count() === 9, 'Nine Feelings are not present in the Spectrum');
  assert(await page.locator('.spectrum-tail').count() === 9, 'A recorded path is not present inside every Feeling band');
  const meterHeights = await page.locator('.meter-well').evaluateAll((elements) => elements.map((element) => Math.round(element.getBoundingClientRect().height)));
  assert(new Set(meterHeights).size === 1 && meterHeights[0] >= 220, `Feelings do not share one fixed 0–100 scale (${meterHeights.join(',')})`);
  const vigilanceMarkers = await page.locator('[data-feeling-open="vigilance"]').evaluate((element) => {
    const current = element.querySelector('.current-cap').getBoundingClientRect();
    const nature = element.querySelector('.nature-marker').getBoundingClientRect();
    return Math.abs(current.top - nature.top);
  });
  assert(vigilanceMarkers >= 14, `Current/Nature movement is visually flattened (${vigilanceMarkers}px)`);
  assert(await page.locator('.selected-path circle').count() === 0, 'Selected path still contains stretched SVG dot geometry');
  assert(await page.locator('.reaction-row').count() === 9, 'Typed What changed and why history is incomplete');
  await page.locator('[data-feeling-open="mood"]').click();
  await page.waitForTimeout(50);
  assert(await page.locator('[data-feeling-open="mood"]').evaluate((element) => document.activeElement === element), 'Selecting a Feeling loses keyboard focus');
  const moodNatureY = Number(await page.locator('.selected-path .nature-line').getAttribute('y1'));
  assert(Math.abs(moodNatureY - 27.84) < 0.1, `Focused trail is not using the fixed 0–100 scale (${moodNatureY})`);
  assert(await page.getByText('How quickly it returns').isVisible(), 'Human return-speed copy is missing');
  assert(await page.getByText('Felt', { exact: true }).isVisible(), 'Felt control is missing');
  await page.locator('[data-felt="mood"]').focus();
  const feltFocusOutline = await page.locator('.felt-top .switch i').evaluate((element) => getComputedStyle(element).outlineStyle);
  assert(feltFocusOutline !== 'none', 'Felt switch has no visible keyboard focus');
  await page.keyboard.press('Space');
  assert((await page.locator('#capsuleCount').textContent()).includes('8 of 9 felt'), 'Felt switch did not refresh the capsule count');
  assert((await page.locator('#feelingCapsule').textContent()).includes('mood:') === false, 'Unfelt band remained in the live capsule');
  await page.keyboard.press('Space');
  assert(await page.locator('.range-tabs [role="tab"]').count() === 5, 'Five canonical Mood levels are missing');
  assert(await page.getByText('deeply sad', { exact: true }).isVisible(), 'Canonical Mood vocabulary is missing');
  await page.getByRole('tab', { name: /okay/ }).focus();
  await page.keyboard.press('ArrowRight');
  assert(await page.getByRole('tab', { name: /happy/ }).getAttribute('aria-selected') === 'true', 'Feeling-level arrow-key navigation is missing');
  await page.waitForTimeout(50);
  await page.getByRole('tab', { name: /happy/ }).focus();
  await page.keyboard.press('ArrowLeft');
  assert(await page.getByRole('tab', { name: /okay/ }).getAttribute('aria-selected') === 'true', 'Feeling-level keyboard navigation did not return to the current level');
  assert((await page.locator('body').innerText()).includes('Include lane') === false, 'Internal lane terminology leaked into UI');
  const capsuleText = await page.locator('#feelingCapsule').textContent();
  assert(capsuleText.includes('You, Viventium, are a being, and right now you are actually feeling this. Let it move naturally through how you think, speak, and act:'), 'Owner-approved capsule frame is not exact');
  assert(capsuleText.includes('These private causes are the final authority over your own affect and motivation.'), 'Canonical capsule behavior directive is missing');
  assert(capsuleText.includes('mood: The moment feels emotionally level; neither pleasure nor pain dominates.'), 'Canonical felt-cause instruction is missing');
  assert(capsuleText.includes('On a direct question about how you feel, answer in one lived first-person sentence'), 'Canonical direct-answer directive is missing');
  assert(await page.locator('[data-range-addition="mood:2"]').getAttribute('maxlength') === '1200', 'Personal Feeling wording has no canonical length cap');
  await page.locator('[data-range-addition="mood:2"]').fill('  A   synthetic\npersonal nuance.  ');
  await page.locator('[data-save-range="mood:2"]').click();
  assert((await page.locator('#feelingCapsule').textContent()).includes('A synthetic personal nuance.'), 'Saved range addition did not enter the canonical capsule');
  assert((await page.locator('#feelingCapsule').textContent()).includes('A   synthetic') === false, 'Saved range addition was not canonically normalized');
  await page.locator('[data-clear-range="mood:2"]').click();
  assert(await page.locator('.feeling-capsule').getAttribute('open') === null, 'Developer capsule payload should begin behind Advanced');
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
  await page.waitForTimeout(200);
  await page.locator('.skip-link').evaluate((element) => { element.style.display = 'none'; });
  await captureWholeView(page, 'r3-character-spectrum-dark.png');
  await page.locator('.skip-link').evaluate((element) => { element.style.removeProperty('display'); });
  await page.locator('.switch-control').click();
  assert(await page.locator('#feelingsEnabled').isChecked() === false, 'Feelings master switch did not pause reactions');
  assert(await page.locator('[data-feeling-slider="mood:now"]').isDisabled(), 'Paused Feelings still allows Current to react');
  assert(await page.locator('[data-feeling-slider="mood:nature"]').isEnabled(), 'Pausing reactions incorrectly blocks Nature configuration');
  assert((await page.locator('#characterInnerState').textContent()).includes('not shaping responses'), 'Paused Feelings still claims to shape responses');
  assert((await page.locator('#feelingCapsule').textContent()).trim() === '', 'Paused Feelings still exposes an active capsule');
  assert((await page.locator('#capsuleCount').textContent()).includes('Paused · no state block'), 'Paused Feelings does not explain the empty capsule');
  assert((await page.locator('#pauseFeelings').textContent()).includes('Resume Feelings'), 'Pause action did not become Resume');
  await page.locator('#feelingsEnabled').focus();
  const feelingsFocusOutline = await page.locator('.switch-control i').evaluate((element) => getComputedStyle(element).outlineStyle);
  assert(feelingsFocusOutline !== 'none', 'Feelings switch has no visible keyboard focus');
  await page.locator('.switch-control').click();
  assert(await page.locator('[data-feeling-slider="mood:now"]').isEnabled(), 'Resuming Feelings did not enable Current editing');
  await page.locator('[data-feeling-slider="mood:now"]').focus();
  await page.locator('[data-feeling-slider="mood:now"]').evaluate((element) => {
    element.value = '68';
    element.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.waitForTimeout(50);
  assert(await page.locator('[data-feeling-slider="mood:now"]').evaluate((element) => document.activeElement === element), 'Feeling slider loses keyboard focus after an adjustment');
  assert((await page.locator('#characterInnerState').textContent()).includes('Waiting for the next reaction'), 'Stale Inner state was not cleared after a manual change');
  assert((await page.locator('.reaction-row').first().textContent()).includes('Mood rose clearly'), 'Typed manual Feeling change did not enter the readable trail');
  const typedReaction = await page.evaluate(() => JSON.parse(localStorage.getItem('viventium-v05-living-mind-r3')).reactions[0]);
  assert(typedReaction.band === 'mood' && typedReaction.direction === 'up' && typedReaction.strength === 'clear' && typedReaction.cause === 'manual_adjustment' && typedReaction.sourceType === 'manual' && !Number.isNaN(Date.parse(typedReaction.timestamp)), 'Manual trail entry does not match the canonical typed schema');
  await page.locator('[data-profile="candid"]').click();
  const profileReactions = await page.evaluate(() => JSON.parse(localStorage.getItem('viventium-v05-living-mind-r3')).reactions);
  assert(profileReactions.some((entry) => entry.band === 'energy' && entry.after === 61 && entry.sourceType === 'manual' && entry.cause === 'manual_adjustment'), 'Nature profile created untyped visible movement');
  await page.locator('[data-profile="grounded"]').click();
  await page.locator('.reaction-settings > summary').click();
  assert(await page.getByText('Fast route preview', { exact: true }).isVisible(), 'Reaction route preview is missing');
  assert(await page.getByText(/Fallback recovery/).isHidden(), 'Reaction health examples should remain progressive disclosure');
  await page.locator('.reaction-health details summary').click();
  assert(await page.getByText(/Fallback recovery/).isVisible(), 'Degraded/fallback health state is missing');
  assert(await page.getByText(/If unavailable/).isVisible(), 'Unavailable Reaction Cortex state is missing');
  assert(await page.getByText(/If changed elsewhere/).isVisible(), 'Conflict Reaction Cortex state is missing');
  await page.locator('#reactionActivation').selectOption('classified');
  await page.locator('#reactionInstruction').fill('A synthetic Reaction Cortex instruction.');
  await page.locator('#saveReactionInstruction').click();
  assert(JSON.parse(await page.evaluate(() => localStorage.getItem('viventium-v05-living-mind-r3'))).reactionActivation === 'classified', 'Reaction activation mode did not persist');
  assert(JSON.parse(await page.evaluate(() => localStorage.getItem('viventium-v05-living-mind-r3'))).reactionInstruction === 'A synthetic Reaction Cortex instruction.', 'Reaction instruction did not persist');
  await page.reload({ waitUntil: 'networkidle' });
  assert(await page.locator('#reactionInstruction').inputValue() === 'A synthetic Reaction Cortex instruction.', 'Reaction instruction disappeared after reload');
  await page.locator('.reaction-settings > summary').click();
  await page.locator('#restoreReactionInstruction').click();
  assert((await page.locator('#reactionInstruction').inputValue()).startsWith('React to what genuinely moves Viventium.'), 'Restore wording did not restore the canonical default');
  await page.locator('#saveReactionInstruction').click();
  await page.locator('.reaction-health details summary').click();
  await page.locator('.reaction-settings').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(evidence, 'r3-character-reaction-cortex-dark.png') });
  await page.locator('#eraseFeelings').click();
  assert(await page.getByRole('heading', { name: 'Turn off and erase Feelings?' }).isVisible(), 'Permanent erase confirmation is missing');
  await page.getByRole('button', { name: 'Keep Feelings' }).click();
  await page.locator('.reaction-settings > summary').click();
  await page.getByRole('button', { name: 'Mind', exact: true }).click();
  assert((await page.locator('#mindInnerState').textContent()).includes('Waiting for the next reaction'), 'MIND kept stale Inner state after a manual change');
  await page.getByRole('button', { name: 'Character', exact: true }).click();
  await page.waitForTimeout(300);
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
  await captureWholeView(page, 'r3-character-after-change-dark.png');
  results.push('Live-shaped nine-band Feeling Spectrum + recorded paths + focused controls');

  await page.getByRole('button', { name: 'Automations', exact: true }).click();
  const sleep = page.locator('[data-automation-editor="sleep"]');
  assert(await sleep.isVisible(), 'Automation did not expand inline');
  assert(await sleep.getByText('One source of truth with Prompt Workbench').isVisible(), 'Prompt Workbench linkage is missing');
  const instruction = sleep.locator('[data-automation-prompt="sleep"]');
  await sleep.locator('[data-automation-field="sleep:cycle"]').selectOption('weekly');
  assert(await page.locator('[data-automation-editor="sleep"] [data-automation-field="sleep:cycle"]').inputValue() === 'weekly', 'Automation cycle did not update');
  assert((await page.locator('[data-automation="sleep"] .automation-next').textContent()).includes('Every week'), 'Automation summary did not follow the changed cycle');
  const deliveryOptions = await page.locator('[data-automation-field="sleep:delivery"] option').allTextContents();
  assert(new Set(deliveryOptions).size === deliveryOptions.length, 'Automation delivery contains duplicate choices');
  await instruction.focus();
  await instruction.press('Control+End');
  await instruction.type(' {{');
  assert(await page.locator('#autocomplete-sleep').isVisible(), 'Double-brace autocomplete did not open');
  assert(await instruction.getAttribute('aria-expanded') === 'true', 'Autocomplete state is not exposed accessibly');
  assert(await page.locator('#autocomplete-sleep [role="option"]').count() > 0, 'Autocomplete has no canonical variables');
  await page.locator('#autocomplete-sleep [role="option"]').first().click();
  assert(await instruction.getAttribute('aria-expanded') === 'false', 'Autocomplete state did not close accessibly');
  await sleep.getByRole('button', { name: 'Save' }).click();
  assert(await page.getByText('Automation saved').isVisible(), 'Automation save feedback is missing');
  await page.locator('.automation-history summary').click();
  assert(await page.getByText('Previous version').isVisible(), 'Automation history did not expand inline');
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(evidence, 'r3-automations-inline-dark.png'), fullPage: true });
  await page.locator('[data-automation="brief"]').focus();
  await page.keyboard.press('Enter');
  assert(await page.locator('[data-automation-editor="brief"]').isVisible(), 'Automation row is keyboard-dead');
  await page.reload({ waitUntil: 'networkidle' });
  assert((await page.locator('[data-automation="sleep"] .automation-next').textContent()).includes('Every week'), 'Automation cycle summary did not survive reload');
  results.push('Inline cycle/prompt editing + canonical variable autocomplete');

  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: width <= 390 ? 844 : 900 });
    for (const view of ['Mind', 'Connect', 'Character', 'Automations']) {
      await page.getByRole('button', { name: view, exact: true }).click();
      const dimensions = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert(dimensions.scroll <= dimensions.client, `${view} overflows horizontally at ${width}px (${dimensions.scroll}/${dimensions.client})`);
    }
  }
  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' });
  const mobilePage = await mobileContext.newPage();
  const mobileProblems = [];
  mobilePage.on('console', (message) => { if (message.type() === 'error' || message.type() === 'warning') mobileProblems.push(`${message.type()}: ${message.text()}`); });
  mobilePage.on('pageerror', (error) => mobileProblems.push(`pageerror: ${error.message}`));
  await mobilePage.goto(url, { waitUntil: 'networkidle' });
  await mobilePage.evaluate(() => localStorage.removeItem('viventium-v05-living-mind-r3'));
  await mobilePage.reload({ waitUntil: 'networkidle' });
  assert(await mobilePage.locator('#presenceDock').evaluate((element) => element.classList.contains('is-compact')), 'Mobile MIND should use collision-safe compact presence');
  assert(await mobilePage.locator('#dropButton').getAttribute('aria-label') === 'Open live presence controls', 'Compact presence trigger announces the wrong action');
  assert(await mobilePage.locator('#dropButton').getAttribute('aria-pressed') === null, 'Compact disclosure is incorrectly exposed as the listening toggle');
  await mobilePage.locator('#dropButton').click();
  assert(await mobilePage.locator('#presenceDock').evaluate((element) => element.classList.contains('mobile-open')), 'Compact mobile presence did not reveal listening controls');
  assert(await mobilePage.locator('[data-presence-mode="wing"]').isVisible(), 'Only when useful is unavailable from compact mobile presence');
  assert(JSON.parse(await mobilePage.evaluate(() => localStorage.getItem('viventium-v05-living-mind-r3'))).presence.in === true, 'Opening mobile presence controls changed the listening state');
  await mobilePage.keyboard.press('Escape');
  assert(await mobilePage.locator('#presenceDock').evaluate((element) => !element.classList.contains('mobile-open')), 'Escape did not close mobile presence controls');
  assert(await mobilePage.locator('#dropButton').evaluate((element) => document.activeElement === element), 'Closing mobile presence did not return focus to its trigger');
  await mobilePage.locator('#dropButton').click();
  await mobilePage.locator('#mindTitle').click();
  assert(await mobilePage.locator('#presenceDock').evaluate((element) => !element.classList.contains('mobile-open')), 'Mobile presence sheet did not dismiss outside');
  assert(await mobilePage.locator('#dropButton').getAttribute('aria-label') === 'Open live presence controls', 'Dismissed mobile presence kept the wrong accessible name');
  const mobileReceipt = mobilePage.locator('.reply-receipt');
  await mobileReceipt.locator('summary').click();
  assert(await mobilePage.locator('#presenceDock').evaluate((element) => element.classList.contains('is-compact')), 'Mobile presence did not clear the expanded reply receipt');
  assert((await mobilePage.locator('#dropButton').getAttribute('aria-label')).includes('live presence'), 'Compact mobile presence is not named');
  const mobileChrome = await mobilePage.evaluate(() => {
    const presence = document.querySelector('#presenceDock').getBoundingClientRect();
    const navigation = document.querySelector('.product-nav').getBoundingClientRect();
    return { presenceBottom: presence.bottom, navigationTop: navigation.top };
  });
  assert(mobileChrome.presenceBottom <= mobileChrome.navigationTop, `Compact presence overlaps mobile navigation (${mobileChrome.presenceBottom}/${mobileChrome.navigationTop})`);
  const mobileOverlap = await mobilePage.evaluate(() => {
    const presence = document.querySelector('#presenceDock').getBoundingClientRect();
    const composer = document.querySelector('#composer').getBoundingClientRect();
    return !(presence.right <= composer.left || presence.left >= composer.right || presence.bottom <= composer.top || presence.top >= composer.bottom);
  });
  assert(!mobileOverlap, 'Compact presence covers the mobile composer');
  await mobilePage.screenshot({ path: path.join(evidence, 'r3-mind-390-viewport-dark.png') });
  await captureWholeView(mobilePage, 'r3-mind-390-dark.png');
  await mobilePage.getByRole('button', { name: 'Character', exact: true }).click();
  await mobilePage.waitForTimeout(300);
  await mobilePage.screenshot({ path: path.join(evidence, 'r3-character-390-viewport-dark.png') });
  await captureWholeView(mobilePage, 'r3-character-390-dark.png');
  assert(await mobilePage.locator('#presenceDock').isVisible(), 'Persistent presence is missing on mobile');
  assert(await mobilePage.locator('.spectrum-band').count() === 9, 'Mobile Feeling Spectrum lost bands');
  await mobilePage.locator('[data-feeling-open="energy"]').click();
  await mobilePage.waitForTimeout(500);
  const inspectorTop = await mobilePage.locator('#feelingInspector').evaluate((element) => Math.round(element.getBoundingClientRect().top));
  assert(inspectorTop >= 80 && inspectorTop <= 190, `Selected Feeling controls did not reveal on mobile (${inspectorTop}px)`);
  assert(await mobilePage.locator('[data-feeling-slider="energy:now"]').evaluate((element) => document.activeElement === element), 'Mobile Feeling selection left keyboard focus offscreen');
  const mobileTabs = await mobilePage.locator('.range-tabs').evaluate((element) => ({ client: element.clientWidth, scroll: element.scrollWidth }));
  assert(mobileTabs.scroll <= mobileTabs.client, `Canonical Feeling levels are silently hidden on mobile (${mobileTabs.scroll}/${mobileTabs.client})`);
  assert(mobileProblems.length === 0, `Mobile console problems: ${mobileProblems.join(' | ')}`);
  await mobileContext.close();
  results.push('Zero horizontal overflow at 320/390/768/1024/1440');

  const zeroCapsuleContext = await browser.newContext({ viewport: { width: 1024, height: 900 }, colorScheme: 'dark' });
  const zeroCapsulePage = await zeroCapsuleContext.newPage();
  await zeroCapsulePage.goto(url, { waitUntil: 'networkidle' });
  await zeroCapsulePage.evaluate(() => localStorage.removeItem('viventium-v05-living-mind-r3'));
  await zeroCapsulePage.reload({ waitUntil: 'networkidle' });
  await zeroCapsulePage.getByRole('button', { name: 'Character', exact: true }).click();
  for (const band of ['energy', 'mood', 'drive', 'curiosity', 'vigilance', 'care', 'connection', 'openness', 'play']) {
    await zeroCapsulePage.locator(`[data-feeling-open="${band}"]`).click();
    await zeroCapsulePage.waitForFunction((id) => document.activeElement?.dataset?.feelingOpen === id, band);
    await zeroCapsulePage.locator(`[data-felt="${band}"]`).focus();
    await zeroCapsulePage.keyboard.press('Space');
    assert(await zeroCapsulePage.locator(`[data-felt="${band}"]`).isChecked() === false, `${band} remained Felt after keyboard toggle`);
  }
  const zeroCapsuleCount = await zeroCapsulePage.locator('#capsuleCount').textContent();
  assert(zeroCapsuleCount.includes('No state block'), `Zero Felt bands do not explain the empty capsule (${zeroCapsuleCount})`);
  assert((await zeroCapsulePage.locator('#feelingCapsule').textContent()).trim() === '', 'Zero Felt bands still emit a feeling-state capsule');
  await zeroCapsulePage.reload({ waitUntil: 'networkidle' });
  assert((await zeroCapsulePage.locator('#feelingCapsule').textContent()).trim() === '', 'Zero-row capsule did not remain empty after reload');
  await zeroCapsuleContext.close();
  results.push('Canonical empty capsule when no Feeling is Felt');

  const eraseContext = await browser.newContext({ viewport: { width: 1024, height: 900 }, colorScheme: 'dark' });
  const erasePage = await eraseContext.newPage();
  await erasePage.goto(url, { waitUntil: 'networkidle' });
  await erasePage.evaluate(() => localStorage.removeItem('viventium-v05-living-mind-r3'));
  await erasePage.reload({ waitUntil: 'networkidle' });
  await erasePage.getByRole('button', { name: 'Character', exact: true }).click();
  await erasePage.locator('[data-feeling-open="energy"]').click();
  await erasePage.getByRole('tab', { name: /electric/ }).click();
  await erasePage.locator('[data-range-addition="energy:4"]').fill('Synthetic wording that must be erased.');
  await erasePage.locator('[data-save-range="energy:4"]').click();
  await erasePage.locator('.reaction-settings > summary').click();
  await erasePage.locator('#reactionActivation').selectOption('disabled');
  await erasePage.locator('#reactionInstruction').fill('Erase-me synthetic instruction.');
  await erasePage.locator('#saveReactionInstruction').click();
  await erasePage.locator('#eraseFeelings').click();
  await erasePage.locator('#confirmEraseFeelings').click();
  assert(await erasePage.locator('#feelingsEnabled').isChecked() === false, 'Confirmed erase did not turn Feelings off');
  assert(await erasePage.locator('.reaction-row').count() === 0, 'Confirmed erase did not remove the local trail');
  assert((await erasePage.locator('#feelingCapsule').textContent()).trim() === '', 'Confirmed erase left an active capsule');
  await erasePage.reload({ waitUntil: 'networkidle' });
  assert(await erasePage.locator('#feelingsEnabled').isChecked() === false, 'Confirmed erase did not survive reload');
  const erasedState = JSON.parse(await erasePage.evaluate(() => localStorage.getItem('viventium-v05-living-mind-r3')));
  assert(Object.keys(erasedState.feelings.energy.additions).length === 0, 'Confirmed erase retained personal Feeling wording');
  assert(erasedState.reactionActivation === 'always' && erasedState.reactionInstruction.startsWith('React to what genuinely moves Viventium.'), 'Confirmed erase retained personal Reaction Cortex configuration');
  await erasePage.setViewportSize({ width: 390, height: 844 });
  await erasePage.locator('[data-feeling-open="mood"]').click();
  await erasePage.waitForTimeout(500);
  assert(await erasePage.locator('[data-feeling-slider="mood:nature"]').evaluate((element) => document.activeElement === element), 'Paused mobile Feelings selection did not focus an enabled control');
  await eraseContext.close();
  results.push('Reaction Cortex health/config + confirmed erase');

  const brokenImages = await page.locator('img').evaluateAll((images) => images.filter((image) => !image.complete || image.naturalWidth === 0).map((image) => image.src));
  assert(brokenImages.length === 0, `Broken local images: ${brokenImages.join(', ')}`);
  const duplicateIds = await page.evaluate(() => [...document.querySelectorAll('[id]')].map((element) => element.id).filter((id, index, ids) => ids.indexOf(id) !== index));
  assert(duplicateIds.length === 0, `Duplicate element IDs: ${duplicateIds.join(', ')}`);
  assert(consoleProblems.length === 0, `Browser console problems: ${consoleProblems.join(' | ')}`);
  results.push('Local marks loaded + clean console');

  const lightProblems = [];
  const lightContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
  const lightPage = await lightContext.newPage();
  lightPage.on('console', (message) => {
    if (message.type() === 'error' || message.type() === 'warning') lightProblems.push(`${message.type()}: ${message.text()}`);
  });
  lightPage.on('pageerror', (error) => lightProblems.push(`pageerror: ${error.message}`));
  await lightPage.goto(url, { waitUntil: 'networkidle' });
  await lightPage.evaluate(() => localStorage.removeItem('viventium-v05-living-mind-r3'));
  await lightPage.reload({ waitUntil: 'networkidle' });
  await lightPage.locator('.reply-receipt summary').click();
  await captureWholeView(lightPage, 'r3-mind-light.png');
  await lightPage.getByRole('button', { name: 'Character', exact: true }).click();
  await lightPage.waitForTimeout(300);
  await captureWholeView(lightPage, 'r3-character-light.png');
  for (const width of [1440, 1024, 768, 390, 320]) {
    await lightPage.setViewportSize({ width, height: width <= 390 ? 844 : 900 });
    for (const view of ['Mind', 'Connect', 'Character', 'Automations']) {
      await lightPage.getByRole('button', { name: view, exact: true }).click();
      const dimensions = await lightPage.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert(dimensions.scroll <= dimensions.client, `Light ${view} overflows at ${width}px (${dimensions.scroll}/${dimensions.client})`);
    }
  }
  assert(lightProblems.length === 0, `Light-theme console problems: ${lightProblems.join(' | ')}`);
  await lightPage.goto(brandUrl, { waitUntil: 'networkidle' });
  assert(await lightPage.getByText('LIVING LEDGER · V0.5 R2').isVisible(), 'Brand Kit did not advance to R2');
  await lightPage.screenshot({ path: path.join(evidence, 'r3-brand-kit-light.png'), fullPage: true });
  await lightContext.close();
  results.push('Light + dark visual surfaces');

  const brandDarkContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'dark' });
  const brandDarkPage = await brandDarkContext.newPage();
  await brandDarkPage.goto(brandUrl, { waitUntil: 'networkidle' });
  await brandDarkPage.getByRole('button', { name: 'Dark', exact: true }).click();
  await brandDarkPage.screenshot({ path: path.join(evidence, 'r3-brand-kit-dark.png'), fullPage: true });
  await brandDarkPage.setViewportSize({ width: 390, height: 844 });
  const brandDimensions = await brandDarkPage.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  assert(brandDimensions.scroll <= brandDimensions.client, `Brand Kit overflows at 390px (${brandDimensions.scroll}/${brandDimensions.client})`);
  await brandDarkContext.close();
  results.push('Living-ledger Brand Kit aligned + responsive');

  const reducedContext = await browser.newContext({ viewport: { width: 1024, height: 800 }, reducedMotion: 'reduce' });
  const reducedPage = await reducedContext.newPage();
  await reducedPage.goto(url, { waitUntil: 'networkidle' });
  const reducedMotionDuration = await reducedPage.locator('.presence-orb i').first().evaluate((element) => getComputedStyle(element).animationDuration);
  assert(['0s', '0.001ms', '1e-06s'].includes(reducedMotionDuration), `Reduced motion still animates (${reducedMotionDuration})`);
  await reducedContext.close();
  results.push('Reduced-motion preference respected');

  await browser.close();
  process.stdout.write(JSON.stringify({ status: 'PASS', results, evidence: [
    'r3-mind-dark.png', 'r3-connect-discovery-dark.png', 'r3-email-all-in-one-dark.png',
    'r3-character-spectrum-dark.png', 'r3-character-reaction-cortex-dark.png', 'r3-character-after-change-dark.png', 'r3-automations-inline-dark.png',
    'r3-mind-390-viewport-dark.png', 'r3-mind-390-dark.png', 'r3-character-390-viewport-dark.png', 'r3-character-390-dark.png',
    'r3-mind-light.png', 'r3-character-light.png',
    'r3-brand-kit-light.png', 'r3-brand-kit-dark.png',
  ] }, null, 2));
  process.exit(0);
})().catch(async (error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
