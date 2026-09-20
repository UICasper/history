"""Stage 3: download/crop museum images, fetch comparison objects, generate
AI illustrations, and split the main object image into rembg parallax layers.
"""

import io
import random
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from .clients import met_api
from .clients.image_gen import generate_illustration
from .clients.rembg_client import remove_background
from .utils.cache import load_stage, output_dir_for, save_stage
from .utils.config import load_config
from .utils.logging import get_logger

STAGE_NAME = "stage3_assets"


def _download_image(url: str) -> Image.Image:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def _save_image(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=92)


def _detail_crops(img: Image.Image, count: int) -> list:
    w, h = img.size
    crops = []
    for _ in range(count):
        scale = random.uniform(0.2, 0.45)
        crop_size = int(min(w, h) * scale)
        x = random.randint(0, max(0, w - crop_size))
        y = random.randint(0, max(0, h - crop_size))
        crops.append(img.crop((x, y, x + crop_size, y + crop_size)))
    return crops


def _find_comparison_objects(obj: dict, count_min: int, count_max: int, exclude_id: int) -> list:
    query = (
        obj.get("culture")
        or obj.get("period")
        or obj.get("objectName")
        or obj.get("department")
        or "ancient"
    )
    ids = met_api.search_object_ids(query)
    random.shuffle(ids)
    found = []
    for oid in ids:
        if oid == exclude_id:
            continue
        try:
            cand = met_api.get_object(oid)
        except requests.HTTPError:
            continue
        if met_api.is_usable_candidate(cand):
            found.append(cand)
        if len(found) >= count_max:
            break
    return found[:max(count_min, min(len(found), count_max))]


def run(
    stage1_result: dict,
    stage2_result: dict,
    run_date: Optional[date] = None,
    force: bool = False,
) -> dict:
    logger = get_logger(run_date)

    if not force:
        cached = load_stage(STAGE_NAME, run_date)
        if cached is not None:
            logger.info("stage3: using cached assets")
            return cached

    cfg = load_config()
    out_dir = output_dir_for(run_date)
    assets_dir = out_dir / "assets"

    obj = stage1_result["object"]
    logger.info("stage3: downloading main object image")
    main_img = _download_image(obj["primaryImage"])
    main_path = assets_dir / "object_main.jpg"
    _save_image(main_img, main_path)

    additional_paths = []
    for i, url in enumerate(obj.get("additionalImages") or []):
        try:
            img = _download_image(url)
        except requests.HTTPError:
            continue
        p = assets_dir / f"object_extra_{i:02d}.jpg"
        _save_image(img, p)
        additional_paths.append(str(p.relative_to(out_dir)))

    logger.info("stage3: cropping detail regions")
    crop_count = random.randint(
        cfg["assets"]["detail_crops_min"], cfg["assets"]["detail_crops_max"]
    )
    crop_paths = []
    for i, crop in enumerate(_detail_crops(main_img, crop_count)):
        p = assets_dir / "crops" / f"crop_{i:02d}.jpg"
        _save_image(crop, p)
        crop_paths.append(str(p.relative_to(out_dir)))
    logger.info("stage3: %d detail crops saved", len(crop_paths))

    logger.info("stage3: fetching comparison objects")
    comparisons = _find_comparison_objects(
        obj,
        cfg["assets"]["comparison_objects_min"],
        cfg["assets"]["comparison_objects_max"],
        obj["objectID"],
    )
    comparison_entries = []
    for i, cand in enumerate(comparisons):
        try:
            img = _download_image(cand["primaryImage"])
        except requests.HTTPError:
            continue
        p = assets_dir / "comparisons" / f"comparison_{i:02d}.jpg"
        _save_image(img, p)
        comparison_entries.append(
            {"object_id": cand["objectID"], "title": cand.get("title"), "path": str(p.relative_to(out_dir))}
        )
    logger.info("stage3: %d comparison objects saved", len(comparison_entries))

    logger.info("stage3: generating AI illustrations")
    illustration_entries = []
    for illus in stage2_result["illustration_prompts"]:
        try:
            img = generate_illustration(illus["prompt"])
        except Exception as e:
            logger.warning("stage3: illustration %s failed: %s", illus["id"], e)
            continue
        p = assets_dir / "illustrations" / f"{illus['id']}.jpg"
        _save_image(img, p)
        illustration_entries.append(
            {"id": illus["id"], "chapter": illus["chapter"], "path": str(p.relative_to(out_dir))}
        )
    logger.info(
        "stage3: %d/%d illustrations generated",
        len(illustration_entries),
        len(stage2_result["illustration_prompts"]),
    )

    logger.info("stage3: running rembg for parallax layers")
    try:
        foreground = remove_background(main_img)
        fg_path = assets_dir / "parallax_foreground.png"
        foreground.save(fg_path)
        parallax = {
            "foreground": str(fg_path.relative_to(out_dir)),
            "background": str(main_path.relative_to(out_dir)),
        }
    except Exception as e:
        logger.warning("stage3: rembg failed: %s", e)
        parallax = None

    result = {
        "main_image": str(main_path.relative_to(out_dir)),
        "additional_images": additional_paths,
        "detail_crops": crop_paths,
        "comparison_objects": comparison_entries,
        "illustrations": illustration_entries,
        "parallax": parallax,
    }
    save_stage(STAGE_NAME, result, run_date)
    logger.info("stage3: done")
    return result


if __name__ == "__main__":
    import json

    from .stage1_pick_object import run as run_stage1
    from .stage2_generate_script import run as run_stage2

    s1 = run_stage1()
    s2 = run_stage2(s1)
    result = run(s1, s2, force=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
