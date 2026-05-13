from __future__ import annotations

import platform


MODEL_FILENAMES = {
    "tiny": "ggml-tiny.bin",
    "tiny.en": "ggml-tiny.en.bin",
    "base": "ggml-base.bin",
    "base.en": "ggml-base.en.bin",
    "small": "ggml-small.bin",
    "small.en": "ggml-small.en.bin",
    "medium": "ggml-medium.bin",
    "medium.en": "ggml-medium.en.bin",
    "large-v1": "ggml-large-v1.bin",
    "large-v2": "ggml-large-v2.bin",
    "large-v2-q5_0": "ggml-large-v2-q5_0.bin",
    "large-v3": "ggml-large-v3.bin",
    "large-v3-q5_0": "ggml-large-v3-q5_0.bin",
    "large-v3-turbo": "ggml-large-v3-turbo.bin",
    "large-v3-turbo-q5_0": "ggml-large-v3-turbo-q5_0.bin",
}

MODEL_SHA1 = {
    "ggml-tiny.bin": "bd577a113a864445d4c299885e0cb97d4ba92b5f",
    "ggml-tiny.en.bin": "c78c86eb1a8faa21b369bcd33207cc90d64ae9df",
    "ggml-base.bin": "465707469ff3a37a2b9b8d8f89f2f99de7299dac",
    "ggml-base.en.bin": "137c40403d78fd54d454da0f9bd998f78703390c",
    "ggml-small.bin": "55356645c2b361a969dfd0ef2c5a50d530afd8d5",
    "ggml-small.en.bin": "db8a495a91d927739e50b3fc1cc4c6b8f6c2d022",
    "ggml-medium.bin": "fd9727b6e1217c2f614f9b698455c4ffd82463b4",
    "ggml-medium.en.bin": "8c30f0e44ce9560643ebd10bbe50cd20eafd3723",
    "ggml-large-v1.bin": "b1caaf735c4cc1429223d5a74f0f4d0b9b59a299",
    "ggml-large-v2.bin": "0f4c8e34f21cf1a914c59d8b3ce882345ad349d6",
    "ggml-large-v2-q5_0.bin": "00e39f2196344e901b3a2bd5814807a769bd1630",
    "ggml-large-v3.bin": "ad82bf6a9043ceed055076d0fd39f5f186ff8062",
    "ggml-large-v3-q5_0.bin": "e6e2ed78495d403bef4b7cff42ef4aaadcfea8de",
    "ggml-large-v3-turbo.bin": "4af2b29d7ec73d781377bfd1758ca957a807e941",
    "ggml-large-v3-turbo-q5_0.bin": "e050f7970618a659205450ad97eb95a18d69c9ee",
}


def default_model_name() -> str:
    if platform.machine().lower() == "x86_64":
        return "small"
    return "large-v3-turbo"


__all__ = ["MODEL_FILENAMES", "MODEL_SHA1", "default_model_name"]
