# RAG quality diagnostics: full retrieval and generation slice

- Run date: `2026-10-31`
- Code revision: `a5356e1`
- Profile: current `BAAI/bge-small-en-v1.5` + `BAAI/bge-reranker-base`; threshold `0.25`; Top-K `4`

The 132-case retrieval-only run covers the combined set. A separate 30-case run adds generation
and judges on 12 positive, 6 no-answer, and 12 ACL-negative cases. The full 132-case generation
run did not finish within the VPS memory budget. No query text, answers, chunk content, secrets,
or restricted document content are included below.

## Full 132-case retrieval-only run

Dataset SHA-256: `619eb9cec165a432e5da1ac3346a434b2c56d78e48f63428f29a10e08dda1f9f`

| Check | Observed | Interpretation |
| --- | ---: | --- |
| Positive target-document hits | `66 / 85` (`0.776`) | Below the `0.980` regression floor |
| MIRACL target-document hits | `25 / 40` (`0.625`) | Main weak slice |
| Synthetic target-document hits | `41 / 45` (`0.911`) | Also below the floor |
| ACL leaks | `0 / 41` | ACL gate passed |
| Case errors | `0` | All retrieval cases completed |
| Generation / no-answer refusal | not run | Retrieval-only mode |

For MIRACL, target-document hit was `0.975` after RRF and reranker scoring, then fell to `0.625`
after thresholding and Top-4. On the same scores, threshold `0.10` raised MIRACL hit to `0.675`
and synthetic hit to `0.956`, or `70 / 85` (`0.824`) overall. That is a measurable coverage gain,
but still misses the `0.980` floor and has not been checked for answer quality or false answers on
no-answer cases. It is not a production change candidate yet.

Runtime: query embedding `3.48 s`, DB search `3.15 s`, reranking `642.55 s` for 1,980 pairs at
batch size 16. Reranking accounts for about `99%` of measured retrieval time.

## 30-case generation diagnostic

Dataset slice SHA-256: `9741a67c195a419149a09e2a645f39ccc10bee0ca3a6ee62b90c329a8dfd72d2`. It contains
12 positive cases (4 synthetic, 8 MIRACL), all 6 no-answer cases, and 12 ACL-negative cases.

| Check | Observed | Interpretation |
| --- | ---: | --- |
| Positive target-document hits | `9 / 12` (`0.750`) | Below the regression floor |
| Synthetic positive target hits | `4 / 4` (`1.000`) | Small synthetic slice |
| MIRACL positive target hits | `5 / 8` (`0.625`) | Small real-text slice |
| Correct no-answer refusals | `6 / 6` (`1.000`) | All six English and Russian cases refused |
| ACL leaks | `0 / 12` | ACL gate passed for this slice |
| Faithfulness | `1.000` (`n=9`) | Generated positive answers with context |
| Context Precision | `0.944` (`n=9`) | Below the `0.975` floor |
| Citation support | `0.833` (`n=9`) | Exploratory on this small slice |
| Answer Relevance | unavailable | The image lacks the multilingual MiniLM ONNX cache; 9 cases were marked errors by the evaluator |

For the eight MIRACL cases, expected documents survived reranker scoring in `8 / 8` cases, then
thresholding and Top-4 retained `5 / 8`. Exact-section Recall@4 fell from `1.000` to `0.625`.
The `0.10–0.30` threshold sweep did not change target hit on this small slice. The four synthetic
cases remained `4 / 4` across those stages. This points to a real-text ranking/selection weakness,
but does not establish a safe replacement policy.

## Resource limits and decision

The full retrieval-only run completed with Docker memory limit `--memory=2500m`; observed process
RSS was about `2.25 GiB` (`2,353,732 KiB`). The full generation attempt was stopped before completion
when host available RAM fell below `0.5 GiB`. On the 30-case diagnostic, batch 16 reached about
`2.23 GiB` RSS (`2,335,236 KiB`). A retry with batch 32 took `171.11 s` for 450 pairs and reached
about `2.47 GiB` RSS (`2,594,328 KiB`) while using swap; batch 16 took `155.50 s` on the same
slice. Batch 32 was slower and used more memory for these longer passages.

Earlier multilingual-candidate reports use different dataset revisions and fail one or more quality
floors. They are context, not a same-dataset comparison:
[MIRACL candidate report](rag_miracl_candidate.md) and
[MIRACL stage diagnostic](rag_miracl_stage_diagnostic.md).

Decisions:

- Keep the current production profile and threshold unchanged.
- Do not claim that the multilingual candidate passes the current combined gates.
- Do not introduce async retrieval or concurrent database sessions; measured DB search is a small
  fraction of this slice, while reranking dominates.
- Before selecting a retrieval change, rerun the same combined dataset on a larger-memory worker
  with both evaluator encoders cached, then compare current and candidate profiles against all
  positive, no-answer, and ACL-negative gates.
