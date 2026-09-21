"""Stage 2: one LLM call generates the long script, Shorts script, illustration
prompts, YouTube metadata, and the shot list -- all as one structured JSON blob.
"""

from datetime import date
from typing import Optional

from .clients import met_api
from .clients.llm_client import generate_structured
from .schemas import VideoPackage
from .utils.cache import load_stage, save_stage
from .utils.config import load_config
from .utils.logging import get_logger

STAGE_NAME = "stage2_package"

PROMPT_TEMPLATE = """\
You are writing the script and YouTube metadata for one episode of a daily
history/education channel called "What Is This Thing?". Tone: curious,
playful, clear. Audience: English-speaking, international, general.

The episode is about this museum object (JSON):
{object_json}

Why this object was chosen: {pick_reason}

Write ALL of the following in one response:

1. long_script: a spoken narration script, {long_min}-{long_max} words, for a
   {long_duration_min}-{long_duration_max} second video, following this exact
   structure in order:
   - Quiz: describe only a cropped detail or silhouette, ask "what is this and
     what was it for?"
   - Reveal: the full object is shown
   - How it was used: explain who used it, where, and how
   - Similar objects: briefly compare it to similar/same-era objects
   - Where it came from: where it originates and how it reached the museum
   - Where it is now: which museum, one closing fact, a question for viewers
     to answer in the comments

2. shorts_script: a spoken script, {shorts_min}-{shorts_max} words, for a
   {shorts_duration_min}-{shorts_duration_max} second Short:
   - 0-3s: the single strangest fact, no intro
   - 3-30s: 4-5 key points
   - 30-40s: a cliffhanger that cuts off and points to the full video

3. title_options: exactly 3 title options.

4. description: a YouTube description. First 2 lines are the hook. Include
   approximate timestamps matching the chapters. End with hashtags.

5. tags: comma-separated YouTube tags.

6. pinned_comment: a short pinned comment text that invites engagement
   (e.g. restates the closing question).

7. thumbnail_text_options: 3 short (2-4 word) high-contrast hook phrases
   for the thumbnail, e.g. "USED FOR WHAT?", "3000 YEARS OLD". ALL CAPS.

8. shot_list: one entry per visual across the ENTIRE long video, roughly
   every {pace_min}-{pace_max} seconds (~{shot_count_min}-{shot_count_max}
   entries total), covering all six chapters in order. Every shot must use
   a REAL photo -- no AI-generated imagery anywhere in this video. Each
   entry picks asset_type (museum_image_crop / comparison_object /
   code_animation) and motion (parallax / spotlight / annotation / reveal /
   static / data_animation), with exactly one motion per shot, never
   stacked. asset_ref should be a short identifier (e.g. "crop_03",
   "comparison_01", "map_animation", "timeline_animation").
"""


def _build_prompt(object_data: dict, pick_reason: str) -> str:
    cfg = load_config()
    v = cfg["video"]
    pacing = cfg["visual_pacing"]
    return PROMPT_TEMPLATE.format(
        object_json=met_api.summarize_for_llm(object_data),
        pick_reason=pick_reason,
        long_min=v["long"]["target_word_count_min"],
        long_max=v["long"]["target_word_count_max"],
        long_duration_min=v["long"]["min_duration_sec"],
        long_duration_max=v["long"]["max_duration_sec"],
        shorts_min=v["shorts"]["target_word_count_min"],
        shorts_max=v["shorts"]["target_word_count_max"],
        shorts_duration_min=v["shorts"]["min_duration_sec"],
        shorts_duration_max=v["shorts"]["max_duration_sec"],
        pace_min=pacing["seconds_per_visual_min"],
        pace_max=pacing["seconds_per_visual_max"],
        shot_count_min=pacing["long_video_visual_count_min"],
        shot_count_max=pacing["long_video_visual_count_max"],
    )


def run(stage1_result: dict, run_date: Optional[date] = None, force: bool = False) -> dict:
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(STAGE_NAME, run_date)
        if cached is not None:
            logger.info("stage2: using cached package")
            return cached

    logger.info("stage2: calling Gemini for script + metadata")
    prompt = _build_prompt(stage1_result["object"], stage1_result["pick_reason"])
    package: VideoPackage = generate_structured(prompt, VideoPackage)

    result = package.model_dump()
    save_stage(STAGE_NAME, result, run_date)
    logger.info(
        "stage2: done (long_script=%d words, %d shots)",
        len(result["long_script"].split()),
        len(result["shot_list"]),
    )
    return result


if __name__ == "__main__":
    import json

    from .stage1_pick_object import run as run_stage1

    stage1_result = run_stage1()
    result = run(stage1_result, force=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
