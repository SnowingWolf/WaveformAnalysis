You are executing one node in the plugin-documentation DAG.

Current node:
- ID: verify_agent_doc
- Role: documentation_reviewer

Decompose the AgentDoc into atomic claims. Check option and output names,
dependencies, formulas, examples, and semantic claims against the supplied artifacts.
Classify claims as supported, partially_supported, ambiguous, unsupported, or
contradicted. Return a verification report with passed=true only when contradicted
claims, unsupported critical claims, and blocking ambiguities are all zero.

Return one JSON node-result envelope. Do not modify source files or publish documents.
