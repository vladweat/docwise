"""Download bge-small + bge-reranker ONNX weights into backend/.models."""

from __future__ import annotations

import sys
from pathlib import Path

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"
MODELS_DIR = Path(__file__).resolve().parent.parent / ".models"
VECTOR_SIZE = 384

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ingestion.onnx_cache import has_cached_onnx  # noqa: E402


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from fastembed import TextEmbedding
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except ImportError:
        print("ERROR: fastembed is not installed. Run make venv first.", file=sys.stderr)
        return 1

    if has_cached_onnx(MODELS_DIR, "bge-small"):
        print(f"OK: embeddings already in {MODELS_DIR}")
    else:
        print(f"Downloading {EMBED_MODEL} (ONNX) into {MODELS_DIR} ...")
        model = TextEmbedding(model_name=EMBED_MODEL, cache_dir=str(MODELS_DIR))
        vector = next(model.embed(["warmup"]))
        length = len(vector) if vector is not None else 0
        if length != VECTOR_SIZE:
            print(f"ERROR: expected {VECTOR_SIZE}-dim embeddings, got {length}", file=sys.stderr)
            return 1
        if not has_cached_onnx(MODELS_DIR, "bge-small"):
            print(f"ERROR: ONNX model was not saved into {MODELS_DIR}", file=sys.stderr)
            return 1
        print(f"OK: saved {EMBED_MODEL} -> {MODELS_DIR}")

    if has_cached_onnx(MODELS_DIR, "bge-reranker", "reranker-base"):
        print(f"OK: reranker already in {MODELS_DIR}")
        return 0

    print(f"Downloading {RERANK_MODEL} (ONNX) into {MODELS_DIR} ...")
    reranker = TextCrossEncoder(model_name=RERANK_MODEL, cache_dir=str(MODELS_DIR))
    scores = list(reranker.rerank("warmup", ["warmup document"]))
    if not scores:
        print("ERROR: reranker warmup returned no scores", file=sys.stderr)
        return 1
    if not has_cached_onnx(MODELS_DIR, "bge-reranker", "reranker-base"):
        print(f"ERROR: reranker ONNX was not saved into {MODELS_DIR}", file=sys.stderr)
        return 1
    print(f"OK: saved {RERANK_MODEL} -> {MODELS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
