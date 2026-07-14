> **Where this fits:** `nictopia/` is the standalone React + Vite visual demo built in parallel with
> the flagship Python system during the hackathon. The team compared both implementations in
> [`docs/reference/shashank_branch_review.md`](../docs/reference/shashank_branch_review.md) and chose
> the Python package ([`murmuration/`](../murmuration/)) as the primary stage demo. This app remains
> the fastest way to see the idea: `npm install && npm run dev` — no backend, no API keys, all data
> served from committed caches of real archived grid incidents.

# Murmuration

**SCSP AI Hackathon · Track:** Electric Grid Optimization

> A bilateral protocol that lets the grid and the AI compute fleet talk to each other — and a 3D demo that plays it through three real historical stress events.

## Team

- _add team members here before submission_

## What we built

Murmuration is a hackathon prototype of a **standing-envelope coordination protocol** between three constituencies that today have no common wire: grid operators (ISOs/utilities), large compute fleets (hyperscaler data centers), and distributed energy resources (home batteries, EVs, smart thermostats aggregated as VPPs).

The thesis is in `docs/reference/electric_travel.md`: bulk power can't cross the three asynchronous US interconnections (only ~2 GW of HVDC ties exist between them), but **compute jobs can migrate over fiber**. So when ERCOT melts in a heat wave, you can't ship Texas electrons to California, but you *can* ship the training jobs out of DFW data centers to CAISO and free up the load. Murmuration is the protocol that makes that decision negotiable, telemetered, and settled.

The app is an interactive 3D globe (react-globe.gl) showing three demo scenarios anchored to real archived events:

- **ERCOT heat / Winter Storm Uri (Feb 2021)** — 850 MW data-center migration + 320 MW VPP swarm
- **CAISO PSPS (Oct 2019)** — Bay Area DC routes 700 MW out to ERCOT+PJM + 280 MW local CA VPP
- **CAISO duck curve (Apr 15, 2024)** — DC absorbs 900 MW at negative LMP midday, releases 900 MW at sunset, VPP shaves the ramp

Each scenario plays a 4-phase beat — **NEED → SOURCE → ROUTE → PROTECT** — with live-demo gating pauses, an animated "Murmuration Bus" message ticker showing the typed protocol on the wire (`GridStateUpdate`, `DispatchRequest`, `DispatchAck`, `TelemetryFrame`, `FlexibilityEnvelope`), and a settlement panel computing dollars and tons of CO₂ avoided from real EIA-930 fuel-mix data.

The honest framing of what's playback and what's modeled is documented in `docs/murmuration_diagram.md` (nine Mermaid diagrams covering the problem space, the protocol, the three scenarios, the counterfactual, and the offline-safe data architecture).

## Datasets and APIs used

All data is fetched once offline and cached as JSON in `public/cache/` so the demo runs with no network. Source-of-truth pulls live at runtime are explicitly out of scope (see `docs/reference/electric_travel.md` and `docs/murmuration_diagram.md` §9 for the offline-safe rationale).

- **EIA Open Data API** (api.eia.gov) — hourly fuel mix per balancing authority (`scripts/fetch_eia.py`, requires `EIA_KEY`)
- **gridstatus.io archive** — 15-minute LMP series for CAISO SP15 during the duck-curve and heatdome events (`scripts/fetch_historical.py`)
- **EPA eGRID + IPCC carbon factors** — embedded in `scripts/fetch_historical.py` for CO₂ avoided math
- **CAISO OASIS / ERCOT / PJM Data Miner 2** — referenced for the historical anchor metadata; numbers cross-checked against published incident reports (FERC Uri report, PG&E PSPS press releases, CAISO duck curve LMP archive)

Cached snapshots live in `public/cache/`:
- `eia_snapshot.json` — point-in-time EIA-930 fuel-mix snapshot
- `historical/ercot_uri_2021_02_16.json`
- `historical/caiso_psps_2019_10_09.json`
- `historical/caiso_duck_2024_04_15.json`
- `historical/caiso_heatdome_2023_08_15.json`
- `historical/pjm_helene_2024_09_27.json`

## How to run it

Requires Node.js 22.12+ and npm 11+ (Vite 8's floor; verified with Node 26 / npm 11 — older npm
versions can silently skip Vite's native rolldown binding).

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

For a production build:

```bash
npm run build
npm run preview
```

A static build of this app is committed at `murmuration/ui/replay/` and served by the flagship
server at `/replay/` — regenerate it with `../scripts/build_replay.sh` after source changes.

### Demo flow

1. Pick one of the three scenarios from the top bar (ERCOT heat wave / CAISO wildfire / Duck curve).
2. Click **Run Scenario**.
3. Watch the four-phase beat play across the globe — DC nodes change color as they take stress, animated arcs show compute migration over fiber, purple rings show local VPP injection, green threads connect to critical sites (hospitals, EMS, water).
4. The Murmuration Bus side-panel ticks through the typed protocol messages as they go on the wire.
5. Settlement metrics (USD, tCO₂ avoided, headroom) update at the end of each phase.
6. Some phases are gated — click **Continue →** to advance after the audience has had a beat to react.
7. **Reset** before re-running.

The detailed pitch playbook is in `docs/demo/demo_flow.md`. Open candidate work for the team is tracked in `docs/demo/todo_list.md`. Defenses for hard judge questions are in `docs/demo/judge_qa_prep.md`.

## Project structure

```text
src/
├── App.tsx                       # Scenario coordination + state
├── components/
│   ├── GlobeView.tsx             # react-globe.gl: nodes, arcs, rings, labels
│   ├── BusTicker.tsx             # Typed protocol message stream
│   ├── EventLog.tsx              # Phase-by-phase event log
│   └── MetricsPanel.tsx          # Settlement USD + CO₂ panel
├── lib/
│   ├── simulation.ts             # The three scenarios + phase playback
│   ├── eia.ts                    # EIA snapshot loader
│   └── geo.ts                    # BA centroids + critical-site coords
└── types.ts                      # Scenario / Phase / Bus message types

docs/
├── murmuration_diagram.md        # 9-diagram problem-and-solution spine
├── reference/
│   └── electric_travel.md        # Why compute migrates but power doesn't
└── demo/
    ├── demo_flow.md              # 10-min pitch playbook
    ├── demo_slides.html          # reveal.js starter deck
    ├── todo_list.md              # Open candidate work
    └── judge_qa_prep.md          # Hard-question defenses

scripts/
├── fetch_eia.py                  # One-shot EIA-930 fetch
└── fetch_historical.py           # One-shot historical anchor fetch

public/cache/                     # Committed offline-safe data snapshots
```

## What's modeled vs. what's playback

In the spirit of the rubric's Problem-Solution Fit criterion, this is the honest accounting:

- The **historical anchors** (Uri, PSPS, duck curve) are real and verifiable against public incident reports and gridstatus/EIA archives.
- The **fuel-mix and LMP data** in `public/cache/` are real EIA-930 and gridstatus pulls.
- The **settlement and CO₂ math** uses real EPA eGRID / IPCC carbon factors over real MW × duration × price — not made-up numbers.
- The **MW dispatch values** in each scenario (850 MW migration, 320 MW VPP, etc.) are conservative estimates of what real DFW / Bay Area DC campuses and existing VPP aggregators could plausibly commit, anchored to LBNL data center load reports.
- The **bilateral protocol playback is deterministic**, not LLM-driven in the critical path — by design (the thesis in `demo_flow.md` Beat 6 is that the LLM writes standing envelopes offline and stays out of the dispatch loop, which is exactly what the demo shows). Open candidates to add a visible LLM lever for the live demo are listed in `docs/demo/todo_list.md`.
- The **VPP swarm response** is modeled as instantly perfect (no opt-outs, no constraint violations). Real VPP dispatch has dropouts; we don't model those.

## License and submission

Per SCSP rules, this repo is public and the team retains IP. SCSP receives a non-exclusive license to publish the work product.
