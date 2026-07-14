"""Live ISO data client. Pulls real CAISO data via gridstatus; ERCOT/PJM optional.

We pull real load + real fuel mix (free, public, no auth). Carbon intensity is
derived from the fuel mix. Stress score is derived from load-to-peak ratio.
LMP is partially synthetic (CAISO's free CSV doesn't carry LMPs at the BA
level — true LMPs need OASIS API which is slower); we drive it from stress.

Anywhere a live pull fails, we fall back to a plausible synthetic so the demo
never breaks.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time

from gridstatus import CAISO, Ercot, PJM
from murmuration.data.eia_client import EIAClient

log = logging.getLogger(__name__)

# rough emission intensities (g CO2 / kWh) by fuel type
CARBON_FACTORS = {
    "Solar": 20,
    "Wind": 11,
    "Geothermal": 38,
    "Biomass": 230,
    "Biogas": 230,
    "Small Hydro": 10,
    "Large Hydro": 10,
    "Nuclear": 12,
    "Natural Gas": 490,
    "Coal": 950,
    "Oil": 700,
    "Imports": 450,        # CAISO imports are mixed; assume gas-heavy
    "Batteries": 0,        # zero-sum over time
    "Other": 400,
}

# rough peak-load anchors (MW) per BA, used to scale stress
PEAK_LOAD = {
    "CAISO":  50_000,
    "ERCOT":  85_000,
    "PJM":   165_000,
    "MISO":  127_000,
    "NYISO":  32_000,
    "ISO-NE": 26_000,
    "SPP":    57_000,
}


@dataclass
class BaSnapshot:
    timestamp: datetime
    ba: str
    load_mw: float
    headroom_mw: float
    carbon_g_kwh: float
    lmp_dollars_mwh: float
    stress_score: float        # 0–1
    fuel_mix: dict[str, float]
    notes: str = ""


def _carbon_from_mix(mix: dict[str, float]) -> float:
    """Weighted average gCO2/kWh from a fuel-mix dict (MW values, can be negative for batteries)."""
    total = sum(max(v, 0) for v in mix.values())
    if total <= 0:
        return 350.0
    weighted = sum(max(v, 0) * CARBON_FACTORS.get(k, 400) for k, v in mix.items())
    return weighted / total


def _stress_from_load(ba: str, load_mw: float) -> tuple[float, float]:
    """Return (stress_score, headroom_mw)."""
    peak = PEAK_LOAD.get(ba, 50_000)
    ratio = load_mw / peak
    # below 60% of peak -> 0 stress; above 95% -> 1.0
    stress = max(0.0, min(1.0, (ratio - 0.6) / 0.35))
    headroom = max(0.0, peak * 0.95 - load_mw)
    return stress, headroom


def _lmp_from_stress(stress: float, base: float = 30.0) -> float:
    """Synthetic LMP curve. Real LMPs require OASIS calls; this is plausible
    enough for the protocol demo and is overridden when scenarios inject spikes."""
    # convex shape: cheap when relaxed, exponential when stressed
    return base + (stress ** 2) * 380.0


class ISOClient:
    def __init__(self):
        # lazy-init: ERCOT and PJM may need API keys; we only construct on demand
        self._caiso = CAISO()
        self._ercot: Ercot | None = None
        self._pjm: PJM | None = None
        self._eia = EIAClient()    # picks up EIA_API_KEY from env
        if self._eia.enabled:
            log.info("EIA-930 client enabled — ERCOT/PJM will use real fuel mix")
        else:
            log.info("EIA_API_KEY not set — ERCOT/PJM stay synthetic")
        self._cache: dict[str, tuple[float, BaSnapshot]] = {}
        self._cache_ttl_sec = 60.0
        self._lmp_overrides: dict[str, float] = {}
        self._carbon_overrides: dict[str, float] = {}
        self._stress_overrides: dict[str, float] = {}

    def _ercot_or_none(self) -> Ercot | None:
        if self._ercot is None:
            try:
                self._ercot = Ercot()
            except Exception:
                log.warning("ERCOT client unavailable; using synthetic")
                return None
        return self._ercot

    def _pjm_or_none(self) -> PJM | None:
        if self._pjm is None:
            try:
                self._pjm = PJM()
            except Exception:
                log.info("PJM unavailable (no API key); using synthetic")
                return None
        return self._pjm

    # ---- public ----
    def set_lmp_override(self, ba: str, lmp: float | None) -> None:
        if lmp is None:
            self._lmp_overrides.pop(ba, None)
        else:
            self._lmp_overrides[ba] = lmp

    def set_carbon_override(self, ba: str, ci: float | None) -> None:
        if ci is None:
            self._carbon_overrides.pop(ba, None)
        else:
            self._carbon_overrides[ba] = ci

    def set_stress_override(self, ba: str, stress: float | None) -> None:
        if stress is None:
            self._stress_overrides.pop(ba, None)
        else:
            self._stress_overrides[ba] = stress

    def snapshot(self, ba: str) -> BaSnapshot:
        now = time.time()
        cached = self._cache.get(ba)
        if cached and now - cached[0] < self._cache_ttl_sec:
            return self._apply_override(cached[1], ba)
        snap = self._fresh_snapshot(ba)
        self._cache[ba] = (now, snap)
        return self._apply_override(snap, ba)

    def _apply_override(self, snap: BaSnapshot, ba: str) -> BaSnapshot:
        lmp_override = self._lmp_overrides.get(ba)
        carbon_override = self._carbon_overrides.get(ba)
        stress_override = self._stress_overrides.get(ba)
        if lmp_override is None and carbon_override is None and stress_override is None:
            return snap
        new_lmp = lmp_override if lmp_override is not None else snap.lmp_dollars_mwh
        new_carbon = carbon_override if carbon_override is not None else snap.carbon_g_kwh
        if stress_override is not None:
            new_stress = stress_override
        elif lmp_override is not None and lmp_override > 30:
            # derive stress from overridden LMP — inverse of _lmp_from_stress
            new_stress = max(snap.stress_score,
                             min(1.0, ((lmp_override - 30.0) / 380.0) ** 0.5))
        else:
            new_stress = snap.stress_score
        return BaSnapshot(**{
            **snap.__dict__,
            "lmp_dollars_mwh": new_lmp,
            "carbon_g_kwh": new_carbon,
            "stress_score": new_stress,
            "notes": (snap.notes + " [scenario override]").strip(),
        })

    # ---- internals ----
    def _fresh_snapshot(self, ba: str) -> BaSnapshot:
        try:
            if ba == "CAISO":
                return self._caiso_snapshot()
            if ba == "ERCOT":
                return self._ercot_snapshot()
            if ba == "PJM":
                return self._pjm_snapshot()
            # All other ISOs (MISO, NYISO, ISO-NE, SPP, ...) -> EIA-only path
            return self._eia_only_snapshot(ba)
        except Exception:
            log.exception("live fetch failed for %s; using synthetic", ba)
        return self._synthetic_snapshot(ba)

    def _eia_only_snapshot(self, ba: str) -> BaSnapshot:
        """Used for ISOs we don't have gridstatus support for.
        Pulls EIA-930 fuel mix and back-derives load from total generation."""
        eia = self._eia.fuel_mix(ba) if self._eia.enabled else None
        if eia is None:
            return self._synthetic_snapshot(ba)
        latest_load = eia.total_mwh
        carbon = eia.carbon_g_kwh
        stress, headroom = _stress_from_load(ba, latest_load)
        notes = f"live {ba} (EIA-930 fuel mix); renewables {eia.renewable_pct:.0%}"
        return BaSnapshot(
            timestamp=datetime.now(timezone.utc),
            ba=ba,
            load_mw=latest_load,
            headroom_mw=headroom,
            carbon_g_kwh=carbon,
            lmp_dollars_mwh=_lmp_from_stress(stress),
            stress_score=stress,
            fuel_mix=eia.fuel_mix_mwh,
            notes=notes,
        )

    def _caiso_snapshot(self) -> BaSnapshot:
        load_df = self._caiso.get_load("today")
        mix_df = self._caiso.get_fuel_mix("today")
        latest_load = float(load_df.iloc[-1]["Load"])
        latest_mix_row = mix_df.iloc[-1]
        mix = {
            col: float(latest_mix_row[col])
            for col in mix_df.columns
            if col not in ("Time", "Interval Start", "Interval End")
        }
        stress, headroom = _stress_from_load("CAISO", latest_load)
        carbon = _carbon_from_mix(mix)
        return BaSnapshot(
            timestamp=datetime.now(timezone.utc),
            ba="CAISO",
            load_mw=latest_load,
            headroom_mw=headroom,
            carbon_g_kwh=carbon,
            lmp_dollars_mwh=_lmp_from_stress(stress),
            stress_score=stress,
            fuel_mix=mix,
            notes=f"live CAISO; renewables {self._renewable_pct(mix):.0%}",
        )

    def _ercot_snapshot(self) -> BaSnapshot:
        # Try EIA-930 first for fuel mix → real carbon. Load synthesized from
        # peak ratio if gridstatus's free dashboard is 403.
        eia = self._eia.fuel_mix("ERCOT") if self._eia.enabled else None
        ercot = self._ercot_or_none()
        latest_load = None
        if ercot is not None:
            try:
                load_df = ercot.get_load("today")
                latest_load = float(load_df.iloc[-1]["Load"])
            except Exception:
                latest_load = None
        if latest_load is None and eia is not None:
            # back-derive total load from EIA fuel mix (sum of all generation)
            latest_load = eia.total_mwh
        if latest_load is None:
            return self._synthetic_snapshot("ERCOT")
        carbon = eia.carbon_g_kwh if eia is not None else 380.0
        stress, headroom = _stress_from_load("ERCOT", latest_load)
        notes = "live ERCOT (EIA-930 fuel mix)" if eia else "live ERCOT load"
        if eia:
            notes += f"; renewables {eia.renewable_pct:.0%}"
        return BaSnapshot(
            timestamp=datetime.now(timezone.utc),
            ba="ERCOT",
            load_mw=latest_load,
            headroom_mw=headroom,
            carbon_g_kwh=carbon,
            lmp_dollars_mwh=_lmp_from_stress(stress),
            stress_score=stress,
            fuel_mix=(eia.fuel_mix_mwh if eia else {}),
            notes=notes,
        )

    def _pjm_snapshot(self) -> BaSnapshot:
        eia = self._eia.fuel_mix("PJM") if self._eia.enabled else None
        pjm = self._pjm_or_none()
        latest_load = None
        if pjm is not None:
            try:
                load_df = pjm.get_load("today")
                latest_load = float(load_df.iloc[-1]["Load"])
            except Exception:
                latest_load = None
        if latest_load is None and eia is not None:
            latest_load = eia.total_mwh
        if latest_load is None:
            return self._synthetic_snapshot("PJM")
        carbon = eia.carbon_g_kwh if eia is not None else 420.0
        stress, headroom = _stress_from_load("PJM", latest_load)
        notes = "live PJM (EIA-930 fuel mix)" if eia else "live PJM load"
        if eia:
            notes += f"; renewables {eia.renewable_pct:.0%}"
        return BaSnapshot(
            timestamp=datetime.now(timezone.utc),
            ba="PJM",
            load_mw=latest_load,
            headroom_mw=headroom,
            carbon_g_kwh=carbon,
            lmp_dollars_mwh=_lmp_from_stress(stress),
            stress_score=stress,
            fuel_mix=(eia.fuel_mix_mwh if eia else {}),
            notes=notes,
        )

    def _synthetic_snapshot(self, ba: str) -> BaSnapshot:
        peak = PEAK_LOAD.get(ba, 50_000)
        load = peak * 0.7
        stress, headroom = _stress_from_load(ba, load)
        return BaSnapshot(
            timestamp=datetime.now(timezone.utc),
            ba=ba,
            load_mw=load,
            headroom_mw=headroom,
            carbon_g_kwh=400.0,
            lmp_dollars_mwh=_lmp_from_stress(stress),
            stress_score=stress,
            fuel_mix={},
            notes="synthetic fallback",
        )

    @staticmethod
    def _renewable_pct(mix: dict[str, float]) -> float:
        total = sum(max(v, 0) for v in mix.values())
        if total <= 0:
            return 0.0
        renewable = sum(
            max(mix.get(k, 0), 0)
            for k in ("Solar", "Wind", "Geothermal", "Biomass", "Biogas",
                      "Small Hydro", "Large Hydro")
        )
        return renewable / total
