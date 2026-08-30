# compat_inventory

- `task_id`: `architecture_docs_refresh_20260730`
- `route`: `retire_compat`
- `inventory_scope`: Retire the published `architecture/data-access.html` documentation route and its Markdown source while replacing its active in-repository links with focused architecture references.
- `canonical_policy`: `entry-only compat; internal code uses canonical form only`

## compat_items
- `compat_id`: `data-access-markdown-source`
  - `kind`: `docs_redirect`
  - `canonical_form`: Focused architecture sources for Plugin DAG/Lineage/cache, records-backed data boundaries, and specialized runtime guides.
  - `legacy_form`: `docs/features/context/DATA_ACCESS.md`
  - `location`: `docs/features/context/DATA_ACCESS.md` and active Markdown references.
  - `runtime_surface`: `docs_only`
  - `delete_action`: `remove`
  - `risk_level`: `medium`
  - `required_gates`:
    - `deletion_scope_confirmed`
    - `doc_sync`
    - `doc_anchors`
    - `site_web_generation`
  - `migration_note`: User explicitly approved deletion. Migrate active references by subject; do not rewrite historical protocol artifacts.
  - `review_decision`: `approved`

- `compat_id`: `architecture-data-access-route`
  - `kind`: `route_alias`
  - `canonical_form`: `architecture/plugin-dag-lineage-cache.html`, `architecture/records-wave-pool.html`, and specialized feature pages selected by the migrated source links.
  - `legacy_form`: `architecture/data-access.html`
  - `location`: `docs/site-guides.yaml`, generated-site tests, search/navigation expectations, and active Markdown links.
  - `runtime_surface`: `docs_only`
  - `delete_action`: `remove`
  - `risk_level`: `medium`
  - `required_gates`:
    - `deletion_scope_confirmed`
    - `doc_sync`
    - `doc_anchors`
    - `site_web_generation`
  - `migration_note`: User explicitly selected deletion rather than a redirect. The generated site must no longer publish this path.
  - `review_decision`: `approved`

- `compat_id`: `generated-user-guide-section`
  - `kind`: `docs_redirect`
  - `canonical_form`: Repository Markdown sources remain available under `docs/user-guide/`, `docs/features/context/`, and `docs/plugins/tutorials/`.
  - `legacy_form`: Generated HTML navigation section `用户指南`.
  - `location`: `docs/site-guides.yaml`, generated sidebar, homepage, and search index.
  - `runtime_surface`: `docs_only`
  - `delete_action`: `remove`
  - `risk_level`: `medium`
  - `required_gates`:
    - `deletion_scope_confirmed`
    - `focused_documentation_tests`
    - `site_web_generation`
  - `migration_note`: User explicitly requested deletion of the generated section. Preserve all source Markdown and do not publish replacement redirects.
  - `review_decision`: `approved`

- `compat_id`: `generated-user-guide-routes`
  - `kind`: `route_alias`
  - `canonical_form`: No generated HTML replacement; source Markdown remains in the repository.
  - `legacy_form`: `guides/index.html`, `guides/quickstart.html`, `guides/examples.html`, `guides/configuration.html`, `guides/plugin-authoring.html`, and `guides/lineage.html`.
  - `location`: `docs/site-guides.yaml`, generated files, search index, and HTTP route tests.
  - `runtime_surface`: `docs_only`
  - `delete_action`: `remove`
  - `risk_level`: `medium`
  - `required_gates`:
    - `deletion_scope_confirmed`
    - `focused_documentation_tests`
    - `site_web_generation`
  - `migration_note`: User explicitly approved route removal by requesting deletion of the entire generated section; no redirects are added.
  - `review_decision`: `approved`
