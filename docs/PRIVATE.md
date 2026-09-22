# Private documentation

The **`docs/_private/`** directory is listed in `.gitignore` and is not part of the public repository.

It holds working materials outside the product spec, for example:

- milestone roadmap (`product/milestones.md`)
- tech debt, improvements checklist, repo conventions, ChainWise port map (`engineering/`)
- ops runbooks (`operations/`)
- portfolio / interview notes and sales one-pager (`portfolio/`)
- Cursor restore kit (`AGENTS.md`, `cursor/rules/`) and personal cheatsheet (`DEV-CHEATSHEET.md`)

**Public documentation** is everything else under `docs/` (see [README.md](README.md)): SRS, platform, pipeline, ADRs, API, screenshots.

After cloning, create `docs/_private/` locally or restore it from your own backup. Index when restored: `docs/_private/README.md`.
