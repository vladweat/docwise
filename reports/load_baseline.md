# Load baseline (retrieval)

Generated: `2026-09-22T13:38:50+00:00`
Eval user: `eval-employee@docwise.example.com` (hybrid `retrieve`: dense + FTS + RRF + rerank, no LLM)

## Corpus (indexed)

| Metric | Value |
| --- | ---: |
| `document_chunks` rows | 135 |
| `documents` ready | 22 |
| `documents` failed | 0 |
| Orgs with chunks | 4 |
| `HNSW_MAX_SCAN_TUPLES` | 20000 |
| `HNSW_ITERATIVE_SCAN` | relaxed_order |
| `RERANK_THRESHOLD` | 0.25 |

## Retrieval load

- Golden questions: **28** × **2** rounds = **56** `retrieve()` calls
- Concurrency: **1**
- Celery queue depth (`LLEN celery`) before run: **0**

| Latency (ms) | Value |
| --- | ---: |
| min | 1475.5 |
| mean | 1757.1 |
| p50 | 1732.0 |
| p95 | 2050.9 |
| p99 | 2278.4 |
| max | 2453.2 |

## How to reproduce

```bash
make up-fast
make eval-retrieval   # or existing indexed pilot corpus
make load-baseline    # LOAD_ROUNDS=3 LOAD_CONCURRENCY=2
```

Pilot acceptance: compare p95 to prior run on the **same** corpus size; if dense weakens in `/inspect`,
raise `HNSW_MAX_SCAN_TUPLES` and re-run. Chat TTFT adds LLM stream time — use `rag_audit_logs` after
a chat soak (`make check-pilot-alerts`).

