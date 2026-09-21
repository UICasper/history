"""Art Explainer daily orchestrator: runs N (config: art_explainer.pieces_per_day)
independent real-painting pieces for a given date. Separate from run.py's
main daily object -- meant to be invoked alongside it, not instead of it.
"""

import argparse
import json
from datetime import date

from . import art_pipeline
from .utils.config import load_config
from .utils.logging import get_logger


def run(run_date: date = None, force: bool = False) -> list:
    run_date = run_date or date.today()
    logger = get_logger(run_date)
    count = load_config()["art_explainer"]["pieces_per_day"]
    logger.info("=== art explainer run starting for %s (%d pieces) ===", run_date.isoformat(), count)

    packages = []
    for index in range(1, count + 1):
        logger.info("--- art piece %d/%d ---", index, count)
        packages.append(art_pipeline.run_one(index, run_date=run_date, force=force))

    logger.info("=== art explainer run complete for %s ===", run_date.isoformat())
    return packages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the daily art-explainer pipeline.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--force", action="store_true", help="ignore all stage caches and re-run everything")
    args = parser.parse_args()

    run_date = date.fromisoformat(args.date) if args.date else date.today()
    packages = run(run_date=run_date, force=args.force)
    print(json.dumps(packages, indent=2, ensure_ascii=False))
