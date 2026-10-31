"""Download one supported embedding/reranker profile into backend/.models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / ".models"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ingestion.embedding_profiles import embedding_profile, reranker_profile  # noqa: E402
from app.services.ingestion.onnx_cache import has_cached_onnx  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("current", "multilingual-compact"), default="current")
    args = parser.parse_args()
    embedding = embedding_profile(args.profile)
    reranker_config = reranker_profile(args.profile)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from fastembed import TextEmbedding
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except ImportError:
        print("ERROR: fastembed is not installed. Run make venv first.", file=sys.stderr)
        return 1

    if has_cached_onnx(MODELS_DIR, *embedding.cache_markers):
        print(f"OK: {embedding.model_name} already cached")
    else:
        print(f"Downloading {embedding.model_name} (ONNX) into {MODELS_DIR} ...")
        model = TextEmbedding(model_name=embedding.model_name, cache_dir=str(MODELS_DIR))
        vector = next(model.embed(["warmup"]))
        length = len(vector) if vector is not None else 0
        if length != embedding.vector_size:
            print(f"ERROR: expected {embedding.vector_size}-dim embeddings, got {length}", file=sys.stderr)
            return 1
        if not has_cached_onnx(MODELS_DIR, *embedding.cache_markers):
            print(f"ERROR: ONNX model was not saved into {MODELS_DIR}", file=sys.stderr)
            return 1
        print(f"OK: saved {embedding.model_name} -> {MODELS_DIR}")

    if has_cached_onnx(MODELS_DIR, *reranker_config.cache_markers):
        print(f"OK: {reranker_config.model_name} already cached")
        return 0

    print(f"Downloading {reranker_config.model_name} (ONNX) into {MODELS_DIR} ...")
    reranker = TextCrossEncoder(model_name=reranker_config.model_name, cache_dir=str(MODELS_DIR))
    scores = list(reranker.rerank("warmup", ["warmup document"]))
    if not scores:
        print("ERROR: reranker warmup returned no scores", file=sys.stderr)
        return 1
    if not has_cached_onnx(MODELS_DIR, *reranker_config.cache_markers):
        print(f"ERROR: ONNX model was not saved into {MODELS_DIR}", file=sys.stderr)
        return 1
    print(f"OK: saved {reranker_config.model_name} -> {MODELS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
