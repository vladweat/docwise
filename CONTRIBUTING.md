# Участие в разработке

## Подготовка

Следуйте [локальному запуску](docs/development/getting-started.md). Перед изменениями
прочитайте [архитектуру](docs/product/architecture.md) и repository-specific
[AGENTS.md](AGENTS.md).

## Границы изменений

- Не принимайте `organization_id`, `access_roles` или role из request body как полномочие.
- Любой corpus query фильтруйте по tenant и ACL до RRF/rerank/LLM.
- ORM/schema changes сопровождайте новой Alembic migration; старые migration files не меняйте.
- API/schema/config changes синхронизируйте с документацией.
- Не добавляйте секреты, `.env`, dumps и customer documents.

## Проверки

```bash
make lint
make test-smoke
make test
make typecheck
make test-frontend
```

Выберите проверки пропорционально изменению, но в PR укажите реально выполненные команды.
Изменения retrieval, chunking, embeddings, FTS, rerank или prompt требуют процедуры из
[evaluation.md](docs/product/evaluation.md). Live eval не входит в обычную CI и требует
инфраструктуру/ключ LLM.

## Pull request

- Делайте один логический change на commit.
- Объясните причину и влияние, а не только список файлов.
- Укажите migration, config, security и rollback impact.
- Не заявляйте успешно пройденную проверку, если она не запускалась.
- Для документации проверяйте относительные ссылки, пути, команды и утверждения по коду.
