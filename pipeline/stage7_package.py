"""Stage 7: assemble every earlier stage's output into one package.json that
the dashboard reads directly.
"""

import json
from datetime import date
from typing import Optional

from .utils.cache import output_dir_for
from .utils.logging import get_logger

STAGE_NAME = "stage7_package"


def run(
    stage1_result: dict,
    stage2_result: dict,
    stage5_result: dict,
    stage6_result: dict,
    run_date: Optional[date] = None,
    force: bool = False,
) -> dict:
    logger = get_logger(run_date)
    out_dir = output_dir_for(run_date)
    package_path = out_dir / "package.json"

    if not force and package_path.exists():
        logger.info("stage7: using existing package.json")
        with open(package_path, "r", encoding="utf-8") as f:
            return json.load(f)

    obj = stage1_result["object"]
    package = {
        "date": (run_date or date.today()).isoformat(),
        "object": {
            "museum": stage1_result["museum"],
            "object_id": obj.get("objectID"),
            "title": obj.get("title"),
            "object_url": obj.get("objectURL"),
            "pick_reason": stage1_result.get("pick_reason"),
        },
        "metadata": {
            "title_options": stage2_result["title_options"],
            "description": stage2_result["description"],
            "tags": stage2_result["tags"],
            "pinned_comment": stage2_result["pinned_comment"],
        },
        "scripts": {
            "long": stage2_result["long_script"],
            "shorts": stage2_result["shorts_script"],
        },
        "video": {
            "long": stage5_result["long_video"],
            "shorts": stage5_result["shorts_video"],
        },
        "thumbnails": stage6_result["thumbnails"],
        "shorts_cover": stage6_result["shorts_cover"],
        "publish_status": "not_posted",
    }

    with open(package_path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)
    logger.info("stage7: package.json written")
    return package


if __name__ == "__main__":
    from .stage1_pick_object import run as run_stage1
    from .stage2_generate_script import run as run_stage2
    from .stage3_assets import run as run_stage3
    from .stage5_render import run as run_stage5
    from .stage6_thumbnails import run as run_stage6

    s1 = run_stage1()
    s2 = run_stage2(s1)
    s3 = run_stage3(s1, s2)
    s5 = run_stage5(s1, s2, s3, None)
    s6 = run_stage6(s3, s2["thumbnail_text_options"])
    result = run(s1, s2, s5, s6, force=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
