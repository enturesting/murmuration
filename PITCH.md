# Murmuration · 10-slide pitch deck

Just words and structure. Build the design pass after dry-running.
Each slide has speaker notes (italics) and what to actually show.

---

## Slide 1 — Title + thesis

**MURMURATION**
*The protocol AI infrastructure and the electric grid should speak.*

> Team Murmuration · SF/Boston/DC · Grid-Aware AI Agents track

*Speaker note (10s):* "Today AI hyperscalers and the electric grid don't talk. We're going to show you why that's the bottleneck for both decarbonization and AI growth — and a working protocol that fixes it."

---

## Slide 2 — The structural problem

**Two isolated planning systems. Three broken horizons.**

| Horizon | Hyperscaler decides | ISO decides | Today's gap |
|---|---|---|---|
| Routing (sec–min) | Where this job runs | Which BAs are stressed | Routing is grid-blind |
| Provisioning (hours–days) | Tomorrow's queue placement | How much reserve to commit | Forecasts don't cross over |
| Planning (months–years) | Where to build next GW | Which interconnects to approve | Multi-year backlogs, no flexibility credit |

*Speaker note (30s):* "Hyperscalers plan capacity 5–15 years out, sign PPAs, increasingly bypass the grid because the interface is too slow. ISOs run interconnection studies on padded nameplate numbers. Both lose."

---

## Slide 3 — What exists, what's missing

| Solution | What it does | Why it falls short |
|---|---|---|
| OpenADR 2.0/3.0 | Utility → building DR signals | Building-shaped, slow cadence, near-zero hyperscaler adoption |
| ERCOT CLR | Custom industrial-load market | Texas-only, manual onboarding |
| Google Carbon-Intelligent Computing | Internal time/space shift | One-way, closed, not a protocol |
| Lancium / Crusoe | Purpose-built flexible DCs | Bespoke per facility, no standard |

*Speaker note (30s):* "Every existing solution is one-way, single-vendor, or built for buildings. The bidirectional, real-time, AI-shaped protocol that's needed does not exist."

---

## Slide 4 — Murmuration

**Three things, one demo:**

1. A **bidirectional protocol** — 7 message types, semantically AI-shaped
2. **Two Claude agents** — one ISO-side, one hyperscaler-side, negotiating in real time
3. **Two reference clients** that prove it works at both extremes:
   - **#1 Hyperscaler Compute Fleet** — 3 data centers (200 MW each), CAISO/ERCOT/PJM
   - **#2 Residential VPP** — 100 homes (5 kW each), SF Bay Area
   - *Six orders of magnitude apart, identical envelope schema.*

*Speaker note (45s):* "The protocol is the thesis. The two flagship clients are the proof. Same `FlexibilityEnvelope` schema works for a 500 MW data center and a 5 kW home battery without modification — that's how we know we built infrastructure, not a point solution."

*Show:* simple architecture diagram from MURMURATION.md §2.2.

---

## Slide 5 — Live demo Act I: Texas heat wave

*Switch to the live globe.* Click "Texas heat wave."

What judges see in 90 seconds:
- ERCOT marker turns red, LMP spikes to $410, stress score 1.0.
- Grid agent issues a `DispatchRequest` (animated arc, ERCOT → DC-TX-1).
- Compute agent acks within the standing envelope (-125 MW × 90 min).
- DC-TX-1 gauge slides from 217 MW down to its 50 MW serving floor (5 jobs paused).
- A second cyan arc fires from DC-TX-1 to DC-CA-North (workload conceptually shifting).
- Counters tick: $X paid, X tCO₂ avoided, **0 SLA breaches**.

*Speaker note (15s):* "That's #1 — single-agent dispatch on the routing horizon. One BA, one DC, sub-15-second response."

---

## Slide 6 — Live demo Act II: Surplus solar / VPP lights up

*Click "CAISO surplus solar."*

What changes:
- CAISO marker turns green, LMP drops to $4, carbon to 18 g/kWh.
- Grid agent issues a *lean-in* dispatch — opposite of throttle.
- DC-CA-North picks up extra training (+28 MW).
- **VPP-CA-Bay homes light up** — green dots scatter across the Bay Area as batteries discharge to soak surplus that would have been curtailed.
- Counter ticks: lean-in MW·min, carbon delta, "X homes responding."

*Speaker note (30s):* "Same protocol, opposite direction, two completely different asset classes responding. That's #2 — the VPP. 100 homes acting through the same envelope schema as a 200 MW data center. Six orders of magnitude. Zero schema changes."

---

## Slide 7 — Live demo Act III: Sub-second contingency

*Click "PJM line trip · contingency."*

What happens:
- PJM marker pulses bright magenta — `ContingencyAlert` published on the bus.
- Compute agent's pre-authorized fast path fires immediately. **No DispatchRequest cycle, no Claude call.**
- DC-VA-1 drops 30% of its training load in **<2 milliseconds** of bus latency.
- Magenta arcs animate ISO → DC instantaneously.
- Metric tile updates: `CTGY RESPONSE: 0.3 ms` (or whatever measured).

*Speaker note (45s):* "GPU clusters can drop 30% of their power in under 2 seconds — faster than batteries, far faster than gas turbines. ERCOT's Fast Frequency Response market would buy this today if anyone offered it. This is the angle that's unique to AI loads. Nobody else can do this."

---

## Slide 8 — How the architecture stays sane

**The seam: one `FlexibleAsset` interface. Same protocol message catalog above it.**

```
              Claude Agent (ISO ops)  ⇄  Murmuration Bus  ⇄  Claude Agent (DC fleet)
                                                                     │
                              ┌──────────────────────────────────────┴──┐
                              │              FlexibleAsset                │
                              └──────┬─────────┬─────────┬────────────────┘
                                  DataCenter  HomeBattery  EV  Thermostat ...
                                  (200 MW)    (5 kW)
```

Two design moves prevent bottlenecks:
- **Commit/dispatch separation** — envelope refresh is async (5 min); dispatch within envelope is auto-honored. Claude is on the negotiation path, *not* on the dispatch path.
- **Telemetry-based settlement** — opaque payloads protect commercial sensitivity; metered response is the source of truth.

*Speaker note (45s):* "If Claude is slow, dispatch is still fast. If the bus dies, both sides degrade gracefully against last-known state. The protocol is built to never become the bottleneck."

---

## Slide 9 — The stakeholder map (no zero-sum)

| Stakeholder | Captures | Magnitude |
|---|---|---|
| Hyperscaler | DR + capacity + curtailment + frequency-response revenue, faster interconnect | 8–20% energy opex cut, 5–15% Scope 2 cut, $10M+/yr per GW |
| ISO/RTO | Real-time visibility, effective capacity, peaker displacement | Avoid $50–100M peaker capex per stress region |
| Renewable developers | Less curtailment, better PPA economics | 100s of GWh/yr soaked instead of curtailed |
| Ratepayers | Lower socialized capex, fewer blackouts | Indirect; meaningful at scale |
| Climate / regulators | Demonstrable Scope 2 reductions, faster transition | Scope 2 cut, fossil capacity avoided |

*Speaker note (30s):* "Every stakeholder's incentive points the same direction. The protocol is durable because nobody loses."

---

## Slide 10 — What's next

**On a working protocol:**

1. **Real ISO market participation** — wire up ERCOT CLR + PJM capacity auction integrations
2. **OpenADR 3.0 transport binding** — ride the existing standard's wire protocol; layer Murmuration's semantics on top
3. **Interconnection-priority unlock** — flexibility-weighted queue prioritization (ISO/FERC rule work, ~3yr)
4. **Pilot deployment** — one hyperscaler campus + one ISO + one regulator

*Speaker note (30s):* "We didn't just build a demo. We built the protocol that makes the next decade of AI-grid integration tractable. The same architecture that flattens a Texas heat wave today scales to gigawatt-class deployments tomorrow. We're ready to pilot."

**Q&A.**

---

## Closing notes for whoever reads this on dry-run day

- Slide 5/6/7 are the live demo. Practice the click-cadence so each Act is ~90 seconds.
- Have fallback videos pre-recorded for each Act in case the network or Claude API hiccups.
- Memorize the two stats: "200 MW down to 50 MW serving floor in 90 sec" + "0.3 ms contingency response."
- For Q&A, the "Anticipated Q&A" table in MURMURATION.md §14.3 has the seven questions judges actually ask.
