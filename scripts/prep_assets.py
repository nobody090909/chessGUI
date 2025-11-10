#!/usr/bin/env python3
"""
prep_assets.py — Convert chess piece SVGs → PNGs for Tkinter.

- Input:  assets/svg/<set>/{wP.svg … bK.svg}
- Output: assets/png/<size>/{wP.png … bK.png}

Usage:
  python scripts/prep_assets.py --src assets/svg/merida --out assets/png --sizes 72 96
  python scripts/prep_assets.py --src assets/svg/merida --out assets/png --sizes 72 --engine inkscape

Requires:
  - Prefer: pip install cairosvg
  - Fallback: Inkscape CLI available (inkscape command)
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List

PIECES = ["P","N","B","R","Q","K"]
CODES = [f"{s}{p}" for s in ("w","b") for p in PIECES]

def _convert_one_cairosvg(src: Path, dst: Path, size: int):
    import cairosvg  # type: ignore
    dst.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(url=str(src), write_to=str(dst), output_width=size, output_height=size)

def _convert_one_inkscape(src: Path, dst: Path, size: int):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "inkscape",
        str(src),
        "-o", str(dst),
        "-w", str(size),
        "-h", str(size),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def _validate_inputs(src_dir: Path, codes: List[str]):
    missing = [str(src_dir / f"{c}.svg") for c in codes if not (src_dir / f"{c}.svg").exists()]
    if missing:
        raise FileNotFoundError("Missing SVGs:\n" + "\n".join(missing))

def _engine_available(name: str) -> bool:
    if name == "cairosvg":
        try:
            import cairosvg  # noqa
            return True
        except Exception:
            return False
    if name == "inkscape":
        return shutil.which("inkscape") is not None
    return False

def convert_dir(src_svg_dir: Path, out_png_root: Path, sizes: Iterable[int], engine: str = "auto"):
    src_svg_dir = src_svg_dir.resolve()
    out_png_root = out_png_root.resolve()
    _validate_inputs(src_svg_dir, CODES)

    # pick engine
    chosen = None
    if engine == "auto":
        chosen = "cairosvg" if _engine_available("cairosvg") else ("inkscape" if _engine_available("inkscape") else None)
    else:
        chosen = engine if _engine_available(engine) else None
    if not chosen:
        raise RuntimeError("No conversion engine available. Install 'cairosvg' or Inkscape CLI.")

    for size in sizes:
        out_dir = out_png_root / str(size)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[i] Converting to {out_dir} using {chosen} ...")
        for code in CODES:
            src = src_svg_dir / f"{code}.svg"
            dst = out_dir / f"{code}.png"
            if chosen == "cairosvg":
                _convert_one_cairosvg(src, dst, size)
            else:
                _convert_one_inkscape(src, dst, size)
        print(f"[✓] Done: {size}px")

def parse_args():
    ap = argparse.ArgumentParser(description="Convert chess SVG pieces to PNG at desired sizes.")
    ap.add_argument("--src", required=True, help="SVG dir (e.g., assets/svg/merida)")
    ap.add_argument("--out", default="assets/png", help="PNG root output dir (default: assets/png)")
    ap.add_argument("--sizes", nargs="+", type=int, default=[72], help="One or more square sizes in px (default: 72)")
    ap.add_argument("--engine", choices=["auto","cairosvg","inkscape"], default="auto", help="Conversion engine")
    return ap.parse_args()

if __name__ == "__main__":
    args = parse_args()
    convert_dir(Path(args.src), Path(args.out), args.sizes, engine=args.engine)
    print("[✓] All conversions completed.")
