#!/bin/bash
# 快速安装脚本

set -e

echo "=================================="
echo "Waveform Analysis 安装脚本"
echo "=================================="
echo

# 检查 Python 版本
echo "检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python 版本: $python_version"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo "错误: pip3 未找到，请先安装 pip"
    exit 1
fi

# 创建虚拟环境（可选）
read -p "是否创建虚拟环境? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ 虚拟环境已激活"
fi

# 升级 pip
echo "升级 pip..."
pip3 install --upgrade pip

# 安装包（开发模式）
echo "安装 waveform-analysis（开发模式）..."
pip3 install -e .

# 安装开发依赖
read -p "是否安装开发依赖? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "安装开发依赖..."
    pip3 install -e ".[dev]"
    echo "✅ 开发依赖已安装"
fi

echo
echo "=================================="
echo "安装完成！"
echo "=================================="
echo
echo "快速开始:"
echo "  1. 运行示例: python examples/basic_analysis.py"
echo "  2. 运行测试: pytest tests/"
echo "  3. 使用CLI: waveform-process --help"
echo
echo "如果创建了虚拟环境，使用以下命令激活:"
echo "  source venv/bin/activate"
echo
