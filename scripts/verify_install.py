#!/usr/bin/env python3
"""
安装验证脚本 - 检查包是否正确安装
"""

import sys


def check_import():
    """检查包导入"""
    print("1. 检查包导入...")
    try:
        import waveform_analysis

        print(f"   ✅ waveform_analysis 版本: {waveform_analysis.__version__}")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return False

    return True


def check_core_modules():
    """检查核心模块"""
    print("\n2. 检查核心模块...")
    try:
        from waveform_analysis import (
            Context,
            WaveformStruct,
            group_multi_channel_hits,
        )
        from waveform_analysis.core.processing.loader import get_raw_files, get_waveforms

        print("   ✅ 所有核心模块可导入")
        return True
    except ImportError as e:
        print(f"   ❌ 核心模块导入失败: {e}")
        return False


def check_submodules():
    """检查子模块"""
    print("\n3. 检查子模块...")
    modules = [
        ("waveform_analysis.core", ["loader", "processor"]),
        ("waveform_analysis.fitting", ["models"]),
        ("waveform_analysis.utils", []),
    ]

    all_ok = True
    for pkg, subs in modules:
        try:
            __import__(pkg)
            print(f"   ✅ {pkg}")
            for sub in subs:
                __import__(f"{pkg}.{sub}")
                print(f"      ✅ {pkg}.{sub}")
        except ImportError as e:
            print(f"   ❌ {pkg}: {e}")
            all_ok = False

    return all_ok


def check_cli():
    """检查命令行工具"""
    print("\n4. 检查命令行工具...")
    import subprocess

    try:
        result = subprocess.run(["waveform-process", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"   ✅ CLI 工具可用: {result.stdout.strip()}")
            return True
        else:
            print(f"   ⚠️  CLI 可能未正确安装")
            return False
    except FileNotFoundError:
        print("   ⚠️  CLI 命令未找到（可能需要重新激活环境）")
        return False
    except Exception as e:
        print(f"   ⚠️  CLI 检查失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Waveform Analysis 安装验证")
    print("=" * 60)

    checks = [
        check_import,
        check_core_modules,
        check_submodules,
        check_cli,
    ]

    results = [check() for check in checks]

    print("\n" + "=" * 60)
    print("验证结果:")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n✅ 所有检查通过！包已正确安装。")
        print("\n下一步:")
        print("  - 运行示例: waveform-process --scan-daq --daq-root DAQ")
        print("  - 查看文档: cat QUICKSTART.md")
        print("  - 运行测试: pytest tests/")
        return 0
    else:
        print("\n⚠️  部分检查未通过。")
        print("\n建议:")
        print("  - 重新安装: pip install -e .")
        print("  - 检查依赖: pip install -r requirements.txt")
        print("  - 激活虚拟环境（如果使用）")
        return 1


if __name__ == "__main__":
    sys.exit(main())
