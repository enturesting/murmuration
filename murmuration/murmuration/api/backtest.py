"""Backtest API — exposes the agentic_workflow prototype's economics over REST.

The original hackathon prototype (repo-root ``agentic_workflow/``) replays a
synthetic 14-day, 4-zone grid dataset and schedules GPU jobs under hard-bid
economics. This router surfaces its no-LLM parts (dataset generation, the
read-only data layer, and the cheapest-slot baseline scheduler) so the unified
server can demo them without API keys. The full Claude runner stays CLI-only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# repo root is three levels above this package dir: <root>/murmuration/murmuration/api/
AW_DIR = Path(__file__).resolve().parents[3] / "agentic_workflow"
DATA_DIR = AW_DIR / "data"


def _modules():
    """Lazily import the prototype's modules with DATA_DIR pointed at its data dir.

    gridcache resolves ``data/`` relative to the process cwd, so repoint it —
    the server runs with cwd=murmuration/.
    """
    if str(AW_DIR) not in sys.path:
        sys.path.insert(0, str(AW_DIR))
    import generate_grid  # noqa: F401  (imported for recommend_cheapest_slot_for_job)
    import gridcache
    gridcache.DATA_DIR = DATA_DIR
    return generate_grid, gridcache


def _no_dataset() -> JSONResponse:
    return JSONResponse(
        {"error": "no dataset generated yet", "hint": "POST /api/backtest/generate first"},
        status_code=409,
    )


@router.post("/generate")
def generate():
    """Run the prototype's one-shot data generator (~1s, no API keys)."""
    proc = subprocess.run(
        [sys.executable, str(AW_DIR / "generate_grid.py")],
        cwd=AW_DIR, capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        return JSONResponse(
            {"error": "generator failed", "stderr": proc.stderr[-2000:]},
            status_code=500,
        )
    _, gridcache = _modules()
    gridcache.load_grid.cache_clear()
    gridcache.load_jobs.cache_clear()
    files = sorted(p.name for p in DATA_DIR.glob("synthetic_*"))
    return {"generated": files}


@router.get("/summary")
def summary():
    """Dataset overview: zones, window, size, price/carbon ranges."""
    _, gridcache = _modules()
    try:
        g = gridcache.load_grid()
    except FileNotFoundError:
        return _no_dataset()
    t0, t1 = gridcache.time_range()
    return {
        "zones": gridcache.available_zones(),
        "hours": int(len(g) / max(1, g["zone"].nunique())),
        "rows": int(len(g)),
        "window": {"from": t0.isoformat(), "to": t1.isoformat()},
        "lmp_rt_usd_per_mwh": {
            "min": round(float(g["lmp_rt_usd_per_mwh"].min()), 2),
            "avg": round(float(g["lmp_rt_usd_per_mwh"].mean()), 2),
            "max": round(float(g["lmp_rt_usd_per_mwh"].max()), 2),
        },
        "carbon_g_per_kwh": {
            "min": round(float(g["carbon_g_per_kwh"].min()), 1),
            "avg": round(float(g["carbon_g_per_kwh"].mean()), 1),
            "max": round(float(g["carbon_g_per_kwh"].max()), 1),
        },
    }


@router.get("/jobs")
def jobs():
    """Pending jobs with their bid economics."""
    _, gridcache = _modules()
    try:
        j = gridcache.load_jobs()
    except FileNotFoundError:
        return _no_dataset()
    cols = ["job_id", "kind", "sla", "duration_hours", "power_mw",
            "submitted_ts_utc", "deadline_ts_utc", "region_flexible",
            "pinned_zone", "max_price_usd_per_mwh", "bid_type"]
    out = []
    for _, row in j.iterrows():
        rec = {}
        for c in cols:
            v = row[c]
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            elif hasattr(v, "item"):
                v = v.item()
            elif v is not None and not isinstance(v, (str, int, float, bool)):
                v = str(v)
            rec[c] = v
        out.append(rec)
    return {"jobs": out}


@router.get("/recommend/{job_id}")
def recommend(job_id: str, max_stress_score: int = 3):
    """Cheapest feasible slot for one job (the prototype's non-LLM baseline)."""
    generate_grid, gridcache = _modules()
    try:
        g = gridcache.load_grid()
        j = gridcache.load_jobs()
    except FileNotFoundError:
        return _no_dataset()
    rows = j[j["job_id"] == job_id]
    if rows.empty:
        return JSONResponse({"error": f"unknown job_id {job_id!r}"}, status_code=404)
    rec = generate_grid.recommend_cheapest_slot_for_job(
        g, rows.iloc[0], max_stress_score=max_stress_score,
    )
    # timestamps inside the dict may be pandas Timestamps — make them JSON-safe
    for k, v in list(rec.items()):
        if hasattr(v, "isoformat"):
            rec[k] = v.isoformat()
    return rec
