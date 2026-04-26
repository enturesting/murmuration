# murmuration
SCSP AI Hackathon DC


Comments:
Overutilized and underutilized scenarios in local data centers in one region 
Then if not then it looks at a wider span 

Simplify agentic comments 

Make it simple on API press 

# Grid-Aware Compute Agents

Two AI agents — one representing a grid operator, one representing a fleet of data centers — that negotiate over where and when to run GPU workloads. The compute side bids on power; the grid side surfaces conditions. Together they route compute toward whichever region is cleanest, cheapest, and least stressed, without violating SLAs.

This is a hackathon project. The agents are real (Claude via the Anthropic API). The grid is synthetic but calibrated against real PJM and ERCOT operating ranges, and the schema mirrors what the agents would consume in production from public data feeds.

---

## The problem

Data centers are on track to be roughly 10% of US electricity demand within a few years. That load is concentrated geographically — Northern Virginia alone hosts the densest cluster of data centers on Earth. Two coupled headaches result:

- Grid operators (ISOs) struggle to maintain reliability as data center load grows faster than transmission and generation can be added.
- Data center operators face rising electricity prices, growing carbon scrutiny, and limited tools for shifting load.

Today these two sides barely coordinate. Grid operators treat data centers as inflexible load. Data centers treat the grid as a passive utility. We propose they should talk — and that the conversation can be mediated by AI agents acting on behalf of each side.

---

## What this project demonstrates

A working two-agent system in which:

- A **grid-side agent** ("ISO operator") publishes structured briefings about grid conditions across multiple zones — prices, carbon intensity, stress level, peak status, load vs. forecast.
- A **compute-side agent** ("DC fleet ops") reads those briefings, evaluates candidate placements, and decides per job whether to schedule, reject, or escalate — playing by **hard-bid rules** (each job has a willingness-to-pay; the agent never schedules above bid unless the job's SLA forces it).
- Both agents reason in natural language but ground every quantitative claim in tool calls. No hallucinated MWs.
- The system is benchmarked against two non-LLM baselines (naive and heuristic) on the same simulated trace. The scorecard reports cost, carbon, reject rate, and zone placement distribution — apples-to-apples comparison.

---

## Datasets we simulate

The project replays a 14-day window of synthetic grid data spanning four zones. The data is generated to be statistically plausible and to mirror the schema of real public feeds, so the same agent code could later be pointed at live PJM Data Miner 2 + Electricity Maps without modification.

### Zones modeled

| Code | Region | Generation profile | Why it's in the demo |
|---|---|---|---|
| **DOM** | Dominion Energy / Northern Virginia | Gas-heavy with limited wind | Highest data-center load growth in the US; the "stressed home grid" |
| **COMED** | Commonwealth Edison / Chicago | Nuclear baseload-dominated | The "clean haven" — lowest carbon, cheapest for steady load |
| **AEP** | American Electric Power / Ohio-WV-KY | Coal-heavy with growing wind | "Dirty but cheap when wind blows" — the contrarian zone |
| **ERCOT** | Texas | Largest US wind + solar capacity | Massive cross-zone arbitrage potential during midday solar and overnight wind |

DOM, COMED, and AEP are all PJM Interconnection zones. ERCOT is a separate ISO covering most of Texas. In production, cross-ISO compute routing has real complexity (separate markets, separate settlement); we abstract over that for the demo.

### Signals the agent sees (per zone, per hour)

These are the decision-relevant signals exposed to the agents through `gridcache.py`. They map directly to columns in real public data feeds:

| Signal | Maps to (real-world feed) | What it tells the agent |
|---|---|---|
| `lmp_rt_usd_per_mwh` | PJM Data Miner 2: *Real-Time Hourly LMPs* | What it costs to run compute right now |
| `lmp_da_usd_per_mwh` | PJM Data Miner 2: *Day-Ahead Hourly LMPs* | Yesterday's forecast price for this hour — the "expected" cost |
| `load_mw` | PJM Data Miner 2: *Instantaneous Load* (resampled hourly) | How much electricity demand the zone is serving |
| `load_forecast_mw` | PJM Data Miner 2: *Seven-Day Load Forecast* | What was forecast for this hour 24h ago |
| `carbon_g_per_kwh` | Electricity Maps API + EIA-930 fuel mix | Emissions intensity of grid power right now |
| `stress_score` (1-5) | Derived: utilization band + RT/DA spread | Single-number summary of "how tight is the grid" |
| `is_peak_hour` | Derived: top 10% of zone's daily load | Capacity-charge–relevant flag |
| `utilization` | Derived: load / total capacity | Reserve margin proxy |

The agent does **not** see per-fuel generation columns (`wind_mw`, `solar_mw`, `coal_mw`, etc.). Those exist in the parquet for the data generator and analytics, but they're plumbing — the carbon and price signals already encode the relevant information.

### Forecast bust modeling

Day-ahead LMPs (`lmp_da`) and the published load forecast are computed from a *baseline* weather curve that excludes scenario perturbations. Real-time LMPs and actual load include those perturbations. So during a simulated heat wave, actual load runs ~15-20% above forecast, RT prices spike to 5× day-ahead, and the agent can detect the disagreement as a "forecast bust" — exactly the signal a real ops team would react to.

### Scripted scenarios

Five dramatic events are baked into specific hours of the synthetic window. Each stresses different signals so the agent has to demonstrate different behaviors:

| # | Scenario | Hours | What the agent should do |
|---|---|---|---|
| 1 | DOM heat dome (forecast bust) | 60–96 | Move deferrable jobs out of DOM; let must-run inference eat the cost |
| 2 | ERCOT solar-noon arbitrage | 132–138 | Route afternoon batch jobs DOM→ERCOT |
| 3 | AEP+ERCOT overnight wind ramp | 150–168 | Pull deferrable jobs *forward* into the cheap window |
| 4 | COMED nuclear unit forced outage | 210–218 | Stop preferring COMED; route flexible jobs to ERCOT/AEP |
| 5 | Coincident DOM peak + ERCOT wind+solar | 250–258 | Migrate everything deferrable west — the money shot |

Plus one bidding scenario:

| # | Scenario | Hours | What it tests |
|---|---|---|---|
| 6 | Dynamic spot-pricing bid (showcase job) | 150–174 | A specific 80 MW × 6h training job with a $50/MWh hard bid is submitted right at the wind ramp |

Each scenario is annotated in `data/synthetic_scenarios.json` with the signals it targets and the expected agent behavior.

### Why synthetic instead of real PJM data

Three reasons, in order of importance:

1. **The demo runs identically every time.** Live API outages, rate limits, and data freshness issues won't kill the presentation.
2. **We can guarantee dramatic moments happen on cue.** Real PJM data has price spikes, but they're scattered. Synthetic data places them where the demo needs them.
3. **Schema parity.** The synthetic data uses the same column names, units, and shapes as PJM Data Miner 2 + Electricity Maps. Swapping in real CSVs is a one-line change in the data layer.

The agents and scorecard logic are data-source-agnostic. A judge asking "does this work on real data?" gets a clean answer: the same code reads a different parquet.

### Job mix simulated

`data/synthetic_jobs.parquet` contains ~26 jobs across the 14-day window, with realistic variety:

| Kind | SLA tier | Bid type | Bid range | Typical duration |
|---|---|---|---|---|
| Training | Deferrable | `spot_flexible` | $50/MWh | 6-12h |
| Batch inference | Deferrable | `deadline_flexible` | $80/MWh | 3h |
| Embedding backfill | Deferrable | `spot_flexible` | $60/MWh | 4h |
| Eval runs | Deferrable | `deadline_flexible` | $70/MWh | 6h |
| Data pipelines | Opportunistic | `opportunistic` | $35/MWh | 8h |
| Inference (real-time) | Latency-critical | `must_run` | $300/MWh | 1-2h |

`bid_type == "must_run"` jobs ignore the bid — they always schedule, even at peak prices. Everything else is hard-bid: rejected if no slot fits.

The job set includes one **showcase** job — `j000_spot_training`, an 80 MW × 6h training run submitted right as the wind ramp begins, with a $50/MWh bid. It exists to give the agent a single dramatic decision the demo can spotlight.

---

## Architecture

```
                       runner.py / baselines.py
                                  │
                                  ▼
                          compute_agent.py
                          ┌──────────────────┐
                          │  SYSTEM PROMPT   │
                          │  TOOLS:          │
                          │   list_jobs      │
                          │   get_briefing ──┼──┐
                          │   evaluate_slot  │  │  the bus
                          │   submit         │  │
                          └──────────────────┘  │
                                                ▼
                                       grid_agent.py
                                       ┌──────────────────┐
                                       │  SYSTEM PROMPT   │
                                       │  TOOLS:          │
                                       │   snapshot       │
                                       │   conditions     │
                                       │   recent_history │
                                       │   forecast       │
                                       │   submit         │
                                       └──────────────────┘
                                                │
                                                ▼
                                          gridcache.py
                                                │
                                                ▼
                                  data/synthetic_grid.parquet
                                  data/synthetic_jobs.parquet
                                  data/synthetic_scenarios.json
```

### The bus

When the compute agent calls its `get_grid_briefing` tool, that tool internally calls `grid_agent.produce_briefing()` — which spins up a separate Claude conversation with its own system prompt and tools. The grid agent reads data, reasons, and returns a structured briefing. From the compute agent's perspective it's just a tool call returning a dict. From the architecture's perspective, two AI agents have just exchanged a structured message.

This nested-agent pattern is what makes the demo legible: judges can read the transcript and see one Claude consulting another in plain English, with every number traceable to a tool call.

### File map

```
project/
├── data/
│   ├── synthetic_grid.parquet       # 14d × 4 zones × hourly = 1,344 rows
│   ├── synthetic_jobs.parquet       # ~26 simulated DC jobs
│   └── synthetic_scenarios.json     # annotated dramatic events
├── synthetic_grid.py                # one-shot data generator
├── gridcache.py                     # read-only data layer (no LLM)
├── grid_agent.py                    # grid-side Claude agent
├── compute_agent.py                 # compute-side Claude agent
├── runner.py                        # orchestrates the agent across ticks
└── out/
    ├── run_<timestamp>/             # agent run artifacts
    │   ├── decisions.json
    │   ├── events.json
    │   └── scorecard.json
    └── baseline_<policy>_<ts>/      # baseline run artifacts (same shape)
```

### Why two agents instead of one

Three reasons:

1. **It mirrors the real-world trust boundary.** ISOs and hyperscalers don't share their internal state. Modeling that explicitly makes the architecture deployable, not just demo-able.
2. **Smaller scope per agent yields better reasoning.** Each Claude has a focused prompt and a small toolset. The grid agent describes; the compute agent decides. Mixing those roles in a single agent leads to muddier outputs.
3. **The negotiation transcript is the demo.** Watching two agents exchange messages is more compelling than a single agent's monologue.

### Hard-bid decision rules

Every pending job has a `max_price_usd_per_mwh` and a `bid_type`. The compute agent applies these rules — same rules used by the heuristic baseline, so comparisons are fair:

- If `bid_type == "must_run"` (latency-critical inference): always schedule. Status `escalated_must_run`. The cost is logged but the SLA dominates.
- Else if a feasible slot exists with avg LMP ≤ bid: schedule the cheapest such slot, tiebreak by lower carbon. Status `scheduled`.
- Else: reject. Status `rejected_no_feasible_slot`, with a reason citing the cheapest available price and the bid it exceeded.

The agent is explicitly told in its system prompt that *rejection is the correct outcome* under hard-bid rules. LLMs default to "trying to be helpful" by satisfying users; the prompt counters that tendency.

---

## Running it

### Setup (once)

```bash
# Python 3.10+
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic python-dotenv pandas numpy pyarrow matplotlib
```

Create `.env` in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
```

### Generate the synthetic data (once)

```bash
python synthetic_grid.py
```

Writes `data/synthetic_grid.parquet`, `data/synthetic_jobs.parquet`, `data/synthetic_scenarios.json`. ~1 second.

### Sanity-check the data layer (optional)

```bash
python gridcache.py
```

Smoke-tests the read functions and prints a per-zone snapshot at hour 72 (mid heat-dome).

### Run the agent across the simulation window

```bash
python runner.py
```

Default window: `2024-07-17T00:00Z → 2024-07-22T00:00Z` (5 days), 6-hour ticks, ~20 ticks total. Each tick calls the compute agent, which calls the grid agent, which reads `gridcache`.

Cost: roughly **$0.10–0.20 per tick × 20 ticks ≈ $2–4 per full run**. Dominated by the nested grid-agent calls.

Output: `out/run_<timestamp>/` containing `decisions.json`, `events.json`, `scorecard.json`.


### Single-agent smoke tests

```bash
python grid_agent.py     # one briefing, prints structured response
python compute_agent.py  # one scheduling pass at hour 72
```

Useful for iterating on prompts without paying for full multi-tick runs.

---

## What "winning" looks like

A successful agent run shows three things in the scorecard:

1. **Lower total cost than heuristic** for the same number of jobs scheduled. The heuristic concentrates jobs in COMED (the obvious cheap answer); a smart agent diversifies into ERCOT during solar peaks and AEP during wind ramps for further savings.
2. **Lower total carbon** than heuristic, particularly during the wind/solar windows where the agent should pull deferrable jobs forward.
3. **Cleaner zone distribution** — not 6 of 8 jobs in COMED. The transcript should show reasoning like *"DOM is stressed → COMED, but COMED is at stress 3 with the nuclear outage → try ERCOT instead."*

If the agent only matches the heuristic on raw numbers, the *secondary* pitch is explainability: the negotiation transcript is something a real utility ops team or hyperscaler ops lead can read and audit, which classical optimization solvers can't offer.

---

## What's deliberately out of scope

- **Batteries, EVs, behind-the-meter DERs.** Real and important but each is a project unto itself.
- **Cooling capacity and PUE modeling.** Hand-waved as constants.
- **Inter-region data transfer cost and latency.** Latency-critical jobs are pinned; everything else is treated as freely movable.
- **Transmission congestion as a separate signal.** Folded into LMPs (which is roughly how real grids work) rather than modeled explicitly.
- **Day-ahead bidding behavior on the compute side.** The agent only operates in real-time decisions; it doesn't participate in the day-ahead market.
- **Multi-ISO settlement and currency.** ERCOT is included as if it were just another zone.

Each of these is a legitimate v2 capability. None block the v1 narrative.

---

## A note on real vs. synthetic data

The project is built so that swapping to real public data feeds is straightforward:

- PJM Data Miner 2 (free, requires API key) provides Real-Time + Day-Ahead LMPs, Instantaneous Load, and Seven-Day Load Forecast for DOM, COMED, AEP. Same column semantics as our synthetic file.
- Electricity Maps (free CSV download for historical, paid API for live) provides hourly carbon intensity per region.
- ERCOT data is available through `gridstatus` Python library for LMPs and load.

To switch, replace `data/synthetic_grid.parquet` with a real-data parquet of the same shape. The agents, baselines, and scorecard need no changes. This was a deliberate design choice: data layer agnostic, agent layer focused.

---

## Status of v1 (what's built)

- ✅ Synthetic data generator with 4 zones and 6 scenarios (`synthetic_grid.py`)
- ✅ Read-only data layer with time-of-decision discipline (`gridcache.py`)
- ✅ Grid-side Claude agent with structured briefing output (`grid_agent.py`)
- ✅ Compute-side Claude agent with hard-bid decision rules (`compute_agent.py`)
- ✅ Multi-tick orchestrator with persistent artifacts (`runner.py`)
- ✅ Naive and heuristic baselines for comparison (`baselines.py`)