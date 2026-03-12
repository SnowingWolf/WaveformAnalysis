import waveform_analysis
from waveform_analysis import cli


def test_init_version_reads_metadata(monkeypatch):
    monkeypatch.setattr(waveform_analysis, "package_version", lambda _: "1.2.3")
    assert waveform_analysis._resolve_package_version() == "1.2.3"


def test_init_version_fallback_when_package_not_installed(monkeypatch):
    def _raise_not_found(_: str):
        raise waveform_analysis.PackageNotFoundError

    monkeypatch.setattr(waveform_analysis, "package_version", _raise_not_found)
    assert waveform_analysis._resolve_package_version() == "0.0.0+unknown"


def test_cli_version_reads_metadata(monkeypatch):
    monkeypatch.setattr(cli, "package_version", lambda _: "2.3.4")
    assert cli._pkg_version() == "2.3.4"


def test_cli_version_fallback_when_package_not_installed(monkeypatch):
    def _raise_not_found(_: str):
        raise cli.PackageNotFoundError

    monkeypatch.setattr(cli, "package_version", _raise_not_found)
    assert cli._pkg_version() == "0.0.0+unknown"
