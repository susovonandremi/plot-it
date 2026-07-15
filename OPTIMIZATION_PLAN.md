# PlotIt — Optimization & Improvement Plan

_Audit date: 2026-07-15. Based on a full read of ~13.5k LOC (backend 10.5k, frontend 3k) plus a live run of the app. Every root-cause claim below was verified against source (file:line) and reproduced against the running app (`rooms_placed=3, score=49/100 grade F, Sun=0`)._

---

## TL;DR — the single most important finding

One line in the orchestration route corrupts **every** quality metric the product reports:

```python
# backend/routes/generate.py:429
placed_rooms = all_floor_layouts.get(1, all_floor_layouts.get(0, []))
```

For a **single-story** house the floor loop builds floor `0` (the real, CP-SAT-solved living floor) **and** floor `1` (the auto-generated ROOF: stair + water tank + terrace = exactly 3 elements). This line picks floor `1` — **the roof** — as the "primary" layout. So circulation, accessibility, blueprint score, environment, proportions, vastu heatmap, and `rooms_placed` are all computed **against the roof, not the house**.

That one bug, plus two others, fully explains the numbers I measured:

| Symptom | Root cause | Fix |
|---|---|---|
| `rooms_placed=3` regardless of request | `generate.py:429` selects the roof floor | `primary_fn = 1 if total_floors>1 else 0` |
| `score=49` (hard F) | `blueprint_scorer.py:174` caps to 49 when accessibility<50; scoring runs on the door-less roof + `EXTERIOR` node not in graph | Score the living floor; exclude `EXTERIOR`/annotations from the accessibility graph; compute doors before scoring |
| `Sun=0`, ventilation flat | `solar_wind_engine.py:57` tests exterior walls against full `plot_width`, but every room is inset by the setback offset → no room ever touches an edge | Pass buildable dims + setback offset (or compare vs placed-room bbox) |

**These three fixes are ~1 day of work and turn the product's output from "broken/F-grade" to actually representative.** Everything else in this plan is important, but this is the headline.

---

## How to read this plan

Findings are grouped by area and tagged **[Cx]** correctness, **[Sx]** security/infra, **[Ux]** UX/frontend, **[Ax]** architecture/hygiene. Severity: 🔴 CRITICAL · 🟠 HIGH · 🟡 MEDIUM · ⚪ LOW. Each item has file:line and a fix. The phased roadmap at the end sequences them.

---

## 1. Generation correctness — the product's core value

### 🔴 [C1] Primary layout is the roof floor for single-story houses
`generate.py:429`. See TL;DR. This is #1 to fix. Note the schema blueprint at `:532` already uses the correct `core_fn = 1 if total_floors>1 else 0` — so the returned drawing is the house but every *score* is the roof. Inconsistent by construction.
**Fix:** `primary_fn = 1 if total_floors > 1 else 0; placed_rooms = all_floor_layouts.get(primary_fn, [])`.

### 🔴 [C2] Setback coordinate-frame mismatch zeroes Sun / ventilation / windows
`generate.py:562-566` passes the **raw** `plot_width`/`plot_depth` to `analyze_environment`, but every room was inset by `setback_offset_x/y_ft` (~3.3 ft). `solar_wind_engine.py:57` detects exterior walls with `abs(rx+rw - plot_width) <= TOL` — which no inset room satisfies. Result: `sun_hours=0` for all rooms, ventilation collapses to "interior". Latent even after [C1].
**Fix:** pass `buildable_width_ft`/`buildable_depth_ft` **and** the setback offset, or compare against the placed-room bounding box (as the serializer already does).

### 🔴 [C3] Broad `try/except` blocks make a broken pipeline report `success: true`
`generate.py:210-226` pre-initializes zeroed defaults; `:490-523, 540-581` each wrap a stage in `except Exception → warn → keep the zeros`; `schema_serializer.py:272` is a bare `except: pass`. A fully failed sub-pipeline returns HTTP 200 with plausible-looking zero data. This is *why* [C1]/[C2] shipped silently.
**Fix:** attach a per-stage `errors[]` array to the response; set `success:false` when a **core** stage (solve/serialize) fails; let non-core stages degrade but report it. Stop swallowing.

### 🟠 [C4] Blueprint score hard-capped at 49 by an accessibility gate on a door-less graph
`blueprint_scorer.py:174`. `ensure_full_accessibility` is called with `doors=[]` (`generate.py:475`); the only door targets `room2_id='EXTERIOR'`, which is **not a node** in the graph (`accessibility_engine.py:111`), so BFS reaches almost nothing → accessibility≈33 → overall capped to 49. The real doors are computed *inside* `serialize_floor_plan` and thrown away.
**Fix:** compute doors once before scoring and thread them through; exclude `EXTERIOR`/`is_annotation` rooms from the graph; don't gate on an empty-door graph.

### 🟠 [C5] Vastu constraints are a silent no-op in the solver
`generate.py:352-356`: program rooms have no `id`, so `floor_vastu` stays empty; even with ids, `assign_vastu_zones` mints `Bedroom_1` while the solver mints `bedroom_0` — they never match. The solver's Vastu objective always uses zone `'C'`. Vastu placement is effectively dead, yet it's a headline feature.
**Fix:** assign stable room ids in `building_program` and reuse them across `assign_vastu_zones`, `_expand_rooms`, and `floor_vastu`.

### 🟠 [C6] Solver is non-deterministic despite a computed & returned seed
`generate.py:260` computes `layout_seed` from the prompt and returns it, but never passes it to CP-SAT; `constraint_solver.py:599` uses `num_workers=4`. Same prompt → different layouts run-to-run; the `"seed"` field is cosmetic.
**Fix:** `solver.parameters.random_seed = layout_seed % 2**31` and `num_search_workers=1` when reproducibility matters.

### 🟠 [C7] Feasibility check uses the full plot; the solver only has the buildable envelope
`generate.py:196-206` compares min-area to `plot_size_sqft*0.95`, but CP-SAT is constrained to `buildable_width×buildable_depth` (~784 sqft of a 1200 sqft plot after setbacks). The check passes, then the solver can't fit rooms → relaxation cascade / degraded proportions / dropped rooms.
**Fix:** compare against `buildable_area_sqft`.

### 🟠 [C8] Over-constrained solver model → frequent relaxation / low-quality `FEASIBLE`
`constraint_solver.py:311-325` adds O(n²) hard alignment BoolVars; `:250` + `:519-522` compute room area **twice** (multiplication equality in constraints *and* objective); `:431-440` nests foyer×living×dining×kitchen strict topology + shared-edge equalities that easily go INFEASIBLE, discarding the whole model into relaxation (dropping adjacency + Vastu). With a 5s limit this often returns low-quality `FEASIBLE`.
**Fix:** make alignment/topology **soft weighted** terms over a capped pair subset; reuse the single `area_var`. Biggest lever on layout *quality*.

### 🟡 [C9–C13] Secondary correctness
- **[C9]** `generate.py:429`-adjacent: `floors_generated` counts the roof (single-story reports `2`). Fix labeling after [C1].
- **[C10]** `blueprint_scorer.py:23-40` space-efficiency sums bounding-box area **including** the plot-covering `open_terrace` annotation — exclude `is_annotation` everywhere in scoring/coverage.
- **[C11]** `schema_serializer.py:197-208` mixes buildable room coords with full-plot `overall_width`/`plot_width_ft` — dimension chains won't sum. Pick one coordinate frame.
- **[C12]** `constraint_solver.py:648-678` emergency strip-fill can emit out-of-bounds/overlapping rooms (violates the module's "zero overlaps" guarantee) and drops labels/flags.
- **[C13]** `generate.py:236` hardcodes `road_width_m=8.534` (always "medium road" setbacks); `MIN_ESTIMATES` (`:197`) duplicates the solver's `ROOM_SIZES` with different numbers. Parameterize + centralize.

---

## 2. Security & infrastructure — deploy-blockers

### 🔴 [S1] Committed SQLite DBs with real user data
`git ls-files` tracks `plotai_projects.db` and `backend/plotai_projects.db` (38 and 74 real rows: prompts, SVGs, scores). No `*.db` in `.gitignore`. The root DB even shows as *modified* in the working tree — a live DB is versioned.
**Fix:** `git rm --cached *.db backend/*.db`; add `*.db *.sqlite*` to `.gitignore`; scrub history (git-filter-repo/BFG) if the repo is or ever was public.

### 🔴 [S2] CORS `allow_origins=["*"]` **with** `allow_credentials=True`
`main.py:39-45`. Spec-violating combo Starlette resolves by reflecting Origin — any site can make credentialed calls. Clerk/Stripe auth is already scaffolded, so this is a live CSRF-class exposure the moment sessions exist.
**Fix:** drive an explicit allowlist from the `ALLOWED_ORIGINS` env var (already in `.env.example`), or set `allow_credentials=False`.

### 🔴 [S3] `frontend/.env` committed; zero auth / IDOR on data endpoints
`frontend/.env` is tracked (backend/.env is ignored — asymmetric footgun). And **no endpoint has auth**: `GET /projects` returns everyone's projects, `GET/DELETE /projects/{id}` is open IDOR (`projects.py`, no `owner_id` column). Any anon caller reads or deletes any project.
**Fix:** gitignore + `git rm --cached frontend/.env` (ship `.env.example`); add auth (Clerk is scaffolded) + `owner_id` + per-user filtering; require auth on delete.

### 🟠 [S4] Raw exception strings leaked to clients
`generate.py:694`, `parse.py:31`, `consultation.py:69`, `export.py:43/85`, `stream.py:369` all return/emit `str(e)`. Leaks paths, library internals, DB/key errors.
**Fix:** generic message + correlation id to client; full detail to server logs only.

### 🟠 [S5] LLM path: empty bearer token, no timeout, no startup validation
`nlp_parser.py:11,209` sends `Authorization: Bearer None`/`Bearer ` (key empty) and `requests.post` (`:224,393,487`) has **no timeout** — a hung Groq call ties up a worker forever. Failures fall into a broad except → silent degradation to defaults with no health signal.
**Fix:** validate key at startup / surface in `/health`; add `timeout=` to every `requests.post`; short-circuit when the key is missing instead of sending a bogus header.

### 🟠 [S6] Unbounded auto-save on every generation
`generate.py:666-677` INSERTs a new row (full SVG/schema blob) on **every** `/generate`, no dedupe/cap/TTL; `list_projects` only ever surfaces 20. Unauthenticated write-amplifier + disk-exhaustion DoS on the free Render disk.
**Fix:** gate behind auth/opt-in; add retention/caps; stop storing full blobs per call.

### 🟠 [S7] SQLite misconfig: relative path, no WAL, ephemeral in prod
`project_store.py:10` `DB_FILE="plotit_projects.db"` is **relative to CWD** → two live copies depending on launch dir (`plotai` vs `plotit` naming is also half-migrated). No WAL/`busy_timeout` → `database is locked` under async concurrency. Render's disk is ephemeral → data lost every deploy; no migrations.
**Fix:** absolute module-anchored path; WAL + busy_timeout; move to the Postgres already templated in `.env.example` for prod.

### 🟡 [S8–S12] Hardening
- **[S8]** `requirements.txt` — 8 of 12 deps unpinned → non-reproducible builds / supply-chain risk. Pin `==` or add a lockfile (uv/pip-tools).
- **[S9]** Body-size middleware (`main.py:52`) only trusts `Content-Length`; chunked encoding bypasses it and the **WebSocket** (`stream.py:82`) has no size/rate limit at all. Bound `rooms`/`previous_layout` list lengths in Pydantic.
- **[S10]** Dockerfile runs as **root**, hardcodes `--port 8000` (ignores Render `$PORT`), no HEALTHCHECK, `COPY . .` bakes the leaked `.db`/`.env` into the image. Add non-root `USER`, `${PORT}`, healthcheck, and a `.dockerignore`.
- **[S11]** `render.yaml` declares only `PORT` — no `GROQ_API_KEY`/`ALLOWED_ORIGINS`/`DATABASE_URL`, so prod has no LLM key and no persistent DB. Declare env vars (`sync:false` for secrets) + managed Postgres.
- **[S12]** Rate limits only on `parse`/`generate`; `consultation` (LLM cost), `export` (CPU), `projects`, and the WS are unlimited. Behind Render's proxy `get_remote_address` may bucket all users together. Add limits + trusted-proxy config. Also DXF text injection: `dxf_exporter.py:97,195` write client `label` straight into DXF `TEXT` (a `\n` desyncs all group codes) — validate + strip.

---

## 3. Frontend & UX

### 🔴 [U1] WebSocket has no timeout → permanent "Generating…" hang
`plotit.js:27-63` + `Home.jsx:61-100`. If the backend accepts the socket but never sends `complete`/`error` (server stall, or a clean `close` code 1000 before `complete`), the Promise never settles → `isGenerating` stuck `true` forever, input disabled, no error, no retry. Only escape is a page reload.
**Fix:** timeout that rejects + `ws.close()`; treat premature clean-close as failure; drive the REST fallback on timeout.

### 🔴 [U2] Parse failure is a misleading dead-end
`Home.jsx:108-140`. Consultation only triggers on **HTTP 200 + `consultation.needed`**. The real deployment has no `GROQ_API_KEY`, so `/parse` 5xxs → generic `"Sorry, I couldn't process that. Please try again."` — a retry that can never succeed. (Interlocks with backend [S5]: the backend actually returns 200-with-consultation in some paths but errors in others — contract is inconsistent.)
**Fix:** distinguish network/5xx from validation; surface the real cause; make the backend consistently return 200-with-consultation, or let the frontend enter consultation manually on parse failure.

### 🟠 [U3] Any missing schema field crashes the **entire** main pane
`layers.jsx:91,198,213,307,383,484`, `BlueprintRenderer.jsx:13` deref `structural.beams.map`, `dimensionChains.overall_width`, `vastu_score.overall`, etc. with no guards. One missing field throws → the `ErrorBoundary` wrapping **all** of `main` (`Home.jsx:222`) trips → user loses canvas **and** header to "Something went wrong." Given backend [C3] emits partial schemas, this fires in practice.
**Fix:** null-guard each layer (`(structural?.beams||[]).map`, `vastu_score?.overall ?? 0`); scope the ErrorBoundary to just the canvas so chat/header survive.

### 🟠 [U4] Dead resume flow + [U5] XSS via raw SVG
- **[U4]** `consultationStore.js:63` `restoreDraft()` sets `isConsultationActive:true`, but the resume modal renders only when `pendingDraft && !isConsultationActive` (`Home.jsx:295`) — so it **never** shows; the app silently jumps back into mid-consultation questions with empty history. Fix: don't activate in `restoreDraft`; activate on the user's "Resume" click.
- **[U5]** `InteractiveCanvas.jsx:361` injects backend `blueprintSvg` via `dangerouslySetInnerHTML` unsanitized. SVG carries `<script>`/`onload`; if the prompt is ever echoed into the title block, that's reflected XSS. Fix: DOMPurify (`USE_PROFILES:{svg:true}`) or drop the raw-SVG path and always render the JSON schema.

### 🟡 [U6–U12] UX / correctness
- **[U6]** `InteractiveCanvas.jsx:185` renders `<Bot/>` but never imports it → ReferenceError → ErrorBoundary the moment generation starts with no prior blueprint. Add the import.
- **[U7]** Send box stays live during consultation (`ChatInterface.jsx:64` ignores `isConsultationActive`) → double-submit clobbers questions/answers. Disable while consulting.
- **[U8]** WebSocket never closed on reset/unmount (`plotit.js`) → socket leak; a stale stream can repopulate a just-cleared canvas. Return an abort/close handle.
- **[U9]** `recommendRooms` sends `orientation` (`plotit.js:69`) but the store only holds `entry_direction` → backend gets `undefined`; recommendations use default orientation.
- **[U10]** No responsive layout — fixed 280px+320px panels in `w-screen overflow-hidden` (`DashboardLayout.jsx`, `SplitScreenView.jsx`) → desktop-only; canvas crushed on tablet/phone.
- **[U11]** Accessibility: header nav items are `div`s with `onClick` (`Home.jsx:229`), icon buttons unlabeled, resume modal has no `role="dialog"`/focus-trap/Esc. Keyboard & screen-reader users blocked.
- **[U12]** WS success path never drives progress to 100% (only REST fallback does, `Home.jsx:92`); dense-plan label/dimension overlap has no decluttering (`layers.jsx:144-190`); `activeFloor` not reset on `handleReset` → blank canvas switching between multi/single-floor plans.

### ⚪ [U13] Cleanups
`store/test_store.js` (a CommonJS `child_process` script) shipped in `src/`; ~15 stray `console.log/warn/error`; unused imports/refs (`parsedPlotDataRef`, `hasPromptDims`, `Layers/History/Settings`, exported-but-unused `StaircaseSymbol`/`LiftSymbol`); export raster drops embedded fonts and has no `onerror`.

---

## 4. Architecture, testing & repo hygiene

### 🔴 [A1] The "master" test suite can't import — zero coverage where it matters
`tests/run_master_test_suite.py:12-13` imports `services.layout_engine` (never existed) and `services.svg_renderer` (deleted). The whole suite fails at import — **nothing runs**. Anyone treating it as a green gate is protected by nothing. Meanwhile the last **three commits** are all "fix 500/NameError/TypeError in generate route" — regressions are caught in prod, not CI.
**Fix:** delete or rewrite against the real pipeline; add the integration test in [A2].

### 🔴 [A2] Core pipeline has no automated coverage; frontend has one `1+1==2` test
~10k LOC of layout logic (`constraint_solver`, `building_program` 1103 LOC, `geometry_processor`, `schema_serializer`) has no integration test asserting a valid, non-overlapping, in-bounds floor plan. Frontend suite is literally `expect(1+1).toBe(2)` (`Simple.test.js`).
**Fix:** one end-to-end test — `POST /generate` with a fixed payload asserting: no overlaps, all rooms in bounds, doors connect, non-empty schema, **`rooms_placed == rooms requested`** (would have caught [C1]). Add store + API-client + `BlueprintRenderer` smoke tests on the frontend.

### 🟠 [A3] 704-line god-route + duplicated pipeline in `stream.py`
`generate.py:112` is one ~590-line function (parse→…→serialize) with 9 inline try/excepts — untestable, and the direct cause of the recurring "NameError → 500" class. `stream.py:169-308` is a **near-duplicate** of the same pipeline that has **already drifted** (diff/proportion wired differently). Every fix must be applied twice.
**Fix:** extract a `PipelineOrchestrator` returning a typed result; the route becomes ~30 lines; `stream.py` wraps it with progress events. This structurally kills the 500 class and the double-maintenance.

### 🟠 [A4] Five copies of unit constants; tolerance dupes defeat `constants.py`
`FT_TO_M`/`M_TO_FT` redefined in `generate.py:229`, `stream.py:169`, `site_context_engine.py:180`, `building_program.py:999` (`/0.3048`), `nlp_parser.py:21`. `diff_engine.py:96` redeclares `POSITION_TOLERANCE`/`SIZE_TOLERANCE` that `constants.py:25` **already defines "for the diff engine"**; `circulation_engine.py:27` ditto. A precision/direction fix in one silently leaves the others wrong.
**Fix:** single source in `services/constants.py`; import everywhere.

### 🟡 [A5] Dead code, orphaned service, print-debugging
- `label_placer.py` is **fully orphaned** (only its own test imports it) — delete it + test.
- `generate.py` has **24 `print()`** calls (emoji, needs the stdout UTF-8 patch) where `logger` exists — route through logging.
- Deprecated `@app.on_event("startup")` (`main.py:67`) and `datetime.utcnow()` (`project_store.py:35`) — migrate to `lifespan` / `datetime.now(timezone.utc)`.
- Dead SVG-format branches (`generate.py:524-528,662-664`) always 400 — remove.

### 🟡 [A6] Repo junk (commit the good deletions, extend the sweep)
The uncommitted deletions of `patch_renderer*`, `restore_renderer*`, `*_cleanup.py`, shims, old SVG renderers are **correct — commit them now.** Then extend: delete `debug/` (~1.2 MB incl. a 1.1 MB `file_structure.txt`), `tmp/` (`trigger_500.py`, `fix_renderer.py`), `backend/scratch/`, `stitch_design/` + `stitch_plotai_redesign_system.zip` (737 KB), stale `*_output.txt`, and move/删 `antigravity_workflow.md` (43 KB). Add `.gitignore`: `*.db *.zip tmp/ scratch/ *_output.txt *.log`.

---

## Phased roadmap

### Phase 0 — Stop the bleeding (½ day, do first)
Security/hygiene that's pure downside if left: **[S1]** untrack DBs, **[S3]** untrack `frontend/.env` + gitignore sweep **[A6]**, commit the good deletions. No logic risk.

### Phase 1 — Fix the core output (1–2 days) ← **highest ROI**
**[C1] [C2] [C4]** — the roof-floor bug, the setback/Sun bug, the accessibility gate. Turns `rooms=3/score=49/Sun=0` into representative numbers. Add **[A2]**'s one integration test asserting `rooms_placed == requested` to lock it. **[C3]** stop swallowing errors so the next regression is visible.

### Phase 2 — Deploy-safe (2–3 days)
**[S2]** CORS, **[S3]** auth + `owner_id` + IDOR, **[S4]** error leakage, **[S5]** LLM key validation + timeouts, **[S7]** DB path/WAL/Postgres, **[S10/S11]** Docker + render.yaml. Now it can face the internet.

### Phase 3 — Layout quality & determinism (3–4 days)
**[C5]** wire Vastu ids, **[C6]** seed the solver, **[C7]** buildable-area feasibility, **[C8]** soft constraints (biggest quality lever), **[C10–C13]** annotation/coord/strip-fill fixes.

### Phase 4 — Frontend robustness (2–3 days)
**[U1]** WS timeout, **[U2]** parse dead-end, **[U3]** layer guards + scoped ErrorBoundary, **[U5]** sanitize SVG, **[U6/U7/U8]** Bot import / double-submit / socket leak, then **[U9–U12]** UX polish.

### Phase 5 — Structural cleanup (3–5 days)
**[A3]** extract the orchestrator + dedupe `stream.py`, **[A4]** central constants, **[A1]** fix/replace master suite, **[A5]** dead code + logging, **[S6/S8/S9/S12]** remaining hardening. Expand test coverage as you go.

---

## Highest-leverage moves, ranked
1. **[C1]** roof-floor selection — one line, fixes `rooms_placed` and every score. _(Phase 1)_
2. **[C2]+[C4]** setback frame + accessibility gate — restores Sun and lifts the 49 cap. _(Phase 1)_
3. **[A2]** one `rooms_placed == requested` integration test — locks 1&2, would've caught the last 3 prod bugs. _(Phase 1)_
4. **[S1]+[S3]** untrack DBs and `.env`, add auth — stops data leakage/IDOR. _(Phase 0/2)_
5. **[A3]** decompose the god-route — structurally ends the recurring 500 class. _(Phase 5, but every phase gets easier after it)_
6. **[C8]** soft solver constraints — the biggest lever on actual layout *quality*. _(Phase 3)_
