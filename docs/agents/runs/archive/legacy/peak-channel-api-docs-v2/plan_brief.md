# plan_brief

- task_id: peak-channel-api-docs-v2
- route: retire_compat
- workflow_cost: strict
- lifecycle_profile: compat_retirement_review
- risk_level: medium
- scope_in: PeakChannelAccessor API deletion, position reconstruction caller migration, tests, examples, documentation source and generated site input
- scope_out: plugin output dtype and PeakletChannelsPlugin aggregation implementation
- required_gates: compat_inventory_ready, deletion_scope_confirmed, targeted tests, ruff, black, doc_sync, doc_anchors, impact_assessed_if_needed, schema_checked_if_needed
- executor_role: executor.config
- blocking_assumptions: user JSON confirms immediate removal of the listed public API and fallback

## retire_compat Notes

- compat_inventory_required: true
- compat_inventory_path: docs/agents/protocol/artifacts/peak_channel_api_docs_v2_compat_inventory.md
- deletion_policy: balanced
- public_surface_confirmation_required: true
- high_risk_items_redirected: false
