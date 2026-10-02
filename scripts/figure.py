#!/usr/bin/env python3
"""Rasterize tutoring figures so the agent can look at them.

An image-reading tool will not open .svg, and an XML parser accepting the file
proves nothing about what it looks like. This renders each figure to PNG in a
`.check/` folder next to it; the agent opens the PNG, looks, fixes, repeats,
then deletes the check folder.

Renders with headless Chrome/Edge/Chromium when one is installed (that is what
VS Code, Obsidian and GitHub will show), otherwise with PyMuPDF, which ignores
some SVG features (inherited text-anchor, web fonts) and can differ.

    python figure.py study/lec3.1/extras/halving-to-one.svg [more files...]
    python figure.py --engine mupdf FILE
    python figure.py --clean study/lec3.1/extras
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import common as c

BROWSER_NAMES = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "msedge", "microsoft-edge"]
BROWSER_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_browser() -> str | None:
    if env := os.environ.get("TPS_BROWSER"):
        return env
    for name in BROWSER_NAMES:
        if found := shutil.which(name):
            return found
    return next((p for p in BROWSER_PATHS if Path(p).exists()), None)


def svg_size(svg: Path) -> tuple[int, int]:
    head = svg.read_text(encoding="utf-8", errors="replace")[:4000]
    root = re.search(r"<svg\b[^>]*>", head, re.S)
    tag = root.group(0) if root else ""

    def num(attr):
        m = re.search(rf'\b{attr}\s*=\s*"([\d.]+)(px)?"', tag)
        return float(m.group(1)) if m else None

    w, h = num("width"), num("height")
    if not (w and h):
        vb = re.search(r'viewBox\s*=\s*"[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', tag)
        if vb:
            w, h = float(vb.group(1)), float(vb.group(2))
    return int(w or 1200), int(h or 800)


def render_browser(browser: str, svg: Path, png: Path, scale: float) -> None:
    w, h = svg_size(svg)
    png = png.resolve()  # the browser resolves relative paths against its own folder
    profile = Path(tempfile.mkdtemp(prefix="chrome-", dir=png.parent))  # stays inside .check/
    try:
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               f"--user-data-dir={profile}", f"--force-device-scale-factor={scale}",
               f"--window-size={w},{h}", f"--screenshot={png}", svg.resolve().as_uri()]
        subprocess.run(cmd, capture_output=True, timeout=90)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not png.exists():
        raise RuntimeError("browser produced no screenshot")


def render_mupdf(src: Path, png: Path, scale: float) -> None:
    fitz = c.fitz()
    with fitz.open(src) as doc:
        doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(png)


def looks_blank(png: Path) -> bool:
    fitz = c.fitz()
    pix = fitz.Pixmap(str(png))
    return pix.color_count() <= 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Rasterize figures to .check/*.png so they can be looked at.")
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--engine", choices=["auto", "browser", "mupdf"], default="auto")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--clean", nargs="+", type=Path, metavar="DIR",
                    help="delete the .check/ folder inside each DIR and stop")
    args = ap.parse_args()

    if args.clean:
        for d in args.clean:
            check = d / ".check" if d.name != ".check" else d
            if check.exists():
                shutil.rmtree(check)
                print(f"removed {check}")
        return 0
    if not args.files:
        ap.error("give figure files, or --clean DIR")

    browser = find_browser() if args.engine != "mupdf" else None
    if args.engine == "browser" and not browser:
        sys.exit("No Chrome/Edge/Chromium found (set TPS_BROWSER to its path), or use --engine mupdf.")
    if args.engine == "auto" and not browser:
        print("note: no Chrome/Edge/Chromium found; using PyMuPDF, which can differ from what "
              "Markdown viewers show (inherited text-anchor, fonts).")

    status = 0
    for src in args.files:
        if not src.exists():
            print(f"{src}: not found")
            status = 1
            continue
        out_dir = src.parent / ".check"
        out_dir.mkdir(exist_ok=True)
        png = out_dir / f"{src.stem}.png"
        png.unlink(missing_ok=True)
        try:
            if src.suffix.lower() == ".svg" and browser:
                render_browser(browser, src, png, args.scale)
                engine = "browser"
            else:
                render_mupdf(src, png, args.scale)
                engine = "mupdf"
        except Exception as e:  # report and keep going with the other figures
            print(f"{src}: could not render ({e})")
            status = 1
            continue
        warn = "  WARNING: looks blank" if looks_blank(png) else ""
        print(f"{src} -> {png} [{engine}]{warn}")
    print("Open each PNG and look at it. When done: python figure.py --clean <extras dir>")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
