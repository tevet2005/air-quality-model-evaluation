"""Detect a constant time offset between two hourly series.

A wrong time zone (for example model output in UTC read as local time) shows up as a
lag that maximises the correlation between model and observations. Correlating raw
series is dominated by day-to-day weather, so the diurnal-anomaly option removes each
day's mean first and correlates only the shape of the daily cycle.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _anomaly(s: pd.Series) -> pd.Series:
    return s - s.groupby(s.index.floor("D")).transform("mean")


def lag_scan(obs: pd.Series, mod: pd.Series, lags: Iterable[int] = range(-12, 13),
             diurnal_anomaly: bool = False) -> pd.DataFrame:
    """Correlation of obs(t) with mod(t - lag) for each lag in hours.

    A positive best lag means the model timestamps must be shifted forward by that
    many hours to line up with the observations.
    """
    o = obs.asfreq("h")
    rows = []
    for lag in lags:
        m = mod.copy()
        m.index = m.index + pd.Timedelta(hours=lag)
        m = m.reindex(o.index)
        a, b = (_anomaly(o), _anomaly(m)) if diurnal_anomaly else (o, m)
        ok = a.notna() & b.notna()
        r = np.corrcoef(a[ok], b[ok])[0, 1] if ok.sum() > 2 else np.nan
        rows.append({"lag_hours": lag, "r": r, "n": int(ok.sum())})
    return pd.DataFrame(rows)


def best_lag(obs: pd.Series, mod: pd.Series, lags: Iterable[int] = range(-12, 13),
             diurnal_anomaly: bool = True) -> int:
    scan = lag_scan(obs, mod, lags, diurnal_anomaly)
    return int(scan.loc[scan["r"].idxmax(), "lag_hours"])
