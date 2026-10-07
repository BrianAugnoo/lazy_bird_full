"""Inspect model directories: weight formats, weight files and metadata.

A model is a directory (an HF snapshot) holding weights in one or more formats.
``FORMATS`` maps each format name, as used by ``LLMModel.formats`` and by engine
``formats`` lists, to the file patterns of its weights.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from lazy_bird.tools import gguf

FORMATS: dict[str, tuple[str, ...]] = {
    "safetensors": ("*.safetensors",),
    "gguf": ("*.gguf",),
    "onnx": ("*.onnx",),
    "openvino": ("*openvino*.xml",),
    "bin": ("*.bin",),
    "pth": ("*.pth", "*.pt"),
    "ckpt": ("*.ckpt",),
    "h5": ("*.h5",),
    "msgpack": ("*.msgpack",),
}
# *.bin files that are not model weights (training state, OpenVINO weights...).
NOT_WEIGHTS = ("training_args.bin", "optimizer*.bin", "scheduler*.bin", "rng_state*.bin", "*openvino*.bin")
# Small files fetched with any download: configuration, tokenizer, pooling...
SUPPORT_PATTERNS = ("*.json", "*.txt", "*.model", "*.tiktoken", "*.md", "*.py", "*.yaml", "*/*.json")
PREFERRED_GGUF = ("Q4_K_M", "Q5_K_M", "Q4_K_S", "Q8_0", "Q6_K", "F16", "BF16")


def format_of(relative_path: str) -> str | None:
    """Weight format of one file, or None for non-weight files."""
    name = Path(relative_path).name.lower()
    path = relative_path.lower()
    if any(fnmatch.fnmatch(name, pattern) for pattern in NOT_WEIGHTS):
        return None
    for weight_format, patterns in FORMATS.items():
        if any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path, pattern) for pattern in patterns):
            return weight_format
    return None


def weight_files(local_path: str | Path) -> dict[str, list[str]]:
    """Weight files of a model, grouped by format (paths relative to the model directory)."""
    root = Path(local_path)
    if root.is_file():
        found = format_of(root.name)
        return {found: [root.name]} if found else {}
    grouped: dict[str, list[str]] = {}
    if not root.is_dir():
        return grouped
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in Path(relative).parts) or not path.is_file():
            continue
        found = format_of(relative)
        if found:
            grouped.setdefault(found, []).append(relative)
    return {name: grouped[name] for name in FORMATS if name in grouped}


def default_file(weight_format: str | None, files: dict[str, list[str]]) -> str | None:
    """The weight file used when a format offers several alternatives (GGUF quantizations)."""
    candidates = files.get(weight_format or "", [])
    if weight_format != "gguf" or not candidates:
        return None
    by_quantization = {gguf.quantization(candidate): candidate for candidate in candidates}
    return next((by_quantization[name] for name in PREFERRED_GGUF if name in by_quantization), candidates[0])


def weights_size_mb(local_path: str, weight_format: str | None = None, selected_file: str | None = None) -> float:
    """Size of the weights a model loads, in MiB.

    Only the files of ``weight_format`` count (or ``selected_file`` alone). For ONNX
    the main ``model.onnx`` is preferred over quantized variants.
    """
    root = Path(local_path)
    if root.is_file():
        return root.stat().st_size / 1024**2
    if selected_file and (root / selected_file).is_file():
        return (root / selected_file).stat().st_size / 1024**2
    files = weight_files(root)
    chosen = files.get((weight_format or "").lower()) if weight_format else [name for group in files.values() for name in group]
    chosen = list(chosen or [])
    if (weight_format or "").lower() == "onnx" and chosen:
        main = [name for name in chosen if Path(name).name == "model.onnx"]
        chosen = main[:1] or [max(chosen, key=lambda name: (root / name).stat().st_size)]
    return sum((root / name).stat().st_size for name in chosen) / 1024**2


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def extract(local_path: str | Path) -> dict[str, Any]:
    """Read what lazy_bird needs to know about a model directory (or single weight file).

    Returns ``formats``, ``files`` (weights per format), ``dimension`` and
    ``max_context_length`` (None when unknown) and ``name`` (a suggestion).
    Raises ``FileNotFoundError`` when the path does not exist and ``ValueError`` when
    it holds no weights in a known format.
    """
    root = Path(local_path)
    if not root.exists():
        raise FileNotFoundError(f"Local path {root} does not exist.")
    files = weight_files(root)
    if not files:
        raise ValueError(f"No model weights found in {root} (known formats: {', '.join(FORMATS)}).")
    directory = root if root.is_dir() else root.parent
    config = _read_json(directory / "config.json")
    config = {**config.get("text_config", {}), **config}
    sentence_config = _read_json(directory / "sentence_bert_config.json")
    dimension = config.get("hidden_size") or config.get("d_model") or config.get("n_embd")
    context = sentence_config.get("max_seq_length") or config.get("max_position_embeddings") or config.get("n_positions")
    name = None
    if "gguf" in files:
        try:
            summary = gguf.summary(directory / files["gguf"][0] if root.is_dir() else root)
            dimension = dimension or summary["embedding_length"]
            context = context or summary["context_length"]
            name = summary["name"]
        except (OSError, gguf.GGUFError) as error:
            logger.warning("Could not read GGUF metadata of {}: {}", root, error)
    return {
        "formats": list(files),
        "files": files,
        "name": name,
        "dimension": dimension if isinstance(dimension, int) else None,
        "max_context_length": context if isinstance(context, int) else None,
    }


def download_model(
    repo_id: str,
    *,
    files: list[str] | None = None,
    revision: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> str:
    """Download a Hugging Face model into the HF cache; return its snapshot path.

    With ``files``, only those weight files are downloaded, plus the small support
    files (configuration, tokenizer...). ``progress(done_bytes, total_bytes)`` is
    called while downloading.
    """
    from huggingface_hub import snapshot_download

    allow_patterns = None if files is None else [*files, *SUPPORT_PATTERNS]
    return snapshot_download(
        repo_id=repo_id,
        revision=revision,
        allow_patterns=allow_patterns,
        tqdm_class=_progress_class(progress) if progress else None,
    )


def _progress_class(callback: Callable[[int, int], None]):
    """A tqdm replacement adding up the byte bars of a snapshot download."""
    from tqdm.auto import tqdm

    totals: dict[int, tuple[int, int]] = {}

    class Progress(tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["disable"] = True  # nothing printed; a disabled tqdm also stops counting
            super().__init__(*args, **kwargs)
            self._bytes = kwargs.get("unit") == "B"
            self._done = 0

        def update(self, n=1):
            super().update(n)
            if self._bytes and n:
                self._done += n
                totals[id(self)] = (self._done, self.total or 0)
                callback(int(sum(done for done, _ in totals.values())), int(sum(total for _, total in totals.values())))

    return Progress


def list_repo_files(repo_id: str, revision: str | None = None) -> list[dict[str, Any]]:
    """Files of a Hugging Face model repository with their size and weight format."""
    from huggingface_hub import HfApi

    items = HfApi().list_repo_tree(repo_id, recursive=True, revision=revision, expand=True)
    files = []
    for item in items:
        size = getattr(item, "size", None)
        if size is None:
            continue
        files.append({"path": item.path, "size": size, "format": format_of(item.path)})
    return sorted(files, key=lambda item: item["path"])
