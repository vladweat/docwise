# Agent notes (Docwise)

Enterprise RAG workspace (repo `docwise`).

Start here: `docs/product/srs.md` (product), `docs/product/milestones.md` (roadmap checkboxes), `docs/engineering/decisions.md` (ADRs vs draft TZ), `docs/README.md` (index). Cursor rules in `.cursor/rules/` restate the same invariants. Workspace-only notes (port map, portfolio levels, career KB) live under `docs/_private/` when present locally — not tracked on GitHub.

Non-negotiables:

1. Two-layer access: SQL `organization_id = current_org` ([tenancy.md](docs/platform/tenancy.md)) **then** `document_chunks.access_roles` (and the same on file download). Never prompt-filter unauthorized or cross-tenant chunks.
2. No naive character-split RAG. Chunks stay on one page/section; inject a meta header before embedding.
3. Hybrid search: pgvector + Postgres FTS with org + ACL → RRF (`k=60`) → cross-encoder rerank → Top-4 → grounded LLM. Do **not** `SELECT` all chunks into RAM BM25 (one-artifact in-memory sparse is out of scope).
4. SSE JSON envelopes: `citations` → `token` → `meta` → `[DONE]`. If context is insufficient, refuse. Every fact needs `{document, page}`.

Keep sync SQLAlchemy. UUID PKs (not sequential integer ids). Do not port solc, Slither, or AST semantic splitters. When you change an API or RAG/ACL/tenancy invariant, update `docs/` and the matching `.cursor/rules/` file in the same change.

Plan entitlements, billing, SSO, and hostname pin org — they never replace SQL `organization_id` + `access_roles`. Canonical: [docs/platform/billing.md](docs/platform/billing.md), ADR-013–015 in [decisions.md](docs/engineering/decisions.md).
