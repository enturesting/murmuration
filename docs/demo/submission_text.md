# Submission text — drop into SCSP form fields

> Drop-ready text for the SCSP Hackathon Grid track submission. Multiple length variants because we don't know which form field needs which length. Pick the closest fit, paste, lightly edit if the form has a character limit.
>
> **Lock the final version at 4:45 today.** Whoever owns submission-form-fill (per `sync_agenda_2pm.md`) updates this file with what actually got pasted, so we have a record.
>
> Strategy reminder: in a 12-team comparison, **judges read submissions before they watch demos.** This text frames their viewing. Lead with the SCSP-aligned thesis: enablement layer for the experts running US critical infrastructure.

---

## Project name

**Murmuration**

## Track / category

SCSP Hackathon · Electric Grid Optimization

## Tagline (≤140 chars)

A protocol — and two live agents — for the grid and the AI compute fleet to coordinate flexibility under stress.

*(111 chars. Mirrors the cold-open slide subtitle.)*

## Short description (~50 words)

The grid is breaking more often, with higher stakes — and billions of dollars of flexibility sit idle when stress hits because there's no common language between supply and demand. Murmuration is that wire format: a bilateral protocol and two live Python agents that let datacenters, virtual power plants (VPPs — swarms of home batteries, EVs, and smart thermostats), and Independent System Operators (ISOs — the entities running each regional grid) coordinate in seconds, not phone-tree minutes.

## Long description (~250 words)

Heat waves, polar vortexes, line trips, Asheville floods, Maui fires, California wildfires — events we used to call rare now hit every season. The experts who keep the grid standing are coordinating with tools built for a world that doesn't exist anymore. Meanwhile, data centers scaling at gigawatt pace, EV fleets, and home batteries sit idle when stress hits — because there's no common language between supply and demand.

**Murmuration is the wire format for the flexible energy fleet**: a bilateral protocol with seven message types and two live Python agents — one on the grid side, one on the compute fleet side — that negotiate **flexibility envelopes** (each side's published offer: "I'll absorb up to X megawatts, in this band, with this notice") in seconds. Every demo scenario is anchored to a real archived event: Texas Uri (2021), PJM Loudoun (2024), and seven more. The anomaly detector (rolling 4σ z-score on live grid state), the topology healer (networkx K-shortest paths), and the tiered workload router are real — none of it scripted into the scenarios.

We are explicitly **not replacing** operators, utilities, or policymakers. We are the **enablement layer** that lets the experts running US critical infrastructure keep the wheel — and make it turn faster. Data centers keep scaling without breaking the grid. Critical infrastructure — hospitals, water systems, ISO control rooms — gets first-class routing the moment stress hits. No new market rules required.

**The ask:** a 12-month pilot. One ISO, one hyperscaler campus, one VPP aggregator.

## Inspiration

Texas Uri killed 246 people in February 2021. The ERCOT operator at 2 AM, four minutes from cascading collapse, had three tools to choose from: peakers, curtailment, brownouts. The 4.5 million customers who lost power for days weren't the consequence of insufficient generation — they were the consequence of **zero coordination across the bilateral interface** between the grid and the loads that could have helped. Cold-snap events, line trips, polar vortex cascades all share the same shape: the grid is stressed, and meanwhile flexibility sits idle on the other side of an interface that doesn't speak the same language. What if there were a wire format — a common language — that let the experts running the grid coordinate with the compute fleet, the VPP swarm, and the regulators in seconds, not phone-tree minutes?

## How we built it

Python 3.12 backend with FastAPI, Pydantic for the protocol schema, WebSockets for the live UI feed. The bilateral bus is a Pydantic-validated message channel with seven core message types: `GridStateUpdate`, `GridForecast`, `DispatchRequest`, `ContingencyAlert`, `FlexibilityEnvelope`, `LoadForecast`, `DispatchAck`/`TelemetryFrame`, plus extensions for `WorkloadMigration`, `CounterOffer`, and `TopologyReconfigure`. Two live Python agents — `GridAgent` and `ComputeAgent` — speak the protocol on a 3-second tick loop. Anomaly detection is a rolling z-score (4σ) on live `GridStateUpdate` events. Topology graph is `networkx` with K-shortest path computation. Load forecasting uses scikit-learn `GradientBoostingRegressor`. Live ISO data via `gridstatus` (CAISO, ERCOT, PJM, MISO) and EIA-930 fuel mix. Solar profiles from NREL PVWatts. Narrator uses Claude Haiku with a deterministic rule-based fallback. Web UI is vanilla JS with `globe.gl` and `d3` for three views (3D Globe, Flat Map, narrative Story tab).

## Challenges we ran into

**Claim hygiene.** The grid kills people when it fails — Uri killed 246. We owed honest framing. Every counterfactual in the demo says "would have softened," never "would have prevented." Hard discipline to maintain when you're trying to win a hackathon.

**Judge legibility.** A protocol is invisible. We had to make message-bus events visible on screen in real time with cause-and-effect labels that read like an operator's EMS — not a developer's debug log. Polish on the visualization layer (REAL DATA pulse badges, cause-effect labels, always-visible legend) carried that weight.

**Separating triggers from response.** A scenario tells the world what to hand us — Loudoun substation overloads, ERCOT LMP spikes — but the agent response has to be real, observable on the bus, and not pre-scripted. The PJM Loudoun scenario only declares `unavailable=["DC-VA-1a"]`. Everything that follows — the anomaly detector firing on a 4σ z-score, the topology healer recomputing K-shortest paths, the workload router escalating tiers — is the protocol responding live. Keeping that boundary clean is real engineering, not just narrative framing.

**Resisting feature sprawl.** Nine scenarios is a lot. The temptation was always to add a tenth. We held the line: depth on two scenarios beats breadth on five.

## Accomplishments we're proud of

**Self-healing that was never scripted.** The PJM Loudoun beat triggers our anomaly detector (rolling 4σ z-score on live grid state). The detector fires a `ContingencyAlert` on the bus. The `TopologyHealer` consumes the alert, marks the failed edge in the `networkx` substation graph, computes K-shortest alternate paths, publishes `TopologyReconfigure`. The `WorkloadRouter` then fails over to sibling availability zones (Tier 1 — sub-millisecond, no data migration). The scenario file only declares `unavailable=["DC-VA-1a"]`. **The protocol does the rest.** We believe this is the only entry in the Grid track where this exact path is unscripted, end to end.

## What we learned

The hardest part of building a coordination protocol isn't the protocol — it's the **honesty layer**. What can the system actually claim? What's modeled vs. played back? What does a regulator need to believe before they trust it? We ended up writing more documentation about claim hygiene and grid-physics constraints than we did about the bus itself. That documentation is in the repo: `docs/reference/electric_travel.md` (what can and can't travel between US grid regions) and `docs/demo/judge_qa_prep.md` (the questions a sharp grid expert will actually ask).

## What's next

The 12-month pilot: one ISO, one hyperscaler (large cloud provider) campus, one VPP aggregator. Within that pilot — replace the deterministic playback with a real workload scheduler integration, add a cryptographic signing layer to the bus, walk the protocol through the **FERC** (Federal Energy Regulatory Commission) and **NERC** (North American Electric Reliability Corporation) standards path. **FERC Order 2222 already opened wholesale markets to distributed energy resources; Murmuration is the wire format that lets aggregators actually plug in.** Phase 2: continental scale-out across all 7 US ISOs, target 5 GW of bilateral envelope capacity by 2027. **We are explicitly not building a replacement for operators or utilities — we are the enablement layer that lets the experts keep the wheel and make it turn faster.** The next conversations are with ISOs, hyperscalers, and the FERC standards office.

## Built with

`Python 3.12` · `FastAPI` · `Pydantic` · `WebSockets` · `gridstatus` · `EIA-930` · `NREL PVWatts` · `networkx` · `scikit-learn` · `Claude (Haiku)` · `globe.gl` · `d3` · `vanilla JavaScript`

## Links

- **GitHub:** https://github.com/enturesting/murmuration
- **Demo video:** _TBD — record by 3:45 today, paste link here_
- **Local demo:** `bash murmuration/run.sh` from repo root → http://127.0.0.1:8765/
- **Architecture / thesis doc:** `MURMURATION.md` in repo root
- **Pitch / slide-by-slide rationale:** `PITCH.md` in repo root
- **Live presenter script:** `docs/demo/presenter_card.md`

## Team

_TBD — fill names + roles + LinkedIn or GitHub handles before submission_

---

## Strategic notes for whoever pastes this (do not paste these into the form)

1. **Lead with the SCSP-aligned thesis.** Murmuration is *enablement of experts running US critical infrastructure* — that's exactly the framing SCSP's parent org publishes papers about. Make sure that phrase or one very close to it lands in the first 30 words of whatever's the most-prominent description field.
2. **If the form has a "What dataset / data source" field**, name `gridstatus` (CAISO, ERCOT, PJM, MISO live), EIA-930 (hourly fuel mix), HIFLD (transmission topology), NREL PVWatts (solar profiles). Specificity = credibility.
3. **If the form asks "Tech innovation" or "Most novel piece"**, lead with the unscripted self-healing path (anomaly detector → topology healer → tiered router on PJM Loudoun). That's the technical-difficulty winner.
4. **If the form has a character cap shorter than the long description**, cut from the bottom up — the "ask" line and the closing future-paint can be sacrificed before the problem-paint or the agents-are-real line.
5. **Cross-check with `presenter_card.md`** before pasting — same thesis, same vocabulary. If submission text and live pitch use different framing, judges feel it.
