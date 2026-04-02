# Power Agents MCP Server (Beta)

> **Status:** Beta  
> **Master Documentation:** [docs/requirements_and_learnings/18_Power_Agents_Beta.md](../../../docs/requirements_and_learnings/18_Power_Agents_Beta.md)

---

## Quick Start

```bash
# 1. Start LibreChat first
cd viventium_v0_4
./viventium-librechat-start.sh --fast

# 2. Start Power Agents Beta
./viventium-power-agents-beta-start.sh start
```

## What This Is

Power Agents provides "unleashed" agentic coding capabilities:
- **Claude Code CLI** - Anthropic's autonomous coding agent
- **Browser automation** - AI-controlled web browsing
- **Per-user Docker containers** - Isolated sandboxes with persistent storage

## File Structure

| File | Purpose |
|------|---------|
| `mcp_server.py` | FastMCP server - manages containers, exposes MCP tools |
| `agent_server.py` | FastAPI server - runs inside each user container |
| `Dockerfile` | User container image (power-sandbox) |
| `Dockerfile.mcp` | MCP server image |
| `docker-compose.yml` | MCP server deployment |

## Key Ports

| Port | Service |
|------|---------|
| 8085 | MCP Server |
| 9100 | User container port 3000 (React, Node) |
| 9101 | User container port 5000 (Flask) |
| 9103 | User container port 8080 (HTTP servers) |
| 9104 | User container port 8888 (Jupyter) |

## Development

```bash
# Rebuild after code changes
docker compose build --no-cache

# Restart
docker compose down && docker compose up -d

# View logs
docker logs viventium-power-agent-mcp
```

## Full Documentation

For comprehensive documentation including:
- Requirements & Specifications
- Architecture diagrams
- All learnings and best practices
- Troubleshooting guide
- Edge cases and limitations

See: **[docs/requirements_and_learnings/18_Power_Agents_Beta.md](../../../docs/requirements_and_learnings/18_Power_Agents_Beta.md)**
