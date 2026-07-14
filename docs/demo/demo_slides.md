# Demo slides — markdown mirror

> VSCode-readable mirror of `demo_slides.html`. The HTML is the canonical version for stage (Reveal.js, fullscreen). This file is for editing comfort and review. Keep them in sync if you change one.
>
> **4 slides total. Slide 4 is dual-purpose: lead into live demo AND close.**
>
> Built against the dev-cs codebase — slide content reflects the live-agent + topology-healer + tiered-router architecture.

---

## Slide 1 · Title  (~10s on screen, max)

**Visuals:**
- Murmuration logo (image at `docs/demo/murmuration_logo.png`) — large, centered
- Team: Nick · Rohan · Shashank · Teddy
- "SCSP Hackathon · Electric Grid Optimization" tag at bottom

**Spoken:** Hook A (locked) delivered over this slide:
> "The grid and the AI compute fleet need to start talking. We built the protocol — and the agents that speak it."

Plus names + SCSP track. Don't linger.

---

## Slide 2 · Problem  (~18s spoken — Beat 1 problem paint)

> # The grid is breaking more often, with higher stakes.

- Heat waves · polar vortexes · line trips · **Asheville floods · Maui fires · California wildfires**
- The operator at 2 AM has three tools: **peakers · curtailment · brownouts**. Each one costs more than the last.
- Meanwhile **billions of dollars of flexibility sit idle** when stress hits — no common language fast enough to coordinate.

**Spoken delivery notes:**
- Three fragments mirror three spoken sentences — speak as scenes, not bullets
- After third fragment: brief pause + acknowledgment ("I've probably missed ones that hit closer to home for some of you.")

---

## Slide 3 · How we're solving it  (~25s — Beat 1 "what we built" + hook)

> # The wire format for the flexible energy fleet.

**The protocol** — Bilateral wire format · 7 message types · 2 live Python agents · standing envelopes negotiated in seconds.

**Predictive models on top** — Load forecasting · real-time anomaly detection · live awareness of where compute capacity is available.

**AI is the load — and the solution** — Same compute fleet creating grid pressure can relieve it · published as a standing offer the grid calls on in milliseconds.

**Spoken delivery notes:**
- Headline IS the memorable phrase ("wire format for the flexible energy fleet") — judges quote it
- After the three blocks, deliver the democratization paragraph verbally ("the door this opens — everyday households join a virtual power plant... reserves of the future aren't just peaker plants. They're neighborhoods.")
- Then advance to slide 4 as the bridge into the live demo

---

## Slide 4 · Watch it work — close + live demo bridge  (DUAL PURPOSE)

> # Watch it work.

*2 real-world scenarios · 2 live Python agents · anchored to actual archived events*

> ### "The reserves of the future aren't just peaker plants. *They're neighborhoods.*"

**PILOT ASK · 1 ISO · 1 HYPERSCALER · 1 VPP · 12 MONTHS · NO NEW MARKET RULES**

**Questions?**

**Dual-purpose use:**
- **BEFORE the live demo:** Presenter says "Watch it work" → switches to live app at `http://127.0.0.1:8765/` (3D Globe tab). The sticky neighborhoods line is on screen but not emphasized yet — it's the line you've pre-loaded.
- **AFTER the live demo:** Presenter returns to this slide (in Reveal: press `b` to blackout while switching, then return). Now emphasize the sticky line, hit the pilot ask, end on "Questions?"
- **If the demo crashes mid-stream:** This slide is the fallback close. Can pivot here at any time.

---

## How to use the slides on stage

| Reveal key | Action |
|---|---|
| `→` / `space` | Next slide |
| `←` | Previous slide |
| `b` | Blackout (use to hide the deck while switching to live app) |
| `s` | Speaker notes window (notes are on every slide) |
| `f` | Fullscreen |
| `o` | Overview / grid view |

---

## On the title slide image

The logo file should be saved at `docs/demo/murmuration_logo.png`. If it's not there, the title slide will show alt text instead of the image — still functional, just less branded.

If you want to use a different image or skip the image entirely, edit the `<img>` tag in the title-slide `<section>` of `demo_slides.html`.

---

## Why 4 slides instead of the previous 1

- The single-slide approach overflowed on lower-resolution displays (too much content crammed into one)
- 4 slides spreads the load — nothing overflows, every slide has a clear job
- Slide 4 doing dual duty (demo bridge + close) keeps the count low
- The arc preview slide (NEED → DISPATCH → SELF-HEAL → PROTECT) was deliberately cut — that content lives in the live demo itself, no need to pre-show it

---

## Cross-references

- Live presenter script: `presenter_card.md` (this is where the spoken text lives)
- Full demo flow: `demo_flow.md`
- Q&A defenses: `judge_qa_prep.md`
