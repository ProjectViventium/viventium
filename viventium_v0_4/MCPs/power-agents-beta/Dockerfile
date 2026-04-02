# VIVENTIUM START
# Purpose: Power Sandbox container with Claude Code + Codex CLI for unleashed agentic coding.
# This gives users BEST-IN-CLASS coding agents (not a framework that tries to replicate them).
# Features:
# - Claude Code CLI (Anthropic's official agent)
# - Codex CLI (OpenAI's official agent)
# - browser-use for browser automation
# - Full Linux environment with common dev tools
# - Persistent /home/agent workspace
# - Network access enabled
# VIVENTIUM END

FROM node:22-bookworm

ARG TZ=UTC
ENV TZ="$TZ"
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    ca-certificates \
    curl \
    wget \
    git \
    unzip \
    jq \
    less \
    procps \
    # Development tools
    build-essential \
    ripgrep \
    fzf \
    gh \
    # Python for browser-use
    python3 \
    python3-pip \
    python3-venv \
    # Browser dependencies for browser-use
    chromium \
    chromium-driver \
    # Network tools (useful for debugging)
    dnsutils \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Create agent user (non-root for security)
# Node image already has 'node' user with UID 1000, so use a different UID
RUN useradd -m -s /bin/bash -u 1001 agent \
    && mkdir -p /home/agent/workspace \
    && chown -R agent:agent /home/agent

# Set up npm global directory for agent user
RUN mkdir -p /home/agent/.npm-global \
    && chown -R agent:agent /home/agent/.npm-global

# Switch to agent user for installations
USER agent
WORKDIR /home/agent

# Configure npm to use user-local directory
ENV NPM_CONFIG_PREFIX=/home/agent/.npm-global
ENV PATH=/home/agent/.npm-global/bin:$PATH

# Install Claude Code CLI
# Note: Uses @anthropic-ai/claude-code package
RUN npm install -g @anthropic-ai/claude-code

# Install Codex CLI
# Note: Uses @openai/codex package
RUN npm install -g @openai/codex

# Set up Python virtual environment for browser-use
RUN python3 -m venv /home/agent/.venv
ENV PATH=/home/agent/.venv/bin:$PATH

# Install browser-use and dependencies
RUN pip install --no-cache-dir \
    browser-use \
    playwright \
    langchain \
    langchain-anthropic \
    langchain-openai \
    fastapi \
    uvicorn \
    httpx

# Install Playwright browsers (use system chromium)
ENV PLAYWRIGHT_BROWSERS_PATH=/home/agent/.playwright
RUN playwright install chromium

# Copy the agent server
COPY --chown=agent:agent agent_server.py /home/agent/agent_server.py

# Environment variables for sandbox operation
# These allow the CLIs to run without additional sandboxing (we're already in a container)
ENV CODEX_UNSAFE_ALLOW_NO_SANDBOX=1
ENV CLAUDE_CODE_SKIP_PERMISSIONS=1

# Expose API port and common dev ports
# These ports will be mapped to host ports so users can access servers created by agents
EXPOSE 3000 5000 8000 8080 8888

# Working directory for user projects
WORKDIR /home/agent/workspace

# Default command: run the agent server
CMD ["python3", "/home/agent/agent_server.py"]
