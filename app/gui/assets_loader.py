from __future__ import annotations
from pathlib import Path
import tkinter as tk

PIECE_CODES = ["wP","wN","wB","wR","wQ","wK","bP","bN","bB","bR","bQ","bK"]

class Assets:
    def __init__(self, images: dict[str, tk.PhotoImage], sq_size: int):
        self.images = images
        self.sq_size = sq_size

    def img(self, code: str) -> tk.PhotoImage:
        return self.images[code]

def load_piece_images(project_root: Path, sq_size: int) -> Assets:
    base = project_root / "assets" / "png" / str(sq_size)
    images: dict[str, tk.PhotoImage] = {}
    missing = []
    for code in PIECE_CODES:
        p = base / f"{code}.png"
        if not p.exists():
            missing.append(str(p))
            continue
        img = tk.PhotoImage(file=str(p))
        images[code] = img
    if missing:
        raise FileNotFoundError("Missing piece images:\n" + "\n".join(missing))
    return Assets(images, sq_size)
