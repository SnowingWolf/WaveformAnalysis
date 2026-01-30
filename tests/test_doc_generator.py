"""
测试文档生成器和覆盖检查器

测试内容：
- PluginDocGenerator: 文档生成器
- DocCoverageChecker: 文档覆盖检查器
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core.plugins.core.base import Option, Plugin


# 测试用插件
class MockPlugin(Plugin):
    """Mock plugin for testing documentation generation."""

    provides = "mock_data"
    depends_on = ["st_waveforms"]
    version = "1.2.3"
    description = "A mock plugin for testing."
    output_dtype = np.dtype([("value", "f4"), ("count", "i4")])

    options = {
        "threshold": Option(default=10.0, type=float, help="Detection threshold"),
        "enabled": Option(default=True, type=bool, help="Enable feature"),
    }

    def compute(self, context, run_id, **kwargs):
        return np.zeros(10, dtype=self.output_dtype)


class MockPluginNoDoc(Plugin):
    """Plugin without proper documentation."""

    provides = "mock_no_doc"
    depends_on = []
    output_dtype = None

    options = {
        "param": Option(default=1),  # No help text
    }

    def compute(self, context, run_id, **kwargs):
        return []


class TestPluginDocGenerator:
    """测试 PluginDocGenerator"""

    def test_extract_doc_info_from_plugin(self):
        """测试从插件提取文档信息"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        doc_info = generator.extract_doc_info(MockPlugin, MockPlugin())

        assert doc_info.name == "MockPlugin"
        assert doc_info.provides == "mock_data"
        assert doc_info.version == "1.2.3"
        assert doc_info.description == "A mock plugin for testing."
        assert "st_waveforms" in doc_info.depends_on

    def test_extract_config_options(self):
        """测试提取配置选项"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        doc_info = generator.extract_doc_info(MockPlugin, MockPlugin())

        assert len(doc_info.config_options) == 2

        # 查找 threshold 选项
        threshold_opt = next(
            (o for o in doc_info.config_options if o.name == "threshold"), None
        )
        assert threshold_opt is not None
        assert threshold_opt.type == "float"
        assert threshold_opt.default == 10.0
        assert threshold_opt.doc == "Detection threshold"

    def test_extract_output_fields(self):
        """测试提取输出字段"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        doc_info = generator.extract_doc_info(MockPlugin, MockPlugin())

        assert doc_info.output_kind == "structured_array"
        assert len(doc_info.output_fields) == 2

        field_names = [f.name for f in doc_info.output_fields]
        assert "value" in field_names
        assert "count" in field_names

    def test_category_detection(self):
        """测试类别检测"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()

        # 测试不同的 provides 名称
        assert generator._detect_category("raw_files", "RawFilesPlugin") == "data_loading"
        assert generator._detect_category("waveforms", "WaveformsPlugin") == "waveform_processing"
        assert generator._detect_category("basic_features", "BasicFeaturesPlugin") == "feature_extraction"
        assert generator._detect_category("grouped_events", "GroupedEventsPlugin") == "event_analysis"
        assert generator._detect_category("dataframe", "DataFramePlugin") == "data_export"
        # signal_peaks 匹配 "peak" 关键词，归类为 feature_extraction
        assert generator._detect_category("signal_peaks", "SignalPeaksPlugin") == "feature_extraction"
        # filtered_waveforms 匹配 "waveform" 关键词，归类为 waveform_processing
        assert generator._detect_category("filtered_waveforms", "FilteredWaveformsPlugin") == "waveform_processing"
        # 纯 filter 名称归类为 signal_processing
        assert generator._detect_category("lowpass_filter", "LowpassFilterPlugin") == "signal_processing"

    def test_accelerator_detection(self):
        """测试加速器检测"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()

        # CPU 插件
        assert generator._detect_accelerator(MockPlugin) == "cpu"

    def test_render_plugin_page(self):
        """测试渲染插件页面"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.register_plugin(MockPlugin)

        doc_info = generator.extract_doc_info(MockPlugin, MockPlugin())
        content = generator.render_plugin_page(doc_info)

        # 检查内容包含关键信息
        assert "MockPlugin" in content
        assert "mock_data" in content
        assert "1.2.3" in content
        assert "threshold" in content
        assert "Detection threshold" in content

    def test_render_index_page(self):
        """测试渲染索引页面"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.register_plugin(MockPlugin)

        doc_infos = generator.get_all_doc_info()
        content = generator.render_index_page(doc_infos)

        assert "MockPlugin" in content
        assert "mock_data" in content

    def test_generate_all_creates_files(self):
        """测试生成所有文档创建文件"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.register_plugin(MockPlugin)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            results = generator.generate_all(output_dir)

            # 检查生成的文件
            assert "mock_data" in results
            assert "INDEX" in results

            # 检查文件存在
            assert (output_dir / "mock_data.md").exists()
            assert (output_dir / "INDEX.md").exists()

            # 检查文件内容
            content = (output_dir / "mock_data.md").read_text()
            assert "MockPlugin" in content

    def test_load_builtin_plugins(self):
        """测试加载内置插件"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        count = generator.load_builtin_plugins()

        # 应该加载多个插件
        assert count > 0

        # 检查是否包含已知插件
        doc_infos = generator.get_all_doc_info()
        provides_list = [d.provides for d in doc_infos]

        # 检查一些已知的内置插件
        # 注意：具体插件名称可能因版本而异
        assert len(provides_list) > 0


class TestDocCoverageChecker:
    """测试 DocCoverageChecker"""

    def test_get_builtin_plugins(self):
        """测试获取内置插件"""
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker

        checker = DocCoverageChecker()
        plugins = checker.get_builtin_plugins()

        # 应该有多个内置插件
        assert len(plugins) > 0

        # 每个插件应该有 (类名, provides, 类) 三元组
        for plugin_name, provides, plugin_class in plugins:
            assert isinstance(plugin_name, str)
            assert isinstance(provides, str)
            assert hasattr(plugin_class, "compute")

    def test_check_coverage_missing_docs(self):
        """测试检查覆盖率（缺少文档）"""
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker

        with tempfile.TemporaryDirectory() as tmpdir:
            # 使用空目录作为文档目录
            checker = DocCoverageChecker(
                docs_dir=Path(tmpdir),
                auto_docs_dir=Path(tmpdir) / "auto",
            )

            report = checker.check_coverage()

            # 应该有缺失文档的错误
            assert report.total_plugins > 0
            assert report.documented_plugins == 0
            assert report.coverage_percent == 0.0
            assert not report.passed
            assert report.error_count > 0

    def test_check_coverage_all_documented(self):
        """测试检查覆盖率（全部文档化）"""
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            auto_docs_dir = Path(tmpdir) / "auto"
            auto_docs_dir.mkdir(parents=True)

            # 先生成所有文档
            generator = PluginDocGenerator()
            generator.load_builtin_plugins()
            generator.generate_all(auto_docs_dir)

            # 然后检查覆盖率
            checker = DocCoverageChecker(
                docs_dir=Path(tmpdir),
                auto_docs_dir=auto_docs_dir,
            )

            report = checker.check_coverage()

            # 应该全部通过
            assert report.coverage_percent == 100.0
            assert report.passed
            assert report.error_count == 0

    def test_check_spec_quality_warnings(self):
        """测试检查 spec 质量警告"""
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker

        checker = DocCoverageChecker()
        issues = checker.check_spec_quality(MockPluginNoDoc)

        # 应该有警告
        warning_messages = [i.message for i in issues if i.severity == "warning"]

        # 检查是否检测到缺少 help 的选项
        assert any("param" in msg and "help" in msg for msg in warning_messages)

        # 检查是否检测到缺少 output_dtype
        assert any("output_dtype" in msg for msg in warning_messages)

    def test_report_passed_property(self):
        """测试报告的 passed 属性"""
        from waveform_analysis.utils.doc_coverage import CoverageIssue, CoverageReport

        # 无问题的报告
        report_ok = CoverageReport(
            total_plugins=5,
            documented_plugins=5,
            coverage_percent=100.0,
            issues=[],
        )
        assert report_ok.passed

        # 只有警告的报告
        report_warning = CoverageReport(
            total_plugins=5,
            documented_plugins=5,
            coverage_percent=100.0,
            issues=[
                CoverageIssue(
                    plugin_name="Test",
                    provides="test",
                    severity="warning",
                    message="Missing help",
                )
            ],
        )
        assert report_warning.passed  # 警告不影响通过

        # 有错误的报告
        report_error = CoverageReport(
            total_plugins=5,
            documented_plugins=4,
            coverage_percent=80.0,
            issues=[
                CoverageIssue(
                    plugin_name="Test",
                    provides="test",
                    severity="error",
                    message="Missing documentation",
                )
            ],
        )
        assert not report_error.passed

    def test_print_report(self, capsys):
        """测试打印报告"""
        from waveform_analysis.utils.doc_coverage import (
            CoverageIssue,
            CoverageReport,
            DocCoverageChecker,
        )

        checker = DocCoverageChecker()

        report = CoverageReport(
            total_plugins=10,
            documented_plugins=8,
            coverage_percent=80.0,
            issues=[
                CoverageIssue(
                    plugin_name="TestPlugin",
                    provides="test_data",
                    severity="error",
                    message="Missing documentation file",
                )
            ],
            missing_provides={"test_data", "other_data"},
        )

        checker.print_report(report)

        captured = capsys.readouterr()
        assert "Coverage: 80.0%" in captured.out
        assert "FAILED" in captured.out
        assert "TestPlugin" in captured.out


class TestCLI:
    """测试 CLI 命令"""

    def test_cli_help(self):
        """测试 CLI 帮助"""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "waveform_analysis.utils.cli_docs", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "generate" in result.stdout
        assert "check" in result.stdout

    def test_cli_generate_plugins_auto(self):
        """测试 CLI 生成插件文档"""
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "waveform_analysis.utils.cli_docs",
                    "generate",
                    "plugins-auto",
                    "-o",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
            )

            # 检查是否成功
            assert result.returncode == 0
            assert "已加载" in result.stdout
            assert "已生成" in result.stdout

            # 检查文件是否生成
            output_dir = Path(tmpdir)
            assert (output_dir / "INDEX.md").exists()

    def test_cli_check_coverage(self):
        """测试 CLI 检查覆盖率"""
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            # 先生成文档
            subprocess.run(
                [
                    "python",
                    "-m",
                    "waveform_analysis.utils.cli_docs",
                    "generate",
                    "plugins-auto",
                    "-o",
                    str(Path(tmpdir) / "plugins" / "builtin" / "auto"),
                ],
                capture_output=True,
                text=True,
            )

            # 然后检查覆盖率
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "waveform_analysis.utils.cli_docs",
                    "check",
                    "coverage",
                    "-d",
                    tmpdir,
                ],
                capture_output=True,
                text=True,
            )

            # 检查输出
            assert "Coverage" in result.stdout
