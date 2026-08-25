"""
测试文档生成器和覆盖检查器

测试内容：
- PluginDocGenerator: 文档生成器
- DocCoverageChecker: 文档覆盖检查器
"""

from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest
import yaml

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
        threshold_opt = next((o for o in doc_info.config_options if o.name == "threshold"), None)
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

    def test_output_field_notes_are_rendered_from_dtype_metadata(self):
        """Bundled dtype metadata must replace the generated fallback text."""
        from waveform_analysis.core.plugins.builtin.cpu.peak_classification import (
            PeakClassificationPlugin,
        )
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        plugin = PeakClassificationPlugin()
        doc_info = generator.extract_doc_info(type(plugin), plugin)
        fields = {field.name: field for field in doc_info.output_fields}

        assert fields["peak_id"].doc.startswith("Zero-based index")
        assert doc_info.field_notes["peak_id"].startswith("Zero-based index")
        assert fields["label"].doc.startswith("Classification code")

        html = generator.render_plugin_html(doc_info)
        assert "No field description available." not in html
        assert "Classification code: 0=unknown, 1=S1, 2=S2, 3=S1_S2" in html

    def test_bundled_dtype_field_notes_cover_registered_output_fields(self):
        """Every registered output field has one bundled source-reviewed narrative."""
        from waveform_analysis.documentation.field_notes import load_dtype_field_notes
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.load_builtin_plugins()
        notes = load_dtype_field_notes()

        for doc_info in generator.get_all_doc_info():
            expected = {field.name for field in doc_info.output_fields}
            assert set(notes[doc_info.provides]) == expected

    def test_bundled_dtype_field_notes_have_no_duplicate_yaml_keys(self):
        """YAML parsing must not silently discard a duplicated field narrative."""
        from importlib.resources import files

        root = files("waveform_analysis.documentation")
        tree = yaml.compose(
            root.joinpath("dtype_field_notes.yaml").read_text(encoding="utf-8"),
            Loader=yaml.SafeLoader,
        )

        def duplicate_paths(node, path=""):
            if isinstance(node, yaml.MappingNode):
                keys = [key.value for key, _ in node.value]
                duplicates = {key for key in keys if keys.count(key) > 1}
                assert not duplicates, f"duplicate YAML keys at {path or '<root>'}: {duplicates}"
                for key, value in node.value:
                    duplicate_paths(value, f"{path}.{key.value}" if path else key.value)
            elif isinstance(node, yaml.SequenceNode):
                for index, value in enumerate(node.value):
                    duplicate_paths(value, f"{path}[{index}]")

        assert tree is not None
        duplicate_paths(tree)

    def test_category_detection(self):
        """测试类别检测"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()

        # 测试不同的 provides 名称
        assert generator._detect_category("raw_files", "RawFilesPlugin") == "data_loading"
        assert generator._detect_category("waveforms", "WaveformsPlugin") == "waveform_processing"
        assert (
            generator._detect_category("basic_features", "BasicFeaturesPlugin")
            == "feature_extraction"
        )
        assert (
            generator._detect_category("grouped_events", "GroupedEventsPlugin") == "event_analysis"
        )
        assert generator._detect_category("dataframe", "DataFramePlugin") == "data_export"
        # signal_peaks 匹配 "peak" 关键词，归类为 feature_extraction
        assert (
            generator._detect_category("signal_peaks", "SignalPeaksPlugin") == "feature_extraction"
        )
        # filtered_waveforms 匹配 "waveform" 关键词，归类为 waveform_processing
        assert (
            generator._detect_category("filtered_waveforms", "FilteredWaveformsPlugin")
            == "waveform_processing"
        )
        # 纯 filter 名称归类为 signal_processing
        assert (
            generator._detect_category("lowpass_filter", "LowpassFilterPlugin")
            == "signal_processing"
        )
        # peaklet 系列插件归入 Peaks 集合（功能域: Peaks）
        assert generator._detect_category("peaklets", "PeakletPlugin") == "peaks"
        assert (
            generator._detect_category("peaklet_components", "PeakletComponentsPlugin") == "peaks"
        )
        assert generator._detect_category("peaklet_waveforms", "PeakletWaveformPlugin") == "peaks"
        assert (
            generator._detect_category("peaklet_waveform_pool", "PeakletWaveformPoolPlugin")
            == "peaks"
        )
        assert generator._detect_category("peaklet_features", "PeakletFeaturesPlugin") == "peaks"
        assert generator._detect_category("peaklet_channels", "PeakletChannelsPlugin") == "peaks"

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

    def test_render_plugin_page_uses_custom_usage_example(self):
        """Plugins can replace the generic registration example when dependencies require it."""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        class CustomUsagePlugin(MockPlugin):
            provides = "custom_usage"
            doc_usage_example = """
            ctx.register(*complete_plugin_set())
            data = ctx.get_data("run_001", "custom_usage")
            """

        generator = PluginDocGenerator()
        doc_info = generator.extract_doc_info(CustomUsagePlugin, CustomUsagePlugin())
        content = generator.render_plugin_page(doc_info)

        assert "ctx.register(*complete_plugin_set())" in content
        assert "ctx.register(CustomUsagePlugin())" not in content

    def test_render_index_page(self):
        """测试渲染索引页面"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.register_plugin(MockPlugin)

        doc_infos = generator.get_all_doc_info()
        content = generator.render_index_page(doc_infos)

        assert "MockPlugin" in content
        assert "mock_data" in content

    def test_render_agent_plugin_page(self):
        """测试渲染 agent 插件页面"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        doc_info = generator.extract_doc_info(MockPlugin, MockPlugin())
        content = generator.render_plugin_page(doc_info, profile="agent")

        assert 'profile: "agent"' in content
        assert "## Operational Notes" in content
        assert "### Change Playbook" in content
        assert "mock_data" in content

    def test_render_agent_index_page(self):
        """测试渲染 agent 索引页面"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.register_plugin(MockPlugin)

        doc_infos = generator.get_all_doc_info()
        content = generator.render_index_page(doc_infos, profile="agent")

        assert "Agent Plugin Reference" in content
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

    def test_generate_all_agent_creates_files(self):
        """测试生成 agent 文档创建文件"""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.register_plugin(MockPlugin)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            results = generator.generate_all(output_dir, profile="agent")

            assert "mock_data" in results
            assert "INDEX" in results
            assert (output_dir / "mock_data.md").exists()
            assert (output_dir / "INDEX.md").exists()

            content = (output_dir / "mock_data.md").read_text()
            assert 'profile: "agent"' in content
            assert "## Maintenance" in content

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

    def test_dynamic_dependency_view_preserves_declared_and_resolved_contracts(self):
        """Dynamic plugins expose both their declaration and the documentation profile result."""
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        generator = PluginDocGenerator()
        generator.load_builtin_plugins()
        view = next(
            item for item in generator.get_all_doc_info() if item.provides == "hit_threshold"
        )

        assert view.depends_on == []
        assert view.resolved_depends_on == [
            "records",
            "wave_pool",
            "records_asymmetry_mask",
        ]
        assert view.dependency_profile == "documentation-default-v1"
        assert "wave_source" in view.dependency_config_keys
        assert "asymmetry_cut_enabled" in view.dependency_config_keys
        assert view.source_fingerprint


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

    def test_strict_content_quality_detects_generated_drift(self, tmp_path):
        """Strict coverage must catch a stale generated page, not just missing files."""
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker

        repository_root = Path(__file__).parents[1]
        auto_docs = tmp_path / "auto"
        agent_docs = tmp_path / "agent"
        shutil.copytree(repository_root / "docs/plugins/reference/builtin/auto", auto_docs)
        shutil.copytree(repository_root / "docs/plugins/reference/agent", agent_docs)
        stale_page = auto_docs / "hit_threshold.md"
        stale_page.write_text(
            stale_page.read_text(encoding="utf-8").replace(
                "source_fingerprint:", "source_fingerprint: stale-marker\n# source_fingerprint:"
            ),
            encoding="utf-8",
        )

        checker = DocCoverageChecker(
            docs_dir=tmp_path,
            auto_docs_dir=auto_docs,
            agent_docs_dir=agent_docs,
        )
        report = checker.check_coverage(
            require_spec_quality=True,
            require_content_quality=True,
        )

        assert not report.passed
        assert any(
            issue.provides == "hit_threshold" and issue.category == "generated_drift"
            for issue in report.issues
        )

    def test_coverage_uses_frontmatter_identity_and_reports_drift(self):
        """Filename-only copies must not silently satisfy plugin coverage."""
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker

        with tempfile.TemporaryDirectory() as tmpdir:
            auto_docs_dir = Path(tmpdir) / "auto"
            auto_docs_dir.mkdir(parents=True)
            (auto_docs_dir / "renamed.md").write_text(
                "---\nprovides: mock_data\nversion: 0.0.1\n---\n# mock_data\n",
                encoding="utf-8",
            )
            (auto_docs_dir / "removed.md").write_text(
                "---\nprovides: removed_plugin\nversion: 1.0.0\n---\n# removed_plugin\n",
                encoding="utf-8",
            )

            checker = DocCoverageChecker(
                docs_dir=Path(tmpdir),
                auto_docs_dir=auto_docs_dir,
            )
            checker.get_builtin_plugins = lambda: [("MockPlugin", "mock_data", MockPlugin)]

            report = checker.check_coverage()

            assert report.coverage_percent == 100.0
            assert report.stale_provides == {"mock_data"}
            assert report.extra_provides == {"removed_plugin"}
            assert report.filename_mismatches == {"renamed.md": "mock_data"}
            assert {issue.category for issue in report.issues} >= {
                "stale_documentation",
                "extra_documentation",
                "filename_mismatch",
            }
            assert not report.passed

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

    def test_cli_help(self, monkeypatch, capsys):
        """测试 CLI 帮助"""
        from waveform_analysis.utils import cli_docs

        monkeypatch.setattr("sys.argv", ["waveform-docs", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            cli_docs.main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "generate" in captured.out
        assert "check" in captured.out

    @pytest.mark.slow
    def test_cli_generate_plugins_auto(self, monkeypatch, capsys):
        """测试 CLI 生成插件文档"""
        from waveform_analysis.utils import cli_docs

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr(
                "sys.argv",
                ["waveform-docs", "generate", "plugins-auto", "-o", tmpdir],
            )
            result = cli_docs.main()
            captured = capsys.readouterr()

            assert result == 0
            assert "已加载" in captured.out
            assert "已生成" in captured.out

            output_dir = Path(tmpdir)
            assert (output_dir / "INDEX.md").exists()

    @pytest.mark.slow
    def test_cli_check_coverage(self, monkeypatch, capsys):
        """测试 CLI 检查覆盖率"""
        from waveform_analysis.utils import cli_docs

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "plugins" / "builtin" / "auto"
            monkeypatch.setattr(
                "sys.argv",
                ["waveform-docs", "generate", "plugins-auto", "-o", str(output_dir)],
            )
            assert cli_docs.main() == 0
            _ = capsys.readouterr()

            monkeypatch.setattr(
                "sys.argv",
                ["waveform-docs", "check", "coverage", "-d", tmpdir],
            )
            result = cli_docs.main()
            captured = capsys.readouterr()

            assert result in (0, 1)
            assert "Coverage" in captured.out

    def test_cli_check_coverage_uses_warning_exit_code(self, monkeypatch):
        """Warning-only quality results use the shared exit code 2."""
        from waveform_analysis.utils import cli_docs, doc_coverage

        report = doc_coverage.CoverageReport(
            total_plugins=1,
            documented_plugins=1,
            coverage_percent=100.0,
            issues=[
                doc_coverage.CoverageIssue(
                    plugin_name="MockPlugin",
                    provides="mock_data",
                    severity="warning",
                    message="spec warning",
                )
            ],
        )

        class StubChecker:
            def __init__(self, **_kwargs):
                pass

            def check_coverage(self, **_kwargs):
                return report

            def print_report(self, _report):
                pass

        monkeypatch.setattr(doc_coverage, "DocCoverageChecker", StubChecker)
        monkeypatch.setattr(
            "sys.argv",
            ["waveform-docs", "check", "coverage"],
        )

        assert cli_docs.main() == cli_docs.EXIT_OK

        monkeypatch.setattr(
            "sys.argv",
            ["waveform-docs", "check", "coverage", "--fail-on-warning"],
        )
        assert cli_docs.main() == cli_docs.EXIT_WARNING
