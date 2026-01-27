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

usage() {
    echo "Usage: $0 [--yes] [--venv|--no-venv] [--dev|--no-dev] [--non-interactive]"
    echo
    echo "Options:"
    echo "  --yes               Non-interactive; create venv and install dev deps"
    echo "  --venv              Create venv (non-interactive)"
    echo "  --no-venv           Skip venv creation (non-interactive)"
    echo "  --dev               Install dev dependencies (non-interactive)"
    echo "  --no-dev            Skip dev dependencies (non-interactive)"
    echo "  --non-interactive   Do not prompt; default to --no-venv --no-dev"
    echo "  -h, --help          Show this help"
}

INTERACTIVE=1
CREATE_VENV=""
INSTALL_DEV=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|-y)
            INTERACTIVE=0
            CREATE_VENV="yes"
            INSTALL_DEV="yes"
            shift
            ;;
        --venv)
            INTERACTIVE=0
            CREATE_VENV="yes"
            shift
            ;;
        --no-venv)
            INTERACTIVE=0
            CREATE_VENV="no"
            shift
            ;;
        --dev)
            INTERACTIVE=0
            INSTALL_DEV="yes"
            shift
            ;;
        --no-dev)
            INTERACTIVE=0
            INSTALL_DEV="no"
            shift
            ;;
        --non-interactive)
            INTERACTIVE=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            usage
            exit 1
            ;;
    esac
done

# 创建虚拟环境（可选）
if [[ $INTERACTIVE -eq 1 ]]; then
    read -p "是否创建虚拟环境? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CREATE_VENV="yes"
    else
        CREATE_VENV="no"
    fi
else
    if [[ -z "$CREATE_VENV" ]]; then
        CREATE_VENV="no"
    fi
fi

if [[ "$CREATE_VENV" == "yes" ]]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✅ 虚拟环境已激活"
fi

# 升级 pip
echo "升级 pip..."
python3 -m pip install --upgrade pip

# 安装包（开发模式）
echo "安装 waveform-analysis（开发模式）..."
python3 -m pip install -e .

# 安装开发依赖
if [[ $INTERACTIVE -eq 1 ]]; then
    read -p "是否安装开发依赖? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        INSTALL_DEV="yes"
    else
        INSTALL_DEV="no"
    fi
else
    if [[ -z "$INSTALL_DEV" ]]; then
        INSTALL_DEV="no"
    fi
fi

if [[ "$INSTALL_DEV" == "yes" ]]; then
    echo "安装开发依赖..."
    python3 -m pip install -e ".[dev]"
    echo "✅ 开发依赖已安装"
fi

echo
echo "=================================="
echo "安装完成！"
echo "=================================="
echo
echo "快速开始:"
echo "  1. 运行示例: python examples/config_management_example.py"
echo "  2. 运行测试: pytest tests/"
echo "  3. 使用CLI: waveform-process --help"
echo
echo "如果创建了虚拟环境，使用以下命令激活:"
echo "  source venv/bin/activate"
echo
