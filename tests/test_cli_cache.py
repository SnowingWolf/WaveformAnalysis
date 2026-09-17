"""waveform-cache CLI defaults."""

from waveform_analysis.cli_cache import create_parser


def test_storage_dir_defaults_to_wa_data():
    args = create_parser().parse_args(["info"])

    assert args.storage_dir == "./wa_data"
