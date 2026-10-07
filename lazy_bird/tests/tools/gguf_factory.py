"""Build tiny GGUF files for tests."""

import struct
from pathlib import Path


def _string(value: str) -> bytes:
    data = value.encode()
    return struct.pack("<Q", len(data)) + data


def write_gguf(path: Path, metadata: dict, *, vocabulary: int = 3) -> Path:
    """Write a GGUF v3 header with ``metadata`` (str/int values) and a token array."""
    items = []
    for key, value in metadata.items():
        if isinstance(value, str):
            items.append(_string(key) + struct.pack("<I", 8) + _string(value))
        else:
            items.append(_string(key) + struct.pack("<I", 4) + struct.pack("<I", value))
    tokens = struct.pack("<IQ", 8, vocabulary) + b"".join(_string(f"tok{index}") for index in range(vocabulary))
    items.append(_string("tokenizer.ggml.tokens") + struct.pack("<I", 9) + tokens)
    header = b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0) + struct.pack("<Q", len(items))
    path.write_bytes(header + b"".join(items) + b"\0" * 64)
    return path
