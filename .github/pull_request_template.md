## Summary

<!-- What changed and why -->

## Test plan

- [ ] `make test-smoke` (or `make test` for broader changes)

## RAG / retrieval

See [docs/product/evaluation.md](../docs/product/evaluation.md), section “Release discipline”.

- [ ] I did **not** change `backend/app/services/retrieval/`, `backend/app/services/chat/` prompts, chunking/ingestion embed path, or fusion/rerank/FTS thresholds
- [ ] I changed retrieval only → ran `make eval-retrieval` (`OPENAI_API_KEY` in `.env`)
- [ ] I changed fusion, rerank, FTS, chunking, embeddings, or rerank threshold → ran `make eval` and updated `reports/rag_benchmark.md`
- [ ] I changed chat system prompt, refusal text, or answer shaping → ran `make eval` (check Answer Relevance in per-question table)
- [ ] If metrics moved materially → updated the date/summary in `docs/product/nfr.md` § RAG quality

## Tenancy / ACL

- [ ] No retrieval or document access without SQL `organization_id` + `access_roles` (no prompt-only filtering)
