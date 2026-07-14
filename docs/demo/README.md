# Demo materials  (dev-na working set)

Scratch space for everything pitch-related. Iterate freely.

> Built against the **dev-cs / dev-na** codebase: Python+FastAPI backend, live tick loop, 9 scenarios, 3 UI views (Globe / Flat Map / Story).
>
> URL: `http://127.0.0.1:8765/`  ← NOT 5173 (that was `feature/nictopia`).

## Files

- **`demo_flow.md`** — beat-by-beat plan for the 5-minute live demo. Hard time budget, contingencies, setup checklist at the bottom.
- **`demo_slides.md`** — markdown mirror of the cold-open slide.
- **`demo_slides.html`** — reveal.js slide deck (1 cold-open slide). Self-contained — opens in any browser.
- **`criteria.md`** — judging-rubric cheat sheet, judge profiles (McGee / Barati), beat-to-rubric coverage check.
- **`judge_qa_prep.md`** — hard-question defenses with judge-tagged answers (`[McGee]`, `[Barati]`, `[Both]`).
- **`todo_list.md`** — pre-stage TODO list, prioritized P0 → P5.

## Running the slides

Just open the HTML file:

```bash
open docs/demo/demo_slides.html
```

Reveal is loaded from CDN, so first open needs the network. After that the browser caches the assets. For an air-gapped stage, vendor reveal locally before demo day.

### Useful keys
- `→` / `space` — next slide
- `←` — previous
- `s` — speaker notes window (notes are written into each slide's `<aside class="notes">`)
- `o` — overview / grid view
- `f` — fullscreen

## Running the live app (the actual demo)

```bash
# from repo root
cd murmuration
bash run.sh    # needs .venv with requirements.txt installed
```

Then open `http://127.0.0.1:8765/`. Default tab is **3D Globe**. Other tabs: Flat Map, Story.

## Reading order for new team members

1. `demo_flow.md` — get the script in your head
2. `criteria.md` — understand what each beat is earning
3. `judge_qa_prep.md` — be ready for hard questions
4. `todo_list.md` — see what's still open
5. `demo_slides.md` / `.html` — the cold-open

## Cross-references

- Grid-physics reference: `docs/reference/electric_travel.md`
- Protocol thesis + design: `MURMURATION.md` (repo root)
- Pitch slide-by-slide rationale: `PITCH.md` (repo root)
