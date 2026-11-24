import numpy as np
import pandas as pd

from aqeval import qc


def test_clean_masks_error_codes():
    s = qc.clean(pd.Series(["10", 9999, "x", 5]))
    assert s.isna().tolist() == [False, True, True, False]


def test_completeness_counts_against_expected_index():
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    s = pd.Series([1.0, np.nan], index=idx[:2])
    rep = qc.completeness(s.rename("pm"), idx)
    assert rep.loc["pm", "valid"] == 1 and rep.loc["pm", "missing_rate"] == 0.75


def test_daily_mean_hour_ending_and_threshold():
    # hour-ending stamps 01:00..24:00 (=next day 00:00) belong to one day
    idx = pd.date_range("2024-01-01 01:00", periods=24, freq="h")
    s = pd.Series(1.0, index=idx)
    d = qc.daily_mean(s, min_valid_hours=20)
    assert list(d.index) == [pd.Timestamp("2024-01-01")] and d.iloc[0] == 1.0
    s.iloc[:5] = np.nan  # only 19 valid hours
    assert qc.daily_mean(s, min_valid_hours=20).isna().all()


def test_to_timezone_from_utc():
    idx = pd.DatetimeIndex(["2024-01-01 00:00"])
    assert qc.to_timezone(idx, "Asia/Kolkata")[0] == pd.Timestamp("2024-01-01 05:30")


