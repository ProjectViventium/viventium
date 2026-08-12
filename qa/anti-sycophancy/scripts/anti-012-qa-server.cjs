#!/usr/bin/env node
"use strict";

const http = require("node:http");

const CLASSIFIER_SCENARIOS = new Set([
  "no-classified",
  "fast-before-boundary",
  "timed-out-no-new",
  "timed-out-new-late-recovery",
]);

function classifierBody(activate) {
  return {
    id: "qa-classifier-response",
    object: "chat.completion",
    created: 0,
    model: "qa-classifier",
    choices: [
      {
        index: 0,
        finish_reason: "stop",
        message: {
          role: "assistant",
          content: JSON.stringify({
            activate,
            confidence: activate ? 1 : 0,
            reason: activate ? "qa_positive" : "qa_negative",
          }),
        },
      },
    ],
    usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  };
}

function sendJson(response, statusCode, value) {
  if (response.destroyed || response.writableEnded) return;
  response.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(`${JSON.stringify(value)}\n`);
}

function evaluateExactlyOnceFixtureEffect(
  metrics,
  { cleanupRequired = false } = {},
) {
  const failures = [];
  if (Number(metrics?.effectRequestCount) !== 1) {
    failures.push("effect_request_count_not_one");
  }
  if (Number(metrics?.effectAppliedCount) !== 1) {
    failures.push("effect_applied_count_not_one");
  }
  if (Number(metrics?.effectDuplicateCount) !== 0) {
    failures.push("effect_duplicate_count_not_zero");
  }
  if (cleanupRequired) {
    if (Number(metrics?.effectCleanupCount) !== 1) {
      failures.push("effect_cleanup_count_not_one");
    }
    if (Number(metrics?.effectActiveReceiptCount) !== 0) {
      failures.push("effect_active_receipt_count_not_zero");
    }
  } else if (Number(metrics?.effectActiveReceiptCount) !== 1) {
    failures.push("effect_active_receipt_count_not_one");
  }
  return { pass: failures.length === 0, failures };
}

function createAnti012QaServer({ classifierScenario = "no-classified" } = {}) {
  if (!CLASSIFIER_SCENARIOS.has(classifierScenario)) {
    throw new Error("unsupported_anti_012_classifier_scenario");
  }
  const counters = {
    classifierRequestCount: 0,
    classifierResponseCount: 0,
    effectRequestCount: 0,
    effectAppliedCount: 0,
    effectDuplicateCount: 0,
    effectCleanupCount: 0,
  };
  const pendingClassifierResponses = new Set();
  const effectReceipts = new Set();
  const classifierWaiters = new Set();
  const sockets = new Set();

  const publicMetrics = () => ({
    classifierRequestCount: counters.classifierRequestCount,
    classifierResponseCount: counters.classifierResponseCount,
    classifierPendingCount: pendingClassifierResponses.size,
    effectRequestCount: counters.effectRequestCount,
    effectAppliedCount: counters.effectAppliedCount,
    effectDuplicateCount: counters.effectDuplicateCount,
    effectCleanupCount: counters.effectCleanupCount,
  });

  const notifyClassifierWaiters = () => {
    for (const waiter of classifierWaiters) {
      if (counters.classifierRequestCount >= waiter.count) {
        classifierWaiters.delete(waiter);
        waiter.resolve();
      }
    }
  };

  const server = http.createServer((request, response) => {
    const pathname = new URL(request.url || "/", "http://127.0.0.1").pathname;
    if (
      request.method === "POST" &&
      (pathname === "/v1/chat/completions" || pathname === "/chat/completions")
    ) {
      counters.classifierRequestCount += 1;
      const ordinal = counters.classifierRequestCount;
      notifyClassifierWaiters();
      const mustRemainPending =
        classifierScenario === "timed-out-no-new" ||
        (classifierScenario === "timed-out-new-late-recovery" && ordinal === 1);
      if (mustRemainPending) {
        pendingClassifierResponses.add(response);
        response.on("close", () => pendingClassifierResponses.delete(response));
        request.resume();
        return;
      }
      const activate =
        classifierScenario === "fast-before-boundary" ||
        classifierScenario === "timed-out-new-late-recovery";
      counters.classifierResponseCount += 1;
      request.resume();
      sendJson(response, 200, classifierBody(activate));
      return;
    }

    if (pathname === "/qa/effect" && request.method === "POST") {
      const key = String(request.headers["idempotency-key"] || "").trim();
      if (!key || key.length > 256) {
        request.resume();
        sendJson(response, 400, { error: "valid_idempotency_key_required" });
        return;
      }
      counters.effectRequestCount += 1;
      const applied = !effectReceipts.has(key);
      if (applied) {
        effectReceipts.add(key);
        counters.effectAppliedCount += 1;
      } else {
        counters.effectDuplicateCount += 1;
      }
      request.resume();
      sendJson(response, 200, {
        applied,
        requestCount: counters.effectRequestCount,
        appliedCount: counters.effectAppliedCount,
        duplicateCount: counters.effectDuplicateCount,
      });
      return;
    }

    if (pathname === "/qa/effect" && request.method === "DELETE") {
      const key = String(request.headers["idempotency-key"] || "").trim();
      const deletedCount = key && effectReceipts.delete(key) ? 1 : 0;
      counters.effectCleanupCount += deletedCount;
      request.resume();
      sendJson(response, 200, {
        deletedCount,
        cleanupCount: counters.effectCleanupCount,
      });
      return;
    }

    if (pathname === "/qa/metrics" && request.method === "GET") {
      request.resume();
      sendJson(response, 200, {
        ...publicMetrics(),
        effectActiveReceiptCount: effectReceipts.size,
      });
      return;
    }

    request.resume();
    sendJson(response, 404, { error: "not_found" });
  });

  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
  });

  return {
    listen(port = 0) {
      return new Promise((resolve, reject) => {
        server.once("error", reject);
        server.listen(port, "127.0.0.1", () => {
          server.off("error", reject);
          resolve(server.address());
        });
      });
    },
    waitForClassifierRequests(count) {
      if (counters.classifierRequestCount >= count) return Promise.resolve();
      return new Promise((resolve) =>
        classifierWaiters.add({ count, resolve }),
      );
    },
    metrics: () => ({ ...counters }),
    publicMetrics,
    close() {
      for (const response of pendingClassifierResponses) response.destroy();
      pendingClassifierResponses.clear();
      for (const socket of sockets) socket.destroy();
      classifierWaiters.clear();
      return new Promise((resolve) => server.close(() => resolve()));
    },
  };
}

function parseCliArgs(argv) {
  let classifierScenario = "no-classified";
  let port = 0;
  for (const arg of argv) {
    if (arg.startsWith("--scenario=")) classifierScenario = arg.slice(11);
    else if (arg.startsWith("--port="))
      port = Number.parseInt(arg.slice(7), 10);
    else throw new Error("unknown_anti_012_qa_server_argument");
  }
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new Error("invalid_anti_012_qa_server_port");
  }
  return { classifierScenario, port };
}

module.exports = {
  CLASSIFIER_SCENARIOS,
  createAnti012QaServer,
  evaluateExactlyOnceFixtureEffect,
  parseCliArgs,
};

if (require.main === module) {
  const args = parseCliArgs(process.argv.slice(2));
  const qaServer = createAnti012QaServer(args);
  qaServer.listen(args.port).then((address) => {
    process.stdout.write(`${JSON.stringify({ port: address.port })}\n`);
  });
  const shutdown = () => qaServer.close().finally(() => process.exit(0));
  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
}
