import json
from datetime import date
from typing import Any, Dict, List

from .config import ROOT, load_config


def _path():
    cfg = load_config()
    return ROOT / cfg["paths"]["used_objects_file"]


def load_used_objects() -> List[Dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_used(museum: str, object_id: int) -> bool:
    return any(
        entry["museum"] == museum and entry["object_id"] == object_id
        for entry in load_used_objects()
    )


def mark_used(museum: str, object_id: int, title: str, run_date: date = None) -> None:
    path = _path()
    entries = load_used_objects()
    entries.append(
        {
            "museum": museum,
            "object_id": object_id,
            "title": title,
            "date": (run_date or date.today()).isoformat(),
        }
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
