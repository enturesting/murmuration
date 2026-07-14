# Judging criteria — cheat sheet

> One-page reference for stage. Maps the SCSP rubric (4 × 25%) and the two grid-track judges (McGee, Barati) onto the beats of `demo_flow.md` and the answers in `judge_qa_prep.md`.
>
> Built against the **dev-cs / dev-na** codebase: live Python tick loop, real EIA-930 + gridstatus.io data, two real Claude-narrated agents, anomaly detector, topology healer, tiered workload router, 9 scenarios.
>
> Use this when (a) deciding what to emphasize live, (b) answering "which rubric dimension is your strongest?" and (c) sanity-checking that every beat is earning at least one rubric point.

---

## The rubric

| Dimension | Weight | What it really asks |
|---|---|---|
| **Novelty of Approach** | 25% | Did we challenge convention or just rebuild it? |
| **Technical Difficulty** | 25% | Is this beyond off-the-shelf? |
| **Potential National Impact** | 25% | Could this scale and matter at country-scale? |
| **Problem-Solution Fit** | 25% | Do we actually understand the user, and does the build address their real need? |

---

## Where each dimension is won (and lost)

### Novelty (25%)
- **Won by:** the *standing envelope* framing. Existing DR is per-event, per-program, phone-tree. Envelopes are standing, bilateral, telemetric, schema-identical at every scale (200 MW DC ↔ 5 kW home battery, same `FlexibilityEnvelope`).
- **Won by:** the **tiered workload router** that escalates intra-region (sub-ms) → cross-region (~45 ms) → throttle-in-place. Real ops choose the cheapest tier that works; existing DR programs only do "shed or don't."
- **Lost by:** sounding like "AI optimizes demand response" — that's a thousand startups. Be specific that the contribution is a *protocol*, a *wire format*, plus the *negotiation discipline* on top.
- **Stage line:** "One schema, every scale. 200 MW data center to 5 kW home battery, same envelope. And one tiered router that knows the difference between a sibling-AZ failover and a transcontinental migration."

### Technical Difficulty (25%) — STRONG SUIT WITH DEV-CS
- **Won by:** showing the **bilateral bus + telemetric ack + live narrator** during dispatch. The narrator runs Claude Haiku 4.5 with a rule-based fallback. Real EIA-930 + gridstatus.io data behind the numbers. CO₂ math from EPA eGRID factors.
- **Won by:** the **anomaly detector** (rolling z-score per BA, auto-fires `ContingencyAlert` on >4σ). The protocol responds to *unplanned* events, not just scripted ones.
- **Won by:** the **topology healer** (networkx K-shortest paths around failed edges, publishes `TopologyReconfigure`). Self-healing grid in code, not slides.
- **Won by:** the **tiered router** picking the right escalation level per workload class (training/batch_infer/online_serve/fine_tune/embedding all behave differently under throttle).
- **Lost by:** the deterministic-playback critique. **Pre-empt by naming where the LLM lives:** the narrator generates the operator's voice live, and the agents (`GridAgent`, `ComputeAgent`) are real Python classes, not scripted JSON.
- **Stage line:** "These numbers come from real CAISO load + EIA-930 fuel mix. The fetch happens live. The anomaly detector you just saw is a z-score watchdog on every BA stream."

### Potential National Impact (25%)
- **Won by:** anchoring each scenario to a real incident with measurable consequence. Uri (246 deaths, $130B). PJM-DOM substation congestion (Dominion 2024 moratorium). Polar vortex cascade across multiple ISOs. Duck curve (~800 GWh curtailed/yr in CAISO).
- **Won by:** showing the protocol works across **7 ISOs** simultaneously (CAISO/ERCOT/PJM/MISO/NYISO/ISO-NE/SPP all present in the live data and topology graph).
- **Lost by:** absolutist claims ("would have prevented Uri"). Use **"would have softened"** / **"X% of"**. Honest concession is more credible than bravado.
- **Stage line:** "We don't claim to prevent these. We claim a measurable supplement that costs zero new generation."

### Problem-Solution Fit (25%)
- **Won by:** speaking the language of the people who'd actually deploy this. Operator personas, dispatch timing, settlement, fallback when an envelope under-delivers. This is **the McGee + Barati battle** (see below).
- **Won by:** the **3-AZ-per-region topology** (`DC-CA-1a/1b/1c`, etc.) — judges who've worked at hyperscalers will recognize the AWS region-as-3-AZs pattern immediately. Routing within sibling AZs first is exactly how cloud schedulers actually work.
- **Lost by:** abstract "AI agent coordinates everything" framing with no operational grounding.
- **Stage line:** "Today the operator's tools are peakers, curtailment, and brownouts. We add a fourth: bilateral standing envelopes with tiered workload routing."

---

## Reading the judges

### Monty McGee — operational realism
- **What he wants:** "could this run in a control room tomorrow?" Cares about dispatch timing, capacity limits, transmission, failure modes, regulatory reality.
- **Frame answers as:** "An operator sees X on their screen → emits Y → gets ack in Z seconds → falls back to W if delivery is short."
- **Strongest demo moments for him:**
  - The sub-2s dispatch claim during the **PJM line-trip contingency** (the topology healer publishing `TopologyReconfigure` while the compute agent fires its pre-authorized envelope)
  - The **PJM Loudoun substation overload** scenario — DC-VA-1a goes dark, sibling AZs (DC-VA-1b Sterling, DC-VA-1c Manassas) absorb the load via the tiered router. *Real intra-region failover, on-screen.*
  - The bilateral framing as an existing FERC/NERC-compatible pattern (DR Auction Mechanism, Capacity Performance precedents)
  - The explicit fallback story (envelope shortfall → ISO sees telemetry deficit → falls back to existing DR/peakers, "strictly additive")
- **Avoid:** "AI optimizes everything" / "the agent decides." He hears that as hand-waving.

### Dr. Masoud Barati — model correctness
- **What he wants:** "is the simplified model valid?" Cares about cause→effect, feedback loops, what's simulated vs. real, measurable system response.
- **Frame answers as:** "Demand spike → headroom drop → envelope dispatch → frequency held → settlement at envelope rate." A clean causal chain.
- **Strongest demo moments for him:**
  - **CAISO surplus solar** scenario showing bidirectional system dynamics (compute leans IN at negative LMP, then VPP shaves the evening ramp)
  - The **anomaly detector firing in real time** — z-score on a real EIA-930 stream, no scripting
  - The **load forecaster** (`GradientBoostingRegressor`) feeding the GridAgent's dispatch threshold logic — observable cause of agent action
  - The volunteered limits in the `judge_qa_prep.md` "honest-limit questions" section (no Hz/VAR modeling, etc.)
- **Avoid:** opaque numbers without provenance. He'll ask for the citation; have it ready (see `judge_qa_prep.md` data-integrity section).

### Both judges, in one sentence
> Look like a grid control system (McGee). Behave like a valid simplified power system (Barati). Show clear before/after improvement (both). Be understandable in under 2–3 minutes (both).

---

## Beat → rubric coverage check

If any rubric dimension has zero coverage, fix the demo, not the rubric.

| Beat | Novelty | Tech Diff | Impact | Fit |
|---|:---:|:---:|:---:|:---:|
| Cold open slide | ✓ (name the protocol) | — | ✓ (state the stakes) | ✓ (name the user) |
| Texas heat wave (Uri-anchored) | ✓ (envelope on stage) | ✓ (live bus + narrator visible) | ✓ (Uri anchor) | ✓ (operator language) |
| PJM Loudoun self-healing | ✓ (tiered router + healer) | ✓✓ (anomaly detector + topology graph) | ✓ (NoVA real growth) | ✓ (3-AZ topology = real ops) |
| Live close | — | ✓ (live narrator generates close text) | ✓ (pilot ask) | ✓ (CTA = real users) |

Every column has at least two ✓. The PJM Loudoun beat carries the heaviest Tech Difficulty load — don't cut it without recomposing.

If we recover stage time and want a third scenario, queue **CAISO surplus solar** (Barati-aligned: bidirectional, feedback loops, carbon math).

---

## If a judge asks "which dimension is your strongest?"

> "Honestly — Technical Difficulty, because we built three real agentic systems instead of one optimizer: the bilateral protocol bus, the tiered workload router, and the topology healer with anomaly detection. Problem-Solution Fit is close behind because we modeled the 3-AZ-per-region topology that hyperscalers actually use. Novelty is the standing-envelope schema being the same at six orders of magnitude. Impact is the easiest to claim and the hardest to prove in five minutes."

This is honest, accurate, and steers them toward the dimensions where dev-cs has the strongest evidence.

---

## What changed from the nictopia-era version of this doc

For team awareness — context drift to be aware of:
- **Tech Difficulty** is now the *strongest* leg (was the weakest under nictopia's frontend-only model). dev-cs has live agents, anomaly detector, topology healer, real ISO data, Claude narrator.
- **The "Where's the AI?" killer question** has a much stronger answer (live narrator + real agent classes, not just pre-scripted phases).
- **Beat lineup** is now Texas heat wave + PJM Loudoun self-healing (was ERCOT + Duck Curve). PJM Loudoun is the standout dev-cs differentiator that nictopia couldn't show.
- **WITH/WITHOUT toggle** is no longer a built-in UI affordance; counterfactual is now spoken during each beat (or shown in the Story view if we use it).
