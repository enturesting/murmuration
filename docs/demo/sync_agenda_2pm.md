# 2pm sync agenda — final mad-dash to 5pm submission

> Today, 2026-04-26. Drafted by Nic at ~1pm to make the team sync productive instead of meandering.
>
> Hard truth: **at 5pm we submit.** Anything not done by 4:45 doesn't ship. This page exists so we don't burn the 1hr sync on architecture debate.

---

## 📊 Honest rubric self-score — 73/100  (Nic's read at ~1:45pm)

**B+. Borderline top-3 of 12.** Could be top-3 if other teams land in the 60s, could be top-6 if everyone hits 75+. This score is the fact base for every decision below — if you disagree with the call, push back so we can recalibrate the polish list.

| Dimension (25 max) | Score | Where points come from / where they leak |
|---|:---:|---|
| **Technical Difficulty** | **22 / 25** | 🟢 Live Python agents, anomaly detector, topology healer, tiered router, real ISO data, live narrator. PJM Loudoun is the proof. Loses 3 to "uses existing libraries (FastAPI/Pydantic/networkx)" critique + no benchmarks. |
| **Novelty of Approach** | **19 / 25** | 🟢 Standing envelopes, six orders of magnitude on one schema, cloud-pattern tiered router. Loses 6 to "could be heard as just AI for DR" + no formal first-to-X claim. |
| **Potential National Impact** | **17 / 25** | 🟡 7 ISOs in graph, real archived events, claim hygiene, "no new market rules." Loses 8 to no LOIs, no design partner, demo shows only 2 of 7 ISOs, counterfactuals self-bounded ("softened, not prevented"). |
| **Problem-Solution Fit** | **15 / 25** | 🔴 3-AZ topology, operator language, honest-limit answers. Loses 10 to: **no operator interviews, no design partner, academic-vs-ethnographic framing.** This is the landmine. |

### Realistic delta with time we have

| Scenario | Score |
|---|:---:|
| **Floor** — demo crashes mid-stream OR operator-fit question fumbled | ~70 |
| **Likely** — current trajectory, no further investment | ~75 |
| **Ceiling** — clean rehearsal + operator-fit locked + consumer pillar delivered + acronyms land | ~85 |

### Top-3 improvement levers (prioritized by points-per-effort)

1. **+5–7 to Fit** — Lock decision #4 verbatim. Practice the answer aloud once in rehearsal. **🎯 Stretch goal: if anyone can text or call one grid contact (operator, ISO staff, FERC alum, utility engineer) before 5pm and get a single quote into the submission text, that's worth +2 on its own.** This is the single most leveraged move left on the board.
2. **+3 to Tech Diff** — Two clean dress rehearsals before 4:30. Live demos that crash mid-execution lose 5–10 points instantly. Rehearsal is insurance, not polish.
3. **+3 to Impact** — Watcher checklist: confirm Beat 4's consumer-pillar line ("everyday households become first-class grid participants") *actually got delivered.* Easy to skip when running long. It's free points sitting on the floor.

### What we are deliberately NOT going to improve

- **Tech Difficulty beyond what's there.** Adding more = breaking what works at T-3hr.
- **Novelty by reframing the protocol.** Locked. Ship it as designed.
- **Impact via LOIs / partnerships.** Not feasible by 5pm.
- **Beats 2 and 3 narrative restructure.** Per Nic — those are for the 2pm sync to refine collaboratively, not pre-decide.

---

## ✅ What's already done (don't relitigate)

- Demo runs locally on `dev-cs` at `http://127.0.0.1:8765/` — Python+FastAPI live tick loop, 9 scenarios, 3 UI views.
- `dev-na` branch ported the demo + reference docs and aligned them with `dev-cs` reality. **Open MR: `dev-na → dev-cs`** (docs-only, +1,536 lines, zero code changes).
- Hook line locked (provisional, re-confirm at 2pm): **A** — *"The grid and the AI compute fleet need to start talking. We built the protocol — and the agents that speak it."*
- Submission form text drafted: **`docs/demo/submission_text.md`** — multi-length variants (tagline / 50-word / 250-word / Inspiration / How we built it / Challenges / Accomplishments / What's next / Built with / Links). Owner of submission-form-fill at 4:45 pastes from there.

## 🎯 4 decisions we need to lock by 2:15

1. **Final beat order.** Default proposal: **(1) Texas heat wave → (2) PJM Loudoun substation overload**. Both are dev-cs's strongest scenarios — Loudoun specifically exercises the `TopologyHealer` + tiered `WorkloadRouter` + `AnomalyDetector` (the "self-healing was never scripted" beat). Confirm or swap.
2. **Live ISO data vs cache-only.** Recommend cache-only — fewer demo-day variables. ERCOT live fetch hit SSL issues on Nic's machine; PJM has no API key.
3. **Live narrator (`ANTHROPIC_API_KEY`) vs rule-based fallback.** Recommend rule-based — deterministic output for stage. Live narrator stays a stretch goal if there's time at 4:15. **Tradeoff to name:** rule-based weakens the "Where's the AI?" answer in Q&A — without live narration in the chatter feed, that question relies entirely on agent-class + anomaly-detector + topology-healer evidence. Acceptable but worth pre-deciding.
4. **"Have you talked to grid operators?" answer.** Problem-Solution Fit landmine — that dimension is 25% of the score and the rubric literally asks "do we understand who we're building for?" If a judge asks and we improvise, we bleed. Default proposal: *"We grounded the design in the FERC/NERC Uri joint inquiry, the JLARC Dominion 2024 study, and existing market patterns (CAISO DRAM, PJM Capacity Performance). Operator ground-truth is the first thing in the 12-month pilot plan — that's exactly what the pilot is for."* Confirm verbatim or rewrite.

## ⚙️ Polish list — capped at 3 items, ≤30 min each

Pick 3 max. Anything bigger than 30 min is killed.

**Recommended top 3 (judge-impact ranked):** REAL DATA badge → Cause-effect labels → Legend strip. Reasoning: badge directly inoculates against the "is this fake?" reflex (highest-leverage Tech-Difficulty + Barati move); cause-effect labels carry the story when narration drifts; legend is hygiene. The other two are P2 — only pick them if the top 3 finish under-budget.

| Item | Effort | Owner | Hits | Why it matters |
|---|---|---|---|---|
| REAL DATA pulse badge w/ source URL | ~15 min | TBD | Tech-Diff · Barati | Anti-"is this fake?" — judges click through to FERC/EIA |
| Cause-effect label sweep ("850 MW REROUTED · scheduler shifts work") | ~30 min | TBD | Fit · Both judges | Anti-grid-eye-roll — every label tells story |
| Always-visible legend strip (Stress / Compute / VPP / Protected · Self-heal) | ~25 min | TBD | Fit · McGee | Solves "what do these lines mean" at a glance |
| Click-to-advance flash banner port from nictopia | ~30 min | TBD | Demo control | Pauses tick until presenter dismisses (P2) |
| Per-BA stability gauge (control-room pip score) | ~25 min | TBD | Fit · McGee | Looks pro — but Loudoun beat already exercises this implicitly (P2) |

## 👥 Work-split for 3pm–5pm

Four parallel tracks. Each owner reports done by the listed cutoff or escalates.

| Track | Owner | Done by |
|---|---|---|
| Record 5-min fallback video (clean run, no narration glitches) | TBD | 3:45 |
| Final visual polish (≤3 items above) | TBD | 4:00 |
| Q&A gap-fill in `judge_qa_prep.md` (5 questions — see below) | TBD | 4:00 |
| Presenter rehearsal — 2× full runs with watchers | TBD | 4:30 |
| Fill submission form, paste video link, push final commit | TBD | 4:45 |

**Watcher checklist for rehearsal** (don't just listen — verify):
- Bus shows ~850 MW during Texas-heat-wave migration; if the actual number on screen ≠ what the presenter says, fix one or the other.
- Stopwatch each beat. If Beat 3 runs >2:00 in rehearsal, drop the tier-1/2/3 walk on stage and say "Tier 1 won — sibling AZs had headroom."
- If live narrator is enabled (decision #3), confirm chatter feed is producing fresh sentences and not falling back silently.

**🛑 Hard freeze at 4:45.** No code, no docs, no commits after that. Submit at 4:55. Watch it land at 4:59.

## 📋 Q&A gap-fill — 5 questions currently underdefended (own by 4:00)

Each owner adds an honest answer (~80 words) to `judge_qa_prep.md` with the right judge tag. These are the ones a sharp Grid-track judge is most likely to ask that the current doc can't fully answer.

| Question | Why it matters | Tag |
|---|---|---|
| How is this different from OpenADR 2.0 / IEEE 2030.5? | Both judges likely know these — they're the existing protocols in the DR space. Current "different from DR" answer doesn't reach far enough. | `[Both]` |
| Do you respect transmission / power-flow constraints in the rerouting? | Barati flag — networkx K-shortest is a graph proxy; production grids reroute under DCOPF/ACOPF thermal limits. Honest answer = acknowledged gap. | `[Barati]` |
| Have you talked to grid operators? | Problem-Solution Fit landmine. Same answer as decision #4 — make sure it's written down in the doc, not just memorized. | `[Both]` |
| What's the LLM's failure mode? | "ISO trust" answer is good but doesn't name the failure case. Bad envelope at intake → operator review catches it. Mid-dispatch hallucination is impossible (no LLM in dispatch path). | `[Both]` |
| Why a sim instead of real data? | McGee — disambiguate "ISO data is real (gridstatus + EIA-930), stress conditions are scenario-injected because we can't trigger Uri on demand." | `[McGee]` |

## 🎤 Storytelling angles to lean into (presenter + submission text)

- "Two real Python agents, not a mock." Live narrator + real anomaly detector + real topology healer. Nobody else in the Grid track will have this.
- "Anchored to actual archived events." Texas Uri (Feb 2021), PJM Loudoun (2024). Specificity = credibility.
- "One protocol — six orders of magnitude." Datacenter (GW) and VPP (kW) on the same wire format. That's the thesis.
- "Self-healing was never scripted." Loudoun beat is the proof: AZ drops, sibling AZs absorb, narrator describes it live.

**New for the presenter card (proposed — discuss):**
- **Open with a moment, not abstract paint.** Replace the current 3-sentence Problem Paint with: *"February 16, 2021. 2 AM Central. ERCOT calls EEA3 — four minutes from cascading collapse. 4.5 million customers about to lose power for days. 246 people will die. And in adjacent regions, the AI compute fleet has hundreds of megawatts of headroom — and no way to offer it."* Then zoom out to the systemic claim. Visceral beats logical for the first 15 seconds.
- **Seed the close with one phrase per judge.** Drop these in parallel during Beat 4: McGee → *"no new market rules required"* · Barati → *"every causal step you saw is observable on the bus feed."*
- **Plant one citation visibly during the demo, not just in Q&A.** Even a small `EIA-930 · live` tag next to one number on screen (this is what the REAL DATA badge polish item buys us — call it out by name during Texas beat).

## 🚧 Out of scope for tonight (push back if anyone proposes these)

- New protocol message types
- Refactoring `MurmurationBus`
- Real-time live data fetch beyond what `gridstatus` already does
- Multi-user / auth / hosted deployment
- Counterfactual WITH/WITHOUT toggle (P4 in `todo_list.md` — nice-to-have, not tonight)

---

## Open questions for Shashank specifically

1. Does the **Story tab** walk the right narrative for our 2-scenario arc, or does it need rewiring? (`demo_flow.md` calls it out as a possible close-beat alternative.)
2. Any scenarios in the 9-pack that are dramatically more visual than the 2 we picked, that we should swap in?
3. Branching: dev-na = docs-only forever (option B) or ongoing personal branch with periodic per-feature MRs (option A)? Your repo, your call.
4. Polish ports — happy for me to own 1-2 of them in dev-na, then MR each as its own small PR?
5. **Bus-number consistency** — during the Texas-heat-wave run today, what MW number actually appears on the bus for the migration leg? Presenter card narration says "850 MW." If the live tick produces a different number, we sync narration to the bus, not the other way around.
6. **MURMURATION.md (54 KB) + PITCH.md (8.5 KB) at root** — do those carry national-impact MW math (e.g., "X% of NoVA growth = Y MW peakers avoided") that should propagate into `judge_qa_prep.md`'s Impact answers? Currently the scaling story is qualitative; one quantified line would buy us real ground on the Impact dimension.
