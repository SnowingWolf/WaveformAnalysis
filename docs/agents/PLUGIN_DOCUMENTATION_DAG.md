# Plugin Documentation DAG

`waveform_analysis.documentation` turns plugin documentation analysis into a
node-by-node, evidence-backed protocol. It does not execute plugins, call
`Context.get_data()`, read run data, or select an external model.

## Resources

- DAG definition: `waveform_analysis/documentation/dags/plugin_documentation.yaml`
- Artifact contracts: `waveform_analysis/documentation/schemas/`
- Agent-node prompts: `waveform_analysis/documentation/prompts/`
- Runtime: `DocumentationOrchestrator`

## Execution Model

The orchestrator builds one `NodeExecutionRequest` for the current node. A
caller supplies the deterministic executor or an external `agent_runner`, then
submits one `NodeExecutionResult`. `execute_deterministic_node()` and
`execute_agent_node()` each execute exactly one matching node; neither has a
default implementation that can invoke plugin compute or access run data. The
orchestrator validates the envelope, artifact, and node acceptance rules,
persists the result when configured, and chooses the next node from the DAG
transition table.

```python
from waveform_analysis.documentation import DocumentationOrchestrator

orchestrator = DocumentationOrchestrator()
state = orchestrator.new_state("hit_merged", repository_root=".")
request = orchestrator.build_request(state)

# Run exactly request.node_id with the selected external agent.
result = external_agent.run_structured(request)
state = orchestrator.accept_result(state, result)
```

`recover_semantics` and the other agent nodes receive only their declared input
artifacts. A `missing_evidence` result routes back to `collect_context`; it must
name the exact evidence needed instead of compensating by inference.

The acceptance rules are executable: semantic decision rules and processing
steps require evidence; anchor-copied and cluster-derived fields are kept
separate; every reported ambiguity identifies affected documentation sections;
and a passing verification report must have zero contradicted claims,
unsupported critical claims, and blocking ambiguities. `generate_agent_doc`
is rejected while the preceding ambiguity report contains a blocking item.

## Publication

`publish()` refuses to write an AgentDoc until
`verification_report.passed == true`. It writes through a temporary sibling file
and replaces the final YAML atomically, preserving the existing document if
serialization fails.

Published files live in `waveform_analysis/documentation/agent_docs/`. At
runtime, `PluginDocGenerator` reads them before the plugin-class `agent_doc`.
It uses a published document only when its schema, plugin name, plugin version,
and SHA-256 source fingerprint all match the registered plugin. A missing,
invalid, or stale file falls back to the source `agent_doc`; runtime Help never
runs the DAG, invokes a model, executes plugin compute, or reads run data.

## Author Workflow

Source `agent_doc` remains the readable fallback layer. A verified published
YAML is the preferred narrative layer, but it only overlays the YAML fields
that are present (`summary`/`overview`, `steps`, `edge_cases`, and
`operational_notes`). Plugin configuration, output schema, dependencies, and
runtime topology always come from the currently registered plugin.

For an algorithm or contract update: update the source `agent_doc` and focused
tests, run the documentation DAG without executing plugin data, review every
agent-node result, then publish only its passed terminal candidate:

```bash
waveform-docs agent-doc publish --plugin <provides>
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
```

The default state/artifact store is `.waveform-docs/agent-doc-artifacts/` and
is intentionally ignored by Git. The published YAML is package data and is
reviewed with the code. `Context.help()` shows a source-fallback note only
when a present YAML is rejected because it is damaged, incompatible, or stale;
ordinary source-only and valid-published documentation do not show provenance.
