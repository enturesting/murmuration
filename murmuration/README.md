# Murmuration

A protocol layer between AI hyperscalers and the electric grid, with autonomous
agents on each side. Two flagship clients ride the same protocol: a **DC
throttler** that lets data centers shed compute load on demand, and a
**residential VPP** that aggregates home batteries / EVs / smart thermostats.

For the full design + thesis, read [`MURMURATION.md`](../MURMURATION.md) and
[`PITCH.md`](../PITCH.md).

---

## Table of contents

- [What you get when it's running](#what-you-get-when-its-running)
- [Quick start](#quick-start)
- [Optional API keys](#optional-api-keys)
- [Optional bulk datasets](#optional-bulk-datasets-hifld)
- [Demo flow](#demo-flow)
- [Project layout](#project-layout)
- [The 7 message types](#the-7-message-types)
- [Troubleshooting](#troubleshooting)

---

## What you get when it's running

- **Live data from 7 US ISOs** — CAISO via the [`gridstatus`](https://github.com/gridstatus/gridstatus)
  library; ERCOT / PJM / MISO / NYISO / ISO-NE / SPP via EIA-930 fuel-mix data.
  Carbon intensity is derived from the live generation mix in real time.
- **Two agents** —
  - `GridAgent` (ISO operator persona): publishes `GridStateUpdate`,
    forecasts load with a `GradientBoostingRegressor`, fires `DispatchRequest`
    when stress crosses threshold, fans out to VPPs, and engages the topology
    healer on contingencies.
  - `ComputeAgent` (hyperscaler fleet-ops persona): publishes a standing
    `FlexibilityEnvelope` per data center, accepts/declines/counter-offers
    dispatches, and drives a tiered `WorkloadRouter` (intra-region first,
    cross-region only when needed).
- **Solar profiles** — NREL PVWatts pre-fetched for each DC region so
  forecasts include a realistic solar curve.
- **Anomaly detector** — rolling z-score watchdog on every BA stream that
  auto-fires `ContingencyAlert` when a feature deviates sharply.
- **Topology graph** — `networkx`-backed substation graph with K-shortest
  paths and a `TopologyHealer` that responds to alerts with a
  `TopologyReconfigure` event.
- **Four views in the UI** at `http://127.0.0.1:8765`:
  - **3D Globe** — globe.gl over the US with pulsating BA / DC / VPP nodes,
    flashing dispatch arcs, and intra/cross-region migration arcs.
  - **Flat Map** — d3 + Albers USA projection, ISO service-territory polygons,
    HIFLD transmission lines (≥220 / 345 / 500 kV bands, counter-scaled
    strokes), HIFLD substations toggle, DMV-region zip-level reserve clusters
    that activate as a stressed BA needs help.
  - **Story** — presentation-grade walkthrough that paces an agentic narrative
    over a clean schematic (trigger → dispatch → ack → checkpoint → migrate →
    grid recovery), with stakeholder value cards across the bottom.
  - **Economics** — the **⚖** tab: a backtest prototype that generates a
    synthetic 14-day dataset, lets you browse hard-bid jobs, and returns a
    per-job cheapest-slot recommendation (no API keys).
- **10 prebuilt scenarios** wired to the bus — Texas heat wave, CAISO evening
  ramp, PJM-DOM congestion, CAISO surplus solar, polar vortex cascade, PJM
  line-trip contingency, carbon arbitrage, ERCOT solar eclipse, PJM Loudoun
  substation overload (AZ-level outage with intra-region failover), and VA
  grid self-healing (500 kV line trip rerouted by the topology healer).

---

## Quick start

Requires **Python 3.12+** (built on 3.12; a fresh install of the pinned requirements is also
verified on 3.14).

```bash
# 1. clone (or already cloned)
cd murmuration

# 2. create the venv and install deps (any Python 3.12+)
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 3. (optional) drop API keys into .env — see "Optional API keys" below
cp ../.env.example .env  # optional — everything runs without keys

# 4. run
./run.sh
```

Then open <http://127.0.0.1:8765> in a browser.

`run.sh` sources `.env` (if present) and execs uvicorn on `127.0.0.1:8765`.

---

## Optional API keys

The system runs end-to-end without any keys (CAISO live + EIA-930 fallback for
the rest), but two optional integrations make the demo richer. Drop the keys
into `murmuration/.env`:

```bash
# Free key — https://www.eia.gov/opendata/register.php
# Used for: ERCOT/PJM/MISO/NYISO/ISO-NE/SPP fuel-mix and carbon intensity.
EIA_API_KEY=your_eia_key_here

# Free key — https://developer.nrel.gov/signup/
# Used for: per-DC solar profile pre-fetch via PVWatts v8.
NREL_API_KEY=your_nrel_key_here

# Optional — only needed if you want Claude-grade narration on the agent feed.
# Without this, the system falls back to rule-based narration.
ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is gitignored.

---

## Optional bulk datasets (HIFLD)

Two HIFLD ([Homeland Infrastructure Foundation-Level Data](https://hifld-geoplatform.opendata.arcgis.com/))
shape files power the **Flat Map** transmission-lines and substations
overlays. They're large public-domain datasets (153 MB GeoJSON, ~21 MB CSV) so
they're **gitignored** — download them yourself if you want those overlays:

| File | Source | Drop it at |
|------|--------|------------|
| `Substations.csv` | <https://hifld-geoplatform.opendata.arcgis.com/datasets/substations> | `murmuration/murmuration/data/Substations.csv` |
| `Electric_Power_Transmission_Lines.geojson` | <https://hifld-geoplatform.opendata.arcgis.com/datasets/electric-power-transmission-lines> | `murmuration/murmuration/data/US_Electric_Power_Transmission_Lines_-6976209181916424225.geojson` (or any `*.geojson` in that folder; the loader globs) |

The system gracefully no-ops these overlays if the files aren't present —
everything else still works.

---

## Demo flow

### Hello-world (3 minutes)

1. Open <http://127.0.0.1:8765>. Watch the bus feed populate with
   `flexibility_envelope` and `grid_state_update` messages — that's the
   protocol working live.
2. CAISO's card fills with real load + carbon within a few seconds.
3. Click **"Texas heat wave"** in the right rail. ERCOT LMP overrides to
   $410/MWh. Within 1–2 ticks the grid agent issues a `DispatchRequest`. The
   compute agent acks. Jobs at `DC-TX-1` pause. Metrics tick.

### The presentation flow

1. Switch to the **Story** tab.
2. Pick **"PJM-DOM congestion"** from the picker.
3. Watch the schematic show PJM critical at **8% headroom**, three VA AZs
   throttle, and a workload-migration arc fire toward CAISO.
4. The agent narrative paces itself: grid critical → dispatch → ack →
   pause shiftable jobs → checkpoint → router scoring → migrating →
   load reduction → grid trending healthy → scenario complete.

### The contingency flow

Pick **"PJM line trip · contingency"** — `ContingencyAlert` is published, the
compute agent's pre-authorized fast path drops 30% of GPU load in <2 ms, and
the topology healer issues a `TopologyReconfigure` rerouting around the
tripped edge.

### The AZ failover flow

Pick **"PJM Loudoun substation overload"** — `DC-VA-1a` (Loudoun) is marked
unavailable. The router migrates jobs **intra-region** to `DC-VA-1b` (Sterling)
and `DC-VA-1c` (Manassas) — sub-millisecond, no SLA hit. No cross-region
churn.

---

## Project layout

```
murmuration/
├── murmuration/
│   ├── protocol/        # MurmurationBus + 12 Pydantic message types
│   ├── data/            # ISO clients (CAISO/gridstatus, EIA-930), HIFLD loaders
│   ├── assets/          # FlexibleAsset ABC, DataCenter, HomeAggregator (VPP)
│   ├── orchestrator/    # GridAgent, ComputeAgent, WorkloadRouter, Narrator
│   ├── forecast/        # GBM load forecaster + NREL PVWatts client
│   ├── anomaly/         # rolling z-score detector → ContingencyAlert
│   ├── topology/        # substation graph + healer
│   ├── simulator/       # 9 ScenarioManager triggers
│   ├── metrics/         # cumulative tracker (MW shed, $ saved, tCO2 avoided)
│   └── api/             # FastAPI server, WebSocket, REST endpoints
├── ui/
│   └── index.html       # single-page UI: Globe + Flat Map + Story tabs
├── requirements.txt
└── run.sh
```

---

## The 7 message types

> The seven core negotiation types are tabled below, plus two orchestrator-emitted types. The
> full protocol exports twelve message classes (see `murmuration/protocol/__init__.py`) — the
> remaining three (`FlexibilityBand`, `CounterOffer`, `TelemetryFrame`) support envelope
> structure, negotiation, and telemetry.

The bus carries plain Pydantic models. Three are agent → bus, three are
bus → agent, one is bidirectional:

| Message | From | Purpose |
|---|---|---|
| `GridStateUpdate` | GridAgent | Live BA snapshot — load, headroom, LMP, carbon |
| `GridForecast` | GridAgent | GBM-forecasted load + LMP + carbon, horizon ~30 min |
| `DispatchRequest` | GridAgent | Targeted shed/lean-in ask + price + duration |
| `ContingencyAlert` | GridAgent / Anomaly | Sub-second event needing fast-path response |
| `FlexibilityEnvelope` | ComputeAgent | Standing offer: how much/how fast a facility can move |
| `LoadForecast` | ComputeAgent | DC-side load forecast back to the grid for planning |
| `DispatchAck` | ComputeAgent | Accept / decline / counter-offer + actions taken |

Two more emitted by the orchestrator for downstream consumers:
`WorkloadMigration` (router decisions, intra- vs cross-region tier) and
`TopologyReconfigure` (healer rerouting around a failed edge).

---

## Troubleshooting

**Server starts but the UI shows no data for ~30s.**
First-time startup pulls EIA-930 fuel mix for 6 ISOs sequentially (each
~3–5s). Subsequent runs hit the 15-min cache. CAISO live data also takes a
few seconds for the first `gridstatus` fetch.

**EIA fetch failed for X: read timeout.**
EIA's API occasionally rate-limits. The system falls back to synthetic for
that BA and keeps running. Restart later to re-attempt.

**Map tab shows the basemap but no transmission lines / substations.**
The HIFLD bulk files aren't in the repo (see [Optional bulk datasets](#optional-bulk-datasets-hifld)).
The map still renders the ISO polygons and DC markers without them.

**Story tab "stress relieved" appears immediately, agent walkthrough never fires.**
That's the symptom of a stale dispatch cooldown. The `ScenarioManager.trigger()`
clears `grid_agent._last_dispatch_at[ba]` for each scenario BA, but if you've
modified those files locally, restart the server (`run.sh`) to pick up the
fix.

**`venv missing — run setup first` from `run.sh`.**
You need to create the venv first — see [Quick start](#quick-start) step 2.

**Browser still shows old UI after editing `ui/index.html`.**
The server sets `Cache-Control: no-store`, but extensions / service workers
can still cache. Hard-reload (⌘⇧R / Ctrl+F5).

---

## Backtest API

The **⚖ Economics** tab is driven by four REST endpoints that wrap the repo's
[`agentic_workflow/`](../agentic_workflow/) hard-bid prototype. They need no API
keys — everything runs on a locally generated synthetic dataset:

| Endpoint | Purpose |
|---|---|
| `POST /api/backtest/generate` | Build the synthetic 14-day, 4-zone grid + job dataset for this environment. |
| `GET /api/backtest/summary` | Dataset overview — zones, horizon, job counts, price stats. |
| `GET /api/backtest/jobs` | List the hard-bid jobs (each with its max willingness-to-pay). |
| `GET /api/backtest/recommend/{job_id}` | Cheapest feasible slot for one job (rejection is a valid answer). |

The nictopia real-incident replay is served alongside these at `/replay/` as a
committed static build (no Node at runtime).

---

## Triggering scenarios from the command line

The scenario endpoint takes the URL-encoded *display name*, not a slug:

```bash
curl -X POST 'http://127.0.0.1:8765/api/scenario/Texas%20heat%20wave'   # ✓
curl -X POST 'http://127.0.0.1:8765/api/scenario/texas_heat_wave'       # ✗ 404
```

---

## License

Hackathon submission. No license has been chosen yet — treat it as
all-rights-reserved unless and until a `LICENSE` file is added.
