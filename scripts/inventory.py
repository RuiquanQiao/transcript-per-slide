#!/usr/bin/env python3
"""List slide PDFs and transcript files with a short content preview.

Does not pair them. Filenames are not a pairing rule (`lec1.1` vs `lec1-1`).
The agent reads this catalog and writes <output>/pairs.json.

Files are sorted by what they are, not what they are called: a PDF saved
without .pdf is still slides, a .txt full of caption timings is still captions.
Anything in the slide or transcript folders that cannot be used as it is
(PowerPoint, video, Word, unknown files, unreadable or locked PDFs, slides with
no text) is handed to the agent with a NEEDS AGENT block.

    python inventory.py [--root COURSE]
"""

from __future__ import annotations

import contextlib
import re
from collections import defaultdict

import common as c

# What the agent does with files the scripts cannot use as they are (see references/handoffs.md).
OTHER = {
    "deck": ("deck", "PowerPoint/Keynote decks, not PDF",
             "Ask the student to export each as PDF (File > Export > PDF) into the slides folder, "
             "or convert them yourself if LibreOffice is installed (handoffs.md#deck)."),
    "media": ("no-transcript", "video/audio recordings; the scripts cannot listen to them",
              "Ask for the transcript download from the recording platform (Echo360, Panopto, Teams, "
              "Zoom; .vtt is best), or Whisper (handoffs.md#no-transcript)."),
    "word": ("word-file", "Word/RTF documents (Teams transcripts come as .docx)",
             "If a transcript: get the .vtt instead, or write its text into <output>/_converted/<name>.txt "
             "and pair that with transcript_from (handoffs.md#word-file)."),
    "pdf-in-transcripts": ("pdf-in-transcripts", "PDFs in a transcripts-only folder",
                           "Slides? Add the folder to [paths] slides. A transcript saved as PDF? Write "
                           "its text into <output>/_converted/<name>.txt and pair that (handoffs.md#pdf-in-transcripts)."),
    "json": ("unknown-format", "JSON files that are not a transcript format the scripts read",
             "If another speech-to-text tool's output: convert to .vtt in <output>/_converted/ keeping "
             "the times (handoffs.md#unknown-format). Otherwise add to [paths] ignore."),
}
UNRECOGNIZED = ("unrecognized-file", "files the scripts do not recognize",
                "Open them and decide (handoffs.md#unrecognized-file): a transcript can be paired as it "
                "is (the scripts read by content); slides in another form need converting; anything "
                "that is not lecture material goes in [paths] ignore so you are not asked again.")


def pdf_preview(path, pages: int = 2, limit: int = 900) -> tuple[int, str]:
    with c.open_pdf(path) as doc:
        text = " ".join((doc[i].get_text("text") or "") for i in range(min(pages, len(doc))))
        return len(doc), re.sub(r"\s+", " ", text).strip()[:limit]


def text_peek(path, limit: int = 200) -> str:
    if c.sniff(path) not in {"text", "captions", "json"}:
        return ""
    return re.sub(r"\s+", " ", c.read_text_any(path)[:limit * 2]).strip()[:limit]


def main() -> int:
    args = c.parser(__doc__.split("\n\n")[0]).parse_args()
    proj = c.project(args)
    paired = proj.paired_files()
    slide_paths, transcript_paths, others = proj.inputs()

    def settled(path) -> contextlib.AbstractContextManager:
        # A paired file (or the original of a converted copy) was already dealt with: preview it,
        # but do not raise its problems again on every run.
        return c.quietly() if paired.get(proj.rel(path)) else contextlib.nullcontext()

    slides = []
    for path in slide_paths:
        entry = {"path": proj.rel(path), "name": path.name, "bytes": path.stat().st_size,
                 "paired_as": paired.get(proj.rel(path))}
        with settled(path):
            try:
                n, preview = pdf_preview(path)
            except c.NeedsAgent as e:  # one bad deck must not stop the catalog
                if e.code == "missing-dependency":
                    raise
                c.handoff_from(e)
                entry["problem"] = e.code
                n, preview = 0, ""
            else:
                if n and not preview:
                    c.handoff("pdf-no-text", path, "no text on its first pages (scanned, or slides exported "
                              "as images)", "Pair it by looking at the pages (open the PDF itself). After "
                              "extract, give each slide a `title` in alignment.json (handoffs.md#pdf-no-text).")
        slides.append({**entry, "pages": n, "preview": preview})
    transcripts = []
    for path in transcript_paths:
        with settled(path):
            preview = c.transcript_preview(proj, path)
        if not preview and not paired.get(proj.rel(path)):
            c.handoff("transcript-empty", path, "no text could be read from it",
                      "Open it. If it is empty, ask the student to download it again; if the text is "
                      "there in a layout the scripts miss, convert it (handoffs.md#transcript-empty).")
        transcripts.append({"path": proj.rel(path), "name": path.name, "bytes": path.stat().st_size,
                            "paired_as": paired.get(proj.rel(path)), "preview": preview})

    unpaired_others = [(p, k) for p, k in others if not paired.get(proj.rel(p))]
    groups = defaultdict(list)
    for path, kind in unpaired_others:
        groups[OTHER.get(kind, UNRECOGNIZED)].append(path)
    for (code, what, do), paths in groups.items():
        with c.quietly():
            details = [f"{proj.rel(p)}" + (f"   peek: {pk}" if (pk := text_peek(p)) else "")
                       for p in paths[:12]]
        if len(paths) > 12:
            details.append(f"... and {len(paths) - 12} more")
        c.handoff(code, f"{len(paths)} file(s)", what, do, details=details)

    out = proj.out / "inventory.json"
    c.write_json(out, {"slides": slides, "transcripts": transcripts,
                       "other": [{"path": proj.rel(p), "kind": k, "paired_as": paired.get(proj.rel(p))}
                                 for p, k in others]})
    new_s = sum(1 for s in slides if not s["paired_as"])
    new_t = sum(1 for t in transcripts if not t["paired_as"])
    print(f"{len(slides)} slide PDFs ({new_s} unpaired), "
          f"{len(transcripts)} transcripts ({new_t} unpaired) -> {proj.rel(out)}")
    # No transcripts is only a problem while there are decks waiting for one
    # (a lecture paired with "transcript": null was a decision, not a gap).
    if not slides or (not transcripts and new_s):
        searched = ", ".join(f"{proj.rel(d)}/" for d in proj.slide_dirs + proj.transcript_dirs)
        missing = "slide PDFs or transcripts" if not slides and not transcripts else \
            "slide PDFs" if not slides else "transcripts"
        c.handoff("no-inputs", searched, f"no {missing} found in the configured folders",
                  "Run locate.py and point [paths] at the right folders; if the files are not in the "
                  "course folder at all, tell the student what to add (SKILL.md, Find the files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(c.run(main))
