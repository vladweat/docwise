# Agent notes (Docwise)

Enterprise RAG workspace (repo `docwise`), adapted from sibling `../chainwise`.

Start here: `docs/srs.md` (product), `docs/decisions.md` (TZ vs ChainWise), `docs/reuse-from-chainwise.md` (file map). Cursor rules in `.cursor/rules/` restates the same invariants.

Non-negotiables:

1. RBAC is a SQL filter on `document_chunks.access_roles` (and the same ACL on file download). Never “prompt-filter” unauthorized chunks.
2. No naive character-split RAG. Chunks stay on one page/section; inject a meta header before embedding.
3. Hybrid search: pgvector + FTS/BM25 with ACL → RRF (`k=60`) → cross-encoder rerank → Top-4 → grounded LLM. Do **not** `SELECT` all chunks into RAM BM25 (that is ChainWise’s one-contract path).
4. SSE JSON envelopes like ChainWise: `citations` → `token` → `meta` → `[DONE]`. If context is insufficient, refuse. Every fact needs `{document, page}`.

Keep sync SQLAlchemy. UUID PKs (not ChainWise integer ids). Do not port solc, Slither, or `semantic_splitter.py`. When you change an API or RAG/ACL invariant, update `docs/` and the matching `.cursor/rules/` file in the same change.
