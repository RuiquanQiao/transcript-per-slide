#!/usr/bin/env python3
"""Extract slide images/text and numbered transcript segments. Does not align or pair.

The agent writes <output>/pairs.json after reading inventory.json. Then:

    python extract.py --from-pairs                 every pair without a pack.md
    python extract.py --from-pairs --key lec1.2    only that lecture
    python extract.py --from-pairs --key lec1.2 --force    redo a packed lecture
    python extract.py --slides <pdf> [--transcript <file>] --key lec1.2
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import common as c

PAGE_PNG = re.compile(r"^\d{3}\.png$")


def clean_slide_text(proj: c.Project, raw: str) -> str:
    for rx in proj.footer_res:
        raw = rx.sub(" ", raw)
    # Beamer/LaTeX itemize bullets are often a custom glyph that PDF text
    # extraction maps to U+00D8 / U+00F8.
    return re.sub(r"[Øø]\s+", "", raw)


def slide_title(cleaned: str) -> str:
    for ln in cleaned.splitlines():
        ln = ln.strip()
        if len(ln) >= 4 and not ln.isdigit():
            return re.sub(r"\s+", " ", ln)[:80]
    return "(no extractable title)"


def extract_slides(proj: c.Project, pdf: Path, pages_dir: Path) -> list[dict]:
    fitz = c.fitz()
    opts = proj.cfg["slides"]
    pages_dir.mkdir(parents=True, exist_ok=True)
    for old in pages_dir.iterdir():  # only our own NNN.png; anything else is left alone
        if PAGE_PNG.match(old.name):
            old.unlink()
    zoom = float(opts["zoom"])
    slides = []
    with fitz.open(pdf) as doc:
        for i, page in enumerate(doc, start=1):
            raw = page.get_text("text") or ""
            if opts["border"]:
                # Stroke the page edge so white slides don't vanish on a white preview.
                r = page.rect
                page.draw_rect(fitz.Rect(r.x0 + 5, r.y0 + 5, r.x1 - 5, r.y1 - 5),
                               color=(0.12, 0.12, 0.12), width=4.5, overlay=True)
            png = pages_dir / f"{i:03d}.png"
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(png)
            cleaned = clean_slide_text(proj, raw)
            slides.append({
                "index": i,
                "title": slide_title(cleaned),
                "text": re.sub(r"\s+", " ", cleaned).strip(),
                "image": png.name,
            })
    return slides


def segment(proj: c.Project, units: list[dict]) -> list[dict]:
    """Cut units into ~sentence-sized numbered segments the agent can assign to slides."""
    min_chars = int(proj.cfg["transcript"]["min_segment_chars"])
    pause = float(proj.cfg["transcript"]["pause_split_seconds"])
    segments: list[dict] = []
    buf, buf_start, buf_speaker, last_end = "", None, None, None

    def flush():
        nonlocal buf, buf_start
        if buf:
            seg = {"id": len(segments), "raw_text": buf}
            if buf_speaker:
                seg["speaker"] = buf_speaker
            if buf_start is not None:
                seg["start"] = c._hms(buf_start)
            segments.append(seg)
        buf, buf_start = "", None

    for u in units:
        if u["speaker"] != buf_speaker or u.get("block"):
            flush()
            buf_speaker = u["speaker"]
        # A silence usually means the lecturer moved to the next slide.
        if pause and u["start"] is not None and last_end is not None and u["start"] - last_end >= pause:
            flush()
        last_end = u["end"]
        for bit in (s.strip() for s in c.SENTENCE_RE.split(u["text"])):
            if not bit:
                continue
            if not buf:
                buf_start = u["start"]
            buf = f"{buf} {bit}".strip()
            if len(buf) >= min_chars and re.search(r"[.!?]$", buf):
                flush()
            elif len(buf) >= min_chars * 4:  # captions without punctuation
                flush()
    flush()
    return segments


def extract_one(proj: c.Project, key: str, slides_pdf: Path, transcript: Path | None) -> Path:
    folder = proj.out / key
    slides = extract_slides(proj, slides_pdf, folder / "pages")
    segments = []
    if transcript:
        if not transcript.exists():
            sys.exit(f"{key}: transcript not found: {transcript}")
        segments = segment(proj, c.transcript_units(proj, transcript))
        if not segments:
            print(f"{key}: warning: no text could be read from {proj.rel(transcript)}")
    out = folder / "extracted.json"
    c.write_json(out, {
        "key": key,
        "slides_pdf": proj.rel(slides_pdf),
        "transcript": proj.rel(transcript) if transcript else None,
        "slides": slides,
        "segments": segments,
    })
    print(f"{key}: {len(slides)} slides, {len(segments)} segments -> {proj.rel(out)}")
    return out


def main() -> int:
    ap = c.parser("Extract slides and transcript segments. Does not align or pair.")
    ap.add_argument("--from-pairs", action="store_true", help="read <output>/pairs.json written by the agent")
    ap.add_argument("--force", action="store_true", help="re-extract even if <key>/pack.md already exists")
    ap.add_argument("--key", action="append", help="lecture key; repeatable with --from-pairs")
    ap.add_argument("--slides", type=Path)
    ap.add_argument("--transcript", type=Path)
    args = ap.parse_args()
    proj = c.project(args)
    proj.out.mkdir(parents=True, exist_ok=True)

    if args.from_pairs:
        pairs = proj.pairs()
        if not pairs:
            sys.exit(f"No {proj.rel(proj.pairs_path)}. Inventory materials, then the agent "
                     "must pair files by reading them.")
        if args.key:
            unknown = sorted(set(args.key) - {p["key"] for p in pairs})
            if unknown:
                sys.exit(f"Not in pairs.json: {', '.join(unknown)}")
            pairs = [p for p in pairs if p["key"] in args.key]
        status = 0
        for pair in pairs:
            key = pair["key"]
            if proj.packed(key) and not args.force:
                print(f"{key}: already packed, skip")
                continue
            slides_pdf = proj.path(pair["slides"])
            transcript = proj.path(pair["transcript"]) if pair.get("transcript") else None
            missing = [proj.rel(p) for p in (slides_pdf, transcript) if p and not p.exists()]
            if missing:  # report and carry on with the other lectures
                print(f"{key}: error: file in pairs.json not found: {', '.join(missing)}")
                status = 1
                continue
            extract_one(proj, key, slides_pdf, transcript)
        return status

    if not args.slides or not args.key or len(args.key) != 1:
        ap.error("pass --from-pairs, or --slides and one --key (optional --transcript)")
    extract_one(proj, args.key[0], proj.path(args.slides),
                proj.path(args.transcript) if args.transcript else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
