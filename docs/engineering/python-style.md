# Соглашения Python (серверная часть)

Правила относятся к `backend/` (Python 3.12). Проверки: ruff (`E`, `F`, `W`) и mypy.
Форматирование: ruff.

## Область действия

- В **каждом** непустом файле `backend/**/*.py` (включая `tests/`, `worker/` и `alembic/env.py`) в начале должна быть строка документации модуля (достаточно одной строки).
- Обработчики маршрутов FastAPI в `app/api/v1/` могут не иметь строк документации функций: HTTP-контракт задают OpenAPI и `docs/engineering/api.md`.
- Для служб в `app/services/` добавляйте строки документации к функциям, описывающим изоляцию организаций, ACL, квоты, SSO, кэш и аудит, даже если типы данных очевидны.

Клиентская часть (`frontend/`) использует TypeScript; JSDoc необязателен и не требуется для каждого экспортируемого элемента.

## Строки документации в коде

Следуйте [PEP 257](https://peps.python.org/pep-0257/). **Не** используйте форматы Google или NumPy (`Args:`, `Returns:`, `Raises:`). Типы и HTTP-контракты указывайте в аннотациях и схемах Pydantic, а не в строках документации.

### Когда добавлять строку документации

| Расположение | Рекомендация |
| --- | --- |
| **Модуль** | Один короткий абзац: назначение, границы и ссылка на ADR или `docs/`, если правило неочевидно. |
| **Открытая функция или класс** | Однострочное описание в **повелительном наклонении**, если имени и типов недостаточно; особенно для безопасности, изоляции организаций, ACL, кэширования, идемпотентности и поведения при отказе. |
| **Внутренние вспомогательные функции** | Строка документации необязательна; добавляйте локальный комментарий только для сложной логики. |
| **Очевидные операции чтения и записи** | Строка документации не нужна, если назначение ясно из сигнатуры `def get_user(db: Session, user_id: UUID) -> User | None`. |

### Что описывать

- **Изоляция организаций:** берите `organization_id` из сессии или членства; тело запроса не должно задавать организацию.
- **Ролевой доступ:** получайте `allowed_roles` из членства; применяйте SQL-условие `access_roles && allowed_roles` до объединения результатов, повторного ранжирования и передачи контекста модели.
- **Чужая организация:** возвращайте `404`, не подтверждая существование чужого или закрытого документа.
- **Файлы cookie и имя узла:** используйте cookie `dw_*` только для текущего узла (ADR-015); имя узла закрепляет организацию, но не заменяет SQL-фильтр `organization_id`.
- **Кэш:** ключи Redis для ответов модели включают `org_id`, поколение индекса и `allowed_roles` вызывающего; не используйте общий кэш для разных организаций или наборов ролей.

При необходимости добавляйте ссылки на ADR из `docs/engineering/decisions.md` рядом с соответствующим текстом (например, `ADR-015`, `ADR-005`).

### Примеры

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
# ❌ ПЛОХО — повторяет аннотации типов
def cache_key(question: str, allowed_roles: Sequence[str], *, organization_id: UUID) -> str:
    """Build cache key.

    Args:
        question: User question.
        allowed_roles: Roles for ACL.
    Returns:
        Redis key string.
    """

# ✅ ХОРОШО — инвариант описан одной строкой
def cache_key(question: str, allowed_roles: Sequence[str], *, organization_id: UUID) -> str:
    """Redis key: org + index generation + roles hash + question (never body-supplied org)."""
```

Язык: **английский** для строк документации в коде; **русский** для пользовательских и проектных документов в `docs/`.

## Комментарии

Код должен быть понятен сам по себе. Используйте `#` или короткую строку документации только для неочевидных правил предметной области, а не для пересказа каждой строки.

## Связанные документы

- [decisions.md](decisions.md) — архитектурные решения (ADR)
- [tenancy.md](../platform/tenancy.md), [auth.md](../platform/auth.md)
- [retrieval.md](../pipeline/retrieval.md) — порядок гибридного поиска
