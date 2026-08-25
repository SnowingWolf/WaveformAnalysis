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
from typing import Any

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


# These pages are deliberately hand-maintained migration references.  They
# live next to generated plugin pages for compatibility, but are not plugin
# coverage entries and therefore do not need generated frontmatter.
_LEGACY_REFERENCE_DOCS = frozenset({"s1_s2.md"})


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
    issues: list[CoverageIssue] = field(default_factory=list)
    documented_provides: set[str] = field(default_factory=set)
    missing_provides: set[str] = field(default_factory=set)
    stale_provides: set[str] = field(default_factory=set)
    extra_provides: set[str] = field(default_factory=set)
    filename_mismatches: dict[str, str] = field(default_factory=dict)

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
        docs_dir: Path | None = None,
        auto_docs_dir: Path | None = None,
        agent_docs_dir: Path | None = None,
    ):
        """初始化检查器

        Args:
            docs_dir: 文档根目录，默认为项目 docs/ 目录
            auto_docs_dir: 自动生成文档目录，默认为 docs/plugins/reference/builtin/auto/
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
            auto_docs_dir = self.docs_dir / "plugins" / "reference" / "builtin" / "auto"
        self.auto_docs_dir = Path(auto_docs_dir)

        if agent_docs_dir is None:
            agent_docs_dir = self.docs_dir / "plugins" / "reference" / "agent"
        self.agent_docs_dir = Path(agent_docs_dir)
        self._builtin_load_errors: list[tuple[str, str]] = []

    def get_builtin_plugins(self) -> list[tuple[str, str, type]]:
        """获取所有内置插件

        Returns:
            列表，每项为 (类名, provides, 类)
        """
        from waveform_analysis.core.plugins.builtin import cpu

        plugins = []
        self._builtin_load_errors = []
        seen_provides: set[str] = set()

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
                except Exception as exc:
                    self._builtin_load_errors.append((name, repr(exc)))

        return plugins

    def get_documented_plugins(self) -> set[str]:
        """获取 frontmatter 声明的已文档化插件 provides 名称。

        Returns:
            只信任 Markdown frontmatter 中的 ``provides``，不以文件名推断。
        """
        return {
            record["provides"]
            for record in self._documentation_records()
            if isinstance(record.get("provides"), str) and record["provides"]
        }

    def _documentation_records(self) -> list[dict[str, Any]]:
        """Read auto-generated Markdown metadata without inferring identity.

        Coverage must not silently turn a renamed or hand-copied file into a
        valid plugin page.  Every record therefore keeps the filename and the
        parsed frontmatter side by side so the checker can report both stale
        pages and filename/content mismatches.
        """

        records: list[dict[str, Any]] = []

        if not self.auto_docs_dir.exists():
            return records

        for md_file in sorted(self.auto_docs_dir.glob("*.md")):
            if md_file.name == "INDEX.md":
                continue
            if md_file.name in _LEGACY_REFERENCE_DOCS:
                continue
            record: dict[str, Any] = {
                "path": md_file,
                "filename": md_file.stem,
                "provides": None,
                "version": None,
                "error": None,
            }
            try:
                text = md_file.read_text(encoding="utf-8")
                lines = text.splitlines()
                if not lines or lines[0].strip() != "---":
                    record["error"] = "缺少 frontmatter（首行应为 ---）"
                else:
                    try:
                        end = next(
                            index
                            for index, line in enumerate(lines[1:], start=1)
                            if line.strip() == "---"
                        )
                    except StopIteration:
                        record["error"] = "frontmatter 未闭合"
                    else:
                        import yaml

                        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
                        if not isinstance(frontmatter, dict):
                            record["error"] = "frontmatter 必须是 mapping"
                        else:
                            record["provides"] = frontmatter.get("provides")
                            record["version"] = frontmatter.get("version")
                            if (
                                not isinstance(record["provides"], str)
                                or not record["provides"].strip()
                            ):
                                record["error"] = "frontmatter 缺少有效 provides"
            except Exception as exc:
                record["error"] = f"无法解析 frontmatter: {exc}"
            records.append(record)

        return records

    def check_spec_quality(self, plugin_class: type) -> list[CoverageIssue]:
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

        # Structured arrays use output_dtype; other result types use output_schema.
        output_dtype = getattr(instance, "output_dtype", None)
        output_schema = getattr(instance, "output_schema", None)
        if output_dtype is None and output_schema is None:
            issues.append(
                CoverageIssue(
                    plugin_name=plugin_name,
                    provides=provides,
                    severity="warning",
                    message="Missing output_dtype or output_schema",
                    category="spec_quality",
                )
            )

        return issues

    def _check_generated_content_quality(
        self,
        builtin_plugins: list[tuple[str, str, type]],
    ) -> list[CoverageIssue]:
        """Check generated Auto/Agent pages against current code-derived views.

        Coverage answers "does a page exist?".  This gate answers the more useful
        release question: "does the page still describe the current plugin contract,
        use non-empty narrative, and identify where that narrative came from?"  The
        comparison is deliberately exact because these two directories are generated
        artifacts, not hand-maintained prose.
        """

        from waveform_analysis.utils.plugin_doc_generator import (
            PluginDocGenerator,
            check_plugin_document_structure,
        )

        issues: list[CoverageIssue] = []
        generator = PluginDocGenerator()
        try:
            loaded = generator.load_builtin_plugins()
            if loaded != len(builtin_plugins):
                issues.append(
                    CoverageIssue(
                        plugin_name="PluginDocGenerator",
                        provides="*",
                        severity="error",
                        message=(
                            f"Generator loaded {loaded} builtin plugins but coverage found "
                            f"{len(builtin_plugins)}"
                        ),
                        category="extraction",
                    )
                )
            views = generator.get_all_doc_info()
        except Exception as exc:
            return [
                CoverageIssue(
                    plugin_name="PluginDocGenerator",
                    provides="*",
                    severity="error",
                    message=f"文档事实提取失败，禁止静默跳过插件: {exc}",
                    category="extraction",
                )
            ]

        by_provides = {view.provides: view for view in views}
        required_narrative = {
            "overview": lambda view: bool(view.overview or view.overview_paragraphs),
            "workflow_steps": lambda view: bool(view.workflow_steps),
            "behavior_notes": lambda view: bool(view.behavior_notes),
            "failure_modes": lambda view: bool(view.failure_modes),
            "usage_example": lambda view: bool(view.usage_example),
        }
        fallback_fragments = (
            "暂无插件说明",
            "暂无生产者说明",
            "暂无字段说明",
            "未声明字段含义",
            "未声明说明",
            "No description",
            "No documented",
            "placeholder",
            "TBD",
        )

        for plugin_name, provides, _plugin_class in builtin_plugins:
            view = by_provides.get(provides)
            if view is None:
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="error",
                        message="代码事实提取结果缺少该 builtin 插件",
                        category="extraction",
                    )
                )
                continue

            status = view.documentation_status
            source = getattr(status, "source", None)
            if source == "source_fallback":
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="error",
                        message=(
                            "已发布 AgentDoc 被拒绝，必须重新审核/发布；"
                            f"原因: {getattr(status, 'reason', '')}"
                        ),
                        category="source_drift",
                    )
                )
            if not view.source_fingerprint:
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="error",
                        message="无法取得插件源码 fingerprint",
                        category="provenance",
                    )
                )

            for field_name, predicate in required_narrative.items():
                if not predicate(view):
                    issues.append(
                        CoverageIssue(
                            plugin_name=plugin_name,
                            provides=provides,
                            severity="error",
                            message=f"生成模型缺少非空叙述字段: {field_name}",
                            category="content_quality",
                        )
                    )
            for option in view.config_options:
                if not (view.config_notes.get(option.name) or option.doc):
                    issues.append(
                        CoverageIssue(
                            plugin_name=plugin_name,
                            provides=provides,
                            severity="error",
                            message=f"配置选项缺少说明: {option.name}",
                            category="content_quality",
                        )
                    )
            for output_field in view.output_fields:
                if not (view.field_notes.get(output_field.name) or output_field.doc):
                    issues.append(
                        CoverageIssue(
                            plugin_name=plugin_name,
                            provides=provides,
                            severity="error",
                            message=f"输出字段缺少含义说明: {output_field.name}",
                            category="content_quality",
                        )
                    )
            if view.resolved_depends_on and any(
                not detail.description for detail in view.resolved_dependency_details
            ):
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="error",
                        message="解析后的依赖缺少生产者说明",
                        category="content_quality",
                    )
                )

            for profile, directory in (
                ("auto", self.auto_docs_dir),
                ("agent", self.agent_docs_dir),
            ):
                path = directory / f"{provides}.md"
                if not path.is_file():
                    issues.append(
                        CoverageIssue(
                            plugin_name=plugin_name,
                            provides=provides,
                            severity="error",
                            message=f"缺少 {profile} 生成页面: {path}",
                            category="generated_documentation",
                        )
                    )
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                    structure_errors = check_plugin_document_structure(content, profile)
                    for error in structure_errors:
                        issues.append(
                            CoverageIssue(
                                plugin_name=plugin_name,
                                provides=provides,
                                severity="error",
                                message=f"{profile} 页面结构错误: {error}",
                                category="generated_documentation",
                            )
                        )
                    expected = generator.render_plugin_page(view, profile=profile)
                    if content != expected:
                        issues.append(
                            CoverageIssue(
                                plugin_name=plugin_name,
                                provides=provides,
                                severity="error",
                                message=f"{profile} 页面与当前代码事实/模板不一致，请重新生成",
                                category="generated_drift",
                            )
                        )
                    for fragment in fallback_fragments:
                        if fragment.casefold() in content.casefold():
                            issues.append(
                                CoverageIssue(
                                    plugin_name=plugin_name,
                                    provides=provides,
                                    severity="error",
                                    message=f"{profile} 页面包含占位或空泛说明: {fragment}",
                                    category="content_quality",
                                )
                            )
                            break
                except OSError as exc:
                    issues.append(
                        CoverageIssue(
                            plugin_name=plugin_name,
                            provides=provides,
                            severity="error",
                            message=f"无法读取 {profile} 页面: {exc}",
                            category="generated_documentation",
                        )
                    )

        return issues

    def check_coverage(
        self,
        require_spec_quality: bool = False,
        require_content_quality: bool = False,
    ) -> CoverageReport:
        """检查文档覆盖率

        Args:
            require_spec_quality: 是否也检查 spec 质量
            require_content_quality: 是否校验 Auto/Agent 生成内容、源码 fingerprint 与叙述完整性

        Returns:
            覆盖报告
        """
        builtin_plugins = self.get_builtin_plugins()
        records = self._documentation_records()
        documented = {
            record["provides"]
            for record in records
            if isinstance(record.get("provides"), str) and record["provides"]
        }
        builtin_by_provides = {
            provides: (plugin_name, plugin_class)
            for plugin_name, provides, plugin_class in builtin_plugins
        }

        issues = []
        missing_provides = set()
        stale_provides: set[str] = set()
        extra_provides: set[str] = set()
        filename_mismatches: dict[str, str] = {}
        seen_provides: dict[str, Path] = {}

        for plugin_name, error in self._builtin_load_errors:
            issues.append(
                CoverageIssue(
                    plugin_name=plugin_name,
                    provides="unknown",
                    severity="error",
                    message=f"无法实例化 builtin 插件，不能静默跳过: {error}",
                    category="instantiation",
                )
            )

        for record in records:
            path = record["path"]
            provides = record.get("provides")
            if record.get("error"):
                issues.append(
                    CoverageIssue(
                        plugin_name=path.stem,
                        provides=str(provides or "unknown"),
                        severity="error",
                        message=str(record["error"]),
                        category="frontmatter",
                    )
                )
                continue
            if not isinstance(provides, str) or not provides:
                continue
            if provides in seen_provides:
                issues.append(
                    CoverageIssue(
                        plugin_name=path.stem,
                        provides=provides,
                        severity="error",
                        message=(
                            f"Duplicate documentation provides; first declared by "
                            f"{seen_provides[provides].name}"
                        ),
                        category="duplicate",
                    )
                )
            else:
                seen_provides[provides] = path
            if provides not in builtin_by_provides:
                extra_provides.add(provides)
                issues.append(
                    CoverageIssue(
                        plugin_name=path.stem,
                        provides=provides,
                        severity="error",
                        message=f"Documentation provides is not a builtin plugin: {provides}",
                        category="extra_documentation",
                    )
                )
                continue

            plugin_name, plugin_class = builtin_by_provides[provides]
            if path.stem != provides:
                filename_mismatches[path.name] = provides
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="error",
                        message=f"Filename/content mismatch: {path.name} declares provides {provides}",
                        category="filename_mismatch",
                    )
                )
            try:
                current_version = getattr(plugin_class(), "version", None)
            except Exception:
                current_version = None
            document_version = record.get("version")
            if current_version and str(document_version or "") != str(current_version):
                stale_provides.add(provides)
                issues.append(
                    CoverageIssue(
                        plugin_name=plugin_name,
                        provides=provides,
                        severity="error",
                        message=(
                            f"Stale documentation version: frontmatter has {document_version!r}, "
                            f"current plugin is {current_version!r}"
                        ),
                        category="stale_documentation",
                    )
                )

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

        if require_content_quality:
            issues.extend(self._check_generated_content_quality(builtin_plugins))

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
            stale_provides=stale_provides,
            extra_provides=extra_provides,
            filename_mismatches=filename_mismatches,
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

        if report.stale_provides:
            print("\nStale Documentation:")
            for provides in sorted(report.stale_provides):
                print(f"  - {provides}.md")

        if report.extra_provides:
            print("\nExtra Documentation:")
            for provides in sorted(report.extra_provides):
                print(f"  - {provides}.md")

        if report.filename_mismatches:
            print("\nFilename/Frontmatter Mismatches:")
            for filename, provides in sorted(report.filename_mismatches.items()):
                print(f"  - {filename} -> {provides}")

        print("\n" + "=" * 60)


@export
def check_and_report(
    docs_dir: Path | None = None,
    strict: bool = False,
    fail_on_warning: bool = False,
) -> bool:
    """便捷函数：检查覆盖率并打印报告

    Args:
        docs_dir: 文档目录
        strict: 是否检查 spec 质量与生成内容质量
        fail_on_warning: 是否在有警告时也失败

    Returns:
        是否通过检查
    """
    checker = DocCoverageChecker(docs_dir=docs_dir)
    report = checker.check_coverage(
        require_spec_quality=strict,
        require_content_quality=strict,
    )
    checker.print_report(report)

    if fail_on_warning:
        return len(report.issues) == 0
    return report.passed
