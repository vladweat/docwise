# Quality evaluation (Ragas)

The `eval/` module shows the system is not naive RAG: faithfulness to context, clean chunks, answer relevance.

## Contents

| Artifact | Purpose |
| --- | --- |
| `eval/golden_dataset.json` | ≥ 30 pairs: `question`, `ground_truth_answer`, `target_doc_id` (prefer `target_page`, `must_not_doc_ids` for ACL) |
| `eval/run_eval.py` | Run through real retrieval+generation pipeline |
| `eval/corpus.py` | Synthetic PDFs with stable UUIDs and tags `all` / `hr` / `finance` |
| `eval/seed_demo.py` | Local demo: employee / HR / admin and twelve PDFs (`all` / `hr` / `finance`) |
| `reports/rag_benchmark.md` | Metrics table for README |

Synthetic set is fine initially; later add questions from real (anonymized) PDFs.

Golden set runs as user `eval-employee@docwise.example.com` (`employee`, `departments=[]`). Roles are not taken from request body. `hr` and `finance` documents are in `must_not_doc_ids` for **every** question.

## Metrics

Computed per Ragas definitions with the same OpenAI-compatible client as chat (`complete_openai` / `stream_openai`). LangChain and `ragas` package are not runtime dependencies.

1. **Faithfulness** — answer stays within context (anti-hallucination).
2. **Context Precision** — few junk chunks in Top-K.
3. **Answer Relevance** — answer substantively addresses the question (cosine of generated questions vs original).

Additionally (custom asserts):

- retrieved chunk page matches `target_page` in a fraction of cases;
- employee user does not receive chunks from `must_not_doc_ids` (exit code 1 on any leak);
- org A user does not receive org B documents (including `access_roles = ['all']`).

## Running

```bash
make eval
# or retrieval + ACL only, without LLM judges:
make eval-retrieval
```

Equivalent inside backend container:

```bash
python /eval/run_eval.py --seed
```

`--seed` creates eval user (org `eval`) and runs fixture PDFs through real `index_pdf` (not Celery). A decoy document in org `eval-foreign` with tag `all` is seeded in parallel; runner adds its UUID to `must_not_doc_ids`. Requires: stack up, LLM key, FastEmbed cache. CI unit tests **do not** invoke this script by default.

Local ACL demo (employee vs HR vs finance, twelve PDFs):

```bash
make demo
```

Script: [eval/seed_demo.py](../../eval/seed_demo.py). Users and walkthrough — root [README.md](../../README.md).

## When to run

After changes to chunking, RRF, reranker threshold, system prompt, embeddings, or sparse (FTS vs BM25 on dense). In PRs — briefly note metric movement, not only “added eval”. After independent FTS (migration `012`) — re-run eval before release.

## Release discipline (fusion / FTS / rerank / prompt)

Use this checklist when a PR touches hybrid retrieval, Postgres FTS, RRF (`k=60`), reranker threshold, chunking/meta headers, embeddings, or chat system/refusal prompts. PR template mirrors the same boxes (`.github/pull_request_template.md`).

| Change area | Command | Update artifacts |
| --- | --- | --- |
| `backend/app/services/retrieval/` only (no prompt) | `make eval-retrieval` | If page hit or ACL regress: note in PR; full `make eval` if rerank threshold moved |
| Fusion, FTS query, rerank threshold, chunking, embeddings | `make eval` | [reports/rag_benchmark.md](../../reports/rag_benchmark.md) (regenerate table via eval runner); [nfr.md](nfr.md) § RAG quality date line if Faithfulness, ACL, or diagnostic metrics move materially (≥ 0.02 absolute or any ACL leak) |
| Chat prompt / refusal wording / answer length | `make eval` | Same as above; compare **Answer Relevance** per-question in benchmark appendix |
| No RAG path change | — | Check “did not change retrieval” in PR template |

**Faithfulness and ACL leaks are release gates** (see thresholds below). Context Precision, Answer Relevance, and page hit are diagnostic until gated in NFR.

**Inspect for misses:** `/search/inspect` (Compose: `ENABLE_SEARCH_INSPECT=true`) — dense → FTS → RRF → reranked. Do not log restricted chunk bodies in tickets visible to the same user.

Maintaining the benchmark file: [reports/rag_benchmark.md](../../reports/rag_benchmark.md#maintaining-this-report).

## Release thresholds

Latest live run (**2026-09-22**, eval fixture section splits; 35 cases, `eval-employee`, retrieval + generation + Ragas):

| Metric | Threshold | Actual |
| --- | ---: | ---: |
| Faithfulness | ≥ 0.8 | 1.000 |
| Context Precision | guideline ≥ 0.9 | 0.994 |
| Answer Relevance | ≥ 0.75 | 0.776 |
| Target page hit | ≥ 0.95 | 1.000 |
| ACL `must_not_doc_ids` | **0 leaks** | 0 / PASS |

Summary: SQL RBAC before LLM holds corpus (7 ACL negatives, 0 leaks). Faithfulness 1.0 on positives. Prior **2026-09-21** run (FTS `012`): page hit 0.929 — two rerank-threshold refusals on multi-topic handbook/engineering chunks; fixed by splitting eval PDF sections (`eval/corpus.py`) so rerank scores clear 0.25 without lowering the threshold. Optional CI: [`.github/workflows/eval.yml`](../../.github/workflows/eval.yml) (`workflow_dispatch`, `OPENAI_API_KEY`). Table: [reports/rag_benchmark.md](../../reports/rag_benchmark.md).
