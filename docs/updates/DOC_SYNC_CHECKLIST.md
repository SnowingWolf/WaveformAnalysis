# Doc Sync Checklist

Use this checklist to keep documentation consistent with recent changes.

## 1) Identify Recent Changes
- Review `git diff --stat` and `git diff --name-status`.
- Note new, renamed, or removed options, defaults, units, or file paths.
- Note new/removed modules or APIs.

## 2) Update Primary Docs
- `CHANGELOG.md`: add an entry for behavior or config changes.
- `docs/architecture/ARCHITECTURE.md`: update system-level defaults or flow.
- `docs/features/core/*`: update core behaviors and defaults.
- `docs/features/plugin/*`: update plugin options and dtypes.
- `docs/features/context/*`: update query defaults and examples.
- `docs/user-guide/*`: update user-facing examples and quickstart.
- `CLAUDE.md` and `AGENTS.md`: update internal guidance.

## 3) Check Units and Defaults
- Confirm each time field and unit (ns vs ps) is consistent.
- Confirm any threshold or window options match code defaults.
- Confirm any renamed options are removed from docs.

## 4) Check Examples
- Examples compile with current API (imports, option names, parameters).
- Defaults used in examples match current defaults.

## 5) Final Consistency Pass
- Search for deprecated names (use `rg`).
- Confirm docs reference the canonical module paths.

## Optional Script
- Run: `scripts/check_doc_sync.sh [base]`
  - `base` defaults to `HEAD`
  - Shows changed code vs doc files to help spot gaps
