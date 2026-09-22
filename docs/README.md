# Docwise documentation

Public product and engineering specs. Source of truth: [srs.md](product/srs.md), [decisions.md](engineering/decisions.md), [api.md](engineering/api.md). OpenAPI (`/docs`) is disabled in `production`.

Internal materials (roadmap, tech debt, deploy notes) live in `docs/_private/` ([PRIVATE.md](PRIVATE.md), not in Git).

## Catalog

| Directory | Contents |
| --- | --- |
| `product/` | SRS, architecture, NFR, frontend, evaluation |
| `platform/` | tenancy, auth, billing, data-model |
| `pipeline/` | ingestion, retrieval |
| `engineering/` | HTTP contract, ADRs, Python docstring conventions |
| `portfolio/screenshots/` | PNGs for the root README |

## Where to start

1. [SRS](product/srs.md) — goals, functional requirements, acceptance criteria.
2. [Architecture](product/architecture.md) — components, chat, inspect.
3. [Tenancy](platform/tenancy.md), [Auth](platform/auth.md), [Data model](platform/data-model.md), [Billing](platform/billing.md).
4. [Ingestion](pipeline/ingestion.md), [Retrieval](pipeline/retrieval.md).
5. [API](engineering/api.md), [Python style](engineering/python-style.md), [Frontend](product/frontend.md).
6. [NFR](product/nfr.md), [Evaluation](product/evaluation.md).

## Invariants

- ACL in SQL (`organization_id` + `access_roles`) **before** fusion, rerank, and LLM.
- Plan, SSO, and hostname do not replace `org_id`.
- Cite `{document, page}` or refuse; no naive character-split and no scrolling the full corpus into RAM.
