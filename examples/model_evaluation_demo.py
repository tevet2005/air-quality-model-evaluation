"""End-to-end model evaluation on SYNTHETIC data (no real measurements are used).

The script builds a fake monitoring network and a fake gridded model that
  * runs on UTC while the monitors report local time (UTC+5 in this example),
  * underestimates concentrations by about 20 %, and more at roadside monitors,
then shows how the toolkit finds the time offset and quantifies the bias.

    python examples/model_evaluation_demo.py docs/img
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from aqeval import evaluate, gridmatch, plots, timelag

rng = np.random.default_rng(0)
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/img")
OUT.mkdir(parents=True, exist_ok=True)
UTC_OFFSET = 5

# --- a toy Lambert conformal grid and 40 monitors -----------------------------------------
grid = gridmatch.LambertGrid(lat1=30, lat2=60, lon0=10, lat0=45, x_orig=-150_000, y_orig=-120_000,
                             cell=5_000, ncols=60, nrows=48)
stations = pd.DataFrame({"station": [f"S{i:02d}" for i in range(40)],
                         "lat": 45 + rng.uniform(-0.9, 0.9, 40), "lon": 10 + rng.uniform(-1.6, 1.6, 40),
                         "station_type": np.where(np.arange(40) % 4 == 0, "roadside", "background")})
stations = gridmatch.match(stations, grid)

# --- synthetic hourly concentrations -------------------------------------------------------
t_local = pd.date_range("2015-01-01", "2020-12-31 23:00", freq="h")
season = 6 * np.cos(2 * np.pi * (t_local.dayofyear.to_numpy() - 20) / 365.25)
weather = pd.Series(rng.normal(0, 1, len(t_local)), index=t_local).rolling(72, min_periods=1).mean().to_numpy() * 9
diurnal = 3 * np.sin(2 * np.pi * (t_local.hour.to_numpy() - 14) / 24)
obs_rows, mod_rows = [], []
for s in stations.itertuples():
    road = 6 if s.station_type == "roadside" else 0
    true = np.clip(14 + season + weather + diurnal + road + rng.normal(0, 3, len(t_local)), 0.5, None)
    obs = true + rng.normal(0, 2, len(t_local))
    obs[rng.random(len(t_local)) < 0.03] = np.nan                       # 3 % missing hours
    model = np.clip(0.8 * (true - road * 0.7) + rng.normal(0, 2.5, len(t_local)), 0, None)
    obs_rows.append(pd.DataFrame({"station": s.station, "time_start": t_local, "value": obs}))
    # the model file is stamped in UTC
    mod_rows.append(pd.DataFrame({"station": s.station, "time_start": t_local - pd.Timedelta(hours=UTC_OFFSET), "value": model}))
obs_long, mod_long = pd.concat(obs_rows), pd.concat(mod_rows)

# --- 1. find the time offset ---------------------------------------------------------------
o = obs_long.groupby("time_start")["value"].mean()
m = mod_long.groupby("time_start")["value"].mean()
scan = timelag.lag_scan(o, m, range(-12, 13), diurnal_anomaly=True)
lag = int(scan.loc[scan["r"].idxmax(), "lag_hours"])
plots.lag_scan(scan, OUT / "demo_lag_scan.png", f"detected offset: model time {lag:+d} h")
print(f"detected offset: {lag:+d} h")
mod_long["time_start"] += pd.Timedelta(hours=lag)

# --- 2. daily pairs and statistics ---------------------------------------------------------
od = evaluate.daily_from_hourly(obs_long, "station", "time_start", "value")
md = evaluate.daily_from_hourly(mod_long, "station", "time_start", "value")
pairs = evaluate.pair(od, md, on=["station", "date"]).merge(stations[["station", "station_type"]], on="station")
pairs["year"] = pairs["date"].dt.year
print(evaluate.summarize(pairs).round(2).to_string(index=False))
print(evaluate.summarize(pairs, by=["station_type"]).round(2).to_string(index=False))

plots.monthly_timeseries(pairs, OUT / "demo_monthly.png", "PM2.5 (synthetic)", "µg/m³")
plots.scatter(pairs, OUT / "demo_scatter.png", "PM2.5 (synthetic)", "µg/m³")
plots.yearly_bias(pairs, OUT / "demo_yearly_bias.png")
