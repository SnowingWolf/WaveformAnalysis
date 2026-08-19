from pathlib import Path

from waveform_analysis.utils import cli_docs
from waveform_analysis.utils.doc_links import check_markdown_links


def test_markdown_link_checker_validates_files_resources_and_fragments(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\n## Setup\n\n[details](details.md#details)\n\n![plot](plot.png)\n",
        encoding="utf-8",
    )
    (docs / "details.md").write_text("# Details\n", encoding="utf-8")
    (docs / "plot.png").write_bytes(b"png")

    report = check_markdown_links(docs)

    assert report.passed
    assert report.files_checked == 2
    assert report.links_checked == 2


def test_markdown_link_checker_reports_missing_file_and_cross_page_fragment(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\n[missing](other.md#not-there)\n", encoding="utf-8")

    report = check_markdown_links(docs)

    assert not report.passed
    assert any("本地资源不存在" in issue.message for issue in report.issues)


def test_markdown_link_checker_handles_setext_duplicate_and_escape_fragments(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "Title\n=====\n\n## Repeat\n\n## Repeat\n\n"
        "[setext](#title) [second](#repeat-2) [escape](../../outside.md)\n",
        encoding="utf-8",
    )

    report = check_markdown_links(docs)

    assert not report.passed
    assert any(issue.target == "../../outside.md" for issue in report.issues)
    assert not any(issue.target in {"#title", "#repeat-2"} for issue in report.issues)


def test_markdown_link_checker_supports_reference_and_embedded_html_links(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        '# Guide\n\n[details][ref]\n\n<a href="#guide">self</a>\n'
        '<img src="plot.png">\n\n[ref]: details.md\n',
        encoding="utf-8",
    )
    (docs / "details.md").write_text("# Details\n", encoding="utf-8")
    (docs / "plot.png").write_bytes(b"png")

    report = check_markdown_links(docs)

    assert report.passed
    assert report.links_checked == 3


def test_markdown_link_checker_checks_reference_style_images_and_fragments(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\n![plot][image]\n\n[details](details.md#missing)\n\n" "[image]: plot.png\n",
        encoding="utf-8",
    )
    (docs / "details.md").write_text("# Details\n", encoding="utf-8")
    (docs / "plot.png").write_bytes(b"png")

    report = check_markdown_links(docs)

    assert not report.passed
    assert report.links_checked == 2
    assert any(issue.kind == "fragment" for issue in report.issues)


def test_cli_links_check_returns_error_for_broken_fragment(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\n[bad](#missing)\n", encoding="utf-8")

    result = cli_docs.check_links(type("Args", (), {"docs_dir": str(docs)})())

    assert result == cli_docs.EXIT_ERROR


def test_cli_reports_unsupported_python_version(monkeypatch, capsys):
    monkeypatch.setattr(cli_docs.sys, "version_info", (3, 9, 18))

    assert not cli_docs._ensure_supported_python()
    assert "Python >= 3.10" in capsys.readouterr().err
