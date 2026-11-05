# Образцы документов

Готовые файлы для ручной загрузки в базу знаний или локального просмотра.
Для повторной генерации нужен `backend/.venv` с установленными `pymupdf` и `python-docx`:

```bash
# запуск из корня репозитория
backend/.venv/bin/python samples/export-sample-documents.py
```

## Набор для ручной проверки (12 PDF)

Те же тексты, что создаёт `eval/seed_demo.py`, но **без** записи в MinIO и PostgreSQL.

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
| [People-Compendium.pdf](./People-Compendium.pdf) | `hr` | (длинный закрытый HR-текст — вопрос по любой уникальной фразе) |

## Проверка извлечения текста

| Файл | Что проверяется |
|------|-----------------|
| [Parser-Policy-Test.pdf](./Parser-Policy-Test.pdf) | 2 страницы, заголовки и таблица (модульные проверки разбиения на фрагменты) |
| [Travel-Policy-Test.docx](./Travel-Policy-Test.docx) | DOCX: разделы и таблица L3 / 150 USD |

**Примеры вопросов по DOCX:** лимит отеля 150 USD за ночь; чеки в течение 30 дней; ограничение L3 из таблицы.

## Путь в репозитории

Каталог: `samples/documents/`.

Интерфейс Docwise не раздаёт файлы по URL. Загрузите документ через **База знаний → Загрузить документ** или перетащите его в окно загрузки.
