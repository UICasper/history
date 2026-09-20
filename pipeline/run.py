"""Daily orchestrator: runs every stage in order for a given date (default
today) and writes output/<date>/package.json. Intended to be invoked by cron
or a GitHub Actions schedule; also used by the dashboard's regenerate
endpoint (see dashboard/backend/main.py) to re-run from a given stage.
"""

import argparse
import json
from datetime import date

from . import (
    stage1_pick_object,
    stage2_generate_script,
    stage3_assets,
    stage4_voice,
    stage5_render,
    stage6_thumbnails,
    stage7_package,
)
from .utils.logging import get_logger


def run(run_date: date = None, force: bool = False) -> dict:
    run_date = run_date or date.today()
    logger = get_logger(run_date)
    logger.info("=== daily run starting for %s ===", run_date.isoformat())

    s1 = stage1_pick_object.run(run_date=run_date, force=force)
    s2 = stage2_generate_script.run(s1, run_date=run_date, force=force)
    s3 = stage3_assets.run(s1, s2, run_date=run_date, force=force)

    try:
        s4 = stage4_voice.run(s2, run_date=run_date, force=force)
    except Exception as e:
        logger.warning("stage4 (ElevenLabs voice) failed, continuing with placeholder audio: %s", e)
        s4 = None

    s5 = stage5_render.run(s1, s2, s3, s4, run_date=run_date, force=force)
    s6 = stage6_thumbnails.run(s3, s2["thumbnail_text_options"], run_date=run_date, force=force)
    package = stage7_package.run(s1, s2, s5, s6, run_date=run_date, force=True)

    logger.info("=== daily run complete for %s ===", run_date.isoformat())
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the daily content pipeline.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--force", action="store_true", help="ignore all stage caches and re-run everything")
    args = parser.parse_args()

    run_date = date.fromisoformat(args.date) if args.date else date.today()
    package = run(run_date=run_date, force=args.force)
    print(json.dumps(package, indent=2, ensure_ascii=False))
