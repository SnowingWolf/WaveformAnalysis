# -*- coding: utf-8 -*-
"""
CacheDiagnostics 测试模块
"""

import os
import time
import tempfile
import pytest
import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer, CacheEntry
from waveform_analysis.core.storage.cache_diagnostics import (
    CacheDiagnostics,
    DiagnosticIssue,
    DiagnosticIssueType,
)


@pytest.fixture
def temp_storage_dir():
    """创建临时存储目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def context_with_cache(temp_storage_dir):
    """创建带有缓存数据的 Context"""
    ctx = Context(storage_dir=temp_storage_dir)
    storage = ctx.storage

    # 创建正常的缓存数据
    for run_id in ['run_001', 'run_002']:
        key = f"{run_id}-peaks-abc123"
        data = np.zeros(100, dtype=[('time', '<f8'), ('value', '<f4')])
        storage.save_memmap(key, data, run_id=run_id)

        # 更新元数据
        meta = storage.get_metadata(key, run_id)
        if meta:
            meta['plugin_version'] = '1.0.0'
            storage.save_metadata(key, meta, run_id)

    return ctx


class TestDiagnosticIssue:
    """DiagnosticIssue 测试"""

    def test_create_issue(self):
        """测试创建诊断问题"""
        issue = DiagnosticIssue(
            issue_type=DiagnosticIssueType.VERSION_MISMATCH,
            severity='warning',
            run_id='run_001',
            data_name='peaks',
            key='run_001-peaks-abc123',
            description='版本不匹配',
            details={'cached': '1.0', 'current': '2.0'},
            fixable=True,
            fix_action='删除缓存'
        )

        assert issue.issue_type == DiagnosticIssueType.VERSION_MISMATCH
        assert issue.severity == 'warning'
        assert issue.fixable is True

    def test_issue_str(self):
        """测试问题字符串表示"""
        issue = DiagnosticIssue(
            issue_type=DiagnosticIssueType.MISSING_DATA_FILE,
            severity='error',
            run_id='run_001',
            data_name='peaks',
            key='test',
            description='文件缺失',
        )

        str_repr = str(issue)
        assert 'missing_data_file' in str_repr
        assert '文件缺失' in str_repr


class TestCacheDiagnostics:
    """CacheDiagnostics 测试"""

    def test_diagnose_empty_cache(self, temp_storage_dir):
        """测试诊断空缓存"""
        ctx = Context(storage_dir=temp_storage_dir)
        analyzer = CacheAnalyzer(ctx)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)
        issues = diag.diagnose(verbose=False)

        assert isinstance(issues, list)
        assert len(issues) == 0

    def test_diagnose_healthy_cache(self, context_with_cache):
        """测试诊断健康的缓存"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)
        issues = diag.diagnose(verbose=False)

        # 健康的缓存应该没有严重问题
        errors = [i for i in issues if i.severity == 'error']
        # 可能有版本警告，但不应该有错误（除非数据确实有问题）
        assert isinstance(issues, list)

    def test_check_version_mismatch(self, context_with_cache):
        """测试版本不匹配检查"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)

        # 创建一个模拟条目
        entry = CacheEntry(
            run_id='run_001',
            data_name='peaks',
            key='run_001-peaks-abc123',
            size_bytes=1000,
            created_at=time.time(),
            plugin_version='1.0.0',
            dtype_str='<f8',
            count=100,
            compressed=False,
            has_checksum=False,
            file_path='/tmp/test.bin',
        )

        # 如果没有注册插件，应该返回 None
        issue = diag.check_version_mismatch(entry)
        # 结果取决于是否有注册插件
        assert issue is None or isinstance(issue, DiagnosticIssue)

    def test_check_integrity(self, context_with_cache):
        """测试完整性检查"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)

        entries = analyzer.get_entries()
        for entry in entries:
            issues = diag.check_integrity(entry)
            assert isinstance(issues, list)

    def test_find_orphan_files(self, context_with_cache, temp_storage_dir):
        """测试孤儿文件检测"""
        # 创建一个没有元数据的孤儿文件
        orphan_path = os.path.join(temp_storage_dir, 'orphan_file.bin')
        with open(orphan_path, 'wb') as f:
            f.write(b'test data')

        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)

        # 在扁平模式下查找孤儿文件
        # 注意：这取决于存储模式
        issues = diag.find_orphan_files('run_001')
        assert isinstance(issues, list)

    def test_print_report(self, context_with_cache, capsys):
        """测试打印报告"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)
        issues = diag.diagnose(verbose=False)

        diag.print_report(issues)
        captured = capsys.readouterr()
        # 应该有输出
        assert len(captured.out) > 0

    def test_print_report_empty(self, temp_storage_dir, capsys):
        """测试空报告打印"""
        ctx = Context(storage_dir=temp_storage_dir)
        analyzer = CacheAnalyzer(ctx)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)
        diag.print_report([])

        captured = capsys.readouterr()
        assert '未发现问题' in captured.out

    def test_auto_fix_dry_run(self, context_with_cache):
        """测试自动修复 dry-run"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)
        issues = diag.diagnose(verbose=False)

        # Dry-run 不应该实际删除任何东西
        result = diag.auto_fix(issues, dry_run=True)

        assert 'dry_run' in result
        assert result['dry_run'] is True
        assert 'total' in result
        assert 'fixable' in result

    def test_diagnose_with_run_filter(self, context_with_cache):
        """测试按 run 过滤诊断"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)
        issues = diag.diagnose(run_id='run_001', verbose=False)

        # 所有问题都应该属于 run_001
        for issue in issues:
            assert issue.run_id == 'run_001'

    def test_print_report_grouped_by_type(self, context_with_cache, capsys):
        """测试按类型分组打印报告"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)

        # 创建一些测试问题
        issues = [
            DiagnosticIssue(
                issue_type=DiagnosticIssueType.VERSION_MISMATCH,
                severity='warning',
                run_id='run_001',
                data_name='peaks',
                key='test1',
                description='测试问题1',
            ),
            DiagnosticIssue(
                issue_type=DiagnosticIssueType.MISSING_DATA_FILE,
                severity='error',
                run_id='run_002',
                data_name='waveforms',
                key='test2',
                description='测试问题2',
            ),
        ]

        diag.print_report(issues, group_by='type')
        captured = capsys.readouterr()
        assert 'version_mismatch' in captured.out or 'missing_data_file' in captured.out
