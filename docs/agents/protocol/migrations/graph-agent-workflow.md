# Graph Agent Workflow migration

Graph Agent Workflow is now maintained as a standalone repository:

- Repository: `/mnt/data/Run3/DA-Graph-Workflow`
- Imported from `codex/context-domains@82ca3173d22b9500365fb85fee1add3f2a854496`
- Standalone import commit: `0afdc0e`
- Gateway: `http://10.18.154.11:8899/`

The WaveformAnalysis working tree no longer owns the Graph Agent Workflow
source tree. Gateway state, runtime workspace, and sanitized Console static
files are kept outside both source repositories.
