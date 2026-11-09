"""Image engines using the qualified native MFLUX CLI."""
from pathlib import Path

MODELS = {
    "qwen-image-2.1": "Photorealism, precise changes and reference editing. About 64 s and 50 GiB in the local still benchmark.",
    "z-image-turbo": "Quick text-to-image drafts and iterations. About 18 s and 17 GiB in the local still benchmark.",
}

RUNTIMES = {
    "qwen-image-2.1": ("mflux-generate-qwen-2.1", "mflux-generate-qwen-2.1-edit"),
    "z-image-turbo": ("mflux-generate-z-image-turbo",),
}


def command(model: str, runtime: Path, weights: Path, prompt_file: Path, output: Path, *,
            width: int, height: int, seed: int, reference: Path | None = None) -> list[str]:
    entrypoints = RUNTIMES[model]
    if reference and len(entrypoints) == 1:
        raise ValueError(f"{model} accepts text input only. Select a configured reference-edit model.")
    args = [
        str(runtime / entrypoints[int(reference is not None)]),
        "--model", str(weights), "--base-model", model,
        "--width", str(width), "--height", str(height),
        "--steps", "25" if model == "qwen-image-2.1" else "9",
        "--seed", str(seed), "--prompt-file", str(prompt_file), "--output", str(output), "--no-metadata",
    ]
    if model == "qwen-image-2.1":
        args += ["--guidance", "2.5"]
    if reference:
        args += ["--image-paths", str(reference)]
    return args
