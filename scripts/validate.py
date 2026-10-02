#!/usr/bin/env python3
"""Check the agent's alignment.json against extracted.json.

Prints a coverage line per lecture, then any errors and warnings.
Exit status 1 if any lecture has errors.

    python validate.py              every lecture with an alignment.json
    python validate.py --key lec1.2
"""

from __future__ import annotations

from pathlib import Path

import common as c


def check(folder: Path) -> tuple[str, list[str], list[str]]:
    """Return (coverage summary, errors, warnings) for one lecture."""
    if not (folder / "extracted.json").exists():
        return "", ["no extracted.json (run extract first)"], []
    if not (folder / "alignment.json").exists():
        return "", ["no alignment.json"], []
    ex = c.read_json(folder / "extracted.json")
    al = c.read_json(folder / "alignment.json")
    errors, warnings = [], []
    slide_ids = [s["index"] for s in ex["slides"]]
    seg_ids = {s["id"] for s in ex.get("segments", [])}
    items = al.get("assignments", [])

    seen = [int(a["slide"]) for a in items]
    if missing := sorted(set(slide_ids) - set(seen)):
        errors.append(f"slides with no assignment: {missing}")
    if extra := sorted(set(seen) - set(slide_ids)):
        errors.append(f"assignments for slides that do not exist: {extra}")
    if dup := sorted({s for s in seen if seen.count(s) > 1}):
        errors.append(f"slides assigned more than once: {dup}")

    order = sorted(items, key=lambda a: int(a["slide"]))
    flat = [i for a in order for i in (a.get("segment_ids") or [])]
    if unknown := sorted(set(flat) - seg_ids):
        errors.append(f"unknown segment ids: {unknown[:10]}")
    if dup := sorted({i for i in flat if flat.count(i) > 1}):
        errors.append(f"segments used on more than one slide: {dup[:10]}")
    mono = all(a <= b for a, b in zip(flat, flat[1:]))
    if not mono:
        errors.append("segment ids are not monotonic in slide order")
    no_notes = [int(a["slide"]) for a in order
                if a.get("segment_ids") and not (a.get("notes") or "").strip()]
    if no_notes:
        errors.append(f"slides with speech but no notes: {no_notes}")

    for part in al.get("parts", []):
        if bad := [s for s in part.get("slides", []) if s not in slide_ids]:
            errors.append(f"part {part.get('name')!r} lists missing slides {bad}")

    unused = len(seg_ids - set(flat))
    if seg_ids:
        if unused:
            warnings.append(f"{unused}/{len(seg_ids)} segments unused "
                            "(fine for boilerplate or off-topic chatter)")
        last_spoken = max((int(a["slide"]) for a in order if a.get("segment_ids")), default=0)
        tail = [int(a["slide"]) for a in order
                if int(a["slide"]) > last_spoken and not (a.get("notes") or "").strip()]
        if tail:
            warnings.append(f"slides after the recording ends have no notes: {tail} "
                            "(cut recording: add the '> **No recording**' block)")

    summary = (f"slides {len(set(seen) & set(slide_ids))}/{len(slide_ids)} "
               f"segs {len(set(flat) & seg_ids)}/{len(seg_ids)} mono={mono} unused={unused} "
               f"method={al.get('method')}")
    return summary, errors, warnings


def aligned_keys(proj: c.Project, keys: list[str] | None) -> list[str]:
    if keys:
        return keys
    if not proj.out.exists():
        return []
    return sorted(p.name for p in proj.out.iterdir() if (p / "alignment.json").exists())


def main() -> int:
    ap = c.parser(__doc__.split("\n\n")[0])
    ap.add_argument("--key", action="append", help="lecture key; repeatable")
    args = ap.parse_args()
    proj = c.project(args)
    keys = aligned_keys(proj, args.key)
    if not keys:
        print("No alignment.json found.")
        return 1
    bad = 0
    for key in keys:
        summary, errors, warnings = check(proj.out / key)
        print(f"{key}: {'OK' if not errors else 'FAIL'}  {summary}".rstrip())
        for e in errors:
            print(f"  error: {e}")
        for w in warnings:
            print(f"  warn:  {w}")
        bad += bool(errors)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
