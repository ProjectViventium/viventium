#!/usr/bin/env node
"use strict";

const http = require("node:http");

const LOOPBACK_HOST = "127.0.0.1";
const DEFAULT_PORT = 18082;
const MODES = Object.freeze([
  "healthy-result",
  "healthy-empty",
  "429",
  "401",
  "503",
  "400",
]);
const MODE_SET = new Set(MODES);

const SEARCH_RESPONSE = Object.freeze({
  query: "synthetic-public-safe-query",
  number_of_results: 1,
  results: Object.freeze([
    Object.freeze({
      title: "Synthetic public-safe result",
      url: "https://example.com/",
      content: "Deterministic public-safe evidence for anti-sycophancy QA.",
      engine: "viventium-qa",
      engines: Object.freeze(["viventium-qa"]),
      category: "general",
      score: 1,
    }),
  ]),
  answers: Object.freeze([]),
  corrections: Object.freeze([]),
  infoboxes: Object.freeze([]),
  suggestions: Object.freeze([]),
  unresponsive_engines: Object.freeze([]),
});

const EMPTY_SEARCH_RESPONSE = Object.freeze({
  query: "synthetic-public-safe-query",
  number_of_results: 0,
  results: Object.freeze([]),
  answers: Object.freeze([]),
  corrections: Object.freeze([]),
  infoboxes: Object.freeze([]),
  suggestions: Object.freeze([]),
  unresponsive_engines: Object.freeze([]),
});

const FAILURE_RESPONSES = Object.freeze({
  429: Object.freeze({
    status: 429,
    retryAfter: "2",
    body: Object.freeze({
      error: Object.freeze({
        code: "rate_limited",
        message: "Synthetic rate limit.",
      }),
    }),
  }),
  401: Object.freeze({
    status: 401,
    body: Object.freeze({
      error: Object.freeze({
        code: "unauthorized",
        message: "Synthetic authentication rejection.",
      }),
    }),
  }),
  503: Object.freeze({
    status: 503,
    body: Object.freeze({
      error: Object.freeze({
        code: "provider_unavailable",
        message: "Synthetic provider unavailable.",
      }),
    }),
  }),
  400: Object.freeze({
    status: 400,
    body: Object.freeze({
      error: Object.freeze({
        code: "request_rejected",
        message: "Synthetic request rejection.",
      }),
    }),
  }),
});

function parsePort(rawPort) {
  const port = Number(rawPort);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("--port must be an integer from 1 through 65535");
  }
  return port;
}

function parseArgs(argv) {
  let mode = "";
  let port = DEFAULT_PORT;
  for (const argument of argv) {
    if (argument.startsWith("--mode=")) {
      mode = argument.slice("--mode=".length);
      continue;
    }
    if (argument.startsWith("--port=")) {
      port = parsePort(argument.slice("--port=".length));
      continue;
    }
    throw new Error("Unknown option; only --mode and --port are accepted");
  }
  if (!MODE_SET.has(mode)) {
    throw new Error(`--mode must be one of: ${MODES.join(", ")}`);
  }
  return { mode, port };
}

function isLoopbackAuthority(authority) {
  const normalized = String(authority || "")
    .trim()
    .toLowerCase();
  return (
    normalized === "127.0.0.1" ||
    normalized.startsWith("127.0.0.1:") ||
    normalized === "localhost" ||
    normalized.startsWith("localhost:")
  );
}

function publicHeaders(extra = {}) {
  return {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'",
    "Content-Type": "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
    ...extra,
  };
}

function createReceipt(clock) {
  const startedAt = clock();
  let lastRequestAt = null;
  let requestCount = 0;
  const statusCounts = {};

  return Object.freeze({
    record(status) {
      requestCount += 1;
      lastRequestAt = clock();
      const statusKey = String(status);
      statusCounts[statusKey] = (statusCounts[statusKey] || 0) + 1;
    },
    snapshot() {
      return {
        startedAt,
        lastRequestAt,
        requestCount,
        statusCounts: { ...statusCounts },
      };
    },
  });
}

function createSearchFaultSimulator({
  mode,
  clock = () => new Date().toISOString(),
} = {}) {
  if (!MODE_SET.has(mode)) {
    throw new Error("A supported immutable mode is required");
  }
  const selectedMode = mode;
  const receipt = createReceipt(clock);

  function sendJson(response, status, body, headers = {}) {
    receipt.record(status);
    response.writeHead(status, publicHeaders(headers));
    response.end(JSON.stringify(body));
  }

  function reject(response, status, code, message, headers = {}) {
    sendJson(response, status, { error: { code, message } }, headers);
  }

  const server = http.createServer((request, response) => {
    if (!isLoopbackAuthority(request.headers.host)) {
      request.resume();
      reject(
        response,
        421,
        "loopback_authority_required",
        "Loopback authority required.",
      );
      return;
    }

    const requestTarget = String(request.url || "");
    if (!requestTarget.startsWith("/")) {
      request.resume();
      reject(
        response,
        400,
        "invalid_request_target",
        "Invalid request target.",
      );
      return;
    }

    let url;
    try {
      url = new URL(requestTarget, `http://${LOOPBACK_HOST}`);
    } catch {
      request.resume();
      reject(
        response,
        400,
        "invalid_request_target",
        "Invalid request target.",
      );
      return;
    }

    if (url.pathname === "/health") {
      if (request.method !== "GET") {
        request.resume();
        reject(response, 405, "method_not_allowed", "Method not allowed.", {
          Allow: "GET",
        });
        return;
      }
      const status = selectedMode === "503" ? 503 : 200;
      receipt.record(status);
      response.writeHead(status, publicHeaders());
      response.end(
        JSON.stringify({
          service: "viventium-search-fault-simulator",
          status: selectedMode === "503" ? "degraded" : "ready",
          mode: selectedMode,
          receipt: receipt.snapshot(),
        }),
      );
      return;
    }

    if (url.pathname !== "/search") {
      request.resume();
      reject(response, 404, "not_found", "Route not found.");
      return;
    }

    if (request.method !== "GET") {
      request.resume();
      reject(response, 405, "method_not_allowed", "Method not allowed.", {
        Allow: "GET",
      });
      return;
    }

    const query = url.searchParams.get("q");
    const format = url.searchParams.get("format");
    if (!query || !query.trim() || format !== "json") {
      reject(
        response,
        400,
        "invalid_request",
        "A query and JSON format are required.",
      );
      return;
    }

    if (selectedMode === "healthy-result") {
      sendJson(response, 200, SEARCH_RESPONSE);
      return;
    }
    if (selectedMode === "healthy-empty") {
      sendJson(response, 200, EMPTY_SEARCH_RESPONSE);
      return;
    }

    const failure = FAILURE_RESPONSES[selectedMode];
    sendJson(
      response,
      failure.status,
      failure.body,
      failure.retryAfter ? { "Retry-After": failure.retryAfter } : {},
    );
  });

  server.requestTimeout = 5_000;
  server.headersTimeout = 5_000;
  server.keepAliveTimeout = 1_000;
  server.on("clientError", (_error, socket) => {
    receipt.record(400);
    if (!socket.writable) return;
    socket.end(
      "HTTP/1.1 400 Bad Request\r\n" +
        "Connection: close\r\n" +
        "Content-Type: application/json; charset=utf-8\r\n" +
        "X-Content-Type-Options: nosniff\r\n" +
        "\r\n" +
        '{"error":{"code":"bad_request","message":"Bad request."}}',
    );
  });

  return Object.freeze({
    mode: selectedMode,
    listen(port) {
      return new Promise((resolve, reject) => {
        const onError = (error) => {
          server.off("listening", onListening);
          reject(error);
        };
        const onListening = () => {
          server.off("error", onError);
          resolve(server.address());
        };
        server.once("error", onError);
        server.once("listening", onListening);
        server.listen({ host: LOOPBACK_HOST, port, exclusive: true });
      });
    },
    close() {
      if (!server.listening) return Promise.resolve();
      return new Promise((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      });
    },
    address() {
      return server.address();
    },
    receipt() {
      return receipt.snapshot();
    },
  });
}

async function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch {
    process.stderr.write(
      "Search fault simulator startup configuration is invalid.\n",
    );
    process.exitCode = 2;
    return;
  }

  const simulator = createSearchFaultSimulator({ mode: options.mode });
  let address;
  try {
    address = await simulator.listen(options.port);
  } catch {
    process.stderr.write(
      "Search fault simulator could not bind its loopback port.\n",
    );
    process.exitCode = 1;
    return;
  }
  process.stdout.write(
    `${JSON.stringify({
      event: "ready",
      host: LOOPBACK_HOST,
      port: address.port,
      mode: simulator.mode,
      health: "/health",
      search: "/search",
    })}\n`,
  );

  let stopping = false;
  const stop = async () => {
    if (stopping) return;
    stopping = true;
    await simulator.close();
    process.stdout.write(
      `${JSON.stringify({ event: "stopped", receipt: simulator.receipt() })}\n`,
    );
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
}

if (require.main === module) {
  main().catch(() => {
    process.stderr.write("Search fault simulator stopped unexpectedly.\n");
    process.exitCode = 1;
  });
}

module.exports = {
  LOOPBACK_HOST,
  MODES,
  createSearchFaultSimulator,
  parseArgs,
};
