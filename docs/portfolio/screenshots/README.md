# README screenshots

PNG set for the root [README](../../README.md) gallery.

| File | Scene |
| --- | --- |
| `01-chat-citation.png` | Employee chat: answer + citation chips |
| `02-pdf-highlight.png` | Same flow: PDF pane with snippet highlight |
| `03-acl-refuse.png` | Employee: L3 salary question → grounded refuse (no HR doc) |
| `04-inspect-pipeline.png` | Org-admin `/inspect` → «Прогнать», stages table |

## Regenerate

**Automated (Playwright):** from repo root, with `make up` + `make demo` and LLM key in `.env`:

```bash
cd scripts && npm init -y && npm install playwright@1.51.1 && npx playwright install chromium
cd .. && node scripts/capture-portfolio-screenshots.mjs
```

**Manual:** same clicks as the demo walkthrough in README. On `/inspect`, use the **working hours** question (salary leaves `reranked` empty for admin without `hr`).

## Walkthrough script

Scene order and spoken beats: [interview walkthrough](../../../docs/_private/portfolio/interview-walkthrough.md) (private; same steps as README ACL demo).

## Status

- [x] Gallery in root README
- [x] Files `01`–`04` present
- [x] Synced with README + interview walkthrough (**2026-09-22**; refresh PNGs after major UI changes)
