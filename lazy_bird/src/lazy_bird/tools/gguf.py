"""Read the metadata header of a GGUF file (llama.cpp format) without extra dependencies.

Only the key/value section is parsed; large arrays (the tokenizer vocabulary) are
skipped rather than decoded.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any, BinaryIO

MAGIC = b"GGUF"
_SCALARS = {
    0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d",
}
_STRING, _ARRAY = 8, 9
# llama.cpp `general.file_type` values (llama_ftype) for the common quantizations.
FILE_TYPES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1", 10: "Q2_K", 11: "Q3_K_S",
    12: "Q3_K_M", 13: "Q3_K_L", 14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M", 18: "Q6_K",
    19: "IQ2_XXS", 20: "IQ2_XS", 21: "Q2_K_S", 22: "IQ3_XS", 23: "IQ3_XXS", 24: "IQ1_S", 25: "IQ4_NL",
    26: "IQ3_S", 27: "IQ3_M", 28: "IQ2_S", 29: "IQ2_M", 30: "IQ4_XS", 31: "IQ1_M", 32: "BF16",
}
QUANTIZATION_IN_NAME = re.compile(r"(?i)(?:^|[-_.])((?:I?Q\d(?:_[A-Z0-9]+)*)|F16|F32|BF16)(?=[-_.]|$)")


class GGUFError(ValueError):
    """The file is not a readable GGUF file."""


def _read(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise GGUFError("unexpected end of file")
    return data


def _scalar(stream: BinaryIO, kind: int) -> Any:
    fmt = _SCALARS[kind]
    return struct.unpack(fmt, _read(stream, struct.calcsize(fmt)))[0]


def _string(stream: BinaryIO) -> str:
    (length,) = struct.unpack("<Q", _read(stream, 8))
    return _read(stream, length).decode("utf-8", errors="replace")


def _value(stream: BinaryIO, kind: int, keep_arrays: bool) -> Any:
    if kind in _SCALARS:
        return _scalar(stream, kind)
    if kind == _STRING:
        return _string(stream)
    if kind == _ARRAY:
        item_kind, count = struct.unpack("<IQ", _read(stream, 12))
        if not keep_arrays and item_kind in _SCALARS:
            stream.seek(struct.calcsize(_SCALARS[item_kind]) * count, 1)
            return None
        if not keep_arrays and item_kind == _STRING:
            for _ in range(count):
                (length,) = struct.unpack("<Q", _read(stream, 8))
                stream.seek(length, 1)
            return None
        return [_value(stream, item_kind, keep_arrays) for _ in range(count)]
    raise GGUFError(f"unknown value type {kind}")


def read_metadata(path: str | Path) -> dict[str, Any]:
    """Return the GGUF key/value metadata (arrays are skipped)."""
    with open(path, "rb") as stream:
        if _read(stream, 4) != MAGIC:
            raise GGUFError(f"{path} is not a GGUF file")
        (version,) = struct.unpack("<I", _read(stream, 4))
        count_format = "<I" if version == 1 else "<Q"
        _tensors = struct.unpack(count_format, _read(stream, struct.calcsize(count_format)))[0]
        (kv_count,) = struct.unpack(count_format, _read(stream, struct.calcsize(count_format)))
        metadata: dict[str, Any] = {"gguf.version": version}
        for _ in range(kv_count):
            key = _string(stream)
            (kind,) = struct.unpack("<I", _read(stream, 4))
            value = _value(stream, kind, keep_arrays=False)
            if value is not None:
                metadata[key] = value
        return metadata


def quantization(path: str | Path, metadata: dict[str, Any] | None = None) -> str | None:
    """Quantization of a GGUF file, from its metadata or else from its name."""
    file_type = (metadata or {}).get("general.file_type")
    if isinstance(file_type, int) and file_type in FILE_TYPES:
        return FILE_TYPES[file_type]
    match = QUANTIZATION_IN_NAME.search(Path(path).stem)
    return match.group(1).upper() if match else None


def summary(path: str | Path) -> dict[str, Any]:
    """Name, architecture, context length, embedding size and quantization of a GGUF file."""
    metadata = read_metadata(path)
    architecture = metadata.get("general.architecture")
    return {
        "name": metadata.get("general.name"),
        "architecture": architecture,
        "context_length": metadata.get(f"{architecture}.context_length"),
        "embedding_length": metadata.get(f"{architecture}.embedding_length"),
        "quantization": quantization(path, metadata),
    }
