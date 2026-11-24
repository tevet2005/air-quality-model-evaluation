"""Reshape wide hourly monitoring tables into a tidy long table.

Many monitoring networks publish one row per station x pollutant x day with 24 hour
columns, and use sentinel integers instead of blanks. This module turns such tables
into one row per station x pollutant x hour with an explicit status, without
assuming any particular network: column names, sentinel codes, the hour convention
and unit scales are all arguments. Missing rates per group: ``catalog.coverage``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


@dataclass
class WideHourlyFormat:
    """Describes one wide hourly layout.

    hour_columns  the 24 value columns, in order (first = first hour of the day)
    date_columns  columns that build the calendar date, e.g. ("year", "month", "day")
    id_columns    columns kept as identifiers (station, pollutant, unit, ...)
    status_codes  sentinel value -> status name, e.g. {9999: "missing", 9997: "error"}
    drop_codes    sentinel values that mean "no such hour / not measured" (rows removed)
    hour_ending   True if the first column covers 00:00-01:00 and is labelled 01
    """

    hour_columns: Sequence[str]
    date_columns: Sequence[str]
    id_columns: Sequence[str]
    status_codes: Mapping[float, str] = field(default_factory=dict)
    drop_codes: Sequence[float] = ()
    hour_ending: bool = True


def to_long(table: pd.DataFrame, fmt: WideHourlyFormat,
            scale: Mapping[str, float] | None = None, scale_key: str | None = None) -> pd.DataFrame:
    """Return columns: id columns..., time_start, hour_label, value_raw, status, value.

    ``time_start`` is the start of the averaging hour. ``value`` is ``value_raw`` times
    ``scale[row[scale_key]]`` for valid hours (NaN when the key has no scale).
    """
    t = table.copy()
    t["_date"] = pd.to_datetime(dict(zip(("year", "month", "day"), (t[c] for c in fmt.date_columns))), errors="coerce")
    t = t.dropna(subset=["_date"])
    long = t.melt(id_vars=list(fmt.id_columns) + ["_date"], value_vars=list(fmt.hour_columns),
                  var_name="_hcol", value_name="value_raw")
    pos = {c: i for i, c in enumerate(fmt.hour_columns)}
    idx = long["_hcol"].map(pos)
    long["hour_label"] = idx + (1 if fmt.hour_ending else 0)
    long["time_start"] = long["_date"] + pd.to_timedelta(idx, unit="h")
    long["value_raw"] = pd.to_numeric(long["value_raw"], errors="coerce")
    long = long[~long["value_raw"].isin(list(fmt.drop_codes)) & long["value_raw"].notna()]
    long["status"] = long["value_raw"].map(dict(fmt.status_codes)).fillna("ok")
    factor = long[scale_key].map(scale) if (scale and scale_key) else 1.0
    long["value"] = np.where(long["status"] == "ok", long["value_raw"] * factor, np.nan)
    cols = list(fmt.id_columns) + ["time_start", "hour_label", "value_raw", "status", "value"]
    return long[cols].sort_values(cols[: len(fmt.id_columns)] + ["time_start"]).reset_index(drop=True)
