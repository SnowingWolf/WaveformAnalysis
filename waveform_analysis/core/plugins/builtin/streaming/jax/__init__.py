# -*- coding: utf-8 -*-
"""
[JAX + Streaming] JAX 流式插件模块 - GPU 加速流式处理

本模块包含 JAX 实现的流式插件：
- filtering.py: [JAX + Streaming] 流式滤波插件（GPU 加速）
- peak_finding.py: [JAX + Streaming] 流式寻峰插件（GPU 加速）

**加速器**: JAX (GPU 优先，自动回退 CPU)
**流式支持**: ✓
**依赖**: jax >= 0.4.0, jaxlib >= 0.4.0

**性能特性**:
- GPU 并行批处理
- 内存高效的 chunk 级处理
- 自动负载均衡
- JIT 编译加速
"""

# 导出将在后续 Phase 2 中添加
__all__ = []
