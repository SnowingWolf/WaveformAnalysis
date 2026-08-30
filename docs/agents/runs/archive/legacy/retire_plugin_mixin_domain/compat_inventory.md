# compat_inventory

- `task_id`: `retire_plugin_mixin_domain`
- `route`: `retire_compat`
- `workflow_cost`: `strict`
- `inventory_scope`: `Context` plugin registration and dependency orchestration
- `canonical_policy`: `Context.register() is the only public registration API; internal code delegates to ContextPluginDomain`

## compat_items

- `compat_id`: `context_register_plugin_`
  - `kind`: `other`
  - `canonical_form`: `Context.register(*plugins, allow_override=False, require_spec=False)`
  - `legacy_form`: `Context.register_plugin_(plugin, allow_override=False, require_spec=False)`
  - `location`: `waveform_analysis/core/foundation/mixins.py` and repository call sites
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `remove`
  - `risk_level`: `high`
  - `required_gates`:
    - `doc_sync`
    - `doc_anchors`
    - `assess_change_impact`
    - `schema_compat_check`
    - `targeted_context_tests`
  - `migration_note`: User explicitly confirmed direct removal without a facade or deprecation period; all repository call sites migrate to `Context.register()`.
  - `review_decision`: `approved`

- `compat_id`: `plugin_mixin_import_and_inheritance`
  - `kind`: `import_alias`
  - `canonical_form`: `ContextPluginDomain` composed by `Context`
  - `legacy_form`: `PluginMixin` and `waveform_analysis.core.foundation.mixins`
  - `location`: `waveform_analysis/core/foundation/mixins.py`, `Context(PluginMixin)`, import guidance
  - `runtime_surface`: `internal`
  - `delete_action`: `remove`
  - `risk_level`: `medium`
  - `required_gates`:
    - `doc_sync`
    - `doc_anchors`
    - `targeted_context_tests`
  - `migration_note`: The domain keeps the existing registration, validation, dynamic-dependency, and topological-resolution behavior while Context retains the stable `_plugins` mapping.
  - `review_decision`: `approved`
