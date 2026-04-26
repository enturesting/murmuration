"""
gridcache.py — Read-only data layer for synthetic (or real) grid data.

Both agents and the heuristic baseline call this module. It enforces
time-of-decision discipline: from sim_time T, the caller can see
- everything historical (ts <= T)
- forecasts for the future (lmp_da, load_forecast) — these were published
  in advance, so seeing them at T is legitimate
- but NOT future real-time values (lmp_rt, actual load, actual carbon)

This prevents the agent from accidentally cheating during replay.

Two API surfaces:
- Agent-facing: get_zone_conditions, get_all_zones_snapshot, get_recent_history,
  get_forecast — these return ONLY decision-relevant signals.
- Simulator/baseline-facing: get_full_row, get_window, load_grid — these
  return raw data for evaluation and analytics. Don't pass these to LLM tools.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd


DATA_DIR = Path("data")
GRID_STEM = "synthetic_grid"
JOBS_STEM = "synthetic_jobs"

# Signals exposed to the agent. Per-fuel generation columns are deliberately
# excluded — they're plumbing the agent shouldn't reason over directly.
AGENT_SIGNALS = [
    "load_mw",
    "load_forecast_mw",
    "lmp_rt_usd_per_mwh",
    "lmp_da_usd_per_mwh",
    "carbon_g_per_kwh",
    "stress_score",
    "is_peak_hour",
    "utilization",
]


# ---------------------------------------------------------------------------
# Loading (parquet preferred, csv fallback — matches synthetic_grid.py)
# ---------------------------------------------------------------------------

def _load_dataframe(stem: str) -> pd.DataFrame:
    parquet_path = DATA_DIR / f"{stem}.parquet"
    csv_path = DATA_DIR / f"{stem}.csv"
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        # CSV loses dtype info for timestamps — re-parse.
        for col in df.columns:
            if "ts_utc" in col:
                df[col] = pd.to_datetime(df[col], utc=True)
        return df
    raise FileNotFoundError(
        f"Could not find {parquet_path} or {csv_path}. "
        "Run synthetic_grid.py first."
    )


@lru_cache(maxsize=1)
def load_grid() -> pd.DataFrame:
    """Return the full grid DataFrame. Cached after first load."""
    df = _load_dataframe(GRID_STEM)
    if not isinstance(df["ts_utc"].dtype, pd.DatetimeTZDtype):
        df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df


@lru_cache(maxsize=1)
def load_jobs() -> pd.DataFrame:
    """Return the full jobs DataFrame. Cached after first load."""
    return _load_dataframe(JOBS_STEM)


def available_zones() -> list[str]:
    return sorted(load_grid()["zone"].unique().tolist())


def time_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    g = load_grid()
    return g["ts_utc"].min(), g["ts_utc"].max()


# ---------------------------------------------------------------------------
# Internal helpers (used by simulator + baselines, NOT exposed to agents)
# ---------------------------------------------------------------------------

def _normalize_ts(ts) -> pd.Timestamp:
    """Accept str or Timestamp, return UTC-aware Timestamp."""
    t = pd.Timestamp(ts)
    if t.tz is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return t


def get_full_row(zone: str, sim_time) -> Optional[pd.Series]:
    """Get the full data row for a zone at a specific time. Internal use."""
    g = load_grid()
    sim_time = _normalize_ts(sim_time)
    rows = g[(g["zone"] == zone) & (g["ts_utc"] == sim_time)]
    if rows.empty:
        return None
    return rows.iloc[0]


def get_window(zone: str, start, end) -> pd.DataFrame:
    """Slice grid data for a zone between [start, end). Internal use."""
    g = load_grid()
    start, end = _normalize_ts(start), _normalize_ts(end)
    return g[
        (g["zone"] == zone)
        & (g["ts_utc"] >= start)
        & (g["ts_utc"] < end)
    ].copy()


# ---------------------------------------------------------------------------
# Agent-facing API — returns only decision-relevant signals
# ---------------------------------------------------------------------------

def get_zone_conditions(zone: str, sim_time) -> dict:
    """
    Current conditions for one zone at sim_time.
    Used by the grid agent's briefing tool.
    """
    row = get_full_row(zone, sim_time)
    if row is None:
        return {"zone": zone, "error": f"no data for {zone} at {sim_time}"}

    out = {"zone": zone, "ts_utc": row["ts_utc"].isoformat()}
    for col in AGENT_SIGNALS:
        v = row[col]
        if hasattr(v, "item"):    # unwrap numpy scalar
            v = v.item()
        out[col] = v
    return out


def get_all_zones_snapshot(sim_time) -> dict:
    """One-shot conditions for all zones at sim_time. Saves tool-call round-trips."""
    return {
        "ts_utc": _normalize_ts(sim_time).isoformat(),
        "zones": {z: get_zone_conditions(z, sim_time) for z in available_zones()},
    }


def get_recent_history(zone: str, sim_time, hours_back: int = 24) -> dict:
    """
    Summary of the last `hours_back` hours for `zone`, ending at sim_time.
    Returns aggregates rather than raw rows — agents reason better over summaries
    and we save tokens.
    """
    sim_time = _normalize_ts(sim_time)
    start = sim_time - pd.Timedelta(hours=hours_back)
    window = get_window(zone, start, sim_time)
    if window.empty:
        return {"zone": zone, "error": "no data"}

    return {
        "zone": zone,
        "from_ts_utc": start.isoformat(),
        "to_ts_utc": sim_time.isoformat(),
        "hours": len(window),
        "lmp_rt_avg": round(float(window["lmp_rt_usd_per_mwh"].mean()), 2),
        "lmp_rt_max": round(float(window["lmp_rt_usd_per_mwh"].max()), 2),
        "lmp_rt_min": round(float(window["lmp_rt_usd_per_mwh"].min()), 2),
        "carbon_avg": round(float(window["carbon_g_per_kwh"].mean()), 1),
        "carbon_min": round(float(window["carbon_g_per_kwh"].min()), 1),
        "stress_max": int(window["stress_score"].max()),
        "peak_hours_count": int(window["is_peak_hour"].sum()),
        "load_avg": round(float(window["load_mw"].mean()), 1),
        "load_max": round(float(window["load_mw"].max()), 1),
    }


def get_forecast(zone: str, sim_time, hours_ahead: int = 24) -> dict:
    """
    Forward-looking signals for the next `hours_ahead` hours.

    Time-of-decision: returns ONLY signals that would have been available
    at sim_time — day-ahead LMP and published load forecast. Does NOT return
    future real-time prices, even though we technically have them in the
    parquet (this is a replay, after all).
    """
    sim_time = _normalize_ts(sim_time)
    # Inclusive of sim_time + hours_ahead so caller asking for "next 6h" gets 7 rows
    end = sim_time + pd.Timedelta(hours=hours_ahead + 1)
    window = get_window(zone, sim_time, end)
    if window.empty:
        return {"zone": zone, "error": "no data"}

    hours = [
        {
            "ts_utc": r["ts_utc"].isoformat(),
            "lmp_da_usd_per_mwh": round(float(r["lmp_da_usd_per_mwh"]), 2),
            "load_forecast_mw": round(float(r["load_forecast_mw"]), 1),
        }
        for _, r in window.iterrows()
    ]
    return {
        "zone": zone,
        "from_ts_utc": sim_time.isoformat(),
        "hours_ahead": hours_ahead,
        "hourly": hours,
    }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("Loading data…")
    g = load_grid()
    j = load_jobs()
    t0, t1 = time_range()
    print(f"  grid: {len(g):,} rows, zones {available_zones()}")
    print(f"  time: {t0} → {t1}")
    print(f"  jobs: {len(j)} rows")

    # Pick sim_time in the middle of the heat dome scenario (hour 72)
    sim_time = t0 + pd.Timedelta(hours=72)
    print(f"\nUsing sim_time = {sim_time}  (hour 72, mid-DOM-heat-dome)\n")

    print("--- get_zone_conditions('DOM') ---")
    print(json.dumps(get_zone_conditions("DOM", sim_time), indent=2, default=str))

    print("\n--- get_all_zones_snapshot — one-line per zone ---")
    snap = get_all_zones_snapshot(sim_time)
    for z, conds in snap["zones"].items():
        print(f"  {z:6s}  lmp_rt=${conds['lmp_rt_usd_per_mwh']:7.2f}  "
              f"carbon={conds['carbon_g_per_kwh']:5.0f}  "
              f"stress={conds['stress_score']}  "
              f"peak={conds['is_peak_hour']}")

    print("\n--- get_recent_history('DOM', 24h back) ---")
    print(json.dumps(get_recent_history("DOM", sim_time, 24), indent=2, default=str))

    print("\n--- get_forecast('ERCOT', 6h ahead) ---")
    fc = get_forecast("ERCOT", sim_time, 6)
    print(f"  next 6 hours of ERCOT day-ahead LMP & load forecast:")
    for h in fc["hourly"][:7]:
        print(f"    {h['ts_utc']}  ${h['lmp_da_usd_per_mwh']:7.2f}/MWh  "
              f"{h['load_forecast_mw']:.0f} MW")

    print("\nAll checks passed.")