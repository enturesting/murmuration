"""EIA-930 client — hourly fuel mix by balancing authority.

Free-tier API key required (set EIA_API_KEY env var). When the key is missing
or the call fails, callers should fall back to synthetic data.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
import time

import httpx

log = logging.getLogger(__name__)

# Map our ISO codes to EIA-930 respondent codes
EIA_RESPONDENT = {
    "CAISO": "CISO",
    "ERCOT": "ERCO",
    "PJM":   "PJM",
    "MISO":  "MISO",
    "NYISO": "NYIS",
    "ISO-NE":"ISNE",
    "SPP":   "SWPP",
}

# rough emission intensities (g CO2 / kWh) per EIA fuel-type code
EIA_CARBON_FACTORS = {
    "COL": 950,   # coal
    "NG":  490,   # natural gas
    "OIL": 700,   # petroleum
    "NUC": 12,    # nuclear
    "WND": 11,    # wind
    "SUN": 20,    # solar
    "WAT": 10,    # hydro
    "GEO": 38,    # geothermal
    "BIO": 230,   # biomass / biogas
    "BAT": 0,     # battery (zero-sum over time)
    "OTH": 400,   # other / unknown
    "PS":  10,    # pumped storage
}


@dataclass
class EiaSnapshot:
    timestamp: datetime
    ba: str
    fuel_mix_mwh: dict[str, float]    # {COL: 7280, NG: 32205, ...} for last hour
    carbon_g_kwh: float
    renewable_pct: float
    total_mwh: float


class EIAClient:
    """Pulls hourly fuel-type-data from EIA-930. Caches per-BA for 15 min."""
    BASE = "https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/"

    def __init__(self, api_key: str | None = None, cache_ttl_sec: float = 900.0):
        self.api_key = api_key or os.getenv("EIA_API_KEY")
        self.cache_ttl = cache_ttl_sec
        self._cache: dict[str, tuple[float, EiaSnapshot]] = {}
        self._client: httpx.Client | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=15.0)
        return self._client

    def fuel_mix(self, ba: str) -> EiaSnapshot | None:
        if not self.enabled:
            return None
        respondent = EIA_RESPONDENT.get(ba)
        if not respondent:
            return None

        now = time.time()
        cached = self._cache.get(ba)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        # pull last 12 hours' worth so we get the most-recent complete hour
        params = {
            "api_key": self.api_key,
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": respondent,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": 0,
            "length": 100,
        }
        try:
            r = self._http().get(self.BASE, params=params)
            r.raise_for_status()
            j = r.json()
        except Exception as e:
            log.warning("EIA fetch failed for %s: %s", ba, e)
            return None

        rows = j.get("response", {}).get("data", [])
        if not rows:
            return None
        # group by period; pick the most recent hour with at least 4 fuel rows
        by_period: dict[str, dict[str, float]] = {}
        for r in rows:
            p = r.get("period")
            ft = r.get("fueltype")
            v = r.get("value")
            if p is None or ft is None or v is None:
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            by_period.setdefault(p, {})[ft] = v
        complete = [(p, m) for p, m in by_period.items() if len(m) >= 4]
        if not complete:
            return None
        # most recent complete hour
        complete.sort(key=lambda kv: kv[0], reverse=True)
        period, mix = complete[0]

        total = sum(max(v, 0) for v in mix.values())
        if total <= 0:
            return None
        weighted = sum(max(v, 0) * EIA_CARBON_FACTORS.get(ft, 400)
                       for ft, v in mix.items())
        ci = weighted / total
        renewable = sum(max(mix.get(k, 0), 0)
                        for k in ("WND", "SUN", "WAT", "GEO", "BIO"))
        renewable_pct = renewable / total if total else 0

        snap = EiaSnapshot(
            timestamp=datetime.now(timezone.utc),
            ba=ba,
            fuel_mix_mwh=mix,
            carbon_g_kwh=ci,
            renewable_pct=renewable_pct,
            total_mwh=total,
        )
        self._cache[ba] = (now, snap)
        log.info("EIA-930 %s: %d fuel types, CI=%.0fg/kWh, renewables=%.0f%%, total=%.0f MWh",
                 ba, len(mix), ci, renewable_pct * 100, total)
        return snap
