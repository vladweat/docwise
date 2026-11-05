# RAG quality diagnostics: full retrieval and generation slice

- Run date: `2026-10-31`
- Code revision: `a5356e1`
- Profile: current `BAAI/bge-small-en-v1.5` + `BAAI/bge-reranker-base`; threshold `0.25`; Top-K `4`

The full 132-case run covers retrieval, generation, and judges on 85 positive, 6 no-answer, and
41 ACL-negative cases. No query text, answers, chunk content, secrets, or restricted document
content are included below.

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

## Full 132-case generation and judge run

Code revision: `3d3a034`. The full run used the same dataset hash and current production profiles
as the retrieval baseline, with both answer-relevance encoders cached. It completed all 132 cases
with zero case errors. Aggregate metrics:

| Check | Observed | Interpretation |
| --- | ---: | --- |
| Positive target-document hits | `66 / 85` (`0.776`) | Below the `0.980` floor |
| Target-page hit rate | `1.000` | Gate passed |
| Faithfulness | `0.984` (`n=62`) | Gate passed; refusals and cases without context are excluded |
| Context Precision | `0.961` (`n=68`) | Below the `0.975` floor |
| English Answer Relevance | `0.722` (`n=53`) | Below the `0.827` floor |
| Answer Relevance, all positive cases | `0.591` (`n=85`) | Includes Russian and mixed-language cases |
| Citation support | `0.980` (`n=62`) | Exploratory judge metric |
| Correct no-answer refusals | `6 / 6` | All English and Russian no-answer cases refused |
| ACL leaks | `0 / 41` | ACL gate passed |
| Case errors | `0` | All cases completed |

The system answered `62 / 85` positive cases and refused `23 / 85`; `68 / 85` had retrieved
context. The full report's quality slices show the largest Answer Relevance gap on Russian and
mixed-language questions, while the English slice also remains below its regression floor. The
current run therefore validates the evaluator path and the safety gates, but does not pass the
combined quality gates and does not justify changing the production profile or threshold.

Runtime profile: query embedding `2.57 s`, database search `3.30 s`, and reranking `612.04 s`
for 1,980 pairs at batch size 16. Reranking remains the dominant measured local stage. During
generation/judging the eval container was observed around `2.40 / 2.73 GiB`; host available RAM
was about `0.64 GiB`. No demo containers were running.

The raw per-question generation report is generated under `/tmp` on the VPS and intentionally is
not committed because it contains question text. The sanitized per-case JSON artifact described
below contains IDs, ranks, scores, and metrics only.

## Same-dataset multilingual candidate comparison

The current and `multilingual-compact` profiles were run on the same 132 cases and dataset SHA-256
`619eb9cec165a432e5da1ac3346a434b2c56d78e48f63428f29a10e08dda1f9f`, with the same prompt, LLM,
threshold `0.25`, Top-K `4`, and concurrency `4`. Candidate profile: multilingual MiniLM embeddings,
80-token chunks, and `BAAI/bge-reranker-v2-m3-int8`. Candidate run code was `3d3a034`.

| Metric | Current `0.25` | Multilingual `0.25` | Multilingual `0.10` |
| --- | ---: | ---: | ---: |
| Target document hit, all positive | `0.776` (`66/85`) | `0.953` (`81/85`) | `0.965` (`82/85`) |
| MIRACL target document hit | `0.625` (`25/40`) | `0.900` (`36/40`) | `0.925` (`37/40`) |
| Synthetic target document hit | `0.911` (`41/45`) | `1.000` (`45/45`) | `1.000` (`45/45`) |
| Target section hit | `0.596` (`31/52`) | `0.846` (`44/52`) | `0.885` (`46/52`) |
| Faithfulness | `0.984` (`n=62`) | `0.979` (`n=70`) | `0.986` (`n=71`) |
| Context Precision | `0.961` (`n=68`) | `0.944` (`n=83`) | `0.927` (`n=83`) |
| English Answer Relevance | `0.722` (`n=53`) | `0.741` (`n=53`) | `0.739` (`n=53`) |
| Answer Relevance, all languages | `0.591` (`n=85`) | `0.666` (`n=85`) | `0.661` (`n=85`) |
| Citation support | `0.980` (`n=62`) | `0.966` (`n=70`) | `0.891` (`n=71`) |
| Correct no-answer refusals | `6/6` | `6/6` | `6/6` |
| ACL leaks | `0/41` | `0/41` | `0/41` |
| Case errors | `0` | `0` | `0` |

The candidate at `0.25` substantially improves multilingual retrieval, but misses the target-document
floor (`0.980`) by `0.027`; its Context Precision (`0.944`) and English Answer Relevance (`0.741`)
also remain below their `0.975` and `0.827` floors. Four MIRACL target documents remain absent from
Top-4; eight MIRACL cases miss the exact target section (3 English, 5 Russian). Synthetic target
documents are all found. This localizes the residual retrieval gap to the real-text slice, with a
larger section-recall gap on the Russian questions.

MIRACL exact-section misses at candidate threshold `0.25` (case IDs only):
`miracl-en-2679`, `miracl-en-3809`, `miracl-en-2204`, `miracl-ru-2468`, `miracl-ru-4559`,
`miracl-ru-223`, `miracl-ru-1086`, and `miracl-ru-4489`.

Threshold sweep on the candidate's saved scores raises MIRACL document hit from `0.900` at `0.25`
to `0.925` at `0.10`, and MIRACL section Recall@4 from `0.800` to `0.850`. Synthetic document hit
stays `1.000`, giving `82/85` (`0.965`) combined document hits at `0.10`, still below the floor.
The full candidate run at `0.10` confirmed `6/6` correct no-answer refusals, `0/41` ACL leaks,
and zero case errors. It also measured Context Precision `0.927`, English Answer Relevance `0.739`,
all-language Answer Relevance `0.661`, and citation support `0.891`. Against candidate threshold
`0.25`, the document hit gain is only `+0.012`, while Context Precision drops `0.017` and citation
support drops `0.075`; the three quality floors still fail. Therefore `0.10` is not a safe
promotion candidate even though the refusal and ACL gates pass.

The stage metrics localize a specific part of the retrieval loss: on MIRACL, the exact target
section is in Top-4 for `39/40` cases after reranker scoring, but only `34/40` after threshold `0.10`
and `32/40` after threshold `0.25`. A global threshold discards some relevant multilingual
passages; lowering it recovers two sections, while the full answer run shows worse Context Precision
and citation support. This does not prove a per-language threshold is the fix: there are too few
cases to calibrate one safely, and answer relevance still needs a separate improvement.

At `0.10`, the six remaining MIRACL exact-section misses are `miracl-en-2204`,
`miracl-en-2679`, `miracl-ru-1086`, `miracl-ru-223`, `miracl-ru-2468`, and `miracl-ru-4489`.
The report records only IDs here; the detailed per-question report remains on the VPS. These are
real-text factoid cases with specific entities or terminology, so entity/term matching is a plausible
next hypothesis, not a confirmed root cause. Retrieved passage inspection would be needed before
choosing a code change.

### Full end-to-end candidate at threshold `0.01`

To test whether the remaining five section misses were caused by the cutoff, the same 132-case
candidate run was repeated at `0.01`, changing only the reranker threshold. The isolated evaluation
completed all cases against the same dataset hash; no production setting was changed.

| Metric | Candidate `0.10` | Candidate `0.01` | Change |
| --- | ---: | ---: | ---: |
| Target document hit | `0.965` (`82/85`) | `1.000` (`85/85`) | `+0.035` |
| Target section hit | `0.885` (`46/52`) | `0.981` (`51/52`) | `+0.096` |
| MIRACL target section hit | `0.850` (`34/40`) | `0.975` (`39/40`) | `+0.125` |
| Faithfulness | `0.986` | `0.969` | `-0.017` |
| Context Precision | `0.927` | `0.922` | `-0.005` |
| English Answer Relevance | `0.739` | `0.777` | `+0.038` |
| Answer Relevance, all languages | `0.661` | `0.720` | `+0.059` |
| Citation support | `0.891` | `0.935` | `+0.044` |
| Correct no-answer refusals | `6/6` | `6/6` | unchanged |
| ACL leaks | `0/41` | `0/41` | unchanged |
| Case errors | `0` | `0` | unchanged |

The lower cutoff recovered five of the six previously missed MIRACL sections; the sixth (`miracl-ru-223`)
was absent from dense, sparse, RRF, and reranker-scored results, so threshold changes cannot recover it.
This supports the cutoff as a real source of missed relevant context. It still does not pass the
Context Precision (`0.922` vs `0.975` floor) or English Answer Relevance (`0.777` vs `0.827` floor)
gates. Target-document recall and all-language relevance improve, while precision declines slightly.
Three judge responses were malformed JSON on the first attempt and succeeded on the evaluator's
single retry; all 132 cases completed with zero errors. Reranking took about `1,201.5 s` for 1,980
pairs, roughly `1.96×` the current profile's `612.04 s` on this VPS.

Decision: `0.01` demonstrates a strong recall gain but is not a production-ready configuration because
the combined quality gates still fail and reranking is nearly twice as slow. Keep production profile
and threshold unchanged. The next improvement should target context precision and answer relevance
while preserving the recovered relevant sections. In the multilingual candidate run, the remaining
exact-section miss was absent from all first-stage lists; the current-profile rerun below shows a
different rank path for the same case. The detailed report containing per-case question text was
removed after analysis and is not committed; a later rerun produced the sanitized JSON artifact
described below.

### Unicode FTS diagnosis and current-profile verification

The query for `miracl-ru-223` contains Cyrillic letters followed by Unicode combining acute accents.
PostgreSQL `to_tsvector('simple', ...)` keeps each marked word as one lexeme (for example, `ру́аль`),
while Python's previous lexical regex split it into fragments (`ру`, `аль`). The generated FTS query
then rejected those fragments as unsafe because `str.isalpha()`/`str.isalnum()` return false for
combining marks. `lexical_tokens` now keeps Unicode category `M` marks attached to the preceding
letter, and FTS query validation explicitly allows attached marks. The regression tests cover both
token construction and an actual ACL-filtered `sparse_search` against PostgreSQL.

The full current-profile retrieval-only run after this fix completed the same 132 cases at threshold
`0.25`: target-document hit remained `0.776` (`66/85`), MIRACL target-document hit `0.625` (`25/40`),
ACL leaks `0/41`, and case errors `0`. On the named case, the exact target section was rank `8` at
dense, absent from the sparse exact-section list, rank `9` after RRF, and rank `1` after reranker
scoring; the final `0.25` cutoff still removed it. This separates two facts: FTS tokenization had a
real Unicode correctness bug, but that bug was not the remaining final-stage failure in this current
profile run. Here, the measured failure occurs at thresholding. The candidate multilingual profile
has a different earlier-stage result for this case, so it remains a separate profile-specific
diagnostic. Retrieval-only metrics do not measure Context Precision or Answer Relevance; this fix
does not claim an end-to-end quality gain, and production threshold/profile remain unchanged.

The candidate's query embedding and DB search took `1.50 s` and `5.86 s`; reranking took
`1,257.78 s` for 1,980 pairs, versus `2.57 s`, `3.30 s`, and `612.04 s` for the current profile.
At threshold `0.10`, query embedding and DB search took `1.45 s` and `3.16 s`, while reranking
took `1,192.39 s`. Candidate reranking is `2.06×` slower at `0.25` and `1.95×` slower at `0.10`
than current on this VPS. No profile or threshold change is promoted: the recall gain is meaningful,
but the full quality gates still fail and reranking cost nearly doubles. The full per-question
candidate report was stored in `/tmp` for analysis and removed afterward; see the sanitized case
diagnostic below.

## 30-case generation diagnostic (earlier run)

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
| Answer Relevance | unavailable in that run | The image lacked the multilingual MiniLM ONNX cache; 9 cases were marked errors by the evaluator. The later full run above used the cached model and had zero case errors. |

For the eight MIRACL cases, expected documents survived reranker scoring in `8 / 8` cases, then
thresholding and Top-4 retained `5 / 8`. Exact-section Recall@4 fell from `1.000` to `0.625`.
The `0.10–0.30` threshold sweep did not change target hit on this small slice. The four synthetic
cases remained `4 / 4` across those stages. This points to a real-text ranking/selection weakness,
but does not establish a safe replacement policy.

## Resource limits and decision

The full retrieval-only run completed with Docker memory limit `--memory=2500m`; observed process
RSS was about `2.25 GiB` (`2,353,732 KiB`). The later full generation run completed at a 2.8 GiB
container memory limit, with about `0.64 GiB` host available during generation/judging. On the
30-case diagnostic, batch 16 reached about
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

## Repeated full candidate diagnostic: 2026-10-31

The full `multilingual-compact` run at threshold `0.01` was repeated on the same 132-case dataset
(`04e8b54242c9951607330e39030a6a461f1398c9eab50d4c33e066aacf225f84`). All cases completed without
errors. Target-document hit remained `1.000` (`85/85`), target-section hit `0.981` (`51/52`), and
MIRACL exact-section recall `0.975` (`39/40`). Context Precision was `0.941` (floor `0.975`), and
English Answer Relevance was `0.768` (floor `0.827`); both gates still fail. Faithfulness was
`0.980`, citation support `0.970`, no-answer refusals `6/6`, ACL leaks `0/41`. Reranking took
`1,203.6 s` for 1,980 candidate pairs; the run used about `1.96 GiB` of its `2.73 GiB` container
limit, with roughly `1.0 GiB` host memory available and no OOM event.

The earlier full `0.01` run measured Context Precision `0.922` and English Answer Relevance `0.777`.
The repeated scores vary while leaving both gate decisions unchanged; generation and LLM-judged
metrics should be read as observed run results, not exact deterministic values.

The sanitized per-case artifact is
[`rag_quality_candidate_001_case_diagnostics.json`](rag_quality_candidate_001_case_diagnostics.json).
It contains case IDs, dataset/kind, retrieval ranks, reranker scores, aggregate per-case metrics,
and boolean safety outcomes; it omits questions, expected/generated answers, context text, identities,
and exception text. Its source-level slices show Context Precision `0.996` on synthetic-golden
(`n=45`) versus `0.878` on MIRACL (`n=40`). The average is `1.000` for cases returning one or two
contexts (`n=35`), `0.827` for three (`n=14`), and `0.927` for four (`n=36`). These are correlations
across different queries, not a controlled Top-K comparison. The current report also lacks per-rank
judge verdicts, so reranker scores cannot yet identify which individual contexts to remove. The next
controlled experiment should persist only per-rank relevance booleans and compare context Top-K on
the same cases before any retrieval behavior change. Production profile and threshold remain
unchanged.

## Instrumented case rerun and Top-K simulation: 2026-10-31

The evaluator now stores one `context_relevance_by_rank` boolean per returned chunk plus
`answer_is_refusal`, without writing any question, answer, or context text. A full same-config rerun
completed all 132 cases; one case error left 84/85 positive context-precision observations. ACL
leaks remained `0/41`, no-answer refusals `6/6`, target-document hit `1.000`, target-section hit
`0.981`, Context Precision `0.940`, and English Answer Relevance `0.770`. Both quality gates still
fail, and this generation/judge run is excluded from answer-quality comparisons because one case
errored.

Using the stored per-rank labels, Top-2 gives Context Precision `0.952` versus `0.940` at Top-4,
while retaining `91.3%` of judge-relevant Top-4 contexts and `49/52` exact target sections versus
`51/52` at Top-4. Raising the score threshold to `0.05` or `0.10` lowers Context Precision to
`0.932` or `0.930` and exact section recall to `47/52` or `46/52` in this same run. The full sweep
and calculation definitions are in [context selection Top-K diagnostic](rag_quality_context_selection_topk.md).

This supports a Top-2 hypothesis for a further isolated end-to-end test, but does not establish a
production change: Context Precision still misses its `0.975` floor, target-document hit@2 is not
present in the safe artifact, and generation/citation metrics cannot be recomputed by truncating the
already-generated Top-4 answer. The run also had one case error, so its Case errors gate failed;
Top-K context calculations use the 84 positive cases with successful context-judge results.
Production defaults remain unchanged.

## Corrected refusal classifier and paired end-to-end Top-2: 2026-11-01

The refusal classifier now counts only the exact localized standard refusal as an exact refusal;
embedded refusal language is reported separately. A corrected full Top-4 baseline and a full Top-2
run then completed on the same 132-case dataset (`85` positive, `6` no-answer, `41` ACL-negative),
with the same SHA-256 and all settings held fixed except `rerank_top_k`. Both runs had zero case
errors, zero ACL leaks, and `6/6` correct no-answer refusals.

| Metric | Top-4 | Top-2 |
| --- | ---: | ---: |
| Target document | `85/85` | `84/85` |
| Exact target section | `51/52` | `48/52` |
| Context Precision | `0.952` | `0.959` |
| Faithfulness | `0.974` | `0.952` |
| Citation support | `0.931` | `0.932` |
| English Answer Relevance | `0.798` | `0.743` |
| Russian Answer Relevance | `0.597` | `0.581` |

Top-2 reduces the average returned context count from `2.79` to `1.78`, while reranking still scores
all `1,980` pairs and takes `1,243.27 s` on CPU. Context Precision improves by `0.007` but remains
below the `0.975` gate; English Answer Relevance remains below `0.827` in both runs. The loss in
document/section recall and lower answer metrics do not justify Top-2 as a default. Keep production
Top-4 and threshold `0.01` unchanged. See the [full sanitized comparison](rag_quality_corrected_classifier_comparison.md)
and the [product evaluation record](../docs/product/evaluation.md).

Both artifacts contain only safe per-case diagnostics; prompts, answers and passage text were not
persisted. Evaluation used an isolated temporary PostgreSQL/pgvector database with the RLS session
role. Object-storage writes were stubbed only for seeding this disposable database; no user
S3/MinIO or public demo was used. LLM generation and judges are stochastic, so answer-metric deltas
are run observations and should not be attributed solely to Top-K without repeated runs.

The case-level follow-up found that exact positive-case refusals account for all English gate loss:
without three refused English cases the Top-4 non-refusal answer-relevance mean is `0.847` (gate
`0.827`), while the full score stays `0.799`. For MIRACL, target-document hit is `40/40` but judge
relevance drops sharply after rank 1. See the [failure analysis](rag_quality_failure_analysis.md)
for per-rank rates, language-bucket correction, and the evidence still needed before attributing
the Context Precision result to ranking/chunk noise rather than judge mistakes.

The targeted refusal follow-up is documented in
[refusal case analysis](rag_quality_refusal_case_analysis.md). Across two repeats of the 11 prior
positive refusals, the first classified `9/11` as refusals and the second `10/11`. In the latest
replay, five responses were exact refusals, five embedded a refusal phrase in a longer response, and
one was a regular answer. The first replay's same-model rubric called context sufficient in 6 cases,
partial in 1, and insufficient in 4; it considered refusal inappropriate in 7/11. These labels are
provisional, not independent verification, and do not describe the second replay. All 11 latest
cases had nonempty chunks and no ACL leaks; the code path passed chunks into `build_messages`. The
serialized prompt and response text were not retained. Per-rank verdict vectors matched the original
run for `6/11` cases, underscoring run-to-run variability.
