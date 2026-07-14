# Judge Q&A prep — hard-question defenses

> Companion to `demo_flow.md`. The Q&A section there covers the easy questions. This doc handles the **hard** ones — the questions a smart judge or technical SME will actually ask, and the strongest honest answers we have.
>
> **Built against dev-cs codebase**: live Python tick loop, real EIA-930 + gridstatus.io data, two real Claude-narrated agents (`GridAgent`, `ComputeAgent`), tiered `WorkloadRouter`, `AnomalyDetector` (z-score watchdog), `TopologyHealer` (networkx), 9 scenarios, 7 ISOs.
>
> Rule for everyone on stage: **never overclaim.** "Would have softened" beats "would have prevented." The grid is real and people have died in these incidents (Uri = 246 deaths). Conservative, precise language is also the most credible language.
>
> **Each answer is tagged for the judge it most directly serves:** `[McGee]` (operational realism — control room, dispatch, failure modes), `[Barati]` (model correctness — assumptions, system dynamics, measurable response), `[Both]` (lands for either lens). The full judge framing is in `criteria.md` § "Reading the judges".

---

## Reading the room — judge cheat sheet

| Judge | Lens | Tell |
|---|---|---|
| **Monty McGee** | "Could this run in a control room tomorrow?" | Cares about dispatch timing, fallback, capacity, FERC/NERC reality. |
| **Dr. Masoud Barati** | "Is the simplified model valid?" | Cares about cause→effect, assumptions, before/after metrics, feedback loops. |

**Default reflex when a question lands:**
1. Identify which judge framing it fits (or both).
2. Lead with the answer in *their* language: McGee → operational steps; Barati → causal chain + measurable delta.
3. End by volunteering one limit. Both judges reward honest scoping more than confident overreach.

If you don't know which judge asked: assume Barati if the question contains words like "model," "assume," "valid," "data." Assume McGee for "deploy," "operator," "fail," "real."

---

## The killer question

### "Where's the AI? This looks like a deterministic simulation."  `[Both]`

**The honest answer (much stronger with dev-cs):** "Three places. First, the **live narrator** — that's Claude Haiku 4.5 running in `orchestrator/narrator.py`, generating both agents' voices in real time. You can see its output in the agent-chatter feed below the bus. If you turn off `ANTHROPIC_API_KEY`, it falls back to rule-based summaries — but with the key, every operator-style sentence on screen is being written live. Second, the agents themselves are real Python classes — `GridAgent` reacts to `GridStateUpdate` with a `GradientBoostingRegressor` load forecaster, fires `DispatchRequest` when stress crosses threshold. `ComputeAgent` runs the tiered `WorkloadRouter`. Neither is scripted JSON. Third, the dispatch path itself is *deliberately* deterministic — the LLM writes the standing envelope once, then within-band acceptance is auto. That's how response times stay under 30 seconds. The LLM is one layer up, exactly where you want it."

**Then pivot to a live demonstration if useful:**
- *Show the agent-chatter feed:* "Watch this row — that's Claude generating the operator's reasoning in real time, conditioned on the bus state."
- *Show the topology healer's `TopologyReconfigure` message firing without any scripting:* "Notice the scenario only said 'mark this AZ unavailable' — the reroute logic was triggered by the anomaly detector firing on the resulting `GridStateUpdate` deviation."

**Don't say:** "We ran out of time." Live agents are in the codebase. Show them.

---

## The data integrity questions

### "Is this real data, or did you just make up numbers that look right?"  `[Barati]`

The CAISO load + fuel mix is **live from `gridstatus`** (see `data/iso_client.py`) — pulled every tick from CAISO's public CSV. ERCOT/PJM/MISO/NYISO/ISO-NE/SPP fuel mix comes from **EIA-930** (free, public, with optional API key for higher rate limits). Carbon intensity is **derived live** from the fuel mix using EPA eGRID emission factors embedded in `iso_client.py`. Stress score is derived from load-to-peak ratio.

The **scenario LMP/carbon overrides** (e.g., ERCOT $410, CAISO -$51) are *typed in by us* — they're the dramatic narrative beats. We're explicit about this: scenarios *paint* a stress condition; the underlying data, agent reactions, and metrics are real.

The **MW dispatch numbers** (per-AZ profiles, VPP capacity) are *conservative estimates* of what real campuses and aggregators could commit, anchored to published numbers in the LBNL US Data Center Energy Report. Be explicit that these are scenario inputs, not claims about a specific facility.

### "Show me the citation for [specific number]."  `[Barati]`

Have these ready:
- **Uri (246 deaths, $130B):** FERC/NERC joint Inquiry into Bulk Power System Operations During February 2021 Cold Weather Event (published Nov 2021).
- **PG&E PSPS (~800K customers de-energized Oct 9 2019):** PG&E press releases + CPUC PSPS reports.
- **Dominion 2024 NoVA moratorium (4 GW DC growth vs 2.1 GW substation capacity):** JLARC Virginia Data Center Study 2024 + Utility Dive coverage.
- **CAISO 2024 curtailment (3.4M MWh, +29% YoY):** CAISO annual market report + EIA Today in Energy.
- **Carbon factors:** EPA eGRID 2022 (combustion) + IPCC AR6 WG3 Annex III (lifecycle for renewables/nuclear). Constants in `iso_client.py` `CARBON_FACTORS` dict.

### "Where do live ISO numbers come from in real time?"  `[Both]`

`data/iso_client.py` uses the `gridstatus` Python library for CAISO (no auth, free CSV). For other ISOs, it uses the EIA-930 hourly fuel-mix series via `data/eia_client.py`. If a fetch fails, the scenario continues with synthetic-but-plausible values — demo never breaks. The same fetch infrastructure powers `forecast/nrel.py` (NREL PVWatts solar profiles, optional via `NREL_API_KEY`).

---

## The "why is this hard?" questions

### "Couldn't a hyperscaler just buy peakers and not bother with this?"  `[McGee]`

Three reasons the math doesn't work:
1. **Capital lock-in for an event you might not have.** A 200 MW peaker is ~$200M+ capex for an asset that runs <5% of the year. Standing envelopes monetize the same flexibility with zero new capex.
2. **CO₂.** Peakers are gas turbines at ~430 g/kWh combustion. Migrating 850 MW of training to a clean-grid region during a heat wave is what the eGRID math in our scenarios actually scores.
3. **Permitting.** Adding peaker capacity in NoVA or Dallas runs into multi-year siting fights — Dominion's 2024 moratorium is exactly this. Software contracts ship in months.

### "How is this different from existing demand response programs?"  `[McGee]`

Existing DR is per-utility, per-program, with phone-tree dispatch and per-event opt-in. Standing envelopes are: standing (no per-event approval), bilateral (one channel per pair, not per program), telemetric (`TelemetryFrame` messages stream per second during dispatch), and settled at the envelope rate.

The "one schema, every scale" claim — same `FlexibilityEnvelope` works for a 200 MW DC and a 5 kW home battery — is what no existing DR program does. Plus, we have a **tiered workload router** that picks intra-region failover before cross-region migration. That escalation logic is what an actual cloud scheduler does; today's DR programs are "shed or don't."

### "Why won't FERC / NERC / the ISO governance process kill this in committee?"  `[McGee]`

The bilateral framing is a deliberate move around the multi-year tariff filing problem. An ISO can pilot bilateral coordination contracts with a single hyperscaler without rewriting the wholesale market. CAISO's existing Demand Response Auction Mechanism and PJM's Capacity Performance products are precedent for bilateral standing offers. We're not asking FERC for a new market — we're proposing a wire format two existing market participants can agree to use.

---

## The topology healer + anomaly detector questions  (NEW for dev-cs)

### "Walk me through the self-healing demo. What's actually happening?"  `[Both]`

Step-by-step (PJM Loudoun substation overload scenario):
1. Scenario sets DC-VA-1a's `unavailable` flag and overrides PJM stress to 0.58.
2. Next tick, `GridAgent` publishes `GridStateUpdate` reflecting the new headroom drop.
3. `AnomalyDetector` (in `anomaly/detector.py`) computes z-score on the LMP/stress stream — exceeds the 4σ threshold → publishes `ContingencyAlert(event_type="line_trip")`.
4. `TopologyHealer` (in `topology/healer.py`) consumes the alert. Looks up affected nodes in the `networkx` substation graph (`topology/graph.py`), marks the worst-stressed adjacent line as failed, computes K-shortest alternate paths, publishes `TopologyReconfigure`.
5. `ComputeAgent`'s `WorkloadRouter` receives the same alert. For workloads stranded on DC-VA-1a, it tries Tier 1 (sibling AZs DC-VA-1b, DC-VA-1c). They have headroom → publishes `WorkloadMigration` per workload, intra-region.
6. Globe UI: short cyan arcs flash within the NoVA cluster. Bus feed shows the `TopologyReconfigure` and `WorkloadMigration` messages. Settlement metrics tick up.

**The point:** none of steps 3-6 were scripted. The scenario only fired step 1. Everything downstream is the system reacting.

### "What does the anomaly detector actually use?"  `[Barati]`

A rolling 60-sample window of LMP per BA. Z-score on each new sample. Threshold = 4σ. Cooldown 30s between consecutive alerts on the same BA to prevent spam. See `anomaly/detector.py` `_RollingZ` class — it's ~30 lines of code, deliberately simple. Real grid anomaly detection uses much fancier things (state estimation residuals, EMS dynamic-state validation), but z-score on a single observable is honest enough for a working watchdog.

### "How does the workload router decide which tier to use?"  `[McGee]`

Greedy by tier order. For each stranded workload (we know which workloads were running on the failed AZ), iterate:
1. Tier 1 (intra-region siblings): scan sibling AZs in the same `region`. If aggregate headroom across siblings ≥ workload's MW, migrate there. Sub-ms latency, no data staging.
2. Tier 2 (cross-region): scan eligible regions (each workload class has an eligibility list). Pick the lowest-LMP eligible region with headroom. ~45 ms transcontinental latency, data must be staged.
3. Tier 3 (throttle in place): can't relocate → shed the workload entirely. Counts as MW relief but degrades service.

The router publishes a `WorkloadMigration` event per migration so the UI can draw tier-aware arcs (color/length differs by tier).

---

## The threat-model questions

### "What stops a bad actor from sending fake `DispatchRequest` messages?"  `[McGee]`

The bus is bilateral, not broadcast — each channel is between exactly two named parties (e.g., CAISO ↔ DigitalRealty-SF). Same trust model as the ISO ↔ market-participant channels that exist today. Envelopes are signed; payloads are opaque to anyone outside the channel. We're not proposing new cryptography — we're using what bilateral wholesale markets already deploy.

### "What about a state actor compromising a hyperscaler's compute-side agent and using it to attack the grid?"  `[McGee]`

The dispatch path is bounded by the standing envelope. Even a compromised compute agent can only commit *up to* what its envelope allows, for the duration the envelope allows. The blast radius of a compromised endpoint is the envelope's MW-minutes — not unbounded grid manipulation. The ISO-side agent always has the right to revoke any envelope at any time (and the topology healer can re-isolate if the compromise manifests as anomalous behavior — see anomaly detector).

This isn't a complete answer (an envelope of 200 MW can still cause harm), but it's the right architecture: envelopes are circuit breakers, not blank checks.

### "Why should an ISO trust an LLM in the loop?"  `[Both]`

The LLM is **not in the dispatch loop**. It writes the standing envelope at intake (where the operator has time to review), and the dispatch path is then deterministic auto-accept within band. An LLM hallucinating an envelope is caught at intake by the operator. An LLM hallucinating mid-dispatch is impossible because no LLM is mid-dispatch. The narrator LLM that generates the operator-voice text is observability-only — it can't issue dispatches.

---

## The scope questions

### "Is this a full solution or a wedge?"  `[Both]`

A wedge. Specifically: a coordination protocol between three constituencies (grid, compute, DERs) that today have no common wire. We don't claim to solve generation adequacy, transmission queue reform, or interconnection. We claim that adding a standing-envelope protocol on top of the existing wholesale market unlocks ~hundreds of MW of latent flexibility per major BA without new generation or new permitting.

### "How does this scale beyond a hackathon demo?"  `[McGee]`

The scaling story has three layers:
1. **Pilot:** one ISO + one hyperscaler campus + one VPP aggregator. ~12-month deployment, no new market rules.
2. **Region:** all hyperscaler campuses in one BA opt in. ~24 months.
3. **Continental:** the wire format becomes a NAESB or NIST standard. Multi-year, but doesn't block earlier value.

### "What happens when this fails — a campus opts out mid-dispatch?"  `[McGee]`

The `TelemetryFrame` stream is per-second. The ISO sees commitment vs. delivery in real time. Failure to deliver triggers envelope revocation and falls back to the existing peaker / curtailment / blackout response — i.e., the worst case is exactly today's status quo. The protocol is strictly additive.

---

## The honest-limit questions

### "What can your demo NOT do that real grid coordination would need?"  `[Barati]`

Strongest answer is to volunteer the limits before they're pulled out of us:
- **No real Hz/VAR/voltage modeling.** The protocol talks MW; real grid stability talks Hz and VAR. We mock frequency in the `GridStateUpdate.frequency_hz` field but don't simulate it.
- **VPP dispatch is modeled as ~95% acceptance** in `home_battery.py` — real VPPs have richer opt-out and SoC-floor constraints we abstract.
- **Workload migration is signaled but not actually scheduled.** The `WorkloadRouter` decides where workloads *should* move; in real life a Borg/Kubernetes scheduler would do the actual replacement.
- **No model of communication failure or latency between the bus and the agents.** We assume the bus is always up.
- **No cross-jurisdiction trust model** — the bilateral framing assumes counterparties have a pre-existing legal relationship.

### "What would a v1 of this look like in production?"  `[Both]`

- Add a real signing / cert layer for the bus messages (we use Pydantic for validation, no crypto).
- Replace the `WorkloadRouter` simulation with bindings into a real cloud scheduler (Borg / Kubernetes / Twine).
- Cross-reference each `DispatchRequest` against the operator's existing day-ahead schedule to avoid double-commitment.
- Add the missing physics layers (Hz, VAR) for grid-side ack credibility.
- Integrate with existing CAISO DRAM and PJM Capacity Performance settlement systems.
- Replace the rule-based load forecaster with the operator's existing ISO forecaster (don't duplicate that work).

We chose the protocol design as the contribution because everything above is engineering work that requires the protocol to exist first.

---

## Live-data + setup questions

### "Why are you running offline / live? What changes?"  `[McGee]`

If we're online with `ANTHROPIC_API_KEY` + `EIA_KEY` + `NREL_API_KEY` set:
- Narrator generates voices live via Claude Haiku 4.5
- Non-CAISO ISOs pull live EIA-930 fuel mix
- NREL PVWatts solar profiles refresh on startup
- CAISO load + fuel mix already streams via `gridstatus` regardless of keys

If offline:
- Narrator falls back to rule-based phrasing (still legible)
- Non-CAISO ISOs use synthetic (still plausible)
- Solar profiles use a synthesized diurnal curve

The demo behaves identically in either mode — only the *aliveness* of the narration changes.

### "Why did you choose Python+FastAPI over a single-page web app?"  `[McGee]`

Brainstorm doc §6.3 makes the case: gridstatus is Python (one library covers 7 ISOs, would be reimplemented from scratch in JS), FastAPI scaffolds quickly, scikit-learn forecaster is 50 lines, Pydantic gives free schema validation for the bus messages. The frontend is a single self-contained `index.html` so there's no build step on the demo machine. Python backend + vanilla JS UI = fewest moving parts that earn the rubric.

---

## If we're stumped

- "That's a great question. Honestly we haven't modeled that — let me get back to you." Better than a wrong answer. Judges respect technical honesty more than they reward bluffing.
- Defer to the docs:
  - `MURMURATION.md` — full architecture + thesis
  - `PITCH.md` — slide-by-slide rationale
  - `docs/reference/electric_travel.md` — grid physics (3 interconnections, MW-as-grid-impact, throttle/checkpoint/route)
  - `murmuration/README.md` § "What's modeled vs. what's playback" for the data integrity story
