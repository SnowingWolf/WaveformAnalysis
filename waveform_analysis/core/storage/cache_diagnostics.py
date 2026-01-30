"""
缓存诊断模块 - 问题诊断与修复工具。

提供缓存完整性检查、问题诊断和自动修复功能。
"""

from dataclasses import dataclass, field
from enum import Enum
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..foundation.utils import exporter
from .cache_analyzer import CacheAnalyzer, CacheEntry

if TYPE_CHECKING:
    pass

export, __all__ = exporter()


@export
class DiagnosticIssueType(Enum):
    """诊断问题类型枚举"""

    VERSION_MISMATCH = "version_mismatch"  # 插件版本不匹配
    MISSING_METADATA = "missing_metadata"  # 元数据文件缺失
    MISSING_DATA_FILE = "missing_data_file"  # 数据文件缺失
    SIZE_MISMATCH = "size_mismatch"  # 文件大小不匹配
    CHECKSUM_FAILED = "checksum_failed"  # 校验和验证失败
    ORPHAN_FILE = "orphan_file"  # 孤儿文件（无元数据）
    STORAGE_VERSION_MISMATCH = "storage_version"  # 存储版本不匹配
    CORRUPTED_METADATA = "corrupted_metadata"  # 元数据损坏
    DTYPE_MISMATCH = "dtype_mismatch"  # 数据类型不匹配


@export
@dataclass
class DiagnosticIssue:
    """诊断问题数据类

    Attributes:
        issue_type: 问题类型
        severity: 严重程度 ('error', 'warning', 'info')
        run_id: 运行标识符
        data_name: 数据名称（可为空）
        key: 缓存键
        description: 问题描述
        details: 详细信息字典
        fixable: 是否可自动修复
        fix_action: 修复动作描述
    """

    issue_type: DiagnosticIssueType
    severity: str  # 'error', 'warning', 'info'
    run_id: str
    data_name: Optional[str]
    key: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    fixable: bool = False
    fix_action: Optional[str] = None

    def __str__(self) -> str:
        severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "?")
        return f"{severity_icon} [{self.issue_type.value}] {self.description}"


@export
class CacheDiagnostics:
    """缓存诊断工具

    提供缓存完整性检查、问题诊断和自动修复功能。

    Features:
        - 版本不匹配检测
        - 孤儿文件检测
        - 数据完整性验证
        - 自动修复（支持 dry-run）

    Examples:
        >>> analyzer = CacheAnalyzer(ctx)
        >>> analyzer.scan()
        >>>
        >>> diag = CacheDiagnostics(analyzer)
        >>> issues = diag.diagnose()
        >>> diag.print_report(issues)
        >>>
        >>> # 自动修复（先 dry-run）
        >>> result = diag.auto_fix(issues, dry_run=True)
        >>> print(f"将修复 {result['would_fix']} 个问题")
    """

    def __init__(self, analyzer: CacheAnalyzer):
        """初始化 CacheDiagnostics

        Args:
            analyzer: CacheAnalyzer 实例（需要已完成扫描）
        """
        self.analyzer = analyzer
        self.ctx = analyzer.ctx

    @property
    def storage(self):
        """获取存储实例"""
        return self.ctx.storage

    def diagnose(
        self,
        run_id: Optional[str] = None,
        check_integrity: bool = True,
        check_orphans: bool = True,
        check_versions: bool = True,
        verbose: bool = True,
    ) -> List[DiagnosticIssue]:
        """执行完整诊断

        Args:
            run_id: 仅诊断指定 run，None 则诊断所有
            check_integrity: 是否检查数据完整性
            check_orphans: 是否检查孤儿文件
            check_versions: 是否检查版本不匹配
            verbose: 是否显示进度

        Returns:
            诊断问题列表
        """
        issues: List[DiagnosticIssue] = []

        if verbose:
            print("[CacheDiagnostics] 开始诊断...")

        # 获取要检查的条目
        entries = self.analyzer.get_entries(run_id=run_id)

        if verbose:
            print(f"  检查 {len(entries)} 个缓存条目...")

        # 检查每个条目
        for entry in entries:
            # 版本检查
            if check_versions:
                issue = self.check_version_mismatch(entry)
                if issue:
                    issues.append(issue)

            # 完整性检查
            if check_integrity:
                integrity_issues = self.check_integrity(entry)
                issues.extend(integrity_issues)

        # 检查孤儿文件
        if check_orphans:
            if run_id:
                orphan_issues = self.find_orphan_files(run_id)
            else:
                orphan_issues = []
                for r in self.analyzer.get_all_runs():
                    orphan_issues.extend(self.find_orphan_files(r))
            issues.extend(orphan_issues)

        if verbose:
            error_count = sum(1 for i in issues if i.severity == "error")
            warning_count = sum(1 for i in issues if i.severity == "warning")
            info_count = sum(1 for i in issues if i.severity == "info")
            print(
                f"[CacheDiagnostics] 诊断完成: {error_count} 错误, "
                f"{warning_count} 警告, {info_count} 信息"
            )

        return issues

    def check_version_mismatch(self, entry: CacheEntry) -> Optional[DiagnosticIssue]:
        """检查插件版本不匹配

        Args:
            entry: 缓存条目

        Returns:
            DiagnosticIssue 或 None
        """
        # 获取当前插件版本
        if not hasattr(self.ctx, "_plugins") or entry.data_name not in self.ctx._plugins:
            return None

        plugin = self.ctx._plugins[entry.data_name]
        current_version = str(getattr(plugin, "version", "unknown"))

        if entry.plugin_version != current_version and entry.plugin_version != "unknown":
            return DiagnosticIssue(
                issue_type=DiagnosticIssueType.VERSION_MISMATCH,
                severity="warning",
                run_id=entry.run_id,
                data_name=entry.data_name,
                key=entry.key,
                description=f"插件版本不匹配: 缓存={entry.plugin_version}, 当前={current_version}",
                details={
                    "cached_version": entry.plugin_version,
                    "current_version": current_version,
                },
                fixable=True,
                fix_action="删除缓存，重新计算",
            )

        return None

    def check_integrity(self, entry: CacheEntry) -> List[DiagnosticIssue]:
        """检查单个条目的完整性

        Args:
            entry: 缓存条目

        Returns:
            诊断问题列表
        """
        issues = []

        # 检查数据文件是否存在
        if not os.path.exists(entry.file_path):
            issues.append(
                DiagnosticIssue(
                    issue_type=DiagnosticIssueType.MISSING_DATA_FILE,
                    severity="error",
                    run_id=entry.run_id,
                    data_name=entry.data_name,
                    key=entry.key,
                    description=f"数据文件缺失: {entry.file_path}",
                    details={"file_path": entry.file_path},
                    fixable=True,
                    fix_action="删除孤立的元数据文件",
                )
            )
            return issues

        # 检查存储版本
        storage_version = entry.metadata.get("storage_version")
        if storage_version and hasattr(self.storage, "STORAGE_VERSION"):
            valid_versions = [self.storage.STORAGE_VERSION, "1.0.0"]
            if storage_version not in valid_versions:
                issues.append(
                    DiagnosticIssue(
                        issue_type=DiagnosticIssueType.STORAGE_VERSION_MISMATCH,
                        severity="warning",
                        run_id=entry.run_id,
                        data_name=entry.data_name,
                        key=entry.key,
                        description=f"存储版本不匹配: {storage_version}",
                        details={
                            "cached_version": storage_version,
                            "expected_versions": valid_versions,
                        },
                        fixable=True,
                        fix_action="删除缓存，重新计算",
                    )
                )

        # 检查文件大小（仅对非压缩数据）
        if not entry.compressed:
            actual_size = os.path.getsize(entry.file_path)
            expected_size = entry.size_bytes
            if expected_size > 0 and actual_size != expected_size:
                issues.append(
                    DiagnosticIssue(
                        issue_type=DiagnosticIssueType.SIZE_MISMATCH,
                        severity="error",
                        run_id=entry.run_id,
                        data_name=entry.data_name,
                        key=entry.key,
                        description=f"文件大小不匹配: 实际={actual_size}, 期望={expected_size}",
                        details={
                            "actual_size": actual_size,
                            "expected_size": expected_size,
                        },
                        fixable=True,
                        fix_action="删除损坏的缓存",
                    )
                )

        # 检查校验和（如果有）
        if entry.has_checksum and self.storage.verify_on_load:
            checksum_issue = self._verify_checksum(entry)
            if checksum_issue:
                issues.append(checksum_issue)

        return issues

    def _verify_checksum(self, entry: CacheEntry) -> Optional[DiagnosticIssue]:
        """验证校验和

        Args:
            entry: 缓存条目

        Returns:
            DiagnosticIssue 或 None
        """
        expected_checksum = entry.metadata.get("checksum")
        algorithm = entry.metadata.get("checksum_algorithm", "xxhash64")

        if not expected_checksum:
            return None

        try:
            from .integrity import get_integrity_checker

            checker = get_integrity_checker()

            if not checker.verify_checksum(entry.file_path, expected_checksum, algorithm):
                return DiagnosticIssue(
                    issue_type=DiagnosticIssueType.CHECKSUM_FAILED,
                    severity="error",
                    run_id=entry.run_id,
                    data_name=entry.data_name,
                    key=entry.key,
                    description="校验和验证失败，数据可能已损坏",
                    details={
                        "expected_checksum": expected_checksum,
                        "algorithm": algorithm,
                    },
                    fixable=True,
                    fix_action="删除损坏的缓存",
                )
        except Exception as e:
            return DiagnosticIssue(
                issue_type=DiagnosticIssueType.CHECKSUM_FAILED,
                severity="warning",
                run_id=entry.run_id,
                data_name=entry.data_name,
                key=entry.key,
                description=f"校验和验证出错: {e}",
                details={"error": str(e)},
                fixable=False,
                fix_action=None,
            )

        return None

    def find_orphan_files(self, run_id: str) -> List[DiagnosticIssue]:
        """查找孤儿文件（有数据文件但无元数据）

        Args:
            run_id: 运行标识符

        Returns:
            孤儿文件问题列表
        """
        issues = []

        # 获取数据目录
        if hasattr(self.storage, "get_run_data_dir"):
            data_dir = self.storage.get_run_data_dir(run_id)
        elif hasattr(self.storage, "base_dir"):
            if hasattr(self.storage, "use_run_subdirs") and self.storage.use_run_subdirs:
                data_dir = os.path.join(self.storage.work_dir, run_id, self.storage.data_subdir)
            else:
                data_dir = self.storage.base_dir
        else:
            return issues

        if not os.path.exists(data_dir):
            return issues

        # 扫描数据文件
        data_extensions = {".bin", ".blosc2", ".lz4", ".zst", ".gz", ".parquet"}

        for filename in os.listdir(data_dir):
            # 检查是否是数据文件
            name, ext = os.path.splitext(filename)
            if ext not in data_extensions:
                continue

            # 处理压缩文件的双扩展名（如 .bin.blosc2）
            if ext in {".blosc2", ".lz4", ".zst", ".gz"}:
                base_name, _ = os.path.splitext(name)
                key = base_name
            else:
                key = name

            # 检查是否有对应的元数据
            meta_path = os.path.join(data_dir, f"{key}.json")
            if not os.path.exists(meta_path):
                file_path = os.path.join(data_dir, filename)
                file_size = os.path.getsize(file_path)

                issues.append(
                    DiagnosticIssue(
                        issue_type=DiagnosticIssueType.ORPHAN_FILE,
                        severity="warning",
                        run_id=run_id,
                        data_name=None,
                        key=key,
                        description=f"孤儿文件（无元数据）: {filename}",
                        details={
                            "file_path": file_path,
                            "file_size": file_size,
                            "file_size_human": self._format_size(file_size),
                        },
                        fixable=True,
                        fix_action="删除孤儿文件",
                    )
                )

        return issues

    def print_report(
        self, issues: List[DiagnosticIssue], group_by: str = "severity", show_fixable: bool = True
    ):
        """打印诊断报告

        Args:
            issues: 诊断问题列表
            group_by: 分组方式 ('severity', 'type', 'run_id')
            show_fixable: 是否显示可修复信息
        """
        if not issues:
            print("\n✓ 缓存诊断完成，未发现问题")
            return

        print("\n" + "=" * 70)
        print("缓存诊断报告")
        print("=" * 70)

        # 统计
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        info_count = sum(1 for i in issues if i.severity == "info")
        fixable_count = sum(1 for i in issues if i.fixable)

        print(f"\n总计: {len(issues)} 个问题")
        print(f"  ❌ 错误: {error_count}")
        print(f"  ⚠️  警告: {warning_count}")
        print(f"  ℹ️  信息: {info_count}")
        if show_fixable:
            print(f"  🔧 可自动修复: {fixable_count}")

        print("\n" + "-" * 70)

        # 分组显示
        if group_by == "severity":
            for severity in ["error", "warning", "info"]:
                severity_issues = [i for i in issues if i.severity == severity]
                if severity_issues:
                    icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[severity]
                    print(f"\n{icon} {severity.upper()} ({len(severity_issues)})")
                    for issue in severity_issues:
                        self._print_issue(issue, show_fixable)

        elif group_by == "type":
            types = {i.issue_type for i in issues}
            for issue_type in sorted(types, key=lambda t: t.value):
                type_issues = [i for i in issues if i.issue_type == issue_type]
                print(f"\n[{issue_type.value}] ({len(type_issues)})")
                for issue in type_issues:
                    self._print_issue(issue, show_fixable)

        elif group_by == "run_id":
            runs = {i.run_id for i in issues}
            for run_id in sorted(runs):
                run_issues = [i for i in issues if i.run_id == run_id]
                print(f"\n{run_id} ({len(run_issues)})")
                for issue in run_issues:
                    self._print_issue(issue, show_fixable)

        print("\n" + "=" * 70)

    def _print_issue(self, issue: DiagnosticIssue, show_fixable: bool):
        """打印单个问题"""
        print(f"    • {issue.description}")
        print(f"      Key: {issue.key}")
        if show_fixable and issue.fixable:
            print(f"      🔧 修复方法: {issue.fix_action}")

    def auto_fix(
        self,
        issues: List[DiagnosticIssue],
        dry_run: bool = True,
        fix_types: Optional[List[DiagnosticIssueType]] = None,
    ) -> Dict[str, Any]:
        """自动修复问题

        Args:
            issues: 要修复的问题列表
            dry_run: 如果为 True，只报告将要执行的操作
            fix_types: 要修复的问题类型列表，None 则修复所有可修复的问题

        Returns:
            修复结果统计
        """
        result = {
            "dry_run": dry_run,
            "total": len(issues),
            "fixable": 0,
            "fixed": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        # 过滤可修复的问题
        fixable_issues = [i for i in issues if i.fixable]
        if fix_types:
            fixable_issues = [i for i in fixable_issues if i.issue_type in fix_types]

        result["fixable"] = len(fixable_issues)

        if dry_run:
            print(f"\n[Dry-Run] 将修复 {len(fixable_issues)} 个问题:")

        for issue in fixable_issues:
            success = self._fix_issue(issue, dry_run)
            if success:
                result["fixed"] += 1
                result["details"].append(
                    {
                        "key": issue.key,
                        "type": issue.issue_type.value,
                        "action": issue.fix_action,
                        "status": "fixed" if not dry_run else "would_fix",
                    }
                )
            else:
                result["failed"] += 1
                result["details"].append(
                    {
                        "key": issue.key,
                        "type": issue.issue_type.value,
                        "action": issue.fix_action,
                        "status": "failed",
                    }
                )

        result["skipped"] = result["total"] - result["fixable"]

        if dry_run:
            print("\n[Dry-Run] 完成。实际执行请设置 dry_run=False")
        else:
            print(f"\n[修复完成] 已修复: {result['fixed']}, 失败: {result['failed']}")

        return result

    def _fix_issue(self, issue: DiagnosticIssue, dry_run: bool) -> bool:
        """修复单个问题

        Args:
            issue: 要修复的问题
            dry_run: 是否为演练模式

        Returns:
            是否成功
        """
        try:
            if issue.issue_type in {
                DiagnosticIssueType.VERSION_MISMATCH,
                DiagnosticIssueType.STORAGE_VERSION_MISMATCH,
                DiagnosticIssueType.SIZE_MISMATCH,
                DiagnosticIssueType.CHECKSUM_FAILED,
                DiagnosticIssueType.MISSING_DATA_FILE,
            }:
                # 删除缓存
                if dry_run:
                    print(f"  [would delete] {issue.key}")
                else:
                    self.storage.delete(issue.key, issue.run_id)
                    print(f"  [deleted] {issue.key}")
                return True

            elif issue.issue_type == DiagnosticIssueType.ORPHAN_FILE:
                # 删除孤儿文件
                file_path = issue.details.get("file_path")
                if file_path and os.path.exists(file_path):
                    if dry_run:
                        print(f"  [would delete] {file_path}")
                    else:
                        os.remove(file_path)
                        print(f"  [deleted] {file_path}")
                    return True

            return False

        except Exception as e:
            print(f"  [error] 修复 {issue.key} 失败: {e}")
            return False

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
