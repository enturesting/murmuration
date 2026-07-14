# Murmuration Branch Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all hackathon work (flagship Python system, nictopia React demo, agentic_workflow prototype, docs) onto `feature/consolidation`, verify each app runs from a fresh clone, then merge to `dev` and open a PR to `main`.

**Architecture:** Additive git consolidation — `feature/consolidation` branches off `dev-na`, restores `feature/nictopia` under `nictopia/`, merges `origin/dev` (`--allow-unrelated-histories`, tree union), then layers cleanup + a reviewer-facing root README on top. No history rewrite, no deletions beyond named junk files.

**Tech Stack:** git/gh CLI, Python 3.12 + FastAPI (flagship), React 19 + Vite + TS (nictopia), pandas/pyarrow (agentic_workflow), Reveal.js (slides), headless Chrome (screenshots).

**Spec:** `docs/superpowers/specs/2026-07-13-branch-consolidation-design.md`

## Global Constraints

- **No history rewrite, no force-push.** The `.venv` blob purge is explicitly out of scope until after July 15.
- **Additive:** never delete teammate content except the junk named in Task 3 (`.DS_Store`, `agentic_workflow/__pycache__/`).
- **Zero-keys truth:** every "runs without API keys" claim in the README must match a verification step in Task 6.
- **Deadline:** `main` must be reviewer-ready before end of day July 15, 2026.
- **Working dir:** `/Users/nic/dev/murmuration`. Current branch `dev-na` (tip: spec commit a162cd34). Working tree has EXACTLY these uncommitted files, consumed by Task 1: modified `docs/demo/demo_slides.{md,html}`, untracked `docs/demo/final_polish.md`, `docs/demo/murmuration_logo.png`.
- All `git`/file commands run from the repo root unless a `cd` is shown.

---

### Task 1: Feature branch + finish and commit the slide deck

**Files:**
- Modify: `docs/demo/demo_slides.html` (add missing Problem slide, slide-3 body text, slide-4 heading/subtitle/ask)
- Modify: `docs/demo/demo_slides.md:92` (stale line-number reference)
- Add (already in working tree): `docs/demo/murmuration_logo.png`, `docs/demo/final_polish.md`

**Interfaces:**
- Produces: branch `feature/consolidation` containing a 4-slide deck whose `<section>` count matches the md mirror. Tasks 2–7 all build on this branch.

- [ ] **Step 1: Create the branch**

```bash
git checkout -b feature/consolidation
```

- [ ] **Step 2: Add the missing CSS for the Problem slide**

In `docs/demo/demo_slides.html`, after the `/* slide 1 — title */` CSS block (ends line 30), insert:

```css
        /* slide 2 — problem */
        .reveal .problem-list { list-style: none; margin: 1.2rem auto 0; max-width: 90%; }
        .reveal .problem-list li { font-size: 0.62em; line-height: 1.45; text-align: left; margin-bottom: 0.9rem; padding-left: 1rem; border-left: 3px solid var(--warn); }
        .reveal .problem-list li b { color: var(--warn); }
```

- [ ] **Step 3: Insert the Problem slide**

Between the closing `</section>` of SLIDE 1 (line 71) and the `<!-- ============ SLIDE 3` comment, insert (content verbatim from `demo_slides.md` Slide 2):

```html
        <!-- ============ SLIDE 2 · PROBLEM ============ -->
        <section class="problem-slide">
            <h2>The grid is breaking more often, with higher stakes.</h2>

            <ul class="problem-list">
                <li class="fragment">Heat waves · polar vortexes · line trips · <b>Asheville floods · Maui fires · California wildfires</b></li>
                <li class="fragment">The operator at 2 AM has three tools: <b>peakers · curtailment · brownouts</b>. Each one costs more than the last.</li>
                <li class="fragment">Meanwhile <b>billions of dollars of flexibility sit idle</b> when stress hits — no common language fast enough to coordinate.</li>
            </ul>

            <aside class="notes">
                Slide 2 — PROBLEM (~18s, Beat 1 problem paint). Three fragments mirror three spoken sentences — speak as scenes, not bullets.
                After third fragment: brief pause + acknowledgment ("I've probably missed ones that hit closer to home for some of you.")
            </aside>
        </section>
```

- [ ] **Step 4: Fill the slide-3 solution blocks**

Replace the three header-only divs (lines 78–80 pre-insert) with (body text verbatim from `demo_slides.md` Slide 3; `<b>` is `display:block` so body text flows beneath the header):

```html
                <div><b>The protocol</b>Bilateral wire format · 7 message types · 2 live Python agents · standing envelopes negotiated in seconds.</div>
                <div><b>Predictive models on top</b>Load forecasting · real-time anomaly detection · live awareness of where compute capacity is available.</div>
                <div><b>AI is the load — and the solution</b>Same compute fleet creating grid pressure can relieve it · published as a standing offer the grid calls on in milliseconds.</div>
```

- [ ] **Step 5: Complete slide 4**

In the `close-slide` section, insert before the `.sticky` paragraph:

```html
            <h2>Watch it work.</h2>
            <h3>2 real-world scenarios · 2 live Python agents · anchored to actual archived events</h3>
```

and insert between the `.sticky` paragraph and the `.questions` paragraph:

```html
            <p class="ask">PILOT ASK · 1 ISO · 1 HYPERSCALER · 1 VPP · 12 MONTHS · NO NEW MARKET RULES</p>
```

- [ ] **Step 6: Fix the stale line reference in the md mirror**

In `docs/demo/demo_slides.md` line 92, replace:

```
If you want to use a different image or skip the image entirely, edit the `<img>` tag in `demo_slides.html` line 53.
```

with:

```
If you want to use a different image or skip the image entirely, edit the `<img>` tag in the title-slide `<section>` of `demo_slides.html`.
```

- [ ] **Step 7: Verify deck structure matches the mirror**

```bash
grep -c "<section" docs/demo/demo_slides.html   # Expected: 4
grep -c 'class="ask"' docs/demo/demo_slides.html # Expected: 1
grep -n "Watch it work" docs/demo/demo_slides.html # Expected: 1 hit inside the close-slide h2
```

- [ ] **Step 8: Commit**

```bash
git add docs/demo/demo_slides.html docs/demo/demo_slides.md docs/demo/murmuration_logo.png docs/demo/final_polish.md
git commit -m "docs: finish 4-slide deck to match md mirror; commit logo + final polish notes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git status --short   # Expected: empty
```

---

### Task 2: Restore nictopia under `nictopia/` + reference docs

**Files:**
- Create: `nictopia/**` (from `feature/nictopia` tip fabc1345, minus `docs/` and `.gitignore`)
- Create: `docs/reference/shashank_branch_review.md`, `docs/reference/what_is_nictopia.md`
- Modify: `nictopia/README.md` (prepend provenance note), `.gitignore` (fold nictopia patterns)

**Interfaces:**
- Consumes: branch from Task 1.
- Produces: `nictopia/` app that Task 6 builds with `npm ci && npm run build`; reference docs the Task 5 README links to.

- [ ] **Step 1: Extract the branch tree into `nictopia/`**

```bash
mkdir nictopia
git archive feature/nictopia | tar -x -C nictopia
rm -rf nictopia/docs          # root docs/ is the evolved version of these
```

- [ ] **Step 2: Fold its .gitignore into root, then remove it**

```bash
cat nictopia/.gitignore       # inspect
```

Append to the ROOT `.gitignore` any pattern from that file not already covered (root already has `node_modules`, `.DS_Store`, `.env`). Expect to add roughly:

```gitignore

# nictopia (Vite)
nictopia/dist/
*.local
```

Then:

```bash
rm nictopia/.gitignore
```

- [ ] **Step 3: Restore the two reference docs to root docs/**

```bash
git show feature/nictopia:docs/reference/shashank_branch_review.md > docs/reference/shashank_branch_review.md
git show feature/nictopia:docs/reference/what_is_nictopia.md > docs/reference/what_is_nictopia.md
```

- [ ] **Step 4: Prepend the provenance note to `nictopia/README.md`**

Insert at the very top, above the existing first heading:

```markdown
> **Where this fits:** `nictopia/` is the standalone React + Vite visual demo built in parallel with
> the flagship Python system during the hackathon. The team compared both implementations in
> [`docs/reference/shashank_branch_review.md`](../docs/reference/shashank_branch_review.md) and chose
> the Python package ([`murmuration/`](../murmuration/)) as the primary stage demo. This app remains
> the fastest way to see the idea: `npm install && npm run dev` — no backend, no API keys, all data
> served from committed caches of real archived grid incidents.

```

- [ ] **Step 5: Verify and commit**

```bash
ls nictopia/src/components/GlobeView.tsx nictopia/public/cache/historical/ercot_uri_2021_02_16.json  # both exist
test ! -e nictopia/docs && test ! -e nictopia/.gitignore && echo OK   # Expected: OK
git add -A
git status --short | grep -v "^A" | head   # Expected: no unexpected modifications outside nictopia/, docs/reference/, .gitignore
git commit -m "feat: restore nictopia React demo under nictopia/ + branch-review reference docs

Restored from feature/nictopia (fabc1345), excluding its docs/ subtree
(root docs/ is the evolved version). shashank_branch_review.md and
what_is_nictopia.md restored to docs/reference/ — they document the
two-implementation comparison and the decision to stage the Python demo.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Merge `origin/dev` and remove committed junk

**Files:**
- Merge in: `agentic_workflow/**`, root `.DS_Store` (from origin/dev)
- Delete: `.DS_Store`, `agentic_workflow/__pycache__/`

**Interfaces:**
- Consumes: branch from Task 2.
- Produces: `agentic_workflow/` present at repo root for Tasks 4–6.

- [ ] **Step 1: Re-fetch and confirm the remote tip (origin/dev was force-pushed around event day)**

```bash
git fetch origin
git log --oneline -1 origin/dev   # Expected: 099f3159 Delete __pycache__ directory
```

If the tip is NOT 099f3159, STOP and report — someone pushed again; re-inspect before merging.

- [ ] **Step 2: Merge with unrelated histories**

```bash
git merge origin/dev --allow-unrelated-histories --no-edit -m "merge: bring agentic_workflow prototype (origin/dev) into consolidation

Tree union of Rohan's original two-agent prototype with the dev-na line
(flagship package + docs + nictopia). No path collisions.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: clean merge, no conflicts (disjoint paths). If conflicts appear, they can only be at root level — resolve by keeping OUR version of any root file (`git checkout --ours <file>`) and report which files collided.

- [ ] **Step 3: Remove committed junk at tip**

```bash
git rm .DS_Store
git rm -r agentic_workflow/__pycache__
git commit -m "chore: remove committed .DS_Store and __pycache__ from tip

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Verify the union**

```bash
ls agentic_workflow/ murmuration/ nictopia/ docs/   # all four present
git ls-files | grep -cE "(\.DS_Store|\.pyc$)"       # Expected: 0
```

---

### Task 4: Fix `agentic_workflow` stale references

**Files:**
- Modify: `agentic_workflow/README.md` (scratch notes lines 1–11; `synthetic_grid.py` refs at lines ~178, ~231, ~307; `baselines.py` claims at lines ~39, ~131, ~312)
- Modify: `agentic_workflow/runner.py:264`, `agentic_workflow/generate_grid.py:2,27`

**Interfaces:**
- Consumes: `agentic_workflow/` from Task 3.
- Produces: README whose setup commands actually run — Task 6 executes `python generate_grid.py` per these docs.

**IMPORTANT distinction:** the *script* was renamed `synthetic_grid.py` → `generate_grid.py`, but the *output file* is still legitimately named `data/synthetic_grid.parquet` (see `generate_grid.py:703`). Fix only `.py` references, never `.parquet` ones.

- [ ] **Step 1: Delete the scratch notes**

`agentic_workflow/README.md` currently begins:

```markdown
# murmuration
SCSP AI Hackathon DC


Comments:
Overutilized and underutilized scenarios in local data centers in one region
Then if not then it looks at a wider span

Simplify agentic comments

Make it simple on API press

# Grid-Aware Compute Agents
```

Delete everything before `# Grid-Aware Compute Agents` so that heading is line 1.

- [ ] **Step 2: Fix the script-name references (README)**

Three edits in `agentic_workflow/README.md` (line numbers shift by −11 after Step 1):
- Project-layout entry `├── synthetic_grid.py                # one-shot data generator` → `├── generate_grid.py                 # one-shot data generator`
- Setup command `python synthetic_grid.py` → `python generate_grid.py`
- Status line `- ✅ Synthetic data generator with 4 zones and 6 scenarios (\`synthetic_grid.py\`)` → `- ✅ Synthetic data generator with 4 zones and 6 scenarios (\`generate_grid.py\`)`

- [ ] **Step 3: Correct the unbacked `baselines.py` claims (README)**

- Line ~39: replace
  `- The system is benchmarked against two non-LLM baselines (naive and heuristic) on the same simulated trace. The scorecard reports cost, carbon, reject rate, and zone placement distribution — apples-to-apples comparison.`
  with
  `- The runner emits a scorecard (cost, carbon, reject rate, zone placement distribution) designed for apples-to-apples comparison against non-LLM baselines. (The baseline scripts themselves were not committed before the event ended.)`
- Architecture-diagram line `runner.py / baselines.py` → `runner.py`
- Status line `- ✅ Naive and heuristic baselines for comparison (\`baselines.py\`)` → `- ⏳ Naive and heuristic baselines (\`baselines.py\`) — designed, not committed`

- [ ] **Step 4: Fix the code-side references**

- `agentic_workflow/runner.py:264`: `"Either adjust DEFAULT_START/DEFAULT_END or regenerate data with synthetic_grid.py"` → `...with generate_grid.py"`
- `agentic_workflow/generate_grid.py:2`: `synthetic_grid.py — Generate signal-rich grid data...` → `generate_grid.py — Generate signal-rich grid data...`
- `agentic_workflow/generate_grid.py:27`: `python synthetic_grid.py` → `python generate_grid.py`

- [ ] **Step 5: Verify no stale `.py` references remain, and commit**

```bash
grep -rn "synthetic_grid.py" agentic_workflow/   # Expected: no output
grep -rn "baselines.py" agentic_workflow/README.md   # Expected: only the "designed, not committed" status line
git add agentic_workflow/
git commit -m "docs: fix agentic_workflow stale references (generate_grid.py rename, baselines claim, scratch notes)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Root README, `.env.example`, small doc fixes

**Files:**
- Create: `README.md` (root), `.env.example` (root)
- Modify: `murmuration/README.md` (~lines 78, 174, 192-area), `MURMURATION.md` (banner after line 1)

**Interfaces:**
- Consumes: full tree from Tasks 1–4.
- Produces: root README referencing `docs/media/flagship_globe.png` and `docs/media/nictopia_globe.png` — those files are CREATED by Task 6 (known one-task gap, same branch).

- [ ] **Step 1: Confirm actual env-var names before writing .env.example**

```bash
grep -rhoE "os\.(getenv|environ\.get)\(['\"][A-Z_]+" murmuration/murmuration/ agentic_workflow/ | sort -u
grep -rhoE "(EIA_KEY|EIA_API_KEY)" nictopia/scripts/ | sort -u
```

Expected: `ANTHROPIC_API_KEY`, `EIA_API_KEY`, `NREL_API_KEY`, `PORT` (flagship); `ANTHROPIC_API_KEY` (agentic_workflow); `EIA_KEY` (nictopia refresh script). If names differ, use the grep output in the next step, not this plan's assumption.

- [ ] **Step 2: Write `.env.example` at repo root**

```bash
cat > .env.example <<'EOF'
# All keys are OPTIONAL. Every component runs without them, degrading to
# synthetic/cached data and rule-based narration.
#
# Flagship server: copy this file to murmuration/.env (run.sh sources it there).
# agentic_workflow: put ANTHROPIC_API_KEY in agentic_workflow/.env or export it.
# nictopia: no keys needed to run; EIA_KEY is only for refreshing the committed
#           data snapshot via nictopia/scripts/fetch_eia.py.

# Live Claude agent decisions + narration (flagship, agentic_workflow)
ANTHROPIC_API_KEY=

# Live EIA-930 grid data for non-CAISO ISOs (flagship)
EIA_API_KEY=

# NREL PVWatts solar profiles for the forecaster (flagship)
NREL_API_KEY=

# Snapshot refresh only (nictopia/scripts/fetch_eia.py)
EIA_KEY=
EOF
```

- [ ] **Step 3: Fix `murmuration/README.md` nits**

- Line ~78: `cp .env.example .env  # if you have an example file, otherwise create your own` → `cp ../.env.example .env  # optional — everything runs without keys`
- Line ~174: `│   ├── protocol/        # MurmurationBus + 10 Pydantic message types` → `│   ├── protocol/        # MurmurationBus + 12 Pydantic message types`
- Under the `## The 7 message types` heading, insert as the first paragraph:

```markdown
> The seven core negotiation types are documented below. The full protocol exports twelve message
> classes (see `murmuration/protocol/__init__.py`) — the additional five (`GridForecast`,
> `FlexibilityBand`, `LoadForecast`, `TelemetryFrame`, `CounterOffer`) support forecasting,
> envelope structure, and telemetry.
```

  (Before inserting, check `murmuration/protocol/__init__.py` `__all__` against the seven documented below the heading and name the actual non-documented five in the note.)
- At the end of the README, append:

```markdown
## Triggering scenarios from the command line

The scenario endpoint takes the URL-encoded *display name*, not a slug:

```bash
curl -X POST 'http://127.0.0.1:8765/api/scenario/Texas%20heat%20wave'   # ✓
curl -X POST 'http://127.0.0.1:8765/api/scenario/texas_heat_wave'       # ✗ 404
```
```

- [ ] **Step 4: Add the historical banner to `MURMURATION.md`**

Insert after line 1 (`# Murmuration — Master Brainstorm Document`):

```markdown

> **Historical document (April 2026):** this is the team's pre-build design/brainstorm doc, kept as
> a record of the hackathon process. Some module layouts and counts in §6 drifted from the as-built
> system — for the shipped architecture and how to run it, see the root [README](README.md) and
> [`murmuration/README.md`](murmuration/README.md).
```

- [ ] **Step 5: Write the root `README.md`**

```markdown
<p align="center">
  <img src="docs/demo/murmuration_logo.png" alt="Murmuration" width="360">
</p>

# Murmuration

**The grid and the AI compute fleet need to start talking. We built the protocol — and the agents
that speak it.**

Built in one day at the **SCSP AI Hackathon · Electric Grid Optimization track · Washington DC ·
April 26, 2026**.

Data centers are becoming one of the largest — and most concentrated — loads on the US grid, right
as extreme weather makes the grid more fragile. Murmuration is a bilateral wire format that lets
grid operators and flexible loads negotiate in real time: the grid publishes state and dispatch
requests; data centers and home-battery fleets answer with standing flexibility envelopes, acks,
and counter-offers. Two live Python agents (Claude-backed, with rule-based fallback) speak the
protocol on each side, on top of load forecasting, anomaly detection, and a self-healing topology
layer.

<p align="center">
  <img src="docs/media/flagship_globe.png" alt="Flagship UI — 3D globe view" width="800">
</p>

## Run it (no API keys required)

Everything below runs fully offline — live data sources and Claude narration are optional
enrichments via [`.env.example`](.env.example).

### 1. `murmuration/` — the flagship (Python)

The end-to-end system demoed on stage: protocol bus with 12 Pydantic message types, GridAgent +
ComputeAgent, 9 data centers + a 100-home virtual power plant, GBM load forecaster, z-score
anomaly detector, networkx topology healer, tiered workload router, 9 scenarios, and a 3-tab UI
(3D globe · flat map · story walkthrough) over FastAPI + WebSocket.

```bash
cd murmuration
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
# open http://127.0.0.1:8765 — pick a scenario in the right rail (e.g. "Texas heat wave")
```

See [`murmuration/README.md`](murmuration/README.md) for scenarios, endpoints, troubleshooting.

### 2. `nictopia/` — the visual demo (React)

A standalone globe + flat-map replay of real archived grid incidents (Winter Storm Uri, the 2019
CAISO PSPS, the duck curve, Hurricane Helene) with primary-source citations and formula-derived
dollar/carbon figures. All data ships as committed JSON caches — no backend.

```bash
cd nictopia
npm install
npm run dev
# open http://localhost:5173
```

<p align="center">
  <img src="docs/media/nictopia_globe.png" alt="nictopia — React globe demo" width="800">
</p>

### 3. `agentic_workflow/` — the original prototype (Python)

Where it started: two Claude agents negotiating GPU-job placement over a synthetic 14-day,
4-zone grid replay with hard-bid economics (every job has a max willingness-to-pay; rejection is
a correct outcome). Includes a reproducible merit-order data generator with day-ahead vs real-time
prices and forecast-bust modeling.

```bash
cd agentic_workflow
python3 -m venv .venv && .venv/bin/pip install pandas numpy pyarrow anthropic python-dotenv
.venv/bin/python generate_grid.py   # writes data/*.parquet — no API needed
.venv/bin/python gridcache.py       # data-layer smoke test — no API needed
# .venv/bin/python runner.py        # full agent replay — needs ANTHROPIC_API_KEY, ~$2-4
```

## How the pieces relate

The team built in parallel and merged deliberately: Rohan's `agentic_workflow/` prototype proved
the two-agent negotiation loop; a Copilot-built mock and Nick's `nictopia/` explored how to make
it legible to judges; Shashank's `murmuration/` package unified the ideas into the live protocol
system we staged. The written comparison that drove the final call is in
[`docs/reference/shashank_branch_review.md`](docs/reference/shashank_branch_review.md).

## Repo map

| Path | What it is |
|---|---|
| `murmuration/` | Flagship: protocol + agents + forecasting + topology healer + 3-tab UI |
| `nictopia/` | React globe/flat-map demo over real archived incidents |
| `agentic_workflow/` | Original two-agent prototype with hard-bid job economics |
| `MURMURATION.md` | Pre-build design doc (historical) |
| `PITCH.md` | Pitch-deck rationale |
| `docs/demo/` | Stage materials: 4-slide deck, demo script, judge Q&A prep, presenter card |
| `docs/reference/` | Grid-physics honesty notes, implementation comparison, nictopia design |

## Data honesty

- CAISO data is fetched live (via `gridstatus`) when the network allows; ERCOT/PJM/MISO/NYISO/
  ISO-NE/SPP use EIA-930 (optional key) and everything degrades to calibrated synthetic data.
- nictopia's incident replays are anchored to dated, committed snapshots with FERC/NERC/utility
  source URLs in each JSON.
- HIFLD transmission-line/substation overlays for the flagship flat map require a bulk download
  (paths in `murmuration/README.md`); without them the map simply omits those layers.
- The UIs load three.js/globe.gl/Reveal.js from public CDNs, so the browser needs internet even
  though the backends run offline.

## Team

- **Nick Allison** ([@enturesting](https://github.com/enturesting)) — nictopia globe demo,
  real-incident data anchoring, demo narrative + pitch materials, integration
- **Teddy Allison** — [EDIT ME, Nic: Teddy's role in your words — e.g. scenario decisioning,
  demo story, judge Q&A rehearsal]
- **Rohan Dani** ([@RohanDani2](https://github.com/RohanDani2)) — `agentic_workflow/` prototype:
  synthetic grid generator, hard-bid compute-agent economics
- **Shashank Chikara** — flagship `murmuration/` package: protocol layer, live agents, anomaly
  detector, topology healer, 3-tab UI
```

- [ ] **Step 6: Verify links and commit**

```bash
# every local path referenced by the root README exists (docs/media/* intentionally pending Task 6)
for p in docs/demo/murmuration_logo.png .env.example murmuration/README.md nictopia docs/reference/shashank_branch_review.md docs/demo PITCH.md MURMURATION.md agentic_workflow; do test -e "$p" || echo "MISSING: $p"; done
# Expected: no output
git add README.md .env.example murmuration/README.md MURMURATION.md
git commit -m "docs: reviewer-facing root README, .env.example, README/design-doc fixes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Verification from a fresh clone + screenshots

**Files:**
- Create: `docs/media/flagship_globe.png`, `docs/media/nictopia_globe.png`
- Scratch: `$SCRATCH/murmuration-verify` (fresh clone; use the session scratchpad dir)

**Interfaces:**
- Consumes: complete branch from Task 5.
- Produces: verification evidence for the Task 7 PR body; the two screenshots the root README embeds.

- [ ] **Step 1: Fresh clone**

```bash
SCRATCH=/private/tmp/claude-501/-Users-nic-dev-murmuration/29a676b4-dc23-4544-9afa-7e141d4bb701/scratchpad
git clone --branch feature/consolidation /Users/nic/dev/murmuration "$SCRATCH/murmuration-verify"
cd "$SCRATCH/murmuration-verify"
```

- [ ] **Step 2: Flagship — install, boot, exercise**

```bash
cd "$SCRATCH/murmuration-verify/murmuration"
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Expected: succeeds (pins tested on 3.12)
nohup ./run.sh > "$SCRATCH/flagship.log" 2>&1 &
echo $! > "$SCRATCH/flagship.pid"
for i in $(seq 1 30); do curl -sf http://127.0.0.1:8765/api/state >/dev/null && break; sleep 1; done
curl -s http://127.0.0.1:8765/api/state | head -c 300    # Expected: JSON with grid/asset state
curl -s -X POST 'http://127.0.0.1:8765/api/scenario/Texas%20heat%20wave'
sleep 30
curl -s http://127.0.0.1:8765/api/state | grep -oE '"dispatches_issued":[0-9]+'
# Expected: dispatches_issued >= 1 (event-day runs produced 5 within ~30s)
curl -s http://127.0.0.1:8765/ | head -c 200             # Expected: <!DOCTYPE html> ... UI page
```

- [ ] **Step 3: Flagship screenshot (needs internet for CDN libs)**

```bash
mkdir -p /Users/nic/dev/murmuration/docs/media
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --use-angle=swiftshader --window-size=1600,900 --virtual-time-budget=20000 \
  --screenshot=/Users/nic/dev/murmuration/docs/media/flagship_globe.png http://127.0.0.1:8765/
```

Inspect the PNG (Read tool). If the globe canvas rendered black (headless WebGL failure), take the
screenshot of the Flat Map or Story tab instead by appending the UI's tab hash/param — check
`murmuration/ui/index.html` for how tabs switch — or as a last resort ask Nic to screenshot
manually and drop the file in `docs/media/`. Do not ship a black image.

Then stop the server:

```bash
kill "$(cat "$SCRATCH/flagship.pid")"
```

- [ ] **Step 4: nictopia — type-gate build + serve + screenshot**

```bash
cd "$SCRATCH/murmuration-verify/nictopia"
npm ci || npm install          # lockfile from April 2026; fall back and note churn in PR if ci fails
npm run build                  # Expected: tsc -b passes, vite build emits dist/
nohup npx vite preview --port 4173 > "$SCRATCH/nictopia.log" 2>&1 &
echo $! > "$SCRATCH/nictopia.pid"
for i in $(seq 1 15); do curl -sf http://127.0.0.1:4173/ >/dev/null && break; sleep 1; done
curl -s http://127.0.0.1:4173/ | head -c 200   # Expected: HTML with the app root div
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --use-angle=swiftshader --window-size=1600,900 --virtual-time-budget=20000 \
  --screenshot=/Users/nic/dev/murmuration/docs/media/nictopia_globe.png http://127.0.0.1:4173/
kill "$(cat "$SCRATCH/nictopia.pid")"
```

Inspect the PNG; same black-canvas fallback policy as Step 3.

- [ ] **Step 5: agentic_workflow — no-API smokes**

```bash
cd "$SCRATCH/murmuration-verify/agentic_workflow"
python3 -m venv .venv
.venv/bin/pip install pandas numpy pyarrow anthropic python-dotenv
.venv/bin/python generate_grid.py
ls data/   # Expected: synthetic_grid.parquet (or .csv), synthetic_jobs.parquet, synthetic_scenarios.json
.venv/bin/python gridcache.py   # Expected: smoke output, exit code 0
```

(`runner.py` is intentionally NOT run — needs ANTHROPIC_API_KEY and costs ~$2–4; documented in its README.)

- [ ] **Step 6: Slides sanity**

```bash
cd /Users/nic/dev/murmuration
grep -c "<section" docs/demo/demo_slides.html   # Expected: 4
test -f docs/demo/murmuration_logo.png && echo OK
```

- [ ] **Step 7: Commit screenshots and record evidence**

```bash
cd /Users/nic/dev/murmuration
git add docs/media/
git commit -m "docs: verification screenshots for root README

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Save the verification outputs (pip/npm success, dispatches_issued count, generate_grid file list)
— they go verbatim into the Task 7 PR body. If ANY check failed, STOP: fix on the feature branch
before Task 7, and re-run the failed check from a re-pulled clone.

---

### Task 7: Merge to `dev`, PR to `main`, GitHub tidy-up

**Files:** none (git/GitHub state only)

**Interfaces:**
- Consumes: verified branch from Task 6.
- Produces: PR `dev` → `main` for Nic to merge; closed stale PRs #1/#2; updated repo metadata.

- [ ] **Step 1: Push the feature branch**

```bash
git push -u origin feature/consolidation
```

- [ ] **Step 2: Merge to dev and push**

```bash
git checkout -B dev origin/dev
git merge feature/consolidation --no-edit    # Expected: clean — feature already contains origin/dev
git push origin dev
git checkout feature/consolidation
```

- [ ] **Step 3: Open the PR to main**

```bash
gh pr create --repo enturesting/murmuration --base main --head dev \
  --title "Consolidate hackathon work: flagship + nictopia + prototype, verified" \
  --body "$(cat <<'EOF'
Wraps up the SCSP hackathon repo into one coherent, runnable showcase.

## What's in here
- **Flagship `murmuration/`** (from dev-cs/dev-na): protocol + agents + 3-tab UI, plus all pitch/demo docs and the finished 4-slide deck
- **`nictopia/`**: Nick's React globe demo restored from `feature/nictopia` (Shashank's initial drop had removed it); the two-implementation comparison doc restored to `docs/reference/`
- **`agentic_workflow/`**: Rohan's prototype, already on main — README fixed (script rename, uncommitted-baselines claim, scratch notes), committed `.DS_Store`/`__pycache__` removed
- **New root README** with quick starts for all three apps, data-honesty notes, and team credits
- `.env.example` (all keys optional), historical banner on MURMURATION.md

## Verified from a fresh clone
- [VERIFICATION EVIDENCE FROM TASK 6 — paste: flagship pip install + boot + scenario dispatch counts, nictopia npm build pass, agentic_workflow generate_grid/gridcache smoke results, screenshot files]

## Deliberately NOT done
- No history rewrite (the old committed-.venv blobs still bloat clones to ~156MB) — optional follow-up
- `runner.py` full agent replay not executed (needs API key, ~$2–4)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

(The `[VERIFICATION EVIDENCE...]` placeholder is filled with Task 6's actual outputs at execution time — it must not ship as-is.)

- [ ] **Step 4: Close stale PRs with comments**

```bash
gh pr close 2 --repo enturesting/murmuration --comment "Superseded by the consolidation PR — dev-na's docs (and more) are included there. Branch kept for provenance."
gh pr close 1 --repo enturesting/murmuration --comment "Superseded — the ideas here evolved through feature/nictopia into the flagship UI (see docs/reference/shashank_branch_review.md in the consolidation PR). Branch kept for provenance."
```

- [ ] **Step 5: Update repo metadata**

```bash
gh repo edit enturesting/murmuration \
  --description "Grid-aware compute orchestration protocol + agents — SCSP AI Hackathon (Washington DC, April 2026)" \
  --add-topic energy-grid --add-topic multi-agent --add-topic hackathon --add-topic fastapi --add-topic react --add-topic claude
```

- [ ] **Step 6: Hand off to Nic**

Report the PR URL. **Nic merges the PR to main** (per spec decision 4). After merge, suggest he
spot-check github.com/enturesting/murmuration renders the README + logo + screenshots correctly.

---

## Execution notes

- Tasks are strictly sequential (each consumes the previous branch state) — do not parallelize.
- If any verification in Task 6 fails, the fix happens on `feature/consolidation` BEFORE Task 7;
  nothing is pushed until verification passes.
- The two screenshots are the only steps that can genuinely block (headless WebGL): the fallback
  chain is Flat Map/Story tab → manual screenshot from Nic. Everything else is deterministic.
