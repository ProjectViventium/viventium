# VIVENTIUM START
# Purpose: Agent server running inside each user's power sandbox container.
# This exposes Claude Code, Codex, and browser-use via a simple REST API.
#
# Key insight: We don't build our own agent - we just orchestrate the BEST-IN-CLASS
# agents (Claude Code, Codex) that already exist.
# VIVENTIUM END

import asyncio
import os
import subprocess
import json
import shutil
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(
    title="Viventium Power Agent",
    description="Unleashed Claude Code + Codex + Browser-Use in a sandbox"
)

# ============== CONFIGURATION ==============

WORKSPACE_DIR = Path("/home/agent/workspace")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# ============== POWER AGENT PROMPT INJECTION ==============
# This prompt is automatically appended to every task to ensure
# the agent delivers complete, tested, working solutions.

POWER_AGENT_PROMPT = """

---
CRITICAL OPERATING INSTRUCTIONS (FOLLOW STRICTLY):

1. PATH OF LEAST RESISTANCE: Use the simplest, most direct solution. Don't reinvent wheels.

2. JUST DO IT: Execute immediately without asking questions. Users want RESULTS.

3. SELF-TEST AND VERIFY: 
   - After creating code, RUN IT
   - After starting a server, CURL IT to confirm it responds
   - NEVER report success without verification

4. LOOP UNTIL SUCCESS:
   - If something fails, FIX IT and try again
   - Keep iterating until ACTUALLY COMPLETE

5. NO USER INTERVENTION: Deliver a COMPLETE, WORKING solution.

6. FOR SERVERS - CRITICAL PORT MAPPING:
   Your container ports are mapped to host ports that the USER can access:
   
   - If you run a server on port 3000 → User accesses: http://localhost:9100
   - If you run a server on port 5000 → User accesses: http://localhost:9101  
   - If you run a server on port 8080 → User accesses: http://localhost:9103
   - If you run a server on port 8888 → User accesses: http://localhost:9104
   
   ALWAYS:
   - Start the server in background: nohup python3 server.py > /dev/null 2>&1 &
   - Test with curl: curl http://localhost:8080  (or whatever port)
   - Tell user the MAPPED URL they can click, e.g.: "Click here: http://localhost:9103"

REMEMBER: The user clicks the MAPPED port (9100-9104), not the container port (3000/5000/8080/8888).
Validate EVERYTHING before reporting success. Give user ONE clear clickable URL.
---
"""


# ============== REQUEST/RESPONSE MODELS ==============

class AgentTaskRequest(BaseModel):
    """Request to run an agent task."""
    task: str
    agent: str = "claude"  # "claude" or "codex"
    working_dir: Optional[str] = None
    timeout: int = 300  # 5 minutes default
    auto_approve: bool = True  # Skip confirmation prompts


class BrowseTaskRequest(BaseModel):
    """Request to run a browser automation task."""
    task: str
    start_url: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"
    timeout: int = 120


class TaskResponse(BaseModel):
    """Response from a task execution."""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    duration_seconds: float = 0


class WorkspaceFile(BaseModel):
    """A file in the workspace."""
    name: str
    path: str
    is_dir: bool
    size: int
    modified: str


# ============== STREAMING AGENT EXECUTION ==============

async def stream_claude_code(task: str, working_dir: Path, timeout: int, auto_approve: bool):
    """
    Stream Claude Code CLI output line by line.
    Yields JSON events for real-time visibility.
    """
    start_time = datetime.now()
    
    # Ensure workspace is a git repo
    git_dir = working_dir / ".git"
    if not git_dir.exists():
        init_result = subprocess.run(
            ["git", "init"],
            cwd=str(working_dir),
            capture_output=True,
            text=True
        )
        if init_result.returncode == 0:
            subprocess.run(["git", "config", "user.email", "agent@viventium.local"], cwd=str(working_dir))
            subprocess.run(["git", "config", "user.name", "Viventium Agent"], cwd=str(working_dir))
    
    # Inject power agent prompt into task
    enhanced_task = task + POWER_AGENT_PROMPT
    
    # Build command
    cmd = ["claude"]
    if auto_approve:
        cmd.append("--dangerously-skip-permissions")
    # Use text output (most reliable)
    cmd.extend(["--print", "--output-format", "text", "-p", enhanced_task])
    
    # Build environment
    env = {**os.environ}
    if os.environ.get("CLAUDE_CODE_USE_FOUNDRY") == "1":
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_BASE_URL", None)
        env["CLAUDE_CODE_USE_FOUNDRY"] = "1"
    else:
        env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
    
    yield {"event": "start", "agent": "claude", "task": task, "cwd": str(working_dir)}
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        # Stream stdout line by line
        async def read_stream(stream, stream_type):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    yield {"event": "output", "stream": stream_type, "text": text}
        
        # Read both streams concurrently
        async for event in read_stream(process.stdout, "stdout"):
            yield event
        
        async for event in read_stream(process.stderr, "stderr"):
            yield event
        
        await asyncio.wait_for(process.wait(), timeout=timeout)
        
        duration = (datetime.now() - start_time).total_seconds()
        yield {
            "event": "complete",
            "success": process.returncode == 0,
            "exit_code": process.returncode,
            "duration_seconds": duration
        }
        
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        yield {"event": "error", "error": f"Timeout after {timeout}s"}
    except Exception as e:
        yield {"event": "error", "error": str(e)}


async def stream_codex(task: str, working_dir: Path, timeout: int, auto_approve: bool):
    """
    Stream Codex CLI output line by line.
    """
    start_time = datetime.now()
    
    # Ensure workspace is a git repo
    git_dir = working_dir / ".git"
    if not git_dir.exists():
        init_result = subprocess.run(
            ["git", "init"],
            cwd=str(working_dir),
            capture_output=True,
            text=True
        )
        if init_result.returncode == 0:
            subprocess.run(["git", "config", "user.email", "agent@viventium.local"], cwd=str(working_dir))
            subprocess.run(["git", "config", "user.name", "Viventium Agent"], cwd=str(working_dir))
    
    # Inject power agent prompt into task
    enhanced_task = task + POWER_AGENT_PROMPT
    
    # Build command
    cmd = ["codex"]
    if auto_approve:
        cmd.append("--full-auto")
    cmd.append("exec")
    cmd.append("--skip-git-repo-check")
    cmd.append(enhanced_task)
    
    yield {"event": "start", "agent": "codex", "task": task, "cwd": str(working_dir)}
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **os.environ,
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
                "CODEX_UNSAFE_ALLOW_NO_SANDBOX": "1",
            }
        )
        
        # Stream stdout line by line
        async def read_stream(stream, stream_type):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    yield {"event": "output", "stream": stream_type, "text": text}
        
        async for event in read_stream(process.stdout, "stdout"):
            yield event
        
        async for event in read_stream(process.stderr, "stderr"):
            yield event
        
        await asyncio.wait_for(process.wait(), timeout=timeout)
        
        duration = (datetime.now() - start_time).total_seconds()
        yield {
            "event": "complete",
            "success": process.returncode == 0,
            "exit_code": process.returncode,
            "duration_seconds": duration
        }
        
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        yield {"event": "error", "error": f"Timeout after {timeout}s"}
    except Exception as e:
        yield {"event": "error", "error": str(e)}


# ============== AGENT EXECUTION (NON-STREAMING) ==============

async def run_claude_code(task: str, working_dir: Path, timeout: int, auto_approve: bool) -> TaskResponse:
    """
    Run Claude Code CLI on a task.
    
    Claude Code is Anthropic's official agentic coding assistant.
    It handles context tracking, file operations, and multi-step reasoning.
    """
    start_time = datetime.now()
    
    # Ensure workspace is a git repo (helps with context tracking)
    git_dir = working_dir / ".git"
    if not git_dir.exists():
        init_result = subprocess.run(
            ["git", "init"],
            cwd=str(working_dir),
            capture_output=True,
            text=True
        )
        if init_result.returncode == 0:
            subprocess.run(["git", "config", "user.email", "agent@viventium.local"], cwd=str(working_dir))
            subprocess.run(["git", "config", "user.name", "Viventium Agent"], cwd=str(working_dir))
    
    # Inject power agent prompt into task
    enhanced_task = task + POWER_AGENT_PROMPT
    
    # Build command
    cmd = ["claude"]
    
    # Add flags for non-interactive, fully autonomous operation
    if auto_approve:
        cmd.append("--dangerously-skip-permissions")
    
    # Add the task as a prompt with text output
    cmd.extend(["--print", "--output-format", "text", "-p", enhanced_task])
    
    try:
        # Build environment - support both direct Anthropic and Azure Foundry
        env = {**os.environ}
        
        # Azure Foundry support (for Azure AI Foundry deployments of Claude)
        if os.environ.get("CLAUDE_CODE_USE_FOUNDRY") == "1":
            # Remove regular Anthropic vars to ensure Foundry is used
            env.pop("ANTHROPIC_API_KEY", None)
            env.pop("ANTHROPIC_BASE_URL", None)
            # Keep Foundry vars
            env["CLAUDE_CODE_USE_FOUNDRY"] = "1"
        else:
            # Regular Anthropic API
            env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return TaskResponse(
                success=False,
                output="",
                error=f"Task timed out after {timeout} seconds",
                exit_code=-1,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
        
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        
        return TaskResponse(
            success=process.returncode == 0,
            output=output,
            error=error if error else None,
            exit_code=process.returncode or 0,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
        
    except FileNotFoundError:
        return TaskResponse(
            success=False,
            output="",
            error="Claude Code CLI not found. Is it installed?",
            exit_code=-1,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    except Exception as e:
        return TaskResponse(
            success=False,
            output="",
            error=str(e),
            exit_code=-1,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )


async def run_codex(task: str, working_dir: Path, timeout: int, auto_approve: bool) -> TaskResponse:
    """
    Run OpenAI Codex CLI on a task.
    
    Codex is OpenAI's official agentic coding assistant.
    It provides similar capabilities to Claude Code but uses GPT models.
    """
    start_time = datetime.now()
    
    # Ensure workspace is a git repo (Codex requires this or --skip-git-repo-check)
    git_dir = working_dir / ".git"
    if not git_dir.exists():
        # Initialize git repo for Codex
        init_result = subprocess.run(
            ["git", "init"],
            cwd=str(working_dir),
            capture_output=True,
            text=True
        )
        if init_result.returncode == 0:
            # Configure git user for commits
            subprocess.run(["git", "config", "user.email", "agent@viventium.local"], cwd=str(working_dir))
            subprocess.run(["git", "config", "user.name", "Viventium Agent"], cwd=str(working_dir))
    
    # Inject power agent prompt into task
    enhanced_task = task + POWER_AGENT_PROMPT
    
    # Build command - note: flags come after subcommand for codex
    cmd = ["codex"]
    
    # Add flags for autonomous operation (before exec)
    if auto_approve:
        cmd.append("--full-auto")
    
    # Add exec subcommand, then the flag, then the task
    cmd.append("exec")
    cmd.append("--skip-git-repo-check")
    cmd.append(enhanced_task)
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **os.environ,
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
                "CODEX_UNSAFE_ALLOW_NO_SANDBOX": "1",
            }
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return TaskResponse(
                success=False,
                output="",
                error=f"Task timed out after {timeout} seconds",
                exit_code=-1,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
        
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        
        return TaskResponse(
            success=process.returncode == 0,
            output=output,
            error=error if error else None,
            exit_code=process.returncode or 0,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
        
    except FileNotFoundError:
        return TaskResponse(
            success=False,
            output="",
            error="Codex CLI not found. Is it installed?",
            exit_code=-1,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    except Exception as e:
        return TaskResponse(
            success=False,
            output="",
            error=str(e),
            exit_code=-1,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )


# ============== BROWSER AUTOMATION ==============

async def run_browser_task(task: str, start_url: Optional[str], model: str, timeout: int) -> TaskResponse:
    """
    Run a browser automation task using browser-use.
    """
    start_time = datetime.now()
    
    try:
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI
        
        # Initialize browser (headless in container)
        browser = Browser(config=BrowserConfig(headless=True))
        
        # Initialize LLM based on model name
        if "claude" in model.lower() or "anthropic" in model.lower():
            llm = ChatAnthropic(model=model)
        else:
            llm = ChatOpenAI(model=model)
        
        # Create and run agent
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
        )
        
        # Run with timeout
        try:
            result = await asyncio.wait_for(
                agent.run(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            await browser.close()
            return TaskResponse(
                success=False,
                output="",
                error=f"Browser task timed out after {timeout} seconds",
                exit_code=-1,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
        
        await browser.close()
        
        # Format result
        if hasattr(result, 'final_result'):
            output = str(result.final_result)
        else:
            output = str(result)
        
        return TaskResponse(
            success=True,
            output=output,
            error=None,
            exit_code=0,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
        
    except ImportError as e:
        return TaskResponse(
            success=False,
            output="",
            error=f"browser-use not available: {e}",
            exit_code=-1,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    except Exception as e:
        return TaskResponse(
            success=False,
            output="",
            error=str(e),
            exit_code=-1,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )


# ============== API ENDPOINTS ==============

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "workspace": str(WORKSPACE_DIR),
        "agents": {
            "claude": shutil.which("claude") is not None,
            "codex": shutil.which("codex") is not None,
        }
    }


@app.post("/agent", response_model=TaskResponse)
async def run_agent_task(request: AgentTaskRequest):
    """
    Run a coding task using Claude Code.
    
    This is the main endpoint for unleashed coding power.
    The agent will autonomously:
    - Create, edit, and delete files
    - Run commands and scripts
    - Install packages
    - Debug and fix issues
    - All in the persistent workspace
    
    NOTE: Codex is disabled (no OpenAI API key configured).
    All requests use Claude Code regardless of agent parameter.
    """
    # Determine working directory
    if request.working_dir:
        working_dir = WORKSPACE_DIR / request.working_dir
        working_dir.mkdir(parents=True, exist_ok=True)
    else:
        working_dir = WORKSPACE_DIR
    
    # ALWAYS use Claude Code - Codex is disabled (no API key)
    # Ignore request.agent parameter
    return await run_claude_code(
        request.task,
        working_dir,
        request.timeout,
        request.auto_approve
    )


@app.post("/agent/stream")
async def stream_agent_task(request: AgentTaskRequest):
    """
    Stream a coding task with real-time output visibility.
    
    Returns Server-Sent Events (SSE) with:
    - start: Task started
    - output: Line of output (stdout/stderr)
    - complete: Task finished
    - error: Error occurred
    
    NOTE: Always uses Claude Code (Codex disabled - no API key).
    """
    # Determine working directory
    if request.working_dir:
        working_dir = WORKSPACE_DIR / request.working_dir
        working_dir.mkdir(parents=True, exist_ok=True)
    else:
        working_dir = WORKSPACE_DIR
    
    async def event_generator():
        # ALWAYS use Claude Code - Codex disabled
        stream = stream_claude_code(
            request.task,
            working_dir,
            request.timeout,
            request.auto_approve
        )
        
        async for event in stream:
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/browse", response_model=TaskResponse)
async def run_browse_task(request: BrowseTaskRequest):
    """
    Run a browser automation task using browser-use.
    
    Examples:
    - "Find the top 5 AI funding news from this week"
    - "Go to booking.com and find hotels in Paris under $200"
    - "Research competitor pricing on their websites"
    """
    return await run_browser_task(
        request.task,
        request.start_url,
        request.model,
        request.timeout
    )


@app.get("/workspace", response_model=List[WorkspaceFile])
async def list_workspace(path: str = ""):
    """List files in the workspace."""
    target = WORKSPACE_DIR / path
    
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    files = []
    for item in target.iterdir():
        stat = item.stat()
        files.append(WorkspaceFile(
            name=item.name,
            path=str(item.relative_to(WORKSPACE_DIR)),
            is_dir=item.is_dir(),
            size=stat.st_size if item.is_file() else 0,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
        ))
    
    return sorted(files, key=lambda x: (not x.is_dir, x.name.lower()))


@app.get("/workspace/read")
async def read_file(path: str):
    """Read a file from the workspace."""
    target = WORKSPACE_DIR / path
    
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    try:
        content = target.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shell")
async def run_shell_command(command: str, working_dir: str = ""):
    """
    Run a shell command in the workspace.
    
    Use with caution - this gives full shell access.
    """
    target_dir = WORKSPACE_DIR / working_dir if working_dir else WORKSPACE_DIR
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(target_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=60  # 1 minute timeout for shell commands
        )
        
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "exit_code": process.returncode
        }
        
    except asyncio.TimeoutError:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out after 60 seconds",
            "exit_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1
        }


# ============== RUN ==============

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
