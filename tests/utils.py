from pathlib import Path


def make_csv(dirpath: Path, ch: int, idx: int, start_tag: int, end_tag: int, n_samples: int = 200, meta: bool = True):
    """Create a CSV file with header and three rows (start, mid, end).

    dirpath: Path to RAW directory
    ch, idx: channel and index used in filename
    start_tag, end_tag: timetag values
    n_samples: number of sample columns (S0..)
    meta: whether to add a metadata line before header (so skiprows=2 in loader works)
    """
    fname = dirpath / f"RUN_CH{ch}_{idx}.CSV"
    sample_headers = ";".join(f"S{i}" for i in range(n_samples))
    header = f"HEADER;X;TIMETAG;{sample_headers}\n"

    def row(tag):
        samples = ";".join(str((tag + i) % 100) for i in range(n_samples))
        return f"v;1;{tag};{samples}\n"

    content = ""
    if meta:
        content += "META;INFO\n"
    content += header + row(start_tag) + row((start_tag + end_tag) // 2) + row(end_tag)
    fname.write_text(content, encoding="utf-8")


def make_simple_csv(dirpath: Path, ch: int, idx: int, tag: int, n_samples: int = 50):
    """Create a simpler CSV used by some tests (two data rows)"""
    fname = dirpath / f"RUN_CH{ch}_{idx}.CSV"
    header = "HEADER;X;TIMETAG;" + ";".join(f"S{i}" for i in range(n_samples)) + "\n"
    body = "".join(
        f"v;1;{tag + i};" + ";".join(str((tag + i + j) % 100) for j in range(n_samples)) + "\n" for i in range(2)
    )
    fname.write_text(header + body, encoding="utf-8")
