import numpy as np
import pandas as pd

from aqeval import catalog, evaluate, gridmatch, stations, timelag


def test_wide_to_long_codes_and_hour_ending():
    t = pd.DataFrame({"st": ["A"], "item": ["PM"], "y": [2020], "m": [4], "d": [1],
                      **{f"h{i:02d}": [10] for i in range(1, 25)}})
    t.loc[0, "h01"], t.loc[0, "h02"], t.loc[0, "h03"] = 9999, 9997, 9998
    fmt = stations.WideHourlyFormat(hour_columns=[f"h{i:02d}" for i in range(1, 25)], date_columns=["y", "m", "d"],
                                    id_columns=["st", "item"], status_codes={9999: "missing", 9997: "error"},
                                    drop_codes=[9998])
    long = stations.to_long(t, fmt, scale={"PM": 0.1}, scale_key="item")
    assert len(long) == 23                                   # 9998 removed
    assert long.iloc[0].time_start == pd.Timestamp("2020-04-01 00:00")
    assert long.iloc[0].hour_label == 1 and long.iloc[0].status == "missing"
    assert np.isclose(long[long.status == "ok"].value.iloc[0], 1.0)
    cov = catalog.coverage(long, ["st"], "time_start")
    assert np.isclose(cov.missing_rate[0], 2 / 23)


def test_lambert_grid_centre_and_outside():
    g = gridmatch.LambertGrid(lat1=30, lat2=60, lon0=10, lat0=45, x_orig=-50_000, y_orig=-50_000,
                              cell=10_000, ncols=10, nrows=10)
    x, y = g.project(45, 10)
    assert abs(x) < 1e-6 and abs(y) < 1e-6
    pts = pd.DataFrame({"lat": [45.0, 60.0], "lon": [10.0, 10.0]})
    out = gridmatch.match(pts, g)
    assert out.inside.tolist() == [True, False]
    assert (out.col[0], out.row[0]) == (5, 5)
    assert out.col[1] == -1


def test_regular_grid():
    g = gridmatch.RegularLatLonGrid(lat_first=60, lon_first=-10, dlat=-0.75, dlon=0.75, nrows=30, ncols=43)
    inside, col, row, dist = g.index([48.85], [2.35])
    assert inside[0] and row[0] == 15 and col[0] == 16 and dist[0] < 60_000


def test_metrics_and_summary():
    o = np.arange(1, 11, dtype=float)
    s = evaluate.metrics(o, 0.8 * o)
    assert np.isclose(s["NMB_pct"], -20) and np.isclose(s["r"], 1)
    p = pd.DataFrame({"g": ["a"] * 10 + ["b"] * 10, "obs": np.r_[o, o], "mod": np.r_[o, o * 1.1]})
    t = evaluate.summarize(p, by=["g"])
    assert np.allclose(t.NMB_pct, [0, 10])


def test_daily_from_hourly_completeness():
    t = pd.date_range("2020-01-01", periods=48, freq="h")
    v = np.ones(48); v[30:] = np.nan                         # second day has 6 valid hours
    d = evaluate.daily_from_hourly(pd.DataFrame({"s": "A", "t": t, "v": v}), "s", "t", "v", min_hours=20)
    assert len(d) == 1 and d.date[0] == pd.Timestamp("2020-01-01")


def test_lag_detection():
    t = pd.date_range("2020-01-01", periods=24 * 60, freq="h")
    rng = np.random.default_rng(1)
    signal = np.sin(2 * np.pi * t.hour / 24) + 0.2 * rng.normal(size=len(t))
    obs = pd.Series(signal, index=t)
    mod = pd.Series(signal, index=t - pd.Timedelta(hours=5))   # model stamped 5 h early
    assert timelag.best_lag(obs, mod) == 5


def test_fiscal_year():
    d = pd.Series(pd.to_datetime(["2020-03-31", "2020-04-01"]))
    assert evaluate.fiscal_year(d).tolist() == [2019, 2020]


def test_manifest_and_coverage(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    m = catalog.file_manifest(tmp_path)
    assert m.path.tolist() == ["a.txt"] and len(m.sha256[0]) == 64
    long = pd.DataFrame({"k": "A", "t": pd.date_range("2019-12-31", periods=4, freq="D"),
                         "status": ["ok", "missing", "ok", "ok"]})
    c = catalog.coverage(long, ["k"], "t")
    assert c.n_years[0] == 2 and np.isclose(c.missing_rate[0], 0.25)
