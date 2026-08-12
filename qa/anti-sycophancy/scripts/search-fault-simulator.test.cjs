#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const http = require("node:http");
const test = require("node:test");

const {
  LOOPBACK_HOST,
  MODES,
  createSearchFaultSimulator,
  parseArgs,
} = require("./search-fault-simulator.cjs");

function requestJson({
  port,
  method = "GET",
  path = "/health",
  headers = {},
  body = "",
}) {
  return new Promise((resolve, reject) => {
    const request = http.request(
      {
        host: LOOPBACK_HOST,
        port,
        method,
        path,
        headers,
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const rawBody = Buffer.concat(chunks).toString("utf8");
          resolve({
            status: response.statusCode,
            headers: response.headers,
            body: rawBody ? JSON.parse(rawBody) : null,
          });
        });
      },
    );
    request.on("error", reject);
    if (body) request.write(body);
    request.end();
  });
}

async function withSimulator(mode, callback, options = {}) {
  const simulator = createSearchFaultSimulator({ mode, ...options });
  const address = await simulator.listen(0);
  try {
    await callback({ simulator, port: address.port });
  } finally {
    await simulator.close();
  }
}

test("requires one immutable startup mode and rejects unsafe CLI options", () => {
  assert.deepEqual(MODES, [
    "healthy-result",
    "healthy-empty",
    "429",
    "401",
    "503",
    "400",
  ]);
  assert.throws(() => parseArgs([]), /--mode/);
  assert.throws(() => parseArgs(["--mode=unknown"]), /mode/);
  assert.throws(
    () => parseArgs(["--mode=401", "--host=0.0.0.0"]),
    /Unknown option/,
  );
  assert.throws(() => parseArgs(["--mode=401", "--port=not-a-port"]), /port/);
  assert.deepEqual(parseArgs(["--mode=429", "--port=18082"]), {
    mode: "429",
    port: 18082,
  });
});

test("binds only to IPv4 loopback and serves the real SearXNG GET search shape", async () => {
  await withSimulator("healthy-result", async ({ simulator, port }) => {
    const privateAuthorization = ["Bearer", "private-header"].join(" ");
    assert.deepEqual(simulator.address(), {
      address: LOOPBACK_HOST,
      family: "IPv4",
      port,
    });

    const response = await requestJson({
      port,
      path: "/search?q=private-value&format=json&pageno=1&categories=general&safesearch=1",
      headers: { Authorization: privateAuthorization },
    });

    assert.equal(response.status, 200);
    assert.equal(
      response.headers["content-type"],
      "application/json; charset=utf-8",
    );
    assert.equal(response.body.number_of_results, 1);
    assert.deepEqual(response.body.results, [
      {
        title: "Synthetic public-safe result",
        url: "https://example.com/",
        content: "Deterministic public-safe evidence for anti-sycophancy QA.",
        engine: "viventium-qa",
        engines: ["viventium-qa"],
        category: "general",
        score: 1,
      },
    ]);
    assert.equal(
      JSON.stringify(response.body).includes("private-value"),
      false,
    );
    assert.equal(
      JSON.stringify(simulator.receipt()).includes("private-header"),
      false,
    );
  });
});

test("distinguishes healthy empty evidence from a failed search", async () => {
  await withSimulator("healthy-empty", async ({ port }) => {
    const response = await requestJson({
      port,
      path: "/search?q=synthetic&format=json",
    });
    assert.equal(response.status, 200);
    assert.equal(response.body.number_of_results, 0);
    assert.deepEqual(response.body.results, []);
    assert.deepEqual(response.body.unresponsive_engines, []);
  });
});

test("returns deterministic HTTP failure classes and Retry-After", async () => {
  const cases = [
    { mode: "429", status: 429, code: "rate_limited", retryAfter: "2" },
    { mode: "401", status: 401, code: "unauthorized" },
    { mode: "503", status: 503, code: "provider_unavailable" },
    { mode: "400", status: 400, code: "request_rejected" },
  ];

  for (const expected of cases) {
    await withSimulator(expected.mode, async ({ port }) => {
      const response = await requestJson({
        port,
        path: "/search?q=synthetic&format=json",
      });
      assert.equal(response.status, expected.status);
      assert.equal(response.body.error.code, expected.code);
      assert.equal(response.headers["retry-after"], expected.retryAfter);
    });
  }
});

test("reports degraded health only for the unavailable-provider mode", async () => {
  for (const mode of MODES) {
    await withSimulator(mode, async ({ port }) => {
      const response = await requestJson({ port });
      assert.equal(response.status, mode === "503" ? 503 : 200);
      assert.equal(response.body.service, "viventium-search-fault-simulator");
      assert.equal(response.body.mode, mode);
      assert.equal(response.body.status, mode === "503" ? "degraded" : "ready");
      assert.equal(Object.isFrozen(response.body), false);
    });
  }
});

test("fails closed for unexpected routes, methods, host authorities, and malformed search requests", async () => {
  await withSimulator("healthy-result", async ({ port }) => {
    const wrongRoute = await requestJson({
      port,
      path: "/unexpected?q=private-value",
    });
    assert.equal(wrongRoute.status, 404);
    assert.equal(wrongRoute.body.error.code, "not_found");

    const wrongMethod = await requestJson({
      port,
      method: "POST",
      path: "/search?q=private-value&format=json",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ private: "private-body" }),
    });
    assert.equal(wrongMethod.status, 405);
    assert.equal(wrongMethod.headers.allow, "GET");

    const wrongHost = await requestJson({
      port,
      path: "/search?q=private-value&format=json",
      headers: { Host: "example.com" },
    });
    assert.equal(wrongHost.status, 421);

    const missingQuery = await requestJson({
      port,
      path: "/search?format=json",
    });
    assert.equal(missingQuery.status, 400);
    assert.equal(missingQuery.body.error.code, "invalid_request");

    const wrongFormat = await requestJson({
      port,
      path: "/search?q=synthetic&format=html",
    });
    assert.equal(wrongFormat.status, 400);
    assert.equal(wrongFormat.body.error.code, "invalid_request");
  });
});

test("keeps receipts to counts, statuses, and timestamps without request data", async () => {
  const times = [
    "2026-08-10T12:00:00.000Z",
    "2026-08-10T12:00:01.000Z",
    "2026-08-10T12:00:02.000Z",
    "2026-08-10T12:00:03.000Z",
  ];
  let timeIndex = 0;
  await withSimulator(
    "healthy-result",
    async ({ simulator, port }) => {
      await requestJson({
        port,
        path: "/search?q=never-record-this&format=json",
        headers: { "X-Private": "never-record-this-header" },
      });
      await requestJson({ port, path: "/unexpected" });

      assert.deepEqual(simulator.receipt(), {
        startedAt: "2026-08-10T12:00:00.000Z",
        lastRequestAt: "2026-08-10T12:00:02.000Z",
        requestCount: 2,
        statusCounts: { 200: 1, 404: 1 },
      });
      const serialized = JSON.stringify(simulator.receipt());
      assert.equal(serialized.includes("never-record-this"), false);
      assert.equal(serialized.includes("search"), false);
      assert.equal(serialized.includes("unexpected"), false);
    },
    { clock: () => times[timeIndex++] },
  );
});

test("does not expose a runtime mode-switch route", async () => {
  await withSimulator("401", async ({ port }) => {
    const response = await requestJson({
      port,
      method: "POST",
      path: "/mode",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "healthy-result" }),
    });
    assert.equal(response.status, 404);

    const stillUnauthorized = await requestJson({
      port,
      path: "/search?q=synthetic&format=json",
    });
    assert.equal(stillUnauthorized.status, 401);
  });
});
