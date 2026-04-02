# 18. Power Agents (Beta) - Unleashed Coding Sandboxes

> **Status:** Beta Feature  
> **Last Updated:** 2026-01-28  
> **Feature Location:** `viventium_v0_4/MCPs/power-agents-beta/`

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Specifications](#specifications)
4. [Use Cases](#use-cases)
5. [Architecture](#architecture)
6. [Integration Points](#integration-points)
7. [Configuration](#configuration)
8. [Learnings & Best Practices](#learnings--best-practices)
9. [Edge Cases & Limitations](#edge-cases--limitations)
10. [Troubleshooting](#troubleshooting)
11. [Development Workflow](#development-workflow)

---

## Overview

Power Agents provides "unleashed" agentic coding capabilities within Viventium by giving users access to **best-in-class** coding agents (Claude Code CLI, OpenAI Codex CLI) running in isolated Docker containers with full Linux environments, network access, and persistent storage.

### Key Insight

**We don't build our own agent - we orchestrate the best-in-class agents that already exist.** Claude Code and Codex have sophisticated context tracking, multi-step reasoning, and tool use built in. We simply provide the infrastructure for them to run in isolated, persistent sandboxes for each user.

### What It Enables

- Users can create, run, and deploy code/servers directly from chat
- Full Linux environment with package installation capabilities
- Browser automation for research and web tasks
- Persistent workspaces that survive container restarts
- Per-user isolation for security and resource management

---

## Requirements

### Core Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R1 | Users get isolated sandboxes (not shared environments) | ✅ Implemented |
| R2 | Workspaces persist across sessions | ✅ Implemented |
| R3 | Full Linux environment with network access | ✅ Implemented |
| R4 | Cost-effective multi-user support on shared VM | ✅ Implemented |
| R5 | Integration via MCP protocol | ✅ Implemented |
| R6 | Support both Anthropic direct API and Azure Foundry | ✅ Implemented |
| R7 | Servers created by agents accessible to users | ✅ Implemented |
| R8 | Auto-cleanup of idle containers | ✅ Implemented |
| R9 | Agents self-test and verify before reporting success | ✅ Implemented via prompt injection |

### User Experience Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| UX1 | Simple natural language requests (not developer commands) | ✅ Implemented |
| UX2 | Clear clickable URLs for created servers | ✅ Implemented |
| UX3 | Visibility into agent progress/steps | ⚠️ Partial (LibreChat UI limitation) |
| UX4 | No user intervention required for complete solutions | ✅ Implemented via prompt injection |
| UX5 | Automated startup with single script | ✅ Implemented |

---

## Specifications

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| MCP Server | FastMCP (Python) | MCP protocol implementation |
| User Containers | Docker | Per-user isolation |
| Agent Server | FastAPI (Python) | REST API inside containers |
| Coding Agent | Claude Code CLI | Autonomous coding |
| Browser Agent | browser-use | Browser automation |
| Container Management | Docker-in-Docker | Dynamic container lifecycle |

### Port Assignments

| Port | Service | Notes |
|------|---------|-------|
| 8085 | MCP Server | External port for LibreChat connection |
| 9100-9104 | User Container Ports | First user's mapped ports |
| 9105-9109 | Next User | Port range increments per user |

### Port Mapping (Container → Host)

When agents create servers inside containers, they run on standard ports. These are mapped to host ports:

| Container Port | Host Port | Common Use |
|---------------|-----------|------------|
| 3000 | 9100 | React dev servers, Node.js |
| 5000 | 9101 | Flask, Python web apps |
| 8000 | 9102 | Agent API (internal) |
| 8080 | 9103 | Generic HTTP servers |
| 8888 | 9104 | Jupyter notebooks |

**Critical:** Users click the HOST port (e.g., `http://localhost:9103`), not the container port.

### File Structure

```
viventium_v0_4/MCPs/power-agents-beta/
├── mcp_server.py         # FastMCP server (manages containers)
├── agent_server.py       # FastAPI server (runs in containers)
├── Dockerfile            # User container image
├── Dockerfile.mcp        # MCP server image
├── docker-compose.yml    # MCP server deployment
├── requirements.txt      # Python dependencies
└── README.md             # Technical documentation

~/.viventium/power-agents-beta/users/
└── {user_id}/
    └── workspace/        # Persistent user workspace
```

---

## Use Cases

### Primary Use Cases

1. **Code Creation**
   - "Create a Python API that returns random jokes"
   - "Build a React todo app with local storage"
   - "Make a web scraper for product prices"

2. **Data Visualization**
   - "Give me a page that visualizes US birth rates month over month"
   - "Create an interactive chart of stock prices"

3. **Server Deployment**
   - "Stand up a server that says hello world"
   - "Create a REST API with CRUD operations"

4. **Research Tasks**
   - "Find the top 5 AI funding news from this week"
   - "Research competitor pricing on their websites"

### Example Interaction Flow

```
User: "Create a server that tells a joke"

System:
1. LibreChat calls power_agent_code via MCP
2. MCP server creates/retrieves user container
3. Claude Code runs in container:
   - Creates server.py with Flask app
   - Installs dependencies
   - Starts server with nohup
   - Tests with curl
4. Returns clickable URL: http://localhost:9103

User clicks link → sees joke
```

---

## Architecture

### System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        LibreChat Frontend                         │
│                    (http://localhost:3081)                        │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                     LibreChat Backend                             │
│                    (http://localhost:3080)                        │
└────────────────────────────┬─────────────────────────────────────┘
                             │ MCP Protocol (JSON-RPC over HTTP)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                  Power Agents MCP Server                          │
│                   (http://localhost:8085)                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  FastMCP Server (mcp_server.py)                            │  │
│  │  - Implements MCP streamable-http protocol                 │  │
│  │  - Manages ContainerManager for per-user containers        │  │
│  │  - Exposes tools: power_agent_code, power_agent_browse,    │  │
│  │    power_agent_shell, power_agent_workspace_*              │  │
│  └────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ Docker API + HTTP
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    User Containers (per-user)                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Power Sandbox Container (viventium/power-sandbox)         │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  agent_server.py (FastAPI on port 8000)              │  │  │
│  │  │  - Orchestrates Claude Code CLI                      │  │  │
│  │  │  - Injects POWER_AGENT_PROMPT                        │  │  │
│  │  │  - Streams output via SSE                            │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Installed Tools:                                    │  │  │
│  │  │  - Claude Code CLI (@anthropic-ai/claude-code)       │  │  │
│  │  │  - Codex CLI (@openai/codex) [disabled without key]  │  │  │
│  │  │  - browser-use (Python)                              │  │  │
│  │  │  - Full Linux (Debian), git, Node.js, Python         │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  Persistent Volume: /home/agent/workspace             │  │  │
│  │  │  Mapped to: ~/.viventium/power-agents-beta/users/{id}/       │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Container Lifecycle

```
1. User sends request to LibreChat
2. LibreChat calls MCP tool (power_agent_code)
3. MCP server checks if user has running container
   - If yes: reuse existing container
   - If no: create new container with port mappings
4. MCP server calls agent_server.py in container
5. agent_server.py invokes Claude Code CLI with task + POWER_AGENT_PROMPT
6. Claude Code executes autonomously (creates files, runs commands, etc.)
7. Output streamed back via SSE
8. Container stays running (restart_policy: unless-stopped)
9. User can access created servers via mapped ports
10. Idle containers cleaned up after 2 hours (configurable)
```

---

## Integration Points

### LibreChat Integration

**File:** `viventium_v0_4/LibreChat/librechat.yaml`

```yaml
mcpServers:
  power-agents:
    type: streamable-http
    url: "http://localhost:8085/mcp"
    headers:
      X-User-Id: "{{LIBRECHAT_USER_ID}}"
    startup: false
    chatMenu: true
    timeout: 600000  # 10 minutes for long-running agent tasks
    serverInstructions: |
      POWER AGENTS - Build and run code in a full Linux sandbox!
      
      USE power_agent_code FOR ANY CODING/SERVER TASK.
      
      The tool will:
      1. Create the code
      2. Start any servers automatically
      3. Test it works
      4. Return a CLICKABLE URL for the user
      
      YOUR JOB: Just describe what you want. The tool handles execution.
      
      IMPORTANT - After the tool completes, tell the user the URL:
      - Port 8080 servers → http://localhost:9103
      - Port 3000 servers → http://localhost:9100
```

### Startup Scripts

**LibreChat:** `./viventium-librechat-start.sh --fast`

**Power Agents:** `./viventium-power-agents-beta-start.sh start`

Scripts must be run in this order - LibreChat first, then Power Agents.

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Direct Anthropic API key | - |
| `CLAUDE_CODE_USE_FOUNDRY` | Enable Azure Foundry mode | - |
| `ANTHROPIC_FOUNDRY_API_KEY` | Azure Foundry API key | - |
| `ANTHROPIC_FOUNDRY_RESOURCE` | Azure resource name | - |
| `ANTHROPIC_MODEL` | Model to use | claude-opus-4-5 |
| `OPENAI_API_KEY` | OpenAI key for Codex | - |
| `POWER_AGENT_DATA_DIR` | User workspace base dir | ~/.viventium/power-agents-beta/users |
| `POWER_AGENT_PORT_START` | Starting port for containers | 9100 |
| `POWER_AGENT_MEMORY` | Container memory limit | 4g |
| `POWER_AGENT_CPUS` | Container CPU limit | 2 |
| `POWER_AGENT_IDLE_HOURS` | Hours before idle cleanup | 2 |

### Azure AI Foundry Configuration

For enterprise deployments using Azure AI Foundry:

```bash
export CLAUDE_CODE_USE_FOUNDRY=1
export ANTHROPIC_FOUNDRY_API_KEY="your-foundry-key"
export ANTHROPIC_FOUNDRY_RESOURCE="your-resource-name"
export ANTHROPIC_MODEL="claude-opus-4-5"
```

---

## Learnings & Best Practices

### DO's ✅

| # | Learning | Explanation |
|---|----------|-------------|
| 1 | **Use FastMCP for MCP servers** | Plain FastAPI doesn't implement the MCP JSON-RPC protocol. LibreChat expects proper MCP responses. |
| 2 | **Use absolute paths for Docker volumes** | Relative paths fail with Docker-in-Docker. Use `~/.viventium/...` or full paths. |
| 3 | **Use `docker compose build --no-cache`** | Docker caches aggressively. Always use `--no-cache` when code changes. |
| 4 | **Add custom health endpoints** | FastMCP doesn't provide `/health` by default. Add with `@mcp.custom_route("/health")`. |
| 5 | **Use `localhost` in librechat.yaml** | Don't use `${VAR:-default}` syntax - LibreChat doesn't resolve environment variables in YAML. |
| 6 | **Start port ranges at 9100+** | Port 9000 is commonly used by PHP-FPM and other services. Avoid conflicts. |
| 7 | **Initialize workspace as git repo** | Both Claude Code and Codex work better with git context for tracking changes. |
| 8 | **Use `--skip-git-repo-check` for Codex** | Required when workspace isn't a pre-existing trusted git repo. |
| 9 | **Add restart policy to containers** | Use `restart_policy={"Name": "unless-stopped"}` so servers persist after agent tasks complete. |
| 10 | **Inject prompts for autonomous operation** | Use POWER_AGENT_PROMPT to ensure agents self-test, loop until success, and provide clear URLs. |
| 11 | **Map multiple dev ports** | Map common ports (3000, 5000, 8080, 8888) to allow various frameworks. |
| 12 | **Use SSE for streaming** | Server-Sent Events provide real-time visibility into agent execution. |
| 13 | **Default to Claude Code** | Always use Claude Code unless user explicitly has OpenAI key configured. |
| 14 | **Keep `agent` parameter for backwards compatibility** | Even if ignored, prevents validation errors when LLM sends it. |

### DON'Ts ❌

| # | Anti-Pattern | Why It's Bad |
|---|--------------|--------------|
| 1 | **Don't use plain FastAPI for MCP** | LibreChat expects MCP JSON-RPC protocol, not REST. You'll get 404 errors. |
| 2 | **Don't use `${VAR:-default}` in librechat.yaml** | LibreChat doesn't resolve these - you'll get "Invalid URL" errors. |
| 3 | **Don't forget `--no-cache` when rebuilding** | Old code persists in Docker layer cache, causing confusing bugs. |
| 4 | **Don't use `host.docker.internal` in librechat.yaml** | For local dev, use `localhost`. Only containers need `host.docker.internal`. |
| 5 | **Don't skip health endpoints** | Container orchestration and health checks depend on them. |
| 6 | **Don't put CLI flags before subcommands** | Codex requires: `codex --full-auto exec --skip-git-repo-check <task>` (flag order matters). |
| 7 | **Don't rely on LibreChat for live streaming display** | LibreChat shows "Running" then full result - no incremental updates during execution. |
| 8 | **Don't expect container to stay running without restart policy** | Containers exit after tasks by default - add restart policy. |
| 9 | **Don't create agents that ask questions** | Users want RESULTS, not clarifications. Prompt agents to "just do it". |
| 10 | **Don't report success without self-testing** | Agents must curl/test their own servers before claiming success. |

### Common Gotchas

| Issue | Cause | Solution |
|-------|-------|----------|
| 404 on `/mcp` endpoint | Using FastAPI instead of FastMCP | Rewrite with FastMCP |
| Old code in container | Docker build cache | `docker compose build --no-cache` |
| "Invalid URL" in LibreChat | `${VAR}` syntax in yaml | Use static URLs |
| "Mounts denied" | Docker Desktop file sharing | Use paths in `~/` |
| User containers unreachable | Wrong network address | Use `host.docker.internal` inside containers |
| "Not inside a trusted directory" | Codex requires git repo | Add `--skip-git-repo-check` flag |
| Codex flag error | Flag before subcommand | Put `--skip-git-repo-check` after `exec` |
| 401 Unauthorized for Codex | Invalid/missing OpenAI key | Disable Codex, default to Claude |
| Server not accessible after task | Container exited | Add `restart_policy: unless-stopped` |
| User clicks wrong port | Confusion between container/host ports | Clear messaging in output about mapped ports |
| Agent modifies file but server shows old content | Server not restarted | Prompt agent to always restart servers |

---

## Edge Cases & Limitations

### Known Limitations

1. **LibreChat UI Streaming**
   - LibreChat shows "Running..." during tool execution
   - Full output only visible after tool completes
   - Cannot show true real-time streaming in the UI

2. **Codex Support**
   - Codex CLI requires OpenAI API key
   - Currently disabled by default (hardcoded to Claude)
   - Re-enable by modifying agent_server.py if OpenAI key available

3. **Container Persistence**
   - Containers restart if they exit (restart policy)
   - But running processes inside (servers) don't auto-restart
   - Agent must start servers with `nohup ... &`

4. **Port Conflicts**
   - If user creates servers on non-mapped ports, they won't be accessible
   - Only ports 3000, 5000, 8000, 8080, 8888 are mapped

5. **Browser Automation**
   - Requires Chromium/Playwright in container
   - May have stability issues with complex sites
   - Headless only (no visual debugging)

### Security Considerations

1. **Container Isolation**
   - Each user gets separate container
   - Containers have limited resources (4GB RAM, 2 CPUs by default)
   - No access to host filesystem outside workspace

2. **Network Access**
   - Containers have full outbound internet access
   - Required for package installation and web tasks
   - Consider network policies for production

3. **API Key Handling**
   - Keys passed via environment variables
   - Not persisted to disk
   - Not exposed in logs

---

## Troubleshooting

### Quick Diagnostics

```bash
# Check if MCP server is running
curl http://localhost:8085/health

# Check container status
docker ps --filter "label=viventium.service=power-agent"

# View MCP server logs
docker logs viventium-power-agent-mcp

# View user container logs
docker logs <container-name>

# Test port accessibility
curl http://localhost:9103
```

### Common Issues

#### MCP Server Won't Start

```bash
# Check Docker is running
docker ps

# Check for port conflicts
lsof -i :8085

# Force rebuild
cd viventium_v0_4/MCPs/power-agents-beta
docker compose build --no-cache
docker compose up -d
```

#### "Disconnected" in LibreChat

1. Verify MCP server health: `curl http://localhost:8085/health`
2. Check librechat.yaml has correct URL: `http://localhost:8085/mcp`
3. Restart LibreChat backend
4. Re-initialize the integration in chat

#### Container Not Creating

```bash
# Check Docker disk space
docker system df

# Clean up if needed
docker system prune -af

# Check image exists
docker images | grep power-sandbox
```

#### Server Not Accessible After Task

1. Check container still running: `docker ps`
2. Check if server process is running: `docker exec <container> ps aux`
3. Test from inside container: `docker exec <container> curl localhost:8080`
4. Verify port mapping: `docker port <container>`

---

## Development Workflow

### Making Changes

1. **Edit Code**
   - MCP server: `mcp_server.py`
   - Container code: `agent_server.py`

2. **Rebuild Images**
   ```bash
   cd viventium_v0_4/MCPs/power-agents-beta
   docker compose build --no-cache
   ```

3. **Restart Services**
   ```bash
   ./viventium-power-agents-beta-start.sh restart
   ```

4. **Test**
   - Direct test: `curl -X POST http://localhost:8085/mcp ...`
   - Through LibreChat: Use chat interface

### Testing Checklist

- [ ] MCP server health endpoint responds
- [ ] Container creates on first request
- [ ] Container reused on subsequent requests
- [ ] Claude Code executes successfully
- [ ] Output includes clear URL for user
- [ ] Server accessible on mapped port
- [ ] Container persists after task (restart policy)
- [ ] Workspace files persist across restarts

---

## Managed Cloud Deployment Notes

### Deployment Status: Paused Historical Reference (2026-01-29)

| Component | Resource Type | Status |
|-----------|----------|--------|
| MCP service | Container app | Deleted (cost control) |
| Power Agents host | Virtual machine | Deleted (cost control) |
| Workspace storage | File share | Deleted (cost control) |
| LibreChat Config | Updated with power-agents MCP | Applied |

### Architecture Overview

For managed cloud deployment, Power Agents used a hybrid architecture:

1. **MCP Server** - stateless cloud service
2. **Power Agent Host** - VM with Docker for container management
3. **Persistent File Share** - workspace storage
4. **Managed model endpoint** - model access

### Deployment Files

| File | Purpose |
|------|---------|
| `config.cloud.example.yaml` | Feature flags, VM config, storage |
| `mcp_server_azure.py` | Azure-specific MCP server |
| `vm_agent_manager.py` | VM container manager API |
| `docker-compose.azure.yml` | VM service orchestration |
| `power-agents-vm-setup.sh` | VM initialization script |
| `librechat-cloud.yaml` | Example MCP configuration for a cloud deployment |

### Deployment Steps

Deployment commands and environment-specific runbooks were moved to the private deployment repo.
The public doc keeps only the architectural pattern and product requirements.

### Configuration (config.cloud.example.yaml)

```yaml
features:
  deploy_power_agents: true
  power_agents_deploy_mode: hybrid

power_agents:
  vm_size: Standard_D4s_v5
  container_port_start: 9100
  container_port_end: 9199
  container_memory: 4g
  container_cpus: 2
  idle_timeout_minutes: 20
  max_lifetime_minutes: 20
  file_share_name: power-agents-workspaces
```

### User URLs In Cloud Deployments

In a VM-backed cloud deployment, user-created servers are typically accessible at:
```
http://{vm-public-ip}:{user-port}
```

For example:
- Port 8080 server → `http://20.x.x.x:9103`
- Port 3000 server → `http://20.x.x.x:9100`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-01-28 | Initial implementation |
| 0.1.1 | 2026-01-28 | Fixed FastMCP protocol implementation |
| 0.1.2 | 2026-01-28 | Added port mapping for user-accessible servers |
| 0.1.3 | 2026-01-28 | Added restart policy for container persistence |
| 0.1.4 | 2026-01-28 | Added prompt injection for autonomous operation |
| 0.2.0 | 2026-01-28 | Renamed to Beta, added managed cloud deployment notes |

---

## Related Documents

- Historical setup and implementation notes were moved to the private research archive on
  `2026-03-31`.
- [Prompt Design](../prompt_design/power_agent.md) - Agent operating instructions
- [MCP Integration](./07_MCPs.md) - General MCP documentation

---

## CLI Reference

### Claude Code CLI

```bash
# Full autonomous mode
claude --dangerously-skip-permissions --print --output-format text -p "task"
```

### Codex CLI (if enabled)

```bash
# Full autonomous mode with git bypass
codex --full-auto exec --skip-git-repo-check "task"
```

### Environment for Azure Foundry

```bash
# Required for Azure AI Foundry
export CLAUDE_CODE_USE_FOUNDRY=1
export ANTHROPIC_FOUNDRY_API_KEY="..."
export ANTHROPIC_FOUNDRY_RESOURCE="..."
export ANTHROPIC_MODEL="claude-opus-4-5"
```
