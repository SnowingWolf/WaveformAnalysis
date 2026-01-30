"""
文档覆盖检查器 - 检查插件文档覆盖率

本模块提供检查插件文档覆盖率的功能：
- CoverageIssue: 覆盖问题数据类
- CoverageReport: 覆盖报告数据类
- DocCoverageChecker: 文档覆盖检查器

用法:
    >>> from waveform_analysis.utils.doc_coverage import DocCoverageChecker
    >>> checker = DocCoverageChecker()
    >>> report = checker.check_coverage()
    >>> checker.print_report(report)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
@dataclass
class CoverageIssue:
    """文档覆盖问题

    Attributes:
        plugin_name: 插件类名
        provides: 插件提供的数据名
        severity: 严重程度 ("error" | "warning")
        message: 问题描述
        category: 问题类别
    """

    plugin_name: str
    provides: str
    severity: str  # "error" | "warning"
    message: str
    category: str = "documentation"


@export
@dataclass
class CoverageReport:
    """文档覆盖报告

    Attributes:
        total_plugins: 总插件数
        documented_plugins: 已文档化的插件数
        coverage_percent: 覆盖率百分比
        issues: 问题列表
        documented_provides: 已文档化的 provides 集合
        missing_provides: 缺少文档的 provides 集合
    """

    total_plugins: int
    documented_plugins: int
    coverage_percent: float
    issues: List[CoverageIssue] = field(default_factory=list)
    documented_provides: Set[str] = field(default_factory=set)
    missing_provides: Set[str] = field(default_factory=set)

    @property
    def passed(self) -> bool:
        """检查是否通过（无 error 级别问题）"""
        return not any(i.severity == "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        """错误数量"""
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        """警告数量"""
        return sum(1 for i in self.issues if i.severity == "warning")


@export
class DocCoverageChecker:
    """文档覆盖检查器

    检查所有内置插件是否有对应的文档文件。

    Attributes:
        docs_dir: 文档目录路径
        auto_docs_dir: 自动生成文档目录路径

    Examples:
        >>> checker = DocCoverageChecker()
        >>> report = checker.check_coverage()
        >>> if not report.passed:
        ...     checker.print_report(report)
        ...     sys.exit(1)
    """

    def __init__(
        self,
        docs_dir: Optional[Path] = None,
        auto_docs_dir: Optional[Path] = None,
    ):
        """初始化检查器

        Args:
            docs_dir: 文档根目录，默认为项目 docs/ 目录
            auto_docs_dir: 自动生成文档目录，默认为 docs/plugins/builtin/auto/
        """
        if docs_dir is None:
            # 尝试找到项目根目录
            current = Path(__file__).parent
            while current.parent != current:
                if (current / "docs").exists():
                    docs_dir = current / "docs"
                    break
                current = current.parent
            if docs_dir is None:
                docs_dir = Path("docs")

        self.docs_dir = Path(docs_dir)

        if auto_docs_dir is None:
            auto_docs_dir = self.docs_dir / "plugins" / "builtin" / "auto"
        self.auto_docs_dir = Path(auto_docs_dir)

    def get_builtin_plugins(self) -> List[Tuple[str, str, Type]]:
        """获取所有内置插件

        Returns:
            列表，每项为 (类名, provides, 类)
        """
        from waveform_analysis.core.plugins.builtin import cpu

        plugins = []
        seen_provides: Set[str] = set()

        for name in cpu.__all__:
            obj = getattr(cpu, name, None)
            if obj is None:
                continue
            # 检查是否是 Plugin 子类
            if isinstance(obj, type) and hasattr(obj, "provides") and hasattr(obj, "compute"):
                try:
                    instance = obj()
                    provides = getattr(instance, "provides", None)
                    if provides and provides not in seen_provides:
                        plugins.append((name, provides, obj))
                        seen_provides.add(provides)
                except Exception:
                    # 跳过无法实例化的插件
                    pass

        return plugins

    def get_documented_plugins(self) -> Set[str]:
        """获取已文档化的插件（provides 名称）

        Returns:
            已文档化的 provides 集合
        """
        documented = set()

        if not self.auto_docs_dir.exists():
            return documented

        for md_file in self.auto_docs_dir.glob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            # 文件名即为 provides 名称
            provides = md_file.stem
            documented.add(provides)

        return documented

    def check_spec_quality(self, plugin_class: Type) -> List[CoverageIssue]:
        """检查插件 spec 质量

        Args:
            plugin_class: 插件类

        Returns:
            问题列表
        """
        issues = []

        try:
            instance = plugin_class()
        except Exception as e:
            issues.append(
                CoverageIssue(
                    plugin_name=plugin_class.__name__,
                    provides="unknown",
                    severity="error",
                    message=f"Cannot instantiate plugin: {e}",
                    category="instantiation",
                )
            )
            return issues

        provides = getattr(instance, "provides", "unknown")
        plugin_name = plugin_class.__name__

        # 检查 description
        description = getattr(instance, "description", "")
        if not description and not plugin_class.__doc__:
            issues.append(
                CoverageIssue(
                    plugin_name=plugin_name,
                    provides=provides,
                    severity="warning",
                    message="Missing description or docstring",
                    category="spec_quality",
                )
            )

        # 检查 version
        version = getattr(instance, "version", None)
        if not version or version == "0.0.0":
            issues.append(
                CoverageIssue(
                    plugin_name=plugin_name,
                    provides=provides,
                    severity="warning",
                    message="Missing or default version (0.0.0)",
                    category="spec_quality",
                )
            )

        # 检查 options 的 help 字段
        options = getattr(instance, "options", {})
        for opt_name, opt in options.items():
            help_text = getattr(opt, "help", None)
            if not help_text:
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="warning",
                        message=f"Option '{opt_name}' missing help text",
                        category="spec_quality",
                    )
                )

        # 检查 output_dtype
        output_dtype = getattr(instance, "output_dtype", None)
        if output_dtype is None:
            issues.append(
                CoverageIssue(
                    plugin_name=plugin_name,
                    provides=provides,
                    severity="warning",
                    message="Missing output_dtype",
                    category="spec_quality",
                )
            )

        return issues

    def check_coverage(self, require_spec_quality: bool = False) -> CoverageReport:
        """检查文档覆盖率

        Args:
            require_spec_quality: 是否也检查 spec 质量

        Returns:
            覆盖报告
        """
        builtin_plugins = self.get_builtin_plugins()
        documented = self.get_documented_plugins()

        issues = []
        missing_provides = set()

        for plugin_name, provides, plugin_class in builtin_plugins:
            # 检查文档是否存在
            if provides not in documented:
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="error",
                        message=f"Missing documentation file: {provides}.md",
                        category="documentation",
                    )
                )
                missing_provides.add(provides)

            # 检查 spec 质量
            if require_spec_quality:
                spec_issues = self.check_spec_quality(plugin_class)
                issues.extend(spec_issues)

        # 计算覆盖率
        total = len(builtin_plugins)
        documented_count = total - len(missing_provides)
        coverage_percent = (documented_count / total * 100) if total > 0 else 100.0

        return CoverageReport(
            total_plugins=total,
            documented_plugins=documented_count,
            coverage_percent=coverage_percent,
            issues=issues,
            documented_provides=documented,
            missing_provides=missing_provides,
        )

    def print_report(self, report: CoverageReport, verbose: bool = True) -> None:
        """打印覆盖报告

        Args:
            report: 覆盖报告
            verbose: 是否显示详细信息
        """
        # 标题
        print("\n" + "=" * 60)
        print("Documentation Coverage Report")
        print("=" * 60)

        # 摘要
        status = "✅ PASSED" if report.passed else "❌ FAILED"
        print(f"\nStatus: {status}")
        print(f"Coverage: {report.coverage_percent:.1f}%")
        print(f"Total Plugins: {report.total_plugins}")
        print(f"Documented: {report.documented_plugins}")
        print(f"Errors: {report.error_count}")
        print(f"Warnings: {report.warning_count}")

        # 详细问题
        if verbose and report.issues:
            print("\n" + "-" * 60)
            print("Issues:")
            print("-" * 60)

            # 按严重程度分组
            errors = [i for i in report.issues if i.severity == "error"]
            warnings = [i for i in report.issues if i.severity == "warning"]

            if errors:
                print("\n❌ Errors:")
                for issue in errors:
                    print(f"  [{issue.category}] {issue.plugin_name} ({issue.provides})")
                    print(f"    → {issue.message}")

            if warnings:
                print("\n⚠️  Warnings:")
                for issue in warnings:
                    print(f"  [{issue.category}] {issue.plugin_name} ({issue.provides})")
                    print(f"    → {issue.message}")

        # 缺失文档列表
        if report.missing_provides:
            print("\n" + "-" * 60)
            print("Missing Documentation:")
            print("-" * 60)
            for provides in sorted(report.missing_provides):
                print(f"  - {provides}.md")

        print("\n" + "=" * 60)


@export
def check_and_report(
    docs_dir: Optional[Path] = None,
    strict: bool = False,
    fail_on_warning: bool = False,
) -> bool:
    """便捷函数：检查覆盖率并打印报告

    Args:
        docs_dir: 文档目录
        strict: 是否检查 spec 质量
        fail_on_warning: 是否在有警告时也失败

    Returns:
        是否通过检查
    """
    checker = DocCoverageChecker(docs_dir=docs_dir)
    report = checker.check_coverage(require_spec_quality=strict)
    checker.print_report(report)

    if fail_on_warning:
        return len(report.issues) == 0
    return report.passed
