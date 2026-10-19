#!/usr/bin/env python3
"""Find where a course's slides and transcripts are, whatever the folders are called.

Scans the whole course folder (skipping hidden and tool folders, the output
folder and the skill itself) and prints, per folder: slide PDFs, transcript
files, and near-misses that need a step from the student first (PowerPoint or
Keynote decks to export as PDF, recordings with no transcript, Word transcripts).
A short peek at the first file of each kind shows what it is.

Does not decide anything. The agent reads this, judges by content which folders
hold slides and which hold transcripts (`ppt/`, `Week 3/`, `recordings/`, or
everything loose in the course folder), and writes them into
transcript-per-slide.toml under [paths].

    python locate.py [--root COURSE]
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import common as c

KINDS = [
    # (key, label, suffixes)
    ("slides", "slide PDFs", {".pdf"}),
    ("transcripts", "transcripts", c.TRANSCRIPT_SUFFIXES),
    ("decks", "PowerPoint/Keynote decks (export to PDF first)", {".pptx", ".ppt", ".key", ".odp"}),
    ("word", "Word documents (if transcripts: download .vtt/.txt instead, or save as .txt)", {".docx", ".doc"}),
    ("media", "recordings (need a transcript; video/audio cannot be read)",
     {".mp4", ".m4a", ".mp3", ".mov", ".wav", ".webm", ".mkv", ".aac", ".m4v"}),
]
MAX_FILES = 50_000
SAMPLES = 4


def peek(proj: c.Project, kind: str, path: Path, limit: int = 160) -> str:
    try:
        if kind == "slides":
            with c.open_pdf(path) as doc:
                text = doc[0].get_text("text") if len(doc) else ""
                text = f"[{len(doc)} pages] {text}"
        elif kind == "transcripts":
            text = c.transcript_preview(proj, path, limit * 2)
        else:
            return ""
    except c.NeedsAgent as e:  # unreadable or locked: say so, keep scanning
        return f"(cannot read: {e.code}, {e.problem})"
    except Exception as e:
        return f"(cannot read: {e.__class__.__name__})"
    return re.sub(r"\s+", " ", text).strip()[:limit]


def scan(proj: c.Project) -> tuple[dict[Path, dict[str, list[Path]]], bool]:
    folders: dict[Path, dict[str, list[Path]]] = {}
    seen, truncated = 0, False
    for dirpath, dirnames, filenames in os.walk(proj.root):
        here = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith(".") and d not in c.JUNK_DIRS
                             and not proj.skipped(here / d / "_", proj.root))
        for name in sorted(filenames):
            seen += 1
            if seen > MAX_FILES:
                return folders, True
            path = here / name
            if name.startswith(".") or name.lower() in c.JUNK_FILES:
                continue
            if not any(path.suffix.lower() in s for _, _, s in KINDS):
                # Named wrong (no extension, ".download", "slides.pdf.bak"): go by content.
                kind = {"pdf": "slides", "captions": "transcripts"}.get(c.sniff(path))
                if kind:
                    folders.setdefault(here, {}).setdefault(kind, []).append(path)
                continue
            for key, _, suffixes in KINDS:
                if path.suffix.lower() in suffixes:
                    if key == "transcripts" and path.suffix.lower() == ".json" \
                            and not c.transcript_units(proj, path):
                        break  # some other JSON file
                    folders.setdefault(here, {}).setdefault(key, []).append(path)
                    break
    return folders, truncated


def main() -> int:
    args = c.parser(__doc__.split("\n\n")[0]).parse_args()
    proj = c.project(args)
    folders, truncated = scan(proj)

    def label(d: Path) -> str:
        r = proj.rel(d)
        return "(course folder itself)" if r == "." else f"{r}/"

    print(f"course folder: {proj.root.as_posix()}")
    print(f"config: {proj.rel(proj.config_path) if proj.config_path.exists() else '(none yet, using defaults)'}")
    for name, dirs in (("slides", proj.slide_dirs), ("transcripts", proj.transcript_dirs)):
        shown = ", ".join(f"{label(d)} ({'exists' if d.exists() else 'missing'})" for d in dirs)
        print(f"  [paths] {name}: {shown}")
    print()

    configured = {"slides": proj.slide_dirs, "transcripts": proj.transcript_dirs}
    for d, kinds in sorted(folders.items(), key=lambda kv: proj.rel(kv[0])):
        roles = [k for k, ds in configured.items()
                 if any(d.resolve().is_relative_to(x.resolve()) for x in ds if x.exists())]
        print(f"{label(d)}" + (f"   <- already searched as {' and '.join(roles)}" if roles else ""))
        for key, text, _ in KINDS:
            files = kinds.get(key)
            if not files:
                continue
            names = ", ".join(f.name for f in files[:SAMPLES]) + (", ..." if len(files) > SAMPLES else "")
            print(f"  {len(files)} {text}: {names}")
            p = peek(proj, key, files[0])
            if p:
                print(f"     peek {files[0].name}: {p}")
        print()

    if truncated:
        print(f"Stopped after {MAX_FILES} files: is --root really the course folder?")
    totals = {k: sum(len(v.get(k, [])) for v in folders.values()) for k, _, _ in KINDS}
    if not totals["slides"] and not totals["transcripts"]:
        found = [f"{n} {k}" for k, n in totals.items() if n]
        c.handoff("no-inputs", proj.root, "no slide PDFs and no transcripts anywhere in this folder"
                  + (f" (only: {', '.join(found)})" if found else ""),
                  "Stop. Tell the student what to add and where (SKILL.md, Find the files); do not "
                  "create folders or move files yourself.")
    else:
        print("totals: " + ", ".join(f"{n} {k}" for k, n in totals.items() if n))
    return 0


if __name__ == "__main__":
    raise SystemExit(c.run(main))
