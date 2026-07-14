# Demo prep TODOs — pre-Sunday-5pm  (dev-na working list)

> Working list for `dev-na` (off `dev-cs`) — judge-comprehension polish + final demo prep. Claim or skip; don't double-up. Cross items off as they ship.
>
> Last reset: 2026-04-26 — fresh after switching base from `feature/nictopia` to `dev-cs`.
>
> The `dev-cs` codebase is **architecturally complete** (live agents, anomaly detector, topology healer, tiered router, 9 scenarios, real ISO data). What remains is **judge-comprehension polish + demo logistics**.

---

## P0 · ship before stage  (must-do)

These are the items without which the demo is at unacceptable risk.

- [ ] **Record fallback video** — pre-record a clean 5-min run of `dev-cs` per `demo_flow.md`. Save as `docs/demo/backup_video.mp4`. Hard rule: no live demo without a fallback recording.
- [ ] **Lock the hook line** (A or B in `demo_slides.md`) so the presenter can rehearse.
- [ ] **Run the demo end-to-end at least twice** with the live tick loop to catch any pacing/visual surprises.
- [ ] **Decide on live ISO data vs cache-only** for stage. Recommend cache-only — fewer moving parts.
- [ ] **Set `.env` for stage** — at minimum decide whether `ANTHROPIC_API_KEY` is set (live narrator vs rule-based fallback).
- [ ] **Confirm demo machine** — which laptop, which display, projector compatibility tested.

## P1 · judge-comprehension polish  (high-value, finite effort)

These lift directly from `feature/nictopia` and address the "judges can't follow at a glance" problem nictopia solved.

- [ ] **Click-to-advance flash banner pattern** — port the `FlashBanner` UX from nictopia to dev-cs's vanilla-JS UI. Per-phase center-screen narrative banner that pauses the auto-tick until the presenter dismisses. Major demo-control improvement. ~30 min.
- [ ] **Always-visible legend strip** at top-center of map (Stress / Compute / VPP / Protected · Self-heal). Pulses when the corresponding flow is active. Solves "what do these lines mean." ~25 min.
- [ ] **Per-BA stability gauge** at top-left — pip-score visual. Looks like a control-room monitor. dev-cs has BA cards but not a compact at-a-glance stress gauge. ~25 min.
- [ ] **REAL DATA pulse badge** on each scenario citing the anchor incident with a clickable source URL. ~15 min.
- [ ] **Cause-effect labels** — sweep the UI strings to read "850 MW REROUTED · scheduler shifts work" not "850 MW transferred." Anti-grid-eye-roll. ~30 min.

## P2 · scenario iteration  (where we differentiate further)

The team flagged these as wanted features. dev-cs already has the engine to support them — we adjust scenario data + UI to surface them better.

- [ ] **Make "Engage VPP" decision smarter** — the `WorkloadRouter` already does this in code (Tier 1 sibling-AZ before Tier 2 cross-region). Currently the visual doesn't make this clear. Add a UI annotation that says "VPP local relief sufficient — no cross-region migration needed" when Tier 1 succeeds.
- [ ] **Highlight self-healing more prominently** — the PJM Loudoun scenario already exercises the `TopologyHealer` and tiered router. Add a flash banner that explicitly says "✓ AZ failed · sibling AZs absorbed load · no SLA hit · no cross-region migration."
- [ ] **Add or surface a "carbon arbitrage" scenario beat** — dev-cs has it, but it doesn't pop visually. A green/dirty side-by-side comparison would land it.

## P3 · narrative + rubric coverage  (close gaps in pitch story)

- [ ] **Update `judge_qa_prep.md`** — there's still a couple of items pointing at nictopia-specific files. Sweep for `caiso_duck_2024_04_15.json` and similar — they exist in dev-cs's structure differently.
- [ ] **Generate Story-tab content** — dev-cs has a 3rd UI view ("Story") which is a presentation-grade walkthrough. Verify it actually tells the right narrative for our 2-scenario demo arc.
- [ ] **Pre-flight `ANTHROPIC_API_KEY`** — if we're running with the live narrator, generate ~10 sample outputs ahead of time so we know what voice/length to expect. If rule-based fallback is on, no prep needed.

## P4 · nice-to-have polish  (skip unless P0–P2 done)

- [ ] **Counterfactual side-by-side** — dev-cs doesn't have a built-in WITH/WITHOUT toggle. Could add a comparison panel for the closing beat. ~1 hr.
- [ ] **Outcome-summary panel after scenario completion** — port from nictopia's `OutcomePanel` concept. "Houston hospitals stayed online · 4.5M people kept power · 0 SLA breaches." Climactic close. ~1 hr.
- [ ] **NREL solar profile sparklines** in the duck-curve scenario beat — dev-cs has the data, just isn't rendering it inline.

## P5 · post-demo  (out of scope for tonight)

- [ ] Replace the deterministic playback with a real workload scheduler integration.
- [ ] Add a real signing / cert layer for the bus.
- [ ] Continental scaling story for Phase 2 (May 9).
- [ ] Production deployment story.

---

## Things explicitly out of scope before stage

- Real-time live data fetch beyond what `gridstatus` already does (offline-safe rule from `electric_travel.md` is non-negotiable).
- Multi-user / auth / backend-beyond-fastapi.
- Actual deployment to a hosted URL (judges run it locally per the README).
- New components in the bus protocol schema beyond what `protocol/messages.py` already declares.
- Refactoring the `MurmurationBus` for performance — it's plenty fast for the demo.

---

## Owner / status

| Item | Owner | Status |
|---|---|---|
| Record fallback video | TBD | not started |
| Lock hook line | TBD | not started |
| End-to-end runs (2×) | TBD | not started |
| Live ISO vs cache decision | team | needs sync |
| `.env` setup for stage | TBD | not started |
| Demo machine confirmation | TBD | not started |
| Click-to-advance flash banner port | TBD | not started |
| Legend strip | TBD | not started |
| Stability gauge | TBD | not started |
| REAL DATA badge | TBD | not started |
| Cause-effect label sweep | TBD | not started |

Update this table as the team divides work in the next sync.
