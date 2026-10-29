# API документов

Все routes ограничены текущей organization. `admin` и `manager` управляют базой знаний;
backend повторно проверяет права независимо от UI.

## Загрузка

```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data
```

Поля: `file` (PDF/DOCX) и `access_roles` (повторяющееся поле или JSON array).
Успех — `201`, документ в `pending`; Celery обрабатывает его асинхронно.

| Условие | Результат |
| --- | --- |
| Файл больше `UPLOAD_MAX_BYTES` (default 50 MiB) | `413` |
| Неподдерживаемый формат | `400` |
| Такой SHA-256 уже загружен в этой org | `409 resource.conflict`, без раскрытия существующей записи |
| Превышена page quota | `402 billing.payment_required`, Celery не вызывается |

Для PDF квота считается по страницам; для DOCX — по логическим разделам. Parsing не выполняется внутри upload handler.

## Список и статус

```http
GET /api/v1/documents?limit=20&offset=0&status=ready
GET /api/v1/documents/{id}/status
```

`limit`: 1–100 (default 20); `offset`: от 0. Возвращаются только документы текущей org, разрешённые текущей роли.
Status включает `pending | processing | ready | failed`, `stage` и безопасный `last_error` для failed.

## Изменение доступа

```http
PATCH /api/v1/documents/{id}
Content-Type: application/json
```

Тело: `{ "access_roles": ["hr", "admin"] }`. В одной транзакции обновляются документ и все его chunks;
переиндексация не требуется. Пустой список — `422`; отсутствующая запись — `404 resource.not_found`.

## Удаление и просмотр оригинала

```http
DELETE /api/v1/documents/{id}
GET /api/v1/documents/{id}/raw
```

`DELETE` возвращает `204`, удаляет строки документа/chunks и записывает `storage_deletions` outbox row
в той же транзакции. Worker повторяет удаление private S3 object; ошибки остаются в очереди.

`raw` возвращает PDF или DOCX только после tenant/ACL проверки. Постоянная публичная ссылка на объект storage не выдаётся.

Ошибки и общий формат ответов: [API overview](overview.md). Ingestion flow: [pipeline/ingestion.md](../../pipeline/ingestion.md).
