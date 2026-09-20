"""Stage 1: pick one museum object for today's video.

Searches The Met Collection API for candidates, filters to usable ones
(public domain, has a primary image, not already used), then asks Gemini
to choose the single most surprising/quiz-worthy candidate.
"""

import random
from datetime import date
from typing import Optional

import requests

from .clients import met_api
from .clients.gemini_client import generate_structured
from .schemas import ObjectPick
from .utils.cache import load_stage, save_stage
from .utils.logging import get_logger
from .utils.used_objects import is_used, mark_used

STAGE_NAME = "stage1_object"
MUSEUM = "met"

# Broad search terms to rotate through so candidates aren't always from the
# same corner of the collection.
SEARCH_TERMS = [
    "ancient", "ceremonial", "ritual", "weapon", "jewelry", "tool",
    "musical instrument", "game", "armor", "amulet", "vessel", "mask",
]

CANDIDATE_POOL_SIZE = 25


def _gather_candidates() -> list[dict]:
    ids: list[int] = []
    terms = random.sample(SEARCH_TERMS, k=len(SEARCH_TERMS))
    for term in terms:
        ids.extend(met_api.search_object_ids(term))
        if len(ids) >= CANDIDATE_POOL_SIZE * 4:
            break

    random.shuffle(ids)

    candidates = []
    for object_id in ids:
        if is_used(MUSEUM, object_id):
            continue
        try:
            obj = met_api.get_object(object_id)
        except requests.HTTPError:
            # The Met's search index includes some deprecated/removed object IDs.
            continue
        if met_api.is_usable_candidate(obj):
            candidates.append(obj)
        if len(candidates) >= CANDIDATE_POOL_SIZE:
            break
    return candidates


def run(run_date: Optional[date] = None, force: bool = False) -> dict:
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(STAGE_NAME, run_date)
        if cached is not None:
            logger.info("stage1: using cached object pick")
            return cached

    logger.info("stage1: gathering candidates from The Met API")
    candidates = _gather_candidates()
    if not candidates:
        raise RuntimeError("stage1: no usable candidates found (all used, or API returned nothing)")
    logger.info("stage1: %d usable candidates found", len(candidates))

    summaries = [met_api.summarize_for_llm(c) for c in candidates]
    prompt = (
        "You are choosing one museum object to feature in a daily 'what is this "
        "thing?' history/education video. The audience is curious, general, "
        "English-speaking. Pick the single most surprising, quiz-worthy object "
        "from the list below -- something people will be shocked to learn the "
        "purpose of, or that has a great story. Avoid generic paintings; prefer "
        "objects with a clear function or twist.\n\n"
        f"Candidates (JSON):\n{summaries}\n\n"
        "Respond with the chosen object's object_id and a one-line reason."
    )
    pick = generate_structured(prompt, ObjectPick)
    logger.info("stage1: LLM picked object_id=%s reason=%s", pick.chosen_object_id, pick.reason)

    chosen = next(
        (c for c in candidates if c.get("objectID") == pick.chosen_object_id), None
    )
    if chosen is None:
        # LLM hallucinated an id outside the candidate list; fall back to the first candidate.
        logger.warning("stage1: LLM returned an id not in the candidate list, using first candidate")
        chosen = candidates[0]
        pick.chosen_object_id = chosen["objectID"]

    result = {
        "museum": MUSEUM,
        "object": chosen,
        "pick_reason": pick.reason,
    }
    save_stage(STAGE_NAME, result, run_date)
    mark_used(MUSEUM, chosen["objectID"], chosen.get("title", ""), run_date)
    logger.info("stage1: done")
    return result


if __name__ == "__main__":
    import json

    result = run(force=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
