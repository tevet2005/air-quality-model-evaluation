"""Match point locations (monitors, clinics, residences) to model grid cells.

Two grid types are supported without extra dependencies:

* ``LambertGrid``: Lambert conformal conic grid on a sphere, as used by many regional
  chemical-transport and weather models (two standard parallels, a reference
  longitude/latitude, lower-left corner offsets and a square cell size).
* ``RegularLatLonGrid``: regular latitude/longitude grid (reanalyses, global models).

``match`` returns, for each point, whether it lies inside the grid, the 0-based
column/row and the distance from the point to the cell centre.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

EARTH_RADIUS_M = 6_370_000.0


@dataclass(frozen=True)
class LambertGrid:
    lat1: float          # first standard parallel (deg)
    lat2: float          # second standard parallel (deg)
    lon0: float          # central meridian (deg)
    lat0: float          # latitude of projection origin (deg)
    x_orig: float        # x of the lower-left grid corner (m)
    y_orig: float        # y of the lower-left grid corner (m)
    cell: float          # cell size (m)
    ncols: int
    nrows: int
    radius: float = EARTH_RADIUS_M

    def _consts(self):
        p1, p2, p0 = np.radians([self.lat1, self.lat2, self.lat0])
        if np.isclose(p1, p2):
            n = np.sin(p1)
        else:
            n = np.log(np.cos(p1) / np.cos(p2)) / np.log(np.tan(np.pi / 4 + p2 / 2) / np.tan(np.pi / 4 + p1 / 2))
        f = np.cos(p1) * np.tan(np.pi / 4 + p1 / 2) ** n / n
        rho0 = self.radius * f / np.tan(np.pi / 4 + p0 / 2) ** n
        return n, f, rho0

    def project(self, lat, lon):
        """Degrees -> projected x, y (m)."""
        n, f, rho0 = self._consts()
        phi, lam = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
        rho = self.radius * f / np.tan(np.pi / 4 + phi / 2) ** n
        theta = n * (lam - np.radians(self.lon0))
        return rho * np.sin(theta), rho0 - rho * np.cos(theta)

    def index(self, lat, lon):
        x, y = self.project(lat, lon)
        fc, fr = (x - self.x_orig) / self.cell, (y - self.y_orig) / self.cell
        col, row = np.floor(fc).astype(int), np.floor(fr).astype(int)
        inside = (col >= 0) & (col < self.ncols) & (row >= 0) & (row < self.nrows)
        dist = np.hypot(fc - col - 0.5, fr - row - 0.5) * self.cell
        return inside, col, row, dist


@dataclass(frozen=True)
class RegularLatLonGrid:
    lat_first: float     # latitude of the first row centre (deg); rows may run north -> south
    lon_first: float     # longitude of the first column centre (deg)
    dlat: float          # signed step between row centres (deg)
    dlon: float          # step between column centres (deg)
    nrows: int
    ncols: int

    def index(self, lat, lon):
        lat, lon = np.asarray(lat, float), np.asarray(lon, float)
        row = np.rint((lat - self.lat_first) / self.dlat).astype(int)
        col = np.rint((lon - self.lon_first) / self.dlon).astype(int)
        inside = (col >= 0) & (col < self.ncols) & (row >= 0) & (row < self.nrows)
        clat, clon = self.lat_first + row * self.dlat, self.lon_first + col * self.dlon
        return inside, col, row, haversine_m(lat, lon, clat, clon)


def haversine_m(lat1, lon1, lat2, lon2, radius: float = EARTH_RADIUS_M):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dlam = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2) ** 2
    return 2 * radius * np.arcsin(np.sqrt(a))


def match(points: pd.DataFrame, grid, lat: str = "lat", lon: str = "lon", prefix: str = "") -> pd.DataFrame:
    """Add <prefix>inside, <prefix>col, <prefix>row, <prefix>dist_m (col/row = -1 when outside)."""
    inside, col, row, dist = grid.index(points[lat].to_numpy(), points[lon].to_numpy())
    out = points.copy()
    out[f"{prefix}inside"] = inside
    out[f"{prefix}col"] = np.where(inside, col, -1)
    out[f"{prefix}row"] = np.where(inside, row, -1)
    out[f"{prefix}dist_m"] = np.where(inside, dist, np.nan)
    return out
