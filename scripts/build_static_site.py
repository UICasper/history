"""Assemble a static, backend-free copy of the dashboard for GitHub Pages
(or Netlify/Vercel static hosting): the frontend files plus each recent
day's package.json + the media files it references, under docs/data/.

The frontend detects the absence of a live API and reads from these files
instead (see dashboard/frontend/app.js, STATIC_MODE) -- publish-status
toggling, metadata editing, and regenerate buttons are disabled in that mode
since there's no backend to write to.

Usage: python -m scripts.build_static_site [--keep-days N]
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.utils.config import load_config  # noqa: E402

FRONTEND_FILES = ["index.html", "app.js", "style.css"]


def _referenced_files(package: dict) -> list:
    paths = [package["video"]["long"], package["video"]["shorts"], package["shorts_cover"]]
    paths += [t["path"] for t in package["thumbnails"]]
    return [p.replace("\\", "/") for p in paths]


def build(keep_days: int = 14) -> Path:
    cfg = load_config()
    output_dir = ROOT / cfg["paths"]["output_dir"]
    site_dir = ROOT / "docs"
    data_dir = site_dir / "data"
    site_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    frontend_dir = ROOT / "dashboard" / "frontend"
    for name in FRONTEND_FILES:
        shutil.copyfile(frontend_dir / name, site_dir / name)

    day_dirs = sorted(
        (p for p in output_dir.iterdir() if p.is_dir() and (p / "package.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    )
    kept = day_dirs[:keep_days]
    kept_names = {p.name for p in kept}

    for existing in data_dir.iterdir():
        if existing.is_dir() and existing.name not in kept_names:
            shutil.rmtree(existing)

    for day_dir in kept:
        date_str = day_dir.name
        with open(day_dir / "package.json", "r", encoding="utf-8") as f:
            package = json.load(f)

        dest = data_dir / date_str
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(day_dir / "package.json", dest / "package.json")

        for rel in _referenced_files(package):
            src = day_dir / rel
            if not src.exists():
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)

    days_json = data_dir / "days.json"
    with open(days_json, "w", encoding="utf-8") as f:
        json.dump(sorted(kept_names, reverse=True), f)

    return site_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the static (GitHub Pages) dashboard site.")
    parser.add_argument("--keep-days", type=int, default=14, help="how many recent days to publish")
    args = parser.parse_args()

    site_dir = build(keep_days=args.keep_days)
    print(f"Static site built at {site_dir}")
