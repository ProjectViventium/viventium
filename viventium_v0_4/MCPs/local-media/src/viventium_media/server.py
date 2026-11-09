"""Expose the local media modules through the standard MCP stdio transport."""
import argparse
import asyncio
from importlib.resources import files
import json
import os
from pathlib import Path
import signal
import sys
from tempfile import mkdtemp
from typing import Literal

from mcp.server.fastmcp import FastMCP

from . import images, video
from .engine import Artifact, MediaError, Settings, Workspace, bootstrap, render


_ATTACHMENT_HANDOFF = (
    "To attach the result in chat, link the exact path returned by this tool. "
    "Leave the file at that path for Viventium to deliver."
)


def create_server(settings: Settings, workspace: Workspace) -> FastMCP:
    mcp = FastMCP("Viventium Media")
    available = {name: description for name, description in images.MODELS.items() if settings.ready(name)}
    if available:
        image_model = Literal[tuple(available)]
        description = ("Generate a local still image. Returns the finished workspace artifact. "
                       "For edits, pass an optional workspace reference image to a model that supports it. "
                       "Choose the model for the request. ") + _ATTACHMENT_HANDOFF + " " + " ".join(
            f"{name}: {info}" for name, info in available.items()
        )

        @mcp.tool(description=description)
        async def generate_image(
            prompt: str, model: image_model, reference: str | None = None,
            width: int = 384, height: int = 384, seed: int = 2718,
        ) -> Artifact:
            """Reference is an optional workspace image path. Returns the finished workspace artifact."""
            return await render(settings, workspace, model, prompt, width=width, height=height,
                                seed=seed, reference=reference)

    if settings.ready(video.MODEL):
        @mcp.tool(description="Generate a local video and return the finished MP4 workspace artifact. "
                  + video.DESCRIPTION + " Reference is an optional workspace image path. "
                  "56 frames gives about 2.3 seconds; 141 gives about six seconds at 24 fps. "
                  + _ATTACHMENT_HANDOFF)
        async def generate_video(
            prompt: str, model: Literal["minimax-h3"], reference: str | None = None,
            width: int = 384, height: int = 256, frames: int = 56, seed: int = 2718,
        ) -> Artifact:
            """Returns the finished MP4 workspace artifact."""
            return await render(settings, workspace, model, prompt, width=width, height=height,
                                seed=seed, reference=reference, frames=frames)
    return mcp


async def serve(mcp: FastMCP):
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        await mcp.run_stdio_async()
    except asyncio.CancelledError:
        pass
    finally:
        loop.remove_signal_handler(signal.SIGTERM)


def main():
    parser = argparse.ArgumentParser(description="Viventium local media tools")
    parser.add_argument("action", choices=["serve", "connection", "doctor", "example"])
    parser.add_argument("--config", type=Path)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--workspace", type=Path, help="The worker's authorized workspace")
    scope.add_argument("--workspace-parent", type=Path,
                       help="Allow a native worker's working directory within this authorized root")
    parser.add_argument("--worker-temp-output", action="store_true",
                        help="Keep selected outputs in the native worker's private temporary directory")
    args = parser.parse_args()
    if args.action == "example":
        print(files(__package__).joinpath("config.example.toml").read_text(), end="")
        return 0
    if args.config is None:
        parser.error("--config is required")
    try:
        settings = Settings.read(args.config)
        if args.action == "doctor":
            states = {
                name: ("disabled" if name not in settings.models else
                       "ready" if settings.ready(name) else "missing runtime or model files")
                for name in (*images.MODELS, video.MODEL)
            }
            print(json.dumps(states, indent=2))
            return int(any(state == "missing runtime or model files" for state in states.values()))
        if args.workspace is None and args.workspace_parent is None:
            parser.error("serve and connection require --workspace or --workspace-parent")
        if args.worker_temp_output and args.workspace_parent is None:
            parser.error("--worker-temp-output requires --workspace-parent")
        workspace = Workspace.open(args.workspace or args.workspace_parent)
        if args.action == "connection":
            print(json.dumps(bootstrap(settings.file, workspace, sys.executable, settings.timeout,
                                       worker_cwd=args.workspace_parent is not None,
                                       worker_temp_output=args.worker_temp_output), indent=2))
        else:
            if args.workspace_parent is not None:
                cwd = Workspace.open(Path.cwd())
                if not cwd.root.is_relative_to(workspace.root):
                    raise MediaError("The native worker is outside its authorized workspace root.")
                workspace = cwd
            if args.worker_temp_output:
                temporary = os.environ.get("TMPDIR")
                if not temporary or not Path(temporary).is_absolute():
                    raise MediaError("The native worker's temporary directory is unavailable.")
                temporary_root = Workspace.open(Path(temporary)).root
                workspace = Workspace(workspace.root, Path(mkdtemp(prefix="viventium-media-", dir=temporary_root)))
            asyncio.run(serve(create_server(settings, workspace)))
    except (OSError, ValueError, KeyError, MediaError) as error:
        parser.exit(2, f"Local media configuration: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
