#!/bin/bash
# 快速运行所有性能优化相关的测试

set -e

echo "=================================================="
echo "性能优化测试套件"
echo "=================================================="
echo ""

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试结果统计
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name=$1
    local test_path=$2

    echo -e "${YELLOW}[运行]${NC} $test_name"
    echo "----------------------------------------"

    if pytest "$test_path" -v --tb=short; then
        echo -e "${GREEN}[✓]${NC} $test_name 通过"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}[✗]${NC} $test_name 失败"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo ""
}

# 1. 功能测试 A1: Numba 加速
run_test "功能测试 A1: Numba 加速单元测试" \
    "tests/plugins/test_performance_optimizations.py"

# 2. 功能测试 A2: 并行执行
run_test "功能测试 A2: 并行执行框架测试" \
    "tests/core/test_parallel_execution.py"

# 3. 压力测试 B2: 边界情况和压力测试（不含 slow）
run_test "压力测试 B2: 边界情况测试（快速）" \
    "tests/plugins/test_stress_tests.py::TestEdgeCases"

run_test "压力测试 B2: 循环依赖检测" \
    "tests/plugins/test_stress_tests.py::TestDependencyCycles"

run_test "压力测试 B2: 健壮性测试" \
    "tests/plugins/test_stress_tests.py::TestRobustness"

# 4. 集成测试 C1: 端到端测试（不含 slow）
run_test "集成测试 C1: 端到端流水线测试" \
    "tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_complete_pipeline_basic"

run_test "集成测试 C1: 输出一致性测试" \
    "tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_output_consistency_deterministic"

run_test "集成测试 C1: 数据完整性测试" \
    "tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_data_integrity_through_pipeline"

run_test "集成测试 C1: 配置测试" \
    "tests/integration/test_end_to_end.py::TestEndToEndPipeline::test_different_configurations"

run_test "集成测试 C1: 真实场景测试" \
    "tests/integration/test_end_to_end.py::TestRealWorldScenarios"

# 总结
echo "=================================================="
echo "测试总结"
echo "=================================================="
echo -e "总测试组数: $TOTAL_TESTS"
echo -e "${GREEN}通过: $PASSED_TESTS${NC}"
echo -e "${RED}失败: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    echo ""
    echo "提示: 运行 './scripts/run_slow_tests.sh' 执行大数据集测试"
    exit 0
else
    echo -e "${RED}✗ 有测试失败，请检查上方输出${NC}"
    exit 1
fi
