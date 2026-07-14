# Murmuration Branch Consolidation — Design

**Date:** 2026-07-13
**Author:** Nic + Claude
**Status:** Approved (design approved in session 2026-07-13)

## Purpose

Consolidate everything the team built at the SCSP AI Hackathon (Washington DC, April 26, 2026)
into one verified-working branch, merge it to `dev` and then `main`, so the public repo
(`github.com/enturesting/murmuration`) reads as a complete, runnable prior project.

**Hard deadline context:** the repo is the prior-work link for Teddy Allison's application to the
fal x Sequoia 72-hour video hackathon. Applications close **July 16, 2026**; Teddy applies by end
of day **July 15**. Reviewer-facing polish on `main` is the deliverable.

## Current state (verified 2026-07-13)

Branch topology:

- `origin/main` (default, public) = merge of PR #3 (`dev` → `main`, merged event day).
  Tip contains only Rohan's `agentic_workflow/` prototype plus committed `.DS_Store` and
  `agentic_workflow/__pycache__/*.pyc`. **No root README, no .gitignore.**
- `origin/dev` = Rohan Dani's original two-agent prototype, reorganized under `agentic_workflow/`.
  History contains a committed-then-deleted `.venv` (22,601 files; git pack is ~156MB and
  reachable from public `main`). Unique capabilities vs the flagship: synthetic dataset generator
  with day-ahead LMP + forecast-bust modeling (`generate_grid.py`), hard-bid job economics
  (`compute_agent.py`), time-of-decision backtest discipline (`gridcache.py`).
- `dev-cs` = Shashank Chikara's "Initial drop" (4decc999): the flagship Python package
  `murmuration/` (protocol bus, GridAgent/ComputeAgent, anomaly detector, topology healer,
  workload router, 9 scenarios, FastAPI + WebSocket server, 3-tab single-file UI).
  This commit **deleted** the React app from the tree.
- `dev-na` (current local branch) = `dev-cs` + 14 docs commits (docs/demo pitch materials,
  MURMURATION.md fixes). Superset of `dev-cs`; disjoint history from `dev`/`main`.
  Uncommitted working tree: modified `docs/demo/demo_slides.{md,html}` (4-slide redesign;
  **HTML incomplete** — missing Problem slide, slide-3 body text, slide-4 "Watch it work" +
  PILOT ASK), untracked `docs/demo/murmuration_logo.png` (required by the new HTML) and
  `docs/demo/final_polish.md`.
- `feature/nictopia` = Nic's React 19 + Vite + TS globe/flat-map demo. Runs fully offline from
  committed caches (`npm install && npm run dev`, zero keys). Unique assets: 5 dated
  real-incident JSONs with FERC/NERC citations (`public/cache/historical/`), EIA carbon-math
  library (`src/lib/eia.ts` + snapshots), judge-comprehension UI components.
  Survives only on this branch. Ancestor of `dev-cs`.
- `origin/copilot/create-murmuration-prototype` = Copilot-generated mock demo. Superseded at
  every capability level by both the flagship UI and nictopia. Draft PR #1 open.
- Open PRs: #2 (`dev-na` → `dev-cs`, docs-only, superseded), #1 (draft, superseded).
- Security: **no secrets on any branch or in any reachable history** (audited). No key rotation
  needed. All API-key references are env-var reads or placeholders.

## Decisions (user-approved)

1. **Test bar:** demo runs end-to-end, verified from a fresh clone; steps documented in README.
   No new test suite.
2. **nictopia:** restored into the final tree under `nictopia/`.
3. **History:** additive consolidation, **no history rewrite** before the deadline. The ~156MB
   pack stays for now; a `git filter-repo` purge of `.venv` blobs is an optional follow-up after
   July 15. No fresh-root branch: the multi-author history is collaboration evidence.
4. **Merge path:** feature branch → `dev` → PR `dev` → `main`; **Nic merges the final PR**.

## Target tree on `main`

```
README.md                  ← NEW: reviewer-facing root README (the centerpiece)
.gitignore                 ← dev-na's (only complete one), extended if needed post-merge
.env.example               ← NEW: the three optional keys (ANTHROPIC_API_KEY, EIA_API_KEY, NREL_API_KEY)
MURMURATION.md             ← + short "historical design doc — see murmuration/README.md for as-built" banner
MURMURATION.pdf            ← kept as-is (763KB snapshot artifact)
PITCH.md                   ← kept as-is
docs/                      ← demo scripts, judge Q&A prep, finished slides, reference docs
  demo/                    ← + committed logo, finished demo_slides.html, final_polish.md
  reference/               ← + shashank_branch_review.md and what_is_nictopia.md restored if absent
  media/                   ← NEW: UI screenshots captured during verification
  superpowers/specs/       ← this document
murmuration/               ← flagship Python package, unchanged except README nits + .env.example note
nictopia/                  ← restored React app (src/, public/, scripts/, configs, README, INTEGRATION.md)
agentic_workflow/          ← Rohan's prototype, cleaned (junk removed, README fixed)
```

## Work plan

### Phase 1 — feature branch + working-tree resolution

- Create `feature/consolidation` off the `dev-na` tip (85427cfe at design time; this spec commits
  on top of it first).
- Finish `docs/demo/demo_slides.html` to match `demo_slides.md`: add the missing Problem slide
  (slide 2), fill slide-3 body text, add slide-4 "Watch it work" heading + subtitle + PILOT ASK
  line (the `.ask` CSS class exists, unused).
- Commit slides + `murmuration_logo.png` + `final_polish.md` in one commit (the HTML
  hard-requires the PNG via `img src="murmuration_logo.png"`).

### Phase 2 — restore nictopia under `nictopia/`

- Restore from `feature/nictopia` tip (fabc1345) into `nictopia/` **excluding its `docs/`
  subtree** (dev-na's root `docs/` is the evolved version) and excluding its root `.gitignore`
  (fold needed entries into root .gitignore).
- Restore `docs/reference/shashank_branch_review.md` and `docs/reference/what_is_nictopia.md`
  to root `docs/reference/` if not already present on dev-na.
- Add a short provenance note at the top of `nictopia/README.md`: what this app is relative to
  the flagship, and that the team chose `dev-cs` as the primary demo (per the branch review).

### Phase 3 — merge `origin/dev`, clean `agentic_workflow/`

- `git merge origin/dev --allow-unrelated-histories` (tree union; no path collisions expected).
- Delete committed junk at tip: `.DS_Store`, `agentic_workflow/__pycache__/*.pyc`.
- Fix `agentic_workflow/README.md`: remove scratch notes above the title; fix
  `synthetic_grid.py` → `generate_grid.py` references (also in `runner.py` and the
  `generate_grid.py` docstring); correct or remove the unbacked `baselines.py` claim.
- Keep `agent-ds.ipynb` (teammate's file, harmless).

### Phase 4 — README + small fixes

- Write root `README.md`: logo; one-line thesis; event line (SCSP AI Hackathon · Electric Grid
  Optimization · Washington DC · April 26, 2026); what it does (elevator pitch adapted from
  MURMURATION.md §14.1); UI screenshot; repo map with the evolution story (agentic_workflow
  prototype → copilot/nictopia visual demos → murmuration flagship, linking the branch review);
  quick start for each app, flagship first, emphasizing zero-keys operation; honest data-source
  notes (CAISO live via gridstatus, others EIA-930/synthetic fallback, HIFLD bulk data
  download-on-demand); **Team section naming all four members** — Nic Allison, Teddy Allison,
  Rohan Dani, Shashank Chikara — with **placeholder role wording for Teddy that Nic edits**.
- `murmuration/README.md` nits: fix message-type count (12 exported classes), point Quick start
  at the new root `.env.example`, document the URL-encoded scenario display-name POST.
- Add `.env.example` at root.
- Add historical banner to `MURMURATION.md`.
- Update GitHub repo description + topics (e.g. "Grid-aware compute orchestration protocol —
  SCSP AI Hackathon (DC), April 2026"; topics: energy-grid, multi-agent, hackathon, fastapi,
  react).

### Phase 5 — verification (fresh clone of the feature branch)

All from a scratch clone, so nothing depends on local state:

1. **Flagship:** `cd murmuration && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`
   (run.sh expects `.venv` inside `murmuration/`); `./run.sh`; assert
   `GET /api/state` returns grid entries + assets; `POST /api/scenario/Texas%20heat%20wave`;
   within ~30s assert `dispatches_issued > 0` and `dispatches_accepted > 0` in `/api/state`;
   `GET /` returns the UI HTML. Open in browser, screenshot Globe tab → `docs/media/`.
2. **nictopia:** `cd nictopia && npm install && npm run build` (includes `tsc -b` type gate);
   `npm run dev` smoke — page serves at :5173; screenshot → `docs/media/`.
3. **agentic_workflow:** venv with `pandas numpy pyarrow anthropic python-dotenv`;
   `python generate_grid.py` writes the three data files; `python gridcache.py` no-API smoke
   passes. `runner.py` full replay costs ~$2–4 in API calls — documented in its README, not run.
4. **Slides:** `docs/demo/demo_slides.html` has 4 `<section>`s matching the md; logo referenced
   and committed.

### Phase 6 — merge + GitHub tidy-up

- Push `feature/consolidation`. Merge to `dev` (normal merge — feature already contains
  `origin/dev`), push.
- Open PR `dev` → `main` with a summary of the consolidation + verification evidence.
  **Nic merges.**
- Comment + close PR #2 ("superseded by consolidation PR") and draft PR #1 ("prototype
  preserved on its branch; superseded"). Keep all branches for provenance.

## Out of scope

- History rewrite / `.venv` blob purge (optional follow-up after July 15).
- Porting nictopia's judge-comprehension components into the Python UI (the never-executed
  cherry-pick plan in `shashank_branch_review.md` §5).
- New features, tests/CI, packaging metadata.
- The `results/` research files and `murmur_parallel.md` outside the repo.
- Recording the backup demo video referenced in `docs/demo/todo_list.md`.

## Risks

- **Merge union surprises:** `origin/dev` merge should be collision-free (disjoint paths);
  verify `git status` after merge shows only expected additions.
- **CDN dependence:** the flagship UI and slides load three.js/globe.gl/Reveal.js from CDNs —
  browser verification needs internet; noted honestly in README.
- **npm install drift:** nictopia's lockfile is from April 2026; if `npm ci` fails on this
  machine, fall back to `npm install` and note any lockfile churn in the PR rather than
  hand-editing versions.
- **Remote instability:** `origin/dev` was force-pushed around event day; re-fetch before
  merging and confirm tip is 099f3159.
