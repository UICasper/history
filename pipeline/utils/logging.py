import logging
from datetime import date
from typing import Optional

from .cache import output_dir_for


def get_logger(run_date: Optional[date] = None) -> logging.Logger:
    d = output_dir_for(run_date)
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(d / "run.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(sh)
    return logger
