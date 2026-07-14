# Murmuration `feature/nictopia` — Integration Guide

A one-page reference for **what's cherry-pickable** out of this branch. If your version of the demo ends up as the team's primary, this tells you how to lift specific pieces from `feature/nictopia` into yours.

> **Branch**: `feature/nictopia`
> **Maintainer**: Nic (niclog2010@gmail.com)
> **Stack**: React 19 + Vite 8 + TypeScript + react-globe.gl + react-simple-maps + three.js
> **Status**: working demo end-to-end. 3 scenarios. Globe + Flat Map tabs. Real EIA/CAISO/gridstatus data anchors. See `docs/reference/electric_travel.md` for the grid-physics reference.

---

## Pull what you want

Each section lists the minimum files + deps to lift a feature into another React/Vite/TypeScript project. Most pieces are intentionally self-contained.

### 1. Real EIA carbon math (drop-in pure functions)

**What it gives you**: `getCarbonIntensity(ba)`, `tonsCo2Avoided(mw, durationMin, ba)`, `settlementUsd(mw, durationMin, pricePerMwh)`, `energyMwh(mw, durationMin)`. All derived from a real EIA-930 snapshot of CAISO/ERCOT/PJM/MISO carbon intensity (CAISO 69 / ERCOT 227 / PJM 338 / MISO 303 g CO₂/kWh). EPA eGRID + IPCC AR6 lifecycle emission factors.

**Files to copy**:
- `src/lib/eia.ts`
- `src/data/eia_snapshot.json`

**Deps**: none (pure TS + bundled JSON).

**Refresh script**: `scripts/fetch_eia.py` — set `EIA_KEY=<your_key>` (free, instant signup at https://www.eia.gov/opendata/register.php) and run with Python 3.11+ via `uv` (see `docs/reference/electric_travel.md` for install).

---

### 2. Historical incident replay data (5 archived hours)

**What it gives you**: real fuel-mix + LMP from 5 verified historical events. Use as authoritative anchors for any "this number is real" claim.

**Files**: `public/cache/historical/*.json`
- `ercot_uri_2021_02_16.json` — Winter Storm Uri peak load shed (EIA-930 fuel mix; LMP cap $9k from FERC)
- `caiso_psps_2019_10_09.json` — PG&E PSPS event (EIA-930 fuel mix during PSPS)
- `caiso_duck_2024_04_15.json` — real CAISO 96 × 15-min LMP from gridstatus: -$51 to +$61
- `caiso_heatdome_2023_08_15.json` — real LMP max $1,872 from gridstatus
- `pjm_helene_2024_09_27.json` — Carolinas EIA-930 during Helene

**Refresh script**: `scripts/fetch_historical.py` (Python 3.11 + gridstatus + EIA_KEY env var).

---

### 3. 3D Globe view (`react-globe.gl`-based)

**What it gives you**: WebGL globe with night-Earth texture, animated flow arcs, halo rings, hospital pins, VPP swarm, hover tooltips, zoom controls.

**Files to copy**:
- `src/components/GlobeView.tsx`
- `src/lib/geo.ts` (DC locations, BA centers, VPP swarm coords, critical sites by region, US outline path)

**Deps**: `react-globe.gl`, `three`. Plus the `LayerState` type from your version of `App.tsx` (or define locally).

**External CDN**: Earth night texture loads from `unpkg.com/three-globe/example/img/earth-night.jpg`. Pre-warm or self-host for offline demo.

---

### 4. Flat Map view (`react-simple-maps`-based)

**What it gives you**: 2D US map with state outlines, pan + zoom, all data layers (DCs, VPPs, hospitals, arcs, halos). Same data props as GlobeView.

**Files to copy**:
- `src/components/FlatMapView.tsx`
- `src/lib/geo.ts` (same as Globe)

**Deps**: `react-simple-maps`, `us-atlas` (the topojson is imported via `import statesTopo from 'us-atlas/states-10m.json'`), `d3-geo` (peer of react-simple-maps).

**No external assets** — fully bundled.

---

### 5. Bus ticker (live JSON message stream)

**What it gives you**: Side-panel that animates incoming bus messages with type-coded badges (GRID STATE, DISPATCH REQ, ENVELOPE, etc.) + REAL pill on anchored messages.

**Files to copy**:
- `src/components/BusTicker.tsx`
- The `BusMessage` and `BusMessageType` types from `src/types.ts`

**Deps**: just React.

**How to feed it**: pass `messages: BusMessage[]`. Each message has `{ id, ts, type, direction, summary, payload }`. Add a `_anchor` field to any payload to get the inline REAL badge.

---

### 6. Gated phase pattern (the "now engage VPP" dramatic beat)

**What it gives you**: pause-and-resume scenario engine. A scenario phase tagged `gated: true` causes the engine to pause after applying it; surfaces a big CTA button; resumes on click.

**Files to copy**:
- The `pendingGate` state + `schedulePhases` + `triggerScenario` + `resumeFromGate` functions from `src/App.tsx`
- The `Phase` type extension in `src/types.ts` (the `gated`, `gateLabel`, `gateSublabel` fields)
- CSS: search `index.css` for `.gate-overlay`, `.gate-button`, `.gate-sublabel`

**Deps**: just React state.

---

### 7. Scenario engine (phase-based replay)

**What it gives you**: a clean `Scenario` → `Phase[]` data model. Each phase is a partial-update bundle (nodes, edges, metrics, logs, bus messages, agent chatter, anchor). Plays out in order with `setTimeout` per phase. Easy to add scenarios.

**Files to copy**:
- `src/lib/simulation.ts` (initial state + 3 working scenarios)
- `src/types.ts` (Scenario, Phase, GridNode, GridEdge, Metrics, etc.)

**Deps**: depends on `src/lib/eia.ts` (for computed metrics). Replace with stub functions if you don't want the EIA math.

**To add a 4th scenario**: copy any of `ercotHeatWaveScenario` / `wildfireCaisoScenario` / `duckCurveScenario` and modify. Add to `SCENARIOS` array at bottom of file.

---

### 8. Grid-physics reference doc

**What it gives you**: the canonical "what travels where, what doesn't, why our viz is honest" doc. Includes mermaid diagram, key terms glossary, MW-as-grid-impact explainer, throttle/checkpoint/route mechanism flavors, anticipated audience Q&A.

**Files to copy**:
- `docs/reference/electric_travel.md` (zero deps, plain markdown)

Use this to brief any teammate before they talk to a grid-savvy listener.

---

### 9. Real-data anchoring pattern

**What it gives you**: the `Scenario.anchor` field convention + the pulsing green "REPLAYING REAL DATA" banner that shows during scenario playback with a clickable source link.

**Files**:
- `Scenario.anchor` type in `src/types.ts` (`{ incident, date, sourceUrl, realFact }`)
- The banner JSX in `src/App.tsx` (search for `real-data-banner`)
- CSS: search `index.css` for `.real-data-banner` + `.rdb-*` classes
- Bus message `_anchor` payload field + REAL pill in `src/components/BusTicker.tsx`

---

## Repo conventions

- **Writing rules** (gloss jargon, electricity stays local, anchor every number, counterfactual precision) — see top of `/Users/nic/dev/murmur_parallel.md`.
- **Glossary** of every grid acronym used — `docs/reference/electric_travel.md` "Key terms".
- **Scenario phases use `setTimeout`** scheduled via `schedulePhases()` so the engine is paused-and-resumable, not a single chained promise.
- **All metrics on screen are formula-derived** from `MW × duration × price` or `MW × duration × (peaker_carbon - ba_carbon)` via `src/lib/eia.ts`. No magic numbers in headlines or final-phase text. (See B1 work in `murmur_parallel.md` history.)

## Build / run

```bash
export PATH="$HOME/.local/node/bin:$PATH"   # if Node was installed standalone
cd /Users/nic/dev/murmuration
npm install
npm run dev   # http://localhost:5173/
npm run build # tsc + vite build
```

## Build size note

This branch is **2.3 MB JS / 21 KB CSS** uncompressed (~590 KB JS gzipped). Most of the JS is `three.js` (for the globe) + `react-simple-maps` topojson. Acceptable for a hackathon demo on local machine. If you don't need the globe, dropping `react-globe.gl` + `three` saves ~1.8 MB.

## What's NOT in this branch (consider before merging)

- No backend / no live API calls — runs fully offline from cached JSON
- No actual Anthropic SDK calls — bus messages are pre-scripted per phase
- No tests
- No CI config
- Real EIA API key is **NOT committed** — set `EIA_KEY` env var to refresh the snapshot via `scripts/fetch_eia.py`
