# Python style (backend)

Applies to `backend/` (Python 3.12). Lint: ruff (`E`, `F`, `W`) + mypy. Format: ruff.

## Scope

- **Every** non-empty `backend/**/*.py` file (including `tests/`, `worker/`, and `alembic/env.py`) opens with a **module** docstring (one line is enough).
- **FastAPI route handlers** in `app/api/v1/` may omit function docstrings; OpenAPI and `docs/engineering/api.md` are the HTTP contract.
- **Services** (`app/services/`): add function docstrings for tenancy, ACL, quotas, SSO, cache, and audit behavior even when types are obvious.

Frontend (`frontend/`) uses TypeScript; JSDoc is optional and not required on every export.

## Docstrings

Follow [PEP 257](https://peps.python.org/pep-0257/). **Do not** use Google or NumPy layouts (`Args:`, `Returns:`, `Raises:`). Types and HTTP contracts belong in annotations and Pydantic schemas, not in docstrings.

### When to write one

| Location | Guidance |
| --- | --- |
| **Module** | One short paragraph: responsibility, boundaries, link to ADR or `docs/` when the rule is non-obvious. |
| **Public function / class** | One-line summary in **imperative mood** when the name and types are not enough — especially security, tenancy, ACL, caching, idempotency, or fail-open behavior. |
| **Private helpers** | Optional; prefer a local comment only if the logic is tricky. |
| **Obvious CRUD** | Skip the docstring if `def get_user(db: Session, user_id: UUID) -> User | None` is self-explanatory. |

### What to emphasize

- **Tenancy:** `organization_id` from session/membership, never from the request body as authority.
- **RBAC:** `allowed_roles` from membership; SQL `access_roles && allowed_roles` before fusion, rerank, or LLM.
- **Cross-tenant:** prefer `404` over confirming a foreign or restricted document exists.
- **Cookies / host:** host-only `dw_*` cookies (ADR-015); hostname pins org but does not replace SQL `organization_id`.
- **Cache:** LLM Redis keys include `org_id`, index generation, and caller `allowed_roles` — never share across tenants or role sets.

Reference ADRs in `docs/engineering/decisions.md` inline when it helps reviewers (e.g. `ADR-015`, `ADR-005`).

### Examples

```python
"""Postgres RLS for corpus tables (`documents`, `document_chunks`)."""

def chunk_acl_filter(allowed_roles: list[str]):
    """SQL overlap predicate for document_chunks.access_roles (current membership only)."""

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Principal:
    """Resolve session user, enforce host pin and SSO, bind RLS for the current org."""

def create_access_token(subject: str, *, org_id: str | None = None, sso: bool = False) -> str:
    """Access JWT: identity + current org. Role comes from membership, not the token."""
```

```python
# ❌ BAD — duplicates type hints
def cache_key(question: str, allowed_roles: Sequence[str], *, organization_id: UUID) -> str:
    """Build cache key.

    Args:
        question: User question.
        allowed_roles: Roles for ACL.
    Returns:
        Redis key string.
    """

# ✅ GOOD — invariant in one line
def cache_key(question: str, allowed_roles: Sequence[str], *, organization_id: UUID) -> str:
    """Redis key: org + index generation + roles hash + question (never body-supplied org)."""
```

Language: **English** in code docstrings and in public `docs/` product specs.

## Comments

Code should be mostly self-explanatory. Use `#` or a short docstring only for non-obvious business rules, not to narrate each statement.

## Related docs

- [decisions.md](decisions.md) — ADRs
- [tenancy.md](../platform/tenancy.md), [auth.md](../platform/auth.md)
- [retrieval.md](../pipeline/retrieval.md) — hybrid pipeline order
