"""Art Explainer: a second, separate content stream from the same channel --
two short (1-2 minute) videos per day, each covering ONE real painting from
a museum collection end to end. Every image is a real photo of the actual
painting (crops/pans across it); nothing here is AI-generated.

Reuses the main pipeline's plumbing where the shapes line up: Gemini for the
script, edge-tts for voice, the same Remotion "Shorts" composition (already
1080x1920) for rendering, and the main pipeline's low-level render/thumbnail
helpers -- so this file is mostly picking real paintings and wiring existing
pieces together, not reimplementing them.
"""

import random
from datetime import date
from typing import Optional

import requests
from PIL import Image

from .clients import met_api
from .clients.edge_tts_client import synthesize_with_word_timestamps
from .clients.llm_client import generate_structured
from .schemas import ArtPackage, ObjectPick
from .stage3_assets import _detail_crops, _download_image, _save_image
from .stage5_render import (
    _build_pools,
    _chapter_cue_seconds,
    _encode_sequence,
    _mux_audio,
    _prepare_audio_files,
    _render_sequence,
    _resolve_shot_image,
    _synthetic_word_timestamps,
)
from .stage6_thumbnails import _render_shorts_cover
from .utils.cache import load_stage, output_dir_for, save_stage
from .utils.config import ROOT, load_config
from .utils.logging import get_logger
from .utils.used_objects import is_used, mark_used

MUSEUM = "met"
DEPARTMENT_ID = 11  # European Paintings
SEARCH_TERMS = [
    "portrait", "landscape", "still life", "self-portrait", "battle",
    "mythology", "religious painting", "seascape", "royal portrait",
    "genre scene", "allegory", "interior scene",
]
CANDIDATE_POOL_SIZE = 20
REMOTION_DIR = ROOT / "remotion"


# ---------------------------------------------------------------- stage 1 --

def _is_usable_painting(obj: dict) -> bool:
    classification = (obj.get("classification") or "").lower()
    return bool(
        obj.get("isPublicDomain")
        and obj.get("primaryImage")
        and (obj.get("title") or obj.get("objectName"))
        and "painting" in classification
    )


def _gather_painting_candidates() -> list:
    ids: list = []
    terms = random.sample(SEARCH_TERMS, k=len(SEARCH_TERMS))
    for term in terms:
        try:
            ids.extend(met_api.search_object_ids(term, department_id=DEPARTMENT_ID))
        except requests.RequestException:
            continue
        if len(ids) >= CANDIDATE_POOL_SIZE * 4:
            break
    random.shuffle(ids)

    candidates = []
    for object_id in ids:
        if is_used(MUSEUM, object_id):
            continue
        try:
            obj = met_api.get_object(object_id)
        except requests.RequestException:
            continue
        if _is_usable_painting(obj):
            candidates.append(obj)
        if len(candidates) >= CANDIDATE_POOL_SIZE:
            break
    return candidates


def pick_painting(index: int, run_date: Optional[date] = None, force: bool = False) -> dict:
    stage_name = f"art{index}_pick"
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(stage_name, run_date)
        if cached is not None:
            logger.info("art%d: using cached painting pick", index)
            return cached

    logger.info("art%d: gathering painting candidates from The Met API", index)
    candidates = _gather_painting_candidates()
    if not candidates:
        raise RuntimeError(f"art{index}: no usable painting candidates found")
    logger.info("art%d: %d usable candidates found", index, len(candidates))

    summaries = [met_api.summarize_for_llm(c) for c in candidates]
    prompt = (
        "You are choosing ONE real painting to feature in a short (1-2 minute) "
        "art-explainer video for a general, curious, English-speaking audience. "
        "Pick the single most visually striking or story-rich painting from the "
        "list below -- one with interesting technique, symbolism, hidden "
        "details, or a memorable story about the artist or subject.\n\n"
        f"Candidates (JSON):\n{summaries}\n\n"
        "Respond with the chosen object's object_id and a one-line reason."
    )
    pick = generate_structured(prompt, ObjectPick)
    logger.info("art%d: LLM picked object_id=%s reason=%s", index, pick.chosen_object_id, pick.reason)

    chosen = next((c for c in candidates if c.get("objectID") == pick.chosen_object_id), None)
    if chosen is None:
        logger.warning("art%d: LLM returned an id not in the candidate list, using first candidate", index)
        chosen = candidates[0]
        pick.chosen_object_id = chosen["objectID"]

    result = {"museum": MUSEUM, "object": chosen, "pick_reason": pick.reason}
    save_stage(stage_name, result, run_date)
    mark_used(MUSEUM, chosen["objectID"], chosen.get("title", ""), run_date)
    logger.info("art%d: done", index)
    return result


# ---------------------------------------------------------------- stage 2 --

ART_PROMPT_TEMPLATE = """\
You are writing the script and YouTube metadata for one episode of a daily
"Art Explainer" series: a fast, engaging 1-2 minute walkthrough of ONE real
painting for a curious, general, English-speaking audience. Tone: punchy,
vivid, no fluff -- pack in as many genuinely interesting facts as fit.

The painting (JSON):
{object_json}

Why this painting was chosen: {pick_reason}

Write ALL of the following in one response:

1. script: a spoken narration script, {word_min}-{word_max} words, for a
   {duration_min}-{duration_max} second video.

   The FIRST sentence is the hook and must stand alone: 6-12 words, spoken
   in under 3 seconds, with zero setup. Do not name the painting, the
   artist, or say anything like "this painting" / "today" / "let's look
   at" -- open with the single most shocking claim, a direct question to
   the viewer, or an unresolved detail, phrased so a scrolling viewer
   would stop mid-scroll and feel like they CANNOT look away or skip this
   one. Make it feel urgent and personal, not like a museum caption.
   ("A man was murdered for owning this." / "Look closely -- someone is
   stealing from him right now." / "This 'saint' is actually a self-
   portrait of the artist." / "You've seen this painting your whole
   life and missed this.") Only after that hook lands do you reveal what
   the painting is.

   After the hook, cover quickly and in this rough order: artist + date,
   the subject/story, technique or materials, one hidden detail or symbol
   worth zooming into, and a short closing line (a punchy final fact or a
   question back to the viewer -- never "thanks for watching" or any
   sign-off). Keep every sentence tight -- this is a rapid-fire highlight
   reel, not a lecture.

2. title_options: exactly 3 title options.

3. description: a YouTube description, 2-4 sentences, end with hashtags.

4. tags: comma-separated YouTube tags.

5. pinned_comment: a short pinned comment inviting engagement.

6. thumbnail_text_options: 3 short (2-4 word) high-contrast hook phrases,
   ALL CAPS.

7. shot_list: REQUIRED, and it must have {shot_count_min}-{shot_count_max}
   entries -- never just one or two. One entry per visual across the
   ENTIRE video, roughly every {pace_min}-{pace_max} seconds, so the image
   on screen keeps changing in sync with the script for its full length;
   a single static shot for the whole video is wrong even if the script
   is short. This video only ever shows THIS ONE real painting -- every shot
   is either the whole painting (asset_ref "main", motion "reveal") or a
   close crop of one region of it (asset_ref like "crop_03"). Pick motion
   (parallax / spotlight / annotation / reveal / static) per shot, exactly
   one per shot, never stacked, and never "data_animation" (not available
   here). Use "reveal" for the shot(s) showing the whole painting -- put one
   near the start. Use "parallax" at most once, only if the painting has a
   clear single foreground subject.
"""


def _build_art_prompt(object_data: dict, pick_reason: str) -> str:
    cfg = load_config()["art_explainer"]
    pace_min = cfg["seconds_per_visual_min"]
    pace_max = cfg["seconds_per_visual_max"]
    shot_count_min = max(6, int(cfg["duration_min_sec"] / pace_max))
    shot_count_max = max(shot_count_min + 2, int(cfg["duration_max_sec"] / pace_min))
    return ART_PROMPT_TEMPLATE.format(
        object_json=met_api.summarize_for_llm(object_data),
        pick_reason=pick_reason,
        word_min=cfg["target_word_count_min"],
        word_max=cfg["target_word_count_max"],
        duration_min=cfg["duration_min_sec"],
        duration_max=cfg["duration_max_sec"],
        pace_min=pace_min,
        pace_max=pace_max,
        shot_count_min=shot_count_min,
        shot_count_max=shot_count_max,
    )


def generate_script(index: int, stage_pick: dict, run_date: Optional[date] = None, force: bool = False) -> dict:
    stage_name = f"art{index}_script"
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(stage_name, run_date)
        if cached is not None:
            logger.info("art%d: using cached script", index)
            return cached

    logger.info("art%d: calling Gemini for script + metadata", index)
    prompt = _build_art_prompt(stage_pick["object"], stage_pick["pick_reason"])
    package: ArtPackage = generate_structured(prompt, ArtPackage)

    result = package.model_dump()
    save_stage(stage_name, result, run_date)
    logger.info("art%d: done (script=%d words, %d shots)", index, len(result["script"].split()), len(result["shot_list"]))
    return result


# ---------------------------------------------------------------- stage 3 --

def gather_assets(index: int, stage_pick: dict, run_date: Optional[date] = None, force: bool = False) -> dict:
    stage_name = f"art{index}_assets"
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(stage_name, run_date)
        if cached is not None:
            logger.info("art%d: using cached assets", index)
            return cached

    cfg = load_config()["art_explainer"]
    out_dir = output_dir_for(run_date)
    assets_dir = out_dir / "art" / str(index) / "assets"

    obj = stage_pick["object"]
    logger.info("art%d: downloading painting image", index)
    main_img = _download_image(obj["primaryImage"])
    main_path = assets_dir / "painting_main.jpg"
    _save_image(main_img, main_path)

    logger.info("art%d: cropping detail regions", index)
    crop_count = random.randint(cfg["detail_crops_min"], cfg["detail_crops_max"])
    crop_paths = []
    for i, crop in enumerate(_detail_crops(main_img, crop_count)):
        p = assets_dir / "crops" / f"crop_{i:02d}.jpg"
        _save_image(crop, p)
        crop_paths.append(str(p.relative_to(out_dir)))
    logger.info("art%d: %d detail crops saved", index, len(crop_paths))

    logger.info("art%d: running rembg for an optional parallax layer", index)
    try:
        from .clients.rembg_client import remove_background  # lazy: see stage3_assets.py

        foreground = remove_background(main_img)
        fg_path = assets_dir / "parallax_foreground.png"
        foreground.save(fg_path)
        parallax = {
            "foreground": str(fg_path.relative_to(out_dir)),
            "background": str(main_path.relative_to(out_dir)),
        }
    except Exception as e:
        logger.warning("art%d: rembg failed: %s", index, e)
        parallax = None

    result = {
        "main_image": str(main_path.relative_to(out_dir)),
        "detail_crops": crop_paths,
        "comparison_objects": [],
        "parallax": parallax,
    }
    save_stage(stage_name, result, run_date)
    logger.info("art%d: done", index)
    return result


# ---------------------------------------------------------------- stage 4 --

def synthesize_voice(index: int, stage_script: dict, run_date: Optional[date] = None, force: bool = False) -> dict:
    stage_name = f"art{index}_voice"
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(stage_name, run_date)
        if cached is not None:
            logger.info("art%d: using cached voice", index)
            return cached

    cfg = load_config()["audio"]
    out_dir = output_dir_for(run_date)
    audio_path = out_dir / "art" / str(index) / "audio" / "voice.mp3"
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("art%d: synthesizing voice (provider=edge)", index)
    voice_result = synthesize_with_word_timestamps(
        stage_script["script"], cfg["edge_voice"], cfg.get("edge_rate", "+0%")
    )
    audio_path.write_bytes(voice_result["audio_bytes"])

    result = {
        "audio": str(audio_path.relative_to(out_dir)),
        "word_timestamps": voice_result["words"],
    }
    save_stage(stage_name, result, run_date)
    logger.info("art%d: done", index)
    return result


# ---------------------------------------------------------------- stage 5 --

def render_video(
    index: int,
    stage_script: dict,
    stage_assets: dict,
    stage_voice: Optional[dict],
    run_date: Optional[date] = None,
    force: bool = False,
) -> dict:
    stage_name = f"art{index}_render"
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(stage_name, run_date)
        if cached is not None:
            logger.info("art%d: using cached render", index)
            return cached

    cfg = load_config()
    art_cfg = cfg["art_explainer"]
    out_dir = output_dir_for(run_date)
    date_str = (run_date or date.today()).isoformat()
    public_dir = REMOTION_DIR / "public" / "render" / f"{date_str}-art{index}"
    if public_dir.exists():
        import shutil
        shutil.rmtree(public_dir)
    public_dir.mkdir(parents=True, exist_ok=True)

    pools = _build_pools(stage_assets)
    counters: dict = {}
    shots = []
    for s in stage_script["shot_list"]:
        shot = dict(s)
        shot["chapter"] = "art"
        shot["asset_type"] = "museum_image_crop"
        shots.append(_resolve_shot_image(shot, stage_assets, out_dir, public_dir, pools, counters))

    for shot in shots:
        if shot.get("image"):
            shot["image"] = f"render/{date_str}-art{index}/{shot['image']}"
        if shot.get("backgroundImage"):
            shot["backgroundImage"] = f"render/{date_str}-art{index}/{shot['backgroundImage']}"

    if stage_voice and stage_voice.get("word_timestamps"):
        words = stage_voice["word_timestamps"]
    else:
        words = _synthetic_word_timestamps(stage_script["script"])

    brand = {
        "accent": cfg["brand"]["colors"]["accent"],
        "background": cfg["brand"]["colors"]["background"],
        "text": cfg["brand"]["colors"]["text"],
        "keywordAccent": cfg["brand"]["colors"]["subtitle_keyword_accent"],
    }
    props = {"shotList": shots, "wordTimestamps": words, "brand": brand}

    props_path = REMOTION_DIR / "sample-props" / f"art_tmp_{index}.json"
    import json
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    audio_dir = out_dir / "art" / str(index) / "audio_render"
    total_duration = sum(s["duration_sec"] for s in shots) or 1.0
    stage_voice_like = {"art_audio": stage_voice["audio"]} if stage_voice and stage_voice.get("audio") else None
    audio_files = _prepare_audio_files(
        stage_voice_like, "art_audio", audio_dir, cfg, total_duration, f"art{index}", out_dir
    )

    seq_dir = out_dir / "art" / str(index) / "frames"
    silent = out_dir / "art" / str(index) / "silent.mp4"
    final_out = out_dir / "art" / str(index) / "video.mp4"

    logger.info("art%d: rendering picture (%d shots, %.1fs)", index, len(shots), total_duration)
    _render_sequence("Shorts", props_path, seq_dir, port=3220 + index)
    _encode_sequence(seq_dir, art_cfg["video"]["fps"], silent)
    import shutil as _shutil
    _shutil.rmtree(seq_dir)
    props_path.unlink(missing_ok=True)

    logger.info("art%d: muxing audio with ffmpeg", index)
    cues = _chapter_cue_seconds(shots)
    _mux_audio(
        silent, audio_files["voice_path"], audio_files["music_path"], audio_files["sfx_path"],
        cues, audio_files["duck_gain"], total_duration, final_out,
    )
    silent.unlink(missing_ok=True)

    result = {"video": str(final_out.relative_to(out_dir))}
    save_stage(stage_name, result, run_date)
    logger.info("art%d: done", index)
    return result


# ---------------------------------------------------------------- stage 6 --

def render_thumbnail(
    index: int,
    stage_assets: dict,
    thumbnail_text_options: list,
    run_date: Optional[date] = None,
    force: bool = False,
) -> dict:
    stage_name = f"art{index}_thumb"
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(stage_name, run_date)
        if cached is not None:
            logger.info("art%d: using cached thumbnail", index)
            return cached

    cfg = load_config()
    out_dir = output_dir_for(run_date)
    thumb_dir = out_dir / "art" / str(index) / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    main_img = Image.open(out_dir / stage_assets["main_image"])
    foreground = None
    if stage_assets.get("parallax"):
        foreground = Image.open(out_dir / stage_assets["parallax"]["foreground"])

    text = (thumbnail_text_options or ["REAL PAINTING"])[0]
    cover = _render_shorts_cover(main_img, foreground, text, cfg)
    cover_path = thumb_dir / "cover.jpg"
    cover.convert("RGB").save(cover_path, quality=92)

    result = {"cover": str(cover_path.relative_to(out_dir)), "text": text}
    save_stage(stage_name, result, run_date)
    logger.info("art%d: done", index)
    return result


# ---------------------------------------------------------------- stage 7 --

def assemble_package(
    index: int,
    stage_pick: dict,
    stage_script: dict,
    stage_render: dict,
    stage_thumb: dict,
    run_date: Optional[date] = None,
    force: bool = False,
) -> dict:
    logger = get_logger(run_date)
    out_dir = output_dir_for(run_date)
    package_dir = out_dir / "art" / str(index)
    package_path = package_dir / "package.json"

    if not force and package_path.exists():
        logger.info("art%d: using existing package.json", index)
        import json
        with open(package_path, "r", encoding="utf-8") as f:
            return json.load(f)

    obj = stage_pick["object"]
    package = {
        "date": (run_date or date.today()).isoformat(),
        "index": index,
        "object": {
            "museum": stage_pick["museum"],
            "object_id": obj.get("objectID"),
            "title": obj.get("title"),
            "artist": obj.get("artistDisplayName"),
            "object_url": obj.get("objectURL"),
            "pick_reason": stage_pick.get("pick_reason"),
        },
        "metadata": {
            "title_options": stage_script["title_options"],
            "description": stage_script["description"],
            "tags": stage_script["tags"],
            "pinned_comment": stage_script["pinned_comment"],
        },
        "script": stage_script["script"],
        "video": stage_render["video"],
        "cover": stage_thumb["cover"],
        "publish_status": "not_posted",
    }

    import json
    with open(package_path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)
    logger.info("art%d: package.json written", index)
    return package


def run_one(index: int, run_date: Optional[date] = None, force: bool = False) -> dict:
    s1 = pick_painting(index, run_date=run_date, force=force)
    s2 = generate_script(index, s1, run_date=run_date, force=force)
    s3 = gather_assets(index, s1, run_date=run_date, force=force)
    try:
        s4 = synthesize_voice(index, s2, run_date=run_date, force=force)
    except Exception as e:
        get_logger(run_date).warning("art%d: voice synthesis failed, continuing with placeholder: %s", index, e)
        s4 = None
    s5 = render_video(index, s2, s3, s4, run_date=run_date, force=force)
    s6 = render_thumbnail(index, s3, s2["thumbnail_text_options"], run_date=run_date, force=force)
    return assemble_package(index, s1, s2, s5, s6, run_date=run_date, force=True)
