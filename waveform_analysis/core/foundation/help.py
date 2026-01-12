"""
Help 系统核心实现

提供交互式帮助、快速参考和代码模板生成功能。
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from waveform_analysis.core.foundation.utils import exporter

if TYPE_CHECKING:
    from waveform_analysis.core.context import Context

export, __all__ = exporter()


@export
class HelpSystem:
    """核心 help 系统"""

    def __init__(self, ctx: 'Context'):
        """
        初始化 Help 系统

        创建帮助系统实例，关联到特定的 Context。

        Args:
            ctx: Context 实例，用于访问插件和配置信息

        初始化内容:
        - 注册帮助主题（quickstart, config, plugins, performance, examples）
        - 初始化帮助内容缓存
        """
        self.ctx = ctx
        self._topics = {
            'quickstart': QuickstartHelp(),
            'config': ConfigHelp(),
            'plugins': PluginHelp(),
            'performance': PerformanceHelp(),
            'examples': ExamplesHelp(),
        }
        self._cache: Dict[tuple, str] = {}

    def show(
        self,
        topic: Optional[str] = None,
        search: Optional[str] = None,
        verbose: bool = False
    ) -> str:
        """
        显示帮助信息

        Args:
            topic: 帮助主题 ('quickstart', 'config', 'plugins', 'performance', 'examples')
            search: 搜索关键词
            verbose: 显示详细信息

        Returns:
            帮助文本
        """
        # 搜索模式
        if search:
            return self._search(search)

        # 默认快速参考
        if topic is None:
            return self._quick_reference()

        # 主题模式
        if topic in self._topics:
            cache_key = (topic, verbose)
            if cache_key not in self._cache:
                self._cache[cache_key] = self._topics[topic].show(self.ctx, verbose)
            return self._cache[cache_key]

        # 未知主题
        return self._unknown_topic(topic)

    def _quick_reference(self) -> str:
        """默认快速参考"""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║ WaveformAnalysis Context - 快速参考                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

📚 核心概念
  • Context: 插件系统调度器，管理依赖、配置、缓存
  • Plugin: 数据处理单元（RawFiles → Waveforms → Peaks）
  • Lineage: 自动血缘追踪，确保缓存一致性

🚀 快速开始
────────────────────────────────────────────────────────────────────────────────
  from waveform_analysis.core.context import Context
  from waveform_analysis.core.plugins.builtin import standard_plugins

  ctx = Context(storage_dir='./data')
  ctx.register(standard_plugins)
  ctx.set_config({'n_channels': 2})
  data = ctx.get_data('run_001', 'peaks')
────────────────────────────────────────────────────────────────────────────────

📖 帮助主题
  ctx.help('quickstart')   - 5分钟快速上手
  ctx.help('config')       - 配置管理详解
  ctx.help('plugins')      - 插件系统指南
  ctx.help('performance')  - 性能优化技巧
  ctx.help('examples')     - 常见场景示例

🔍 搜索功能
  ctx.help(search='time_range')  - 搜索相关方法和配置

💡 提示: 使用 verbose=True 查看详细说明
  ctx.help('quickstart', verbose=True)
"""

    def _search(self, query: str) -> str:
        """搜索功能（简化版，Phase 2 实现完整版）"""
        return f"""
🔍 搜索 "{query}" 的结果:

⚠️  搜索功能将在 Phase 2 中实现。

💡 临时解决方案:
  • 使用 dir(ctx) 查看所有方法
  • 使用 help(ctx.method_name) 查看方法文档
  • 使用 ctx.list_plugin_configs() 查看配置选项
"""

    def _unknown_topic(self, topic: str) -> str:
        """未知主题提示"""
        available = ', '.join(self._topics.keys())
        return f"""
❌ 未知主题: '{topic}'

可用主题: {available}

💡 使用 ctx.help() 查看快速参考
"""


@export
class QuickstartHelp:
    """快速开始主题"""

    SCENARIOS = {
        'basic': '基础分析流程 (推荐新手)',
        'memory_efficient': '内存优化流程 (大数据集)',
    }

    def show(self, ctx: 'Context', verbose: bool = False) -> str:
        """显示快速开始帮助"""
        if not verbose:
            # 简洁模式：只显示场景列表
            output = "╔══════════════════════════════════════════════════════════════════╗\n"
            output += "║ 快速开始指南                                                     ║\n"
            output += "╚══════════════════════════════════════════════════════════════════╝\n\n"
            output += "选择场景:\n"
            for i, (key, desc) in enumerate(self.SCENARIOS.items(), 1):
                output += f"  {i}. {key:20} - {desc}\n"
            output += "\n使用方式:\n"
            output += "  ctx.quickstart('basic')  # 生成代码模板\n\n"
            output += "💡 提示: 使用 verbose=True 查看所有场景的完整代码\n"
            return output
        else:
            # 详细模式：显示所有场景的完整代码
            return self._show_verbose_help()

    def _show_verbose_help(self) -> str:
        """显示详细帮助（包含代码示例）"""
        output = "╔══════════════════════════════════════════════════════════════════╗\n"
        output += "║ 快速开始指南 - 详细模式                                         ║\n"
        output += "╚══════════════════════════════════════════════════════════════════╝\n\n"

        # 场景 1: 基础分析
        output += "┌──────────────────────────────────────────────────────────────────┐\n"
        output += "│ 场景 1: 基础分析流程                                             │\n"
        output += "└──────────────────────────────────────────────────────────────────┘\n\n"
        output += "📝 代码模板 (可直接复制):\n"
        output += "─" * 72 + "\n"
        output += """from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin import standard_plugins

# 1. 初始化 Context
ctx = Context(storage_dir='./strax_data')
ctx.register(standard_plugins)

# 2. 设置配置
ctx.set_config({
    'data_root': 'DAQ',
    'n_channels': 2,
    'threshold': 15.0,
})

# 3. 获取数据（自动触发依赖链）
peaks = ctx.get_data('run_001', 'peaks')
print(f"Found {len(peaks)} peaks")

# 4. 可视化血缘图
ctx.plot_lineage('peaks', kind='labview')
"""
        output += "─" * 72 + "\n\n"
        output += "📊 数据流: raw_files → waveforms → st_waveforms → peaks\n"
        output += "⏱️  预计运行时间: 约 30秒 (取决于数据量)\n"
        output += "💾 缓存位置: ./strax_data/\n\n"

        # 场景 2: 内存优化
        output += "┌──────────────────────────────────────────────────────────────────┐\n"
        output += "│ 场景 2: 内存优化流程 (节省 70-80% 内存)                         │\n"
        output += "└──────────────────────────────────────────────────────────────────┘\n\n"
        output += "📝 代码模板:\n"
        output += "─" * 72 + "\n"
        output += """from waveform_analysis import WaveformDataset

# load_waveforms=False 跳过波形数据加载
ds = WaveformDataset(run_name='run_001', n_channels=2, load_waveforms=False)

# 链式调用（波形步骤会被跳过）
(ds
    .load_raw_data()
    .extract_waveforms()        # 跳过
    .structure_waveforms()      # 跳过
    .build_waveform_features()  # 仍会计算特征
    .build_dataframe()
    .group_events()
    .pair_events())

# 获取结果
df = ds.get_paired_events()
print(f"Processed {len(df)} paired events")
"""
        output += "─" * 72 + "\n\n"
        output += "💡 注意: get_waveform_at() 会返回 None\n"
        output += "🔗 更多场景: 运行 ctx.quickstart('template_name')\n"

        return output


@export
class ConfigHelp:
    """配置管理主题"""

    def show(self, ctx: 'Context', verbose: bool = False) -> str:
        """显示配置管理帮助"""
        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║ 配置管理指南                                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

🔧 配置方法:

  1. 查看可用配置选项
     ctx.list_plugin_configs()            # 所有插件的配置选项
     ctx.list_plugin_configs('waveforms') # 特定插件的配置选项

  2. 查看当前配置值
     ctx.show_config()                    # 全局配置概览
     ctx.show_config('waveforms')         # 特定插件的配置

  3. 设置配置
     # 全局配置（影响多个插件）
     ctx.set_config({'n_channels': 2})

     # 插件特定配置（推荐，避免冲突）
     ctx.set_config({'threshold': 50}, plugin_name='peaks')

📋 配置优先级 (从高到低):
  1. 插件特定配置（嵌套字典）: ctx.config = {'peaks': {'threshold': 50}}
  2. 插件特定配置（点分隔）:   ctx.config = {'peaks.threshold': 50}
  3. 全局配置:                 ctx.config = {'threshold': 50}
  4. 插件默认值:               plugin.options['threshold'].default

💡 最佳实践:
  ✓ 优先使用插件特定配置避免全局命名冲突
  ✓ 使用 show_config() 检查配置是否生效
  ✓ 配置项拼写错误会出现在「未使用配置」中

📊 常见配置场景:
  • 内存优化:   ctx.set_config({'chunksize': 5000})
  • 性能优化:   ctx.set_config({'channel_workers': 4}, plugin_name='waveforms')
  • 调试模式:   ctx.set_config({'show_progress': True, 'verbose': True})
"""

        if verbose:
            output += """
📚 配置系统详解:

• 配置发现: list_plugin_configs() 提供业界领先的配置发现工具
  - 显示所有插件的配置选项、默认值、类型、帮助文本
  - 图标区分默认值和已修改的配置 (✓ vs ⚙️)
  - 明确标记已自定义的配置值 (🔧)
  - 统计已注册插件数、配置项总数、已修改配置数

• 配置验证: show_config() 提供智能配置分析
  - 自动识别哪些插件使用了每个全局配置项
  - 三类配置分组: 全局配置、插件特定配置、未使用配置
  - 详细的插件配置视图（配置值 vs 默认值对比）

• 配置建议: (Phase 2 实现)
  - validate_config(): 验证配置有效性
  - suggest_config(use_case='memory_efficient'): 推荐配置方案
"""

        return output


@export
class PluginHelp:
    """插件系统主题"""

    def show(self, ctx: 'Context', verbose: bool = False) -> str:
        """显示插件系统帮助"""
        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║ 插件系统指南                                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

📦 插件架构:

  • Plugin: 独立的数据处理单元
  • 每个插件声明: provides, depends_on, options, version, dtype
  • Context 自动管理依赖关系（DAG）

🔗 标准插件数据流:

  raw_files → waveforms → st_waveforms → event_length
                                            ↓
                                       basic_features
                                      ↙             ↘
                                  peaks           charges
                                      ↘             ↙
                                        dataframe
                                            ↓
                                    grouped_events
                                            ↓
                                     paired_events

💻 使用插件:

  # 1. 注册插件
  from waveform_analysis.core.plugins.builtin import standard_plugins
  ctx.register(standard_plugins)

  # 2. 获取数据（自动触发依赖链）
  peaks = ctx.get_data('run_001', 'peaks')

  # 3. 查看血缘图
  ctx.plot_lineage('peaks', kind='labview')

📋 查看已注册插件:

  ctx.list_provided_data()      # 查看所有可用数据类型
  ctx.list_plugin_configs()     # 查看插件配置选项
"""

        if verbose:
            output += """
🔧 自定义插件示例:

────────────────────────────────────────────────────────────────────────────────
from waveform_analysis.core.plugins.core.base import Plugin
import numpy as np

class MyPlugin(Plugin):
    provides = 'my_data'
    depends_on = ['waveforms']
    version = '1.0.0'
    options = {
        'threshold': Option(default=10.0, help='阈值参数'),
    }

    def compute(self, waveforms, run_id):
        threshold = self.config.get('threshold', 10.0)
        # ... 处理逻辑 ...
        return result

# 注册自定义插件
ctx.register(MyPlugin())
data = ctx.get_data('run_001', 'my_data')
────────────────────────────────────────────────────────────────────────────────

📚 更多信息:
  • 插件基类: waveform_analysis.core.plugins.core.base.Plugin
  • 内置插件: waveform_analysis.core.plugins.builtin.standard
  • 流式插件: waveform_analysis.core.plugins.core.streaming.StreamingPlugin
"""

        return output


@export
class PerformanceHelp:
    """性能优化主题"""

    def show(self, ctx: 'Context', verbose: bool = False) -> str:
        """显示性能优化帮助"""
        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║ 性能优化指南                                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

⚡ 优化技巧:

1. **内存优化**
   • 跳过波形加载: load_waveforms=False (节省 70-80%)
   • 调整 chunksize: set_config({'chunksize': 5000})
   • 使用流式处理: StreamingContext

2. **缓存优化**
   • 血缘自动缓存: 插件版本/配置/dtype 变化时自动失效
   • 手动清理缓存: ctx.clear_cache('run_001', 'data_name')
   • 查看缓存目录: ctx.storage_dir

3. **并行执行**
   • ExecutorManager: 全局线程池/进程池复用
   • IO 密集: get_executor('io_intensive')
   • CPU 密集: get_executor('cpu_intensive')

4. **Numba 加速**
   • group_multi_channel_hits(use_numba=True)
   • JIT 编译热循环函数

📊 性能分析:

  # 启用统计收集
  ctx = Context(enable_stats=True, stats_mode='detailed')
  # ... 执行操作 ...
  print(ctx.get_performance_report())

💡 常见场景配置:

  # 内存优化
  ctx.set_config({'chunksize': 5000, 'enable_cache': False})

  # 性能优化
  ctx.set_config({'chunksize': 20000, 'channel_workers': 4, 'use_numba': True})
"""

        if verbose:
            output += """
🔍 性能瓶颈诊断:

1. 检查缓存命中率
   • 查看日志中的 "Loading cached data" vs "Computing data"

2. 分析插件执行时间
   • 使用 enable_stats=True 启用性能统计
   • 查看 PluginStatsCollector 输出

3. 内存使用监控
   • 使用系统工具: htop, ps aux
   • Python profiler: memory_profiler

4. I/O 优化
   • 减少磁盘读写: 使用缓存
   • 批量处理: BatchProcessor
   • 并行 I/O: ExecutorManager

📈 基准测试:

  # I/O 基准测试
  python scripts/benchmark_io.py --n-files 100 --n-channels 2

  # 完整流程基准测试
  time python your_analysis.py
"""

        return output


@export
class ExamplesHelp:
    """常见场景示例主题"""

    def show(self, ctx: 'Context', verbose: bool = False) -> str:
        """显示常见场景示例"""
        output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║ 常见场景示例                                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

🎯 快速生成代码模板:

  ctx.quickstart('basic')              # 基础分析流程
  ctx.quickstart('memory_efficient')   # 内存优化
  ctx.quickstart('batch_processing')   # 批量处理 (Phase 2.3)
  ctx.quickstart('streaming')          # 流式处理 (Phase 2.3)
  ctx.quickstart('custom_plugin')      # 自定义插件 (Phase 2.3)

📚 常见操作:

1. **基础分析**
   ctx.quickstart('basic')

2. **批量处理多个运行**
   示例代码将在 Phase 2.3 提供

3. **时间范围查询**
   data = ctx.get_data_time_range('run_001', 'peaks', start_time=1000, end_time=2000)

4. **自定义特征**
   def my_feature(st_waveforms, **params):
       return np.array([...])

   ds.register_feature('my_feature', my_feature)
   ds.compute_registered_features()

5. **血缘可视化**
   ctx.plot_lineage('df_paired', kind='labview', interactive=True)
   ctx.plot_lineage('df_paired', kind='plotly', verbose=2)

💼 完整示例:

  • examples/basic_analysis.py              - 基础分析
  • examples/advanced_features.py           - 高级功能
  • examples/skip_waveforms.py              - 内存优化
  • examples/config_management_example.py   - 配置管理
"""

        if verbose:
            output += """
🔬 高级场景:

1. **Strax 插件集成**
   from waveform_analysis.core.plugins.core.adapters import wrap_strax_plugin
   adapter = wrap_strax_plugin(MyStraxPlugin)
   ctx.register(adapter)

2. **批量导出数据**
   from waveform_analysis.core.data.export import batch_export
   batch_export(ctx, run_ids=['run_001', 'run_002'],
                data_name='peaks', output_dir='./exports', format='parquet')

3. **热重载插件（开发）**
   from waveform_analysis.core.plugins.core.hot_reload import enable_hot_reload
   reloader = enable_hot_reload(ctx, ['my_plugin'], auto_reload=True)

4. **性能分析**
   ctx = Context(enable_stats=True, stats_mode='detailed')
   # ... 操作 ...
   stats = ctx.stats_collector.get_summary()

🔗 更多资源:
  • 文档: docs/
  • 示例: examples/
  • 测试: tests/
"""

        return output
