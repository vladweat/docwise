# README screenshots

PNG set for the root [README](../../../README.md) gallery.

| File | Scene |
| --- | --- |
| `01-chat-citation.png` | Employee chat: answer + citation chips |
| `02-pdf-highlight.png` | Same flow: PDF pane with snippet highlight |
| `03-acl-refuse.png` | Employee: L3 salary question → grounded refuse (no HR doc) |
| `04-inspect-pipeline.png` | Org-admin `/inspect` → stages table |

## Regenerate

From repo root, with `make up` + `make demo` and an LLM key in `.env`:

```bash
cd scripts && npm init -y && npm install playwright@1.51.1 && npx playwright install chromium
cd .. && node scripts/capture-portfolio-screenshots.mjs
```

Manual clicks follow the ACL walkthrough in the root README.
