# Docwise documentation

Public product and engineering specs (English). Source of truth: [srs.md](product/srs.md), [decisions.md](engineering/decisions.md), [api.md](engineering/api.md). OpenAPI (`/docs`) is disabled in `production`.

Internal materials (roadmap, tech debt, ops runbooks, interview notes) live in `docs/_private/` ([PRIVATE.md](PRIVATE.md), not in Git).

## Catalog

| Directory | Contents |
| --- | --- |
| `product/` | SRS, architecture, NFR, frontend, evaluation |
| `platform/` | tenancy, auth, billing, data-model, data-retention |
| `pipeline/` | ingestion, retrieval |
| `engineering/` | HTTP contract, ADRs, Python docstring conventions |
| `portfolio/screenshots/` | PNGs for the root README |

## Where to start

1. [SRS](product/srs.md) — goals, functional requirements, acceptance criteria.
2. [Architecture](product/architecture.md) — components, upload / chat / inspect.
3. [Tenancy](platform/tenancy.md), [Auth](platform/auth.md), [Data model](platform/data-model.md), [Data retention](platform/data-retention.md), [Billing](platform/billing.md).
4. [Ingestion](pipeline/ingestion.md), [Retrieval](pipeline/retrieval.md).
5. [API](engineering/api.md), [Python style](engineering/python-style.md), [Frontend](product/frontend.md).
6. [NFR](product/nfr.md), [Evaluation](product/evaluation.md).

Invariants (org isolation, SQL ACL before LLM, cite-or-refuse): see [tenancy.md](platform/tenancy.md) and [retrieval.md](pipeline/retrieval.md).
