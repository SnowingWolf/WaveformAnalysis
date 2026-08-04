#!/bin/bash
# 运行慢速测试（大数据集和内存压力测试）

set -e

echo "=================================================="
echo "慢速测试套件（大数据集和内存测试）"
echo "=================================================="
echo ""
echo "警告: 这些测试可能需要几分钟时间"
echo ""

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 大数据集压力测试
echo -e "${YELLOW}[运行]${NC} 大数据集压力测试"
echo "----------------------------------------"
if pytest tests/plugins/test_stress_tests.py::TestLargeDatasets -v --tb=short; then
    echo -e "${GREEN}[✓]${NC} 大数据集测试通过"
else
    echo -e "${RED}[✗]${NC} 大数据集测试失败"
fi
echo ""

# 2. 内存压力测试
echo -e "${YELLOW}[运行]${NC} 内存压力测试"
echo "----------------------------------------"
if pytest tests/plugins/test_stress_tests.py::TestMemoryPressure -v --tb=short; then
    echo -e "${GREEN}[✓]${NC} 内存压力测试通过"
else
    echo -e "${RED}[✗]${NC} 内存压力测试失败"
fi
echo ""

# 3. 性能提升测试
echo -e "${YELLOW}[运行]${NC} 性能提升验证测试"
echo "----------------------------------------"
if pytest tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_performance_improvement -v --tb=short; then
    echo -e "${GREEN}[✓]${NC} 性能提升测试通过"
else
    echo -e "${RED}[✗]${NC} 性能提升测试失败"
fi
echo ""

echo "=================================================="
echo "慢速测试完成"
echo "=================================================="
