"""Embedding engines, and the helpers the engines that run on this machine have in common."""

import gc
from contextlib import nullcontext
from typing import ContextManager

from loguru import logger


def _torch():
    try:
        import torch
    except ImportError:
        return None
    return torch


def detect_device() -> str:
    """Return the best locally available torch device."""
    torch = _torch()
    if torch is None:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def inference_mode() -> ContextManager:
    """``torch.inference_mode()`` when torch is installed: no gradients, no autograd bookkeeping."""
    torch = _torch()
    return torch.inference_mode() if torch is not None else nullcontext()


def release_memory() -> None:
    """Give back what Python and the CUDA caching allocator keep for tensors that no longer exist."""
    gc.collect()
    torch = _torch()
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


def release_model(model) -> None:
    """Free the weights of a model that will not be used again, GPU copy included.

    The weights are moved to the CPU first: that frees the GPU copy right away, even if
    something still references the model object.
    """
    try:
        model.to("cpu")
    except Exception as error:  # e.g. ONNX backends have no device to move to
        logger.debug("Could not move the model to the CPU before releasing it: {}", error)
    release_memory()
