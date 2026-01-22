---
name: update-docs
description: Synchronize repository documentation after code or behavior changes; use when asked to update or sync docs, changelog, architecture notes, CLAUDE.md, AGENTS.md, or docs/ pages with recent updates.
---

# Update Docs

## Scope
- Primary files: `CHANGELOG.md`, `docs/architecture.md`, `CLAUDE.md`, `AGENTS.md`.
- Also scan `docs/` for related pages that mention the changed behavior.

## Workflow
1. Identify the recent changes (git diff, touched files, or user summary).
2. Map each change to the affected docs and update those sections.
3. Keep wording concrete: defaults, units, config names, and paths.
4. Update `CHANGELOG.md` with a concise entry describing what changed and why.
5. Cross-check for consistency (names, units, defaults, and terminology).
6. If uncertain about intent or scope, ask a focused question before editing.

## Helpers
- Checklist: `docs/updates/DOC_SYNC_CHECKLIST.md`
- Script: `scripts/check_doc_sync.sh [base]`

## Changelog Rules
- Add to the latest or Unreleased section.
- Include type tag: `feat`, `fix`, `refactor`, or `docs`.
- Note breaking changes explicitly.
- Mention renamed options or unit shifts.

## Style
- Keep lines <= 100 chars.
- Prefer canonical doc sources; avoid duplicating content.
- Use ASCII unless the target file already uses non-ASCII.

## Validation Checklist
- Names and defaults match code.
- Units are consistent across docs.
- References to deprecated options are removed.
