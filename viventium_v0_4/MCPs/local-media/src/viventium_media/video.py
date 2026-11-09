"""Video engine using the qualified MiniMax H3 Metal CLI."""
from pathlib import Path

MODEL = "minimax-h3"
DESCRIPTION = (
    "Realistic motion from text or a starting image, with generated audio. "
    "About 3 min for a short clip or 10 min for six seconds, at about 20 GiB in the local benchmark."
)
WEIGHTS = {
    "--diffusion-model": "minimax_h3_fl2va_pruned-Q5_0.gguf",
    "--llm": "qwen3vl_32b_minimax_h3-Q4_K_M.gguf",
    "--vae": "vae/minimax_h3_video_vae_fp16.safetensors",
    "--audio-vae": "vae/minimax_h3_audio_vae_fp32.safetensors",
}


def command(runtime: Path, weights: Path, prompt_file: Path, output: Path, *,
            width: int, height: int, frames: int, seed: int, reference: Path | None = None) -> list[str]:
    args = [
        str(runtime / "sd-cli"), "--mode", "vid_gen",
        "--width", str(width), "--height", str(height), "--video-frames", str(frames), "--fps", "24",
        "--seed", str(seed), "--cfg-scale", "1.0", "--rng", "cpu",
        "--prompt-file", str(prompt_file), "--output", str(output), "--sampling-method", "euler",
        "--backend", "MTL0", "--params-backend", "disk", "--mmap", "--vae-tiling", "--steps", "12",
    ]
    for flag, file in WEIGHTS.items():
        args += [flag, str(weights / file)]
    if reference:
        args += ["--init-img", str(reference)]
    return args


def encode(ffmpeg: Path, source: Path, output: Path) -> list[str]:
    return [
        str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-map_metadata", "-1", "-movflags", "+faststart", str(output),
    ]


def probe(ffprobe: Path, source: Path) -> list[str]:
    return [
        str(ffprobe), "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
        "-of", "json", str(source),
    ]
