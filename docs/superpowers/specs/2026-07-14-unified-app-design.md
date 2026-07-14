# Unified App — Design (feature/unified-app, experimental)

**Date:** 2026-07-14 · **Status:** user pre-approved scope ("take a stab at mixing the parts
together"); branch is NOT merged — Nic tests, then decides.

## Goal

One server, one URL. `cd murmuration && ./run.sh` serves all three hackathon apps:

| Route | What | Source |
|---|---|---|
| `/` | Flagship live-agent UI (unchanged) + topbar links to the other two | `murmuration/ui/index.html` |
| `/replay/` | nictopia real-incident replay (static Vite build, `--base=/replay/`) | built from `nictopia/`, output committed at `murmuration/ui/replay/` |
| `/api/backtest/*` | agentic_workflow economics as REST (no LLM, no keys) | imports `agentic_workflow/{generate_grid,gridcache}.py` |
| 4th UI tab "Economics" | generate dataset → summary → jobs table → per-job cheapest-slot recommendation | new pane in `ui/index.html` following existing tab patterns |

## Backtest API (all no-key; LLM runner stays CLI-only)

- `POST /api/backtest/generate` — subprocess `sys.executable generate_grid.py` (cwd=agentic_workflow); returns file list. ~1s.
- `GET /api/backtest/summary` — zones, hour range, row count, scenario list, price ranges (via gridcache).
- `GET /api/backtest/jobs` — pending jobs with bid economics fields.
- `GET /api/backtest/recommend/{job_id}` — `generate_grid.recommend_cheapest_slot_for_job` result.

Implementation: new module `murmuration/murmuration/api/backtest.py` (APIRouter); lazily
`sys.path`-inserts `<repo_root>/agentic_workflow`; degrades to clear 409/404 JSON when the dataset
hasn't been generated yet. Flagship venv already has pandas/numpy; parquet-vs-csv fallback is
handled by the scripts themselves.

## nictopia integration

- `npm run build -- --base=/replay/` (Node 26); copy `dist/` → `murmuration/ui/replay/` and
  commit it (so the unified app needs no Node at runtime). Root `.gitignore` gets a
  `!murmuration/ui/replay` carve-out (it globs `dist/` only, but replay/ is a plain dir — verify).
- Small header back-link "← Live agents" added in nictopia `App.tsx` (rebuilt into the bundle).
- Flagship topbar gets "REPLAY" link → `/replay/`.

## Verification bar (before pushing the branch)

Fresh clone → venv → `./run.sh`: `/` serves; `/replay/` serves the built app (assets load under
`/replay/assets/`); `POST /api/backtest/generate` then `summary`/`jobs`/`recommend` return sane
JSON; Economics tab renders and drives those endpoints (headless screenshot); existing behavior
regression-checked (scenario trigger still dispatches). Then an adversarial verification workflow
(parallel checkers) before handoff.

## Out of scope

Deep unification (porting nictopia components/data into the flagship UI, hard-bid economics into
the live agents) — assessed separately as "Tier C", 3–4 days. LLM backtest runner endpoint (costs
real API dollars). Merging this branch (Nic's call after testing).
