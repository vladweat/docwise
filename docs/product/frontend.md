# Frontend: UI/UX

Stack: Next.js 15 App Router, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui (Radix), PDF: `pdfjs-dist`. State: TanStack Query + Zustand. Theme: dark UI (single palette).

Routes находятся в `frontend/src/app/` — RSC (`metadata` + islands). Feature interactivity
and stores — `frontend/src/features/{chat,documents,settings,auth,inspect}`. Shared HTTP —
`frontend/src/lib/api/`. Primitives — `frontend/src/components/ui`.

UI base — shadcn + `lib/api.ts`, chat, auth. PDF viewer instead of code viewer; citations `Doc.pdf (page N)` or DOCX section. SSE reader: events `citations | token | meta | error | done`. Assistant replies support `+1` / `-1` feedback (`POST /chat/feedback`) when `message_id` is known.

## Routes

| Path | Screen |
| --- | --- |
| `/login` | Login: demo (three buttons) on top; Google/SSO collapsed |
| `/` | Guest: marketing welcome. Authenticated: same split-screen chat as `/chat` |
| `/chat` | Split-screen chat (new session) |
| `/chat/[sessionId]` | Specific session |
| `/documents` | Knowledge Base admin |
| `/inspect` | Org-admin: dense / FTS / RRF / reranked (`ENABLE_SEARCH_INSPECT`) |
| `/settings` | Org-admin: team/invites, plan, usage, SSO, domain |

## Main chat screen

Three columns on wide screens:

- **Sessions (left):** fixed width, can be **fully hidden**. Narrow button on the left restores the list. State — `localStorage` (`dw-sessions-pane-open`). Session delete — with confirmation; API does not return other users’ sessions.
- **Chat (center):** message list and input. Minimum width ~440px: splitter does not crush chat into a narrow column; when space is tight PDF shrinks, not chat.
- **PDF (right, ~55% remainder):** embedded viewer, `GET /api/v1/documents/{id}/raw`. Can be **fully hidden** (header button / double-click splitter). Footnote click reopens PDF. State — `dw-pdf-pane-open`.

Footnotes — interactive tags like `📄 Expense_Policy.pdf (page 4)`, not raw `[^4]`. Stream tokens without waiting for full answer. On narrow screens — separate PDF screen with “Back to chat”.

On footnote click:

1. If another file is open — load the required one.
2. Go to `page`.
3. Soft-highlight block (text/bbox from citation), scroll into view.

While PDF loads, do not block reading the answer. Empty right state: placeholder “Select a citation to open the source”.

SSE: render citation chips first, then grow answer markdown. After `meta.message_id`, show thumbs up/down on the assistant bubble (own messages only). Chat error codes — toast/banner, no full-page break.

## Knowledge Base admin

Table: title, size, pages, access tags, status (`pending` / `processing` / `ready` / `failed`). Failed — show `last_error`.

Upload: drag-and-drop modal, role selection (`HR`, `Finance`, `General` / `all` etc. — mapped to `access_roles`). After upload — poll `GET .../status` until terminal status; status includes `stage`: `parse` → `chunk` → `embed`.

Upload and delete — confirm where needed; manage KB: `admin` or `manager` of current org (`canManageKnowledgeBase`). Changing `access_roles` after upload — Access column dialog → `PATCH /api/v1/documents/{id}` (manager/admin); tags copy to chunks of the same org. List does not show documents outside ACL or current org.

Header shows current org name. Org-admin invites live on `/settings` (Team), not on `/documents`. Org switch does not send `organization_id` in chat body. Do not substitute another company’s id on upload.

`/settings` (org-admin): team roster and invites; current plan and usage; with `BILLING_PROVIDER=dev` — **Dev billing** badge and plan change / past_due / cancel. Employee on `402` for upload/chat — toast “organization quota exceeded”, no billing panel. SSO: IdP metadata and `sso_enforced`. Domain: hostname and verify status. Do not send `organization_id` in these forms as authority.

Logout / login / user switch resets TanStack Query and chat Zustand (do not leave previous account’s sessions on screen). Do not restore `?next=/chat/:id` after login — session id belongs to one user.

## States and accessibility

- Empty chat: hint about ACL and citations; in `Demo` org — employee vs HR hint. PDF snippet highlight on citation click.
- Quota `402` — toast “organization quota exceeded”. Ingest `failed` — `last_error` in table. `/raw` 404 — “Document unavailable”, no foreign filename.
- No rights on cited file (should not happen with correct ACL) — message without leaking another document’s title if it was not in the answer.
- Keyboard: focus footnotes, Enter opens page.
- PDF highlight contrast readable on the dark UI (amber overlay on white PDF canvas).

## UX prohibitions

- Do not render “sources” that were not in the `citations` event.
- Do not embed public MinIO URL in `<iframe>`.
- Do not send `org_id` / `access_roles` in chat body as “filter”.
- Do not treat custom Host as sufficient ACL without cookie session.
- Do not hide model refusal “no information in documents” behind spinner or automatic retry without user action.
