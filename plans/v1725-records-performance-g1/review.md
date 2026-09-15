# GraphSpec review: V1725 records performance G1

- Graph ID: `v1725-records-performance-g1`
- Generation: `1`
- Nodes: `7`
- Edges: `6`
- Compiled stages: `5`
- Validation result: `READY_FOR_HUMAN_APPROVAL`

## Approval candidate hashes

- GraphSpec SHA-256: `5720a049096b995dda2b6ce2ac7413c4301d42445c1470a75b98bb3a12498d3d`
- Registry SHA-256: `765378fe961abc33aaf0201b4c34b6a410077d841af786e57e6f35f9d7722992`
- Compiled Plan SHA-256: `39efd2d360e94ae15e39bd69c20d82612d93fb5eda521ae4d2cf28d9e4f89be0`
- Compiler SHA-256: `a7e6586506a1d540bfff2ac8166d306b40cb2fabea88a96492648b521ee26e8b`
- Reviewer: `xiaoyu`
- Approval marker: `not created by review`

## Errors

- None.

## Loop/SCC contracts

- `scc-0` nodes: `storage_chain`
- `scc-1` nodes: `reader_io`
- `scc-2` nodes: `parallel_resources`
- `scc-3` nodes: `integrate`
- `scc-4` nodes: `foundation_review`
- `scc-5` nodes: `final_qa`
- `scc-6` nodes: `array_compute`

## Condensation graph

- Edge: `scc-0` → `scc-4`
- Edge: `scc-1` → `scc-4`
- Edge: `scc-2` → `scc-3`
- Edge: `scc-3` → `scc-5`
- Edge: `scc-4` → `scc-2`
- Edge: `scc-6` → `scc-4`

## Compiled execution stages

- Stage 0: `scc-0`, `scc-1`, `scc-6`
- Stage 1: `scc-4`
- Stage 2: `scc-2`
- Stage 3: `scc-3`
- Stage 4: `scc-5`

## Node index

- `{"array_compute": {"scc_id": "scc-6", "unit_id": "array_compute"}, "final_qa": {"scc_id": "scc-5", "unit_id": "final_qa"}, "foundation_review": {"scc_id": "scc-4", "unit_id": "foundation_review"}, "integrate": {"scc_id": "scc-3", "unit_id": "integrate"}, "parallel_resources": {"scc_id": "scc-2", "unit_id": "parallel_resources"}, "reader_io": {"scc_id": "scc-1", "unit_id": "reader_io"}, "storage_chain": {"scc_id": "scc-0", "unit_id": "storage_chain"}}`

## Resolved executors

- `reader_io` → `luna-max-executor`
- `array_compute` → `luna-max-executor`
- `storage_chain` → `luna-max-executor`
- `foundation_review` → `luna-max-reviewer`
- `parallel_resources` → `luna-max-executor`
- `integrate` → `luna-max-integrator`
- `final_qa` → `luna-max-reviewer`
