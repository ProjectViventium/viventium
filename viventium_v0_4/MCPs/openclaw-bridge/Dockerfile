# VIVENTIUM START
# Dockerfile for the OpenClaw Bridge MCP server.
# Runs the FastMCP server that manages per-user OpenClaw Gateway instances.
#
# Includes Node.js + OpenClaw for "direct" child process mode.
# Pin versions for reproducibility.
# VIVENTIUM END

FROM python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

WORKDIR /app

# VIVENTIUM START: install exact Node and the independently reviewed OpenClaw lock.
# The nested `openclaw` repo retains corresponding source and provenance; this lock is the
# executable npm payload. Mutable NodeSource repositories and global npm installs are forbidden.
ARG TARGETARCH
ARG NODE_VERSION=22.23.1
ARG NODE_X64_SHA256=9749e988f437343b7fa832c69ded82a312e41a03116d766797ac14f6f9eee578
ARG NODE_ARM64_SHA256=0294e8b915ab75f92c7513d2fcb830ae06e10684e6c603e99a87dbf8835389c1

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl git lsof xz-utils; \
    case "$TARGETARCH" in \
      amd64) node_arch=x64; node_sha="$NODE_X64_SHA256" ;; \
      arm64) node_arch=arm64; node_sha="$NODE_ARM64_SHA256" ;; \
      *) echo "Unsupported OpenClaw image architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    node_archive="node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    curl --fail --silent --show-error --location --output "/tmp/${node_archive}" \
      "https://nodejs.org/dist/v${NODE_VERSION}/${node_archive}"; \
    echo "${node_sha}  /tmp/${node_archive}" | sha256sum --check --strict; \
    tar --extract --xz --file "/tmp/${node_archive}" --directory /usr/local --strip-components=1; \
    rm -f "/tmp/${node_archive}"; \
    node --version | grep --fixed-strings "v${NODE_VERSION}"; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

COPY openclaw-runtime-lock/package.json openclaw-runtime-lock/package-lock.json /opt/openclaw-runtime/
RUN npm ci --omit=dev --prefix /opt/openclaw-runtime && \
    /opt/openclaw-runtime/node_modules/.bin/openclaw --version | grep --fixed-strings "2026.7.1-2" && \
    ln -s /opt/openclaw-runtime/node_modules/.bin/openclaw /usr/local/bin/openclaw && \
    npm cache clean --force
ENV OPENCLAW_DISABLE_BONJOUR=1
ENV FASTMCP_CHECK_FOR_UPDATES=off
# VIVENTIUM END

# Install Python dependencies
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Copy application code
COPY mcp_server.py openclaw_manager.py e2b_runtime.py vm_registry.py vm_control.py ./
# VIVENTIUM START: Bundle channel bridge plugin for in-container OpenClaw loading.
# Keep folder name aligned with plugin id to avoid OpenClaw id-hint mismatch warnings.
COPY viventium-channel-plugin ./viventium-channel-bridge
# VIVENTIUM END

# Default port for MCP server
EXPOSE 8086

# Health check for the MCP bridge (NOT OpenClaw gateway)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8086/health || exit 1

# Security: Docker binds internally on 0.0.0.0, so startup requires OPENCLAW_BRIDGE_SECRET.
CMD ["python", "mcp_server.py", "--port", "8086", "--host", "0.0.0.0"]
