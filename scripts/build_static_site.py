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
import hashlib
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


def _copy_art(day_dir: Path, dest: Path) -> bool:
    """Copy a day's art/ subtree (each piece's package.json + its own media,
    all already relative to day_dir) and write art/items.json for the
    frontend to fetch in one request. Returns True if any art content exists."""
    art_src = day_dir / "art"
    if not art_src.exists():
        return False

    items = []
    for sub in sorted(art_src.iterdir(), key=lambda p: p.name):
        pkg_path = sub / "package.json"
        if not pkg_path.exists():
            continue
        with open(pkg_path, "r", encoding="utf-8") as f:
            package = json.load(f)
        items.append(package)

        art_dest = dest / "art" / sub.name
        art_dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pkg_path, art_dest / "package.json")
        for rel in [package["video"], package["cover"]]:
            rel = rel.replace("\\", "/")
            src = day_dir / rel
            if not src.exists():
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)

    if not items:
        return False
    with open(dest / "art" / "items.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)
    return True


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

    # Cache-bust app.js/style.css: browsers (and GitHub's CDN) can cache
    # these at the bare filename for a while, so without a version query a
    # visitor can end up with a fresh index.html paired with a stale script
    # -- new markup (e.g. a nav button) whose click handler never fires.
    index_path = site_dir / "index.html"
    html = index_path.read_text(encoding="utf-8")
    for name in ["app.js", "style.css"]:
        digest = hashlib.sha1((site_dir / name).read_bytes()).hexdigest()[:10]
        html = html.replace(f'"{name}"', f'"{name}?v={digest}"')
    index_path.write_text(html, encoding="utf-8")

    day_dirs = sorted(
        (
            p for p in output_dir.iterdir()
            if p.is_dir() and ((p / "package.json").exists() or (p / "art").exists())
        ),
        key=lambda p: p.name,
        reverse=True,
    )
    kept = day_dirs[:keep_days]
    kept_names = {p.name for p in kept}

    for existing in data_dir.iterdir():
        if existing.is_dir() and existing.name not in kept_names:
            shutil.rmtree(existing)

    main_day_names = set()
    art_day_names = set()
    for day_dir in kept:
        date_str = day_dir.name
        dest = data_dir / date_str
        dest.mkdir(parents=True, exist_ok=True)

        if (day_dir / "package.json").exists():
            with open(day_dir / "package.json", "r", encoding="utf-8") as f:
                package = json.load(f)
            shutil.copyfile(day_dir / "package.json", dest / "package.json")
            for rel in _referenced_files(package):
                src = day_dir / rel
                if not src.exists():
                    continue
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, out)
            main_day_names.add(date_str)

        if _copy_art(day_dir, dest):
            art_day_names.add(date_str)

    days_json = data_dir / "days.json"
    with open(days_json, "w", encoding="utf-8") as f:
        json.dump(sorted(main_day_names, reverse=True), f)

    art_days_json = data_dir / "art_days.json"
    with open(art_days_json, "w", encoding="utf-8") as f:
        json.dump(sorted(art_day_names, reverse=True), f)

    return site_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the static (GitHub Pages) dashboard site.")
    parser.add_argument("--keep-days", type=int, default=14, help="how many recent days to publish")
    args = parser.parse_args()

    site_dir = build(keep_days=args.keep_days)
    print(f"Static site built at {site_dir}")
