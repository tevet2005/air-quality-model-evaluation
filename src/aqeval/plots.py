"""Standard figures for model-vs-observation evaluation (needs matplotlib)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import evaluate


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def monthly_timeseries(pairs: pd.DataFrame, path, label: str = "", unit: str = ""):
    """Monthly means of paired station-days (observed vs model) with station counts."""
    plt = _plt()
    g = pairs.set_index("date").groupby(pd.Grouper(freq="MS"))
    mo, ns = g[["obs", "mod"]].mean(), g["station"].nunique()
    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax2 = ax.twinx()
    ax2.fill_between(ns.index, ns.values, color="tab:blue", alpha=0.12, step="mid")
    ax2.set_ylabel("stations", color="tab:blue")
    ax.plot(mo.index, mo["obs"], c="k", lw=1.3, label="observed")
    ax.plot(mo.index, mo["mod"], c="tab:red", lw=1.3, label="model")
    ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
    ax.set_ylabel(f"{label} [{unit}]"); ax.legend(loc="upper right", ncol=2)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def scatter(pairs: pd.DataFrame, path, label: str = "", unit: str = ""):
    plt = _plt()
    s = evaluate.metrics(pairs["obs"], pairs["mod"])
    hi = np.nanpercentile(np.r_[pairs["obs"], pairs["mod"]], 99.5)
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    ax.hexbin(pairs["obs"], pairs["mod"], gridsize=50, extent=(0, hi, 0, hi), bins="log", mincnt=1, cmap="viridis")
    ax.plot([0, hi], [0, hi], "w--", lw=1)
    ax.set_xlim(0, hi); ax.set_ylim(0, hi); ax.set_aspect("equal")
    ax.set_xlabel(f"observed [{unit}]"); ax.set_ylabel(f"model [{unit}]"); ax.set_title(label)
    ax.text(0.03, 0.97, f"n={s['n']:,}\nr={s['r']:.2f}\nNMB={s['NMB_pct']:+.0f}%\nRMSE={s['RMSE']:.1f}",
            transform=ax.transAxes, va="top", fontsize=8, bbox=dict(facecolor="w", alpha=0.85, edgecolor="none"))
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def yearly_bias(pairs: pd.DataFrame, path, group: str = "station_type", year: str = "year"):
    """NMB and r per year, one line per group."""
    plt = _plt()
    import matplotlib.ticker as mt
    t = evaluate.summarize(pairs, by=[group, year])
    fig, axes = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
    for (k, g), ls in zip(t.groupby(group), ["-", "--", ":", "-."]):
        axes[0].plot(g[year], g["NMB_pct"], ls, marker="o", ms=3, label=str(k))
        axes[1].plot(g[year], g["r"], ls, marker="o", ms=3)
    axes[0].axhline(0, c="k", lw=0.8); axes[0].set_ylabel("NMB [%]"); axes[0].legend()
    axes[1].set_ylabel("r (daily)"); axes[1].set_xlabel(year)
    axes[1].xaxis.set_major_locator(mt.MaxNLocator(integer=True))
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def lag_scan(scan: pd.DataFrame, path, title: str = ""):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.plot(scan["lag_hours"], scan["r"], marker="o", ms=3)
    best = scan.loc[scan["r"].idxmax()]
    ax.axvline(best["lag_hours"], c="tab:red", lw=1, ls="--")
    ax.set_xlabel("shift applied to model time [h]"); ax.set_ylabel("correlation r")
    ax.set_title(title or f"best shift: {int(best['lag_hours']):+d} h")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
