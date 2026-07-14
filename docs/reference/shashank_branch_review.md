# Branch comparison: `dev-cs` (Shashank) vs `feature/nictopia` (Nic)

> Reviewed at the start of the team meeting so we can decide which branch becomes the team's primary demo, and which pieces from the other branch we should lift in.

**Bottom-line up front**: Shashank's `dev-cs` is **architecturally more complete** — full Python backend with real agents, anomaly detector, topology healer, and 9 scenarios. **Nictopia is more polished narratively** — judge-friendly visuals, click-to-advance pacing, real-data anchors with citations, single-page docs.

**My recommendation**: use `dev-cs` as the demo base. Lift narrative + judge-comprehension polish from `feature/nictopia`. Specifics below.

---

## 1. Stack comparison

| Area | `dev-cs` (Shashank) | `feature/nictopia` (Nic) |
|---|---|---|
| Frontend | Single `index.html` (~3,750 lines), vanilla JS + globe.gl + d3 via CDN | React 19 + Vite 8 + TS, react-globe.gl + react-simple-maps |
| Backend | **Python 3.12 + FastAPI + WebSocket**, 11 modules, ~3,000+ LOC | none (frontend-only with bundled JSON) |
| Live data | gridstatus + EIA-930 streaming via WS, NREL solar profiles | EIA-930 + gridstatus snapshots cached to JSON |
| Agents | `GridAgent` + `ComputeAgent` Python classes; live Anthropic SDK narrator (Claude Haiku 4.5) with rule-based fallback | Pre-scripted bus messages per phase, no live LLM calls |
| Bus | `MurmurationBus` Python pub/sub, real Pydantic message types | TS-typed bus messages, in-memory stream |
| Persistence | Live tick loop (3s), in-memory state, broadcast over WS | Static phase data |
| Run model | `python -m murmuration.api.server` → serves UI + WS | `npm run dev` |

**Implication**: `dev-cs` is closer to the brainstorm doc's full §6 architecture. `feature/nictopia` is the demo-ready polished MVP-0 prototype.

---

## 2. What Shashank has that Nic doesn't

### Backend & protocol

- **Full Python backend** matching brainstorm §6.2 module structure: `forecast/`, `metrics/`, `anomaly/`, `topology/`, `protocol/`, `simulator/`, `api/`, `data/`, `assets/`, `orchestrator/`
- **Real `GridAgent` + `ComputeAgent` classes** (`orchestrator/`) — not pre-scripted. They publish on the bus, react to events, fire dispatches.
- **Live Claude narrator** — uses Anthropic SDK with Claude Haiku 4.5; falls back to rule-based if no key. Voice prompts for both grid + compute personas.
- **Pydantic `MurmurationBus`** with 7 typed message types from §7 — `GridStateUpdate`, `GridForecast`, `DispatchRequest`, `ContingencyAlert`, `FlexibilityEnvelope`, `LoadForecast`, `DispatchAck`/`TelemetryFrame`. Plus extras: `WorkloadMigration`, `CounterOffer`, `TopologyReconfigure`.
- **`AnomalyDetector`** — rolling z-score watchdog on every BA stream. Auto-fires `ContingencyAlert` on >4σ deviation. The "self-healing" feature your team note flagged.
- **`TopologyGraph` + `TopologyHealer`** — `networkx`-backed substation graph. On contingency: marks edge failed, computes K-shortest alt paths, identifies downstream assets, publishes `TopologyReconfigure`. **This is the "smart routing" your team note asked for.**
- **`WorkloadRouter` with tiered escalation**:
  - Tier 1: sibling AZ in same region (sub-ms latency)
  - Tier 2: cross-region (10-100ms)
  - Tier 3: throttle in place (last resort)
  - Each migration published as `WorkloadMigration` so UI draws tier-aware arcs. **This is also the team-note ask.**
- **`ScenarioManager` with 9 scenarios** (vs Nic's 4):
  - Texas heat wave, CAISO evening ramp, PJM-DOM congestion, CAISO surplus solar, polar vortex cascade, PJM line-trip contingency, carbon arbitrage, ERCOT solar eclipse, **PJM Loudoun substation overload (with intra-region failover — the self-healing demo)**
- **`MetricsTracker`** — proper accumulation across the live tick loop
- **9 DCs** organized as 3 AZs per region (`DC-CA-1a/1b/1c`, `DC-TX-1a/b/c`, `DC-VA-1a/b/c`) — gives the AZ-failover story machinery
- **Solar profiles via NREL PVWatts** — fed into the load forecaster as a feature
- **HIFLD transmission lines** + substations on the flat map (real gov geo data)
- **DMV-region zip-level reserve clusters** that activate when stressed BA needs help
- **CSV-derived live ISO data** — CAISO load + fuel mix in real time, carbon derived from mix; falls back to synthetic only on failure

### UI / scope

- **3 views**: 3D Globe + Flat Map + **Story** (full presentation-grade walkthrough mode)
- More polished header (session clock, status pills like LINK UP / RULE FALLBACK / 3 ISO · 3 DC)
- Clickable BA / DC detail cards
- Right-rail with deeper detail
- Bus feed with cleaner pause/playback controls
- HIFLD transmission overlay with voltage-class color/stroke (≥220 / 345 / 500 kV bands)
- 100-home Bay Area VPP rendered as zip-level dots (vs nictopia's 42 abstract VPP dots)

---

## 3. What Nic has that Shashank doesn't

### Judge-comprehension layer (where nictopia is stronger)

- **Click-to-advance scenario engine** — every phase pauses for narration; presenter clicks to dismiss. No auto-fade. Full pacing control. **Major demo-day asset.**
- **FlashBanner** — per-phase center-screen narrative banner, click-to-dismiss, ESC support, color-coded by tone (stress/action/resolved/settled). 16 banners scripted across 4 scenarios with cause-effect language ("ERCOT WARNING → STABLE", "+320 MW local injection · 4 critical hospitals protected").
- **Always-visible LegendStrip** at top-center of map — Stress / Compute / VPP / Protected pills with active-pulse animation when corresponding flow is live. Solves the "what do these lines mean" judge confusion.
- **Per-BA StabilityGauge** at top-left — pip-score visual (5-pip ●●●●● CRITICAL → ●○○○○ healthy) per BA, with status text. Direct McGee-style control-room aesthetic.
- **"REAL DATA" pulse badge** on every scenario showing the anchor incident name + clickable source URL (FERC/NERC/EIA/CAISO/JLARC). Direct anti-eye-roll inoculation.
- **Bus message REAL pill** — anchored bus messages get a green "REAL" tag inline with their content.
- **Mid-arc labels** auto-suppressed while flash banner is up — eliminates label-on-flash overlap.
- **VPP dots quiet down when halo activates** — reduces "glob of play signs" effect.
- **Compute arc dims** when VPP halo active — visual hierarchy shift draws eye to the new event.
- **Gated VPP click** — presenter explicitly clicks "Now engage the Virtual Power Plant" big button — dramatic moment.
- **"Compute migration" labels semantically correct** — "850 MW REROUTED · scheduler shifts work" (not "850 MW transferred"). Anti-grid-eye-roll language baked in.

### Documentation (where nictopia is way ahead)

- **`INTEGRATION.md`** — cherry-pick guide listing every reusable module + its deps
- **`docs/reference/electric_travel.md`** — full grid-physics reference with mermaid diagrams. 3-interconnection model. MW-as-grid-impact section. Throttle/checkpoint/route mechanism explainer. Key-terms glossary.
- **`docs/reference/what_is_nictopia.md`** — 7 mermaid diagrams, judge-flow, data architecture, visual element guide (this file's sibling)
- **`results/D1_data_research.md`** — gridstatus + CAISO OASIS, live-verified Python snippets
- **`results/D2_eia_research.md`** — EIA Open Data v2 endpoints, real BA carbon values
- **`results/D3_incidents.md`** — 5 incidents (Uri 2021, PSPS 2019, CAISO 2024 curtailment, Helene 2024, NoVA 2024) with primary-source citations + claim-language ladder + "WEAKENING facts" inoculation per incident
- **`results/GR1_grid_physics.md`** — NERC/FERC/DOE + Google CICP arXiv 2106.11750 deep citations + Q&A talking points
- **Defensible-math `src/lib/eia.ts`** — every $ and tCO₂ on screen formula-derived from real EIA-930 BA carbon intensities (CAISO 69 / ERCOT 227 / PJM 338 / MISO 303 g CO₂/kWh). When a judge asks "where's $390K from?", you point at the formula.

---

## 4. What the team-note items are already in `dev-cs`

The user's team feedback before this review:

> "thinking for the engage VPP button we want to instead of migrating loads to another region instead migrate them to use VPP. maybe some logic on if the VPP can support your workload then you don't need to migrate (and good for some scenarios where you are unable to migrate jobs)"

✅ **Already in `dev-cs`** via `WorkloadRouter`'s tiered escalation:
- Tier 1: Sibling AZ in same region (no cross-region migration needed if local is fine)
- Tier 2: Cross-region migration
- Tier 3: Throttle / VPP relief

The router code chooses the lowest-tier option that satisfies the dispatch. If VPP can absorb it locally, no cross-region migration fires. Exactly what your team asked for.

> "need to think about simulating that this grid is resilient and self healing able to smartly route (ex. 1 data center had outage, then 2 around it are overloaded)"

✅ **Already in `dev-cs`** via:
- `AnomalyDetector` z-score watchdog
- `TopologyHealer` K-shortest paths around failed edges
- `TopologyReconfigure` bus message broadcast
- "PJM Loudoun substation overload" scenario with intra-region failover already wired
- WorkloadRouter Tier 1 redirect to sibling AZ when one AZ goes down

So your team's two main feature asks are **already implemented in `dev-cs`**. We don't need to build them. We need to make them **legible to judges.**

---

## 5. Proposed merge plan — `dev-cs` as base + nictopia polish lifted in

Use `dev-cs` as the demo's spine. Lift these from `feature/nictopia`:

### High-value cherry picks (~30 min each, big judge-comprehension wins)

| From nictopia → into dev-cs | Why | Effort |
|---|---|---|
| **FlashBanner pattern** — per-phase center-screen click-to-advance overlay with cause-effect language | dev-cs has 9 scenarios but they auto-tick. Adding the click-to-advance flash gives the presenter control. | ~30 min — port `FlashBanner.tsx` logic to vanilla JS overlay (single HTML file structure makes this easier) |
| **LegendStrip** — always-visible top-center color key with active-pulse | Solves the "what do these lines mean" judge problem. dev-cs's UI doesn't have a comparable always-on key. | ~20 min — pure CSS + HTML strip; no React |
| **StabilityGauge** — per-BA pip-score panel | Looks like a control-room monitor. McGee-aligned. dev-cs has BA cards but not a compact at-a-glance stress gauge. | ~25 min |
| **"REAL DATA" pulse badge** with clickable source URL | dev-cs has live data but doesn't *advertise* what's real with citation. The badge is the fastest way to tell judges. | ~15 min — small pill component + Scenario `anchor` field |
| **`docs/reference/electric_travel.md`** + glossary | Pure markdown — no integration cost. Pre-emptive Q&A inoculation. | ~5 min — copy file |
| **`docs/reference/what_is_nictopia.md` (rename/adapt)** | The 7-mermaid-diagram team meeting reference can become "what is the team's combined demo." | ~5 min — adapt 1-2 diagrams |
| **`results/D1/D2/D3/GR1`** | Full citation backing for every claim | ~5 min — copy folder |
| **Cause-effect language audit** — labels like "850 MW REROUTED · scheduler shifts work" not "850 MW transferred" | Anti-grid-eye-roll. Already-validated wording. | ~30 min — sweep dev-cs's UI strings |

### Skip (overlap or already better in dev-cs)

- 3D Globe component — dev-cs's globe.gl works; no React port needed
- Flat Map component — dev-cs already has Albers USA + HIFLD transmission lines, more advanced than ours
- Bus Ticker — dev-cs has bus-feed already
- `src/lib/eia.ts` formulas — dev-cs computes carbon intensity live from real fuel mix, supersedes our snapshot
- 4 nictopia scenarios — dev-cs has 9 already; ours overlap

---

## 6. Risks if we use `dev-cs` as base

1. **Demo brittleness** — live tick loop + WebSocket + Python backend = more moving parts than nictopia's frontend-only static demo. **Mitigation**: record fallback video from dev-cs once it's stable.
2. **Setup friction** — Python venv, requirements.txt, optional API keys. nictopia is `npm install + npm run dev`. **Mitigation**: a teammate spins it up well before showtime; it stays running.
3. **Bug surface** — 3,000+ LOC of Python is more debug surface than nictopia's static phases. **Mitigation**: don't change anything risky after the practice run.
4. **Pacing without click-to-advance** — dev-cs auto-ticks. Judges may not be able to read everything. **Mitigation**: this is the #1 cherry-pick (FlashBanner pattern) — port it before the demo.

## 7. Risks if we use `feature/nictopia` as base instead

1. **Less impressive on technical-difficulty rubric** — no real backend, no live agents, no anomaly detector, no topology healer. Judges who want depth (Barati especially) will find dev-cs more impressive.
2. **9 vs 4 scenarios** — dev-cs covers more value-prop pillars including the contingency / self-healing one your team flagged.
3. **Team's "Tier 1 sibling AZ failover" ask is already in dev-cs** — building it again in nictopia is wasted effort.

---

## 8. Recommendation

**Use `dev-cs` as the demo. Cherry-pick from nictopia as listed above (~2 hours total).**

The combination plays to both judges:
- **McGee** (operational realism): dev-cs's live tick + real ISO data + topology healer + tiered router = "this could run in a control room"
- **Barati** (correctness + dynamics): dev-cs's z-score anomaly detector + load forecaster + TopologyReconfigure feedback loop = "this behaves like a valid simplified power system"
- **Both** (clarity in <2-3 min): nictopia's FlashBanner + LegendStrip + StabilityGauge + "REAL DATA" badges + cause-effect language = "judges understand at a glance"

If the team disagrees and prefers `feature/nictopia` as the base, the gap is closeable but bigger — we'd need to port the anomaly detector, topology healer, and tiered router from dev-cs into nictopia (~4-6 hours of TS reimplementation), and our demo wouldn't have the live-data prestige of dev-cs.

---

## 9. Next steps for the meeting

1. **Decide base branch** (recommend dev-cs)
2. **Walk through dev-cs's PJM Loudoun substation overload scenario** — see if the "self-healing" feature works visually as the team imagines
3. **Identify owner per cherry-pick** from §5 above
4. **Lock the demo script** — which 2-3 scenarios get presented, in what order, with what narration
5. **Schedule a fallback-video recording window** for whoever's branch we land on
6. **Confirm presenter** — they need DEMO1 (narration script — already prompt-spec'd in `murmur_parallel.md`)

---

## 10. Branch URLs for reference

- Shashank: https://github.com/enturesting/murmuration/tree/dev-cs
- Nic: https://github.com/enturesting/murmuration/tree/feature/nictopia
- Original Copilot prototype: https://github.com/enturesting/murmuration/tree/copilot/create-murmuration-prototype
