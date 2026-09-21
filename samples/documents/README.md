# Sample documents

Готовые файлы для ручной загрузки в KB или просмотра локально.  
Сгенерировать заново (нужен `backend/.venv` с `pymupdf`, `python-docx`):

```bash
cd /home/lzvw/projects/docwise
backend/.venv/bin/python samples/export-sample-documents.py
```

## Демо-корпус (12 PDF)

Те же тексты, что даёт `eval/seed_demo.py`, но **без** записи в MinIO/Postgres.

| Файл | Рекомендуемый `access_roles` | Пример вопроса |
|------|------------------------------|----------------|
| [Employee-Handbook.pdf](./Employee-Handbook.pdf) | `all` | What are the core working hours at Docwise? |
| [Leave-Policy.pdf](./Leave-Policy.pdf) | `all` | How many vacation days per year? |
| [Expense-Policy.pdf](./Expense-Policy.pdf) | `all` | When is a manager signature required for expenses? |
| [Engineering-Onboarding.pdf](./Engineering-Onboarding.pdf) | `all` | What is the default Python version for new services? |
| [Travel-Policy.pdf](./Travel-Policy.pdf) | `all` | What is the domestic hotel cap? |
| [IT-Access-Checklist.pdf](./IT-Access-Checklist.pdf) | `all` | What must be installed on day one? |
| [Security-Runbook.pdf](./Security-Runbook.pdf) | `all` | When is a postmortem due after an incident? |
| [Operations-Handbook.pdf](./Operations-Handbook.pdf) | `all` | Who owns requests during business hours? |
| [HR-Compensation.pdf](./HR-Compensation.pdf) | `hr` | What is the L3 individual contributor salary band in USD? |
| [Recruiting-FAQ.pdf](./Recruiting-FAQ.pdf) | `hr` | How soon must interview feedback be entered? |
| [Finance-Q4-Memo.pdf](./Finance-Q4-Memo.pdf) | `finance` | What is the Q4 operating margin target? |
| [People-Compendium.pdf](./People-Compendium.pdf) | `hr` | (длинный HR-only текст — любой вопрос по уникальной фразе) |

## Тесты парсера

| Файл | Назначение |
|------|------------|
| [Parser-Policy-Test.pdf](./Parser-Policy-Test.pdf) | 2 страницы, заголовки + таблица (unit-тесты chunker) |
| [Travel-Policy-Test.docx](./Travel-Policy-Test.docx) | DOCX: разделы + таблица L3 / 150 USD |

**DOCX — примеры вопросов:** travel cap 150 USD per night; receipts within 30 days; L3 limit in the table.

## Пути на диске

Корень каталога:

`/home/lzvw/projects/docwise/samples/documents/`

В UI Docwise файлы **не** раздаются по URL — загрузите через **База знаний → Загрузить документ** или перетащите в модалку upload.
