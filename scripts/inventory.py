#!/usr/bin/env python3
"""List slide PDFs and transcript files with a short content preview.

Does not pair them. Filenames are not a pairing rule (`lec1.1` vs `lec1-1`).
The agent reads this catalog and writes <output>/pairs.json.

    python inventory.py [--root COURSE]
"""

from __future__ import annotations

import re

import common as c


def pdf_preview(path, pages: int = 2, limit: int = 900) -> tuple[int, str]:
    with c.fitz().open(path) as doc:
        text = " ".join((doc[i].get_text("text") or "") for i in range(min(pages, len(doc))))
        return len(doc), re.sub(r"\s+", " ", text).strip()[:limit]


def main() -> int:
    args = c.parser(__doc__.split("\n\n")[0]).parse_args()
    proj = c.project(args)
    paired = {}
    for p in proj.pairs():
        for field in ("slides", "transcript"):
            if p.get(field):
                paired[proj.rel(proj.path(p[field]))] = p["key"]

    slides = []
    for path in c.find_files(proj.slide_dirs, {".pdf"}):
        n, preview = pdf_preview(path)
        slides.append({"path": proj.rel(path), "name": path.name, "bytes": path.stat().st_size,
                       "pages": n, "paired_as": paired.get(proj.rel(path)), "preview": preview})
    transcripts = []
    for path in c.find_files(proj.transcript_dirs, c.TRANSCRIPT_SUFFIXES):
        preview = c.transcript_preview(proj, path)
        if path.suffix.lower() == ".json" and not preview:
            continue  # some other JSON file, not a transcript
        transcripts.append({"path": proj.rel(path), "name": path.name, "bytes": path.stat().st_size,
                            "paired_as": paired.get(proj.rel(path)), "preview": preview})

    out = proj.out / "inventory.json"
    c.write_json(out, {"slides": slides, "transcripts": transcripts})
    new_s = sum(1 for s in slides if not s["paired_as"])
    new_t = sum(1 for t in transcripts if not t["paired_as"])
    print(f"{len(slides)} slide PDFs ({new_s} unpaired), "
          f"{len(transcripts)} transcripts ({new_t} unpaired) -> {proj.rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
