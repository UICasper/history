"""FastAPI backend for the dashboard: serves each day's package.json + files,
lets the mobile UI toggle publish status, and re-runs a stage (and everything
downstream of it) on demand.
"""

import sys
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pipeline import (
    stage1_pick_object,
    stage2_generate_script,
    stage3_assets,
    stage4_voice,
    stage5_render,
    stage6_thumbnails,
    stage7_package,
)
from pipeline.utils.cache import output_dir_for
from pipeline.utils.config import ROOT, get_env, load_config

app = FastAPI(title="What Is This Thing? Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_ROOT = ROOT / load_config()["paths"]["output_dir"]


def require_token(authorization: Optional[str] = Header(None)) -> None:
    expected = get_env("DASHBOARD_TOKEN", required=False)
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="invalid or missing token")


def _parse_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")


def _package_path(d: date) -> Path:
    return output_dir_for(d) / "package.json"


@app.get("/api/days")
def list_days(_: None = Depends(require_token)):
    if not OUTPUT_ROOT.exists():
        return []
    days = sorted(
        (p.name for p in OUTPUT_ROOT.iterdir() if p.is_dir() and (p / "package.json").exists()),
        reverse=True,
    )
    return days


@app.get("/api/days/{date_str}/package")
def get_package(date_str: str, _: None = Depends(require_token)):
    d = _parse_date(date_str)
    path = _package_path(d)
    if not path.exists():
        raise HTTPException(status_code=404, detail="no package for this date yet")
    import json

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class PublishStatusUpdate(BaseModel):
    status: str  # "posted" | "not_posted"


@app.post("/api/days/{date_str}/publish-status")
def set_publish_status(date_str: str, body: PublishStatusUpdate, _: None = Depends(require_token)):
    if body.status not in ("posted", "not_posted"):
        raise HTTPException(status_code=400, detail="status must be 'posted' or 'not_posted'")
    d = _parse_date(date_str)
    path = _package_path(d)
    if not path.exists():
        raise HTTPException(status_code=404, detail="no package for this date yet")
    import json

    with open(path, "r", encoding="utf-8") as f:
        package = json.load(f)
    package["publish_status"] = body.status
    with open(path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)
    return package


class MetadataUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    pinned_comment: Optional[str] = None


@app.post("/api/days/{date_str}/metadata")
def update_metadata(date_str: str, body: MetadataUpdate, _: None = Depends(require_token)):
    d = _parse_date(date_str)
    path = _package_path(d)
    if not path.exists():
        raise HTTPException(status_code=404, detail="no package for this date yet")
    import json

    with open(path, "r", encoding="utf-8") as f:
        package = json.load(f)
    if body.title is not None:
        package["metadata"]["title_options"][0] = body.title
    if body.description is not None:
        package["metadata"]["description"] = body.description
    if body.tags is not None:
        package["metadata"]["tags"] = body.tags
    if body.pinned_comment is not None:
        package["metadata"]["pinned_comment"] = body.pinned_comment
    with open(path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)
    return package


STAGE_ORDER = ["object", "script", "assets", "voice", "render", "thumbnails", "package"]


def _run_pipeline_from(from_stage: str, d: date) -> dict:
    start_index = STAGE_ORDER.index(from_stage)

    s1 = stage1_pick_object.run(run_date=d, force=start_index <= 0)
    s2 = stage2_generate_script.run(s1, run_date=d, force=start_index <= 1)
    s3 = stage3_assets.run(s1, s2, run_date=d, force=start_index <= 2)
    try:
        s4 = stage4_voice.run(s2, run_date=d, force=start_index <= 3)
    except Exception:
        s4 = None
    s5 = stage5_render.run(s1, s2, s3, s4, run_date=d, force=start_index <= 4)
    s6 = stage6_thumbnails.run(s3, s2["thumbnail_text_options"], run_date=d, force=start_index <= 5)
    package = stage7_package.run(s1, s2, s5, s6, run_date=d, force=True)
    return package


class RegenerateRequest(BaseModel):
    stage: str  # one of STAGE_ORDER


@app.post("/api/days/{date_str}/regenerate")
def regenerate(date_str: str, body: RegenerateRequest, _: None = Depends(require_token)):
    if body.stage not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"stage must be one of {STAGE_ORDER}")
    d = _parse_date(date_str)
    return _run_pipeline_from(body.stage, d)


# ---------------------------------------------------------- Art Explainer --

def _art_package_path(d: date, index: int) -> Path:
    return output_dir_for(d) / "art" / str(index) / "package.json"


@app.get("/api/art/days")
def list_art_days(_: None = Depends(require_token)):
    if not OUTPUT_ROOT.exists():
        return []
    days = sorted(
        (p.name for p in OUTPUT_ROOT.iterdir() if p.is_dir() and (p / "art").exists()),
        reverse=True,
    )
    return days


@app.get("/api/art/days/{date_str}")
def get_art_day(date_str: str, _: None = Depends(require_token)):
    import json

    d = _parse_date(date_str)
    art_dir = output_dir_for(d) / "art"
    if not art_dir.exists():
        raise HTTPException(status_code=404, detail="no art pieces for this date yet")
    items = []
    for sub in sorted(art_dir.iterdir(), key=lambda p: p.name):
        pkg_path = sub / "package.json"
        if pkg_path.exists():
            with open(pkg_path, "r", encoding="utf-8") as f:
                items.append(json.load(f))
    return items


class ArtPublishStatusUpdate(BaseModel):
    status: str  # "posted" | "not_posted"


@app.post("/api/art/days/{date_str}/{index}/publish-status")
def set_art_publish_status(date_str: str, index: int, body: ArtPublishStatusUpdate, _: None = Depends(require_token)):
    if body.status not in ("posted", "not_posted"):
        raise HTTPException(status_code=400, detail="status must be 'posted' or 'not_posted'")
    d = _parse_date(date_str)
    path = _art_package_path(d, index)
    if not path.exists():
        raise HTTPException(status_code=404, detail="no art package for this date/index yet")
    import json

    with open(path, "r", encoding="utf-8") as f:
        package = json.load(f)
    package["publish_status"] = body.status
    with open(path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)
    return package


class ArtRegenerateRequest(BaseModel):
    stage: str  # one of ART_STAGE_ORDER


ART_STAGE_ORDER = ["pick", "assets", "script", "voice", "render", "thumb", "package"]


@app.post("/api/art/days/{date_str}/{index}/regenerate")
def regenerate_art(date_str: str, index: int, body: ArtRegenerateRequest, _: None = Depends(require_token)):
    if body.stage not in ART_STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"stage must be one of {ART_STAGE_ORDER}")
    from pipeline import art_pipeline

    d = _parse_date(date_str)
    start_index = ART_STAGE_ORDER.index(body.stage)

    s1 = art_pipeline.pick_painting(index, run_date=d, force=start_index <= 0)
    s3 = art_pipeline.gather_assets(index, s1, run_date=d, force=start_index <= 1)
    s2 = art_pipeline.generate_script(index, s1, s3, run_date=d, force=start_index <= 2)
    try:
        s4 = art_pipeline.synthesize_voice(index, s2, run_date=d, force=start_index <= 3)
    except Exception:
        s4 = None
    s5 = art_pipeline.render_video(index, s2, s3, s4, run_date=d, force=start_index <= 4)
    s6 = art_pipeline.render_thumbnail(index, s3, s2["thumbnail_text_options"], run_date=d, force=start_index <= 5)
    return art_pipeline.assemble_package(index, s1, s2, s5, s6, run_date=d, force=True)


if OUTPUT_ROOT.exists():
    app.mount("/files", StaticFiles(directory=str(OUTPUT_ROOT)), name="files")

FRONTEND_DIR = ROOT / "dashboard" / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
