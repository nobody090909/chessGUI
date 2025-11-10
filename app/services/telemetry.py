from __future__ import annotations
import logging
from pathlib import Path

def setup_logging(project_root: Path) -> logging.Logger:
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("chess_proto")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(logs_dir / "app.log", encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger
