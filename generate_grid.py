"""
synthetic_grid.py — Generate signal-rich grid data for 4 zones (DOM, COMED, AEP, ERCOT).

Outputs to ./data/:
    synthetic_grid.parquet or synthetic_grid.csv
    synthetic_jobs.parquet or synthetic_jobs.csv
    synthetic_scenarios.json

Schema for the agent's data layer:
    Grid:
        ts_utc, zone,
        load_mw, load_forecast_mw,
        lmp_rt_usd_per_mwh, lmp_da_usd_per_mwh,
        carbon_g_per_kwh,
        wind_mw, solar_mw, nuclear_mw,
        coal_mw, gas_baseload_mw, gas_peaker_mw,
        utilization, stress_score, is_peak_hour

    Jobs:
        job_id, kind, sla,
        duration_hours, power_mw,
        submitted_ts_utc, deadline_ts_utc,
        region_flexible, pinned_zone,
        max_price_usd_per_mwh, bid_type

Usage:
    python synthetic_grid.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

START = pd.Timestamp("2024-07-15 00:00", tz="UTC")
HOURS = 14 * 24
SEED = 42
OUT_DIR = Path("data")

# tz_offset_h is summer DST offset, used for solar curve alignment to local noon
ZONES = {
    "DOM": {
        "label": "Dominion (Northern Virginia)",
        "tz_offset_h": -4,
        "base_load_mw": 14000,
        "load_amplitude_mw": 5000,
        "weather_sensitivity": 1.0,
        "nuclear_mw": 4000,
        "wind_capacity_mw": 400,
        "solar_capacity_mw": 600,
        "coal_capacity_mw": 1500,
        "gas_baseload_capacity_mw": 9000,
        "gas_peaker_capacity_mw": 4000,
    },
    "COMED": {
        "label": "ComEd (Chicago)",
        "tz_offset_h": -5,
        "base_load_mw": 11000,
        "load_amplitude_mw": 3500,
        "weather_sensitivity": 0.7,
        "nuclear_mw": 11000,
        "wind_capacity_mw": 2000,
        "solar_capacity_mw": 800,
        "coal_capacity_mw": 1000,
        "gas_baseload_capacity_mw": 4000,
        "gas_peaker_capacity_mw": 2500,
    },
    "AEP": {
        "label": "AEP (Ohio/WV/KY)",
        "tz_offset_h": -4,
        "base_load_mw": 16000,
        "load_amplitude_mw": 4500,
        "weather_sensitivity": 0.6,
        "nuclear_mw": 2300,
        "wind_capacity_mw": 4000,
        "solar_capacity_mw": 1500,
        "coal_capacity_mw": 7000,
        "gas_baseload_capacity_mw": 7000,
        "gas_peaker_capacity_mw": 3000,
    },
    "ERCOT": {
        "label": "ERCOT (Texas)",
        "tz_offset_h": -5,
        "base_load_mw": 50000,
        "load_amplitude_mw": 18000,
        "weather_sensitivity": 1.1,
        "nuclear_mw": 5000,
        "wind_capacity_mw": 30000,
        "solar_capacity_mw": 25000,
        "coal_capacity_mw": 12000,
        "gas_baseload_capacity_mw": 25000,
        "gas_peaker_capacity_mw": 18000,
    },
}

COST = {
    "wind": 0,
    "solar": 0,
    "nuclear": 8,
    "coal": 28,
    "gas_baseload": 38,
    "gas_peaker": 110,
}

CARBON = {
    "wind": 12,
    "solar": 25,
    "nuclear": 12,
    "coal": 950,
    "gas_baseload": 410,
    "gas_peaker": 480,
}


# ---------------------------------------------------------------------------
# Synthetic grid scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name": "DOM heat dome — forecast bust",
        "start_hour": 60,
        "duration_hours": 36,
        "zones": ["DOM"],
        "temp_boost_f": 12,
        "primary_signals": [
            "actual_demand_above_forecast",
            "stress_score",
            "rt_da_spread",
            "peak_hour_cluster",
        ],
        "story": (
            "3-day heat dome in Northern VA. Day-ahead forecast misses the surge; "
            "actual load runs 15% above forecast for 3 afternoons. RT LMP spikes to $300+ "
            "while DA was set around $80. Stress score climbs from 2 to 5. "
            "Agent move: shift deferrable jobs OUT of DOM, preserve capacity for latency-critical inference."
        ),
    },
    {
        "name": "ERCOT solar-noon arbitrage",
        "start_hour": 132,
        "duration_hours": 6,
        "zones": ["ERCOT"],
        "solar_cf_boost": 0.15,
        "primary_signals": [
            "net_generation_solar_dominant",
            "lmp_zone_differential",
            "carbon_zone_differential",
        ],
        "story": (
            "Texas solar peaks at midday CT, exactly when DOM may be hitting afternoon peak. "
            "LMP differential DOM↔ERCOT widens, and ERCOT carbon intensity drops. "
            "Agent move: route afternoon batch jobs from DOM to ERCOT."
        ),
    },
    {
        "name": "AEP+ERCOT overnight wind ramp",
        "start_hour": 150,
        "duration_hours": 18,
        "zones": ["AEP", "ERCOT"],
        "wind_cf_boost": 0.5,
        "primary_signals": [
            "net_generation_wind_dominant",
            "lmp_near_zero",
            "carbon_minimum",
        ],
        "story": (
            "Frontal system causes wind output to surge overnight in Midwest and Texas. "
            "AEP and ERCOT LMPs go near zero, and carbon intensity falls. "
            "Agent move: pull deferrable jobs FORWARD into this window even from days-out deadlines."
        ),
    },
    {
        "name": "COMED nuclear unit forced outage",
        "start_hour": 210,
        "duration_hours": 8,
        "zones": ["COMED"],
        "nuclear_loss_mw": 1200,
        "primary_signals": [
            "net_generation_drop",
            "stress_score_no_weather",
            "carbon_spike",
            "reserve_margin",
        ],
        "story": (
            "Forced outage at a nuclear unit. Net generation drops 1.2 GW. "
            "Gas comes on margin. Stress score climbs with no weather event. "
            "Agent move: stop treating COMED as a clean haven; route flexible jobs to ERCOT/AEP."
        ),
    },
    {
        "name": "Coincident DOM peak + ERCOT wind+solar",
        "start_hour": 250,
        "duration_hours": 8,
        "zones": ["DOM", "AEP", "ERCOT"],
        "temp_boost_f": 8,
        "wind_cf_boost": 0.5,
        "solar_cf_boost": 0.10,
        "primary_signals": [
            "max_cross_zone_divergence_all_signals",
        ],
        "story": (
            "DOM is stressed from heat while ERCOT has wind and solar surplus. "
            "DOM stress and LMP are high, while ERCOT stress and LMP are low. "
            "Agent move: move the most flexible, highest-power deferrable jobs west first."
        ),
    },
    {
        "name": "Dynamic spot-pricing bid — flexible AI training",
        "start_hour": 150,
        "duration_hours": 24,
        "zones": ["DOM", "AEP", "ERCOT"],
        "primary_signals": [
            "lmp_rt_usd_per_mwh",
            "max_price_usd_per_mwh",
            "deadline_ts_utc",
            "region_flexible",
            "cross_zone_lmp_arbitrage",
            "cost_savings",
        ],
        "story": (
            "A data center submits a spot-style bid: run an 80 MW training job only when "
            "power is below $50/MWh within the next 24 hours. During this window, DOM is "
            "expensive and stressed, while AEP/ERCOT have cheap overnight wind. "
            "Agent move: search all eligible zones and hours, then schedule the job in the "
            "lowest-cost slot below the bid threshold before the deadline."
        ),
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_dataframe(df: pd.DataFrame, path_stem: Path) -> Path:
    """
    Write parquet if pyarrow/fastparquet exists.
    Otherwise fall back to CSV.
    """
    parquet_path = path_stem.with_suffix(".parquet")
    csv_path = path_stem.with_suffix(".csv")

    try:
        df.to_parquet(parquet_path, index=False)
        return parquet_path
    except ImportError:
        df.to_csv(csv_path, index=False)
        return csv_path


def get_job_pricing(kind: str, sla: str) -> tuple[float, str]:
    """
    Assign max willingness-to-pay and bid type.

    Higher max price = workload is more urgent / less flexible.
    Lower max price = workload can wait for cheap power.
    """
    if sla == "latency_critical" or kind == "inference":
        return 300.0, "must_run"

    if kind == "training":
        return 50.0, "spot_flexible"

    if kind == "embed_backfill":
        return 60.0, "spot_flexible"

    if kind == "batch_inference":
        return 80.0, "deadline_flexible"

    if kind == "eval_run":
        return 70.0, "deadline_flexible"

    if kind == "data_pipeline":
        return 35.0, "opportunistic"

    return 75.0, "deadline_flexible"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_grid_data() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    timestamps = pd.date_range(START, periods=HOURS, freq="1h")
    h = np.arange(HOURS)

    hour_of_day_utc = (h + START.hour) % 24
    diurnal = 0.55 + 0.45 * np.sin(2 * np.pi * (hour_of_day_utc - 9) / 24)

    day_of_week = ((h // 24) + START.dayofweek) % 7
    weekend_mult = np.where(day_of_week >= 5, 0.82, 1.0)

    base_temp_dev = (
        6 * np.sin(2 * np.pi * h / (24 * 7))
        + 4 * np.sin(2 * np.pi * (hour_of_day_utc - 14) / 24)
        + rng.normal(0, 1.5, HOURS)
    )

    wind_cf = np.zeros(HOURS)
    wind_cf[0] = 0.35

    for t in range(1, HOURS):
        wind_cf[t] = 0.85 * wind_cf[t - 1] + 0.15 * 0.35 + rng.normal(0, 0.06)

    wind_cf = np.clip(wind_cf, 0.0, 1.0)

    # Scenario perturbations are applied to actual values, not forecast values.
    zone_temp_boost = {z: np.zeros(HOURS) for z in ZONES}
    zone_wind_boost = {z: np.zeros(HOURS) for z in ZONES}
    zone_solar_boost = {z: np.zeros(HOURS) for z in ZONES}
    zone_nuke_loss = {z: np.zeros(HOURS) for z in ZONES}

    for scenario in SCENARIOS:
        a = scenario["start_hour"]
        d = scenario["duration_hours"]

        # Only scenarios with physical perturbation keys affect the grid data.
        # The dynamic spot-pricing scenario is mostly an annotation for the agent layer.
        ramp = np.minimum(np.arange(d), np.arange(d)[::-1]).astype(float)
        ramp = ramp / max(ramp.max(), 1)

        for zone in scenario["zones"]:
            if "temp_boost_f" in scenario:
                zone_temp_boost[zone][a:a + d] += scenario["temp_boost_f"] * ramp

            if "wind_cf_boost" in scenario:
                zone_wind_boost[zone][a:a + d] += scenario["wind_cf_boost"] * ramp

            if "solar_cf_boost" in scenario:
                zone_solar_boost[zone][a:a + d] += scenario["solar_cf_boost"] * ramp

            if "nuclear_loss_mw" in scenario:
                zone_nuke_loss[zone][a:a + d] += scenario["nuclear_loss_mw"]

    rows = []

    for zone_name, cfg in ZONES.items():
        local_hour = (hour_of_day_utc + cfg["tz_offset_h"]) % 24

        solar_base_cf = np.maximum(0, np.sin(np.pi * (local_hour - 6) / 12))
        solar_cf = np.clip(solar_base_cf + zone_solar_boost[zone_name], 0, 1.05)
        solar_mw = cfg["solar_capacity_mw"] * solar_cf

        # Forecast load: baseline forecast, no scenario perturbations.
        weather_cooling_forecast = (
            cfg["weather_sensitivity"] * np.maximum(0, base_temp_dev) ** 1.3 * 80
        )

        load_forecast = (
            cfg["base_load_mw"]
            + cfg["load_amplitude_mw"] * diurnal * weekend_mult
            + weather_cooling_forecast
            + rng.normal(0, cfg["base_load_mw"] * 0.04, HOURS)
        )

        # Actual load: includes scenario weather boosts.
        temp_actual = base_temp_dev + zone_temp_boost[zone_name]

        weather_cooling_actual = (
            cfg["weather_sensitivity"] * np.maximum(0, temp_actual) ** 1.3 * 80
        )

        load_actual = (
            cfg["base_load_mw"]
            + cfg["load_amplitude_mw"] * diurnal * weekend_mult
            + weather_cooling_actual
            + rng.normal(0, cfg["base_load_mw"] * 0.008, HOURS)
        )

        # Dispatch in merit order.
        zone_wind_cf = np.clip(wind_cf + zone_wind_boost[zone_name], 0, 1)
        wind_mw = cfg["wind_capacity_mw"] * zone_wind_cf

        nuclear_mw = np.maximum(0, cfg["nuclear_mw"] - zone_nuke_loss[zone_name])

        residual = np.maximum(0, load_actual - wind_mw - solar_mw - nuclear_mw)

        coal_mw = np.minimum(residual, cfg["coal_capacity_mw"])
        residual = np.maximum(0, residual - coal_mw)

        gas_baseload_mw = np.minimum(residual, cfg["gas_baseload_capacity_mw"])
        residual = np.maximum(0, residual - gas_baseload_mw)

        gas_peaker_mw = np.minimum(residual, cfg["gas_peaker_capacity_mw"])

        # LMP from highest-cost dispatched generation + scarcity + clean suppression.
        lmp = np.full(HOURS, COST["nuclear"], dtype=float)
        lmp = np.where(coal_mw > 0, COST["coal"], lmp)
        lmp = np.where(gas_baseload_mw > 0, COST["gas_baseload"], lmp)
        lmp = np.where(gas_peaker_mw > 0, COST["gas_peaker"], lmp)

        total_capacity = (
            cfg["nuclear_mw"]
            + cfg["wind_capacity_mw"]
            + cfg["solar_capacity_mw"]
            + cfg["coal_capacity_mw"]
            + cfg["gas_baseload_capacity_mw"]
            + cfg["gas_peaker_capacity_mw"]
        )

        utilization = load_actual / total_capacity

        scarcity_adder = 220 / (1 + np.exp(-25 * (utilization - 0.88)))

        clean_share = (wind_mw + solar_mw) / np.maximum(load_actual, 1)
        clean_suppression = 35 * np.maximum(0, clean_share - 0.30)

        lmp_rt = lmp + scarcity_adder - clean_suppression + rng.normal(0, 4, HOURS)
        lmp_rt = np.maximum(lmp_rt, -25)

        # Day-ahead LMP is computed from forecast load.
        residual_da = np.maximum(0, load_forecast - wind_mw - solar_mw - nuclear_mw)

        coal_da = np.minimum(residual_da, cfg["coal_capacity_mw"])
        gas_base_da = np.minimum(
            np.maximum(0, residual_da - coal_da),
            cfg["gas_baseload_capacity_mw"],
        )
        gas_peaker_da = np.minimum(
            np.maximum(0, residual_da - coal_da - gas_base_da),
            cfg["gas_peaker_capacity_mw"],
        )

        lmp_da_marginal = np.full(HOURS, COST["nuclear"], dtype=float)
        lmp_da_marginal = np.where(coal_da > 0, COST["coal"], lmp_da_marginal)
        lmp_da_marginal = np.where(gas_base_da > 0, COST["gas_baseload"], lmp_da_marginal)
        lmp_da_marginal = np.where(gas_peaker_da > 0, COST["gas_peaker"], lmp_da_marginal)

        utilization_da = load_forecast / total_capacity
        scarcity_da = 220 / (1 + np.exp(-25 * (utilization_da - 0.88)))

        lmp_da = lmp_da_marginal + scarcity_da - clean_suppression + rng.normal(0, 8, HOURS)
        lmp_da = np.maximum(lmp_da, -20)

        # Carbon weighted by generation mix serving load.
        gen_total = (
            wind_mw
            + solar_mw
            + nuclear_mw
            + coal_mw
            + gas_baseload_mw
            + gas_peaker_mw
        )
        gen_total = np.maximum(gen_total, 1)

        carbon = (
            wind_mw * CARBON["wind"]
            + solar_mw * CARBON["solar"]
            + nuclear_mw * CARBON["nuclear"]
            + coal_mw * CARBON["coal"]
            + gas_baseload_mw * CARBON["gas_baseload"]
            + gas_peaker_mw * CARBON["gas_peaker"]
        ) / gen_total

        # Stress score from utilization + RT/DA spread.
        rt_da_spread_pct = (lmp_rt - lmp_da) / np.maximum(lmp_da, 5)
        forecast_bust = np.clip(rt_da_spread_pct, 0, 2) / 2
        util_band = np.clip((utilization - 0.65) / 0.30, 0, 1)

        stress_continuous = 0.6 * util_band + 0.4 * forecast_bust
        stress_score = np.clip(np.round(1 + stress_continuous * 4), 1, 5).astype(int)

        # Peak-hour: top 10% load hours per day for each zone.
        load_series = pd.Series(load_actual, index=timestamps)
        daily_threshold = load_series.resample("1D").transform(lambda x: np.percentile(x, 90))
        is_peak_hour = load_series.values >= daily_threshold.values

        for i, ts in enumerate(timestamps):
            rows.append(
                {
                    "ts_utc": ts,
                    "zone": zone_name,
                    "load_mw": round(float(load_actual[i]), 1),
                    "load_forecast_mw": round(float(load_forecast[i]), 1),
                    "lmp_rt_usd_per_mwh": round(float(lmp_rt[i]), 2),
                    "lmp_da_usd_per_mwh": round(float(lmp_da[i]), 2),
                    "carbon_g_per_kwh": round(float(carbon[i]), 1),
                    "wind_mw": round(float(wind_mw[i]), 1),
                    "solar_mw": round(float(solar_mw[i]), 1),
                    "nuclear_mw": round(float(nuclear_mw[i]), 1),
                    "coal_mw": round(float(coal_mw[i]), 1),
                    "gas_baseload_mw": round(float(gas_baseload_mw[i]), 1),
                    "gas_peaker_mw": round(float(gas_peaker_mw[i]), 1),
                    "utilization": round(float(utilization[i]), 3),
                    "stress_score": int(stress_score[i]),
                    "is_peak_hour": bool(is_peak_hour[i]),
                }
            )

    return pd.DataFrame(rows).sort_values(["ts_utc", "zone"]).reset_index(drop=True)


def generate_jobs(num_jobs: int = 25) -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 1)

    job_types = [
        # kind, sla, duration_hours, power_mw, deadline_window_hours, region_flexible
        ("training", "deferrable", 8, 4.0, 72, True),
        ("training", "deferrable", 6, 3.0, 48, True),
        ("training", "deferrable", 12, 5.0, 96, True),
        ("embed_backfill", "deferrable", 4, 2.0, 36, True),
        ("batch_inference", "deferrable", 3, 1.5, 24, True),
        ("inference", "latency_critical", 2, 1.0, 3, False),
        ("inference", "latency_critical", 1, 0.6, 2, False),
        ("inference", "latency_critical", 1, 0.8, 4, False),
        ("eval_run", "deferrable", 6, 2.5, 60, True),
        ("data_pipeline", "opportunistic", 8, 1.0, 168, True),
    ]

    pinnable_zones = ["DOM", "COMED", "AEP"]

    rows = []

    # Add one explicit showcase job for the dynamic pricing demo.
    rows.append(
        {
            "job_id": "j000_spot_training",
            "kind": "training",
            "sla": "deferrable",
            "duration_hours": 6,
            "power_mw": 80.0,
            "submitted_ts_utc": START + pd.Timedelta(hours=150),
            "deadline_ts_utc": START + pd.Timedelta(hours=174),
            "region_flexible": True,
            "pinned_zone": None,
            "max_price_usd_per_mwh": 50.0,
            "bid_type": "spot_flexible",
        }
    )

    for i in range(num_jobs):
        kind, sla, duration, power_mw, deadline_window, is_flexible = job_types[
            rng.integers(0, len(job_types))
        ]

        submitted_h = int(rng.integers(0, HOURS - duration - 1))
        deadline_h = min(
            submitted_h + deadline_window + int(rng.integers(-3, 4)),
            HOURS - 1,
        )

        max_price, bid_type = get_job_pricing(kind, sla)

        rows.append(
            {
                "job_id": f"j{i + 1:03d}",
                "kind": kind,
                "sla": sla,
                "duration_hours": duration,
                "power_mw": power_mw,
                "submitted_ts_utc": START + pd.Timedelta(hours=submitted_h),
                "deadline_ts_utc": START + pd.Timedelta(hours=deadline_h),
                "region_flexible": is_flexible,
                "pinned_zone": None
                if is_flexible
                else pinnable_zones[rng.integers(0, len(pinnable_zones))],
                "max_price_usd_per_mwh": max_price,
                "bid_type": bid_type,
            }
        )

    return pd.DataFrame(rows).sort_values("submitted_ts_utc").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Optional simple scheduler demo
# ---------------------------------------------------------------------------

def recommend_cheapest_slot_for_job(
    grid: pd.DataFrame,
    job: pd.Series,
    max_stress_score: int = 3,
) -> dict:
    """
    Simple demo scheduler.

    Finds the cheapest valid start time and zone for one job, respecting:
        - submitted time
        - deadline
        - region flexibility
        - max price
        - max stress score

    This is not production optimization. It is a hackathon-friendly baseline.
    """
    duration = int(job["duration_hours"])
    latest_start = pd.Timestamp(job["deadline_ts_utc"]) - pd.Timedelta(hours=duration)
    submitted = pd.Timestamp(job["submitted_ts_utc"])

    if bool(job["region_flexible"]):
        candidate_zones = list(ZONES.keys())
    else:
        candidate_zones = [job["pinned_zone"]]

    candidates = grid[
        (grid["zone"].isin(candidate_zones))
        & (grid["ts_utc"] >= submitted)
        & (grid["ts_utc"] <= latest_start)
    ].copy()

    if candidates.empty:
        return {
            "job_id": job["job_id"],
            "status": "no_feasible_window",
            "reason": "No candidate hours before deadline.",
        }

    results = []

    for _, start_row in candidates.iterrows():
        zone = start_row["zone"]
        start_ts = start_row["ts_utc"]
        end_ts = start_ts + pd.Timedelta(hours=duration)

        window = grid[
            (grid["zone"] == zone)
            & (grid["ts_utc"] >= start_ts)
            & (grid["ts_utc"] < end_ts)
        ]

        if len(window) < duration:
            continue

        avg_price = float(window["lmp_rt_usd_per_mwh"].mean())
        max_stress = int(window["stress_score"].max())
        avg_carbon = float(window["carbon_g_per_kwh"].mean())
        total_cost = float(job["power_mw"]) * duration * avg_price

        price_ok = avg_price <= float(job["max_price_usd_per_mwh"])
        stress_ok = max_stress <= max_stress_score

        results.append(
            {
                "job_id": job["job_id"],
                "zone": zone,
                "start_ts_utc": start_ts,
                "end_ts_utc": end_ts,
                "avg_price_usd_per_mwh": round(avg_price, 2),
                "max_price_usd_per_mwh": float(job["max_price_usd_per_mwh"]),
                "price_ok": price_ok,
                "max_stress_score": max_stress,
                "stress_ok": stress_ok,
                "avg_carbon_g_per_kwh": round(avg_carbon, 1),
                "total_energy_cost_usd": round(total_cost, 2),
            }
        )

    if not results:
        return {
            "job_id": job["job_id"],
            "status": "no_feasible_window",
            "reason": "No complete duration window before deadline.",
        }

    result_df = pd.DataFrame(results)

    ideal = result_df[
        (result_df["price_ok"] == True)
        & (result_df["stress_ok"] == True)
    ]

    if not ideal.empty:
        best = ideal.sort_values(
            ["total_energy_cost_usd", "avg_carbon_g_per_kwh"]
        ).iloc[0].to_dict()
        best["status"] = "scheduled"
        return best

    cheapest_avail = result_df.sort_values("avg_price_usd_per_mwh").iloc[0]
    return {
        "job_id": job["job_id"],
        "status": "rejected_no_feasible_slot",
        "reason": (
            f"Cheapest feasible window is "
            f"${cheapest_avail['avg_price_usd_per_mwh']}/MWh "
            f"in {cheapest_avail['zone']}, exceeds bid of "
            f"${job['max_price_usd_per_mwh']}/MWh."
        ),
        "cheapest_zone": cheapest_avail["zone"],
        "cheapest_price_usd_per_mwh": float(cheapest_avail["avg_price_usd_per_mwh"]),
        "bid_usd_per_mwh": float(job["max_price_usd_per_mwh"]),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    grid = generate_grid_data()
    grid_path = write_dataframe(grid, OUT_DIR / "synthetic_grid")
    print(f"Wrote {len(grid):,} rows to {grid_path}")

    jobs = generate_jobs(num_jobs=25)
    jobs_path = write_dataframe(jobs, OUT_DIR / "synthetic_jobs")
    print(f"Wrote {len(jobs)} jobs to {jobs_path}")

    scenarios_path = OUT_DIR / "synthetic_scenarios.json"
    with open(scenarios_path, "w") as f:
        json.dump(SCENARIOS, f, indent=2)

    print(f"Wrote {len(SCENARIOS)} scenarios to {scenarios_path}")

    print("\n--- Per-zone summary ---")
    by_zone = (
        grid.groupby("zone")
        .agg(
            load_avg=("load_mw", "mean"),
            load_max=("load_mw", "max"),
            lmp_rt_avg=("lmp_rt_usd_per_mwh", "mean"),
            lmp_rt_p95=("lmp_rt_usd_per_mwh", lambda x: np.percentile(x, 95)),
            carbon_avg=("carbon_g_per_kwh", "mean"),
            carbon_min=("carbon_g_per_kwh", "min"),
            stress_max=("stress_score", "max"),
            peak_hours=("is_peak_hour", "sum"),
        )
        .round(1)
    )

    print(by_zone)

    print("\n--- Dynamic pricing demo job ---")
    spot_job = jobs[jobs["job_id"] == "j000_spot_training"].iloc[0]
    recommendation = recommend_cheapest_slot_for_job(grid, spot_job)

    print(json.dumps(recommendation, indent=2, default=str))

    if recommendation.get("status") == "scheduled":
        print(
            "\nAgent recommendation: "
            f"Schedule {spot_job['job_id']} in {recommendation['zone']} "
            f"from {recommendation['start_ts_utc']} to {recommendation['end_ts_utc']}. "
            f"Average price is ${recommendation['avg_price_usd_per_mwh']}/MWh, "
            f"below the job bid of ${recommendation['max_price_usd_per_mwh']}/MWh."
        )
    else:
        print(
            "\nAgent recommendation: "
            "No ideal below-bid, low-stress window was found. "
            "Use the least-bad option or raise the bid threshold."
        )


if __name__ == "__main__":
    main()