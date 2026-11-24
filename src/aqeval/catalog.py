"""Keep track of what data you hold: file manifests and per-dataset coverage.

``file_manifest`` lists every file under a folder with size and SHA-256 so that a
download can be verified and reproduced. ``coverage`` summarises a tidy table into
first/last time, number of years and missing rate per group.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

import pandas as pd


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def file_manifest(folder: str | Path, pattern: str = "*", with_hash: bool = True) -> pd.DataFrame:
    folder = Path(folder)
    rows = []
    for p in sorted(folder.rglob(pattern)):
        if p.is_file():
            rows.append({"path": str(p.relative_to(folder)), "size_bytes": p.stat().st_size,
                         "sha256": sha256(p) if with_hash else None})
    return pd.DataFrame(rows, columns=["path", "size_bytes", "sha256"])


def coverage(long: pd.DataFrame, by: Sequence[str], time: str, status: str = "status",
             bad: Sequence[str] = ("missing", "error")) -> pd.DataFrame:
    """first, last, n_years, n_records, missing_rate per group."""
    g = long.assign(_bad=long[status].isin(list(bad))).groupby(list(by))
    out = g.agg(first=(time, "min"), last=(time, "max"), n_records=("_bad", "size"), n_bad=("_bad", "sum"))
    out["n_years"] = g[time].apply(lambda s: s.dt.year.nunique())
    out["missing_rate"] = out.n_bad / out.n_records
    return out.drop(columns="n_bad").reset_index()
