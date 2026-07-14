"""NREL PVWatts client — hourly solar capacity-factor profile per location.

PVWatts returns a TMY (typical meteorological year) hourly profile, so this
gives us a "normal solar shape" for any lat/lon. Used as a feature in the
forecaster to anchor carbon-intensity predictions to expected solar output.

Free-tier API key required (set NREL_API_KEY env var). Falls back to a
synthesized diurnal solar curve when the key is absent or call fails.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
import os

import httpx

log = logging.getLogger(__name__)


@dataclass
class SolarProfile:
    """Hourly capacity factor (0..1) for a year — but we collapse to a
    representative-day shape (24 hours) for use in forecasting."""
    lat: float
    lon: float
    hourly_avg_kw_per_kw: list[float]    # length 24, indexed by local hour
    annual_capacity_factor: float
    annual_kwh_per_kw: float


class NRELClient:
    BASE = "https://developer.nrel.gov/api/pvwatts/v8.json"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("NREL_API_KEY")
        self._client: httpx.Client | None = None
        self._cache: dict[tuple[float, float], SolarProfile] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=20.0)
        return self._client

    def solar_profile(self, lat: float, lon: float) -> SolarProfile | None:
        key = (round(lat, 2), round(lon, 2))
        if key in self._cache:
            return self._cache[key]
        if not self.enabled:
            return None
        params = {
            "api_key": self.api_key,
            "lat": lat,
            "lon": lon,
            "system_capacity": 1,    # 1 kW reference system → output is capacity factor
            "module_type": 0,
            "array_type": 1,
            "losses": 14,
            "tilt": abs(lat),
            "azimuth": 180,
            "timeframe": "hourly",
            "dataset": "tmy3",
        }
        try:
            r = self._http().get(self.BASE, params=params)
            r.raise_for_status()
            j = r.json()
        except Exception as e:
            log.warning("NREL PVWatts fetch failed for (%s, %s): %s", lat, lon, e)
            return None
        out = j.get("outputs") or {}
        ac_hourly = out.get("ac")    # 8760 hourly Wh values (1 kW system)
        if not ac_hourly or len(ac_hourly) < 24:
            return None
        # collapse 8760 hours → 24-hour average shape (kW per kW installed)
        hourly_avg = [0.0] * 24
        counts = [0] * 24
        for i, wh in enumerate(ac_hourly):
            h = i % 24
            hourly_avg[h] += float(wh) / 1000.0    # Wh -> kWh
            counts[h] += 1
        hourly_avg = [hourly_avg[h] / max(counts[h], 1) for h in range(24)]
        cf = float(out.get("capacity_factor", 0.0)) / 100.0
        ann = float(out.get("ac_annual", 0.0))
        prof = SolarProfile(
            lat=lat, lon=lon,
            hourly_avg_kw_per_kw=hourly_avg,
            annual_capacity_factor=cf,
            annual_kwh_per_kw=ann,
        )
        self._cache[key] = prof
        log.info("NREL PVWatts (%.2f, %.2f): CF=%.1f%%, peak %.2f kW/kW at h=%d",
                 lat, lon, cf * 100, max(hourly_avg), hourly_avg.index(max(hourly_avg)))
        return prof


def expected_solar_now(profile: SolarProfile | None, t: datetime) -> float:
    """Return expected fraction of rated solar (0..1) at time t.
    Uses local-hour-of-day as the index. Caller scales by installed capacity."""
    if profile is None:
        # fallback: simple sine wave peaked at noon
        h = t.hour + t.minute / 60.0
        if h < 6 or h > 18:
            return 0.0
        return max(0.0, math.sin((h - 6) / 12 * math.pi)) * 0.5
    h = (t.hour + t.minute / 60.0) % 24
    lo = int(h)
    hi = (lo + 1) % 24
    frac = h - lo
    return profile.hourly_avg_kw_per_kw[lo] * (1 - frac) + profile.hourly_avg_kw_per_kw[hi] * frac
