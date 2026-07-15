---
name: run-plot-ai
description: Build, launch, and drive the PlotIt app (FastAPI backend + Vite/React frontend). Use when asked to run, start, serve, smoke-test, or screenshot PlotIt / plot-ai, or to confirm a backend generate/parse or blueprint change works in the real running app.
---

# Run PlotIt

PlotIt turns a natural-language prompt into a 2D architectural blueprint. Two
processes: a **FastAPI backend** (`backend/`, port 8000) that runs the CP-SAT
layout pipeline, and a **Vite/React frontend** (`frontend/`, port 5173). Most
changes land in the backend `/generate` pipeline, so the primary driver is an
HTTP smoke test; a headless-Chrome screenshot proves the SPA still renders.

Paths below are relative to the repo root (`E:\Projects\plot-ai`). Windows +
Git Bash. The driver lives at `.claude/skills/run-plot-ai/driver.mjs`.

## Prerequisites

- Python venv already exists at `backend/venv` with all deps (ortools, fastapi,
  uvicorn, shapely, networkx, cairosvg). A second identical venv exists at
  `.venv` — either works.
- `frontend/node_modules` already installed (Node v22, npm).
- Google Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`
  (used headless for screenshots). Edge is a fallback.
- No API keys required for `/generate` — it works from structured input. Only
  `/parse` calls Groq; without `GROQ_API_KEY` it degrades to consultation mode
  (still HTTP 200). `backend/.env` exists with empty keys, which is fine.

## Build

No build step needed to run — deps come pre-installed and were used as-is this
session. The commands below are the clean-machine recovery path (not exercised
here, since both venvs and `node_modules` already existed):

```bash
# backend (only if venv is missing)
cd backend && python -m venv venv && ./venv/Scripts/python.exe -m pip install -r requirements.txt

# frontend (only if node_modules is missing)
cd frontend && npm install
```

## Run (agent path)

Start both servers in the background, then run the driver.

```bash
# 1. Backend — bind 127.0.0.1 so curl/fetch reach it
cd backend && ./venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 &
# wait ~5s, then confirm:
curl -s http://127.0.0.1:8000/health

# 2. Frontend — Vite binds IPv6 [::1]; reach it via localhost (NOT 127.0.0.1)
cd frontend && npm run dev &
# wait ~5s, then confirm:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/
```

With both up, drive the app:

```bash
node .claude/skills/run-plot-ai/driver.mjs          # backend smoke + screenshot
node .claude/skills/run-plot-ai/driver.mjs smoke    # backend HTTP smoke only
node .claude/skills/run-plot-ai/driver.mjs shot      # screenshot only
```

Expected output:

```
Backend smoke @ http://127.0.0.1:8000
  ✓ /health -> v4.0.0, 12 features
  ✓ /styles -> 8 presets
  ✓ /generate -> engine=cpsat_feasible, rooms=3, floors=2, score=49
  ✓ /parse -> success (consultation.needed=true, GROQ key absent = expected)
Backend smoke PASSED

Screenshot @ http://localhost:5173
  ✓ wrote .claude/skills/run-plot-ai/scratch/plotai-home.png
```

The screenshot lands in `.claude/skills/run-plot-ai/scratch/` (gitignored).
**Open the PNG** — a correct render is the dark CAD UI with "NO BLUEPRINT
LOADED" in the canvas and two example prompt chips in the left panel.

Driver env overrides: `API=`, `WEB=`, `CHROME=`, `OUT=`.

## Direct invocation (backend, no server)

Most backend PRs touch the `/generate` pipeline. To exercise it without HTTP,
call the route function directly. The `@limiter` decorator demands a real
Starlette `Request` (a stub throws), and the pipeline prints emoji so you need
`PYTHONIOENCODING=utf-8` or Windows cp1252 stdout crashes mid-run:

```bash
cd backend && PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -c "
import asyncio
from starlette.requests import Request
from routes.generate import generate_blueprint_endpoint, GenerateRequest, RoomConfig
scope = {'type':'http','method':'POST','path':'/api/v1/generate','headers':[],'client':('127.0.0.1',12345),'query_string':b''}
req = Request(scope)
gr = GenerateRequest(plot_size_sqft=1200, floors=1, prompt='1200 sqft 2BHK north',
  rooms=[RoomConfig(type='bedroom', count=2), RoomConfig(type='kitchen', count=1)])
out = asyncio.run(generate_blueprint_endpoint(req, gr))
print('RESULT', out['success'], out['data']['engine'], out['data']['rooms_placed'])
"
```

(This auto-saves a project row to `backend/plotit_projects.db` as a side effect.)

## Run (human path)

`cd backend && uvicorn main:app --reload` then `cd frontend && npm run dev`, and
open http://localhost:5173 in a browser. Ctrl-C each to stop. Useless for
automated verification (needs a human at the window) — use the driver instead.

## Test

```bash
# backend suite — pytest lives in the ROOT .venv, not backend/venv
cd backend && PYTHONIOENCODING=utf-8 ../.venv/Scripts/python.exe -m pytest tests/ -q
cd frontend && npm test -- --run                               # vitest (one-shot)
```

Backend: `59 passed` in ~24s. Note the emoji logs need `PYTHONIOENCODING=utf-8`
on Windows here too.

## Gotchas

- **Vite binds IPv6 only.** The dev server listens on `[::1]:5173`, so
  `curl http://127.0.0.1:5173` returns nothing (exit 7 / HTTP 000). Use
  `http://localhost:5173`. The driver already targets `localhost`.
- **`/generate` needs no API key; `/parse` does.** The layout pipeline is fully
  offline (CP-SAT). Only NLP parsing hits Groq. With no key, `/parse` still
  returns HTTP 200 but forces `consultation.needed=true` — that's expected, not
  a failure. Don't chase it as a bug.
- **`rooms_placed` can be less than rooms requested.** The solver places what
  fits the buildable envelope after setbacks; a 1200 sqft 2BHK reports
  `rooms=3, floors=2` (ground + roof auto-added). Non-zero is the pass signal,
  not an exact count.
- **Windows Python can't read Git Bash `/tmp`.** When capturing curl output for
  the venv Python to parse, write to a real path like `backend/scratch/`, not
  `/tmp/...` — the MSYS `/tmp` is invisible to the native `python.exe`.
- **Backend must bind `127.0.0.1`, not `0.0.0.0`,** for local curl to connect
  reliably on this Windows host. The Dockerfile uses `0.0.0.0` (correct for
  containers) but locally prefer `127.0.0.1`.
- **Unicode logs.** The backend prints emoji (🏛️ 📐 ✅) to stdout; `main.py`
  reconfigures stdout to UTF-8 so this works on Windows consoles. If you pipe
  logs somewhere that chokes on UTF-8, that's the source.

## Troubleshooting

- `curl /health` → connection refused: uvicorn didn't start. Check the backend
  log; a missing dep (ortools/shapely) means the wrong Python — use
  `backend/venv/Scripts/python.exe`, not a system Python.
- Driver `✗ /health unreachable`: backend not running or bound to the wrong
  host. Restart it with `--host 127.0.0.1 --port 8000`.
- Driver `✗ no Chrome/Edge found`: pass `CHROME=/c/Program\ Files/...` or set
  the `CHROME` env var to your browser's `.exe`.
- Screenshot is blank/white: the frontend isn't up or is on another port. Confirm
  `curl -w '%{http_code}' http://localhost:5173/` returns 200 first.
