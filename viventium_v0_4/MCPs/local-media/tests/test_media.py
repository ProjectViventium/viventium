import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from viventium_media.engine import MediaError, Settings, Workspace, bootstrap, render, render_slot


class MediaContract(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.weights = self.root / "weights"
        for component in ("text_encoder", "transformer", "vae"):
            directory = self.weights / component
            directory.mkdir(parents=True)
            (directory / "model.safetensors.index.json").write_text(
                '{"weight_map": {"example": "0.safetensors"}}'
            )
            (directory / "0.safetensors").touch()
        self.config = self.root / "media.toml"
        self.config.write_text(
            '[models."z-image-turbo"]\nenabled=true\n'
            f'runtime={json.dumps(str(self.runtime))}\nweights={json.dumps(str(self.weights))}\n'
        )

    def renderer(self):
        script = self.runtime / "mflux-generate-z-image-turbo"
        expected = "--literal; newline\nkept"
        script.write_text(f"""#!/usr/bin/env python3
import os
import pathlib
import sys

assert "OPENAI_API_KEY" not in os.environ
assert os.environ["HF_HUB_OFFLINE"] == "1"
assert sys.argv[sys.argv.index("--base-model") + 1] == "z-image-turbo"
prompt = pathlib.Path(sys.argv[sys.argv.index("--prompt-file") + 1])
assert prompt.stat().st_mode & 0o777 == 0o600
assert prompt.read_text() == {expected!r}
output = pathlib.Path(sys.argv[sys.argv.index("--output") + 1])
output.write_bytes(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
))
""")
        script.chmod(0o700)

    def declaration(self):
        return bootstrap(self.config, Workspace.open(self.workspace), sys.executable, 1800)

    async def test_real_stdio_discovery_and_result(self):
        self.renderer()
        declaration = self.declaration()
        codex = tomllib.loads(declaration["codex_config_append"])["mcp_servers"]["viventium_media"]
        portable = declaration["claude_project_mcp"]["mcpServers"]["viventium_media"]
        self.assertEqual(codex["args"], portable["args"])
        self.assertEqual(codex["command"], portable["command"])
        params = StdioServerParameters(**portable, env={"OPENAI_API_KEY": "fixture-never-forward"})
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                self.assertEqual([tool.name for tool in tools], ["generate_image"])
                model = tools[0].inputSchema["properties"]["model"]
                self.assertEqual(model.get("enum", [model.get("const")]), ["z-image-turbo"])
                ref = self.root / "outside.png"
                ref.write_bytes(b"outside")
                (self.workspace / "link.png").symlink_to(ref)
                args = {"prompt": "--literal; newline\nkept", "model": "z-image-turbo"}
                denied = await client.call_tool("generate_image", {**args, "reference": "link.png"})
                self.assertTrue(denied.isError)
                self.assertIn("outside the authorized workspace", str(denied.content))
                with render_slot(self.config):
                    busy = await client.call_tool("generate_image", args)
                    self.assertTrue(busy.isError)
                    self.assertIn("renderer is busy", str(busy.content))
                result = await client.call_tool("generate_image", args)
                self.assertFalse(result.isError, result)
                payload = result.structuredContent or json.loads(result.content[0].text)
                self.assertEqual(payload["model"], "z-image-turbo")
                self.assertEqual(payload["mime_type"], "image/png")
                self.assertEqual((payload["width"], payload["height"]), (1, 1))
                self.assertTrue((self.workspace / payload["path"]).is_file())
                self.assertEqual(len(list((self.workspace / "artifacts").iterdir())), 1)

    async def test_native_worker_outputs_can_feed_the_next_tool_without_exporting_workspace_inputs(self):
        self.renderer()
        worker_tmp = self.root / "worker-temp"
        worker_tmp.mkdir()
        bundle = bootstrap(self.config, Workspace.open(self.workspace), sys.executable, 1800,
                           worker_cwd=True, worker_temp_output=True)
        params = StdioServerParameters(**bundle["claude_project_mcp"]["mcpServers"]["viventium_media"],
                                       env={"TMPDIR": str(worker_tmp)}, cwd=self.workspace)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                result = await client.call_tool("generate_image", {
                    "prompt": "--literal; newline\nkept", "model": "z-image-turbo",
                })
                self.assertFalse(result.isError, result)
                output = Path(result.structuredContent["path"])
                self.assertTrue(output.is_relative_to(worker_tmp.resolve()))
                self.assertFalse((self.workspace / "artifacts").exists())
                scope = Workspace(self.workspace, output.parent.parent)
                self.assertEqual(scope.reference(str(output)), output)
                unrelated = worker_tmp / "unrelated.png"
                unrelated.touch()
                with self.assertRaisesRegex(MediaError, "outside the authorized workspace"):
                    scope.reference(str(unrelated))

    def test_missing_and_disabled_routes_are_unavailable(self):
        settings = Settings.read(self.config)
        self.assertFalse(settings.ready("z-image-turbo"))
        self.assertFalse(settings.ready("qwen-image-2.1"))
        self.assertFalse(settings.ready("minimax-h3"))

    def test_artifacts_symlink_is_rejected(self):
        (self.workspace / "artifacts").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(MediaError, "real directory"):
            Workspace.open(self.workspace).artifacts()

    async def test_stop_kills_engine_and_discards_partial_file(self):
        marker = self.root / "pid"
        script = self.runtime / "mflux-generate-z-image-turbo"
        script.write_text(f"""#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import time
Path(sys.argv[sys.argv.index("--output") + 1]).write_bytes(b"partial")
Path({str(marker)!r}).write_text(str(os.getpid()))
time.sleep(300)
""")
        script.chmod(0o700)
        workspace = Workspace.open(self.workspace)
        task = asyncio.create_task(render(Settings.read(self.config), workspace, "z-image-turbo", "Fixture",
                                          width=64, height=64, seed=1, reference=None))
        try:
            async with asyncio.timeout(5):
                while not marker.exists() or not marker.read_text():
                    await asyncio.sleep(0.02)
            pid = int(marker.read_text())
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(list(workspace.artifacts().iterdir()), [])
        with render_slot(self.config):
            pass


if __name__ == "__main__":
    unittest.main()
