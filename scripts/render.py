#!/usr/bin/env python3
"""Render <output>/<key>/pack.md from the agent-written alignment.json.

Tutoring blocks (<!-- note:N --> ... <!-- /note:N -->) already in pack.md are
kept; everything else is regenerated. If pack.md was edited by hand outside
those blocks, the lecture is not rendered (the edits are listed) unless
--discard-edits is given.

    python render.py --all              every aligned lecture without a pack.md
    python render.py --all --force      ... including packed ones
    python render.py --key lec1.1       that lecture, packed or not
    python render.py --key lec1.1 --draft   render even if validation fails
"""

from __future__ import annotations

import common as c
from validate import aligned_keys, check


def outside_notes(text: str) -> list[str]:
    """Non-blank lines of a pack that are not inside a tutoring block."""
    return [ln.rstrip() for ln in c.NOTE_RE.sub("", text).splitlines() if ln.strip()]


def would_lose(old: str, new: str) -> list[str]:
    """Lines written into pack.md by hand (outside tutoring blocks) that a re-render drops."""
    kept = set(outside_notes(new))
    return [ln for ln in outside_notes(old)
            if ln not in kept and not ln.startswith(("Slides: ", "Transcript: "))]


def render_one(proj: c.Project, key: str, discard_edits: bool = False) -> bool:
    folder = proj.out / key
    ex = c.read_json(folder / "extracted.json")
    al = c.read_json(folder / "alignment.json")
    pack = folder / "pack.md"
    kept = c.kept_notes(pack)

    notes_of: dict[int, str] = {}
    has_speech: dict[int, bool] = {}
    notice_of: dict[int, str] = {}
    for item in al["assignments"]:
        idx = int(item["slide"])
        if notes := (item.get("notes") or "").strip():
            notes_of[idx] = notes
        has_speech[idx] = bool(item.get("segment_ids"))
        if item.get("notice"):
            notice_of[idx] = str(item["notice"])
    part_of = {int(i): p["name"] for p in al.get("parts", []) for i in p["slides"]}

    lines = [f"# {key}", "",
             f"Slides: `{ex.get('slides_pdf', '')}`  ",
             f"Transcript: `{ex.get('transcript') or '(none yet)'}`", ""]
    if notice_of:
        lines += ["**★ Notices (marks, exams, deadlines, assignments, access)**", ""]
        lines += [f"- ★ [{notice_of[s['index']]}] {s['index']}. {s['title']}"
                  for s in ex["slides"] if s["index"] in notice_of]
        lines.append("")

    current = None
    for s in ex["slides"]:
        idx = s["index"]
        part = part_of.get(idx, "Lecture")
        if part != current:
            if current is not None:
                lines += ["---", ""]
            lines += [f"## {part}", ""]
            current = part
        star = f"★ [{notice_of[idx]}] " if idx in notice_of else ""
        lines += [f"### {star}{idx}. {s['title']}", "", f"![Slide {idx}](pages/{s['image']})", ""]
        if idx in notes_of:
            lines += [notes_of[idx], ""]
        elif ex.get("transcript"):
            if has_speech.get(idx):
                lines += ["_Notes not written yet._", ""]
            else:
                lines += ["_No spoken stretch belongs on this page (title, skip, or silent)._", ""]
        lines.append(f"<!-- note:{idx} -->")
        if idx in kept:
            lines.append(kept[idx])
        lines += [f"<!-- /note:{idx} -->", ""]

    # Never drop tutoring the student kept, even if the deck lost that slide.
    orphans = sorted(set(kept) - {s["index"] for s in ex["slides"]})
    if orphans:
        lines += ["---", "", "## Tutoring notes from slides that no longer exist", ""]
        for k in orphans:
            lines += [f"<!-- note:{k} -->", kept[k], f"<!-- /note:{k} -->", ""]
    new = "\n".join(lines)
    if pack.exists() and not discard_edits:
        lost = would_lose(pack.read_text(encoding="utf-8", errors="replace"), new)
        if lost:
            print(f"{key}: NOT rendered: pack.md has {len(lost)} line(s) outside the tutoring "
                  "blocks that are not in alignment.json and would be lost:")
            for ln in lost[:15]:
                print(f"    {ln[:110]}")
            if len(lost) > 15:
                print(f"    ... and {len(lost) - 15} more")
            print("  Move them into alignment.json notes or a <!-- note:N --> block, "
                  "or pass --discard-edits.")
            return False
    pack.write_text(new, encoding="utf-8")
    print(f"{key}: rendered {proj.rel(pack)}")
    return True


def main() -> int:
    ap = c.parser("Render pack.md from alignment.json.")
    ap.add_argument("--all", action="store_true", help="every lecture with an alignment.json")
    ap.add_argument("--key", action="append", help="lecture key; repeatable")
    ap.add_argument("--force", action="store_true", help="with --all: re-render packed lectures too")
    ap.add_argument("--draft", action="store_true", help="render even if validation fails")
    ap.add_argument("--discard-edits", action="store_true",
                    help="overwrite even if pack.md has hand edits outside the tutoring blocks")
    args = ap.parse_args()
    if not args.all and not args.key:
        ap.error("pass --all or --key")
    proj = c.project(args)
    keys = aligned_keys(proj, args.key)
    if not keys:
        print("No alignment.json files found. Extract, then align as an agent, then render.")
        return 1
    status = 0
    for key in keys:
        if not args.key and proj.packed(key) and not args.force:
            print(f"{key}: already packed, skip")
            continue
        folder = proj.out / key
        if not (folder / "extracted.json").exists() or not (folder / "alignment.json").exists():
            print(f"{key}: needs both extracted.json and alignment.json, skip")
            status = 1
            continue
        summary, errors, _ = check(folder)
        if errors and not args.draft:
            print(f"{key}: not rendered, alignment has {len(errors)} error(s); run validate.py "
                  "(or --draft to preview anyway)")
            status = 1
            continue
        if not render_one(proj, key, args.discard_edits):
            status = 1
    proj.ensure_study_readme()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
