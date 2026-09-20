import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

from .config import ROOT, load_config


def output_dir_for(run_date: Optional[date] = None) -> Path:
    run_date = run_date or date.today()
    cfg = load_config()
    d = ROOT / cfg["paths"]["output_dir"] / run_date.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_cache_path(stage_name: str, run_date: Optional[date] = None) -> Path:
    return output_dir_for(run_date) / f"{stage_name}.json"


def load_stage(stage_name: str, run_date: Optional[date] = None) -> Optional[Any]:
    path = stage_cache_path(stage_name, run_date)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_stage(stage_name: str, data: Any, run_date: Optional[date] = None) -> Path:
    path = stage_cache_path(stage_name, run_date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
