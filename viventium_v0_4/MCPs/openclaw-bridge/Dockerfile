# VIVENTIUM START
# Dockerfile for the OpenClaw Bridge MCP server.
# Runs the FastMCP server that manages per-user OpenClaw Gateway instances.
#
# Includes Node.js + OpenClaw for "direct" child process mode.
# Pin versions for reproducibility.
# VIVENTIUM END

FROM python:3.12-slim

WORKDIR /app

# Pin Node.js 22.x LTS and OpenClaw to a specific version
# OpenClaw v2026.2.9 — matches the version cloned into viventium_v0_4/openclaw
ARG NODE_MAJOR=22
ARG OPENCLAW_VERSION=2026.2.9

# Install Node.js (pinned major) and OpenClaw (pinned version)
RUN apt-get update && \
    # VIVENTIUM START: openclaw npm install may resolve git-based deps.
    # Also install lsof because `openclaw gateway --force` depends on it.
    apt-get install -y --no-install-recommends curl ca-certificates gnupg git lsof && \
    # VIVENTIUM END
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | \
      gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" | \
      tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    npm install -g "openclaw@${OPENCLAW_VERSION}" && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mcp_server.py openclaw_manager.py ./
# VIVENTIUM START: Bundle channel bridge plugin for in-container OpenClaw loading.
# Keep folder name aligned with plugin id to avoid OpenClaw id-hint mismatch warnings.
COPY viventium-channel-plugin ./viventium-channel-bridge
# VIVENTIUM END

# Default port for MCP server
EXPOSE 8086

# Health check for the MCP bridge (NOT OpenClaw gateway)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8086/health || exit 1

# Security: bind to 0.0.0.0 in Docker (network isolation provided by Docker),
# but OPENCLAW_BRIDGE_SECRET should be set when running.
CMD ["python", "mcp_server.py", "--port", "8086", "--host", "0.0.0.0"]
