"""Detect FastEmbed/HuggingFace ONNX files in a cache directory.

HF hub stores weights as content-addressed blobs; the `*.onnx` name lives on a
snapshot symlink. FastEmbed also remaps `BAAI/bge-small-en-v1.5` to
`qdrant/bge-small-en-v1.5-onnx-q`, so we match path markers, not the API name.
"""

from __future__ import annotations

from pathlib import Path


def iter_cached_onnx(cache_dir: Path):
    if not cache_dir.is_dir():
        return
    yield from cache_dir.rglob("*.onnx")


def has_cached_onnx(cache_dir: Path, *needles: str) -> bool:
    """True if some `*.onnx` path (symlink names included) contains a needle."""
    markers = [item.lower() for item in needles if item]
    found = False
    for path in iter_cached_onnx(cache_dir):
        found = True
        haystack = str(path).lower()
        if not markers or any(marker in haystack for marker in markers):
            return True
    return found and not markers
