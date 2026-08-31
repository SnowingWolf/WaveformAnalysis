#!/usr/bin/env python3
"""Rebuild the wheel-packaged Next static export without network access."""

from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import uuid

from waveform_analysis.documentation.site_web import NextSiteBuilder, write_prebuilt_manifest

_TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".svg", ".txt"}


def _without_trailing_whitespace(content: bytes) -> bytes:
    """Normalize generated text while preserving its byte-level line endings.

    CRLF, LF, and CR endings are retained for every line that remains. ASCII
    spaces and tabs are removed from line ends. Trailing blank lines are
    collapsed so non-empty input has exactly one final line ending; input with
    no final ending receives LF. Empty input remains empty.
    """

    if not content:
        return b""

    lines: list[tuple[bytes, bytes]] = []
    last_ending = b"\n"
    start = 0
    index = 0
    while index < len(content):
        byte = content[index]
        if byte == 0x0D:  # CR or CRLF
            ending = b"\r\n" if index + 1 < len(content) and content[index + 1] == 0x0A else b"\r"
            lines.append((content[start:index].rstrip(b" \t"), ending))
            last_ending = ending
            index += len(ending)
            start = index
        elif byte == 0x0A:  # LF
            ending = b"\n"
            lines.append((content[start:index].rstrip(b" \t"), ending))
            last_ending = ending
            index += 1
            start = index
        else:
            index += 1
    if start < len(content):
        lines.append((content[start:].rstrip(b" \t"), b""))

    while lines and not lines[-1][0]:
        lines.pop()
    if not lines:
        return last_ending

    normalized = b"".join(body + ending for body, ending in lines)
    if lines[-1][1]:
        return normalized
    return normalized + b"\n"


def _strip_trailing_whitespace(root: Path) -> None:
    """Normalize tracked text artifacts for EOF and trailing-whitespace hooks."""

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        content = path.read_bytes()
        normalized = _without_trailing_whitespace(content)
        if normalized != content:
            path.write_bytes(normalized)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    destination = project_root / "waveform_analysis" / "documentation" / "site_dist"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise RuntimeError(f"prebuilt destination must be a normal directory: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".site-dist-build-", dir=destination.parent
    ) as temporary:
        staging = Path(temporary) / "site_dist"
        NextSiteBuilder(project_root=project_root).generate(staging)
        _strip_trailing_whitespace(staging)
        write_prebuilt_manifest(staging)

        backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
        if destination.exists():
            destination.rename(backup)
        try:
            staging.rename(destination)
        except Exception:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)

    print(f"Built wheel prebuilt site: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
