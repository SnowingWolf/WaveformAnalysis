#!/usr/bin/env python
"""
WaveformAnalysis 文档生成工具 CLI

用法:
  waveform-docs generate plugins-auto     # 自动生成 builtin 插件文档
  waveform-docs generate plugins-agent    # 生成 agent 导向插件文档
  waveform-docs check coverage            # 检查文档覆盖率
"""

from __future__ import annotations

import argparse
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import unquote, urlparse
import uuid

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_WARNING = 2
MIN_PYTHON = (3, 10)


def _ensure_supported_python() -> bool:
    """Fail early with an actionable message on an unsupported interpreter."""

    if sys.version_info[:2] >= MIN_PYTHON:
        return True
    required = ".".join(str(value) for value in MIN_PYTHON)
    current = ".".join(str(value) for value in sys.version_info[:3])
    print(
        f"❌ waveform-docs 需要 Python >= {required}（当前为 {current}）；"
        "请设置 WAVEFORM_PYTHON 后通过对应解释器运行。",
        file=sys.stderr,
    )
    return False


def main():
    """CLI 主入口"""
    if not _ensure_supported_python():
        return EXIT_ERROR
    parser = argparse.ArgumentParser(
        description="WaveformAnalysis 文档生成工具",
        epilog="""
示例:
  # 自动生成 builtin 插件文档
  waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/

  # 生成 agent 导向插件文档
  waveform-docs generate plugins-agent -o docs/plugins/reference/agent/

  # 检查文档覆盖率
  waveform-docs check coverage --strict
""",
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # generate 子命令
    gen_parser = subparsers.add_parser("generate", help="生成文档")
    gen_parser.add_argument(
        "doc_type",
        choices=["plugins-auto", "plugins-agent", "plugins-web", "site-web"],
        help="文档类型",
    )
    gen_parser.add_argument("--output", "-o", type=str, help="输出路径（文件或目录）")
    gen_parser.add_argument(
        "--plugin",
        "-p",
        type=str,
        help="生成单个插件文档",
    )

    # check 子命令
    check_parser = subparsers.add_parser("check", help="检查文档")
    check_parser.add_argument(
        "check_type",
        choices=["coverage", "links"],
        help="检查类型",
    )

    agent_doc_parser = subparsers.add_parser("agent-doc", help="发布已验证的 AgentDoc 工作流结果")
    agent_doc_subparsers = agent_doc_parser.add_subparsers(dest="agent_doc_command")
    publish_parser = agent_doc_subparsers.add_parser(
        "publish", help="原子发布一个已验证的 AgentDoc"
    )
    publish_parser.add_argument("--plugin", required=True, help="插件 provides 名称")
    publish_parser.add_argument(
        "--artifact-store",
        default=".waveform-docs/agent-doc-artifacts",
        help="工作流状态与 artifact 目录",
    )
    publish_parser.add_argument(
        "--output",
        help="已审核 YAML 输出目录，默认写入包内 documentation/agent_docs",
    )
    check_parser.add_argument(
        "--docs-dir",
        "-d",
        type=str,
        help="文档目录路径",
    )
    check_parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式（也检查 spec 质量）",
    )
    check_parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="有警告时也失败",
    )

    serve_parser = subparsers.add_parser("serve", help="服务已生成的静态文档目录")
    serve_parser.add_argument("--directory", type=str, required=True, help="现有站点目录")
    serve_parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    serve_parser.add_argument("--port", default=8000, type=int, help="监听端口")
    serve_parser.add_argument(
        "--lineage-context-factory",
        help="可选 Context 工厂，格式 package.module:function；启用同源只读 /api/lineage",
    )

    args = parser.parse_args()

    # 检查命令
    if not args.command:
        parser.print_help()
        return 0

    # 执行命令
    if args.command == "generate":
        return cmd_generate(args)
    elif args.command == "check":
        return cmd_check(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command == "agent-doc":
        return cmd_agent_doc(args)

    return 0


def cmd_agent_doc(args):
    if args.agent_doc_command != "publish":
        print("❌ agent-doc 需要子命令；可用命令：publish")
        return 1
    try:
        import yaml

        from waveform_analysis.documentation import (
            DocumentationOrchestrator,
            FileArtifactStore,
        )
        from waveform_analysis.documentation.types import DAGState, NodeExecutionResult

        store = FileArtifactStore(args.artifact_store)
        raw_state = store.load_state(args.plugin)
        if raw_state is None:
            raise ValueError(f"找不到插件 `{args.plugin}` 的持久化工作流状态")
        state = DAGState(**raw_state)
        if state.plugin_name != args.plugin:
            raise ValueError("持久化状态的 plugin_name 与 --plugin 不一致")
        for artifact_name in (
            "plugin_manifest",
            "plugin_facts",
            "agent_doc",
            "verification_report",
        ):
            artifact = store.load_artifact(args.plugin, artifact_name)
            if artifact is not None:
                state.artifacts[artifact_name] = artifact
        if state.current_node != "publish_agent_doc":
            raise ValueError("只允许发布已通过验证并停在 publish_agent_doc 的工作流状态")
        if not state.history or state.history[-1] != {
            "node_id": "verify_agent_doc",
            "status": "passed",
            "next_node": "publish_agent_doc",
        }:
            raise ValueError("持久化状态缺少通过验证后进入 publish_agent_doc 的记录")

        orchestrator = DocumentationOrchestrator(artifact_store=store)
        document = orchestrator.published_document(state)
        destination = Path(args.output) if args.output else None
        output = orchestrator.publish(state, destination)
        result = NodeExecutionResult(
            dag_name=orchestrator.dag.name,
            dag_version=orchestrator.dag.version,
            node_id="publish_agent_doc",
            node_status="success",
            artifact_type="PublishedAgentDoc",
            artifact=document,
            issues=[],
            requested_evidence=[],
            confidence="high",
        )
        orchestrator.accept_result(state, result)
        print(f"✅ 已发布验证通过的 AgentDoc: {output}")
        return 0
    except Exception as exc:
        print(f"❌ 发布 AgentDoc 时出错: {exc}")
        return 1


def cmd_generate(args):
    """处理 generate 命令"""
    if args.doc_type == "plugins-web":
        return generate_plugins_web(args)
    if args.doc_type == "site-web":
        return generate_site_web(args)
    if args.doc_type == "plugins-agent":
        return generate_plugins_docs(
            args=args,
            profile="agent",
            default_output="docs/plugins/reference/agent",
            label="agent 插件文档",
        )
    return generate_plugins_docs(
        args=args,
        profile="auto",
        default_output="docs/plugins/reference/builtin/auto",
        label="builtin 插件文档",
    )


def generate_plugins_web(args):
    """Generate the offline plugin HTML site."""
    if args.plugin:
        print("❌ plugins-web only supports full-site generation")
        return 1
    try:
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        output_path = Path(args.output or "docs/_site")
        generator = PluginDocGenerator()
        count = generator.load_builtin_plugins()
        results = generator.generate_web(output_path)
        print(f"✅ 已生成插件静态站点: {count} 个插件")
        print(f"   输出目录: {output_path}")
        print(f"   文件数: {len(results)}")
        return 0
    except Exception as exc:
        print(f"❌ 生成静态站点时出错: {exc}")
        return 1


_REQUIRED_SITE_RESULT_KEYS = {
    "SITE_INDEX",
    "INDEX",
    "ROOT_LINEAGE",
    "LINEAGE_INDEX",
    "ACCESSOR_INDEX",
    "CONTEXT_INDEX",
    "context:records-view",
    "context:records-wave-pool",
    "ADAPTER_INDEX",
    "VISUALIZATION_INDEX",
}


class _SiteReferenceParser(HTMLParser):
    """Collect local navigation and asset references from one generated page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.anchors: set[str] = set()
        self.aria_controls: list[str] = []

    def handle_starttag(self, _tag, attrs):
        values = {name.lower(): value for name, value in attrs if value is not None}
        for name in ("href", "src"):
            value = values.get(name)
            if value:
                self.references.append(value)
        for name in ("id", "name"):
            value = values.get(name)
            if value:
                self.anchors.add(value)
        controls = values.get("aria-controls")
        if controls:
            self.aria_controls.extend(token for token in controls.split() if token)


def _resolve_site_reference(root: Path, page: Path, reference: str) -> tuple[Path | None, str]:
    """Resolve one local HTML URL and return its target plus fragment."""

    parsed = urlparse(reference)
    if parsed.scheme or parsed.netloc:
        return None, unquote(parsed.fragment)
    path_text = unquote(parsed.path)
    if not path_text:
        target = page.resolve()
    else:
        target = (
            root / path_text.lstrip("/") if path_text.startswith("/") else page.parent / path_text
        ).resolve()
        if target.is_dir():
            target /= "index.html"
    return target, unquote(parsed.fragment)


def _extract_search_index_urls(path: Path) -> list[str]:
    """Read URLs from a generated ``assets/search-index.js`` file."""

    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?:window\.)?WAVEFORM_DOCS_SEARCH\s*=\s*", text)
    if not match:
        raise ValueError(f"搜索索引缺少 WAVEFORM_DOCS_SEARCH 数组: {path.name}")
    try:
        payload = text[match.end() :].lstrip()
        entries, end = json.JSONDecoder().raw_decode(payload)
        if payload[end:].strip().strip(";").strip():
            raise ValueError("搜索索引数组后存在非空内容")
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"搜索索引不是有效 JSON: {path.name}: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"搜索索引不是有效 JSON: {path.name}: {exc}") from exc
    if not isinstance(entries, list):
        raise ValueError(f"搜索索引必须是数组: {path.name}")
    urls: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("url"), str):
            raise ValueError(f"搜索索引第 {index + 1} 项缺少字符串 url: {path.name}")
        urls.append(entry["url"])
    return urls


def _validate_generated_site(output_dir: Path, results: dict[str, Path]) -> None:
    """Reject incomplete builds and broken local HTML references before publication."""
    missing_keys = sorted(_REQUIRED_SITE_RESULT_KEYS - results.keys())
    if missing_keys:
        raise ValueError(f"site-web 生成结果缺少必要页面: {', '.join(missing_keys)}")

    root = output_dir.resolve()
    for name, generated_path in results.items():
        path = Path(generated_path).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"site-web 生成结果越过输出目录: {name} -> {path}")
        if not path.is_file():
            raise ValueError(f"site-web 生成结果不存在: {name} -> {path}")

    html_pages = sorted(output_dir.rglob("*.html"))
    page_anchors: dict[Path, set[str]] = {}
    page_parsers: dict[Path, _SiteReferenceParser] = {}
    for page in html_pages:
        parser = _SiteReferenceParser()
        parser.feed(page.read_text(encoding="utf-8"))
        page_anchors[page.resolve()] = parser.anchors
        page_parsers[page.resolve()] = parser

    broken: list[str] = []
    for page in html_pages:
        parser = page_parsers[page.resolve()]
        for reference in parser.references:
            target, fragment = _resolve_site_reference(root, page, reference)
            if target is None:
                continue
            if not target.is_relative_to(root):
                broken.append(f"{page.relative_to(output_dir)} -> {reference}")
                continue
            if not target.is_file():
                broken.append(f"{page.relative_to(output_dir)} -> {reference}")
                continue
            if fragment and target.suffix.lower() in {".html", ".htm"}:
                anchors = page_anchors.get(target.resolve(), set())
                if not any(anchor.casefold() == fragment.casefold() for anchor in anchors):
                    broken.append(
                        f"{page.relative_to(output_dir)} -> {reference} (fragment 不存在)"
                    )

        for control in parser.aria_controls:
            if control not in parser.anchors:
                broken.append(
                    f"{page.relative_to(output_dir)} -> aria-controls={control} (DOM 节点不存在)"
                )

    for search_index in sorted(output_dir.rglob("search-index.js")):
        try:
            search_urls = _extract_search_index_urls(search_index)
        except ValueError as exc:
            broken.append(str(exc))
            continue
        search_source = root / "index.html"
        for url in search_urls:
            target, fragment = _resolve_site_reference(root, search_source, url)
            if target is None:
                continue
            if not target.is_relative_to(root) or not target.is_file():
                broken.append(f"{search_index.relative_to(output_dir)} -> {url}")
                continue
            if fragment and target.suffix.lower() in {".html", ".htm"}:
                anchors = page_anchors.get(target.resolve(), set())
                if not any(anchor.casefold() == fragment.casefold() for anchor in anchors):
                    broken.append(
                        f"{search_index.relative_to(output_dir)} -> {url} (fragment 不存在)"
                    )
    if broken:
        preview = "; ".join(broken[:10])
        suffix = f"; 另有 {len(broken) - 10} 项" if len(broken) > 10 else ""
        raise ValueError(f"site-web 包含无效本地链接: {preview}{suffix}")


def _atomic_generate_site(output_path: Path, generator) -> dict[str, Path]:
    """Generate, validate, and publish one complete site while preserving rollback."""
    output_path = Path(output_path)
    if output_path.is_symlink() or (output_path.exists() and not output_path.is_dir()):
        raise ValueError(f"site-web 输出路径必须是普通目录: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = Path(
        tempfile.mkdtemp(prefix=f".{output_path.name}.staging-", dir=output_path.parent)
    )
    backup_path = output_path.parent / f".{output_path.name}.backup-{uuid.uuid4().hex}"
    try:
        results = generator.generate(staging_path)
        _validate_generated_site(staging_path, results)
        remapped = {
            name: output_path / Path(path).resolve().relative_to(staging_path.resolve())
            for name, path in results.items()
        }
        if output_path.exists():
            output_path.rename(backup_path)
        try:
            staging_path.rename(output_path)
        except Exception:
            if backup_path.exists() and not output_path.exists():
                backup_path.rename(output_path)
            raise
        if backup_path.exists():
            shutil.rmtree(backup_path)
        return remapped
    finally:
        if staging_path.exists():
            shutil.rmtree(staging_path, ignore_errors=True)


def generate_site_web(args):
    """Generate the complete offline HTML documentation site."""
    if args.plugin:
        print("❌ site-web 仅支持全量生成，不能使用 --plugin")
        return 1
    try:
        from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator

        output_path = Path(args.output or "docs/_site")
        generator = DocumentationSiteGenerator()
        results = _atomic_generate_site(output_path, generator)
        print("✅ 已生成 WaveformAnalysis HTML 文档总站")
        print(f"   输出目录: {output_path}")
        print(f"   文件数: {len(results)}")
        guide_warnings = getattr(generator, "guide_warnings", ())
        if guide_warnings:
            print(f"   Markdown 链接警告: {len(guide_warnings)}")
            for warning in guide_warnings:
                print(f"   ⚠️ {warning}")
            return EXIT_WARNING
        return EXIT_OK
    except Exception as exc:
        print(f"❌ 生成 HTML 文档总站时出错: {exc}")
        return 1


class _DocumentationRequestHandler(SimpleHTTPRequestHandler):
    """Serve static documentation and, when configured, a read-only DAG endpoint."""

    def __init__(self, *args, lineage_payload_provider=None, **kwargs):
        self._lineage_payload_provider = lineage_payload_provider
        super().__init__(*args, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        if urlparse(self.path).path != "/api/lineage":
            return super().do_GET()
        if self._lineage_payload_provider is None:
            self.send_error(404, "Dynamic lineage is not enabled")
            return
        try:
            body = json.dumps(
                self._lineage_payload_provider(), ensure_ascii=True, separators=(",", ":")
            ).encode("utf-8")
        except Exception as exc:
            self.send_error(500, f"Could not build lineage payload: {exc}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _lineage_payload_provider(factory_reference: str):
    """Load one trusted Context factory and return a topology-only payload provider."""
    module_name, separator, attribute_name = factory_reference.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("--lineage-context-factory 必须是 package.module:function 格式")
    factory = getattr(importlib.import_module(module_name), attribute_name, None)
    if not callable(factory):
        raise ValueError(f"Context 工厂不可调用: {factory_reference}")

    def provide():
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        return PluginDocGenerator().build_lineage_payload_for_context(factory())

    # Fail before serving rather than exposing a nominal API that always returns 500.
    provide()
    return provide


def cmd_serve(args):
    """Serve an existing directory without generating files or opening a browser."""
    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        print(f"❌ 站点目录不存在: {directory}")
        return 1
    try:
        lineage_provider = (
            _lineage_payload_provider(args.lineage_context_factory)
            if args.lineage_context_factory
            else None
        )
    except Exception as exc:
        print(f"❌ 无法启用动态 DAG: {exc}")
        return 1
    handler = partial(
        _DocumentationRequestHandler,
        directory=str(directory),
        lineage_payload_provider=lineage_provider,
    )
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        print(f"❌ 无法启动服务器: {exc}")
        return 1
    print(f"Serving {directory} at http://{args.host}:{args.port}/")
    if lineage_provider is not None:
        print("Dynamic lineage enabled at /api/lineage (topology metadata only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def generate_plugins_docs(args, profile, default_output, label):
    """生成插件文档"""
    try:
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        # 确定输出目录
        output_dir = args.output or default_output
        output_path = Path(output_dir)

        # 初始化生成器
        generator = PluginDocGenerator()

        # 加载内置插件
        count = generator.load_builtin_plugins()
        print(f"✅ 已加载 {count} 个内置插件")

        # 生成单个插件或所有插件
        if args.plugin:
            # 生成单个插件
            file_path = output_path / f"{args.plugin}.md"
            try:
                result = generator.generate_single(args.plugin, file_path, profile=profile)
                print(f"✅ 已生成: {result}")
            except ValueError as e:
                print(f"❌ 错误: {e}")
                return 1
        else:
            # 生成所有插件
            results = generator.generate_all(output_path, profile=profile)
            print(f"✅ 已生成 {label}: {len(results)} 个文档文件")
            print(f"   输出目录: {output_path}")

            # 列出生成的文件
            for _provides, path in sorted(results.items()):
                print(f"   - {path.name}")

        return 0

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("提示: 运行 'pip install jinja2' 安装依赖")
        return 1

    except Exception as e:
        print(f"❌ 生成文档时出错: {e}")
        import traceback

        traceback.print_exc()
        return 1


def generate_docs(args):
    """生成文档（原有功能）"""
    try:
        from waveform_analysis.utils.doc_generator import DocGenerator

        # 初始化生成器
        ctx = None
        if args.with_context:
            from waveform_analysis.core.context import Context
            from waveform_analysis.core.plugins import profiles

            ctx = Context()
            ctx.register(*profiles.cpu_default())
            print("✅ 已加载 Context 和标准插件")

        generator = DocGenerator(ctx)

        # 确定输出路径
        output_path = args.output or "docs"

        # 生成文档
        if args.doc_type == "api":
            if not args.output:
                output_path = f"docs/api_reference.{args.format.replace('markdown', 'md')}"
            generator.generate_api_reference(output_path, format=args.format)

        elif args.doc_type == "config":
            if not args.output:
                output_path = "docs/config_reference.md"
            generator.generate_config_reference(output_path)

        elif args.doc_type == "plugins":
            if not args.output:
                output_path = "docs/plugin_guide.md"
            generator.generate_plugin_guide(output_path)

        elif args.doc_type == "all":
            if not args.output:
                output_path = "docs"
            generator.generate_all(output_path)

        print("\n✅ 文档生成成功")
        return 0

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("提示: 运行 'pip install jinja2' 安装依赖")
        return 1

    except Exception as e:
        print(f"❌ 生成文档时出错: {e}")
        import traceback

        traceback.print_exc()
        return 1


def cmd_check(args):
    """处理 check 命令"""
    if args.check_type == "coverage":
        return check_coverage(args)
    if args.check_type == "links":
        return check_links(args)
    return EXIT_OK


def check_coverage(args):
    """检查文档覆盖率"""
    try:
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker

        # 确定文档目录
        docs_dir = Path(args.docs_dir) if args.docs_dir else None

        # 如果指定了 docs_dir，auto_docs_dir 默认为 docs_dir/plugins/reference/builtin/auto
        auto_docs_dir = None
        if docs_dir:
            auto_docs_dir = docs_dir / "plugins" / "reference" / "builtin" / "auto"

        # 初始化检查器
        checker = DocCoverageChecker(docs_dir=docs_dir, auto_docs_dir=auto_docs_dir)

        # 执行检查
        report = checker.check_coverage(
            require_spec_quality=args.strict,
            require_content_quality=args.strict,
        )

        # 打印报告
        checker.print_report(report)

        # 确定退出码
        if report.error_count:
            return EXIT_ERROR
        if report.warning_count:
            # Keep the historical default (warnings are informational), while
            # exposing a distinct non-zero code when a quality gate opts in.
            return EXIT_WARNING if args.fail_on_warning else EXIT_OK
        return EXIT_OK

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        return EXIT_ERROR

    except Exception as e:
        print(f"❌ 检查覆盖率时出错: {e}")
        import traceback

        traceback.print_exc()
        return EXIT_ERROR


def check_links(args):
    """Check local Markdown links, page fragments and embedded resources."""

    try:
        from waveform_analysis.utils.doc_links import check_markdown_links

        docs_dir = Path(args.docs_dir) if args.docs_dir else Path("docs")
        report = check_markdown_links(docs_dir)
        print("\nMarkdown Link Report")
        print(f"Docs directory: {report.docs_dir}")
        print(f"Markdown files: {report.files_checked}")
        print(f"Local references: {report.links_checked}")
        if report.issues:
            print(f"Issues: {len(report.issues)}")
            for issue in report.issues:
                print(f"  ❌ {issue.format(report.docs_dir)}")
            return EXIT_ERROR
        print("✅ All local Markdown links and fragments are valid")
        return EXIT_OK
    except ImportError as exc:
        print(f"❌ 缺少依赖: {exc}")
        return EXIT_ERROR
    except Exception as exc:
        print(f"❌ 检查 Markdown 链接时出错: {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
