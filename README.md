# What Is This Thing?

Daily automated pipeline that turns one CC0 museum object into a ready-to-upload
YouTube content package (long video + Shorts + thumbnails + metadata), viewable
from a mobile dashboard. YouTube upload is manual -- this project never calls
the YouTube API.

## Status

All 5 phases are implemented (stages 1-7 + dashboard + scheduling). Everything
that doesn't require a paid/keyed API has been tested end-to-end against real
data:

- **Stage 1** (pick object) -- Met API tested live; the LLM pick step needs
  `GEMINI_API_KEY`.
- **Stage 2** (script + metadata) -- needs `GEMINI_API_KEY`.
- **Stage 3** (assets: images, crops, comparisons, illustrations, rembg) --
  fully tested end-to-end. Illustrations fall back to the free, no-key
  Pollinations API when `GEMINI_API_KEY` is absent (watermarked; Gemini's own
  image gen is watermark-free once a key is added).
- **Stage 4** (ElevenLabs voice + word timestamps) -- needs `ELEVENLABS_API_KEY`.
- **Stage 5** (Remotion render) -- fully tested end-to-end with a synthetic
  shot list and placeholder audio. See "A note on rendering" below.
- **Stage 6** (thumbnails + Shorts cover) -- fully tested end-to-end, no API
  needed (Pillow + a bundled font).
- **Stage 7** (package.json) -- fully tested end-to-end.
- **Dashboard** (FastAPI + plain HTML/JS) -- fully tested end-to-end against
  real stage output (today view, copy buttons, publish toggle, regenerate).
- **Scheduling** -- Windows Task Scheduler script and a GitHub Actions
  workflow are provided; neither has been run on a live schedule yet.

## A note on rendering

Remotion's bundled `ffmpeg`/`ffprobe` binaries crash on this machine --
Windows Smart App Control blocks them. Rather than touch that OS policy,
`pipeline/stage5_render.py` only asks Remotion for a still-frame (PNG)
sequence -- which uses Remotion's Rust compositor, not its bundled ffmpeg --
and encodes/muxes everything (video + voice + ducked music + chapter SFX)
with the system `ffmpeg`. This is more portable anyway (it's exactly what
happens on the GitHub Actions runner too) so it's the permanent design, not a
temporary hack. It does mean the system `ffmpeg` (confirmed present on this
machine) is a hard requirement, on top of what `requirements.txt` installs.

## Setup

1. Python 3.12+, Node 24+, git, **ffmpeg** (system-installed, on PATH) --
   all already required to be on PATH.
2. Create the virtualenv and install Python dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. Install Remotion's dependencies:
   ```powershell
   cd remotion
   npm install
   cd ..
   ```
4. Copy `.env.example` to `.env` and fill in the keys you have:
   ```powershell
   Copy-Item .env.example .env
   ```
   - `GEMINI_API_KEY` -- required for stages 1-2 (get one free at ai.google.dev).
   - `GROQ_API_KEY` -- optional fallback LLM, not wired up yet.
   - `ELEVENLABS_API_KEY` -- required for stage 4 (voice). This is the only
     paid service in the whole project.
   - `SMITHSONIAN_API_KEY`, `RIJKSMUSEUM_API_KEY` -- optional, only needed if
     you want candidates from those museums in addition to The Met (which
     needs no key).
   - `DASHBOARD_TOKEN` -- optional; if set, the dashboard API requires it as
     a Bearer token (the frontend reads it from `localStorage.dashboardToken`).

## Config

`config/config.json` is the single source of truth for schedule time, video
dimensions, pacing, illustration counts, brand fonts/colors, and which
LLM/image/museum providers are primary vs. fallback. Edit it directly; no
code changes needed for most tuning. Brand fonts (Anton + Work Sans, both
OFL-licensed) are already bundled under `assets/fonts/`.

## Running the full pipeline

```powershell
.\.venv\Scripts\python.exe -m pipeline.run              # today
.\.venv\Scripts\python.exe -m pipeline.run --date 2026-09-20
.\.venv\Scripts\python.exe -m pipeline.run --force       # ignore all caches
```

## Running a stage manually

Each stage is idempotent: it caches its output to
`output/<YYYY-MM-DD>/<stage_name>.json` and skips recomputation unless called
with `force=True`. A run's log is at `output/<YYYY-MM-DD>/run.log`.

```powershell
.\.venv\Scripts\python.exe -m pipeline.stage1_pick_object      # pick today's object
.\.venv\Scripts\python.exe -m pipeline.stage2_generate_script  # script + metadata
.\.venv\Scripts\python.exe -m pipeline.stage3_assets           # images/crops/illustrations/rembg
.\.venv\Scripts\python.exe -m pipeline.stage4_voice            # ElevenLabs voice + timestamps
.\.venv\Scripts\python.exe -m pipeline.stage5_render           # Remotion render + ffmpeg mux
.\.venv\Scripts\python.exe -m pipeline.stage6_thumbnails       # thumbnails + Shorts cover
.\.venv\Scripts\python.exe -m pipeline.stage7_package          # assemble package.json
```

Re-running a stage command re-picks/regenerates only that stage; downstream
stages will pick up the new cached input the next time they run. The
dashboard's per-stage "Regenerate" buttons do the same thing over the API.

## Dashboard

```powershell
.\.venv\Scripts\python.exe -m uvicorn dashboard.backend.main:app --port 8420
```

Open `http://localhost:8420/` (mobile-width viewport recommended). The
FastAPI app serves the API, the day's output files (`/files/<date>/...`),
and the frontend itself, all from one origin. To deploy the frontend
separately (e.g. Cloudflare Pages) as static-only, point
`dashboard/frontend/app.js`'s `API_BASE` at your backend's URL instead.

## Scheduling

- **Windows Task Scheduler** (this machine): `powershell -File
  scripts\schedule_windows_task.ps1` registers a daily task at the time set
  in `config/config.json` (`schedule.time`).
- **GitHub Actions** (alternative): `.github/workflows/daily.yml` runs on a
  cron schedule (edit the UTC hour to match your timezone) or via manual
  dispatch. Add your API keys as repo secrets with the same names as in
  `.env.example`. It uploads `output/` as a build artifact each run, and
  also publishes the static dashboard (see next section).

## Viewing the dashboard from your phone, anywhere

The FastAPI dashboard (`dashboard/backend/main.py`) only runs on whatever
machine you start it on -- fine on the same WiFi network, not reachable from
outside it. To get a link that works from your phone anywhere, with no PC
needing to be on: `scripts/build_static_site.py` copies the frontend plus
each recent day's `package.json` + video/thumbnail files (the last 14 days,
oldest pruned automatically) into `docs/`, which the daily GitHub Actions
workflow commits and pushes automatically. Enable it once:

1. Push this repo to GitHub.
2. Repo Settings -> Pages -> Source: "Deploy from a branch" -> Branch:
   `main`, folder: `/docs`.
3. After the next scheduled (or manually dispatched) workflow run, your
   dashboard is at `https://<you>.github.io/<repo>/`.

This static copy is **read-only**: the frontend detects there's no live API
behind it (`STATIC_MODE` in `app.js`) and disables the publish-status
toggle, metadata editing, and regenerate buttons -- you can still watch/
download videos and thumbnails and copy titles/description/tags/pinned
comment, which covers the actual on-the-go use case (grab the files, paste
the metadata into the YouTube app). Do the rest (toggling publish status,
regenerating a stage) from the live local dashboard. To preview the static
build locally before pushing: `python -m scripts.build_static_site` then
serve `docs/` with any static file server.

## Repo layout

```
config/             brand + schedule config (config.json)
pipeline/            Python pipeline
  clients/           museum API / Gemini / ElevenLabs / image-gen / ffmpeg clients
  utils/              config loading, per-stage disk cache, logging, used-objects tracking
  stageN_*.py         one file per pipeline stage (1-7)
  run.py              daily orchestrator (stage1 -> stage7)
  schemas.py          pydantic schemas for structured LLM output
data/
  used_objects.json   running list of objects already featured, never repeated
remotion/             Remotion (React) render project -- picture only, see "A note on rendering"
dashboard/
  backend/            FastAPI (main.py)
  frontend/            plain HTML/JS, mobile-first
assets/               brand fonts (bundled), CC0 music/SFX (drop your own into assets/audio/)
scripts/               scheduling helpers (Windows Task Scheduler) + build_static_site.py
.github/workflows/     GitHub Actions daily schedule (alternative) + static-site publish
docs/                  static (read-only) dashboard build for GitHub Pages -- generated, committed by CI
output/YYYY-MM-DD/     per-day stage cache + final content package (gitignored)
```
