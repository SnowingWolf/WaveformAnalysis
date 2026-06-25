#!/usr/bin/env python
"""
将 gain_adc_per_pe 集成到系统的完整指南

本文档展示三种集成方式：
1. 全局配置（所有 run 共享）
2. Run 特定配置（不同 run 不同增益）
3. 通过配置文件管理（推荐用于生产环境）
"""

from pathlib import Path

import yaml

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    BasicFeaturesPlugin,
    DataFramePlugin,
    RawFilesPlugin,
    WaveformsPlugin,
)


# ============================================================================
# 方式 1: 全局配置（推荐用于测试和开发）
# ============================================================================
def method_1_global_config():
    """
    方式 1: 在 Context 中设置全局增益配置

    优点：简单直接，适合快速测试
    缺点：所有 run 使用相同增益
    """
    print("=" * 80)
    print("方式 1: 全局配置")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")

    # 注册所有需要的插件
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        BasicFeaturesPlugin(),
        DataFramePlugin(),
    )

    # 设置全局增益配置
    gain_config = {
        "0:9": 200.0,
        "0:10": 200.0,
        "0:11": 200.0,
        "0:12": 200.0,
        "0:13": 200.0,
        "0:14": 200.0,
        "0:15": 200.0,
    }

    ctx.set_config({"gain_adc_per_pe": gain_config})

    print("✓ 已设置全局增益配置")
    print(f"  配置的通道数: {len(gain_config)}")
    print("  增益值: 200.0 ADC/PE")

    # 现在处理任何 run 都会使用这个增益
    # df = ctx.get_array(run_id="your_run", target="df")
    # df 会包含 area_pe 和 height_pe 列

    return ctx


# ============================================================================
# 方式 2: Run 特定配置文件（推荐用于生产环境）
# ============================================================================
def method_2_run_config_file():
    """
    方式 2: 为每个 run 创建 run_config.yaml

    优点：灵活，每个 run 可以有不同的增益
    缺点：需要为每个 run 创建配置文件
    """
    print("\n" + "=" * 80)
    print("方式 2: Run 特定配置文件")
    print("=" * 80)

    # 1. 创建 run_config.yaml 文件示例
    run_config = {
        "plugins": {
            "df": {
                "gain_adc_per_pe": {
                    "0:9": 200.0,
                    "0:10": 200.0,
                    "0:11": 200.0,
                    "0:12": 200.0,
                    "0:13": 200.0,
                    "0:14": 200.0,
                    "0:15": 200.0,
                }
            }
        }
    }

    print("run_config.yaml 示例结构:")
    print(yaml.dump(run_config, default_flow_style=False, allow_unicode=True))

    print("\n配置文件位置: DAQ/<run_name>/run_config.yaml")
    print("\n使用方法:")
    print("  1. 在 DAQ 目录下创建 run_config.yaml")
    print("  2. 按上述格式填写增益配置")
    print("  3. Context 会自动加载该配置")

    return run_config


# ============================================================================
# 方式 3: 批量生成配置文件（推荐用于多 run）
# ============================================================================
def method_3_generate_config_files(daq_root: str = "DAQ", gain_value: float = 200.0):
    """
    方式 3: 批量为所有 run 生成配置文件

    优点：一次性配置所有 run
    缺点：需要确保所有 run 使用相同的增益
    """
    print("\n" + "=" * 80)
    print("方式 3: 批量生成配置文件")
    print("=" * 80)

    daq_path = Path(daq_root)
    if not daq_path.exists():
        print(f"✗ DAQ 目录不存在: {daq_root}")
        return

    # 定义增益配置
    gain_config = {
        "0:9": gain_value,
        "0:10": gain_value,
        "0:11": gain_value,
        "0:12": gain_value,
        "0:13": gain_value,
        "0:14": gain_value,
        "0:15": gain_value,
    }

    run_config_template = {"plugins": {"df": {"gain_adc_per_pe": gain_config}}}

    # 遍历所有 run 目录
    run_dirs = [d for d in daq_path.iterdir() if d.is_dir() and not d.name.startswith(".")]

    created_count = 0
    skipped_count = 0

    for run_dir in run_dirs:
        config_file = run_dir / "run_config.yaml"

        if config_file.exists():
            print(f"⊙ 跳过 {run_dir.name} (配置文件已存在)")
            skipped_count += 1
            continue

        # 写入配置文件
        with open(config_file, "w") as f:
            yaml.dump(run_config_template, f, default_flow_style=False, allow_unicode=True)

        print(f"✓ 创建 {run_dir.name}/run_config.yaml")
        created_count += 1

    print("\n总结:")
    print(f"  创建: {created_count} 个配置文件")
    print(f"  跳过: {skipped_count} 个配置文件")
    print(f"  增益值: {gain_value} ADC/PE (通道 9-15)")


# ============================================================================
# 方式 4: 从标定文件加载（最灵活）
# ============================================================================
def method_4_load_from_calibration(calibration_file: str = "calibration.yaml"):
    """
    方式 4: 从专门的标定文件加载增益

    优点：集中管理所有标定参数，便于版本控制
    缺点：需要维护单独的标定文件
    """
    print("\n" + "=" * 80)
    print("方式 4: 从标定文件加载")
    print("=" * 80)

    # 标定文件示例结构
    calibration_template = {
        "version": "1.0",
        "date": "2026-06-23",
        "description": "单光子增益标定结果",
        "gains": {
            "0:9": 200.0,
            "0:10": 200.0,
            "0:11": 200.0,
            "0:12": 200.0,
            "0:13": 200.0,
            "0:14": 200.0,
            "0:15": 200.0,
        },
    }

    print("calibration.yaml 示例结构:")
    print(yaml.dump(calibration_template, default_flow_style=False, allow_unicode=True))

    # 使用示例
    print("\n使用方法:")
    print("```python")
    print("# 加载标定文件")
    print("with open('calibration.yaml') as f:")
    print("    calib = yaml.safe_load(f)")
    print("")
    print("# 应用到 Context")
    print("ctx = Context()")
    print("ctx.set_config({'gain_adc_per_pe': calib['gains']})")
    print("```")

    return calibration_template


# ============================================================================
# 完整工作流示例
# ============================================================================
def complete_workflow_example():
    """完整的数据处理工作流，包含增益配置"""
    print("\n" + "=" * 80)
    print("完整工作流示例")
    print("=" * 80)

    # 1. 创建 Context
    ctx = Context(storage_dir="./strax_data")

    # 2. 注册插件
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        BasicFeaturesPlugin(),
        DataFramePlugin(),
    )

    # 3. 设置增益配置
    gain_config = {
        "0:9": 200.0,
        "0:10": 200.0,
        "0:11": 200.0,
        "0:12": 200.0,
        "0:13": 200.0,
        "0:14": 200.0,
        "0:15": 200.0,
    }
    ctx.set_config({"gain_adc_per_pe": gain_config})

    print("✓ 系统配置完成")
    print("  存储目录: ./strax_data")
    print("  注册插件: 4 个")
    print(f"  增益配置: {len(gain_config)} 个通道")

    # 4. 处理数据
    print("\n处理数据流程:")
    print("  1. raw_files → 读取原始数据")
    print("  2. waveforms → 提取波形")
    print("  3. basic_features → 计算基础特征 (area, height in ADC)")
    print("  4. df → 构建 DataFrame + 增益校准 (area_pe, height_pe)")

    # 实际使用
    print("\n实际使用:")
    print("```python")
    print("# 获取校准后的数据")
    print("df = ctx.get_array(run_id='your_run', target='df')")
    print("")
    print("# 现在 df 包含以下列:")
    print("# - area: 峰面积 (ADC counts)")
    print("# - height: 峰高 (ADC counts)")
    print("# - area_pe: 峰面积 (光电子数) ← 使用增益校准")
    print("# - height_pe: 峰高 (光电子数) ← 使用增益校准")
    print("```")


# ============================================================================
# 验证增益配置
# ============================================================================
def verify_gain_config(ctx: Context):
    """验证增益配置是否正确应用"""
    print("\n" + "=" * 80)
    print("验证增益配置")
    print("=" * 80)

    # 查看当前配置
    print("\n1. 查看全局配置:")
    print("```python")
    print("ctx.show_config('df')")
    print("```")

    # 查看插件选项
    print("\n2. 查看插件选项:")
    print("```python")
    print("ctx.list_plugin_configs()")
    print("```")

    # 检查数据输出
    print("\n3. 检查数据输出:")
    print("```python")
    print("df = ctx.get_array(run_id='test_run', target='df')")
    print("print(df.dtype.names)  # 应该包含 'area_pe' 和 'height_pe'")
    print("")
    print("# 验证转换是否正确")
    print("for i in range(min(5, len(df))):")
    print("    print(f'area={df[i][\"area\"]:.1f} ADC, '")
    print("          f'area_pe={df[i][\"area_pe\"]:.2f} PE')")
    print("```")


# ============================================================================
# 主函数
# ============================================================================
def main():
    print("\n" + "=" * 80)
    print("gain_adc_per_pe 系统集成完整指南")
    print("=" * 80)

    print("\n推荐使用方式（按场景）:")
    print("  • 快速测试 → 方式 1: 全局配置")
    print("  • 生产环境 → 方式 2: Run 特定配置文件")
    print("  • 批量处理 → 方式 3: 批量生成配置")
    print("  • 集中管理 → 方式 4: 标定文件")

    # 运行各个示例
    method_1_global_config()
    method_2_run_config_file()

    # 方式 3 需要实际的 DAQ 目录，这里只展示
    print("\n" + "=" * 80)
    print("方式 3: 批量生成配置文件")
    print("=" * 80)
    print("使用方法:")
    print("```python")
    print("method_3_generate_config_files(daq_root='DAQ', gain_value=200.0)")
    print("```")

    method_4_load_from_calibration()
    complete_workflow_example()

    print("\n" + "=" * 80)
    print("下一步操作")
    print("=" * 80)
    print("\n1. 选择适合你的集成方式")
    print("2. 配置增益参数")
    print("3. 运行数据处理")
    print("4. 验证 area_pe 和 height_pe 列是否正确生成")
    print("\n完整文档: examples/gain_integration_guide.py")


if __name__ == "__main__":
    main()
