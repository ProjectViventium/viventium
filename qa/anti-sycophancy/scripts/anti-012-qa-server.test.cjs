#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  createAnti012QaServer,
  evaluateExactlyOnceFixtureEffect,
} = require("./anti-012-qa-server.cjs");

async function withServer(scenario, callback) {
  const qaServer = createAnti012QaServer({ classifierScenario: scenario });
  const address = await qaServer.listen();
  try {
    await callback({ qaServer, baseUrl: `http://127.0.0.1:${address.port}` });
  } finally {
    await qaServer.close();
  }
}

async function classifierRequest(baseUrl, { signal } = {}) {
  return fetch(`${baseUrl}/v1/chat/completions`, {
    method: "POST",
    signal,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: "qa-classifier", messages: [] }),
  });
}

test("classifier scenarios are selected at the QA endpoint boundary, never from prompt text", async () => {
  await withServer("no-classified", async ({ baseUrl }) => {
    const response = await classifierRequest(baseUrl);
    const body = await response.json();
    assert.match(body.choices[0].message.content, /"activate":false/);
  });
  await withServer("fast-before-boundary", async ({ baseUrl }) => {
    const response = await classifierRequest(baseUrl);
    const body = await response.json();
    assert.match(body.choices[0].message.content, /"activate":true/);
  });
});

test("timeout scenarios are deterministic without sleep-based timing", async () => {
  await withServer("timed-out-no-new", async ({ qaServer, baseUrl }) => {
    const controller = new AbortController();
    const first = classifierRequest(baseUrl, {
      signal: controller.signal,
    }).catch((error) => error.name);
    await qaServer.waitForClassifierRequests(1);
    assert.equal(qaServer.metrics().classifierResponseCount, 0);
    controller.abort();
    assert.equal(await first, "AbortError");
  });

  await withServer(
    "timed-out-new-late-recovery",
    async ({ qaServer, baseUrl }) => {
      const controller = new AbortController();
      const first = classifierRequest(baseUrl, {
        signal: controller.signal,
      }).catch((error) => error.name);
      await qaServer.waitForClassifierRequests(1);
      const lateResponse = await classifierRequest(baseUrl);
      const lateBody = await lateResponse.json();
      assert.match(lateBody.choices[0].message.content, /"activate":true/);
      controller.abort();
      assert.equal(await first, "AbortError");
      assert.deepEqual(qaServer.publicMetrics(), {
        classifierRequestCount: 2,
        classifierResponseCount: 1,
        classifierPendingCount: 1,
        effectRequestCount: 0,
        effectAppliedCount: 0,
        effectDuplicateCount: 0,
        effectCleanupCount: 0,
      });
    },
  );
});

test("fixture arithmetic requires one request, one application, no duplicate, and cleanup", async () => {
  await withServer("no-classified", async ({ baseUrl }) => {
    const idempotencyKey = "private-product-turn-effect-key";
    const applied = await fetch(`${baseUrl}/qa/effect`, {
      method: "POST",
      headers: { "idempotency-key": idempotencyKey },
    }).then((response) => response.json());
    assert.deepEqual(applied, {
      applied: true,
      requestCount: 1,
      appliedCount: 1,
      duplicateCount: 0,
    });

    const beforeCleanup = await fetch(`${baseUrl}/qa/metrics`).then(
      (response) => response.json(),
    );
    assert.deepEqual(
      evaluateExactlyOnceFixtureEffect(beforeCleanup, {
        cleanupRequired: false,
      }),
      { pass: true, failures: [] },
    );

    const cleanup = await fetch(`${baseUrl}/qa/effect`, {
      method: "DELETE",
      headers: { "idempotency-key": idempotencyKey },
    }).then((response) => response.json());
    assert.deepEqual(cleanup, { deletedCount: 1, cleanupCount: 1 });

    const afterCleanup = await fetch(`${baseUrl}/qa/metrics`).then((response) =>
      response.json(),
    );
    assert.deepEqual(
      evaluateExactlyOnceFixtureEffect(afterCleanup, {
        cleanupRequired: true,
      }),
      { pass: true, failures: [] },
    );
  });
});

test("fixture arithmetic rejects receiver-deduped duplicate requests", () => {
  assert.deepEqual(
    evaluateExactlyOnceFixtureEffect(
      {
        effectRequestCount: 2,
        effectAppliedCount: 1,
        effectDuplicateCount: 1,
        effectCleanupCount: 1,
        effectActiveReceiptCount: 0,
      },
      { cleanupRequired: true },
    ),
    {
      pass: false,
      failures: ["effect_request_count_not_one", "effect_duplicate_count_not_zero"],
    },
  );
});

test("fixture-only effect control deduplicates retries and proves explicit cleanup", async () => {
  await withServer("no-classified", async ({ baseUrl }) => {
    const idempotencyKey = "private-synthetic-effect-key";
    const callEffect = () =>
      fetch(`${baseUrl}/qa/effect`, {
        method: "POST",
        headers: { "idempotency-key": idempotencyKey },
      }).then((response) => response.json());

    assert.deepEqual(await callEffect(), {
      applied: true,
      requestCount: 1,
      appliedCount: 1,
      duplicateCount: 0,
    });
    assert.deepEqual(await callEffect(), {
      applied: false,
      requestCount: 2,
      appliedCount: 1,
      duplicateCount: 1,
    });

    const cleanup = await fetch(`${baseUrl}/qa/effect`, {
      method: "DELETE",
      headers: { "idempotency-key": idempotencyKey },
    }).then((response) => response.json());
    assert.deepEqual(cleanup, { deletedCount: 1, cleanupCount: 1 });

    const afterCleanup = await fetch(`${baseUrl}/qa/metrics`).then((response) =>
      response.json(),
    );
    assert.equal(afterCleanup.effectActiveReceiptCount, 0);
    assert.equal(JSON.stringify(afterCleanup).includes(idempotencyKey), false);
  });
});
