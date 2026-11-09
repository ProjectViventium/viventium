# Viventium local media tools

This optional Viventium package provides `generate_image` and `generate_video` through native
MCP stdio. Use it on the Mac that has the model files and Apple GPU. Image and video availability
can be configured independently. xPerfect supplies the workspace, access and run lifecycle.

| Model | Tool | Use |
| --- | --- | --- |
| Qwen-Image 2.1 | `generate_image` | Photorealistic stills and edits with a reference. |
| Z-Image Turbo | `generate_image` | Fast drafts from text. |
| MiniMax H3 | `generate_video` | Realistic motion and audio from text or a starting image. |

Each enabled model must have its own local weights and qualified executable. The model sees only
ready choices when the connection starts and selects one explicitly. The server checks that choice
on every call. It never downloads model files during a request. Restart the native tool connection
after changing enabled models or file locations.

## Set up on the rendering Mac

1. Install the package in a Python 3.11+ virtual environment with
   `python -m pip install ./viventium_v0_4/MCPs/local-media`. Use the resulting
   `viventium-media` executable from that environment.
2. Install [MFLUX](https://github.com/mflux-community/mflux) for the image engines. The qualified
   image version is `mflux==0.23.0`. For video use the Metal build of
   [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) at `f5df5f8` and FFmpeg with ffprobe.
   Keep each runtime in its own directory.
3. Provision the weights for the models you want. With the Hugging Face CLI, run
   `hf download REPOSITORY --revision REVISION --local-dir MODEL_DIRECTORY`, using the values below.
   For H3, specify the four files listed below after the repository name to avoid pulling other variants.
4. Save `viventium-media example` to a private TOML file, or copy [config.example.toml](config.example.toml).
   Set the absolute runtime
   `bin` and weight directory paths. Set `enabled = true` for each choice you want. Run
   `viventium-media doctor --config /absolute/path/to/media.toml` to check readiness.

| Model | Repository | Revision |
| --- | --- | --- |
| Qwen-Image 2.1 Q8 | `mflux-community/qwen-image-2-1-mflux-q8` | `f5c8cc79a6741026a6057546012fba3b0a4b5b25` |
| Z-Image Turbo Q8 | `mflux-community/z-image-turbo-mflux-q8` | `4ccff28917346aa9daae49cd3c477cf5260a242c` |
| MiniMax H3 Q5_0 | `unsloth/MiniMax-H3-GGUF` | `babc040eff0084465460ead58fdb8ec44296f8dd` |

H3 files: `minimax_h3_fl2va_pruned-Q5_0.gguf`, `qwen3vl_32b_minimax_h3-Q4_K_M.gguf`,
`vae/minimax_h3_video_vae_fp16.safetensors`, and `vae/minimax_h3_audio_vae_fp32.safetensors`.
See each upstream model card for its license and terms.

## Enable in Viventium

Put `media.toml` and the module's `.venv` in the same private directory. Use an existing native
host workspace root. After local setup, start Viventium with:

```sh
VIVENTIUM_LOCAL_MEDIA_CONFIG=/absolute/path/to/media.toml bin/viventium start
```

For a saved setting, set `integrations.local_media.config` in Viventium's configuration. A blank
setting keeps it off. Restart to change the registration. The switch adds the same tools to
authorized background host workers through both delegated launches and native handoffs. Speaking
Main and result-only callbacks do not gain these action tools. It does not change execution mode
or grant local access to Docker workers. Leave the current worker and delivery settings in place.

Ask for the file in chat. For example: “Make me a quick square draft of a red teapot by a rainy
window and send the PNG here.” A finished file uses the normal chat attachment path. Telegram
can send PNGs as photos and MP4s as videos, within its configured file limit.

## Connect an xPerfect worker

Generate an existing xPerfect bootstrap bundle fragment:

```sh
viventium-media connection --config /absolute/path/to/media.toml --workspace /absolute/path/to/workspace
```

For ordinary native workers that start in their own workspace below a known root, use
`--workspace-parent /absolute/path/to/worker-workspaces` instead. The MCP server scopes each call
to its working directory, which must be the configured root or a workspace inside it.

Apply the output to the operator-owned host worker's `bootstrap_bundle` using xPerfect's normal
worker configuration. It includes `codex_config_append` for Codex and `claude_project_mcp` for
Claude, Grok and Direct. If the worker already has connections, merge the server entry into those
fields. A direct native client can use the corresponding MCP declaration. The connection needs
a host worker with native tool access. Public Library registration and restricted Docker/clean-room
runs are separate deployment paths.

Use an ordinary request such as “Give me a quick picture of a red teapot by a window”, “Edit this
reference photo and keep the lighting” or “Give me a six-second clip with room tone”. The worker
chooses a configured model and links the exact result path. The regular MCP server writes into
the workspace's `artifacts/` directory. Viventium's compiler enables `--worker-temp-output` when
the worker starts inside the private LIFE workspace. New renders then stay in the worker's native
temporary area until the existing attachment publisher captures the result. The source reference
stays in LIFE. Use the returned path as the reference for a follow-up render in the same worker.

Keep one configuration per rendering Mac to share one local render slot across its authorized
workers. The module returns a busy result while a render is active. xPerfect owns work scheduling
and cancellation. Set its native run deadline long enough for the chosen render. The tested
six-second H3 case took about ten minutes. The package never modifies runtime accounts or credentials.
