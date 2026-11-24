"""Evaluate gridded model output against monitoring stations.

Typical flow::

    obs_daily = evaluate.daily_from_hourly(obs_long, "station", "time_start", "value")
    mod_daily = evaluate.daily_from_hourly(model_long, "station", "time_start", "value")
    pairs = evaluate.pair(obs_daily, mod_daily, on=["station", "date"])
    evaluate.summarize(pairs, by=["station_type", "year"])

Statistics follow common air-quality model evaluation practice:
mean bias (MB), normalized mean bias (NMB = sum(M - O) / sum(O)), RMSE and Pearson r.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from . import qc


def metrics(obs, mod) -> dict:
    o, m = np.asarray(obs, float), np.asarray(mod, float)
    ok = np.isfinite(o) & np.isfinite(m)
    o, m = o[ok], m[ok]
    if len(o) < 3:
        return {"n": int(len(o))}
    return {"n": int(len(o)), "obs_mean": o.mean(), "mod_mean": m.mean(), "MB": (m - o).mean(),
            "NMB_pct": 100 * (m - o).sum() / o.sum() if o.sum() else np.nan,
            "RMSE": float(np.sqrt(((m - o) ** 2).mean())), "r": float(np.corrcoef(o, m)[0, 1])}


def daily_from_hourly(long: pd.DataFrame, key: str | Sequence[str], time: str, value: str,
                      min_hours: int = 20) -> pd.DataFrame:
    """Daily means of a long table with hour-start timestamps (already in local time).

    Uses ``qc.daily_mean``: days with fewer than ``min_hours`` valid hours are dropped.
    """
    keys = [key] if isinstance(key, str) else list(key)
    wide = long.pivot_table(index=time, columns=keys, values=value, aggfunc="mean")
    daily = qc.daily_mean(wide, min_valid_hours=min_hours, hour_ending=False)
    daily.index.name = "date"
    out = daily.stack(list(range(len(keys))), future_stack=True).dropna().rename(value).reset_index()
    return out[keys + ["date", value]]


def pair(obs: pd.DataFrame, mod: pd.DataFrame, on: Sequence[str], obs_col: str = "value",
         mod_col: str = "value") -> pd.DataFrame:
    o = obs.rename(columns={obs_col: "obs"})
    m = mod[list(on) + [mod_col]].rename(columns={mod_col: "mod"})
    return o.merge(m, on=list(on))


def summarize(pairs: pd.DataFrame, by: Sequence[str] = ()) -> pd.DataFrame:
    if not by:
        return pd.DataFrame([metrics(pairs["obs"], pairs["mod"])])
    rows = []
    for k, g in pairs.groupby(list(by)):
        k = k if isinstance(k, tuple) else (k,)
        rows.append({**dict(zip(by, k)), **metrics(g["obs"], g["mod"])})
    return pd.DataFrame(rows)


def fiscal_year(dates: pd.Series, start_month: int = 4) -> pd.Series:
    """Year label of a fiscal year that starts in ``start_month``."""
    return dates.dt.year - (dates.dt.month < start_month)
